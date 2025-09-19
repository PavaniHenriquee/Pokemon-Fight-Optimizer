"""Helper for transformation of Names to number, so i can use Numpy efficiently"""
from enum import auto, IntEnum, IntFlag


class Types(IntEnum):
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


class Stat(IntEnum):
    """Stats to number, used for override stat in move description, like body press"""
    def _generate_next_value_(name, start, count, last_values):  # pylint:disable=E0213
        return count
    ATTACK = auto()
    DEFENSE = auto()
    SPECIAL_ATTACK = auto()
    SPECIAL_DEFENSE = auto()
    SPEED = auto()


class Status(IntEnum):
    """Status to numbers"""
    def _generate_next_value_(name, start, count, last_values):  # pylint:disable=E0213
        return count + 1
    SLEEP = auto()
    FREEZE = auto()
    PARALYSIS = auto()
    BURN = auto()
    POISON = auto()
    TOXIC = auto()


class VolStatus(IntFlag):
    """Volatile status to numbers"""
    FLINCH = auto()
    CONFUSION = auto()
    HEAL_BLOCK = auto()
    SALT_CURE = auto()
    SPARKLIN_ARIA = auto()
    PARTIALLY_TRAPPED = auto()


class SideCondition(IntFlag):
    """Side condition to numbers"""
    STEALTH_ROCK = auto()
    SPIKES = auto()
    TOXIC_SPIKES = auto()
    STIKCY_WEBS = auto()
    REFLECT = auto()
    LIGHT_SCREEN = auto()
    AURORA_VEIL = auto()


class Gender(IntEnum):
    """Gender to numbers"""
    def _generate_next_value_(name, start, count, last_values):  # pylint:disable=E0213
        return count
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


def status_to_number(status):
    """Transform it to number"""
    if not isinstance(status, str):
        return 0

    return Status[status.upper()]


def gender_to_number(gender):
    """Transform it to number"""
    if gender is None:
        g = 'Genderless'
    else:
        g = gender

    return Gender[g.upper()]


class Target(IntEnum):
    """Which target is the move"""
    def _generate_next_value_(name, start, count, last_values):  # pylint:disable=E0213
        return count

    NORMAL = auto()
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
    RANDOM_NORMAL = auto()
    SCRIPTED = auto()
    SELF = auto()


class AbilityActivation(IntFlag):
    """When will the ability be used"""
    SWITCH_IN = auto()
    ON_PREPARE_HIT = auto()
    ON_DAMAGE = auto()
    ON_WEATHER_CHANGE = auto()
    ON_END = auto()
    ON_RECEIVE_DAMAGE = auto()


class MoveCategory(IntEnum):
    """The three move types"""
    def _generate_next_value_(name, start, count, last_values):  # pylint:disable=E0213
        return count
    PHYSICAL = auto()
    SPECIAL = auto()
    STATUS = auto()


class ItemType(IntEnum):
    """Item type"""
    def _generate_next_value_(name, start, count, last_values):  # pylint:disable=E0213
        return count
    BERRY = auto()
    CONSUMABLE = auto()
    CHOICE = auto()
    HELD = auto()
    MEGA = auto()


class ItemActivation(IntFlag):
    """When will the ability be used"""
    SWITCH_IN = auto()
    ON_PREPARE_HIT = auto()
    ON_DAMAGE = auto()
    ON_WEATHER_CHANGE = auto()
    ON_END = auto()
    ON_RECEIVE_DAMAGE = auto()
    ON_SELECTION = auto()
