"""Helpers that are only needed in the engine directory"""
import random
from numba import njit
from Utils.helper import stage_to_multiplier, get_type_effectiveness
from Engine.status_calc import after_turn_status, freeze, paralysis, B_P
from Models.idx_const import Pok, Move, Sec, Field, POK_LEN, MOVE_STRIDE, OFFSET_MOVE, Flags
from Models.helper import (
    Status, VolStatus, Types, Weather, AbilityActivation, MoveCategory, TARGET_SELF_SIDE,
    STEEL_POISON
)
from Models.constants import (
    _POK_SPEED, _POK_STATUS, _STATUS_PARALYSIS, _POK_SPEED_STAT_STAGE, _POK_AB_WHEN,
    _ABILITYACTIVATION_ON_MODIFY_SPEED, _WEATHER_SUN,_ABILITYNAMES_CHLOROPHYLL,
    _POK_AB_ID
)
from DataBase.AbilitiesDB import AbilityNames
from DataBase.MoveDB import MoveName


SANDSTORM_IM = {Types.ROCK, Types.GROUND, Types.STEEL}
DAMP_IGNORES = {MoveName.EXPLOSION, MoveName.SELFDESTRUCT}
WEATHER_NOT_END_OF_TURN = {0, Weather.RAIN}


@njit
def check_speed(p1, p2, weather):
    """Gives speed after modifications of stages, paralysis and Abilities"""
    p1_speed = p1[_POK_SPEED]
    p2_speed = p2[_POK_SPEED]
    if p1[_POK_STATUS] == _STATUS_PARALYSIS:
        p1_speed //= 4
    if p2[_POK_STATUS] == _STATUS_PARALYSIS:
        p2_speed //= 4
    # Apply Stat stages if necessary
    if p1[_POK_SPEED_STAT_STAGE] != 0:
        p1_speed = stage_to_multiplier(p1[_POK_SPEED_STAT_STAGE], p1_speed)
    if p2[_POK_SPEED_STAT_STAGE] != 0:
        p2_speed = stage_to_multiplier(p2[_POK_SPEED_STAT_STAGE], p2_speed)
    ab_w1 = p1[_POK_AB_WHEN]
    ab_w2 = p2[_POK_AB_WHEN]
    if ab_w1 & _ABILITYACTIVATION_ON_MODIFY_SPEED:
        ab = p1[_POK_AB_ID]
        if weather == _WEATHER_SUN and ab == _ABILITYNAMES_CHLOROPHYLL:
            p1_speed *= 2
    if ab_w2 & _ABILITYACTIVATION_ON_MODIFY_SPEED:
        ab = p2[_POK_AB_ID]
        if weather == _WEATHER_SUN and ab == _ABILITYNAMES_CHLOROPHYLL:
            p2_speed *= 2
    return p1_speed, p2_speed


def move_speed_tie(p1, m1, p2, m2):
    """Get at random the order"""
    if random.getrandbits(1):
        return [(p1, m1, p2), (p2, m2, p1)]
    return [(p2, m2, p1), (p1, m1, p2)]


def move_order(p1, my_move, p2, opp_move, p1_switch, p2_switch, weather):
    """Calculates the order which the what move should be played
    Returns:

    [('Faster Pokemon', 'Move of Faster Pokemon', 'Slower Pokemon'),
        ('Slower Pokemon, 'Move of Slower Pokemon', 'Faster Pokemon')]"""
    if p1_switch and p2_switch:
        return []

    move_offset = MOVE_STRIDE
    base_offset = OFFSET_MOVE

    if p1_switch:
        move2 = p2[
            base_offset + (move_offset * opp_move):
            base_offset + (move_offset * (opp_move + 1))
        ] if opp_move != 10 else 10
        return [(p2, move2, p1)]
    if p2_switch:
        move1 = p1[
            base_offset + (move_offset * my_move):
            base_offset + (move_offset * (my_move + 1))
        ] if opp_move != 10 else 10
        return [(p1, move1, p2)]

    strug1 = False
    strug2 = False
    if my_move < 4:
        move1 = p1[
            base_offset + (move_offset * my_move):
            base_offset + (move_offset * (my_move + 1))
        ]
    else:
        move1 = my_move
        strug1 = True
    if opp_move < 4:
        move2 = p2[
            base_offset + (move_offset * opp_move):
            base_offset + (move_offset * (opp_move + 1))
        ]
    else:
        move2 = opp_move
        strug2 = True

    p1_speed, p2_speed = check_speed(p1, p2, weather)

    move1_prio = move1[Move.PRIORITY] if not strug1 else 0
    move2_prio = move2[Move.PRIORITY] if not strug2 else 0

    if (
        (move1_prio != 0 or move2_prio != 0)
        and move1_prio != move2_prio
    ):
        if move1_prio > move2_prio:
            order = [(p1, move1, p2), (p2, move2, p1)]
        else:
            order = [(p2, move2, p1), (p1, move1, p2)]
    else:
        if p1_speed > p2_speed:
            order = [(p1, move1, p2), (p2, move2, p1)]
        elif p2_speed > p1_speed:
            order = [(p2, move2, p1), (p1, move1, p2)]
        else:
            order = move_speed_tie(p1, move1, p2, move2)

    return order


