"""Database for abilities in python, where it gives everything a move does"""  # pylint:disable=C0103
from enum import IntEnum, auto


class AbilityNames(IntEnum):
    """Converting ability names to numbers"""
    def _generate_next_value_(name, start, count, last_values):  # pylint:disable=E0213
        return count + 1

    BLAZE = auto()
    TORRENT = auto()
    OVERGROW = auto()
    MOLD_BREAKER = auto()
    NO_GUARD = auto()
    SIMPLE = auto()
    KEEN_EYE = auto()
