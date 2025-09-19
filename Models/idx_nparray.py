"""Index of what everything means in the np array"""
from enum import IntEnum, auto


class MoveFlags(IntEnum):
    """Move Flags index"""
    def _generate_next_value_(name, start, count, last_values):  # pylint:disable=E0213
        return count

    BYPASS_SUB = auto()
    BITE = auto()
    BULLET = auto()
    CANT_USE_TWICE = auto()
    CHARGE = auto()
    CONTACT = auto()
    DANCE = auto()
    DEFROST = auto()
    DISTANCE = auto()
    FAIL_COPYCAT = auto()
    FAIL_ENCORE = auto()
    FAIL_INSTRUCT = auto()
    FAIL_ME_FIRST = auto()
    FAIL_MIMIC = auto()
    FUTURE_MOVE = auto()
    GRAVITY = auto()
    HEAL = auto()
    METRONOME = auto()
    MIRROR = auto()
    MUST_PRESSURE = auto()
    NO_ASSIST = auto()
    NO_PARENTAL_BOND = auto()
    NO_SKETCH = auto()
    NO_SLEEP_TALK = auto()
    PLEDGE_COMBO = auto()
    POWDER = auto()
    PROTECT = auto()
    PULSE = auto()
    PUNCH = auto()
    RECHARGE = auto()
    REFLECTABLE = auto()
    SLICING = auto()
    SNATCHING = auto()
    SOUND = auto()
    WIND = auto()


class SecondaryArray(IntEnum):
    """Index for secondary effects(where it only has 2 secondary effects if it's one of the fangs moves)"""
    def _generate_next_value_(name, start, count, last_values):  # pylint: disable=(W0237, E0213)
        return count

    CHANCE = auto()
    SEC_TARGET = auto()
    SEC_BOOST_ATK = auto()
    SEC_BOOST_DEF = auto()
    SEC_BOOST_SPATK = auto()
    SEC_BOOST_SPDEF = auto()
    SEC_BOOST_SPEED = auto()
    SEC_BOOST_ACC = auto()
    SEC_BOOST_EV = auto()
    VOL_STATUS = auto()
    STATUS = auto()
    CHANCE2 = auto()
    VOL_STATUS2 = auto()


class MoveArray(IntEnum):
    """Index for each move"""
    def _generate_next_value_(name, start, count, last_values):  # pylint: disable=(W0237, E0213)
        return count

    ID = auto()
    CATEGORY = auto()
    TYPE = auto()
    TARGET = auto()
    POWER = auto()
    ACCURACY = auto()
    CRIT_RATIO = auto()
    WILL_CRIT = auto()
    OH_KO = auto()
    SHEER_FORCE = auto()
    PRIORITY = auto()
    OVERRIDE_OFF_POK = auto()
    OVERRIDE_OFF_STAT = auto()
    OVERRIDE_DEF_STAT = auto()
    IGNORE_DEF = auto()
    IGNORE_IMMUNITY = auto()
    PP = auto()
    PP_UP = auto()
    MULTI_HIT_MIN = auto()
    MULTI_HIT_MAX = auto()
    SELF_SWITCH = auto()
    NON_GHOST = auto()
    IGNORE_AB = auto()
    DAMAGE = auto()
    SPREAD_HIT = auto()
    SPREAD_MOD = auto()
    CRIT_MOD = auto()
    FORCE_STATUS = auto()
    VOL_STATUS = auto()
    HAS_CRASH_DAMAGE = auto()
    SELFDESTRUCT = auto()
    SLEEP_USABLE = auto()
    SMART_TARGET = auto()
    BOOST_ATK = auto()
    BOOST_DEF = auto()
    BOOST_SPATK = auto()
    BOOST_SPDEF = auto()
    BOOST_SPEED = auto()
    BOOST_ACC = auto()
    BOOST_EV = auto()
    SIDE_CONDITION = auto()
    RECOIL = auto()
    DRAIN = auto()


class BaseArray(IntEnum):
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


class AbilityIdx(IntEnum):
    """Index for Ability"""
    def _generate_next_value_(name, start, count, last_values):  # pylint: disable=(W0237, E0213)
        return count

    ID = auto()
    WHEN = auto()
    BREAKABLE = auto()
    CANT_SUPRESS = auto()
    FAIL_ROLEPLAY = auto()
    FAIL_SKILL_SWAP = auto()
    NO_ENTRAIN = auto()
    NO_RECEIVER = auto()
    NO_TRACER = auto()
    NO_TRANSFORM = auto()
    SUPRESS_WEATHER = auto()


class ItemIdx(IntEnum):
    """Index for Items"""
    def _generate_next_value_(name, start, count, last_values):  # pylint: disable=(W0237, E0213)
        return count

    ID = auto()
    WHEN = auto()
    ITEM_TYPE = auto()
    FLING_POWER = auto()
    FLING_STATUS = auto()
    FLING_VOLATILE = auto()
    NATURAL_GIFT_POWER = auto()
    NATURAL_GIFT_TYPE = auto()
    ITEM_USER = auto()
