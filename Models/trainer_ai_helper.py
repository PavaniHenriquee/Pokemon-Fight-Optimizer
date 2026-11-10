"""
Helper to make the trainer ai more readable and everything more organized
"""
import random
import numpy as np
from Utils.jit import njit
from Utils.loader import TYPE_CHART
from Utils.helper import get_type_effectiveness
from DataBase.PkDB import POKEMON_ABILITY_POOL, POKEMON_LENGTH
from DataBase.MoveDB import PHYSICAL, SPECIAL, FIRE_MOVES, WATER_MOVES, ELECTRIC_MOVES, MoveName
from DataBase.AbilitiesDB import AbilityNames
from DataBase.loader import abDB
from Engine.speed import check_speed, quick_claw, custap_ready
from Models.item import raw_hold_effect, embargoed
from Models.idx_const import POK_LEN
from Models.helper import TARGET_SELF_SIDE, TARGET_OPP_SIDE, STEEL_POISON
from Models.constants import (
    _ABILITYNAMES_STALL, _ABILITYNAMES_VOLT_ABSORB, _ABILITYNAMES_MOTOR_DRIVE, _ABILITYNAMES_IMMUNITY,
    _ABILITYNAMES_MAGIC_GUARD, _ABILITYNAMES_POISON_POINT, _ABILITYNAMES_POISON_HEAL, _ABILITYNAMES_LIMBER,
    _ABILITYNAMES_WATER_VEIL, _ABILITYNAMES_CLEAR_BODY, _ABILITYNAMES_WHITE_SMOKE,
    _ABILITYNAMES_WATER_ABSORB, _ABILITYNAMES_FLASH_FIRE, _ABILITYNAMES_LEVITATE,
    _ABILITYNAMES_SOUNDPROOF, _ABILITYNAMES_WONDER_GUARD, _MOVENAME_COVET, _MOVENAME_CURSE,
    _MOVENAME_EXPLOSION, _MOVENAME_SELFDESTRUCT, _MOVENAME_SUCKER_PUNCH, _MOVENAME_FOCUS_PUNCH,
    _MOVENAME_FUTURE_SIGHT, _MOVENAME_DREAM_EATER, _MOVENAME_NIGHTMARE, _MOVENAME_SWAGGER,
    _MOVENAME_FLATTER, _ABILITYNAMES_VITAL_SPIRIT, _ABILITYNAMES_LEAF_GUARD, _MOVENAME_GYRO_BALL,
    _ABILITYNAMES_HYDRATION, _ABILITYNAMES_OWN_TEMPO, _ABILITYNAMES_OBLIVIOUS, _MOVENAME_FLAIL,
    _ABILITYNAMES_SUCTION_CUPS, _ABILITYNAMES_STURDY, _ABILITYNAMES_HYPER_CUTTER,
    _ABILITYNAMES_SPEED_BOOST, _ABILITYNAMES_NO_GUARD, _ABILITYNAMES_KEEN_EYE,
    _ABILITYNAMES_SIMPLE, _MOVE_TYPE, _MOVE_CATEGORY,_POK_TYPE1, _POK_TYPE2, _POK_AB_ID,
    _ABILITYNAMES_ADAPTABILITY, _MOVECATEGORY_STATUS, _TYPES_ELECTRIC, _TYPES_WATER,
    _TYPES_FIRE, _TYPES_GROUND, _MOVE_STATUS, _POK_STATUS, _STATUS_SLEEP,
    _STATUS_POISON, _STATUS_TOXIC, _WEATHER_SUN, _WEATHER_RAIN, _STATUS_PARALYSIS,
    _ABILITYNAMES_MOLD_BREAKER, _STATUS_BURN, _MOVE_VOL_STATUS, _POK_VOL_STATUS,
    _VOLSTATUS_CONFUSION, _VOLSTATUS_ATTRACT, _POK_GENDER, _GENDER_GENDERLESS, _MOVENAME_TRICK_ROOM,
    _MOVE_BOOST_ATK, _MOVE_BOOST_DEF, _MOVE_BOOST_SPATK,_MOVE_BOOST_SPDEF, _MOVE_BOOST_SPEED,
    _MOVE_BOOST_ACC, _MOVE_BOOST_EV, _MOVE_TARGET, _POK_ATTACK_STAT_STAGE, _POK_DEFENSE_STAT_STAGE,
    _POK_SPECIAL_ATTACK_STAT_STAGE, _POK_SPECIAL_DEFENSE_STAT_STAGE, _POK_SPEED_STAT_STAGE,
    _POK_ACCURACY_STAT_STAGE, _POK_EVASION_STAT_STAGE, _MOVE_ID, _POK_CURRENT_HP,
    _MOVE_PRIORITY, _MOVENAME_FAKE_OUT, _POK_MOVE1_ID, _POK_MOVE2_ID, _POK_MOVE3_ID,
    _POK_MOVE4_ID, _MOVENAME_PSYCH_UP, _MOVENAME_DRAGON_DANCE, _VOLSTATUS_LEECH_SEED,
    _VOLSTATUS_CURSE, _POK_MAX_HP, _MOVE_ACCURACY, _POK_ITEM_ID, _MOVE_DRAIN, _MOVENAME_BIDE,
    _ABILITYNAMES_DAMP,
    _MOVENAME_BUG_BITE, _POK_TURNS, _MOVENAME_COUNTER, _TYPES_NORMAL, _TYPES_FIGHTING,
    _TYPES_POISON, _TYPES_ROCK, _TYPES_BUG, _TYPES_GHOST, _TYPES_STEEL, _TYPES_FLYING,
    _ITEMNAMES_CHESTO_BERRY, _ITEMNAMES_LUM_BERRY, _ITEMNAMES_BERRY_JUICE, _ITEMNAMES_ORAN_BERRY,
    _ITEMNAMES_BRIGHT_POWDER, _ITEMNAMES_LAX_INCENSE, _ITEMNAMES_LEFTOVERS, _ITEMNAMES_LIGHT_BALL,
    _ITEMNAMES_THICK_CLUB, _ITEMNAMES_OCCA_BERRY, _ITEMNAMES_PASSHO_BERRY, _ITEMNAMES_WACAN_BERRY,
    _ITEMNAMES_RINDO_BERRY, _ITEMNAMES_YACHE_BERRY, _ITEMNAMES_CHOPLE_BERRY, _ITEMNAMES_KEBIA_BERRY,
    _ITEMNAMES_SHUCA_BERRY, _ITEMNAMES_COBA_BERRY, _ITEMNAMES_PAYAPA_BERRY, _ITEMNAMES_TANGA_BERRY,
    _ITEMNAMES_CHARTI_BERRY, _ITEMNAMES_KASIB_BERRY, _ITEMNAMES_HABAN_BERRY, _ITEMNAMES_COLBUR_BERRY,
    _ITEMNAMES_BABIRI_BERRY, _ITEMNAMES_CHILAN_BERRY, _ITEMNAMES_BLACK_SLUDGE, _POK_TURNS_ACTIVE,
    _MOVE_CRIT_RATIO, _MOVE_CHARGE_RECHARGE, _MOVENAME_ICY_WIND, _MOVENAME_ROCK_TOMB,
    _MOVENAME_CLOSE_COMBAT, _MOVENAME_OVERHEAT, _MOVENAME_DRACO_METEOR, _MOVENAME_LEAF_STORM,
    _MOVENAME_PSYCHO_BOOST, _MOVENAME_SUPERPOWER, _MOVENAME_HAMMER_ARM,
    _MOVENAME_MUD_SHOT, _MOVENAME_TICKLE, _MOVENAME_BULK_UP, _VOLSTATUS_FOCUS_ENERGY,
    _MOVENAME_MIRROR_COAT, _MOVENAME_ASSURANCE, _ABILITYNAMES_ROUGH_SKIN, _ABILITYNAMES_ROCK_HEAD,
    _MOVENAME_NATURAL_GIFT, _ITEM_NATURAL_GIFT_POWER, _ITEM_NATURAL_GIFT_TYPE, _MOVENAME_LOW_KICK,
    _MOVE_POWER, _MOVENAME_BOUNCE, _MOVENAME_DIG, _MOVENAME_GRAVITY, _ITEMNAMES_POWER_HERB,
    _WEATHER_SANDSTORM, _WEATHER_HAIL,
    _TYPES_ICE, _MOVE_RECOIL, _TYPES_GRASS,
    _TYPES_PSYCHIC, _TYPES_DRAGON, _TYPES_DARK,
    _VOLSTATUS_FORESIGHT, _VOLSTATUS_INGRAIN, _VOLSTATUS_AQUA_RING, _VOLSTATUS_MUD_SPORT,
    _VOLSTATUS_WATER_SPORT, _VOLSTATUS_YAWN, _VOLSTATUS_HELPING_HAND, _VOLSTATUS_PROTECT,
    _VOLSTATUS_ENDURE, _VOLSTATUS_DESTINY_BOND, _ABILITYNAMES_INSOMNIA, _MOVENAME_PROTECT,
    _MOVENAME_FEINT, _MOVENAME_RECOVER, _MOVENAME_DEFENSE_CURL, _POK_PROTECT_COUNT,
    _ENEMY_AI_KNOWS_MOVE1, _ENEMY_AI_KNOWS_MOVE2, _ENEMY_AI_KNOWS_MOVE3, _ENEMY_AI_KNOWS_MOVE4,
    _MOVECATEGORY_PHYSICAL, _MOVECATEGORY_SPECIAL, _MOVENAME_CHARGE, _VOLSTATUS_TAUNT,
    _VOLSTATUS_ENCORE, _VOLSTATUS_DISABLE, _VOLSTATUS_PARTIALLY_TRAPPED, _POK_LAST_MOVE_ID,
    _MOVENAME_WHIRLPOOL, _MOVE_SIDE_CONDITION, _SIDECONDITION_REFLECT, _SIDECONDITION_LIGHT_SCREEN,
    _SIDECONDITION_MIST, _SIDECONDITION_SAFEGUARD, _SIDECONDITION_LUCKY_CHANT,
    _SIDECONDITION_TOXIC_SPIKES, _SIDECONDITION_STEALTH_ROCK, _MOVENAME_RAIN_DANCE,
    _MOVENAME_SANDSTORM, _MOVENAME_BRICK_BREAK, _MOVENAME_REFLECT, _MOVENAME_LIGHT_SCREEN,
    _MOVENAME_LUCKY_CHANT, _MOVENAME_TOXIC_SPIKES, _MOVENAME_STEALTH_ROCK, _MOVENAME_ROAR,
    _MOVENAME_WHIRLWIND, _ABILITYNAMES_SWIFT_SWIM, _ABILITYNAMES_RAIN_DISH, _MOVE_FORCE_SWITCH,
    _MOVENAME_BATON_PASS, _MOVENAME_TELEPORT, _MOVENAME_PURSUIT, _SIDECONDITION_SPIKES,
    _MOVENAME_SYNTHESIS, _MOVENAME_REFRESH, _MOVENAME_KNOCK_OFF, _MOVENAME_RECYCLE,
    _MOVENAME_WORRY_SEED, _MOVENAME_PERISH_SONG, _MOVENAME_SPLASH, _MOVENAME_SLEEP_TALK,
    _VOLSTATUS_PERISH_SONG, _POK_CONSUMED_ITEM, _ABILITYNAMES_TRUANT, _ABILITYNAMES_MULTITYPE,
    _ABILITYNAMES_STICKY_HOLD, _MOVENAME_METRONOME, _MOVENAME_MIRROR_MOVE, _MOVENAME_COPYCAT,
    _MOVENAME_NATURE_POWER, _TYPES_TYPELESS, _MOVENAME_BLIZZARD, _MOVE_OH_KO, _POK_LEVEL,
    _MOVENAME_FIRE_FANG, _MOVENAME_SUBSTITUTE, _POK_VOL_STATUS2, _VOLSTATUS2_SUBSTITUTE,
    _MOVENAME_SUPERSONIC, _MOVENAME_CONFUSE_RAY, _MOVENAME_SWEET_KISS, _MOVENAME_LEECH_SEED,
    _ITEM_HOLD_EFFECT, _HOLDEFFECT_PRIORITY_DOWN,
    _MOVENAME_THIEF, _MOVENAME_PLUCK, _MOVENAME_TRICK, _MOVENAME_SWITCHEROO, _MOVENAME_EMBARGO,
    _MOVENAME_FLING, _ITEM_FLING_POWER, _ABILITYNAMES_GUTS, _ITEMNAMES_FLAME_ORB,
    _ITEMNAMES_KINGS_ROCK, _ITEMNAMES_POISON_BARB, _ITEMNAMES_RAZOR_FANG, _ITEMNAMES_TOXIC_ORB,
    _HOLDEFFECT_HP_RESTORE_PSN_TYPE, _HOLDEFFECT_EVS_UP_SPEED_DOWN, _HOLDEFFECT_LVLUP_EV_UP,
    _HOLDEFFECT_DMG_USER_CONTACT_XFR, _HOLDEFFECT_CHOICE_ATK, _HOLDEFFECT_CHOICE_SPATK,
    _HOLDEFFECT_CHOICE_SPEED, _HOLDEFFECT_SPEED_DOWN_GROUNDED, _HOLDEFFECT_PSN_USER,
    _HOLDEFFECT_BRN_USER, _HOLDEFFECT_HP_RESTORE_SPICY, _HOLDEFFECT_HP_RESTORE_DRY,
    _HOLDEFFECT_HP_RESTORE_SWEET, _HOLDEFFECT_HP_RESTORE_BITTER, _HOLDEFFECT_HP_RESTORE_SOUR,
)
from Engine.damage_calc import (
    weight_power, matchup_types, gyro_ball_power, gravity_types, EXPLODE_MOVES, is_scrappy,
    FORESIGHT_TYPES
)
from Engine.ability_helper import ignorable_ability, levitates, normalized_type, grounded_by_item

COUNTER_EX_TYPES = (
    _TYPES_NORMAL, _TYPES_FIGHTING, _TYPES_FLYING, _TYPES_POISON, _TYPES_GROUND,
    _TYPES_ROCK, _TYPES_BUG, _TYPES_GHOST, _TYPES_STEEL
)
MIRROR_COAT_EX_TYPES = (
    _TYPES_FIRE, _TYPES_WATER, _TYPES_GRASS, _TYPES_ELECTRIC, _TYPES_PSYCHIC,
    _TYPES_ICE, _TYPES_DRAGON, _TYPES_DARK
)
SAND_IMMUNE_TYPES = (_TYPES_GROUND, _TYPES_ROCK, _TYPES_STEEL)
ELEC_AB_IM = (_ABILITYNAMES_VOLT_ABSORB, _ABILITYNAMES_MOTOR_DRIVE)
POISON_AB_IM = (_ABILITYNAMES_IMMUNITY, _ABILITYNAMES_MAGIC_GUARD, _ABILITYNAMES_POISON_HEAL)
PARA_AB_IM = (_ABILITYNAMES_LIMBER, _ABILITYNAMES_MAGIC_GUARD)
BURN_AB_IM = (_ABILITYNAMES_WATER_VEIL, _ABILITYNAMES_MAGIC_GUARD)
STAT_AB_IM = (_ABILITYNAMES_CLEAR_BODY, _ABILITYNAMES_WHITE_SMOKE)
ABILITY_BASIC_FLAG = (
    _ABILITYNAMES_VOLT_ABSORB, _ABILITYNAMES_MOTOR_DRIVE, _ABILITYNAMES_WATER_ABSORB,
    _ABILITYNAMES_FLASH_FIRE, _ABILITYNAMES_LEVITATE, _ABILITYNAMES_SOUNDPROOF,
    _ABILITYNAMES_WONDER_GUARD
)
ABSORB_ABI = (
    _ABILITYNAMES_WATER_ABSORB, _ABILITYNAMES_VOLT_ABSORB, _ABILITYNAMES_FLASH_FIRE
)

