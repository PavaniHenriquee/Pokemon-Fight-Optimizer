"""Transform ability in Numpy array"""
import numpy as np
from Models.helper import AbilityActivation
from Models.idx_nparray import AbilityIdx
from DataBase.AbilitiesDB import AbilityNames


def ability_to_np(ability):
    """Basic array for ability"""
    array = np.zeros(len(AbilityIdx), dtype=np.int16)
    if not ability:
        return array

    array[AbilityIdx.ID] = AbilityNames[ability['name'].upper()].value
    array[AbilityIdx.WHEN] = AbilityActivation[ability['when'].upper()].value
    array[AbilityIdx.BREAKABLE] = int(ability.get('breakable', False) is True)
    array[AbilityIdx.CANT_SUPRESS] = int(ability.get('cant_suppress', False) is True)
    array[AbilityIdx.FAIL_ROLEPLAY] = int(ability.get('fail_roleplay', False) is True)
    array[AbilityIdx.FAIL_SKILL_SWAP] = int(ability.get('fail_skill_swap', False) is True)
    array[AbilityIdx.NO_ENTRAIN] = int(ability.get('no_entrain', False) is True)
    array[AbilityIdx.NO_RECEIVER] = int(ability.get('no_receiver', False) is True)
    array[AbilityIdx.NO_TRACER] = int(ability.get('no_tracer', False) is True)
    array[AbilityIdx.NO_TRANSFORM] = int(ability.get('no_transform', False) is True)
    array[AbilityIdx.SUPRESS_WEATHER] = int(ability.get('suppress_weather', False) is True)
    return array
