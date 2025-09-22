"""Helper functions"""
import random
import numpy as np
from Utils.loader import type_chart
from Models.helper import Types


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
    a_type = Types(atk_type).name.capitalize()
    d_type1 = Types(defender_type1).name.capitalize()
    d_type2 = Types(defender_type2).name.capitalize() if defender_type2 != 0 else None
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


def batch_independent_score_from_rand(rand_dict, idx, rng=None):
    """
    Compute the total score from rand_dict[idx] using one getrandbits call
    to generate independent 0..255 draws (one per pair).
    Returns the total score delta.
    rng: optional random.Random-like object (must implement getrandbits(n)).
         If None, uses the top-level random module.
    """
    if rng is None:
        rng = random

    entries = entries_from_rand(rand_dict, idx)
    n = len(entries)
    if n == 0:
        return 0

    # Fast numpy path when a numpy Generator is provided
    if np is not None and hasattr(rng, 'integers') and isinstance(rng, np.random.Generator):
        scores = np.array([s for s, _ in entries], dtype=np.int64)
        chances = np.array([c for _, c in entries], dtype=np.uint16)
        draws = rng.integers(0, 256, size=n, dtype=np.uint16)
        mask = draws < chances
        return int(scores.dot(mask.astype(np.int64)))

    # get n independent bytes in one call
    bits = rng.getrandbits(n * 8)  # produces an integer with n*8 random bits

    total = 0
    for j, (s, c) in enumerate(entries):
        # extract j-th byte (0..255)
        r = (bits >> (8 * j)) & 0xFF
        if r < c:           # c expected in 0..255
            total += s
    return total