FUTURE_ATTACK_MOVES = (_MOVENAME_FUTURE_SIGHT,)
MAYBE_BAD_MOVES = (
    _MOVENAME_SUCKER_PUNCH,
    _MOVENAME_FOCUS_PUNCH,
    _MOVENAME_EXPLOSION,
    _MOVENAME_SELFDESTRUCT
)
SLEEP_MOVES = (_MOVENAME_DREAM_EATER, _MOVENAME_NIGHTMARE)
CONFUSE_SPECIAL_CASES = (_MOVENAME_SWAGGER, _MOVENAME_FLATTER)
CURSE_SPECIAL_CASES = (_MOVENAME_GYRO_BALL, _MOVENAME_TRICK_ROOM)

# --- Abilities explicitly checked in basic_flag / expert_flag ---
_EXPLICIT_RELEVANT: set = {
    _ABILITYNAMES_VOLT_ABSORB,
    _ABILITYNAMES_MOTOR_DRIVE,
    _ABILITYNAMES_WATER_ABSORB,
    _ABILITYNAMES_FLASH_FIRE,
    _ABILITYNAMES_LEVITATE,
    _ABILITYNAMES_SOUNDPROOF,
    _ABILITYNAMES_WONDER_GUARD,
    _ABILITYNAMES_VITAL_SPIRIT,
    _ABILITYNAMES_IMMUNITY,
    _ABILITYNAMES_MAGIC_GUARD,
    _ABILITYNAMES_POISON_POINT,
    _ABILITYNAMES_LEAF_GUARD,
    _ABILITYNAMES_HYDRATION,
    _ABILITYNAMES_LIMBER,
    _ABILITYNAMES_WATER_VEIL,
    _ABILITYNAMES_CLEAR_BODY,
    _ABILITYNAMES_WHITE_SMOKE,
    _ABILITYNAMES_OWN_TEMPO,
    _ABILITYNAMES_OBLIVIOUS,
    _ABILITYNAMES_SUCTION_CUPS,
    _ABILITYNAMES_STURDY,
    _ABILITYNAMES_HYPER_CUTTER,
    _ABILITYNAMES_SPEED_BOOST,
    _ABILITYNAMES_NO_GUARD,
    _ABILITYNAMES_KEEN_EYE,
    _ABILITYNAMES_SIMPLE,
    _ABILITYNAMES_INSOMNIA,
    _ABILITYNAMES_POISON_HEAL,
    _ABILITYNAMES_STICKY_HOLD,
    _ABILITYNAMES_TRUANT,
    _ABILITYNAMES_MULTITYPE,
}

_DAMAGE_RELEVANT_WHEN = {"on_try_move"}

_activation_relevant: set = set()
for ab_name, ab_data in abDB.items():
    when = ab_data.get("when")
    if not when:
        continue
    whens = when if isinstance(when, list) else [when]
    if any(w in _DAMAGE_RELEVANT_WHEN for w in whens):
        try:
            _activation_relevant.add(
                getattr(AbilityNames, ab_name.upper().replace(" ", "_"))
            )
        except AttributeError:
            pass

# Final constant - this is what Numba sees, and it's a tuple
RELEVANT_ABILITIES: tuple = tuple(_EXPLICIT_RELEVANT | _activation_relevant)


# --- Pre-compute per pokemon whether ANY of its pool abilities are relevant ---
POKEMON_HAS_RELEVANT_ABILITY = np.zeros(POKEMON_LENGTH + 1, dtype=np.bool_)
for pk_id in range(POKEMON_LENGTH + 1):
    for ab_id in POKEMON_ABILITY_POOL[pk_id]:
        if ab_id in RELEVANT_ABILITIES:  # still a set here, build-time only
            POKEMON_HAS_RELEVANT_ABILITY[pk_id] = True
            break

# --------Items that AI considers as good effects to steal------------
ITEMS_STEAL = (_ITEMNAMES_CHESTO_BERRY, _ITEMNAMES_LUM_BERRY, _ITEMNAMES_BERRY_JUICE, _ITEMNAMES_ORAN_BERRY,
    _ITEMNAMES_BRIGHT_POWDER, _ITEMNAMES_LAX_INCENSE, _ITEMNAMES_LEFTOVERS, _ITEMNAMES_LIGHT_BALL,
    _ITEMNAMES_THICK_CLUB, _ITEMNAMES_OCCA_BERRY, _ITEMNAMES_PASSHO_BERRY, _ITEMNAMES_WACAN_BERRY,
    _ITEMNAMES_RINDO_BERRY, _ITEMNAMES_YACHE_BERRY, _ITEMNAMES_CHOPLE_BERRY, _ITEMNAMES_KEBIA_BERRY,
    _ITEMNAMES_SHUCA_BERRY, _ITEMNAMES_COBA_BERRY, _ITEMNAMES_PAYAPA_BERRY, _ITEMNAMES_TANGA_BERRY,
    _ITEMNAMES_CHARTI_BERRY, _ITEMNAMES_KASIB_BERRY, _ITEMNAMES_HABAN_BERRY, _ITEMNAMES_COLBUR_BERRY,
    _ITEMNAMES_BABIRI_BERRY, _ITEMNAMES_CHILAN_BERRY, _ITEMNAMES_BLACK_SLUDGE)

#--------------Move tuples-----------------------------
EXPERT_SPECIFIC_M = (_MOVENAME_BIDE, _MOVENAME_BUG_BITE, _MOVENAME_COUNTER, _MOVENAME_COVET, _MOVENAME_CURSE,
    _MOVENAME_FAKE_OUT, _MOVENAME_FLAIL, _MOVENAME_MIRROR_COAT, _MOVENAME_ASSURANCE,
    _MOVENAME_THIEF, _MOVENAME_PLUCK)
# Basic_CheckCanRemoveItem: Knock Off, Trick and Switcheroo
REMOVE_ITEM_M = (_MOVENAME_KNOCK_OFF, _MOVENAME_TRICK, _MOVENAME_SWITCHEROO)
# Scored by expert_items
ITEM_EXPERT_M = (_MOVENAME_TRICK, _MOVENAME_SWITCHEROO, _MOVENAME_EMBARGO, _MOVENAME_FLING)
# Pokemow List_BadTrade, by hold effect (pokeplatinum Expert_Trick_BadOpponentItems): Macho Brace,
# the choice items, Iron Ball, Lagging Tail / Full Incense, Sticky Barb, the Power items, the Orbs
# and Black Sludge
TRICK_BAD_TRADE = (
    _HOLDEFFECT_EVS_UP_SPEED_DOWN, _HOLDEFFECT_CHOICE_ATK, _HOLDEFFECT_CHOICE_SPATK,
    _HOLDEFFECT_CHOICE_SPEED, _HOLDEFFECT_SPEED_DOWN_GROUNDED, _HOLDEFFECT_PRIORITY_DOWN,
    _HOLDEFFECT_DMG_USER_CONTACT_XFR, _HOLDEFFECT_LVLUP_EV_UP, _HOLDEFFECT_PSN_USER,
    _HOLDEFFECT_BRN_USER, _HOLDEFFECT_HP_RESTORE_PSN_TYPE,
)
# What the AI gives away for +5 (pokeplatinum Expert_Trick_DisruptiveItems, no Macho Brace)
TRICK_DISRUPTIVE = (
    _HOLDEFFECT_CHOICE_ATK, _HOLDEFFECT_CHOICE_SPATK, _HOLDEFFECT_CHOICE_SPEED,
    _HOLDEFFECT_SPEED_DOWN_GROUNDED, _HOLDEFFECT_PRIORITY_DOWN, _HOLDEFFECT_DMG_USER_CONTACT_XFR,
    _HOLDEFFECT_LVLUP_EV_UP,
)
# Figy, Wiki, Mago, Aguav, Iapapa
FLAVOR_BERRY_EFFECTS = (
    _HOLDEFFECT_HP_RESTORE_SPICY, _HOLDEFFECT_HP_RESTORE_DRY, _HOLDEFFECT_HP_RESTORE_SWEET,
    _HOLDEFFECT_HP_RESTORE_BITTER, _HOLDEFFECT_HP_RESTORE_SOUR,
)
# Expert Fling doesn't mind a resisted hit with these (pokeplatinum Expert_Fling_DesirableFlingEffects)
FLING_GOOD_ITEMS = (
    _ITEMNAMES_KINGS_ROCK, _ITEMNAMES_RAZOR_FANG, _ITEMNAMES_POISON_BARB, _ITEMNAMES_TOXIC_ORB,
    _ITEMNAMES_FLAME_ORB, _ITEMNAMES_LIGHT_BALL,
)
FLING_POISON_ITEMS = (_ITEMNAMES_POISON_BARB, _ITEMNAMES_TOXIC_ORB)
CHARGE_INVULNERABLE_M = (_MOVENAME_BOUNCE, _MOVENAME_DIG)
RECOIL_AB = (_ABILITYNAMES_ROCK_HEAD, _ABILITYNAMES_MAGIC_GUARD)
BASIC_SPECIFIC_M  = (_MOVENAME_CURSE, _MOVENAME_FAKE_OUT, _MOVENAME_BULK_UP, _MOVENAME_TICKLE)
# Moves Pokemow gives no Basic and no Expert check at all
NO_AI_CHECK_M = (_MOVENAME_CHARGE,)
SPEED_DOWN_ON_HIT = (_MOVENAME_ICY_WIND, _MOVENAME_ROCK_TOMB, _MOVENAME_MUD_SHOT)
# Expert_CloseCombat and Expert_Overheat (USER_SP_ATK_DOWN_2) are the same check
SELF_DROP_HP_M = (
    _MOVENAME_CLOSE_COMBAT, _MOVENAME_OVERHEAT, _MOVENAME_DRACO_METEOR, _MOVENAME_LEAF_STORM,
    _MOVENAME_PSYCHO_BOOST
)
# pokeplatinum BATTLE_EFFECT_STATUS_CONFUSE, which Expert_Substitute reads off the target's last move
CONFUSE_EFFECT_M = (_MOVENAME_SUPERSONIC, _MOVENAME_CONFUSE_RAY, _MOVENAME_SWEET_KISS)
# Moves the Expert AI looks for among the ones it saw the target use. Detect and Shadow Force
# aren't in MoveDB, Recover is the only RESTORE_HALF_HP move there
PROTECT_LIKE_M = (_MOVENAME_PROTECT,)
FEINT_LIKE_M = (_MOVENAME_FEINT,)
RECOVER_DEF_CURL_M = (_MOVENAME_RECOVER, _MOVENAME_DEFENSE_CURL)
MOVE_ID_SLOTS = (_POK_MOVE1_ID, _POK_MOVE2_ID, _POK_MOVE3_ID, _POK_MOVE4_ID)
# Side condition and weather moves, scored by basic_field / expert_field
WEATHER_M = (_MOVENAME_RAIN_DANCE, _MOVENAME_SANDSTORM)
FIELD_EXPERT_M = WEATHER_M + (_MOVENAME_BRICK_BREAK,)
SCREEN_MIST_SAFEGUARD = (
    _SIDECONDITION_REFLECT, _SIDECONDITION_LIGHT_SCREEN, _SIDECONDITION_MIST,
    _SIDECONDITION_SAFEGUARD
)
SCREENS = _SIDECONDITION_REFLECT | _SIDECONDITION_LIGHT_SCREEN
HAZARD_M = (_MOVENAME_TOXIC_SPIKES, _MOVENAME_STEALTH_ROCK)
FORCE_SWITCH_M = (_MOVENAME_ROAR, _MOVENAME_WHIRLWIND)
SWITCH_EXPERT_M = (_MOVENAME_BATON_PASS, _MOVENAME_PURSUIT, _MOVENAME_TELEPORT)
TARGET_HAZARDS = _SIDECONDITION_SPIKES | _SIDECONDITION_STEALTH_ROCK | _SIDECONDITION_TOXIC_SPIKES
# Stages Expert Roar / Whirlwind and Baton Pass look at, accuracy and speed aren't among them
SWITCH_STAGES = (
    _POK_ATTACK_STAT_STAGE, _POK_DEFENSE_STAT_STAGE, _POK_SPECIAL_ATTACK_STAT_STAGE,
    _POK_SPECIAL_DEFENSE_STAT_STAGE, _POK_EVASION_STAT_STAGE
)
RAIN_DANCE_GOOD_WEATHER = (_WEATHER_HAIL, _WEATHER_SUN, _WEATHER_SANDSTORM)
TOXIC_SPIKES_MAX = 2
AI_KNOWS_MOVE_BITS = (
    _ENEMY_AI_KNOWS_MOVE1, _ENEMY_AI_KNOWS_MOVE2, _ENEMY_AI_KNOWS_MOVE3, _ENEMY_AI_KNOWS_MOVE4
)
GRADUAL_RECOVERY_ITEMS = (_ITEMNAMES_LEFTOVERS, _ITEMNAMES_BLACK_SLUDGE)
SELF_ONCE_VOLS = (_VOLSTATUS_INGRAIN, _VOLSTATUS_AQUA_RING, _VOLSTATUS_MUD_SPORT, _VOLSTATUS_WATER_SPORT)
DAMAGING_CATEGORIES = (_MOVECATEGORY_PHYSICAL, _MOVECATEGORY_SPECIAL)
# Pokemow List_Encore: last moves of the target that Expert Encore likes, the ones in MoveDB
ENCORE_ENCOURAGED_M = (
    MoveName.DREAM_EATER, MoveName.MEDITATE, MoveName.HOWL, MoveName.HARDEN, MoveName.WITHDRAW,
    MoveName.GROWTH, MoveName.WHIRLWIND, MoveName.ROAR, MoveName.LIGHT_SCREEN, MoveName.AMNESIA,
    MoveName.SUPERSONIC, MoveName.CONFUSE_RAY, MoveName.SWEET_KISS, MoveName.POISON_POWDER,
    MoveName.STUN_SPORE, MoveName.THUNDER_WAVE, MoveName.LEECH_SEED, MoveName.SPLASH,
    MoveName.ENCORE, MoveName.NIGHTMARE, MoveName.PROTECT, MoveName.FORESIGHT,
    MoveName.ODOR_SLEUTH, MoveName.PERISH_SONG, MoveName.SANDSTORM, MoveName.ENDURE,
    MoveName.SWAGGER, MoveName.ATTRACT, MoveName.SAFEGUARD, MoveName.RAIN_DANCE,
    MoveName.PSYCH_UP, MoveName.FUTURE_SIGHT, MoveName.FAKE_OUT, MoveName.WILL_O_WISP,
    MoveName.FOLLOW_ME, MoveName.CHARGE, MoveName.INGRAIN, MoveName.RECYCLE, MoveName.KNOCK_OFF,
    MoveName.REFRESH, MoveName.MUD_SPORT, MoveName.WATER_SPORT, MoveName.DRAGON_DANCE,
    MoveName.NATURAL_GIFT, MoveName.FEINT, MoveName.LUCKY_CHANT, MoveName.WORRY_SEED,
    MoveName.AQUA_RING, MoveName.TRICK_ROOM, MoveName.TRICK, MoveName.SWITCHEROO, MoveName.FLING
)
MOVE_CATEGORY_SLOTS = tuple(slot + _MOVE_CATEGORY - _MOVE_ID for slot in MOVE_ID_SLOTS)
# pokeplatinum Basic_SoundproofMoves, the ones in MoveDB (Snore and Metal Sound
# aren't). Perish Song and Hyper Voice aren't on it
SOUNDPROOF_M = (
    MoveName.GROWL, MoveName.ROAR, MoveName.SING, MoveName.SUPERSONIC, MoveName.SCREECH,
    MoveName.UPROAR, MoveName.GRASS_WHISTLE, MoveName.CHATTER, MoveName.BUG_BUZZ
)
# Recover is the only RESTORE_HALF_HP move in MoveDB, Synthesis the only HEAL_HALF_MORE_IN_SUN one
HEAL_M = (_MOVENAME_RECOVER, _MOVENAME_SYNTHESIS)
# Scored by basic_misc / expert_misc
MISC_BASIC_M = HEAL_M + (
    _MOVENAME_REFRESH, _MOVENAME_RECYCLE, _MOVENAME_WORRY_SEED, _MOVENAME_PERISH_SONG
)
MISC_EXPERT_M = MISC_BASIC_M + (_MOVENAME_KNOCK_OFF, _MOVENAME_SPLASH)
REFRESH_STATUSES = (_STATUS_BURN, _STATUS_POISON, _STATUS_TOXIC, _STATUS_PARALYSIS)
WORRY_SEED_BAD_AB = (
    _ABILITYNAMES_TRUANT, _ABILITYNAMES_INSOMNIA, _ABILITYNAMES_VITAL_SPIRIT, _ABILITYNAMES_MULTITYPE
)
# Snore isn't in MoveDB
SLEEP_USABLE_M = (_MOVENAME_SLEEP_TALK,)
SYNTHESIS_BAD_WEATHER = (_WEATHER_RAIN, _WEATHER_SANDSTORM, _WEATHER_HAIL)
# Expert_Recycle_DesirableItems, Starf Berry isn't in ItemDB
RECYCLE_GOOD_ITEMS = (_ITEMNAMES_CHESTO_BERRY, _ITEMNAMES_LUM_BERRY)
# Moves that call another move, scored by expert_call. Metronome and Nature Power have no check
CALL_M = (_MOVENAME_METRONOME, _MOVENAME_MIRROR_MOVE, _MOVENAME_COPYCAT, _MOVENAME_NATURE_POWER)
# Expert_MirrorMove_MoveTable, the same list as Expert_Copycat_EncouragedMoves. Names not in MoveDB
# are skipped
MIRROR_COPYCAT_GOOD_M = tuple(
    getattr(MoveName, name) for name in (
        'SLEEP_POWDER', 'LOVELY_KISS', 'SPORE', 'HYPNOSIS', 'SING', 'GRASS_WHISTLE', 'SHADOW_PUNCH',
        'SAND_ATTACK', 'SMOKESCREEN', 'TOXIC', 'GUILLOTINE', 'HORN_DRILL', 'FISSURE', 'SHEER_COLD',
        'CROSS_CHOP', 'AEROBLAST', 'CONFUSE_RAY', 'SWEET_KISS', 'SCREECH', 'COTTON_SPORE',
        'SCARY_FACE', 'FAKE_TEARS', 'METAL_SOUND', 'THUNDER_WAVE', 'GLARE', 'POISON_POWDER',
        'SHADOW_BALL', 'DYNAMIC_PUNCH', 'HYPER_BEAM', 'EXTREME_SPEED', 'THIEF', 'COVET', 'ATTRACT',
        'SWAGGER', 'TORMENT', 'FLATTER', 'TRICK', 'SUPERPOWER', 'SKILL_SWAP', 'PSYCHO_SHIFT',
        'POWER_SWAP', 'GUARD_SWAP', 'SUCKER_PUNCH', 'HEART_SWAP', 'SWITCHEROO', 'CAPTIVATE',
        'DARK_VOID',
    ) if hasattr(MoveName, name)
)


