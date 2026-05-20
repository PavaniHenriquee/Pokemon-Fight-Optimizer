"""Database for Pokemon in python, pokemon names to numbers"""
from dataclasses import dataclass
import numpy as np
from DataBase.AbilitiesDB import AbilityNames
from DataBase.loader import pkDB


def _int_constants(cls):
    return [value for name, value in cls.__dict__.items() if name.isupper() and isinstance(value, int)]


def _length(cls, start_offset=0):
    values = _int_constants(cls)
    return max(values) - start_offset + 1


@dataclass(slots=True)
class PokemonName:
    """Pokemon name"""
    BULBASAUR = 1
    IVYSAUR = 2
    VENUSAUR = 3
    CHARMANDER = 4
    CHARMELEON = 5
    CHARIZARD = 6
    SQUIRTLE = 7
    WARTORTLE = 8
    BLASTOISE = 9


PokIdToName = {v: k for k, v in PokemonName.__dict__.items() if not k.startswith("__")}
POKEMON_LENGTH = _length(PokemonName)

_MAX_ABILITIES = 2  # adjust if you ever add 3-ability Pokemon
_pool_np = np.zeros((POKEMON_LENGTH + 1, _MAX_ABILITIES), dtype=np.int64)

for pk_id, name in PokIdToName.items():
    abilities = [
        getattr(AbilityNames, ab.upper().replace(" ", "_"))
        for ab in pkDB[name.capitalize()]["abilities"]
    ]
    for i, ab_id in enumerate(abilities):
        _pool_np[pk_id, i] = ab_id

POKEMON_ABILITY_POOL = _pool_np
