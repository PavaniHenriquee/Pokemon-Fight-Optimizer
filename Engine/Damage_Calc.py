from Utils.Helper import round_half_down, stage_to_multiplier, get_stage, get_type_effectiveness
import random

def calculate_damage(attacker, defender, move, crit = False, roll_multiplier = None):
    """ Calculate damage based on current stats of the attacker and the defender, giving back the damage and its effectiveness"""
    if move['category'] == "Status":
        # Status moves don't deal damage(Fail-Safe, Status moves shouldn't get thorugh here)
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

    if crit == True:
        crit_mult = 2
        if def_stage > 0:
            def_stage = 0
    else: crit_mult = 1

    # apply stage multipliers
    attack = raw_attack * stage_to_multiplier(atk_stage)
    defense = raw_defense * stage_to_multiplier(def_stage)

    if roll_multiplier == None:
        roll_multiplier = random.randint(85,100)/100

    #Base damage formula
    damage = (((2 * attacker.level / 5 + 2) * attack * move['power'] / defense) / 50 + 2) 
    
    # STAB
    if move['type'] in getattr(attacker, 'types', []):
        stab = 1.5
    else: stab = 1

    # type effectiveness
    effectiveness = get_type_effectiveness(move['type'], getattr(defender, 'types', []))
    damage *= effectiveness * crit_mult * stab * roll_multiplier
    final_damage = round_half_down(damage)
    return final_damage, effectiveness