@njit
def match_2tuple_any(tup1, tup2):
    """check tuples with 2 elements for if any of them is equal"""
    # Check first element against both
    if tup1[0] == tup2[0] or tup1[0] == tup2[1]:
        return True
    # Check second element against both
    if tup1[1] == tup2[0] or tup1[1] == tup2[1]:
        return True
    return False



@njit
def knows_move(pok, move_id):
    """If any of the Pokemon's 4 moves is move_id"""
    return (
        pok[_POK_MOVE1_ID] == move_id
        or pok[_POK_MOVE2_ID] == move_id
        or pok[_POK_MOVE3_ID] == move_id
        or pok[_POK_MOVE4_ID] == move_id
    )


@njit
def ai_move_view(move, ai_pok, user_pok, weather=0):
    """
    The AI damage calc sees Natural Gift's berry type and power, Low Kick's weight power and
    Gyro Ball's speed power (pokeplatinum TrainerAI_CalcDamage), every other move is returned
    as is
    """
    move_id = move[_MOVE_ID]
    if move_id == _MOVENAME_NATURAL_GIFT:
        view = move.copy()
        power = ai_pok[_ITEM_NATURAL_GIFT_POWER]
        view[_MOVE_POWER] = power
        view[_MOVE_TYPE] = ai_pok[_ITEM_NATURAL_GIFT_TYPE] if power else _TYPES_NORMAL
        return view
    if move_id == _MOVENAME_LOW_KICK:
        view = move.copy()
        view[_MOVE_POWER] = weight_power(user_pok)
        return view
    if move_id == _MOVENAME_GYRO_BALL:
        view = move.copy()
        view[_MOVE_POWER] = gyro_ball_power(ai_pok, user_pok, weather)
        return view
    return move


@njit
def add_adjustment(arr, move_id, delta, chance):
    """Add a [delta, chance] pair to the first free slot (slot is free when chance == 0)."""
    for i in range(5):
        if arr[move_id, i, 1] == 0:   # chance == 0 means slot unused
            arr[move_id, i, 0] = delta
            arr[move_id, i, 1] = chance
            return
    raise ValueError("Insufficient slots in rand")


@njit
def trainer_ai_effectiveness(move, ai_pok, user_pok, gravity=False):
    """
    How the AI consider type effectivness, which has some differences from
    how it usually goes
    """


    """If the user has the ability Normalize, the move's type is changed to Normal.
    Otherwise, if the move is Natural Gift, Hidden Power, Judgment, or Weather Ball,
    the move is adjusted to its correct type."""
    effectiveness = 1.0
    move_type = normalized_type(ai_pok, move)
    move_cat = move[_MOVE_CATEGORY]
    ai_type1 = ai_pok[_POK_TYPE1]
    ai_type2 = ai_pok[_POK_TYPE2]
    ai_ability = ai_pok[_POK_AB_ID]
    # Foresight, Scrappy, Ingrain and Gravity go through the same type chart as the battle
    # (BattleSystem_ApplyTypeChart)
    user_type1, user_type2 = matchup_types(move_type, user_pok, gravity, is_scrappy(ai_pok))

    # STAB
    if move_type == ai_type1 or move_type == ai_type2:  # pylint: disable=consider-using-in
        effectiveness *= 1.5 if ai_ability != _ABILITYNAMES_ADAPTABILITY else 2

    # Common type effectiveness
    # TODO: Gastro Acid, Miracle Eye, Iron Ball
    # Magnet Rise, more...
    s_e = False
    ef_t1 = TYPE_CHART[(move_type*19)+user_type1] / 2
    effectiveness *= ef_t1
    if user_type2:
        ef_t2 = TYPE_CHART[(move_type*19)+user_type2] / 2
        effectiveness *= ef_t2
        if ef_t1*ef_t2 >= 2:
            s_e = True
    elif ef_t1 == 2:
        s_e = True

    # ApplyTypeChart's Levitate (any Ground move) and Wonder Guard (a damaging move that isn't
    # super effective) make it immune. MoveIsOnDamagingTurn is false outside the move's last
    # turn, so charge moves and Fire Fang get past Wonder Guard here
    if move_type == _TYPES_GROUND and levitates(user_pok, ai_pok, gravity):
        return 0.0, False
    if (
        user_pok[_POK_AB_ID] == _ABILITYNAMES_WONDER_GUARD
        and ignorable_ability(user_pok, ai_pok)
        and move_cat != _MOVECATEGORY_STATUS
        and not s_e
        and move[_MOVE_CHARGE_RECHARGE] <= 0
        and move[_MOVE_ID] != _MOVENAME_FIRE_FANG
    ):
        return 0.0, False

    if move_cat != _MOVECATEGORY_STATUS:
        # TODO: Tinted Lens, Filter/Solid Rock, Expert Belt
        pass



    # Correct for the right effectiveness
    if effectiveness == 0.375:
        effectiveness = 0.25
    elif effectiveness == 0.75:
        effectiveness = 0.5
    elif effectiveness == 3.0:
        effectiveness = 2.0
    elif effectiveness == 6.0:
        effectiveness = 4.0

    return effectiveness, s_e


@njit
def basic_ability(move, ability, user_pok, move_category) -> int:
    """
    Score for the target's ability making the move useless (Pokemow Basic checks):
    -12 for the absorbing abilities, Levitate and Wonder Guard, -10 for Soundproof, else 0
    """
    move_type = move[_MOVE_TYPE]
    if move_type == _TYPES_ELECTRIC and ability in ELEC_AB_IM:
        return -12
    if move_type == _TYPES_WATER and ability == _ABILITYNAMES_WATER_ABSORB:
        return -12
    if move_type == _TYPES_FIRE and ability == _ABILITYNAMES_FLASH_FIRE:
        return -12
    if move_type == _TYPES_GROUND and ability == _ABILITYNAMES_LEVITATE:
        return -12
    if move[_MOVE_ID] in SOUNDPROOF_M and ability == _ABILITYNAMES_SOUNDPROOF:
        return -10
    if ability == _ABILITYNAMES_WONDER_GUARD and move_category != _MOVECATEGORY_STATUS:
        eff, den = get_type_effectiveness(move_type, user_pok[_POK_TYPE1], user_pok[_POK_TYPE2])
        if eff // den < 2:
            return -12
    return 0


@njit
def basic_move_status(move, ability, user_pok, ai_pok, weather, user_side=0):
    """
    Checks to see if any of the conditions for move status being irrelevant comes back as true.
    user_side is the target's Field.SIDE_COND
    """
    u_type12 = (user_pok[_POK_TYPE1],user_pok[_POK_TYPE2])
    move_status = move[_MOVE_STATUS]
    user_status = user_pok[_POK_STATUS] != 0

    if user_status:
        return True
    if user_side & _SIDECONDITION_SAFEGUARD:
        return True

    # Sleep
    if (
        move_status == _STATUS_SLEEP
        and (ability == _ABILITYNAMES_VITAL_SPIRIT or ability == _ABILITYNAMES_INSOMNIA)
    ):
        return True

    # Poison
    if (
        move_status in (_STATUS_POISON, _STATUS_TOXIC)
    ):
        if match_2tuple_any(STEEL_POISON, u_type12):
            return True
        if ability in POISON_AB_IM:
            return True
        if weather:
            if (
                weather == _WEATHER_SUN
                and ability == _ABILITYNAMES_LEAF_GUARD
            ):
                return True
            if (
                weather == _WEATHER_RAIN
                and ability == _ABILITYNAMES_HYDRATION
            ):
                return True

    # Paralysis
    if move_status == _STATUS_PARALYSIS:
        has_para_immunity = ability in PARA_AB_IM
        # Electric-specific immunities
        is_electric_fail = False
        if move[_MOVE_TYPE] == _TYPES_ELECTRIC:
            is_ground = _TYPES_GROUND in u_type12
            is_elec_immune_ability = (
                ability in ELEC_AB_IM
                and ai_pok[_POK_AB_ID] != _ABILITYNAMES_MOLD_BREAKER
            )
            is_electric_fail = is_ground or is_elec_immune_ability

        if has_para_immunity or is_electric_fail:
            return True

    # Burn
    if (
        move_status == _STATUS_BURN
        and (
            ability in BURN_AB_IM
            or _TYPES_FIRE in u_type12
        )
    ):
        return True

    return False


@njit
def basic_move_vol_status(move, ability, user_pok, ai_pok, user_side=0):
    """
    Checks to see if any of the conditions for a move that has volatile status
    is irrelevant. user_side is the target's Field.SIDE_COND
    """
    # TODO: Every volatile status
    vol_status = move[_MOVE_VOL_STATUS]
    user_vol_status = user_pok[_POK_VOL_STATUS]

    if vol_status == _VOLSTATUS_CONFUSION:
        if user_vol_status & _VOLSTATUS_CONFUSION:
            return -5
        if ability == _ABILITYNAMES_OWN_TEMPO:
            return -10
        if user_side & _SIDECONDITION_SAFEGUARD:
            return -10
    # Attract
    elif vol_status == _VOLSTATUS_ATTRACT:
        if (
            user_vol_status & _VOLSTATUS_ATTRACT
            or ability == _ABILITYNAMES_OBLIVIOUS
            or (
                user_pok[_POK_GENDER] == ai_pok[_POK_GENDER]
                or user_pok[_POK_GENDER] == _GENDER_GENDERLESS
                or ai_pok[_POK_GENDER] == _GENDER_GENDERLESS
            )
        ):
            return -10
    elif vol_status == _VOLSTATUS_FOCUS_ENERGY:
        if ai_pok[_POK_VOL_STATUS] & _VOLSTATUS_FOCUS_ENERGY:
            return -10
    elif vol_status == _VOLSTATUS_LEECH_SEED:
        if (
            user_vol_status & _VOLSTATUS_LEECH_SEED
            or user_pok[_POK_TYPE1] == _TYPES_GRASS
            or user_pok[_POK_TYPE2] == _TYPES_GRASS
            or ability == _ABILITYNAMES_MAGIC_GUARD
        ):
            return -10
    elif vol_status == _VOLSTATUS_FORESIGHT:
        if user_vol_status & _VOLSTATUS_FORESIGHT:
            return -10
    elif vol_status in SELF_ONCE_VOLS:
        # Ingrain, Aqua Ring, Mud Sport, Water Sport: the AI already has it
        if ai_pok[_POK_VOL_STATUS] & vol_status:
            return -10
    elif vol_status == _VOLSTATUS_YAWN:
        if (
            user_pok[_POK_STATUS] != 0
            or user_side & _SIDECONDITION_SAFEGUARD
            or ability == _ABILITYNAMES_INSOMNIA
            or ability == _ABILITYNAMES_VITAL_SPIRIT
        ):
            return -10
    elif vol_status == _VOLSTATUS_HELPING_HAND:
        # Singles only
        return -10
    elif vol_status == _VOLSTATUS_ENCORE:
        if user_vol_status & _VOLSTATUS_ENCORE:
            return -8
    elif vol_status == _VOLSTATUS_DISABLE:
        if user_vol_status & _VOLSTATUS_DISABLE:
            return -8

    return 0


@njit
def basic_stat_change(move, ability, user_pok, ai_pok) -> bool:
    """
    Checks to see if any of the bad uses for a buff or debuff stat move
    happens and returns the check if the do
    """
    # TODO: Trick room
    b_atk   = move[_MOVE_BOOST_ATK]
    b_def   = move[_MOVE_BOOST_DEF]
    b_spatk = move[_MOVE_BOOST_SPATK]
    b_spdef = move[_MOVE_BOOST_SPDEF]
    b_spe   = move[_MOVE_BOOST_SPEED]
    b_acc   = move[_MOVE_BOOST_ACC]
    b_ev    = move[_MOVE_BOOST_EV]
    if move[_MOVE_TARGET] in TARGET_SELF_SIDE:
        s_atk   = ai_pok[_POK_ATTACK_STAT_STAGE]
        s_def   = ai_pok[_POK_DEFENSE_STAT_STAGE]
        s_spatk = ai_pok[_POK_SPECIAL_ATTACK_STAT_STAGE]
        s_spdef = ai_pok[_POK_SPECIAL_DEFENSE_STAT_STAGE]
        s_spe   = ai_pok[_POK_SPEED_STAT_STAGE]
        s_acc   = ai_pok[_POK_ACCURACY_STAT_STAGE]
        s_ev    = ai_pok[_POK_EVASION_STAT_STAGE]

        # Unify Simple (cap=3) and normal (cap=6) into one threshold
        cap = 3 if ai_pok[_POK_AB_ID] == _ABILITYNAMES_SIMPLE else 6

        if (b_atk   > 0 and s_atk   >= cap) \
        or (b_def   > 0 and s_def   >= cap) \
        or (b_spatk > 0 and s_spatk >= cap) \
        or (b_spdef > 0 and s_spdef >= cap) \
        or (b_spe   > 0 and s_spe   >= cap) \
        or (b_acc   > 0 and s_acc   >= cap) \
        or (b_ev    > 0 and s_ev    >= cap):
            return True

    elif move[_MOVE_TARGET] in TARGET_OPP_SIDE:  # your already-extracted set
        s_atk   = user_pok[_POK_ATTACK_STAT_STAGE]
        s_def   = user_pok[_POK_DEFENSE_STAT_STAGE]
        s_spatk = user_pok[_POK_SPECIAL_ATTACK_STAT_STAGE]
        s_spdef = user_pok[_POK_SPECIAL_DEFENSE_STAT_STAGE]
        s_spe   = user_pok[_POK_SPEED_STAT_STAGE]
        s_acc   = user_pok[_POK_ACCURACY_STAT_STAGE]
        s_ev    = user_pok[_POK_EVASION_STAT_STAGE]

        if (b_atk   < 0 and s_atk   == -6) \
        or (b_def   < 0 and s_def   == -6) \
        or (b_spatk < 0 and s_spatk == -6) \
        or (b_spdef < 0 and s_spdef == -6) \
        or (b_spe   < 0 and s_spe   == -6) \
        or (b_acc   < 0 and s_acc   == -6) \
        or (b_ev    < 0 and s_ev    == -6):
            return True

        # Ability immunity checks (HYPER_CUTTER, KEEN_EYE etc.) use local b_* from above
        # pokeplatinum Basic_CheckLowStatStage_*: only the stats the move lowers, read from the
        # target's ability (No Guard from either side)
        lowers = (
            b_atk < 0 or b_def < 0 or b_spatk < 0 or b_spdef < 0 or b_spe < 0 or b_acc < 0
            or b_ev < 0
        )
        if b_atk < 0 and ability == _ABILITYNAMES_HYPER_CUTTER:  return True
        if b_spe < 0 and ability == _ABILITYNAMES_SPEED_BOOST:   return True
        if lowers and ability in STAT_AB_IM:                    return True
        if (b_acc < 0 or b_ev < 0) and (
            ability == _ABILITYNAMES_NO_GUARD
            or ai_pok[_POK_AB_ID] == _ABILITYNAMES_NO_GUARD
        ):
            return True
        if b_acc < 0 and ability == _ABILITYNAMES_KEEN_EYE:     return True
    return False


