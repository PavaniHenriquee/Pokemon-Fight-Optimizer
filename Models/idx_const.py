"""Fast integer constants for array indexing - no enum overhead"""


# === EXTRACT AND CACHE LENGTHS AS PLAIN INTS ===
POK_LEN       = 417 # len(PokArray)
BASE_LEN      = 25  # len(BaseArray)
AB_LEN        = 11  # len(AbilityIdx)
BASE_MOVE_LEN = 45  # len(MoveArray)
FLAGS_LEN     = 35  # len(MoveFlags)
SEC_LEN       = 13  # len(SecondaryArray)
FIELD_LEN     = 12  # len(Field)
ITEM_LEN      = 9   # len(Item)

# Pre-calculate common offsets
OFFSET_MOVE = BASE_LEN + AB_LEN                    # 36 - where moves start in pokemon array
OFFSET_SEC  = BASE_MOVE_LEN + FLAGS_LEN            # 80 - where secondary starts in move array
MOVE_STRIDE = BASE_MOVE_LEN + FLAGS_LEN + SEC_LEN  # 93 - full size of one move
OFFSET_ITEM = OFFSET_MOVE + (4 * MOVE_STRIDE)      # where item starts after 4 moves

# === Pokemon Array Indices (plain integers) ===
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
    MOVE1_ID                  = OFFSET_MOVE
    MOVE2_ID                  = MOVE1_ID + MOVE_STRIDE
    MOVE3_ID                  = MOVE2_ID + MOVE_STRIDE
    MOVE4_ID                  = MOVE3_ID + MOVE_STRIDE
    ITEM_ID                   = MOVE4_ID + MOVE_STRIDE

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
    SHEER_FORCE      = OH_KO + 1
    PRIORITY         = SHEER_FORCE + 1
    OVERRIDE_OFF_POK = PRIORITY + 1
    OVERRIDE_OFF_STAT= OVERRIDE_OFF_POK + 1
    OVERRIDE_DEF_STAT= OVERRIDE_OFF_STAT + 1
    IGNORE_DEF       = OVERRIDE_DEF_STAT + 1
    IGNORE_IMMUNITY  = IGNORE_DEF + 1
    PP               = IGNORE_IMMUNITY + 1
    PP_UP            = PP + 1
    MULTI_HIT_MIN    = PP_UP + 1
    MULTI_HIT_MAX    = MULTI_HIT_MIN + 1
    SELF_SWITCH      = MULTI_HIT_MAX + 1
    FORCE_SWITCH     = SELF_SWITCH + 1
    NON_GHOST        = FORCE_SWITCH + 1
    IGNORE_AB        = NON_GHOST + 1
    DAMAGE           = IGNORE_AB + 1
    SPREAD_HIT       = DAMAGE + 1
    SPREAD_MOD       = SPREAD_HIT + 1
    CRIT_MOD         = SPREAD_MOD + 1
    FORCE_STAB       = CRIT_MOD + 1
    STATUS           = FORCE_STAB + 1
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

class Field:
    """Battlefield indices - pure integers"""
    MY_POK             = POK_LEN * 12
    OPP_POK            = MY_POK + 1
    TURN               = OPP_POK + 1
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

