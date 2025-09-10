"""Helpers that are only needed in the engine directory"""
import random
from Utils.helper import get_stage, stage_to_multiplier


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


def calculate_hit_miss(move, attacker, defender):
    '''Returns a boolean if the move passed the accuracy check'''
    # TODO: Semi invulnerable states, like Fly, dig etc.
    # TODO: Invulnerability like Eletric Ground, Poison Steel.
    acc_stage = get_stage(attacker, "Accuracy") - get_stage(defender, "Evasion")

    # Checking if it's an always hit move, if so it won't have an number on accuracy so it will always be 100 to hit
    accuracy = move['accuracy'] * stage_to_multiplier(acc_stage, acc=True) if isinstance(move['accuracy'], int) else 100

    if accuracy >= 100:
        is_hit = True
        return is_hit

    random_roll = random.randint(1, 100)
    is_hit = random_roll <= accuracy
    return is_hit


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