@njit
def basic_moves(move, ai_pok, user_pok, ability, effectiveness):
    """
    Moves that triggers a special condition on the basic flag
    """
    move_id = move[_MOVE_ID]
    if move_id == _MOVENAME_CURSE:
        if ai_pok[_POK_TYPE1] == _TYPES_GHOST or ai_pok[_POK_TYPE2] == _TYPES_GHOST:
            if user_pok[_POK_VOL_STATUS] & _VOLSTATUS_CURSE:
                return -10
            if ability == _ABILITYNAMES_MAGIC_GUARD:
                return -10
        else:
            if (
                ai_pok[_POK_AB_ID] == _ABILITYNAMES_SIMPLE
                and (
                    ai_pok[_POK_ATTACK_STAT_STAGE] >= 3
                    or ai_pok[_POK_DEFENSE_STAT_STAGE] >= 3
                )
            ):
                return -10
            if ai_pok[_POK_ATTACK_STAT_STAGE] >= 6:
                return -10
            if ai_pok[_POK_DEFENSE_STAT_STAGE] >= 6:
                return -8
    elif move_id == _MOVENAME_FAKE_OUT:
        if effectiveness <= 0:
            return -10
        if (
            ability == _ABILITYNAMES_MAGIC_GUARD
            and effectiveness < 2
            and ai_pok[_POK_AB_ID] != _ABILITYNAMES_MOLD_BREAKER
        ):
            return -12
        if ai_pok[_POK_TURNS_ACTIVE] > 1:
            return -10
    elif move_id == _MOVENAME_BULK_UP:
        if ai_pok[_POK_AB_ID] == _ABILITYNAMES_SIMPLE:
            if ai_pok[_POK_ATTACK_STAT_STAGE] >= 3 or ai_pok[_POK_DEFENSE_STAT_STAGE] >= 3:
                return -10
        else:
            if ai_pok[_POK_ATTACK_STAT_STAGE] >= 6:
                return -10
            if ai_pok[_POK_DEFENSE_STAT_STAGE] >= 6:
                return -8
    elif move_id == _MOVENAME_TICKLE:
        if ai_pok[_POK_AB_ID] != _ABILITYNAMES_MOLD_BREAKER and ability in STAT_AB_IM:
            return -10
        if user_pok[_POK_ATTACK_STAT_STAGE] <= -6:
            return -10
        if user_pok[_POK_DEFENSE_STAT_STAGE] <= -6:
            return -8

    return 0



@njit
def basic_misc(move, ability, ai_pok, user_pok, ai_know):
    """
    pokeplatinum Basic_CheckCanRecoverHP, Basic_CheckCanRefreshStatus, Basic_CheckCanRecycle,
    Basic_CheckWorrySeed and Basic_CheckPerishSong. ability is the target's
    """
    move_id = move[_MOVE_ID]
    if move_id in HEAL_M:
        return -8 if ai_pok[_POK_CURRENT_HP] == ai_pok[_POK_MAX_HP] else 0
    if move_id == _MOVENAME_REFRESH:
        return 0 if ai_pok[_POK_STATUS] in REFRESH_STATUSES else -10
    if move_id == _MOVENAME_RECYCLE:
        return -10 if ai_pok[_POK_CONSUMED_ITEM] == 0 else 0
    if move_id == _MOVENAME_WORRY_SEED:
        if ability in WORRY_SEED_BAD_AB:
            return -10
        if user_pok[_POK_STATUS] == _STATUS_SLEEP and not seen_move(user_pok, ai_know, SLEEP_USABLE_M):
            return -10
        return 0
    if move_id == _MOVENAME_PERISH_SONG:
        return -10 if user_pok[_POK_VOL_STATUS] & _VOLSTATUS_PERISH_SONG else 0
    return 0


@njit
def basic_field(move, ability, ai_pok, user_pok, weather, ai_side, user_side, user_tspikes, user_bench):
    """
    pokeplatinum Basic checks for the side condition and weather moves. ability is the target's,
    user_bench how many Pokemon the target has alive besides the active
    """
    cond = move[_MOVE_SIDE_CONDITION]
    if cond == _SIDECONDITION_LUCKY_CHANT:
        return -10 if ai_side & cond else 0
    if cond in SCREEN_MIST_SAFEGUARD:
        return -8 if ai_side & cond else 0
    if cond == _SIDECONDITION_TOXIC_SPIKES:
        return -10 if user_tspikes >= TOXIC_SPIKES_MAX or user_bench <= 0 else 0
    if cond == _SIDECONDITION_STEALTH_ROCK:
        return -10 if user_side & cond or user_bench <= 0 else 0
    move_id = move[_MOVE_ID]
    if move_id == _MOVENAME_SANDSTORM:
        return -8 if weather == _WEATHER_SANDSTORM else 0
    if move_id == _MOVENAME_RAIN_DANCE:
        ai_ab = ai_pok[_POK_AB_ID]
        if (
            ai_ab != _ABILITYNAMES_SWIFT_SWIM
            and ai_ab != _ABILITYNAMES_HYDRATION
            and ability == _ABILITYNAMES_HYDRATION
            and user_pok[_POK_STATUS] != 0
        ):
            return -8
        return -8 if weather == _WEATHER_RAIN else 0
    return 0


@njit
def _cant_poison(pok, ability, side):
    """The AI script's "can't be poisoned": statused, behind Safeguard, Poison or Steel, or
    Immunity, Magic Guard or Poison Heal"""
    return bool(
        pok[_POK_STATUS] != 0
        or side & _SIDECONDITION_SAFEGUARD
        or pok[_POK_TYPE1] in STEEL_POISON
        or pok[_POK_TYPE2] in STEEL_POISON
        or ability in POISON_AB_IM
    )


@njit
def _cant_burn(pok, ability, side):
    """The AI script's "can't be burned": statused, behind Safeguard, Fire, or Water Veil or Magic
    Guard"""
    return bool(
        pok[_POK_STATUS] != 0
        or side & _SIDECONDITION_SAFEGUARD
        or pok[_POK_TYPE1] == _TYPES_FIRE
        or pok[_POK_TYPE2] == _TYPES_FIRE
        or ability in BURN_AB_IM
    )


@njit
def basic_fling(ability, ai_pok, user_pok, ai_side, user_side):
    """
    Pokemow Basic Fling: nothing to throw is -10. A poisoning or burning item the target can't get
    is -5 if the AI can't get it either (or has Guts), else +3; a Light Ball the target can't be
    paralyzed by is -5 (pokeplatinum Basic_CheckFling, Klutz left out: no RP species has it).
    ability is the target's
    """
    item = ai_pok[_POK_ITEM_ID]
    if item == 0:
        return -10
    ai_ab = ai_pok[_POK_AB_ID]
    if item in FLING_POISON_ITEMS:
        if ai_ab == _ABILITYNAMES_POISON_HEAL or _cant_poison(user_pok, ability, user_side):
            return -5 if _cant_poison(ai_pok, ai_ab, ai_side) or ai_ab == _ABILITYNAMES_GUTS else 3
    elif item == _ITEMNAMES_FLAME_ORB:
        if _cant_burn(user_pok, ability, user_side):
            return -5 if _cant_burn(ai_pok, ai_ab, ai_side) or ai_ab == _ABILITYNAMES_GUTS else 3
    elif item == _ITEMNAMES_LIGHT_BALL:
        if (
            user_side & _SIDECONDITION_SAFEGUARD
            or user_pok[_POK_STATUS] != 0
            or ability == _ABILITYNAMES_LIMBER
        ):
            return -5
    return 0


@njit
def basic_switch(move, ability, ai_pok, user_bench, ai_bench):
    """
    pokeplatinum Basic_CheckCanForceSwitch and Basic_CheckBatonPass, Teleport always fails in
    a trainer battle (BATTLE_EFFECT_FLEE_FROM_WILD_BATTLE)
    """
    if move[_MOVE_FORCE_SWITCH]:
        if user_bench <= 0:
            return -10
        if ai_pok[_POK_AB_ID] != _ABILITYNAMES_MOLD_BREAKER and ability == _ABILITYNAMES_SUCTION_CUPS:
            return -10
        return 0
    if move[_MOVE_ID] == _MOVENAME_BATON_PASS:
        return -10 if ai_bench <= 0 else 0
    if move[_MOVE_ID] == _MOVENAME_TELEPORT:
        return -10
    return 0


@njit
def basic_flag(
            move, ability, ai_pok, user_pok, effectiveness,
            weather, ai_side=0, user_side=0, user_tspikes=0, user_bench=1, ai_bench=1, ai_know=0,
            turn=0, gravity=False
    ):
    """
    Basic Flag, every trainer has this,
    it discourages moves that would have no effect or that would make no sense.
    ai_side and user_side are both Field.SIDE_COND, user_tspikes the Toxic Spikes layers on the
    target's side and user_bench how many Pokemon it has alive besides the active, ai_bench the
    same for the AI. ai_know is Field.AI_KNOWS, turn is Field.TURN, gravity if Gravity is up
    """
    if move[_MOVE_ID] in NO_AI_CHECK_M:
        return 0
    if move[_MOVE_SIDE_CONDITION] or move[_MOVE_ID] in WEATHER_M:
        return basic_field(
            move, ability, ai_pok, user_pok, weather, ai_side, user_side, user_tspikes, user_bench
        )
    if move[_MOVE_ID] in BASIC_SPECIFIC_M:
        return basic_moves(move, ai_pok, user_pok, ability, effectiveness)
    if move[_MOVE_ID] in MISC_BASIC_M:
        return basic_misc(move, ability, ai_pok, user_pok, ai_know)
    # Basic_CheckCopycat, Pokemow drops pokeplatinum's "and the AI is faster"
    if move[_MOVE_ID] == _MOVENAME_COPYCAT:
        return -10 if turn <= 1 else 0
    # Basic_CheckGravityActive
    if move[_MOVE_ID] == _MOVENAME_GRAVITY:
        return -10 if gravity else 0
    # Basic_CheckCannotSubstitute
    if move[_MOVE_ID] == _MOVENAME_SUBSTITUTE:
        if ai_pok[_POK_VOL_STATUS2] & _VOLSTATUS2_SUBSTITUTE:
            return -8
        return -10 if (ai_pok[_POK_CURRENT_HP] * 100) // ai_pok[_POK_MAX_HP] < 26 else 0
    move_category = move[_MOVE_CATEGORY]
    # Check for immunity types
    if move_category != _MOVECATEGORY_STATUS and effectiveness == 0:
        return -10
    # Check for abilities
    if ai_pok[_POK_AB_ID] != _ABILITYNAMES_MOLD_BREAKER and ability in ABILITY_BASIC_FLAG:
        ability_score = basic_ability(move, ability, user_pok, move_category)
        if ability_score:
            return ability_score
    if move[_MOVE_ID] == _MOVENAME_NATURAL_GIFT and ai_pok[_ITEM_NATURAL_GIFT_POWER] == 0:
        return -10
    # Basic_CheckCannotExplode, the immunity is checked above: Damp unless the AI has Mold
    # Breaker, then the AI's last Pokemon only explodes into the target's last one (-1)
    if move[_MOVE_ID] in EXPLODE_MOVES:
        if ai_pok[_POK_AB_ID] != _ABILITYNAMES_MOLD_BREAKER and ability == _ABILITYNAMES_DAMP:
            return -10
        if ai_bench <= 0:
            return -10 if user_bench > 0 else -1
        return 0
    # Basic_CheckOHKOWouldFail, the immunity is checked above: Sturdy unless the AI has Mold
    # Breaker, then a target with a higher level
    if move[_MOVE_OH_KO]:
        if ai_pok[_POK_AB_ID] != _ABILITYNAMES_MOLD_BREAKER and ability == _ABILITYNAMES_STURDY:
            return -10
        return -10 if ai_pok[_POK_LEVEL] < user_pok[_POK_LEVEL] else 0
    # Basic_CheckCanRemoveItem, also Trick's and Switcheroo's (a target holding nothing still
    # takes the AI's item, the script doesn't look)
    if move[_MOVE_ID] in REMOVE_ITEM_M:
        return -10 if ability == _ABILITYNAMES_STICKY_HOLD or user_pok[_POK_ITEM_ID] == 0 else 0
    # Basic_CheckEmbargo, the Recycle and Frontier checks change nothing outside the Frontier
    if move[_MOVE_ID] == _MOVENAME_EMBARGO:
        return -10 if embargoed(user_pok) else 0
    if move[_MOVE_ID] == _MOVENAME_FLING:
        return basic_fling(ability, ai_pok, user_pok, ai_side, user_side)
    if move[_MOVE_FORCE_SWITCH] or move[_MOVE_ID] in SWITCH_EXPERT_M:
        return basic_switch(move, ability, ai_pok, user_bench, ai_bench)
    if move_category == _MOVECATEGORY_STATUS:
        if move[_MOVE_STATUS] != 0:
            if basic_move_status(move, ability, user_pok, ai_pok, weather, user_side):
                return -10
        if move[_MOVE_VOL_STATUS] != 0:
            vol_status = basic_move_vol_status(move, ability, user_pok, ai_pok, user_side)
            if vol_status:
                return vol_status
        if (
            move[_MOVE_BOOST_ATK]
            or move[_MOVE_BOOST_DEF]
            or move[_MOVE_BOOST_SPATK]
            or move[_MOVE_BOOST_SPDEF]
            or move[_MOVE_BOOST_SPEED]
            or move[_MOVE_BOOST_ACC]
            or move[_MOVE_BOOST_EV]
        ):
            if basic_stat_change(move, ability, user_pok, ai_pok):
                return -10

    '''
    TODO:
    --------------Specific Moves---------------
    Selfdestruct/Explosion
    Nightmare
    Dream Eater
    Belly Drum
    Reflect / Light Screen / Mist / Safeguard
    Camouflage / Power Trick / Lucky Chant / Magnet Rise
    Snore / Sleep Talk
    Lock On / Mean Look / Torment / Miracle Eye / Heal Block / Gastro Acid
    Future Sight / Doom Desire
    Stockpile
    Spit Up / Swallow
    Memento
    Trick / Switcheroo
    Imprison
    Cosmic Power / Calm Mind / Dragon Dance
    Gravity / Tailwind
    Trick Room
    Healing Wish / Lunar Dance
    Acupressure
    Metal Burst
    Embargo
    Fling
    Psycho Shift
    Copycat
    Power Swap / Guard Swap
    Last Resort
    Defog
    Captivate
    --------------Effect Moves-----------------
    Stat Stage Resetting/Copying/Swapping Moves(Example: Haze, Psych Up, Heart Swap)
    Non-Standard Damage and Charge Turn Moves(
    Charge Turn Moves:
        -Razor Wind
        -Sky Attack
        -Blast Burn
        -Frenzy Plant
        -Giga Impact
        -Hydro Cannon
        -Hyper Beam
        -Roar of Time
        -Rock Wrecker
        -Skull Bash
        -Focus Punch
        -Superpower (for some reason)
    Variable Power / Flat Damage Moves:
        -Bide
        -Super Fang
        -Dragon Rage
        -Night Shade
        -Seismic Toss
        -Psywave
        -Counter
        -Flail
        -Reversal
        -Return
        -Present
        -Frustration
        -Sonic Boom
        -Hidden Power
        -Mirror Coat
        -Endeavor
        -Low Kick
        -Grass Knot
        -Gyro Ball
        -Trump Card
        -Crush Grip
        -Wring Out
        -Punishment
        -Magnitude
    )
    Force Switches(Example moves: Roar, Whirlwind)
    Recovery Moves(Example moves: Roost)
    Hazard-Setting Moves (Spikes, Toxic Spikes, Stealth Rock)
    Weather-Setting Moves (Sandstorm, Rain Dance, Sunny Day, Hail)
    '''

    return 0


