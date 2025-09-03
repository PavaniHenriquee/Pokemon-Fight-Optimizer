"""Damage calculations"""
import random
import math
from Utils.helper import stage_to_multiplier, get_stage, get_type_effectiveness


def multipliers(move, attacker, defender, crit, roll_mult):
    """Calc Multiplers for bas formula damage"""
    stab = 1
    effectiveness = 1
    crit_mult = 1
    burn = 1

    # STAB
    if move['type'] in getattr(attacker, 'types', []):
        stab = 1.5

    # Crit
    if crit is True:
        crit_mult = 2

    # effectiveness
    effectiveness = get_type_effectiveness(move['type'], getattr(defender, 'types', []))

    # Roll Multiplier
    if roll_mult is None:
        roll_mult = random.randint(85, 100)/100

    # Burn
    if attacker.status == 'burn':
        if move['category'] == 'Physical' and not (attacker.ability['name'] == 'Guts') and not move['name'] == 'Facade':
            burn = 0.5

    mult = stab * effectiveness * crit_mult * burn * roll_mult
    return mult, effectiveness


def calculate_damage(attacker, defender, move, crit=False, roll_multiplier=None):
    """Calculate damage based on current stats of the attacker and the defender, giving back the damage and its effectiveness"""
    if move['category'] == "Status":
        # Status moves don't deal damage(Trainer AI will fall here)
        return 0, 0
    if move['category'] == 'Physical':
        raw_attack = attacker.attack
        raw_defense = defender.defense
        atk_stage = get_stage(attacker, 'Attack')
        def_stage = get_stage(defender, 'Defense')
    else:
        raw_attack = attacker.special_attack
        raw_defense = defender.special_defense
        atk_stage = get_stage(attacker, 'Special Attack')
        def_stage = get_stage(defender, 'Special Defense')

    if crit is True:
        def_stage = min(def_stage, 0)
        atk_stage = max(atk_stage, 0)

    # apply stage multipliers
    attack = raw_attack * stage_to_multiplier(atk_stage)
    defense = raw_defense * stage_to_multiplier(def_stage)

    # Base damage formula
    damage = math.floor(math.floor(((2 * attacker.level / 5) + 2) * move['power'] * (attack / defense)) / 50 + 2)

    mult, effectiveness = multipliers(move, attacker, defender, crit, roll_multiplier)
    damage *= mult
    final_damage = math.floor(damage)
    return final_damage, effectiveness
