"""Database for moves in python, where it gives everything a move does"""  # pylint:disable=C0103
from enum import IntEnum, auto


class MoveName(IntEnum):
    """Converting move names to numbers"""
    def _generate_next_value_(name, start, count, last_values):  # pylint:disable=E0213
        return count + 1

    TACKLE = auto()
    GROWL = auto()
    SCRATCH = auto()
    TAIL_WHIP = auto()
    POUND = auto()
    LEER = auto()
    EMBER = auto()
    BUBBLE = auto()
    RAZOR_LEAF = auto()