@njit
def evaluate_attack_flag(
            final_damage, effectiveness, user_pok, move, idx, rand, damage_calc
    ):
    """
    For moves subject to the damage calc it sees if it kills. If it doesn't, the "a stronger
    move exists" -1 and the 4x check after it are done in choose_move, since they need every
    move's damage.
    The other moves (status and the damage calc exceptions) get the move exceptions penalty
    and check if its 4x effective
    """
    score = 0
    move_id = move[_MOVE_ID]
    if damage_calc:
        # Check for kill
        if final_damage >= user_pok[_POK_CURRENT_HP]:
            if move_id in FUTURE_ATTACK_MOVES:
                add_adjustment(rand, idx, 4, 85)
            elif move[_MOVE_PRIORITY] >= 1 and move_id != _MOVENAME_FAKE_OUT:
                score = 6
            else:
                score = 4
        return score

    if (
        move_id in MAYBE_BAD_MOVES
    ):
        add_adjustment(rand, idx, -2, 205)
    if effectiveness == 4.0:
        add_adjustment(rand, idx, 2, 176)
    return score

@njit
def expert_status(
        move,
        hp_pct_ai,
        hp_pct_u,
        rand,
        ai_pok,
        move_first,
        idx
):
    """
    Expert flag status checks
    """
    m_status = move[_MOVE_STATUS]

    # Burn
    if m_status == _STATUS_BURN:
        return 0

    # Poison, but not badly poison
    if (
        m_status == _STATUS_POISON
        and (hp_pct_ai < 50 or hp_pct_u < 51)
    ):
        return -1

    # Paralyzing-Inducing
    if m_status == _STATUS_PARALYSIS and not move_first:
        add_adjustment(rand, idx, 3, 236)
        return 0

    # TODO: Badly poison
    if m_status == _STATUS_TOXIC:
        return 0

    # Sleep-Inducing
    if (
        m_status == _STATUS_SLEEP
        and (
            ai_pok[_POK_MOVE1_ID] in SLEEP_MOVES
            or ai_pok[_POK_MOVE2_ID] in SLEEP_MOVES
            or ai_pok[_POK_MOVE3_ID] in SLEEP_MOVES
            or ai_pok[_POK_MOVE4_ID] in SLEEP_MOVES
        )
    ):
        add_adjustment(rand, idx, 1, 128)
        return 0

    return 0


@njit
def seen_move(pok, ai_know, move_ids):
    """If the AI saw pok use one of move_ids (Field.AI_KNOWS move bits)"""
    for i in range(4):
        if ai_know & AI_KNOWS_MOVE_BITS[i] and pok[MOVE_ID_SLOTS[i]] in move_ids:
            return True
    return False


@njit
def has_damaging_move(pok):
    """If any of the Pokemon's moves deals damage"""
    for i in range(4):
        if pok[MOVE_CATEGORY_SLOTS[i]] in DAMAGING_CATEGORIES:
            return True
    return False


@njit
def wearing_down(pok):
    """
    Toxic, Curse, Attract, Leech Seed, Yawn or Perish Song, the list Expert Protect and Feint check.
    """
    return (
        pok[_POK_STATUS] == _STATUS_TOXIC
        or pok[_POK_VOL_STATUS] & (
            _VOLSTATUS_CURSE | _VOLSTATUS_ATTRACT | _VOLSTATUS_LEECH_SEED | _VOLSTATUS_YAWN
            | _VOLSTATUS_PERISH_SONG
        ) != 0
    )


@njit
def expert_protect(ai_pok, u_pok, rand, idx, ai_know):
    """Pokemow Expert Protect. TODO: Lock-On / Mind Reader on the AI"""
    score = 0
    if seen_move(u_pok, ai_know, FEINT_LIKE_M):
        add_adjustment(rand, idx, -2, 128)
    chain = ai_pok[_POK_PROTECT_COUNT]
    if chain >= 2:
        return score - 2
    if wearing_down(ai_pok) or seen_move(u_pok, ai_know, RECOVER_DEF_CURL_M):
        return score - 2
    if wearing_down(u_pok):
        score += 2
    else:
        add_adjustment(rand, idx, 2, 85)
    add_adjustment(rand, idx, -1, 128)
    if chain == 1:
        score -= 1
        add_adjustment(rand, idx, -1, 128)
    return score


@njit
def expert_feint(ai_pok, u_pok, rand, idx, ai_know):
    """
    Pokemow Expert Feint, which differs from pokeplatinum: the HP/item condition is an "or" and a
    target Protect chain of 2 already scores -2
    """
    if not seen_move(u_pok, ai_know, PROTECT_LIKE_M) and random.getrandbits(8) >= 64:
        return 0
    if (
        wearing_down(ai_pok)
        or u_pok[_POK_CURRENT_HP] != u_pok[_POK_MAX_HP]
        or u_pok[_POK_ITEM_ID] in GRADUAL_RECOVERY_ITEMS
    ):
        add_adjustment(rand, idx, 1, 128)
    chain = u_pok[_POK_PROTECT_COUNT]
    if chain == 0:
        add_adjustment(rand, idx, 1, 128)
        return 0
    if chain == 1:
        add_adjustment(rand, idx, 1, 64)
        return 0
    return -2


@njit
def expert_vol_status(
    move, ai_pok, u_pok, turn, rand, idx, hp_pct_u, hp_pct_ai=100, move_first=False, ai_know=0
):
    """
    Expert flag volatile status checks
    """
    # Confusion-Inducing
    if move[_MOVE_VOL_STATUS] == _VOLSTATUS_CONFUSION:
        score = 0
        if move[_MOVE_ID] == _MOVENAME_SWAGGER:
            psych_up = False
            if (
                ai_pok[_POK_MOVE1_ID] == _MOVENAME_PSYCH_UP  #pylint: disable=R1714
                or ai_pok[_POK_MOVE2_ID] == _MOVENAME_PSYCH_UP
                or ai_pok[_POK_MOVE3_ID] == _MOVENAME_PSYCH_UP
                or ai_pok[_POK_MOVE4_ID] == _MOVENAME_PSYCH_UP
            ):
                psych_up = True
            if psych_up:
                if u_pok[_POK_ATTACK_STAT_STAGE] <= -3:
                    if turn == 1:
                        score += 5
                    else:
                        score += 3
                else:
                    score += -5
                return score
        if move[_MOVE_ID] in CONFUSE_SPECIAL_CASES:
            add_adjustment(rand, idx, 1, 128)
        if hp_pct_u <= 70:
            add_adjustment(rand, idx, -1, 128)
            if hp_pct_u < 31:
                score += -1
            if hp_pct_u < 51:
                score += -1
        return score
    vol_status = move[_MOVE_VOL_STATUS]
    if vol_status == _VOLSTATUS_PROTECT:
        return expert_protect(ai_pok, u_pok, rand, idx, ai_know)
    if vol_status == _VOLSTATUS_ENDURE:
        if hp_pct_ai < 4:
            return -1
        if hp_pct_ai < 35:
            add_adjustment(rand, idx, 1, 186)
            return 0
        return -1
    if vol_status == _VOLSTATUS_FORESIGHT:
        # pokeplatinum and Pokemow check the AI's own Ghost typing, not the target's
        if ai_pok[_POK_TYPE1] == _TYPES_GHOST or ai_pok[_POK_TYPE2] == _TYPES_GHOST:
            add_adjustment(rand, idx, 2, 121)
            return 0
        if u_pok[_POK_EVASION_STAT_STAGE] >= 3:
            add_adjustment(rand, idx, 2, 176)
            return 0
        return -2
    if vol_status == _VOLSTATUS_DESTINY_BOND:
        if not move_first or hp_pct_ai > 70:
            return -1
        add_adjustment(rand, idx, -1, 128)
        if hp_pct_ai < 51:
            add_adjustment(rand, idx, 1, 128)
        if hp_pct_ai < 31:
            add_adjustment(rand, idx, 2, 156)
        return 0
    if vol_status == _VOLSTATUS_LEECH_SEED:
        # Pokemow's Toxic check, which Leech Seed shares
        if has_damaging_move(ai_pok):
            if hp_pct_ai < 51:
                add_adjustment(rand, idx, -3, 206)
            if hp_pct_u < 51:
                add_adjustment(rand, idx, -3, 206)
        for move_id_slot in MOVE_ID_SLOTS:
            if ai_pok[move_id_slot] in PROTECT_LIKE_M:
                add_adjustment(rand, idx, 2, 196)
                break
        return 0
    if vol_status == _VOLSTATUS_MUD_SPORT or vol_status == _VOLSTATUS_WATER_SPORT:
        if hp_pct_ai < 50:
            return -1
        sport_type = _TYPES_ELECTRIC if vol_status == _VOLSTATUS_MUD_SPORT else _TYPES_FIRE
        if u_pok[_POK_TYPE1] == sport_type or u_pok[_POK_TYPE2] == sport_type:
            return 1
        return -1
    if vol_status == _VOLSTATUS_AQUA_RING:
        if hp_pct_ai >= 30:
            add_adjustment(rand, idx, 1, 128)
        return 0
    if vol_status == _VOLSTATUS_ENCORE:
        if u_pok[_POK_VOL_STATUS] & _VOLSTATUS_DISABLE:
            add_adjustment(rand, idx, 3, 226)
            return 0
        if not move_first:
            return -2
        if u_pok[_POK_LAST_MOVE_ID] in ENCORE_ENCOURAGED_M:
            add_adjustment(rand, idx, 3, 226)
            return 0
        return -2
    if vol_status == _VOLSTATUS_DISABLE:
        if not move_first:
            return 0
        last = u_pok[_POK_LAST_MOVE_ID]
        # No move yet or a status one (power 0)
        if last not in PHYSICAL and last not in SPECIAL:
            add_adjustment(rand, idx, -1, 156)
            return 0
        return 1
    # Focus Energy, Ingrain, Attract, Yawn, Helping Hand, Follow Me, Taunt have no Expert check
    return 0

@njit(inline='always')
def _expert_stat_self(
    move, ai_pok, rand, idx, hp_pct_ai,
    move_first, u_pok, hp_pct_u, my_last_move
):
    """Handles adjustments for moves targeting self side"""
    if move[_MOVE_BOOST_DEF]:
        if ai_pok[_POK_DEFENSE_STAT_STAGE] >= 3:
            add_adjustment(rand, idx, -1, 156)
        elif hp_pct_ai == 100:
            add_adjustment(rand, idx, 2, 128)
        if hp_pct_ai > 69:
            if random.getrandbits(8) < 200:
                return 0
        if hp_pct_ai < 40:
            return -2
        if my_last_move in SPECIAL:
            return -2
        if my_last_move not in PHYSICAL:
            add_adjustment(rand, idx, -2, 196)
            return 0
        add_adjustment(rand, idx, -2, 150)
        return 0

    if move[_MOVE_BOOST_SPDEF]:
        if ai_pok[_POK_SPECIAL_DEFENSE_STAT_STAGE] >= 3:
            add_adjustment(rand, idx, -1, 156)
        elif hp_pct_ai == 100:
            add_adjustment(rand, idx, 2, 128)
        if hp_pct_ai > 69:
            if random.getrandbits(8) < 200:
                return 0
        if hp_pct_ai < 40:
            return -2
        if my_last_move in PHYSICAL:
            return -2
        if my_last_move not in SPECIAL:
            add_adjustment(rand, idx, -2, 196)
            return 0
        add_adjustment(rand, idx, -2, 150)
        return 0

    if move[_MOVE_BOOST_ATK] and move[_MOVE_ID] != _MOVENAME_DRAGON_DANCE:
        if ai_pok[_POK_ATTACK_STAT_STAGE] >= 3:
            add_adjustment(rand, idx, -1, 156)
        if hp_pct_ai == 100:
            add_adjustment(rand, idx, 2, 128)
        if 39 < hp_pct_ai < 71:
            add_adjustment(rand, idx, -2, 216)
            return 0
        if hp_pct_ai < 40:
            return -2
        return 0

    if move[_MOVE_BOOST_SPATK]:
        if ai_pok[_POK_SPECIAL_ATTACK_STAT_STAGE] >= 3:
            add_adjustment(rand, idx, -1, 156)
        if hp_pct_ai == 100:
            add_adjustment(rand, idx, 2, 128)
        if 39 < hp_pct_ai < 71:
            add_adjustment(rand, idx, -2, 186)
            return 0
        if hp_pct_ai < 40:
            return -2
        return 0

    if move[_MOVE_BOOST_SPEED] and move[_MOVE_ID] != _MOVENAME_DRAGON_DANCE:
        if move_first:
            return -3
        add_adjustment(rand, idx, 3, 186)
        return 0

    if move[_MOVE_BOOST_EV]:
        # TODO: Ingrain, Aqua Ring
        ai_ev_stage = ai_pok[_POK_EVASION_STAT_STAGE]
        if hp_pct_ai > 89:
            add_adjustment(rand, idx, 3, 156)
        if ai_ev_stage >= 3:
            add_adjustment(rand, idx, -1, 128)
        if u_pok[_POK_STATUS] == _STATUS_TOXIC:
            if hp_pct_ai > 50:
                add_adjustment(rand, idx, 3, 206)
            else:
                add_adjustment(rand, idx, 3, 142)
        u_pok_vol_stat = u_pok[_POK_VOL_STATUS]
        if u_pok_vol_stat & _VOLSTATUS_LEECH_SEED:
            add_adjustment(rand, idx, 3, 186)
        if u_pok_vol_stat & _VOLSTATUS_CURSE:
            add_adjustment(rand, idx, 3, 186)
        if hp_pct_ai > 70 or ai_ev_stage == 0:
            return 0
        if hp_pct_ai < 40 or hp_pct_u < 40:
            return -2
        add_adjustment(rand, idx, -2, 186)
        return 0

    raise ValueError("Target self missing something")