class MoveOutcome:
    """Possible moves outcomes"""
    HIT               = 1
    MISS              = 2
    INVULNERABLE      = 3
    SEMI_INVULNERABLE = 4


def ab_on_try_move(move, attacker, defender, accuracy, weather) -> bool:
    """
    Check to see if the ability changes the probabilty of a move hitting
    """
    atk_ab = attacker[_POK_AB_ID]
    def_ab = defender[_POK_AB_ID]
    target = move[Move.TARGET]
    if move in DAMP_IGNORES and (
        atk_ab == AbilityNames.DAMP  #pylint: disable=consider-using-in
        or def_ab == AbilityNames.DAMP
    ):
        return 0
    if (
        atk_ab == AbilityNames.HUSTLE
        and move[Move.CATEGORY] == MoveCategory.PHYSICAL
        and not move[Move.OH_KO]
    ):
        return (accuracy*3277)//4096
    if (
        def_ab == AbilityNames.SAND_VEIL
        and weather == Weather.SANDSTORM
    ):
        return (accuracy*3277)//4096
    if (
        move[Flags.SOUND]
        and (
            def_ab == AbilityNames.SOUNDPROOF
            or (
                atk_ab == AbilityNames.SOUNDPROOF
                and target in TARGET_SELF_SIDE
            )
        )
    ):
        return 0

    return accuracy


def calculate_hit_miss(move, attacker, defender, weather):
    '''Returns a boolean if the move passed the accuracy check'''
    # TODO: Semi invulnerable states, like Fly, dig etc.
    if isinstance(move, int):  #Struggle
        return MoveOutcome.HIT
    move_acc = move[Move.ACCURACY]

    ab_a = attacker[_POK_AB_WHEN]
    ab_d = defender[_POK_AB_WHEN]
    if ab_a & AbilityActivation.ON_TRY_MOVE or ab_d & AbilityActivation.ON_TRY_MOVE:
        move_acc = ab_on_try_move(move, attacker, defender, move_acc, weather)

    if get_type_effectiveness(move[Move.TYPE], defender[Pok.TYPE1], defender[Pok.TYPE2]) == 0:
        return MoveOutcome.INVULNERABLE

    if move_acc == -1:
        return MoveOutcome.HIT
    if move_acc == 0:
        return MoveOutcome.MISS

    acc_stage = attacker[Pok.ACCURACY_STAT_STAGE] - defender[Pok.EVASION_STAT_STAGE]
    if acc_stage > 0:
        accuracy = move_acc*(acc_stage+3)/3
    elif acc_stage < 0:
        accuracy = move_acc*(3)/(3+acc_stage)
    else:
        accuracy = move_acc

    if accuracy == 100 or random.random()*100 < accuracy:
        return MoveOutcome.HIT
    return MoveOutcome.MISS


def calculate_crit():
    """Returns a boolean if the move passed the crit check"""
    return random.getrandbits(4) + 1 == 1


def reset_switch_out(pok):
    """If a pokemon swithces out it needs to reset these conditions"""
    pok[Pok.ATTACK_STAT_STAGE : Pok.EVASION_STAT_STAGE + 1] = 0
    pok[Pok.VOL_STATUS] = 0
    pok[Pok.BADLY_POISON] = 1 if pok[_POK_STATUS] == Status.TOXIC else 0


def flinch_checker(move, defender):
    """Returns true or false if move has a flinch percent and it should flinch"""
    flinch = move[Sec.VOL_STATUS]
    if flinch != 0 and flinch & VolStatus.FLINCH:
        if defender[_POK_AB_ID] == AbilityNames.INNER_FOCUS:
            return False
        if random.random()*100 < move[Sec.CHANCE]:
            return True

    return False


def thaw(move, defender):
    """Check if a move thaws"""
    if move[Move.TYPE] == Types.FIRE:
        defender[_POK_STATUS] = 0
        return True
    return False


def switch_in(attacker, defender):
    """
    What happens when a pokemon switches in so, abilities, hazards
    """
    # TODO: Hazards damage, take in consideration that the pokemon needs to
    # be alive to activiate the ability so before the ability do something like
    # if attacker[Pok.CURRENT_HP] > 0:
    if attacker[_POK_AB_WHEN] & AbilityActivation.ON_SWITCH_IN:
        ability = attacker[_POK_AB_ID]
        if ability == AbilityNames.INTIMIDATE:
            defender[Pok.ATTACK_STAT_STAGE] -= 1


