"""Fast integer constants for array indexing - no enum overhead"""
from dataclasses import dataclass

def _int_constants(cls):
    return [value for name, value in cls.__dict__.items() if name.isupper() and isinstance(value, int)]


def _length(cls, start_offset=0):
    values = _int_constants(cls)
    return max(values) - start_offset + 1


@dataclass(slots=True)
class Pok:
    """Pokemon array indices"""
    ID                        = 0
    LEVEL                     = ID + 1
    TYPE1                     = LEVEL + 1
    TYPE2                     = TYPE1 + 1
    CURRENT_HP                = TYPE2 + 1
    MAX_HP                    = CURRENT_HP + 1
    ATTACK                    = MAX_HP + 1
    DEFENSE                   = ATTACK + 1
    SPECIAL_ATTACK            = DEFENSE + 1
    SPECIAL_DEFENSE           = SPECIAL_ATTACK + 1
    SPEED                     = SPECIAL_DEFENSE + 1
    ATTACK_STAT_STAGE         = SPEED + 1
    DEFENSE_STAT_STAGE        = ATTACK_STAT_STAGE + 1
    SPECIAL_ATTACK_STAT_STAGE = DEFENSE_STAT_STAGE + 1
    SPECIAL_DEFENSE_STAT_STAGE= SPECIAL_ATTACK_STAT_STAGE + 1
    SPEED_STAT_STAGE          = SPECIAL_DEFENSE_STAT_STAGE + 1
    ACCURACY_STAT_STAGE       = SPEED_STAT_STAGE + 1
    EVASION_STAT_STAGE        = ACCURACY_STAT_STAGE + 1
    STATUS                    = EVASION_STAT_STAGE + 1
    VOL_STATUS                = STATUS + 1
    SLEEP_COUNTER             = VOL_STATUS + 1
    BADLY_POISON              = SLEEP_COUNTER + 1
    TURNS                     = BADLY_POISON + 1
    GENDER                    = TURNS + 1
    WEIGHT                    = GENDER + 1
    AB_ID                     = WEIGHT + 1
    AB_WHEN                   = AB_ID + 1
    AB_BREAKABLE              = AB_WHEN + 1
    AB_CANT_SUPRESS           = AB_BREAKABLE + 1
    AB_FAIL_ROLEPLAY          = AB_CANT_SUPRESS + 1
    AB_FAIL_SKILL_SWAP        = AB_FAIL_ROLEPLAY + 1
    AB_NO_ENTRAIN             = AB_FAIL_SKILL_SWAP + 1
    AB_NO_RECEIVER            = AB_NO_ENTRAIN + 1
    AB_NO_TRACER              = AB_NO_RECEIVER + 1
    AB_NO_TRANSFORM           = AB_NO_TRACER + 1
    AB_SUPRESS_WEATHER        = AB_NO_TRANSFORM + 1

@dataclass(slots=True)
class Move:
    """Move array indices - pure integers"""
    ID               = 0
    CATEGORY         = ID + 1
    TYPE             = CATEGORY + 1
    TARGET           = TYPE + 1
    POWER            = TARGET + 1
    ACCURACY         = POWER + 1
    CRIT_RATIO       = ACCURACY + 1
    WILL_CRIT        = CRIT_RATIO + 1
    OH_KO            = WILL_CRIT + 1
    PRIORITY         = OH_KO + 1
    OVERRIDE_OFF_STAT= PRIORITY + 1
    OVERRIDE_DEF_STAT= OVERRIDE_OFF_STAT + 1
    IGNORE_DEF       = OVERRIDE_DEF_STAT + 1
    IGNORE_IMMUNITY  = IGNORE_DEF + 1
    PP               = IGNORE_IMMUNITY + 1
    PP_UP            = PP + 1
    MULTI_HIT_MIN    = PP_UP + 1
    MULTI_HIT_MAX    = MULTI_HIT_MIN + 1
    SELF_SWITCH      = MULTI_HIT_MAX + 1
    FORCE_SWITCH     = SELF_SWITCH + 1
    DAMAGE           = FORCE_SWITCH + 1
    STATUS           = DAMAGE + 1
    VOL_STATUS       = STATUS + 1
    HAS_CRASH_DAMAGE = VOL_STATUS + 1
    SELFDESTRUCT     = HAS_CRASH_DAMAGE + 1
    SLEEP_USABLE     = SELFDESTRUCT + 1
    SMART_TARGET     = SLEEP_USABLE + 1
    BOOST_ATK        = SMART_TARGET + 1
    BOOST_DEF        = BOOST_ATK + 1
    BOOST_SPATK      = BOOST_DEF + 1
    BOOST_SPDEF      = BOOST_SPATK + 1
    BOOST_SPEED      = BOOST_SPDEF + 1
    BOOST_ACC        = BOOST_SPEED + 1
    BOOST_EV         = BOOST_ACC + 1
    SIDE_CONDITION   = BOOST_EV + 1
    RECOIL           = SIDE_CONDITION + 1
    DRAIN            = RECOIL + 1


BASE_MOVE_LEN = _length(Move)


