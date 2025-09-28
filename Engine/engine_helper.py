"""Helpers that are only needed in the engine directory"""
import random
from enum import Enum, auto
import numpy as np
from Utils.helper import stage_to_multiplier, get_type_effectiveness
from Engine.damage_calc import calculate_damage_confusion
from Models.idx_nparray import PokArray, MoveArray, MoveFlags, SecondaryArray
from Models.helper import Status, VolStatus, Types
from DataBase.PkDB import PokemonName


def to_battle_array(my_pty, opp_pty):
    """Tranform both parties in the battle arrray"""
    try:
        pok1 = my_pty[0].to_np()
    except IndexError:
        pok1 = np.zeros(len(PokArray))
    try:
        pok2 = my_pty[1].to_np()
    except IndexError:
        pok2 = np.zeros(len(PokArray))
    try:
        pok3 = my_pty[2].to_np()
    except IndexError:
        pok3 = np.zeros(len(PokArray))
    try:
        pok4 = my_pty[3].to_np()
    except IndexError:
        pok4 = np.zeros(len(PokArray))
    try:
        pok5 = my_pty[4].to_np()
    except IndexError:
        pok5 = np.zeros(len(PokArray))
    try:
        pok6 = my_pty[5].to_np()
    except IndexError:
        pok6 = np.zeros(len(PokArray))
    try:
        o_pok1 = opp_pty[0].to_np()
    except IndexError:
        o_pok1 = np.zeros(len(PokArray))
    try:
        o_pok2 = opp_pty[1].to_np()
    except IndexError:
        o_pok2 = np.zeros(len(PokArray))
    try:
        o_pok3 = opp_pty[2].to_np()
    except IndexError:
        o_pok3 = np.zeros(len(PokArray))
    try:
        o_pok4 = opp_pty[3].to_np()
    except IndexError:
        o_pok4 = np.zeros(len(PokArray))
    try:
        o_pok5 = opp_pty[4].to_np()
    except IndexError:
        o_pok5 = np.zeros(len(PokArray))
    try:
        o_pok6 = opp_pty[5].to_np()
    except IndexError:
        o_pok6 = np.zeros(len(PokArray))

    return np.concatenate([pok1, pok2, pok3, pok4, pok5, pok6,
                           o_pok1, o_pok2, o_pok3, o_pok4, o_pok5, o_pok6])


def check_speed(p1, p2):
    """Gives speed after modifications of stages and paralysis"""
    mult1 = 1
    mult2 = 1
    if p1[PokArray.STATUS] == Status['PARALYSIS']:
        mult1 = 0.25
    if p2[PokArray.STATUS] == Status['PARALYSIS']:
        mult2 = 0.25
    mult1 *= stage_to_multiplier(p1[PokArray.SPEED_STAT_STAGE])
    mult2 *= stage_to_multiplier(p2[PokArray.SPEED_STAT_STAGE])
    p1_speed = mult1 * p1[PokArray.SPEED]
    p2_speed = mult2 * p2[PokArray.SPEED]
    return p1_speed, p2_speed


def move_speed_tie(p1, m1, p2, m2):
    """Get at random the order"""
    speedtie = random.randint(1, 2)
    if speedtie == 1:
        order = [(p1, m1, p2), (p2, m2, p1)]
    else:
        order = [(p2, m2, p1), (p1, m1, p2)]
    return order


def move_order(p1, move1, p2, move2, p1_switch, p2_switch):
    """Calculates the order which the what move should be played
    Returns:

    [('Faster Pokemon', 'Move of Faster Pokemon', 'Slower Pokemon'),
        ('Slower Pokemon, 'Move of Slower Pokemon', 'Faster Pokemon')]"""
    if p1_switch and p2_switch:
        return []
    if p1_switch:
        order = [(p2, move2, p1)]
        return order
    if p2_switch:
        order = [(p1, move1, p2)]
        return order

    p1_speed, p2_speed = check_speed(p1, p2)

    if (
        (move1[MoveArray.PRIORITY] != 0 or move2[MoveArray.PRIORITY] != 0)
        and move1[MoveArray.PRIORITY] != move2[MoveArray.PRIORITY]
    ):
        if move1[MoveArray.PRIORITY] > move2[MoveArray.PRIORITY]:
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


class MoveOutcome(Enum):
    """Possible moves outcomes"""
    HIT = auto()
    MISS = auto()
    INVULNERABLE = auto()
    SEMI_INVULNERABLE = auto()


def calculate_hit_miss(move, attacker, defender):
    '''Returns a boolean if the move passed the accuracy check'''
    # TODO: Semi invulnerable states, like Fly, dig etc.
    # TODO: Invulnerability like Eletric Ground, Poison Steel.
    # TODO: Check for flinch

    if get_type_effectiveness(move[MoveArray.TYPE], defender[PokArray.TYPE1], defender[PokArray.TYPE2]) == 0:
        return MoveOutcome.INVULNERABLE

    if move[MoveArray.ACCURACY] == -1:
        return MoveOutcome.HIT

    acc_stage = attacker[PokArray.ACCURACY_STAT_STAGE] - defender[PokArray.EVASION_STAT_STAGE]
    # Checking if it's an always hit move, if so it won't have an number on accuracy so it will always be 100 to hit
    accuracy = move[MoveArray.ACCURACY] * stage_to_multiplier(acc_stage, acc=True)

    if random.randint(1, 100) <= accuracy:
        return MoveOutcome.HIT
    return MoveOutcome.MISS


def calculate_crit():
    """Returns a boolean if the move passed the crit check"""
    crit_roll = random.randint(1, 16)  # 1/16 chance of a crit
    iscrit = crit_roll == 1
    return iscrit


def get_non_fainted_pokemon(party):
    """Only non fainted pokemon list"""
    return [pokemon for pokemon in party if not getattr(pokemon, 'fainted', False)]


def reset_switch_out(pok):
    """If a pokemon swithces out it needs to reset these conditions"""
    pok[PokArray.ATTACK_STAT_STAGE] = 0
    pok[PokArray.DEFENSE_STAT_STAGE] = 0
    pok[PokArray.SPECIAL_ATTACK_STAT_STAGE] = 0
    pok[PokArray.SPECIAL_DEFENSE_STAT_STAGE] = 0
    pok[PokArray.SPEED_STAT_STAGE] = 0
    pok[PokArray.ACCURACY_STAT_STAGE] = 0
    pok[PokArray.EVASION_STAT_STAGE] = 0
    pok[PokArray.VOL_STATUS] = 0
    pok[PokArray.TURNS] = 0
    pok[PokArray.BADLY_POISON] = 1


def flinch_checker(move):
    """Returns true or false if move has a flinch percent and it should flinch"""
    offset = len(MoveArray) + len(MoveFlags)
    flinch = move[offset + SecondaryArray.VOL_STATUS]
    chance = move[offset + SecondaryArray.CHANCE]
    if flinch != 0 and flinch & VolStatus.FLINCH:
        if random.randint(1, 100) <= chance:
            return True

    return False


def confusion(attacker, my_pok):
    """Calculates confusion turn"""
    if attacker == my_pok:
        print(f"{attacker.name} is confused!")
    else:
        print(f'Enemy {attacker.name} is confused!')
    if random.randint(1, 100) <= 50:
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
    if move[MoveArray.TYPE] == Types['FIRE']:
        defender[PokArray.STATUS] = 0
        print(f"{PokemonName(defender[PokArray.ID]).name.capitalize()} has thawed out!")
        return True
    return False
