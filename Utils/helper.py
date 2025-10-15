"""Helper functions"""
import random
import numpy as np
from Utils.loader import type_chart
from Models.helper import TypesIdToName


def round_half_down(value: float) -> int:
    """Round to nearest integer with .5 rounded down."""
    arr = np.asarray(value)
    flo = np.floor(arr)
    frac = arr - flo
    res = np.where(frac > 0.5, np.ceil(arr), flo).astype(int)
    # return scalar int when scalar input provided
    if arr.shape == ():
        return int(res.item())
    return res


# Convert stage (-6..6) to multiplier used by main-series games
def stage_to_multiplier(stages: np.float32, acc=False) -> float:
    """Check how the stages are affecting the stats"""
    if acc:
        mult = 3
    else:
        mult = 2

    if stages >= 0:
        res = (mult + stages) / mult
    else:
        res = mult / (mult - stages)

    return res


def get_type_effectiveness(atk_type: np.float32, defender_type1: np.float32, defender_type2: np.float32):
    """Check to see if 0.25, 0.50, 1, 2, 4 times effective"""
    a_type = TypesIdToName[atk_type].capitalize()
    d_type1 = TypesIdToName[defender_type1].capitalize()
    d_type2 = TypesIdToName[defender_type2].capitalize() if defender_type2 != 0 else None
    if a_type not in type_chart:
        return 1.0
    vals = [float(type_chart[a_type].get(d, 1.0)) for d in (d_type1, d_type2)]
    if not vals:
        return 1.0
    return float(np.prod(vals))


def get_non_fainted_pokemon(party):
    """Only non fainted pokemon list"""
    return [pokemon for pokemon in party if not getattr(pokemon, 'fainted', False)]


def switch_menu(alive_pokemon, current_pokemon):
    """Makes what the switch menu looks like, it should loop where its used"""
    switch_pok = -1
    ret_menu = False
    print("Choose the Pokemon you want to switch to:")
    for i, pok in enumerate(alive_pokemon):
        print(f"{i+1}. {pok.name}")
    if not current_pokemon.fainted:
        print("r. Return to previous menu")
    switch_choice = input("Choose: ")
    if switch_choice == 'r' and not current_pokemon.fainted:
        ret_menu = True
        return switch_pok, ret_menu, current_pokemon
    if switch_choice.isdigit():
        switch_pok = int(switch_choice) - 1
        if switch_pok < 0 or switch_pok >= len(alive_pokemon):
            print("Please select a valid Pokemon.")
            return switch_pok, ret_menu, current_pokemon
        current_pokemon = alive_pokemon[switch_pok]
        print(f"You switched to {current_pokemon.name}!")
        return switch_pok, ret_menu, current_pokemon
    print("Please select a valid answer.")
    return switch_pok, ret_menu, current_pokemon


def speed_tie(p1, m1, p2, m2):
    """Get at random the order"""
    speedtie = random.randint(1, 2)
    if speedtie == 1:
        order = [(p1, m1, p2), (p2, m2, p1)]
    else:
        order = [(p2, m2, p1), (p1, m1, p2)]
    return order


def calculate_crit():
    """Returns a boolean if the move passed the crit check"""
    crit_roll = random.randint(1, 16)  # 1/16 chance of a crit
    iscrit = crit_roll == 1
    return iscrit


def calculate_hit_miss(move, attacker, defender):  # pylint:disable=W0613
    '''Returns a boolean if the move passed the accuracy check'''
    # acc_stage = get_stage(attacker, "Accuracy") - get_stage(defender, "Evasion")
    acc_stage = 0
    accuracy = move['accuracy'] * stage_to_multiplier(acc_stage, acc=True) if isinstance(move['accuracy'], int) else 1

    if accuracy >= 100:
        is_hit = True
        return is_hit

    random_roll = random.randint(1, 100)
    is_hit = random_roll <= accuracy
    return is_hit


def entries_from_rand(rand_dict, idx):
    """
    Convert your rand[idx] parallel lists to a list of (score_delta, chance) pairs.
    Expects rand_dict[idx] to be {'score': [...], 'chance': [...]}.
    """
    item = rand_dict.get(idx)
    if not item:
        return []
    scores = item.get('score', [])
    chances = item.get('chance', [])
    # zip will silently drop extras; check lengths to catch problems early
    if len(scores) != len(chances):
        raise ValueError(f"score/chance length mismatch for idx={idx}: {len(scores)} vs {len(chances)}")
    return list(zip(scores, chances))


def batch_independent_score_from_rand(rand, idx):
    """
    Rand is a three dim array, where i'm getting the index of the move, so i'm checking the 
    x by 2 array where on the 'col' is how much score and the number out of 255 that is the percentage
    of chance of it adding it or not to the return
    """
    arr = rand[idx]
    total = 0
    for score, chance in arr:
        if np.isnan(score):
            break
        if random.randint(0, 255) < chance:
            total += score
    return total

def possible_rand(rand, idx):
    """Get the min and max score possible from rand by move"""
    arr = rand[idx]
    min_p = 0
    max_p = 0
    for score, _ in arr:
        if np.isnan(score):
            break
        if score < 0:
            min_p += score
        else:
            max_p += score
    return min_p, max_p
