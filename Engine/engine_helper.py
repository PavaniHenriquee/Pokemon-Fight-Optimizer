"""Helpers that are only needed in the engine directory"""
import random
from enum import Enum, auto
from Utils.helper import get_stage, stage_to_multiplier, get_type_effectiveness
from Engine.damage_calc import calculate_damage_confusion


def check_speed(p1, p2):
    """Gives speed after modifications of stages and paralysis"""
    mult1 = 1
    mult2 = 1
    if p1.status == 'paralysis':
        mult1 = 0.25
    if p2.status == 'paralysis':
        mult2 = 0.25
    mult1 *= stage_to_multiplier(get_stage(p1, "Speed"))
    mult2 *= stage_to_multiplier(get_stage(p2, "Speed"))
    p1_speed = mult1 * p1.speed
    p2_speed = mult2 * p2.speed
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

    if (move1['priority'] != 0 or move2['priority'] != 0) and move1['priority'] != move2['priority']:
        if move1['priority'] > move2['priority']:
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

    if get_type_effectiveness(move['type'], defender.types) == 0:
        return MoveOutcome.INVULNERABLE

    if move['accuracy'] == 'always':
        return MoveOutcome.HIT

    acc_stage = get_stage(attacker, "Accuracy") - get_stage(defender, "Evasion")
    # Checking if it's an always hit move, if so it won't have an number on accuracy so it will always be 100 to hit
    accuracy = move['accuracy'] * stage_to_multiplier(acc_stage, acc=True)

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
    pok.stat_stages = {
        'Attack': 0,
        'Defense': 0,
        'Special Attack': 0,
        'Special Defense': 0,
        'Speed': 0,
        'Accuracy': 0,
        'Evasion': 0
    }
    pok.confusion = False
    pok.attract = False
    pok.substitute = False
    pok.leech_seed = False
    pok.turns = 0
    pok.curse = False
    if pok.badly_poison >= 1:
        pok.badly_poison = 1
    pok.vol_status = []


def flinch_checker(move):
    """Returns true or false if move has a flinch percent and it should flinch"""
    for e in move['effects']:
        flinch = e.get('flinch', 0)
        chance = e.get('chance', 100)
        if flinch is True:
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
    if move['type'] == 'Fire':
        defender.status = None
        print(f"{defender.name} has thawed out!")
        return True
    return False
