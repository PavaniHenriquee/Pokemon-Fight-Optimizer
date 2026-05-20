"""Helper for transformation of Names to number, so i can use Numpy efficiently"""
from types import SimpleNamespace
from dataclasses import dataclass
import numpy as np
from Models.idx_const import Pok, POK_LEN


@dataclass(slots=True)
class Types:
    """Types to numbers"""
    NORMAL = 1
    FIGHTING = 2
    FLYING = 3
    POISON = 4
    GROUND = 5
    ROCK = 6
    BUG = 7
    GHOST = 8
    STEEL = 9
    FIRE = 10
    WATER = 11
    GRASS = 12
    ELECTRIC = 13
    PSYCHIC = 14
    ICE = 15
    DRAGON = 16
    DARK = 17
    FAIRY = 18


@dataclass(slots=True)
class Status:
    """Status to numbers"""
    SLEEP = 1
    FREEZE = 2
    PARALYSIS = 3
    BURN = 4
    POISON = 5
    TOXIC = 6


@dataclass(slots=True)
class VolStatus:
    """Volatile status to numbers, using bitmap"""
    FLINCH = 1
    CONFUSION = 2
    HEAL_BLOCK = 4
    SALT_CURE = 8
    SPARKLIN_ARIA = 16
    PARTIALLY_TRAPPED = 32
    LEECH_SEED = 64
    CURSE = 128
    ATTRACT = 256


@dataclass(slots=True)
class SideCondition:
    """Side condition to numbers"""
    STEALTH_ROCK = 1
    SPIKES = 2
    TOXIC_SPIKES = 4
    STIKCY_WEBS = 8
    REFLECT = 16
    LIGHT_SCREEN = 32
    AURORA_VEIL = 64


@dataclass(slots=True)
class Gender:
    """Gender to numbers"""
    GENDERLESS = 0
    MALE = 1
    FEMALE = 2


def type_to_number(types: list):
    """Receive the types list and transform them in numbers"""
    type1 = getattr(Types, types[0].upper())
    try:
        type2 = getattr(Types, types[1].upper())
    except (KeyError, IndexError):
        type2 = 0

    return type1, type2


def gender_to_number(gender):
    """Transform it to number"""
    if gender is None:
        g = 'Genderless'
    else:
        g = gender

    return getattr(Gender, g.upper())


@dataclass(slots=True)
class Target:
    """Target to numbers"""
    NORMAL = 0
    ADJACENT_ALLY = 1
    ADJACENT_ALLY_OR_SELF = 2
    ADJACENT_FOE = 3
    ALL = 4
    ALL_ADJACENT = 5
    ALL_ADJACENT_FOES = 6
    ALLIES = 7
    ALLY_SIDE = 8
    ALLY_TEAM = 9
    ANY = 10
    FOE_SIDE = 11
    RANDOM_NORMAL = 12
    SCRIPTED = 13
    SELF = 14


@dataclass(slots=True)
class AbilityActivation:
    """When will the ability be used"""
    ON_MODIFY_STAT  = 1
    ON_BASE_POWER   = 2
    ON_CHANGE_STAT  = 4
    ON_DAMAGE       = 8
    ON_SWITCH_IN    = 16
    ON_CRITICAL     = 32
    ON_TRY_MOVE     = 64
    ON_SET_STATUS   = 128
    ON_MODIFY_SPEED = 256
    ON_WEATHER      = 512
    ON_MODIFY_ACC   = 1024
    ON_RESIDUAL     = 2048


class MoveCategory:
    """
    Physical, Special, Status
    """
    PHYSICAL = 1
    SPECIAL = 2
    STATUS = 3


PHYSICAL_SPECIAL = {MoveCategory.PHYSICAL, MoveCategory.SPECIAL}


ItemType = SimpleNamespace(
    BERRY = 0,
    CONSUMABLE = 1,
    CHOICE = 2,
    HELD = 3,
    MEGA = 4
)


@dataclass(slots=True)
class ItemActivation:
    """When will the ability be used"""
    SWITCH_IN         = 1
    ON_PREPARE_HIT    = 2
    ON_DAMAGE         = 4
    ON_WEATHER_CHANGE = 8
    ON_END            = 16
    ON_RECEIVE_DAMAGE = 32
    ON_SELECTION      = 64


_HP_OFFSETS_NP = np.array([i * POK_LEN + Pok.CURRENT_HP for i in range(6)])

def count_party(pty):
    """How many pok are alive"""
    return int(np.count_nonzero(pty[_HP_OFFSETS_NP]))

def count_Id(pty):
    """Pokemon in party, no matter if alive or dead"""
    pok_features = POK_LEN
    return np.count_nonzero(pty[Pok.ID :: pok_features])


@dataclass(slots=True)
class Weather:
    """Types of Weather"""
    SUN       = 1
    RAIN      = 2
    HAIL      = 3
    SANDSTORM = 4


@dataclass(slots=True)
class Enemy_AI_Knows:
    """
    Bit allocation for if the ai knows the moves and the ability
    of facing Pokemon
    """
    ABILITY = 1
    MOVE1 = 2
    MOVE2 = 4
    MOVE3 = 8
    MOVE4 = 16


@dataclass(slots=True)
class ActionType:
    """
    Actions
    """
    MOVE = 1
    SWITCH = 2


@dataclass(slots=True)
class BattlePhase:
    """
    Where i'm at in the battle
    """
    TURN_START = 0
    DEATH_END_OF_TURN = 1


TARGET_SELF_SIDE = (
    Target.ADJACENT_ALLY,
    Target.ADJACENT_ALLY_OR_SELF,
    Target.ALLIES,
    Target.ALLY_SIDE,
    Target.SELF
)
TARGET_OPP_SIDE = (
    Target.NORMAL,
    Target.ADJACENT_FOE,
    Target.ALL_ADJACENT_FOES,
    Target.ANY,
    Target.FOE_SIDE,
    Target.RANDOM_NORMAL,
    Target.SCRIPTED
)
