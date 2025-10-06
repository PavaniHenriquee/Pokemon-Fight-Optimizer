"""Fast integer constants for array indexing - no enum overhead"""

# Generate from your existing enums once at import time
from Models.idx_nparray import (
    PokArray as _PokArray,
    MoveArray as _MoveArray,
    MoveFlags as _MoveFlags,
    SecondaryArray as _SecondaryArray,
    BattlefieldArray as _BattlefieldArray,
    BaseArray as _BaseArray,
    AbilityIdx as _AbilityIdx
)

# Convert to plain integers - these are just constants
class Pok:
    """Pokemon array indices as plain integers"""
    ID = int(_PokArray.ID)
    LEVEL = int(_PokArray.LEVEL)
    TYPE1 = int(_PokArray.TYPE1)
    TYPE2 = int(_PokArray.TYPE2)
    CURRENT_HP = int(_PokArray.CURRENT_HP)
    MAX_HP = int(_PokArray.MAX_HP)
    ATTACK = int(_PokArray.ATTACK)
    DEFENSE = int(_PokArray.DEFENSE)
    SPECIAL_ATTACK = int(_PokArray.SPECIAL_ATTACK)
    SPECIAL_DEFENSE = int(_PokArray.SPECIAL_DEFENSE)
    SPEED = int(_PokArray.SPEED)
    ATTACK_STAT_STAGE = int(_PokArray.ATTACK_STAT_STAGE)
    DEFENSE_STAT_STAGE = int(_PokArray.DEFENSE_STAT_STAGE)
    SPECIAL_ATTACK_STAT_STAGE = int(_PokArray.SPECIAL_ATTACK_STAT_STAGE)
    SPECIAL_DEFENSE_STAT_STAGE = int(_PokArray.SPECIAL_DEFENSE_STAT_STAGE)
    SPEED_STAT_STAGE = int(_PokArray.SPEED_STAT_STAGE)
    ACCURACY_STAT_STAGE = int(_PokArray.ACCURACY_STAT_STAGE)
    EVASION_STAT_STAGE = int(_PokArray.EVASION_STAT_STAGE)
    STATUS = int(_PokArray.STATUS)
    VOL_STATUS = int(_PokArray.VOL_STATUS)
    SLEEP_COUNTER = int(_PokArray.SLEEP_COUNTER)
    BADLY_POISON = int(_PokArray.BADLY_POISON)
    TURNS = int(_PokArray.TURNS)
    GENDER = int(_PokArray.GENDER)
    WEIGHT = int(_PokArray.WEIGHT)
    AB_ID = int(_PokArray.AB_ID)
    AB_WHEN = int(_PokArray.AB_WHEN)
    MOVE1_ID = int(_PokArray.MOVE1_ID)
    MOVE2_ID = int(_PokArray.MOVE2_ID)
    MOVE3_ID = int(_PokArray.MOVE3_ID)
    MOVE4_ID = int(_PokArray.MOVE4_ID)
    ITEM_ID = int(_PokArray.ITEM_ID)

class Move:
    """Move array indices as plain integers"""
    ID = int(_MoveArray.ID)
    CATEGORY = int(_MoveArray.CATEGORY)
    TYPE = int(_MoveArray.TYPE)
    TARGET = int(_MoveArray.TARGET)
    POWER = int(_MoveArray.POWER)
    ACCURACY = int(_MoveArray.ACCURACY)
    PRIORITY = int(_MoveArray.PRIORITY)
    STATUS = int(_MoveArray.STATUS)
    DRAIN = int(_MoveArray.DRAIN)
    BOOST_ATK = int(_MoveArray.BOOST_ATK)
    BOOST_DEF = int(_MoveArray.BOOST_DEF)
    BOOST_SPATK = int(_MoveArray.BOOST_SPATK)
    BOOST_SPDEF = int(_MoveArray.BOOST_SPDEF)
    BOOST_SPEED = int(_MoveArray.BOOST_SPEED)
    BOOST_ACC = int(_MoveArray.BOOST_ACC)
    BOOST_EV = int(_MoveArray.BOOST_EV)
    FORCE_SWITCH = int(_MoveArray.FORCE_SWITCH)
    VOL_STATUS = int(_MoveArray.VOL_STATUS)
    OH_KO = int(_MoveArray.OH_KO)

class Flags:
    """Move Flags indices"""
    SOUND = int(_MoveFlags.SOUND)
    HEAL = int(_MoveFlags.HEAL)

class Sec:
    """Secondary array indices"""
    CHANCE = int(_SecondaryArray.CHANCE)
    STATUS = int(_SecondaryArray.STATUS)
    VOL_STATUS = int(_SecondaryArray.VOL_STATUS)
    SEC_BOOST_ATK = int(_SecondaryArray.SEC_BOOST_ATK)
    SEC_BOOST_DEF = int(_SecondaryArray.SEC_BOOST_DEF)
    SEC_BOOST_SPATK = int(_SecondaryArray.SEC_BOOST_SPATK)
    SEC_BOOST_SPDEF = int(_SecondaryArray.SEC_BOOST_SPDEF)
    SEC_BOOST_SPEED = int(_SecondaryArray.SEC_BOOST_SPEED)
    SEC_BOOST_ACC = int(_SecondaryArray.SEC_BOOST_ACC)
    SEC_BOOST_EV = int(_SecondaryArray.SEC_BOOST_EV)

class Field:
    """Battlefield indices"""
    MY_POK = int(_BattlefieldArray.MY_POK)
    OPP_POK = int(_BattlefieldArray.OPP_POK)
    TURN = int(_BattlefieldArray.TURN)
    PHASE = int(_BattlefieldArray.PHASE)

# Cached lengths
BASE_ARRAY_LEN = len(_BaseArray)
ABILITY_LEN = len(_AbilityIdx)
BASE_MOVE_LEN = len(_MoveArray)
MOVE_FLAGS_LEN = len(_MoveFlags)
MOVE_SECONDARY_LEN = len(_SecondaryArray)
POK_LEN = len(_PokArray)
OFFSET_MOVE = BASE_ARRAY_LEN + ABILITY_LEN
OFFSET_SEC = BASE_MOVE_LEN + MOVE_FLAGS_LEN
MOVE_STRIDE = OFFSET_SEC + MOVE_SECONDARY_LEN
OFFSET_ITEM = OFFSET_MOVE + (4 * MOVE_STRIDE)
