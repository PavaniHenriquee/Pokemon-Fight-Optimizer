"""Helper functions"""
import math
import random
from Utils.loader import type_chart


def round_half_down(value: float) -> int:
    """Round to nearest integer with .5 rounded down."""
    flo = math.floor(value)
    frac = value - flo
    if frac > 0.5:
        return math.ceil(value)
    else:
        return flo


# new helper: convert stage (-6..6) to multiplier used by main-series games
def stage_to_multiplier(stages: int, acc=False) -> float:
    """Check how the stages are affecting the stats"""
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
    """ Get what stages the pokemon has, being defensive to only do between -6..6"""
    stages = pokemon.stat_stages[stat_key]
    if stages > 6:
        stages = 6
        pokemon.stat_stages[stat_key] = stages
    elif stages < -6:
        stages = -6
        pokemon.stat_stages[stat_key] = stages
    return stages


def get_type_effectiveness(atk_type, defender_types):
    """Check to see if 0.25, 0.50, 1, 2, 4 times effective"""
    mult = 1.0
    if atk_type not in type_chart:
        return 1.0
    for d in defender_types:
        # defender type key assumed to match chart keys
        mult *= float(type_chart[atk_type].get(d, 1.0))
    return mult


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
        reset_switch_out(current_pokemon)
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


def calculate_hit_miss(move, attacker, defender):
    '''Returns a boolean if the move passed the accuracy check'''
    acc_stage = get_stage(attacker, "Accuracy") - get_stage(defender, "Evasion")
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

    # get n independent bytes in one call
    bits = rng.getrandbits(n * 8)  # produces an integer with n*8 random bits

    total = 0
    for j, (s, c) in enumerate(entries):
        # extract j-th byte (0..255)
        r = (bits >> (8 * j)) & 0xFF
        if r < c:           # c expected in 0..255
            total += s
    return total
