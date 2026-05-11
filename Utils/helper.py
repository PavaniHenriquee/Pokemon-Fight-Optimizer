"""Helper functions"""
import random
import numpy as np
from Utils.loader import TYPE_CHART
from Models.idx_const import POK_LEN, FIELD_LEN


def stage_to_multiplier(stages, stat) -> int:
    """Check how the stages are affecting the stats"""
    
    if stages >= 0:
        res = stat * (2 + stages) // 2
    else:
        res = stat * 2 // (2 - stages)

    return res


def get_type_effectiveness(atk_type, def_type1, def_type2):
    """Get how effective the type is against its target"""
    atk = atk_type
    type1 = def_type1
    type2 = def_type2
    den = 2
    result = TYPE_CHART[(atk * 19) + type1]
    if def_type2:
        result *= TYPE_CHART[(atk * 19) + type2]
        den = 4
    return result, den


def batch_independent_score_from_rand(rand, idx):
    """
    Rand is a three dim array, where i'm getting the index of the move, so i'm checking the 
    x by 2 array where on the 'col' is how much score and the number out of 255 that is the percentage
    of chance of it adding it or not to the return
    """
    total = 0
    r = random.getrandbits
    for score, chance in rand[idx]:
        if r(8) < chance:
            total += score

    return total


def to_battle_array(my_pty, opp_pty, battlefield=None):
    """Transform both parties into a single flat battle array."""

    def get_party_arrays(party, max_size=6):
        arrays = []
        for i in range(max_size):
            try:
                arrays.append(party[i].to_np())
            except IndexError:
                arrays.append(np.zeros(POK_LEN, dtype=np.int32))
        return arrays

    # Process both parties
    my_data = get_party_arrays(my_pty)
    opp_data = get_party_arrays(opp_pty)

    # Handle battlefield with a simple fallback
    battlef = battlefield.to_array() if battlefield else np.zeros(FIELD_LEN, dtype=np.int32)

    return np.concatenate([*my_data, *opp_data, battlef], dtype=np.int32)
