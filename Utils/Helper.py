from Utils.loader import type_chart
import math
import random

def round_half_down(value: float) -> int:
    """Round to nearest integer with .5 rounded down."""
    flo = math.floor(value)
    frac = value - flo
    if frac > 0.5:
        return math.ceil(value)
    else:
        return flo
    
# new helper: convert stage (-6..6) to multiplier used by main-series games
def stage_to_multiplier(stages: int, acc = False) -> float:
    if acc:
        if stages >= 0:
            return (3 + stages) / 3.0
        else:
            return 3.0 / (3 - stages)
    
    if stages >= 0:
        return (2 + stages) / 2.0
    else:
        return 2.0 / (2 - stages)
    
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

def get_non_fainted_pokemon(party):
    return [pokemon for pokemon in party if not getattr(pokemon, 'fainted', False)]

def reset_stat_vol(pok):
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


def switch_menu(alive_pokemon, current_pokemon):
    switch_pok = -1
    ret_menu = False
    print("Choose the Pokemon you want to switch to:")
    for i, pok in enumerate(alive_pokemon):
        print(f"{i+1}. {pok.name}")
    print("r. Return to previous menu") if not(current_pokemon.fainted) else None
    switch_choice = input("Choose: ")
    if switch_choice == 'r' and not(current_pokemon.fainted):
        ret_menu = True
        return switch_pok, ret_menu, current_pokemon
    if switch_choice.isdigit():
        switch_pok = int(switch_choice) - 1
        if switch_pok < 0 or switch_pok >= len(alive_pokemon):
            print("Please select a valid Pokemon.")
            return switch_pok, ret_menu, current_pokemon
        else:
            reset_stat_vol(current_pokemon)
            current_pokemon = alive_pokemon[switch_pok]
            print(f"You switched to {current_pokemon.name}!")
        return switch_pok, ret_menu, current_pokemon
    else:
        print("Please select a valid answer.")
        return switch_pok, ret_menu, current_pokemon
    
def speed_tie(p1, m1, p2, m2):
    speedtie = random.randint(1,2)
    if speedtie == 1:
        order = [(p1, m1, p2), (p2, m2, p1)]
    else:
        order = [(p2, m2, p1), (p1, m1, p2)]
    return order

def calculate_crit():
    """Returns a boolean if the move passed the crit check"""
    crit_roll = random.randint(1,16) #1/16 chance of a crit
    if crit_roll == 1:
        iscrit = True
    else: iscrit = False
    return iscrit

def calculate_hit_miss(move, attacker, defender):
    '''Returns a boolean if the move passed the accuracy check'''
    acc_stage = get_stage(attacker, "Accuracy") - get_stage(defender, "Evasion")
    accuracy = move['accuracy'] * stage_to_multiplier(acc_stage, acc = True)

    if accuracy >= 100:
        is_hit = True
        return is_hit
    
    random_roll = random.randint(1,100)
    if random_roll <= accuracy:
        is_hit = True
    else:
        is_hit = False
    return is_hit