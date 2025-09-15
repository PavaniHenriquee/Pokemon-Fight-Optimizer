"""Helper for transformation of Names to number, so i can use Numpy efficiently"""
from enum import Enum


class Types(Enum):
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


class Status(Enum):
    """Status to numbers"""
    SLEEP = 1
    FREEZE = 2
    PARALYSIS = 3
    BURN = 4
    POISON = 5


class Gender(Enum):
    """Gender to numbers"""
    GENDERLESS = 0
    MALE = 1
    FEMALE = 2


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
