"""Database for Pokemon in python, pokemon names to numbers"""  # pylint:disable=C0103
from types import SimpleNamespace


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
