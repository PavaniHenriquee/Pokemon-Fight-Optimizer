from DataBase.loader import pkDB, abDB, itemDB, moveDB
from Utils.loader import type_chart
from Models.pokemon import Pokemon
import random
import math
#import numpy

round = 1
charmander = Pokemon("Charmander",5,"Blaze","Hardy",["Scratch", "Growl"])
squirtle = Pokemon("Squirtle",5,"Torrent","Hardy",["Tackle", "Tail Whip"])
myPartyPk = [charmander]
oppPartyPk = [squirtle]

def round_half_down(value: float) -> int:
    """Round to nearest integer with .5 rounded down."""
    flo = math.floor(value)
    frac = value - flo
    if frac > 0.5:
        return math.ceil(value)
    else:
        return flo

# new helper: convert stage (-6..6) to multiplier used by main-series games
def stage_to_multiplier(stages: int) -> float:
    if stages >= 0:
        return (2 + stages) / 2.0
    else:
        return 2.0 / (2 - stages)

# new helper: robustly get a Pokemon's stage for a given stat name
def get_stage(pokemon, stat_key: str) -> int:
    stages = pokemon.stat_stages[stat_key]
    if stages > 6:
        stages = 6
    elif stages < -6:
        stages = -6
    return stages

def get_type_effectiveness(atk_type, defender_types):
    mult = 1.0
    if atk_type not in type_chart:
        return 1.0
    for d in defender_types:
        # defender type key assumed to match chart keys
        mult *= float(type_chart[atk_type].get(d, 1.0))
    return mult

def calculate_damage(attacker, defender, move):
    if move['category'] == "Status":
        # Status moves don't deal damage
        return 0
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

def calculate_status(attacker, defender, move):
    if move['category'] != "Status":
       return None
    
    for eff in move['effects']:
        if eff['effect_type'] == 'stat_change':
            if (eff['target'] == 'self' or eff['target'] == 'ally_side'):
                attacker.stat_stages[eff['stat']] += eff['change']
            elif (eff['target'] == 'target' or eff['target'] == 'foe_side' or eff['target'] == 'all_opponents'):
                defender.stat_stages[eff['stat']] += eff['change']

def battle_turn(p1, move1, p2, move2):
    if p1.base_data['base stats']['Speed'] > p2.base_data['base stats']['Speed']:
        order = [(p1, move1,p2), (p2, move2,p1)]
    else:
        order = [(p2, move2,p1), (p1, move1,p2)]
    for attacker, move, defender in order:
        if attacker.current_hp <= 0 or defender.current_hp <= 0:
            continue # Skip if either Pokémon is fainted

        damage, effectiveness = calculate_damage(attacker, defender, move)
        defender.current_hp -= damage
        print(f"{attacker.name} used {move['name']} on {defender.name}!")
        print(f"It dealt {damage} damage.")
        print(f"Effectiveness: {effectiveness}x")
        if defender.current_hp <= 0:
            print(f"{defender.name} has fainted!")
        else:
            print(f"{defender.name} has {defender.current_hp} HP left.")