@njit(inline='always')
def _expert_stat_opp(
    move, ai_pok, rand, idx, hp_pct_ai,
    move_first, u_pok, hp_pct_u, my_last_move
):
    """Handles adjustments for moves targeting opponent side"""
    if move[_MOVE_BOOST_ATK] and not move[_MOVE_BOOST_DEF]:
        score = 0
        atk_stage = u_pok[_POK_ATTACK_STAT_STAGE]
        if atk_stage != 0:
            score += -1
            if hp_pct_ai < 91:
                score += -1
        if atk_stage <= -3:
            add_adjustment(rand, idx, -2, 206)
        if hp_pct_u < 71:
            score += -2
        if my_last_move in SPECIAL:
            add_adjustment(rand, idx, -2, 128)
            return score
        return score

    # No moves that are status and also reduce SP.Atk

    if move[_MOVE_BOOST_DEF]:
        score = 0
        if hp_pct_ai < 70 or u_pok[_POK_DEFENSE_STAT_STAGE] <= -3:
            add_adjustment(rand, idx, -2, 206)
        if hp_pct_u < 71:
            score += -2
        return score

    if move[_MOVE_BOOST_SPDEF]:
        score = 0
        if hp_pct_ai < 70 or u_pok[_POK_SPECIAL_DEFENSE_STAT_STAGE] <= -3:
            add_adjustment(rand, idx, -2, 206)
        if hp_pct_u < 71:
            score += -2
        return score

    if move[_MOVE_BOOST_SPEED]:
        if move_first:
            return -3
        add_adjustment(rand, idx, 2, 186)
        return 0

    if move[_MOVE_BOOST_ACC]:
        if hp_pct_ai < 70 or hp_pct_u < 71:
            add_adjustment(rand, idx, -1, 156)
        if ai_pok[_POK_ACCURACY_STAT_STAGE] <= -2:
            add_adjustment(rand, idx, -2, 176)
        if u_pok[_POK_STATUS] == _STATUS_TOXIC:
            add_adjustment(rand, idx, 2, 186)
        if u_pok[_POK_VOL_STATUS] & _VOLSTATUS_LEECH_SEED:
            add_adjustment(rand, idx, 2, 186)
        if u_pok[_POK_VOL_STATUS] & _VOLSTATUS_CURSE:
            add_adjustment(rand, idx, 2, 186)
        if hp_pct_ai > 70 or u_pok[_POK_ACCURACY_STAT_STAGE] == 0:
            return 0
        if hp_pct_ai < 40 or hp_pct_u < 40:
            return -2
        add_adjustment(rand, idx, -2, 186)
        return 0
        # TODO: Ingrain, Aqua Ring

    if move[_MOVE_BOOST_EV]:
        score = 0
        if hp_pct_ai < 70 or u_pok[_POK_EVASION_STAT_STAGE] <= -3:
            add_adjustment(rand, idx, -2, 206)
        if hp_pct_u < 71:
            score += -2
        return score

    raise ValueError("Target enemy missing something")


@njit
def expert_stat(
    move, ai_pok, rand, idx, hp_pct_ai,
    move_first, u_pok, hp_pct_u, my_last_move
):
    """
    Moves that changes stat
    """
    move_target = move[_MOVE_TARGET]

    if move_target in TARGET_SELF_SIDE:
        return _expert_stat_self(
            move, ai_pok, rand, idx, hp_pct_ai,
            move_first, u_pok, hp_pct_u, my_last_move
        )

    if move_target in TARGET_OPP_SIDE:
        return _expert_stat_opp(
            move, ai_pok, rand, idx, hp_pct_ai,
            move_first, u_pok, hp_pct_u, my_last_move
        )

    raise ValueError("Target no accounted for")


@njit
def expert_moves(move, u_pok, ai_pok, effectiveness, rand, idx, t_dmg, ml_move, move_first):
    """
    Expert moves that have specific logic
    """
    score = 0
    ai_hp_pct = (ai_pok[_POK_CURRENT_HP]*100)//ai_pok[_POK_MAX_HP]
    m_id = move[_MOVE_ID]
    if m_id == _MOVENAME_BIDE:
        if ai_hp_pct < 91:
            return -2
    elif m_id == _MOVENAME_BUG_BITE or m_id == _MOVENAME_PLUCK:
        if effectiveness == 0.5 or effectiveness == 0.25 or effectiveness == 0:
            return -1
        else:
            if ai_pok[_POK_TURNS] == 1:
                add_adjustment(rand, idx, 1, 192)
            add_adjustment(rand, idx, 1, 128)
    elif m_id == _MOVENAME_COUNTER:
        if (
            u_pok[_POK_STATUS] == _STATUS_SLEEP
            or u_pok[_POK_VOL_STATUS] & _VOLSTATUS_CONFUSION
            or u_pok[_POK_VOL_STATUS] & _VOLSTATUS_ATTRACT
        ):
            return -1
        if ai_hp_pct < 31:
            add_adjustment(rand, idx, -1, 246)
        if ai_hp_pct < 51:
            add_adjustment(rand, idx, -1, 156)
        if knows_move(ai_pok, _MOVENAME_MIRROR_COAT):
            add_adjustment(rand, idx, 4, 156)
            return 0
        if u_pok[_POK_VOL_STATUS] & _VOLSTATUS_TAUNT:
            add_adjustment(rand, idx, 1, 156)
        if t_dmg:
            if ml_move in SPECIAL:
                return -1
            add_adjustment(rand, idx, 1, 156)
            return 0
        if u_pok[_POK_TYPE1] in COUNTER_EX_TYPES or u_pok[_POK_TYPE2] in COUNTER_EX_TYPES:
            pass
        else:
            add_adjustment(rand, idx, 4, 126)
    elif m_id == _MOVENAME_MIRROR_COAT:
        if (
            u_pok[_POK_STATUS] == _STATUS_SLEEP
            or u_pok[_POK_VOL_STATUS] & _VOLSTATUS_CONFUSION
            or u_pok[_POK_VOL_STATUS] & _VOLSTATUS_ATTRACT
        ):
            return -1
        if ai_hp_pct < 31:
            add_adjustment(rand, idx, -1, 246)
        if ai_hp_pct < 51:
            add_adjustment(rand, idx, -1, 156)
        if knows_move(ai_pok, _MOVENAME_COUNTER):
            add_adjustment(rand, idx, 4, 156)
            return 0
        if u_pok[_POK_VOL_STATUS] & _VOLSTATUS_TAUNT:
            add_adjustment(rand, idx, 1, 156)
        if t_dmg:
            if ml_move in PHYSICAL:
                return -1
            add_adjustment(rand, idx, 1, 156)
            return 0
        if u_pok[_POK_TYPE1] in MIRROR_COAT_EX_TYPES or u_pok[_POK_TYPE2] in MIRROR_COAT_EX_TYPES:
            pass
        else:
            add_adjustment(rand, idx, 4, 126)
    elif m_id == _MOVENAME_ASSURANCE:
        if effectiveness <= 0.5:
            return -1
        if move_first:
            return 0
        # TODO: Jaboca and Rowap Berry also count, once they're in ItemDB
        if ai_pok[_POK_AB_ID] == _ABILITYNAMES_ROUGH_SKIN:
            add_adjustment(rand, idx, 1, 128)
        else:
            add_adjustment(rand, idx, 1, 64)
    elif m_id == _MOVENAME_COVET or m_id == _MOVENAME_THIEF:
        # AI cheats to see the user items
        if u_pok[_POK_ITEM_ID] in ITEMS_STEAL:
            add_adjustment(rand, idx, 1, 206)
        else:
            return -2
    elif m_id == _MOVENAME_CURSE:
        if ai_pok[_POK_TYPE1] == _TYPES_GHOST or ai_pok[_POK_TYPE2] == _TYPES_GHOST:
            if ai_hp_pct < 81:
                return -1
        else:
            if ai_pok[_POK_DEFENSE_STAT_STAGE] >= 4:
                return 0
            if (
                ai_pok[_POK_MOVE1_ID] in CURSE_SPECIAL_CASES
                or ai_pok[_POK_MOVE2_ID] in CURSE_SPECIAL_CASES
                or ai_pok[_POK_MOVE3_ID] in CURSE_SPECIAL_CASES
                or ai_pok[_POK_MOVE4_ID] in CURSE_SPECIAL_CASES
            ):
                if random.getrandbits(8) < 224:
                    score += 1
                    add_adjustment(rand, idx, 1, 128)
            else:
                add_adjustment(rand, idx, 1, 128)
            if ai_pok[_POK_DEFENSE_STAT_STAGE] >= 2:
                return score
            add_adjustment(rand, idx, 1, 128)
            if ai_pok[_POK_DEFENSE_STAT_STAGE] <= 0:
                add_adjustment(rand, idx, 1, 128)
    elif m_id == _MOVENAME_FAKE_OUT:
        return 2
    elif m_id == _MOVENAME_FLAIL:
        if move_first:
            if ai_hp_pct > 33:
                return -1
            if ai_hp_pct > 20:
                return 0
            if ai_hp_pct < 8:
                score += 1
            add_adjustment(rand, idx, 1, 156)
            return score
        if ai_hp_pct > 60:
            return -1
        if ai_hp_pct > 40:
            return 0
        add_adjustment(rand, idx, 1, 156)

    return score


@njit
def expert_misc(move, ai_pok, u_pok, rand, idx, weather, move_first):
    """
    pokeplatinum Expert_Recovery and Expert_Synthesis, Expert_Refresh, Expert_KnockOff,
    Expert_Recycle and Pokemow Worry Seed. Perish Song and Splash have no Expert check
    """
    move_id = move[_MOVE_ID]
    hp_pct_ai = (ai_pok[_POK_CURRENT_HP]*100) // ai_pok[_POK_MAX_HP]
    hp_pct_u = (u_pok[_POK_CURRENT_HP]*100) // u_pok[_POK_MAX_HP]
    if move_id in HEAL_M:
        score = 0
        if move_id == _MOVENAME_SYNTHESIS and weather in SYNTHESIS_BAD_WEATHER:
            score -= 2
        if hp_pct_ai == 100:
            return score - 3
        if move_first:
            return score - 8
        # 226/256 of -3 and terminate
        if hp_pct_ai > 69 and random.getrandbits(8) >= 30:
            return score - 3
        # Snatch isn't in MoveDB, a target seen using it would make this 2301/4096
        add_adjustment(rand, idx, 2, 236)
        return score
    if move_id == _MOVENAME_REFRESH:
        return -1 if hp_pct_u < 50 else 0
    if move_id == _MOVENAME_KNOCK_OFF:
        if hp_pct_u >= 30 and ai_pok[_POK_TURNS_ACTIVE] != 1:
            add_adjustment(rand, idx, 1, 76)
        return 0
    if move_id == _MOVENAME_RECYCLE:
        if ai_pok[_POK_CONSUMED_ITEM] in RECYCLE_GOOD_ITEMS:
            add_adjustment(rand, idx, 1, 206)
            return 0
        return -2
    if move_id == _MOVENAME_WORRY_SEED:
        # TODO: +1 when the target knows Rest, once it's in MoveDB
        # Pokemow reads the target's HP here, pokeplatinum the AI's own
        if hp_pct_u > 49:
            add_adjustment(rand, idx, 1, 128)
        add_adjustment(rand, idx, 1, 192)
    return 0


@njit
def expert_items(move, ai_pok, u_pok, effectiveness, rand, idx, ai_side, user_side):
    """
    pokeplatinum Expert_Trick (Trick and Switcheroo), Expert_Embargo and Expert_Fling, as Pokemow
    reads them. Trick reads both raw items, the AI cheats; Fling the AI's Fling power, which Embargo
    takes. Klutz is left out (no RP species has it)
    """
    move_id = move[_MOVE_ID]
    if move_id == _MOVENAME_EMBARGO:
        add_adjustment(rand, idx, 1, 128)
        return 0
    if move_id == _MOVENAME_FLING:
        if effectiveness == 0 or effectiveness == 0.25 or effectiveness == 0.5:
            return 0 if ai_pok[_POK_ITEM_ID] in FLING_GOOD_ITEMS else -1
        power = ai_pok[_ITEM_FLING_POWER]
        if power < 30:
            return -2
        if power > 90:
            score = 0
            if effectiveness >= 2:
                score = 4
            else:
                add_adjustment(rand, idx, 1, 128)
            add_adjustment(rand, idx, 1, 192)
            return score
        if power > 60:
            add_adjustment(rand, idx, 1, 192)
            return 0
        add_adjustment(rand, idx, -1, 128)
        return 0
    mine = raw_hold_effect(ai_pok)
    theirs = raw_hold_effect(u_pok)
    ai_ab = ai_pok[_POK_AB_ID]
    u_ab = u_pok[_POK_AB_ID]
    if theirs in TRICK_BAD_TRADE:
        return -3
    if mine in TRICK_DISRUPTIVE:
        return 5
    if mine == _HOLDEFFECT_PSN_USER:
        if not _cant_poison(u_pok, u_ab, user_side):
            return 5
        return -3 if _cant_poison(ai_pok, ai_ab, ai_side) else 5
    if mine == _HOLDEFFECT_BRN_USER:
        if not _cant_burn(u_pok, u_ab, user_side):
            return 5
        return -3 if _cant_burn(ai_pok, ai_ab, ai_side) else 5
    if mine == _HOLDEFFECT_HP_RESTORE_PSN_TYPE:
        if u_pok[_POK_TYPE1] == _TYPES_POISON or u_pok[_POK_TYPE2] == _TYPES_POISON:
            ai_poison = ai_pok[_POK_TYPE1] == _TYPES_POISON or ai_pok[_POK_TYPE2] == _TYPES_POISON
            return -3 if ai_poison or ai_ab == _ABILITYNAMES_MAGIC_GUARD else 5
        # The script jumps to the Toxic Orb's checks here (Pokemow agrees)
        if u_ab == _ABILITYNAMES_MAGIC_GUARD:
            return -3 if _cant_poison(ai_pok, ai_ab, ai_side) else 5
        return 5
    if mine in FLAVOR_BERRY_EFFECTS:
        if theirs in FLAVOR_BERRY_EFFECTS:
            return -3
        add_adjustment(rand, idx, 2, 206)
        return 0
    return -3


@njit
def expert_call(move, u_pok, rand, idx, move_first, copycat_beats):
    """
    pokeplatinum Expert_MirrorMove and Expert_Copycat, both read the target's last move.
    Metronome and Nature Power have no Expert check
    """
    move_id = move[_MOVE_ID]
    good = u_pok[_POK_LAST_MOVE_ID] in MIRROR_COPYCAT_GOOD_M
    if move_id == _MOVENAME_MIRROR_MOVE:
        if move_first and good:
            add_adjustment(rand, idx, 2, 128)
        elif not good:
            add_adjustment(rand, idx, -1, 176)
        return 0
    if move_id == _MOVENAME_COPYCAT:
        if move_first:
            if copycat_beats:
                add_adjustment(rand, idx, 2, 224)
                return 0
            if good:
                add_adjustment(rand, idx, 2, 128)
                return 0
        if not copycat_beats and not good:
            add_adjustment(rand, idx, -1, 176)
    return 0


@njit
def last_move_slot_arr(u_pok, my_last_move):
    """Index in u_pok of the target's last move's id (MOVE_ID_SLOTS), -1 for none, Struggle or a
    move it doesn't know"""
    if my_last_move <= 0:
        return -1
    for i in range(4):
        if u_pok[MOVE_ID_SLOTS[i]] == my_last_move:
            return MOVE_ID_SLOTS[i]
    return -1


@njit
def expert_substitute(ai_pok, u_pok, rand, idx, move_first, my_last_move):
    """
    pokeplatinum / Pokemow Expert_Substitute: Focus Punch 62.5% +1, then one 60.9% -1 roll per
    HP threshold the AI is at or under (90%, 70%, 50%). Moving first, 60.9% +1 when the target's
    last move tried something that didn't stick: a status move and it isn't statused, a
    confusion move and it isn't confused, Leech Seed and it isn't seeded
    """
    if knows_move(ai_pok, _MOVENAME_FOCUS_PUNCH):
        add_adjustment(rand, idx, 1, 160)
    hp_pct = (ai_pok[_POK_CURRENT_HP] * 100) // ai_pok[_POK_MAX_HP]
    if hp_pct <= 90:
        add_adjustment(rand, idx, -1, 156)
    if hp_pct <= 70:
        add_adjustment(rand, idx, -1, 156)
    if hp_pct <= 50:
        add_adjustment(rand, idx, -1, 156)
    if not move_first:
        return 0
    slot = last_move_slot_arr(u_pok, my_last_move)
    if slot < 0:
        return 0
    if (
        u_pok[slot + _MOVE_CATEGORY - _MOVE_ID] == _MOVECATEGORY_STATUS
        and u_pok[slot + _MOVE_STATUS - _MOVE_ID] != 0
        and u_pok[slot + _MOVE_TARGET - _MOVE_ID] in TARGET_OPP_SIDE
    ):
        if u_pok[_POK_STATUS] == 0:
            add_adjustment(rand, idx, 1, 156)
    elif my_last_move in CONFUSE_EFFECT_M:
        if not u_pok[_POK_VOL_STATUS] & _VOLSTATUS_CONFUSION:
            add_adjustment(rand, idx, 1, 156)
    elif my_last_move == _MOVENAME_LEECH_SEED:
        if not u_pok[_POK_VOL_STATUS] & _VOLSTATUS_LEECH_SEED:
            add_adjustment(rand, idx, 1, 156)
    return 0


