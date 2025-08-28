from Utils.loader import type_chart
import math

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

def has_availible_pokemon(party):
    return any(pokemon.fainted == False for pokemon in party)