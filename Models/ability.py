"""Transform ability in Numpy array"""
import numpy as np
from Models.helper import AbilityActivation
from Models.idx_const import Pok, AB_LEN, BASE_LEN
from DataBase.AbilitiesDB import AbilityNames


def ability_to_np(ability):
    """Basic array for ability"""
    array = np.zeros(AB_LEN, dtype=np.int16)
    if not ability:
        return array

    off = BASE_LEN
    array[Pok.AB_ID - off]              = getattr(AbilityNames, ability['name'].upper())
    array[Pok.AB_WHEN - off]            = getattr(AbilityActivation, ability['when'].upper())
    array[Pok.AB_BREAKABLE - off]       = int(ability.get('breakable', False) is True)
    array[Pok.AB_CANT_SUPRESS - off]    = int(ability.get('cant_suppress', False) is True)
    array[Pok.AB_FAIL_ROLEPLAY - off]   = int(ability.get('fail_roleplay', False) is True)
    array[Pok.AB_FAIL_SKILL_SWAP - off] = int(ability.get('fail_skill_swap', False) is True)
    array[Pok.AB_NO_ENTRAIN - off]      = int(ability.get('no_entrain', False) is True)
    array[Pok.AB_NO_RECEIVER - off]     = int(ability.get('no_receiver', False) is True)
    array[Pok.AB_NO_TRACER - off]       = int(ability.get('no_tracer', False) is True)
    array[Pok.AB_NO_TRANSFORM - off]    = int(ability.get('no_transform', False) is True)
    array[Pok.AB_SUPRESS_WEATHER - off] = int(ability.get('suppress_weather', False) is True)
    return array