@njit
def expert_charge_invulnerable(
    ai_pok, u_pok, effectiveness, rand, idx, weather, move_first, ai_know=0
):
    """
    pokeplatinum Expert_ChargeTurnWithInvuln, including its +1 when the target resists or is
    immune
    """
    if ai_pok[_POK_ITEM_ID] == _ITEMNAMES_POWER_HERB:
        return 2
    # The AI saw the target use Protect
    if seen_move(u_pok, ai_know, PROTECT_LIKE_M):
        return -1
    if effectiveness <= 0.5:
        return 1
    if (
        u_pok[_POK_STATUS] == _STATUS_TOXIC
        or u_pok[_POK_VOL_STATUS] & _VOLSTATUS_CURSE
        or u_pok[_POK_VOL_STATUS] & _VOLSTATUS_LEECH_SEED
    ):
        add_adjustment(rand, idx, 1, 176)
        return 0
    ai_types = (ai_pok[_POK_TYPE1], ai_pok[_POK_TYPE2])
    if weather == _WEATHER_SANDSTORM and (
        ai_types[0] in SAND_IMMUNE_TYPES or ai_types[1] in SAND_IMMUNE_TYPES
    ):
        add_adjustment(rand, idx, 1, 176)
        return 0
    if weather == _WEATHER_HAIL and _TYPES_ICE in ai_types:
        add_adjustment(rand, idx, 1, 176)
        return 0
    if move_first:
        add_adjustment(rand, idx, 1, 176)
    return 0


@njit
def expert_gravity(ai_pok, u_pok, rand, idx):
    """
    pokeplatinum Expert_Gravity: 75% chance of +1 against a Levitate or Flying target (Magnet
    Rise isn't in the engine), else 37.5% chance of +1 when the AI has at least 60% HP
    """
    if (
        u_pok[_POK_AB_ID] == _ABILITYNAMES_LEVITATE
        or u_pok[_POK_TYPE1] == _TYPES_FLYING
        or u_pok[_POK_TYPE2] == _TYPES_FLYING
    ):
        add_adjustment(rand, idx, 1, 192)
    elif (ai_pok[_POK_CURRENT_HP] * 100) // ai_pok[_POK_MAX_HP] >= 60:
        add_adjustment(rand, idx, 1, 96)
    return 0


@njit
def last_move_category(u_pok, my_last_move):
    """
    Category of the target's last move. No move yet (0) reads as Physical like pokeplatinum's
    move 0, and Struggle (-1) is Physical
    """
    if my_last_move <= 0:
        return _MOVECATEGORY_PHYSICAL
    for i in range(4):
        if u_pok[MOVE_ID_SLOTS[i]] == my_last_move:
            return u_pok[MOVE_CATEGORY_SLOTS[i]]
    return _MOVECATEGORY_PHYSICAL


@njit
def seen_high_crit(pok, ai_know):
    """If the AI saw pok use a high crit move that doesn't charge (pokeplatinum HIGH_CRITICAL effects)"""
    for i in range(4):
        slot = MOVE_ID_SLOTS[i]
        if (
            ai_know & AI_KNOWS_MOVE_BITS[i]
            and pok[slot + _MOVE_CRIT_RATIO - _MOVE_ID] > 1
            and pok[slot + _MOVE_CHARGE_RECHARGE - _MOVE_ID] == 0
        ):
            return True
    return False


@njit
def expert_field(move, ai_pok, u_pok, rand, idx, weather, my_last_move, ai_know, user_side, move_first):
    """
    pokeplatinum Expert checks for the side condition and weather moves and Brick Break. Mist,
    Safeguard and Sandstorm have none
    """
    move_id = move[_MOVE_ID]
    ai_hp_pct = (ai_pok[_POK_CURRENT_HP]*100) // ai_pok[_POK_MAX_HP]
    if move_id == _MOVENAME_REFLECT or move_id == _MOVENAME_LIGHT_SCREEN:
        if ai_hp_pct < 50:
            return -2
        if ai_hp_pct >= 90:
            add_adjustment(rand, idx, 1, 128)
        want = _MOVECATEGORY_PHYSICAL if move_id == _MOVENAME_REFLECT else _MOVECATEGORY_SPECIAL
        if last_move_category(u_pok, my_last_move) == want:
            add_adjustment(rand, idx, 1, 192)
        return 0
    if move_id == _MOVENAME_RAIN_DANCE:
        ai_ab = ai_pok[_POK_AB_ID]
        if not move_first and ai_ab == _ABILITYNAMES_SWIFT_SWIM:
            return 1
        if ai_hp_pct < 40:
            return -1
        if weather in RAIN_DANCE_GOOD_WEATHER:
            return 1
        if ai_ab == _ABILITYNAMES_RAIN_DISH:
            return 1
        if ai_ab == _ABILITYNAMES_HYDRATION and ai_pok[_POK_STATUS] != 0:
            return 1
        return 0
    if move_id == _MOVENAME_BRICK_BREAK:
        return 1 if user_side & SCREENS else 0
    if move_id == _MOVENAME_LUCKY_CHANT:
        if ai_hp_pct < 70:
            return -1
        if seen_high_crit(u_pok, ai_know):
            return 1
        add_adjustment(rand, idx, 1, 64)
        return 0
    if move_id in HAZARD_M:
        # 50% to skip every other modifier
        if random.getrandbits(1):
            return 0
        if knows_move(ai_pok, FORCE_SWITCH_M[0]) or knows_move(ai_pok, FORCE_SWITCH_M[1]):
            add_adjustment(rand, idx, 1, 192)
        return 1
    return 0


@njit
def max_switch_stage(pok):
    """Highest of the stages Expert Roar / Whirlwind and Baton Pass check"""
    best = pok[SWITCH_STAGES[0]]
    for stage in SWITCH_STAGES:
        best = max(best, pok[stage])
    return best


@njit
def expert_switch(move, ai_pok, u_pok, rand, idx, user_side, move_first):
    """pokeplatinum Expert_ForceSwitch, Expert_BatonPass and Expert_Pursuit, none for Teleport"""
    if move[_MOVE_FORCE_SWITCH]:
        # The target's turn count is TURNS_ACTIVE - 1, a 75% +2 that falls into the 50% +2
        if u_pok[_POK_TURNS_ACTIVE] - 1 > 3:
            add_adjustment(rand, idx, 2, 192)
            add_adjustment(rand, idx, 2, 128)
            return 0
        if user_side & TARGET_HAZARDS or max_switch_stage(u_pok) >= 3:
            add_adjustment(rand, idx, 2, 128)
            return 0
        return -3
    move_id = move[_MOVE_ID]
    if move_id == _MOVENAME_BATON_PASS:
        # Follows the script, its comment doesn't match it
        ai_hp_pct = (ai_pok[_POK_CURRENT_HP]*100) // ai_pok[_POK_MAX_HP]
        stage = max_switch_stage(ai_pok)
        if stage >= 3:
            if ai_hp_pct <= (60 if move_first else 70):
                add_adjustment(rand, idx, 2, 176)
            return 0
        if stage == 2:
            if move_first:
                return -2 if ai_hp_pct > 60 else 0
            return 0 if ai_hp_pct < 70 else -2
        return -2
    if move_id == _MOVENAME_PURSUIT:
        # TODO: +1 50% when the target knows U-turn, once it's in MoveDB
        if (
            ai_pok[_POK_TURNS_ACTIVE] == 1
            or u_pok[_POK_TYPE1] == _TYPES_GHOST or u_pok[_POK_TYPE1] == _TYPES_PSYCHIC
            or u_pok[_POK_TYPE2] == _TYPES_GHOST or u_pok[_POK_TYPE2] == _TYPES_PSYCHIC
        ):
            add_adjustment(rand, idx, 1, 128)
    return 0


@njit
def expert_explosion(ai_pok, u_pok, rand, idx, slower):
    """
    Pokemow Expert Selfdestruction: the second evasion -1 starts at +3 (pokeplatinum's code
    reads +4, Pokemow wins), and at 30% HP or less both +1 rolls apply
    """
    score = 0
    if u_pok[_POK_EVASION_STAT_STAGE] >= 1:
        score -= 1
        if u_pok[_POK_EVASION_STAT_STAGE] >= 3:
            add_adjustment(rand, idx, -1, 128)
    ai_hp_pct = (ai_pok[_POK_CURRENT_HP]*100) // ai_pok[_POK_MAX_HP]
    if ai_hp_pct >= 80 and not slower:
        add_adjustment(rand, idx, -3, 206)
        return score
    if ai_hp_pct > 50:
        add_adjustment(rand, idx, -1, 206)
        return score
    add_adjustment(rand, idx, 1, 128)
    if ai_hp_pct <= 30:
        add_adjustment(rand, idx, 1, 206)
    return score


@njit
def quick_claw_guess(ai_pok, u_pok):
    """
    The AI's guess of which Quick Claws activate this turn, independent of the real roll (Pokemow):
    bit 1 its own, bit 2 the target's. A Custap Berry in a pinch always counts (pokeplatinum
    CompareBattlerSpeed)
    """
    ai_claw = quick_claw(ai_pok) or custap_ready(ai_pok)
    u_claw = quick_claw(u_pok) or custap_ready(u_pok)
    return (1 if ai_claw else 0) | (2 if u_claw else 0)


@njit
def ai_speed_order(ai_pok, u_pok, weather, claw_guess):
    """
    1 if the AI moves first, -1 if the target does, 0 on a speed tie. pokeplatinum
    BattleSystem_CompareBattlerSpeed as the AI calls it (move priority ignored): a lone guessed
    Quick Claw goes first, then a lone Lagging Tail / Full Incense holder last (both: the slower
    first), then a lone Stall holder last, both Stalls the slower first, then speed
    """
    ai_s, u_s = check_speed(ai_pok, u_pok, weather)
    ai_claw = (claw_guess & 1) != 0
    u_claw = (claw_guess & 2) != 0
    if ai_claw != u_claw:
        return 1 if ai_claw else -1
    ai_lag = ai_pok[_ITEM_HOLD_EFFECT] == _HOLDEFFECT_PRIORITY_DOWN
    u_lag = u_pok[_ITEM_HOLD_EFFECT] == _HOLDEFFECT_PRIORITY_DOWN
    if not ai_claw and ai_lag != u_lag:
        return -1 if ai_lag else 1
    if not ai_claw and ai_lag:
        ai_s, u_s = u_s, ai_s
    elif not ai_claw:
        ai_stall = ai_pok[_POK_AB_ID] == _ABILITYNAMES_STALL
        u_stall = u_pok[_POK_AB_ID] == _ABILITYNAMES_STALL
        if ai_stall != u_stall:
            return -1 if ai_stall else 1
        if ai_stall:
            ai_s, u_s = u_s, ai_s
    if ai_s > u_s:
        return 1
    if ai_s < u_s:
        return -1
    return 0


