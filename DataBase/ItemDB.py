"""Database for Items in python, where it gives the idx for Items name"""  # pylint:disable=C0103
from enum import IntEnum, auto


class ItemNames(IntEnum):
    """Converting ability names to numbers"""
    def _generate_next_value_(name, start, count, last_values):  # pylint:disable=E0213
        return count + 1

    ORAN_BERRY = auto()
    SITRUS_BERRY = auto()
    SMOOTH_ROCK = auto()
