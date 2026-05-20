"""Helpers that are only needed in the engine directory"""
import random
from numba import njit
from Utils.helper import stage_to_multiplier, get_type_effectiveness
from Engine.damage_calc import calculate_damage_confusion
from Engine.status_calc import after_turn_status, freeze, paralysis
from Models.idx_const import Pok, Move, Sec, Field, POK_LEN, MOVE_STRIDE, OFFSET_MOVE
from Models.helper import (
    Status, VolStatus, Types, Weather, AbilityActivation, MoveCategory, TARGET_SELF_SIDE
)
from Models.constants import (
    _POK_SPEED, _POK_STATUS, _STATUS_PARALYSIS, _POK_SPEED_STAT_STAGE, _POK_AB_WHEN,
    _ABILITYACTIVATION_ON_MODIFY_SPEED, _WEATHER_SUN,_ABILITYNAMES_CHLOROPHYLL,
    _POK_AB_ID
)
from DataBase.PkDB import PokemonName
from DataBase.AbilitiesDB import AbilityNames
from DataBase.MoveDB import MoveName


SANDSTORM_IM = {Types.ROCK, Types.GROUND, Types.STEEL}
DAMP_IGNORES = {MoveName.EXPLOSION, MoveName.SELFDESTRUCT}
WEATHER_NOT_END_OF_TURN = {0, _WEATHER_SUN, Weather.RAIN}


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


def ab_on_try_move(move, attacker, defender, accuracy) -> bool:
    """
    Check to see if the ability changes the probabilty of a move hitting
    """
    atk_ab = attacker[_POK_AB_ID]
    def_ab = defender[_POK_AB_ID]
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

    return accuracy


def calculate_hit_miss(move, attacker, defender):
    '''Returns a boolean if the move passed the accuracy check'''
    # TODO: Semi invulnerable states, like Fly, dig etc.
    if isinstance(move, int):
        return MoveOutcome.HIT
    move_acc = move[Move.ACCURACY]

    ab_a = attacker[_POK_AB_WHEN]
    ab_d = defender[_POK_AB_WHEN]
    if ab_a & AbilityActivation.ON_TRY_MOVE or ab_d & AbilityActivation.ON_TRY_MOVE:
        move_acc = ab_on_try_move(move, attacker, defender, move_acc)

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

    if random.random() <= accuracy/100:
        return MoveOutcome.HIT
    return MoveOutcome.MISS


def calculate_crit():
    """Returns a boolean if the move passed the crit check"""
    crit_roll = random.getrandbits(4) + 1  # 1/16 chance of a crit
    iscrit = crit_roll == 1
    return iscrit


def reset_switch_out(pok):
    """If a pokemon swithces out it needs to reset these conditions"""
    pok[Pok.ATTACK_STAT_STAGE : Pok.EVASION_STAT_STAGE + 1] = 0
    pok[Pok.VOL_STATUS] = 0
    pok[Pok.BADLY_POISON] = 1 if pok[_POK_STATUS] == Status.TOXIC else 0


def flinch_checker(move, defender):
    """Returns true or false if move has a flinch percent and it should flinch"""
    flinch = move[Sec.VOL_STATUS]
    chance = move[Sec.CHANCE] / 100
    if flinch != 0 and flinch & VolStatus.FLINCH:
        if defender[_POK_AB_ID] == AbilityNames.INNER_FOCUS:
            return False
        if random.random() <= chance:
            return True

    return False


def confusion(attacker, my_pok):
    """Calculates confusion turn"""
    if attacker == my_pok:
        print(f"{attacker.name} is confused!")
    else:
        print(f'Enemy {attacker.name} is confused!')
    if random.getrandbits(1):
        print('it hurt itself in its confusion!')
        dmg = calculate_damage_confusion(attacker)
        attacker.current_hp -= dmg
        print(f'{attacker.name} lost {dmg} HP')
        if attacker.current_hp <= 0:
            attacker.fainted = True
            if attacker == my_pok:
                print(f"{attacker.name} fainted!")
            else:
                print(f"Enemy {attacker.name} fainted!")
        return True
    return False


def vol_early_returns(attacker, my_pok):
    """If any volatile condition stops the move, like confusion, attract, charge moves"""
    new_status = []
    for v in attacker.vol_status:
        status = v.get('name', 0)
        turns = v.get('turns', 0)
        if status == 'confusion':
            if turns > 0:
                v['turns'] -= 1
                return confusion(attacker, my_pok)
            print('Confusion has faded.')
        else:
            new_status.append(v)

    attacker.vol_status = new_status
    return False


def thaw(move, defender):
    """Check if a move thaws"""
    if move[Move.TYPE] == Types.FIRE:
        defender[_POK_STATUS] = 0
        print(f"{PokemonName(defender[Pok.ID]).name.capitalize()} has thawed out!")
        return True
    return False


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
    speed_tie_1 = False
    speed_tie_2 = False
    if p1_speed == p2_speed:
        if random.getrandbits(1):
            speed_tie_1 = True
        else:
            speed_tie_2 = True
    if speed_tie_1 or p1_speed > p2_speed:
        pass
    elif speed_tie_2 or p2_speed > p1_speed:
        pass
    else:
        raise ValueError("Shouldn't get here")
    current_pokemon[Pok.TURNS] = 1
    current_opp[Pok.TURNS] = 1


def after_turn_damage(pokemon, weather: int) -> int:
    """Calculate all damage sources that comes at the end of turns"""
    if weather in WEATHER_NOT_END_OF_TURN and pokemon[_POK_STATUS] == 0:
        return 0
    dmg = 0
    max_hp = pokemon[Pok.MAX_HP]
    dmg += after_turn_status(pokemon)
    type1_2= (pokemon[Pok.TYPE1],pokemon[Pok.TYPE2])
    if weather == Weather.SANDSTORM and not SANDSTORM_IM.isdisjoint(type1_2):
        dmg += max_hp // 16
    elif weather == Weather.HAIL and Types.ICE not in type1_2:
        dmg += max_hp // 16

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
    if atker_status == _STATUS_PARALYSIS and paralysis():
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
        if move[Move.TARGET] in TARGET_SELF_SIDE:
            return False
        #TODO: Some moves still go through, like dig, future sight
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