@dataclass(slots=True)
class Flags:
    """Move Flags indices - pure integers"""
    BYPASS_SUB       = BASE_MOVE_LEN
    BITE             = BYPASS_SUB + 1
    BULLET           = BITE + 1
    CANT_USE_TWICE   = BULLET + 1
    CHARGE           = CANT_USE_TWICE + 1
    CONTACT          = CHARGE + 1
    DANCE            = CONTACT + 1
    DEFROST          = DANCE + 1
    DISTANCE         = DEFROST + 1
    FAIL_COPYCAT     = DISTANCE + 1
    FAIL_ENCORE      = FAIL_COPYCAT + 1
    FAIL_INSTRUCT    = FAIL_ENCORE + 1
    FAIL_ME_FIRST    = FAIL_INSTRUCT + 1
    FAIL_MIMIC       = FAIL_ME_FIRST + 1
    FUTURE_MOVE      = FAIL_MIMIC + 1
    GRAVITY          = FUTURE_MOVE + 1
    HEAL             = GRAVITY + 1
    METRONOME        = HEAL + 1
    MIRROR           = METRONOME + 1
    MUST_PRESSURE    = MIRROR + 1
    NO_ASSIST        = MUST_PRESSURE + 1
    NO_PARENTAL_BOND = NO_ASSIST + 1
    NO_SKETCH        = NO_PARENTAL_BOND + 1
    NO_SLEEP_TALK    = NO_SKETCH + 1
    PLEDGE_COMBO     = NO_SLEEP_TALK + 1
    POWDER           = PLEDGE_COMBO + 1
    PROTECT          = POWDER + 1
    PULSE            = PROTECT + 1
    PUNCH            = PULSE + 1
    RECHARGE         = PUNCH + 1
    REFLECTABLE      = RECHARGE + 1
    SLICING          = REFLECTABLE + 1
    SNATCHING        = SLICING + 1
    SOUND            = SNATCHING + 1
    WIND             = SOUND + 1


FLAGS_LEN = _length(Flags, BASE_MOVE_LEN)
OFFSET_SEC = BASE_MOVE_LEN + FLAGS_LEN


@dataclass(slots=True)
class Sec:
    """Secondary array indices - pure integers"""
    CHANCE      = OFFSET_SEC
    TARGET      = CHANCE + 1
    BOOST_ATK   = TARGET + 1
    BOOST_DEF   = BOOST_ATK + 1
    BOOST_SPATK = BOOST_DEF + 1
    BOOST_SPDEF = BOOST_SPATK + 1
    BOOST_SPEED = BOOST_SPDEF + 1
    BOOST_ACC   = BOOST_SPEED + 1
    BOOST_EV    = BOOST_ACC + 1
    VOL_STATUS  = BOOST_EV + 1
    STATUS      = VOL_STATUS + 1
    CHANCE2     = STATUS + 1
    VOL_STATUS2 = CHANCE2 + 1


SEC_LEN = _length(Sec, OFFSET_SEC)


@dataclass(slots=True)
class Item:
    """Index for Items"""
    ID                 = 0
    WHEN               = ID + 1
    ITEM_TYPE          = WHEN + 1
    FLING_POWER        = ITEM_TYPE + 1
    FLING_STATUS       = FLING_POWER + 1
    FLING_VOLATILE     = FLING_STATUS + 1
    NATURAL_GIFT_POWER = FLING_VOLATILE + 1
    NATURAL_GIFT_TYPE  = NATURAL_GIFT_POWER + 1
    ITEM_USER          = NATURAL_GIFT_TYPE + 1


ITEM_LEN      = _length(Item)
BASE_LEN      = Pok.AB_ID
AB_LEN        = Pok.AB_SUPRESS_WEATHER - Pok.AB_ID + 1
MOVE_STRIDE   = BASE_MOVE_LEN + FLAGS_LEN + SEC_LEN
OFFSET_MOVE   = BASE_LEN + AB_LEN
OFFSET_ITEM   = OFFSET_MOVE + (4 * MOVE_STRIDE)

Pok.MOVE1_ID = OFFSET_MOVE
Pok.MOVE2_ID = Pok.MOVE1_ID + MOVE_STRIDE
Pok.MOVE3_ID = Pok.MOVE2_ID + MOVE_STRIDE
Pok.MOVE4_ID = Pok.MOVE3_ID + MOVE_STRIDE
Pok.ITEM_ID  = Pok.MOVE4_ID + MOVE_STRIDE

POK_LEN       = Pok.ITEM_ID + ITEM_LEN


@dataclass(slots=True)
class Field:
    """Battlefield indices - pure integers"""
    MY_POK             = POK_LEN * 12
    OPP_POK            = MY_POK + 1
    MY_ENTER_FIELD     = OPP_POK + 1
    OPP_ENTER_FIELD    = MY_ENTER_FIELD + 1
    TURN               = OPP_ENTER_FIELD + 1
    WEATHER            = TURN + 1
    WEATHER_DURATION   = WEATHER + 1
    TRICKROOM          = WEATHER_DURATION + 1
    TRICKROOM_DURATION = TRICKROOM + 1
    MY_SCREEN          = TRICKROOM_DURATION + 1
    MY_SCREEN_DURATION = MY_SCREEN + 1
    OPP_SCREEN         = MY_SCREEN_DURATION + 1
    OPP_SCREEN_DURATION= OPP_SCREEN + 1
    PHASE              = OPP_SCREEN_DURATION + 1
    OPP_MOVE           = PHASE + 1
    AI_ITEM1           = OPP_MOVE + 1
    AI_ITEM2           = AI_ITEM1 + 1
    AI_ITEM3           = AI_ITEM2 + 1
    AI_ITEM4           = AI_ITEM3 + 1
    MY_LAST_MOVE       = AI_ITEM4 + 1
    AI_TOOK_DMG_LAST_TURN = MY_LAST_MOVE + 1
    AI_KNOWS           = AI_TOOK_DMG_LAST_TURN + 1

# Last one minus first one +1 because idx 0
FIELD_LEN = Field.AI_KNOWS - Field.MY_POK + 1