'''

# ==========================================
# 1. COMPONENT LENGTHS
# ==========================================
BASE_LEN      = 25
AB_LEN        = 11
BASE_MOVE_LEN = 45
FLAGS_LEN     = 35
SEC_LEN       = 13
ITEM_LEN      = 9
FIELD_LEN     = 13

# ==========================================
# 2. STRIDES & OFFSETS
# ==========================================
# Total size of a single move block
MOVE_STRIDE = BASE_MOVE_LEN + FLAGS_LEN + SEC_LEN  # 93

# Where the first move starts in the Pokemon array
OFFSET_MOVE = BASE_LEN + AB_LEN                    # 36

# ==========================================
# 3. POKEMON INDICES (Linear progression)
# ==========================================
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

# Ability indices (Relative to the end of Base stats)
AB_ID              = BASE_LEN
AB_WHEN            = AB_ID + 1
AB_BREAKABLE       = AB_WHEN + 1
AB_CANT_SUPRESS    = AB_BREAKABLE + 1
AB_FAIL_ROLEPLAY   = AB_CANT_SUPRESS + 1
AB_FAIL_SKILL_SWAP = AB_FAIL_ROLEPLAY + 1
AB_NO_ENTRAIN      = AB_FAIL_SKILL_SWAP + 1
AB_NO_RECEIVER     = AB_NO_ENTRAIN + 1
AB_NO_TRACER       = AB_NO_RECEIVER + 1
AB_NO_TRANSFORM    = AB_NO_TRACER + 1
AB_SUPRESS_WEATHER = AB_NO_TRANSFORM + 1

# Move Slots (Derived from Stride)
MOVE1_ID = OFFSET_MOVE
MOVE2_ID = MOVE1_ID + MOVE_STRIDE
MOVE3_ID = MOVE2_ID + MOVE_STRIDE
MOVE4_ID = MOVE3_ID + MOVE_STRIDE
ITEM_ID  = MOVE4_ID + MOVE_STRIDE

# Total length of a single Pokemon's data
POK_LEN = ITEM_ID + ITEM_LEN  # 409 (Adjusted based on your specific layout)

# ==========================================
# 4. MOVE INDICES (Internal to a Move block)
# ==========================================
M_ID               = 0
M_CATEGORY         = M_ID + 1
M_TYPE             = M_CATEGORY + 1
M_TARGET           = M_TYPE + 1
M_POWER            = M_TARGET + 1
M_ACCURACY         = M_POWER + 1
M_CRIT_RATIO       = M_ACCURACY + 1
M_WILL_CRIT        = M_CRIT_RATIO + 1
M_OH_KO            = M_WILL_CRIT + 1
M_SHEER_FORCE      = M_OH_KO + 1
M_PRIORITY         = M_SHEER_FORCE + 1
M_OVERRIDE_OFF_POK = M_PRIORITY + 1
M_OVERRIDE_OFF_STAT= M_OVERRIDE_OFF_POK + 1
M_OVERRIDE_DEF_STAT= M_OVERRIDE_OFF_STAT + 1
M_IGNORE_DEF       = M_OVERRIDE_DEF_STAT + 1
M_IGNORE_IMMUNITY  = M_IGNORE_DEF + 1
M_PP               = M_IGNORE_IMMUNITY + 1
M_PP_UP            = M_PP + 1
M_MULTI_HIT_MIN    = M_PP_UP + 1
M_MULTI_HIT_MAX    = M_MULTI_HIT_MIN + 1
M_SELF_SWITCH      = M_MULTI_HIT_MAX + 1
M_FORCE_SWITCH     = M_SELF_SWITCH + 1
M_NON_GHOST        = M_FORCE_SWITCH + 1
M_IGNORE_AB        = M_NON_GHOST + 1
M_DAMAGE           = M_IGNORE_AB + 1
M_SPREAD_HIT       = M_DAMAGE + 1
M_SPREAD_MOD       = M_SPREAD_HIT + 1
M_CRIT_MOD         = M_SPREAD_MOD + 1
M_FORCE_STAB       = M_CRIT_MOD + 1
M_STATUS           = M_FORCE_STAB + 1
M_VOL_STATUS       = M_STATUS + 1
M_HAS_CRASH_DAMAGE = M_VOL_STATUS + 1
M_SELFDESTRUCT     = M_HAS_CRASH_DAMAGE + 1
M_SLEEP_USABLE     = M_SELFDESTRUCT + 1
M_SMART_TARGET     = M_SLEEP_USABLE + 1
M_BOOST_ATK        = M_SMART_TARGET + 1
M_BOOST_DEF        = M_BOOST_ATK + 1
M_BOOST_SPATK      = M_BOOST_DEF + 1
M_BOOST_SPDEF      = M_BOOST_SPATK + 1
M_BOOST_SPEED      = M_BOOST_SPDEF + 1
M_BOOST_ACC        = M_BOOST_SPEED + 1
M_BOOST_EV         = M_BOOST_ACC + 1
M_SIDE_CONDITION   = M_BOOST_EV + 1
M_RECOIL           = M_SIDE_CONDITION + 1
M_DRAIN            = M_RECOIL + 1

# Flags start after the base move data
OFFSET_FLAGS = BASE_MOVE_LEN
MF_BYPASS_SUB       = OFFSET_FLAGS
MF_BITE             = MF_BYPASS_SUB + 1
MF_BULLET           = MF_BITE + 1
MF_CANT_USE_TWICE   = MF_BULLET + 1
MF_CHARGE           = MF_CANT_USE_TWICE + 1
MF_CONTACT          = MF_CHARGE + 1
MF_DANCE            = MF_CONTACT + 1
MF_DEFROST          = MF_DANCE + 1
MF_DISTANCE         = MF_DEFROST + 1
MF_FAIL_COPYCAT     = MF_DISTANCE + 1
MF_FAIL_ENCORE      = MF_FAIL_COPYCAT + 1
MF_FAIL_INSTRUCT    = MF_FAIL_ENCORE + 1
MF_FAIL_ME_FIRST    = MF_FAIL_INSTRUCT + 1
MF_FAIL_MIMIC       = MF_FAIL_ME_FIRST + 1
MF_FUTURE_MOVE      = MF_FAIL_MIMIC + 1
MF_GRAVITY          = MF_FUTURE_MOVE + 1
MF_HEAL             = MF_GRAVITY + 1
MF_METRONOME        = MF_HEAL + 1
MF_MIRROR           = MF_METRONOME + 1
MF_MUST_PRESSURE    = MF_MIRROR + 1
MF_NO_ASSIST        = MF_MUST_PRESSURE + 1
MF_NO_PARENTAL_BOND = MF_NO_ASSIST + 1
MF_NO_SKETCH        = MF_NO_PARENTAL_BOND + 1
MF_NO_SLEEP_TALK    = MF_NO_SKETCH + 1
MF_PLEDGE_COMBO     = MF_NO_SLEEP_TALK + 1
MF_POWDER           = MF_PLEDGE_COMBO + 1
MF_PROTECT          = MF_POWDER + 1
MF_PULSE            = MF_PROTECT + 1
MF_PUNCH            = MF_PULSE + 1
MF_RECHARGE         = MF_PUNCH + 1
MF_REFLECTABLE      = MF_RECHARGE + 1
MF_SLICING          = MF_REFLECTABLE + 1
MF_SNATCHING        = MF_SLICING + 1
MF_SOUND            = MF_SNATCHING + 1
MF_WIND             = MF_SOUND + 1

# Secondary Effects start after Flags
OFFSET_SEC = BASE_LEN + FLAGS_LEN
MS_CHANCE      = OFFSET_SEC
MS_TARGET      = MS_CHANCE + 1
MS_BOOST_ATK   = MS_TARGET + 1
MS_BOOST_DEF   = MS_BOOST_ATK + 1
MS_BOOST_SPATK = MS_BOOST_DEF + 1
MS_BOOST_SPDEF = MS_BOOST_SPATK + 1
MS_BOOST_SPEED = MS_BOOST_SPDEF + 1
MS_BOOST_ACC   = MS_BOOST_SPEED + 1
MS_BOOST_EV    = MS_BOOST_ACC + 1
MS_VOL_STATUS  = MS_BOOST_EV + 1
MS_STATUS      = MS_VOL_STATUS + 1
MS_CHANCE2     = MS_STATUS + 1
MS_VOL_STATUS2 = MS_CHANCE2 + 1


# ==========================================
# 5. ITEM INDICES (Internal to Item block)
# ==========================================
I_ID                 = 0
I_WHEN               = I_ID + 1
I_ITEM_TYPE          = I_WHEN + 1
I_FLING_POWER        = I_ITEM_TYPE + 1
I_FLING_STATUS       = I_FLING_POWER + 1
I_FLING_VOLATILE     = I_FLING_STATUS + 1
I_NATURAL_GIFT_POWER = I_FLING_VOLATILE + 1
I_NATURAL_GIFT_TYPE  = I_NATURAL_GIFT_POWER + 1
I_ITEM_USER          = I_NATURAL_GIFT_TYPE + 1



# ==========================================
# 6. BATTLEFIELD INDICES
# ==========================================
ALL_POK_LEN        = POK_LEN * 12
MY_POK             = ALL_POK_LEN
OPP_POK            = MY_POK + 1
TURN               = OPP_POK + 1
WEATHER            = TURN + 1
WEATHER_DURATION   = WEATHER + 1
TRICKROOM          = WEATHER_DURATION + 1
TRICKROOM_DURATION = TRICKROOM + 1
MY_SCREEN          = TRICKROOM_DURATION + 1
MY_SCREEN_DURATION = MY_SCREEN + 1
OPP_SCREEN         = MY_SCREEN_DURATION + 1
OPP_SCREEN_DURATION= OPP_SCREEN + 1
PHASE              = OPP_SCREEN_DURATION + 1
OPP_MOVE           = PHASE + 1'''
