"""Database for Pokemon in python, pokemon names to numbers"""  # pylint:disable=C0103
from types import SimpleNamespace
from DataBase.AbilitiesDB import AbilityNames
from DataBase.loader import pkDB


PokemonName = SimpleNamespace(
    BULBASAUR = 1,
    IVYSAUR = 2,
    VENUSAUR = 3,
    CHARMANDER = 4,
    CHARMELEON = 5,
    CHARIZARD = 6,
    SQUIRTLE = 7,
    WARTORTLE = 8,
    BLASTOISE = 9
)

PokIdToName = {v: k for k, v in PokemonName.__dict__.items() if not k.startswith("__")}
_MAX_ID = max(PokIdToName.keys())
_pool = [() for _ in range(_MAX_ID + 1)]  # index 0 is just padding, unused
for pk_id, name in PokIdToName.items():
    _pool[pk_id] = tuple(
        getattr(AbilityNames, ab.upper().replace(" ", "_"))
        for ab in pkDB[name.capitalize()]["abilities"]
    )

POKEMON_ABILITY_POOL: tuple = tuple(_pool)
