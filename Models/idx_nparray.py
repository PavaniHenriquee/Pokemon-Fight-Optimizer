"""Index of what everything means in the np array"""
from enum import IntEnum, auto


class PokArray(IntEnum):
    """Gives the index of everything in the array"""
    def _generate_next_value_(name, start, count, last_values):  # pylint: disable=(W0237, E0213)
        return count

    LEVEL = auto()
    TYPE1 = auto()
    TYPE2 = auto()
    CURRENT_HP = auto()
    MAX_HP = auto()
    ATTACK = auto()
    DEFENSE = auto()
    SPECIAL_ATTACK = auto()
    SPECIAL_DEFENSE = auto()
    SPEED = auto()
    ATTACK_STAT_STAGE = auto()
    DEFENSE_STAT_STAGE = auto()
    SPECIAL_ATTACK_STAT_STAGE = auto()
    SPECIAL_DEFENSE_STAT_STAGE = auto()
    SPEED_STAT_STAGE = auto()
    ACCURACY_STAT_STAGE = auto()
    EVASION_STAT_STAGE = auto()
    STATUS = auto()
    SLEEP_COUNTER = auto()
    BADLY_POISON = auto()
    TURNS = auto()
    GENDER = auto()
    WEIGHT = auto()
