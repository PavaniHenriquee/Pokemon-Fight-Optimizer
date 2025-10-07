"""Fast integer constants for array indexing - no enum overhead"""
# import idx_nparray as _enums


# === EXTRACT AND CACHE LENGTHS AS PLAIN INTS ===
POK_LEN = 417  # len(PokArray) - hardcoded to avoid any enum calls
BASE_LEN = 25  # len(BaseArray)
AB_LEN = 11    # len(AbilityIdx)
BASE_MOVE_LEN = 45  # len(MoveArray)
FLAGS_LEN = 35 # len(MoveFlags)
SEC_LEN = 13   # len(SecondaryArray)
FIELD_LEN = 12

# Pre-calculate common offsets
OFFSET_MOVE = BASE_LEN + AB_LEN  # 36 - where moves start in pokemon array
OFFSET_SEC = BASE_MOVE_LEN + FLAGS_LEN  # 81 - where secondary starts in move array
MOVE_STRIDE = BASE_MOVE_LEN + FLAGS_LEN + SEC_LEN  # 94 - full size of one move
OFFSET_ITEM = OFFSET_MOVE + (4 * MOVE_STRIDE)  # where item starts after 4 moves

# === Pokemon Array Indices (plain integers) ===
class Pok:
    """Pokemon array indices - pure integers, no enum overhead"""
    ID = 0
    LEVEL = 1
    TYPE1 = 2
    TYPE2 = 3
    CURRENT_HP = 4
    MAX_HP = 5
    ATTACK = 6
    DEFENSE = 7
    SPECIAL_ATTACK = 8
    SPECIAL_DEFENSE = 9
    SPEED = 10
    ATTACK_STAT_STAGE = 11
    DEFENSE_STAT_STAGE = 12
    SPECIAL_ATTACK_STAT_STAGE = 13
    SPECIAL_DEFENSE_STAT_STAGE = 14
    SPEED_STAT_STAGE = 15
    ACCURACY_STAT_STAGE = 16
    EVASION_STAT_STAGE = 17
    STATUS = 18
    VOL_STATUS = 19
    SLEEP_COUNTER = 20
    BADLY_POISON = 21
    TURNS = 22
    GENDER = 23
    WEIGHT = 24
    AB_ID = 25
    AB_WHEN = 26
    AB_BREAKABLE = 27
    AB_CANT_SUPRESS = 28
    AB_FAIL_ROLEPLAY = 29
    AB_FAIL_SKILL_SWAP = 30
    AB_NO_ENTRAIN = 31
    AB_NO_RECEIVER = 32
    AB_NO_TRACER = 33
    AB_NO_TRANSFORM = 34
    AB_SUPRESS_WEATHER = 35
    MOVE1_ID = 36  # OFFSET_MOVE
    MOVE2_ID = 129  # MOVE1_ID + MOVE_STRIDE
    MOVE3_ID = 222  # MOVE2_ID + MOVE_STRIDE
    MOVE4_ID = 315  # MOVE3_ID + MOVE_STRIDE
    ITEM_ID = 408   # MOVE4_ID + MOVE_STRIDE

class Move:
    """Move array indices - pure integers"""
    ID = 0
    CATEGORY = 1
    TYPE = 2
    TARGET = 3
    POWER = 4
    ACCURACY = 5
    CRIT_RATIO = 6
    WILL_CRIT = 7
    OH_KO = 8
    SHEER_FORCE = 9
    PRIORITY = 10
    OVERRIDE_OFF_POK = 11
    OVERRIDE_OFF_STAT = 12
    OVERRIDE_DEF_STAT = 13
    IGNORE_DEF = 14
    IGNORE_IMMUNITY = 15
    PP = 16
    PP_UP = 17
    MULTI_HIT_MIN = 18
    MULTI_HIT_MAX = 19
    SELF_SWITCH = 20
    FORCE_SWITCH = 21
    NON_GHOST = 22
    IGNORE_AB = 23
    DAMAGE = 24
    SPREAD_HIT = 25
    SPREAD_MOD = 26
    CRIT_MOD = 27
    FORCE_STAB = 28
    STATUS = 29
    VOL_STATUS = 30
    HAS_CRASH_DAMAGE = 31
    SELFDESTRUCT = 32
    SLEEP_USABLE = 33
    SMART_TARGET = 34
    BOOST_ATK = 35
    BOOST_DEF = 36
    BOOST_SPATK = 37
    BOOST_SPDEF = 38
    BOOST_SPEED = 39
    BOOST_ACC = 40
    BOOST_EV = 41
    SIDE_CONDITION = 42
    RECOIL = 43
    DRAIN = 44

