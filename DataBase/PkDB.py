"""Database for Pokemon in python, pokemon names to numbers"""  # pylint:disable=C0103
from enum import IntEnum, auto


class PokemonName(IntEnum):
    """Converting move names to numbers"""
    def _generate_next_value_(name, start, count, last_values):  # pylint:disable=E0213
        return count + 1
    BULBASAUR = auto()
    IVYSAUR = auto()
    VENUSAUR = auto()
    CHARMANDER = auto()
    CHARMELEON = auto()
    CHARIZARD = auto()
    SQUIRTLE = auto()
    WARTORTLE = auto()
    BLASTOISE = auto()