def start_of_battle(array):
    """Select the two first pokemon of each team and does ability effects on switch in
    for each following their speed"""
    # TODO: Switch in abilities like Intimidate, Drought etc.
    # Order of entry is in account for things like Drought against Drizzle
    current_pokemon = array[
            (array[Field.MY_POK] * POK_LEN):((array[Field.MY_POK]+1) * POK_LEN)
        ]
    current_opp = array[
            ((array[Field.OPP_POK]+6) * POK_LEN):((array[Field.OPP_POK]+7) * POK_LEN)
        ]
    weather = array[Field.WEATHER]
    p1_speed, p2_speed = check_speed(current_pokemon, current_opp, weather)
    speed_tie = 0
    if p1_speed == p2_speed:
        speed_tie = random.getrandbits(1)
    if speed_tie or p1_speed > p2_speed:
        switch_in(current_pokemon, current_opp)
        switch_in(current_opp, current_pokemon)
    else:
        switch_in(current_opp, current_pokemon)
        switch_in(current_pokemon, current_opp)
    current_pokemon[Pok.TURNS] = 1
    current_opp[Pok.TURNS] = 1
    array[Field.TURN] = 1


def weather_dmg(pokemon, weather, max_hp):
    """
    Weather damage calc
    """
    type1 = pokemon[Pok.TYPE1]
    type2 = pokemon[Pok.TYPE2]
    abi = pokemon[Pok.AB_ID]
    if weather == Weather.SANDSTORM:
        if (
            type1 != Types.ROCK and type1 != Types.GROUND and type1 != Types.STEEL
            and type2 != Types.ROCK and type2 != Types.GROUND and type2 != Types.STEEL
            and abi != AbilityNames.SAND_VEIL
        ):
            return max_hp//16
        return 0
    if weather == Weather.HAIL:
        if type1 != Types.ICE and type2!= Types.ICE:
            return max_hp//16
        return 0
    if weather == Weather.SUN:
        if abi == AbilityNames.SOLAR_POWER:
            return max_hp//8
        return 0
    return 0


def after_turn_damage(pokemon, weather: int) -> int:
    """Calculate all damage sources that comes at the end of turns"""
    # 1. Absolute Immunity Early Exit
    if pokemon[Pok.AB_ID] == AbilityNames.MAGIC_GUARD:
        return 0
    max_hp = pokemon[Pok.MAX_HP]
    dmg = 0
    if pokemon[Pok.STATUS] in B_P:
        dmg += after_turn_status(pokemon)
    if weather not in WEATHER_NOT_END_OF_TURN:
        dmg += weather_dmg(pokemon, weather, max_hp)

    return dmg


def early_returns(attacker, defender, idx: int, flinch: bool, move) -> bool:  # pylint: disable=too-many-return-statements
    """Early returns to see if an attack goes through or not"""
    atker_status = attacker[_POK_STATUS]
    # Check for Sleep and if the attacker wakes up, TODO: Sleep Talk and Snore
    if atker_status == Status.SLEEP:
        if attacker[Pok.SLEEP_COUNTER] > 0:
            attacker[Pok.SLEEP_COUNTER] -= 1
            return True
        attacker[_POK_STATUS] = 0
    # Check for Paralysis
    if (
        atker_status == _STATUS_PARALYSIS
        and paralysis()
        and defender[Pok.AB_ID] != AbilityNames.MAGIC_GUARD  #Gen 4 exclusive
    ):
        return True
    # Freeze
    if atker_status == Status.FREEZE:
        if freeze():
            return True
        attacker[_POK_STATUS] = 0
    # Flinch
    if idx >= 2 and flinch:
        return True
    # Volatile Status early returns, only not implemented confusion for now
    if attacker[Pok.VOL_STATUS] != 0 and attacker[Pok.VOL_STATUS] & VolStatus.CONFUSION:
        if random.getrandbits(1):
            return True
    # In cases like after recoil damage, selfdestruct, etc.
    if defender[Pok.CURRENT_HP] <= 0:
        if not isinstance(move,int) and move[Move.TARGET] in TARGET_SELF_SIDE:
            return False
        #TODO: Some moves still go through, like dig, future sight
        return True
    return False


def contact_ability(attacker, defender):
    """
    Abilities that activate with contact
    """
    if defender[Pok.AB_ID] == AbilityNames.POISON_POINT:
        if (
            attacker[Pok.STATUS] == 0
            and (
                attacker[Pok.TYPE1] not in STEEL_POISON
                or attacker[Pok.TYPE2] not in STEEL_POISON
            )
            and random.random() < .30
        ):
            attacker[Pok.STATUS] = Status.POISON


def heal_end_turn(self_, weather):
    """
    Heals after turns, from items, abilities and volatile conditions
    """
    heal = 0
    max_hp = self_[Pok.MAX_HP]
    if self_[Pok.AB_ID] == AbilityNames.RAIN_DISH and weather == Weather.RAIN:
        heal += max_hp//16

    if heal:
        hp_missing = max_hp - self_[Pok.CURRENT_HP]
        heal = min(heal,hp_missing)
        self_[Pok.CURRENT_HP] += heal


def on_residual(pokemon, action):
    """
    On residual abilities at end of turn
    """
    abi = pokemon[Pok.AB_ID]
    if abi == AbilityNames.SPEED_BOOST and action >= 0:
        pokemon[Pok.SPEED_STAT_STAGE] = max(-6, min(6, pokemon[Pok.SPEED_STAT_STAGE] + 1))