class Flags:
    """Move Flags indices - pure integers"""
    BYPASS_SUB = 0
    BITE = 1
    BULLET = 2
    CANT_USE_TWICE = 3
    CHARGE = 4
    CONTACT = 5
    DANCE = 6
    DEFROST = 7
    DISTANCE = 8
    FAIL_COPYCAT = 9
    FAIL_ENCORE = 10
    FAIL_INSTRUCT = 11
    FAIL_ME_FIRST = 12
    FAIL_MIMIC = 13
    FUTURE_MOVE = 14
    GRAVITY = 15
    HEAL = 16
    METRONOME = 17
    MIRROR = 18
    MUST_PRESSURE = 19
    NO_ASSIST = 20
    NO_PARENTAL_BOND = 21
    NO_SKETCH = 22
    NO_SLEEP_TALK = 23
    PLEDGE_COMBO = 24
    POWDER = 25
    PROTECT = 26
    PULSE = 27
    PUNCH = 28
    RECHARGE = 29
    REFLECTABLE = 30
    SLICING = 31
    SNATCHING = 32
    SOUND = 33
    WIND = 34

class Sec:
    """Secondary array indices - pure integers"""
    CHANCE = 0
    SEC_TARGET = 1
    SEC_BOOST_ATK = 2
    SEC_BOOST_DEF = 3
    SEC_BOOST_SPATK = 4
    SEC_BOOST_SPDEF = 5
    SEC_BOOST_SPEED = 6
    SEC_BOOST_ACC = 7
    SEC_BOOST_EV = 8
    VOL_STATUS = 9
    STATUS = 10
    CHANCE2 = 11
    VOL_STATUS2 = 12

class Field:
    """Battlefield indices - pure integers"""
    MY_POK = 5004  # ALL_POK_LEN = POK_LEN * 12
    OPP_POK = 5005
    TURN = 5006
    WEATHER = 5007
    WEATHER_DURATION = 5008
    TRICKROOM = 5009
    TRICKROOM_DURATION = 5010
    MY_SCREEN = 5011
    MY_SCREEN_DURATION = 5012
    OPP_SCREEN = 5013
    OPP_SCREEN_DURATION = 5014
    PHASE = 5015
    OPP_MOVE = 5016

'''# Verification function (run once to validate hardcoded values)
def _verify_constants():
    """Run this once to verify hardcoded values match enum values"""
    errors = []

    if POK_LEN != len(_enums.PokArray):
        errors.append(f"POK_LEN mismatch: {POK_LEN} != {len(_enums.PokArray)}")
    if BASE_LEN != len(_enums.BaseArray):
        errors.append(f"BASE_LEN mismatch: {BASE_LEN} != {len(_enums.BaseArray)}")
    if BASE_MOVE_LEN != len(_enums.MoveArray):
        errors.append(f"MOVE_LEN mismatch: {BASE_MOVE_LEN} != {len(_enums.MoveArray)}")
    if FLAGS_LEN != len(_enums.MoveFlags):
        errors.append(f"FLAGS_LEN mismatch: {FLAGS_LEN} != {len(_enums.MoveFlags)}")
    if SEC_LEN != len(_enums.SecondaryArray):
        errors.append(f"SEC_LEN mismatch: {SEC_LEN} != {len(_enums.SecondaryArray)}")

    # Verify a few key indices
    if Pok.MOVE1_ID != int(_enums.PokArray.MOVE1_ID):
        errors.append(f"Pok.MOVE1 mismatch: {Pok.MOVE1_ID} != {int(_enums.PokArray.MOVE1_ID)}")
    if Pok.MOVE2_ID != int(_enums.PokArray.MOVE2_ID):
        errors.append(f"Pok.MOVE2 mismatch: {Pok.MOVE2_ID} != {int(_enums.PokArray.MOVE2_ID)}")
    if Pok.MOVE3_ID != int(_enums.PokArray.MOVE3_ID):
        errors.append(f"Pok.MOVE3 mismatch: {Pok.MOVE3_ID} != {int(_enums.PokArray.MOVE3_ID)}")
    if Pok.MOVE4_ID != int(_enums.PokArray.MOVE4_ID):
        errors.append(f"Pok.MOVE4 mismatch: {Pok.MOVE4_ID} != {int(_enums.PokArray.MOVE4_ID)}")
    if Pok.ITEM_ID != int(_enums.PokArray.ITEM_ID):
        errors.append(f"Pok.MOVE4 mismatch: {Pok.ITEM_ID} != {int(_enums.PokArray.ITEM_ID)}")

    if errors:
        raise ValueError("Constant verification failed:\n" + "\n".join(errors))
    return True

# Uncomment to verify during development:
_verify_constants()'''
