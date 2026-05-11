"""Helpers that are only needed in the engine directory"""
import random
from Utils.helper import stage_to_multiplier, get_type_effectiveness
from Engine.damage_calc import calculate_damage_confusion
from Engine.status_calc import after_turn_status
from Models.idx_const import Pok, Move, Sec, Field, POK_LEN
from Models.helper import Status, VolStatus, Types, Weather, AbilityActivation
from DataBase.PkDB import PokemonName
from DataBase.AbilitiesDB import AbilityNames


SANDSTORM_IM = {Types.ROCK, Types.GROUND, Types.STEEL}


def check_speed(p1, p2, weather):
    """Gives speed after modifications of stages, paralysis and Abilities"""
    p1_speed = p1[Pok.SPEED]
    p2_speed = p2[Pok.SPEED]
    if p1[Pok.STATUS] == Status.PARALYSIS:
        p1_speed //= 4
    if p2[Pok.STATUS] == Status.PARALYSIS:
        p2_speed //= 4
    # Apply Stat stages if necessary
    if p1[Pok.SPEED_STAT_STAGE] != 0:
        p1_speed = stage_to_multiplier(p1[Pok.SPEED_STAT_STAGE], p1_speed)
    if p2[Pok.SPEED_STAT_STAGE] != 0:
        p2_speed = stage_to_multiplier(p2[Pok.SPEED_STAT_STAGE], p2_speed)
    ab_w1 = p1[Pok.AB_WHEN]
    ab_w2 = p2[Pok.AB_WHEN]
    if ab_w1 & AbilityActivation.ON_MODIFY_SPEED:
        ab = p1[Pok.AB_ID]
        if weather == Weather.SUN and ab == AbilityNames.CHLOROPHYLL:
            p1_speed *= 2
    if ab_w2 & AbilityActivation.ON_MODIFY_SPEED:
        ab = p2[Pok.AB_ID]
        if weather == Weather.SUN and ab == AbilityNames.CHLOROPHYLL:
            p2_speed *= 2
    return p1_speed, p2_speed


def move_speed_tie(p1, m1, p2, m2):
    """Get at random the order"""
    speedtie = random.getrandbits(1)
    if speedtie == 1:
        order = [(p1, m1, p2), (p2, m2, p1)]
    else:
        order = [(p2, m2, p1), (p1, m1, p2)]
    return order


def move_order(p1, move1, p2, move2, p1_switch, p2_switch, weather):
    """Calculates the order which the what move should be played
    Returns:

    [('Faster Pokemon', 'Move of Faster Pokemon', 'Slower Pokemon'),
        ('Slower Pokemon, 'Move of Slower Pokemon', 'Faster Pokemon')]"""
    if p1_switch and p2_switch:
        return []
    if p1_switch:
        return [(p2, move2, p1)]
    if p2_switch:
        return [(p1, move1, p2)]

    p1_speed, p2_speed = check_speed(p1, p2, weather)

    if (
        (move1[Move.PRIORITY] != 0 or move2[Move.PRIORITY] != 0)
        and move1[Move.PRIORITY] != move2[Move.PRIORITY]
    ):
        if move1[Move.PRIORITY] > move2[Move.PRIORITY]:
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


def calculate_hit_miss(move, attacker, defender):
    '''Returns a boolean if the move passed the accuracy check'''
    # TODO: Semi invulnerable states, like Fly, dig etc.
    move_acc = move[Move.ACCURACY]

    if get_type_effectiveness(move[Move.TYPE], defender[Pok.TYPE1], defender[Pok.TYPE2]) == 0:
        return MoveOutcome.INVULNERABLE

    if move_acc == -1:
        return MoveOutcome.HIT

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


def get_non_fainted_pokemon(party):
    """Only non fainted pokemon list"""
    return [pokemon for pokemon in party if not getattr(pokemon, 'fainted', False)]


def reset_switch_out(pok):
    """If a pokemon swithces out it needs to reset these conditions"""
    pok[Pok.ATTACK_STAT_STAGE]          = 0
    pok[Pok.DEFENSE_STAT_STAGE]         = 0
    pok[Pok.SPECIAL_ATTACK_STAT_STAGE]  = 0
    pok[Pok.SPECIAL_DEFENSE_STAT_STAGE] = 0
    pok[Pok.SPEED_STAT_STAGE]           = 0
    pok[Pok.ACCURACY_STAT_STAGE]        = 0
    pok[Pok.EVASION_STAT_STAGE]         = 0
    pok[Pok.VOL_STATUS]                 = 0
    pok[Pok.TURNS]                      = 0
    pok[Pok.BADLY_POISON]               = 1


def flinch_checker(move):
    """Returns true or false if move has a flinch percent and it should flinch"""
    flinch = move[Sec.VOL_STATUS]
    chance = move[Sec.CHANCE] / 100
    if flinch != 0 and flinch & VolStatus.FLINCH:
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
        defender[Pok.STATUS] = 0
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
    dmg = 0
    max_hp = pokemon[Pok.MAX_HP]
    dmg += after_turn_status(pokemon)
    type1_2= {pokemon[Pok.TYPE1],pokemon[Pok.TYPE2]}
    if weather == Weather.SANDSTORM and not type1_2.isdisjoint(SANDSTORM_IM):
        dmg += max_hp // 16
    elif weather == Weather.HAIL and not Types.ICE in type1_2:
        dmg += max_hp // 16
    
    return dmg
