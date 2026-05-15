"""Helper for transformation of Names to number, so i can use Numpy efficiently"""
from types import SimpleNamespace
import numpy as np
from Models.idx_const import Pok, POK_LEN


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


TypesIdToName = {v: k for k, v in Types.__dict__.items() if not k.startswith("__")}


Stat = SimpleNamespace(
    ATTACK = 0,
    DEFENSE = 1,
    SPECIAL_ATTACK = 2,
    SPECIAL_DEFENSE = 3,
    SPEED = 4
)


class Status:
    """Status to numbers"""
    SLEEP = 1
    FREEZE = 2
    PARALYSIS = 3
    BURN = 4
    POISON = 5
    TOXIC = 6


StatusIdToName = {v: k for k, v in Status.__dict__.items() if not k.startswith("__")}


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


class SideCondition:
    """Side condition to numbers"""
    STEALTH_ROCK = 1
    SPIKES = 2
    TOXIC_SPIKES = 4
    STIKCY_WEBS = 8
    REFLECT = 16
    LIGHT_SCREEN = 32
    AURORA_VEIL = 64


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


def vol_status():
    """returns 0, because you can't start a battle with any volatile status"""
    return 0


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



class AbilityActivation:
    """When will the ability be used"""
    ON_MODIFY_STAT  = 1
    ON_BASE_POWER   = 2
    ON_CHANGE_STAT  = 4
    ON_DAMAGE       = 8
    ON_START        = 16
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



ItemType = SimpleNamespace(
    BERRY = 0,
    CONSUMABLE = 1,
    CHOICE = 2,
    HELD = 3,
    MEGA = 4
)


class ItemActivation:
    """When will the ability be used"""
    SWITCH_IN         = 1
    ON_PREPARE_HIT    = 2
    ON_DAMAGE         = 4
    ON_WEATHER_CHANGE = 8
    ON_END            = 16
    ON_RECEIVE_DAMAGE = 32
    ON_SELECTION      = 64


def count_party(pty):
    """How many pok are alive"""
    pok_features = POK_LEN
    return np.count_nonzero(pty[Pok.CURRENT_HP :: pok_features] > 0)


def count_Id(pty):
    """Pokemon in party, no matter if alive or dead"""
    pok_features = POK_LEN
    return np.count_nonzero(pty[Pok.ID :: pok_features] > 0)


class Weather:
    """Types of Weather"""
    SUN       = 1
    RAIN      = 2
    HAIL      = 3
    SANDSTORM = 4


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
