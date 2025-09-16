"""Helper for transformation of Names to number, so i can use Numpy efficiently"""
from enum import Enum, auto


class Types(Enum):
    """Types to numbers"""
    def _generate_next_value_(name, start, count, last_values):  # pylint:disable=E0213
        return count + 1
    NORMAL = auto()
    FIGHTING = auto()
    FLYING = auto()
    POISON = auto()
    GROUND = auto()
    ROCK = auto()
    BUG = auto()
    GHOST = auto()
    STEEL = auto()
    FIRE = auto()
    WATER = auto()
    GRASS = auto()
    ELECTRIC = auto()
    PSYCHIC = auto()
    ICE = auto()
    DRAGON = auto()
    DARK = auto()
    FAIRY = auto()


class Status(Enum):
    """Status to numbers"""
    SLEEP = auto()
    FREEZE = auto()
    PARALYSIS = auto()
    BURN = auto()
    POISON = auto()


class Gender(Enum):
    """Gender to numbers"""
    GENDERLESS = auto()
    MALE = auto()
    FEMALE = auto()


def type_to_number(types: list):
    """Receive the types list and transform them in numbers"""
    type1 = Types[types[0].upper()]
    try:
        type2 = Types[types[1].upper()]
    except (KeyError, IndexError):
        type2 = 0

    return type1, type2


def status_to_number(status: str):
    """Transform it to number"""
    return Status[status.upper()]


def gender_to_number(gender):
    """Transform it to number"""
    if gender is None:
        g = 'Genderless'
    else:
        g = gender

    return Gender[g.upper()]


class Target(Enum):
    """Which target is the move"""
    ADJACENT_ALLY = auto()
    ADJACENT_ALLY_OR_SELF = auto()
    ADJACENT_FOE = auto()
    ALL = auto()
    ALL_ADJACENT = auto()
    ALL_ADJACENT_FOES = auto()
    ALLIES = auto()
    ALLY_SIDE = auto()
    ALLY_TEAM = auto()
    ANY = auto()
    FOE_SIDE = auto()
    NORMAL = auto()
    RANDOM_NORMAL = auto()
    SCRIPTED = auto()
    SELF = auto()


class MoveFlags(Enum):
    """Move Flags index"""
    BYPASSSUB = auto()
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
    METRONOME = ()
    MIRROR = auto()
    MUST_PRESSURE = auto()
    NO_ASSIST = auto()
    NO_SKY = auto()
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