@njit
def expert_flag(
    ai_pok, u_pok, move, turn, idx, rand, weather, my_last_move, effectiveness, t_dmg, ai_know=0,
    user_side=0, copycat_beats=False, claw_guess=0, speed_weather=-1, ai_side=0
):
    """
    It shows the incentives and disincentives for the best trainer ai out there,
    for ROM HACKS every trainer has it.
    ai_know is Field.AI_KNOWS, its move bits are the target's moves the AI saw.
    user_side is the target's Field.SIDE_COND. copycat_beats: the target's last move, used on
    itself, does more damage than any of the AI's moves. claw_guess: quick_claw_guess.
    weather is the field's, as the script reads it (pokeplatinum AICmd_LoadCurrentWeather ignores
    Cloud Nine); speed_weather is the one the speed compare sees, -1 for the same. ai_side is the
    AI's Field.SIDE_COND
    """
    if speed_weather < 0:
        speed_weather = weather
    # Check if move first (TODO add Trick room logic here)
    order = ai_speed_order(ai_pok, u_pok, speed_weather, claw_guess)
    if order > 0:
        move_first = True
    elif order == 0:
        move_first = random.getrandbits(1)
    else:
        move_first = False

    if move[_MOVE_ID] in NO_AI_CHECK_M:
        return 0
    if move[_MOVE_ID] in EXPLODE_MOVES:
        return expert_explosion(ai_pok, u_pok, rand, idx, order < 0)
    # Expert_OHKOMove: 25% chance of +1
    if move[_MOVE_OH_KO]:
        add_adjustment(rand, idx, 1, 64)
        return 0
    if move[_MOVE_ID] in EXPERT_SPECIFIC_M:
        return expert_moves(
            move, u_pok, ai_pok, effectiveness, rand, idx, t_dmg, my_last_move, move_first
        )
    if move[_MOVE_ID] in ITEM_EXPERT_M:
        return expert_items(move, ai_pok, u_pok, effectiveness, rand, idx, ai_side, user_side)
    if move[_MOVE_ID] in MISC_EXPERT_M:
        return expert_misc(move, ai_pok, u_pok, rand, idx, weather, move_first)
    if move[_MOVE_ID] in CALL_M:
        return expert_call(move, u_pok, rand, idx, move_first, copycat_beats)
    if move[_MOVE_ID] == _MOVENAME_GRAVITY:
        return expert_gravity(ai_pok, u_pok, rand, idx)
    if move[_MOVE_ID] == _MOVENAME_SUBSTITUTE:
        return expert_substitute(ai_pok, u_pok, rand, idx, move_first, my_last_move)
    # Pokemow Expert Blizzard, the roll ends the check either way
    if move[_MOVE_ID] == _MOVENAME_BLIZZARD:
        if effectiveness <= 0.5:
            add_adjustment(rand, idx, -3, 206)
            return 0
        return 1 if weather == _WEATHER_HAIL else 0
    if move[_MOVE_ID] == _MOVENAME_FEINT:
        return expert_feint(ai_pok, u_pok, rand, idx, ai_know)
    if move[_MOVE_FORCE_SWITCH] or move[_MOVE_ID] in SWITCH_EXPERT_M:
        return expert_switch(move, ai_pok, u_pok, rand, idx, user_side, move_first)
    if move[_MOVE_SIDE_CONDITION] or move[_MOVE_ID] in FIELD_EXPERT_M:
        return expert_field(
            move, ai_pok, u_pok, rand, idx, weather, my_last_move, ai_know, user_side, move_first
        )
    if move[_MOVE_CATEGORY] == _MOVECATEGORY_STATUS:
        hp_pct_ai = (ai_pok[_POK_CURRENT_HP]*100) // ai_pok[_POK_MAX_HP]
        hp_pct_u = (u_pok[_POK_CURRENT_HP]*100) // u_pok[_POK_MAX_HP]

        if move[_MOVE_STATUS] != 0:
            return expert_status(
                move, hp_pct_ai, hp_pct_u, rand,
                ai_pok, move_first, idx
            )
        has_boost = (move[_MOVE_BOOST_ATK]          #pylint: disable=too-many-boolean-expressions
            or move[_MOVE_BOOST_DEF]
            or move[_MOVE_BOOST_SPATK]
            or move[_MOVE_BOOST_SPDEF]
            or move[_MOVE_BOOST_SPEED]
            or move[_MOVE_BOOST_ACC]
            or move[_MOVE_BOOST_EV])
        if move[_MOVE_VOL_STATUS] and (move[_MOVE_TARGET] in TARGET_OPP_SIDE or not has_boost):
            return expert_vol_status(
                move, ai_pok, u_pok, turn,
                rand, idx, hp_pct_u, hp_pct_ai, move_first, ai_know
            )
        if has_boost:
            return expert_stat(
                move, ai_pok, rand, idx, hp_pct_ai,
                move_first, u_pok, hp_pct_u, my_last_move
            )

    # Moves Ignoring Accuracy (e.g. Aerial Ace, Shock Wave)
    if move[_MOVE_ACCURACY] == -1:  # -1 is how always hit moves is represented
        score = 0
        ai_acc = ai_pok[_POK_ACCURACY_STAT_STAGE]
        u_ev   = u_pok[_POK_EVASION_STAT_STAGE]
        if ai_acc <= -5 or u_ev >= 5:
            score += 1
        if ai_acc <= -3 or u_ev >= 3:
            add_adjustment(rand, idx, 1, 156)
        return score

    # Draining Moves (e.g. Absorb, Dream Eater)
    if move[_MOVE_DRAIN]:
        if move[_MOVE_ID] == _MOVENAME_DREAM_EATER:
            if effectiveness < 1.0:
                return -1
            if u_pok[_POK_STATUS] == _STATUS_SLEEP:
                add_adjustment(rand, idx, 3, 205)
            return 0
        if effectiveness < 1.0:
            add_adjustment(rand, idx, -3, 206)
        return 0

    # High Critical Hit Rate (e.g. Karate Chop, Razor Leaf, Air Cutter)
    if move[_MOVE_CRIT_RATIO] > 1 and move[_MOVE_CHARGE_RECHARGE] == 0:
        if effectiveness <= 0.5:
            return 0
        if effectiveness >= 2:
            add_adjustment(rand, idx, 1, 128)
        else:
            add_adjustment(rand, idx, 1, 64)
        return 0

    # Speed-Lowering Attacks, only these exact moves (Icy Wind, Rock Tomb, Mud Shot)
    if move[_MOVE_ID] in SPEED_DOWN_ON_HIT:
        if effectiveness <= 0.5:
            return 0
        if move_first:
            return -3
        add_adjustment(rand, idx, 2, 186)
        return 0

    # Expert_CloseCombat / Expert_Overheat: -1 if resisted, slower at 80% HP or less, or faster
    # at 60% or less
    if move[_MOVE_ID] in SELF_DROP_HP_M:
        if effectiveness <= 0.5:
            return -1
        hp_pct_ai = (ai_pok[_POK_CURRENT_HP]*100) // ai_pok[_POK_MAX_HP]
        return -1 if hp_pct_ai <= (60 if move_first else 80) else 0

    # Expert_Superpower: -1 if resisted, Attack below 0, slower at 60% HP or more, or faster
    # above 40%
    if move[_MOVE_ID] == _MOVENAME_SUPERPOWER:
        if effectiveness <= 0.5 or ai_pok[_POK_ATTACK_STAT_STAGE] < 0:
            return -1
        hp_pct_ai = (ai_pok[_POK_CURRENT_HP]*100) // ai_pok[_POK_MAX_HP]
        if move_first:
            return -1 if hp_pct_ai > 40 else 0
        return -1 if hp_pct_ai >= 60 else 0

    # Expert_HammerArm: -1 if resisted, +1 if slower
    if move[_MOVE_ID] == _MOVENAME_HAMMER_ARM:
        if effectiveness <= 0.5:
            return -1
        return 0 if move_first else 1

    # Recoil Moves (e.g. Take Down, Double-Edge)
    if move[_MOVE_RECOIL]:
        if effectiveness <= 0.5:
            return 0
        if ai_pok[_POK_AB_ID] in RECOIL_AB:
            return 1
        return 0

    # Charge Turn Moves With Invulnerability (Bounce, Dig)
    if move[_MOVE_ID] in CHARGE_INVULNERABLE_M:
        return expert_charge_invulnerable(
            ai_pok, u_pok, effectiveness, rand, idx, weather, move_first, ai_know
        )

    # Binding Moves (Wrap, Bind, Clamp, Fire Spin), Whirlpool has its own effect and no check
    if move[_MOVE_VOL_STATUS] & _VOLSTATUS_PARTIALLY_TRAPPED and move[_MOVE_ID] != _MOVENAME_WHIRLPOOL:
        if (
            u_pok[_POK_STATUS] == _STATUS_TOXIC
            or u_pok[_POK_VOL_STATUS] & (_VOLSTATUS_CURSE | _VOLSTATUS_ATTRACT | _VOLSTATUS_PERISH_SONG)
        ):
            add_adjustment(rand, idx, 1, 128)
        return 0

    """
    TODO:
    --------------Specific Moves---------------
    Selfdestruct, Explosion, Memento
    Healing Wish, Lunar Dance
    Mirror Move
    Dragon Dance
    Acupressure
    Vital Throw
    Haze
    Conversion
    Rest
    Toxic
    Spit Up
    Super Fang
    Metal Burst
    Pain Split
    Nightmare
    Lock On, Mind Reader
    Sleep Talk
    Reversal, Flail
    Heal Bell, Aromatherapy
    Thief, Covet
    Detect
    Spikes
    Miracle Eye
    Sunny Day
    Hail
    Gravity
    Tailwind
    Belly Drum
    Psych Up
    Facade
    Focus Punch
    Smelling Salt
    Wake-Up Slap
    Trick, Switcheroo
    Superpower
    Magic Coat
    Endeavor
    Imprison
    Snatch
    Hammer Arm
    Brine
    Pluck
    U-turn
    Close Combat
    Payback
    Assurance
    Embargo
    Fling
    Psycho Shift
    Trump Card
    Heal Block
    Wring Out, Crush Grip
    Power Trick
    Gastro Acid
    Me First
    Copycat
    Power Swap
    Guard Swap
    Punishment
    Last Resort
    Sucker Punch
    Heart Swap
    Magnet Rise
    Defog
    Trick Room
    Blizzard
    Captivate

    --------------Effect Moves-----------------
    Switch-Forcing Moves (Roar, Whirlwind)
    Recovery Moves (e.g., Swallow)
    Charge Turn Moves Without Invulnerability (Razor Wind, Skull Bash, Sky Attack, Solar Beam/Blade)
    Charge Turn Moves With Invulnerability (Fly, Dive, Dig, Bounce)
    Recoil Moves (e.g. Submission, Flare Blitz, Double-Edge)
    Recharge-Turn Attacks (e.g. Hyper Beam, Giga Impact)
    Moves Which Change the User's Ability (Role Play, Skill Swap)
    Moves Which Decrease in Power With Less User HP (Water Spout, Eruption)
    Double-Power Negative-Priority Moves (Avalanche, Revenge)
    Moves Reducing the User's SpAttack by 2 (e.g., Overheat, Draco Meteor)

    --------------Mirror Move------------------
    Sleep Powder
    Lovely Kiss
    Spore
    Hypnosis
    Sing
    Grass Whistle
    Shadow Punch
    Sand Attack
    Smoke Screen
    Toxic
    Guillotine
    Horn Drill
    Fissure
    Sheer Cold
    Cross Chop
    Aeroblast
    Confuse Ray
    Sweet Kiss
    Screech
    Cotton Spore
    Scary Face
    Fake Tears
    Metal Sound
    Thunder Wave
    Glare
    Poison Powder
    Shadow Ball
    Dynamic Punch
    Hyper Beam
    Extreme Speed
    Thief
    Covet
    Attract
    Swagger
    Torment
    Flatter
    Trick
    Superpower
    Skill Swap
    Psycho Shift
    Power Swap
    Guard Swap
    Sucker Punch
    Heart Swap
    Switcheroo
    Captivate
    """
    return 0


@njit
def on_damaging_turn(move):
    """pokeplatinum MoveIsOnDamagingTurn while the AI scores: false for a charge move and Fire Fang"""
    return move[_MOVE_CHARGE_RECHARGE] <= 0 and move[_MOVE_ID] != _MOVENAME_FIRE_FANG


@njit
def party_effectiveness(move_type, attacker, defender, gravity=False, damaging_turn=True):
    """
    pokeplatinum BattleSystem_CalcEffectiveness, the type check the AI uses for its bench: Levitate
    takes Ground moves unless the attacker has Mold Breaker or Gravity is up, Gravity grounds Flying
    types, Scrappy hits Ghosts and Wonder Guard (unless Mold Breaker) takes every move that isn't
    super effective unless damaging_turn is False (on_damaging_turn). Iron Ball works like Gravity
    for its holder. No Foresight or Ingrain. Returns (eff, den) like get_type_effectiveness
    """
    mold_breaker = attacker[_POK_AB_ID] == _ABILITYNAMES_MOLD_BREAKER
    def_ab = defender[_POK_AB_ID]
    grounded = gravity or grounded_by_item(defender)
    if (
        move_type == _TYPES_GROUND and def_ab == _ABILITYNAMES_LEVITATE
        and not mold_breaker and not grounded
    ):
        return 0, 1
    t1, t2 = gravity_types(move_type, defender[_POK_TYPE1], defender[_POK_TYPE2], grounded)
    if is_scrappy(attacker) and move_type in FORESIGHT_TYPES:
        if t1 == _TYPES_GHOST:
            t1 = 0
        if t2 == _TYPES_GHOST:
            t2 = 0
    eff, den = get_type_effectiveness(move_type, t1, t2)
    if (
        def_ab == _ABILITYNAMES_WONDER_GUARD and not mold_breaker
        and damaging_turn and eff < 2 * den
    ):
        return 0, 1
    return eff, den


# Dual non-immunity glitch: (move type, immune defending type, weak defending type) where the immune
# row comes first in pokeplatinum's sTypeMatchupMultipliers, so the weakness flag set after it stays
DUAL_NON_IMMUNITY = (
    (_TYPES_ELECTRIC, _TYPES_GROUND, _TYPES_FLYING),
    (_TYPES_GROUND, _TYPES_FLYING, _TYPES_ROCK),
    (_TYPES_GROUND, _TYPES_FLYING, _TYPES_STEEL),
    (_TYPES_GHOST, _TYPES_NORMAL, _TYPES_PSYCHIC),
    (_TYPES_GHOST, _TYPES_NORMAL, _TYPES_GHOST),
)


@njit
def party_super_effective(move_type, attacker, defender, gravity=False, damaging_turn=True):
    """
    The super-effective flag of party_effectiveness, with the dual non-immunity glitch (Pokemow
    switching page): Electric into Gligar, Ground into Aerodactyl / Skarmory and Ghost into
    Girafarig count as super effective though the immunity stays. Levitate skips the type chart,
    so it has no glitch
    """
    eff, den = party_effectiveness(move_type, attacker, defender, gravity, damaging_turn)
    if eff // den >= 2:
        return True
    if (
        move_type == _TYPES_GROUND and defender[_POK_AB_ID] == _ABILITYNAMES_LEVITATE
        and attacker[_POK_AB_ID] != _ABILITYNAMES_MOLD_BREAKER and not gravity
        and not grounded_by_item(defender)
    ):
        return False
    t1 = defender[_POK_TYPE1]
    t2 = defender[_POK_TYPE2]
    for atk_type, immune, weak in DUAL_NON_IMMUNITY:
        if move_type == atk_type and (
            (t1 == immune and t2 == weak) or (t1 == weak and t2 == immune)
        ):
            return True
    return False


@njit
def check_super_ef_move_pty(ai_party, user_pok, opp_active, gravity=False, damaging_only=False):
    """
    Check if there's any pokemon with super effective move. damaging_only skips status moves and
    empty slots (Pokemow: the Wonder Guard withdraw counts any move, the ineffective-moves one only
    damaging moves)
    """
    buf = np.zeros(6,dtype=np.int16)
    n = 0

    alive = np.where(ai_party[_POK_CURRENT_HP::POK_LEN] > 0)[0]
    if len(alive) <= 1:
        return buf[:0]

    for idx in alive:
        if idx == opp_active:
            continue
        pok = ai_party[(POK_LEN * idx):(POK_LEN * (idx + 1))]
        moves = pok[_POK_MOVE1_ID:_POK_ITEM_ID].reshape(4, -1)
        for mv in moves:
            if damaging_only and (mv[_MOVE_ID] == 0 or mv[_MOVE_CATEGORY] == _MOVECATEGORY_STATUS):
                continue
            if party_super_effective(
                normalized_type(pok, mv), pok, user_pok, gravity, on_damaging_turn(mv)
            ):
                buf[n] = idx
                n += 1
                break
    return buf[:n]


@njit
def check_any_damaging_move_pty(ai_party, user_pok, opp_active, gravity=False):
    """
    Check party for a damaging move that affects the target, status moves and empty slots don't
    count (Pokemow ineffective-moves withdraw)
    """
    buf = np.zeros(6,dtype=np.int16)
    n = 0

    alive = np.where(ai_party[_POK_CURRENT_HP::POK_LEN] > 0)[0]
    if len(alive) <= 1:
        return buf[:0]

    for idx in alive:
        if idx == opp_active:
            continue
        pok = ai_party[(POK_LEN * idx):(POK_LEN * (idx + 1))]
        moves = pok[_POK_MOVE1_ID:_POK_ITEM_ID].reshape(4, -1)
        for mv in moves:
            if mv[_MOVE_ID] == 0 or mv[_MOVE_CATEGORY] == _MOVECATEGORY_STATUS:
                continue
            eff, den = party_effectiveness(
                normalized_type(pok, mv), pok, user_pok, gravity, on_damaging_turn(mv)
            )
            if eff / den != 0:
                buf[n] = idx
                n += 1
                break
    return buf[:n]


@njit
def check_absorb_abi_pty(ai_party, my_last_move, opp_active):
    """
    Check if party has any pokemon with ability that absorbs types
    """
    buf = np.zeros(6,dtype=np.int16)
    n = 0

    alive = np.where(ai_party[_POK_CURRENT_HP::POK_LEN] > 0)[0]
    if len(alive) <= 1:
        return buf[:0]

    for idx in alive:
        if idx == opp_active:
            continue
        pok = ai_party[(POK_LEN * idx):(POK_LEN * (idx + 1))]
        pok_ab = pok[_POK_AB_ID]
        if pok_ab not in ABSORB_ABI:
            continue
        if my_last_move in FIRE_MOVES and pok_ab == _ABILITYNAMES_FLASH_FIRE:
            buf[n] = idx
            n += 1
        elif my_last_move in WATER_MOVES and pok_ab == _ABILITYNAMES_WATER_ABSORB:
            buf[n] = idx
            n += 1
        elif my_last_move in ELECTRIC_MOVES and pok_ab == _ABILITYNAMES_VOLT_ABSORB:
            buf[n] = idx
            n += 1
    return buf[:n]


@njit
def check_immunity_pty(ai_party, user_pok, last_move_type, opp_active, gravity=False):
    """
    Check if there's any pokemon with super effective move
    """
    buf = np.zeros(6,dtype=np.int16)
    n = 0
    # Gen IV BattleSystem_CalcEffectiveness gives Struggle no effectiveness at all
    if last_move_type == _TYPES_TYPELESS:
        return buf[:0]

    alive = np.where(ai_party[_POK_CURRENT_HP::POK_LEN] > 0)[0]
    if len(alive) <= 1:
        return buf[:0]

    for idx in alive:
        if idx == opp_active:
            continue
        pok = ai_party[(POK_LEN * idx):(POK_LEN * (idx + 1))]
        ef, de = party_effectiveness(last_move_type, user_pok, pok, gravity)
        if ef/de == 0:
            moves = pok[_POK_MOVE1_ID:_POK_ITEM_ID].reshape(4, -1)
            for mv in moves:
                if party_super_effective(
                    normalized_type(pok, mv), pok, user_pok, gravity, on_damaging_turn(mv)
                ):
                    buf[n] = idx
                    n += 1
                    break
            if n == 1:
                break

    return buf[:n]


@njit
def check_resistance_pty(ai_party, user_pok, last_move_type, opp_active, gravity=False):
    """
    Check if there's any pokemon with super effective move
    """
    buf = np.zeros(6,dtype=np.int16)
    n = 0
    # Gen IV BattleSystem_CalcEffectiveness gives Struggle no effectiveness at all
    if last_move_type == _TYPES_TYPELESS:
        return buf[:0]

    alive = np.where(ai_party[_POK_CURRENT_HP::POK_LEN] > 0)[0]
    if len(alive) <= 1:
        return buf[:0]

    for idx in alive:
        if idx == opp_active:
            continue
        pok = ai_party[(POK_LEN * idx):(POK_LEN * (idx + 1))]
        ef, de = party_effectiveness(last_move_type, user_pok, pok, gravity)
        if 0 < ef/de < 1:
            moves = pok[_POK_MOVE1_ID:_POK_ITEM_ID].reshape(4, -1)
            for mv in moves:
                if party_super_effective(
                    normalized_type(pok, mv), pok, user_pok, gravity, on_damaging_turn(mv)
                ):
                    buf[n] = idx
                    n += 1
                    break
            if n == 1:
                break

    return buf[:n]
