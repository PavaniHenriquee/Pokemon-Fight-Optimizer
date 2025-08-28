from DataBase.loader import load_database
from Utils.loader import load_utils
from Models.pokemon import Pokemon
import random
import math
#import numpy


pkDB = load_database("PkDB.json")
abDB = load_database("AbilitiesDB.json")
itemDB = load_database("ItemDB.json")
moveDB = load_database("MoveDB.json")
type_chart = load_utils("TypeChart.json")
round = 1
charmander = Pokemon("Charmander", pkDB["Charmander"], 5, abDB["Blaze"], None, {
    1: moveDB["Scratch"],
    2: moveDB["Growl"]
})
squirtle = Pokemon("Squirtle", pkDB["Squirtle"], 5, abDB["Torrent"], None, {
    1: moveDB["Tackle"],
    2: moveDB["Tail Whip"]
})
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
    """
    stat_key: one of 'atk','def','spatk','spdef','spe','hp'
    Pokemon may have attribute stat_stages as dict. Defaults to 0.
    """
    mapping = {
        'atk': 'atk', 'def': 'def', 'spatk': 'spatk',
        'spdef': 'spdef', 'spe': 'spe', 'hp': 'hp'
    }
    stages = 0
    if hasattr(pokemon, 'stat_stages') and isinstance(pokemon.stat_stages, dict):
        # try several possible keys
        for key in (stat_key, mapping.get(stat_key), stat_key.upper(), stat_key.capitalize()):
            if key in pokemon.stat_stages:
                try:
                    stages = int(pokemon.stat_stages[key])
                except Exception:
                    stages = 0
                return max(-6, min(6, stages))
    return 0

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
        raw_attack = attacker.base_data['base stats']['Attack']
        raw_defense = defender.base_data['base stats']['Defense']
        atk_stage = get_stage(attacker, 'atk')
        def_stage = get_stage(defender, 'def')
    else:
        raw_attack = attacker.base_data['base stats']['Special Attack']
        raw_defense = defender.base_data['base stats']['Special Defense']
        atk_stage = get_stage(attacker, 'spatk')
        def_stage = get_stage(defender, 'spdef')

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


