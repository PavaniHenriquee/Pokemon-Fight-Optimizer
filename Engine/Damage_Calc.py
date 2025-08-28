from Utils.Helper import round_half_down, stage_to_multiplier, get_stage, get_type_effectiveness
import random

def calculate_damage(attacker, defender, move):
    if move['category'] == "Status":
        # Status moves don't deal damage
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

    # apply stage multipliers
    attack = raw_attack * stage_to_multiplier(atk_stage)
    defense = raw_defense * stage_to_multiplier(def_stage)

    multiplier = random.randint(85, 100) / 100.0
    damage = (((2 * attacker.level / 5 + 2) * attack * move['power'] / defense) / 50 + 2) * multiplier

    # STAB
    if move['type'] in getattr(attacker, 'types', []):
        damage *= 1.5

    # type effectiveness
    effectiveness = get_type_effectiveness(move['type'], getattr(defender, 'types', []))
    damage *= effectiveness
    final_damage = round_half_down(damage)
    return final_damage, effectiveness