"""Helpers that are only needed in the engine directory"""
import random
import numpy as np
from Utils.jit import njit
from Utils.helper import get_type_effectiveness
from Engine.speed import check_speed, slow_start_active, quick_claw, pinch_hp, custap_ready, goes_first
from Engine.status_calc import  freeze, paralysis, sleep_blocked, SLOT_MASK, TURNS_2_5
from Engine.status_calc import (
    apply_status, infatuate, cure_status, ability_blocks_status, ability_forbids_status,
    stat_drop_blocked
)
from Engine.damage_calc import (
    calculate_damage_confusion, apply_stat_stage, MULTIPLIERS, matchup_types, screen_damage,
    item_power, item_attack, item_defense, unaware_stages, ab_modify_def, rivalry_power, crit_multiplier,
    AIRBORNE_MOVES, HITS_AIRBORNE, HITS_UNDERGROUND, DOUBLE_ATK_AB, is_scrappy,
    UNDERGROUND_MOVES, UNDERWATER_MOVES, HITS_UNDERWATER,
    METRONOME_MOVE_SHIFT, METRONOME_COUNT_MASK, life_orb_damage
)
from Engine.ability_helper import (
    ignorable_ability, levitates, reveal_ability, effective_weather, normalized_type,
    grounded_by_item, slot_move_type, forecast_actives, magnet_risen,
)
from Models.idx_const import (
    ITEM_LEN, POK_LEN, MOVE_STRIDE, OFFSET_MOVE, SIDE_TOXIC_SPIKES, AB_LEN, SIDE_SPIKES
)
from Models.helper import TARGET_SELF_SIDE, Target
from Models.item import ITEM_TABLE, refresh_item, embargoed
from Models.ability import ABILITY_TABLE
from Models.move import METRONOME_POOL, METRONOME_FORBIDDEN, KINGS_ROCK_MOVES, MOVE_TABLE
from Models.constants import (
    _MOVENAME_SWALLOW, _MOVENAME_WISH, _POK_STOCKPILE, _MOVENAME_SPIT_UP,
    _TYPES_NORMAL,
    _MOVENAME_SUCKER_PUNCH, _MOVENAME_FOCUS_PUNCH, _MOVENAME_PAYBACK, _MOVENAME_REVENGE,
    _MOVENAME_AVALANCHE, _VOLSTATUS2_DAMAGED_BY_MOVE,
    _MOVE_SLEEP_USABLE, _FLAGS_NO_SLEEP_TALK, _MOVE_CHARGE_RECHARGE, _ABILITYNAMES_VITAL_SPIRIT,
    _VOLSTATUS_NIGHTMARE, _MOVENAME_DREAM_EATER, _MOVENAME_REST, _MOVENAME_NIGHTMARE,
    _MOVENAME_PSYCHO_SHIFT, _MOVENAME_HEAL_BELL,
    _POK_STATUS, _STATUS_PARALYSIS, _POK_SPEED_STAT_STAGE, _POK_AB_WHEN,
    _WEATHER_SUN, _MOVENAME_FAKE_OUT, _MOVENAME_THUNDER, _MOVENAME_LAST_RESORT, _POK_LAST_RESORT,
    _SEC_BOOST_ACC, _SEC_BOOST_ATK, _SEC_BOOST_SPEED, _SEC_BOOST_EV, _VOLSTATUS_FLINCH,
    _TERRAIN_PLAIN, _TERRAIN_SAND, _TERRAIN_GRASS, _TERRAIN_PUDDLE, _TERRAIN_MOUNTAIN, _TERRAIN_CAVE,
    _TERRAIN_SNOW, _TERRAIN_ICE, _TERRAIN_WATER, _TERRAIN_GREAT_MARSH, _TERRAIN_BRIDGE,
    _POK_AB_ID, _MOVE_PRIORITY, _MOVE_ID, _MOVEOUTCOME_HIT, _MOVEOUTCOME_INVULNERABLE,
    _MOVEOUTCOME_MISS, _TYPES_ROCK, _TYPES_GROUND, _TYPES_STEEL, _TYPES_FIRE, _TYPES_ICE,
    _MOVENAME_EXPLOSION, _MOVENAME_SELFDESTRUCT, _MOVENAME_STRUGGLE, _WEATHER_RAIN,
    _WEATHER_SANDSTORM, _WEATHER_HAIL, _MOVE_TARGET, _MOVE_CATEGORY, _MOVE_OH_KO, _MOVE_ACCURACY,
    _MOVE_TYPE, _ABILITYNAMES_DAMP, _ABILITYNAMES_HUSTLE, _ABILITYNAMES_SAND_VEIL,
    _ABILITYNAMES_SOUNDPROOF, _ABILITYNAMES_INNER_FOCUS, _ABILITYNAMES_INTIMIDATE,
    _ABILITYNAMES_SOLAR_POWER, _ABILITYNAMES_MAGIC_GUARD, _ABILITYNAMES_STEADFAST,
    _ABILITYNAMES_POISON_POINT, _ABILITYNAMES_RAIN_DISH, _ABILITYNAMES_SPEED_BOOST,
    _MOVECATEGORY_PHYSICAL, _FLAGS_SOUND, _FLAGS_DEFROST, _ABILITYACTIVATION_ON_TRY_MOVE, _ABILITYACTIVATION_ON_SWITCH_IN,
    _POK_TYPE1, _POK_TYPE2, _POK_ACCURACY_STAT_STAGE, _POK_EVASION_STAT_STAGE, _POK_ATTACK_STAT_STAGE,
    _POK_VOL_STATUS, _POK_BADLY_POISON, _POK_TURNS, _POK_MAX_HP, _POK_SLEEP_COUNTER, _POK_CURRENT_HP,
    _POK_DEFENSE_STAT_STAGE, _POK_SPECIAL_ATTACK_STAT_STAGE, _SEC_CHANCE, _POK_TURNS_ACTIVE,
    _SEC_CHANCE2, _MOVE_IGNORE_IMMUNITY, _POK_SEMI_INV_MOVE, _POK_VOL_STATUS2, _FLAGS_GRAVITY,
    _FIELD_GRAVITY_TURNS,
    _FIELD_MY_POK, _FIELD_OPP_POK, _FIELD_WEATHER, _FIELD_TURN, _STATUS_TOXIC, _STATUS_POISON,
    _STATUS_SLEEP, _STATUS_FREEZE, _VOLSTATUS_CONFUSION, _POTIONS_FULL_HEAL,
    _POTIONS_FULL_RESTORE, _POTIONS_HYPER_POTION, _POTIONS_POTION, _POTIONS_SUPER_POTION,
    _POTIONS_X_DEFEND, _POTIONS_X_SPECIAL, _POTIONS_X_SPEED,
    _ABILITYNAMES_WATER_ABSORB, _MOVE_DAMAGE, _DAMAGESOURCES_COUNTER, _DAMAGESOURCES_MAGIC_COAT,
    _DAMAGESOURCES_METAL_BURST, _DAMAGESOURCES_ENDEAVOR,
    _TYPES_WATER, _ABILITYACTIVATION_ON_CRITICAL, _MOVE_DRAIN, _POK_DMG_TAKEN,
    _POK_CHARGE_RECHARGE, _POK_LOCKED_MOVE, _ITEM_HOLD_EFFECT,
    _ITEM_ID, _ITEM_EFFECT_PARAM, _MOVENAME_BIDE, _VOLSTATUS_BIDE, _VOLSTATUS_FOCUS_ENERGY, _MOVE_CRIT_RATIO,
    _HOLDEFFECT_HP_RESTORE, _HOLDEFFECT_HP_PCT_RESTORE, _POK_CONFUSION_COUNTER, _ITEM_WHEN,
    _HOLDEFFECT_WEAKEN_SE, _HOLDEFFECT_WEAKEN_NORMAL, _ITEM_EFFECT_TYPE, _HOLDEFFECT_LEECH_BOOST,
    _ITEMACTIVATION_ON_RECEIVE_DAMAGE, _MOVE_WILL_CRIT,
    _ABILITYNAMES_SIMPLE, _POK_LEVEL, _POK_ATTACK, _POK_DEFENSE, _STATUS_BURN,
    _MOVEOUTCOME_SEMI_INVULNERABLE, _VOLSTATUS_SEMI_INVULNERABLE, _VOLSTATUS_HURT_THIS_TURN,
    _POK_CONSEC_COUNT, _ABILITYNAMES_GUTS, _MOVE_RECOIL, _ABILITYNAMES_FLOWER_GIFT,
    _ITEM_NATURAL_GIFT_POWER, _ITEM_NATURAL_GIFT_TYPE, _POK_CONSUMED_ITEM, _MOVE_POWER,
    _MOVEOUTCOME_PROTECTED, _VOLSTATUS_PROTECT, _VOLSTATUS_ENDURE, _VOLSTATUS_FORESIGHT,
    _VOLSTATUS_DESTINY_BOND, _VOLSTATUS_ATTRACT, _FLAGS_PROTECT, _POK_PROTECT_COUNT,
    _POK_YAWN_TURNS, _MOVENAME_PROTECT, _VOLSTATUS_UPROAR, _POK_UPROAR_TURNS, _VOLSTATUS_TAUNT,
    _VOLSTATUS_ENCORE, _VOLSTATUS_DISABLE, _VOLSTATUS_PARTIALLY_TRAPPED, _POK_TRAP_TURNS,
    _POK_TAUNT_TURNS, _POK_ENCORE_TURNS, _POK_DISABLE_TURNS, _POK_LAST_MOVE_ID, _MOVECATEGORY_STATUS,
    _FIELD_MY_SIDE_COND, _FIELD_OPP_SIDE_COND, _SIDECONDITION_LUCKY_CHANT, _SIDECONDITION_MIST,
    _SIDECONDITION_SAFEGUARD, _SIDECONDITION_TOXIC_SPIKES, _SIDECONDITION_STEALTH_ROCK,
    _TYPES_FLYING, _TYPES_POISON, _POK_BASE_AB_ID, _POK_ITEM_KNOCKED_OFF,
    _POK_PERISH_TURNS,
    _VOLSTATUS_PERISH_SONG, _ABILITYNAMES_INSOMNIA, _ABILITYNAMES_STICKY_HOLD, _ABILITYNAMES_MULTITYPE,
    _ABILITYNAMES_TRUANT, _ABILITYNAMES_MOLD_BREAKER, _MOVENAME_SYNTHESIS, _POK_CALLED_MOVE,
    _POK_MIRROR_MOVE, _FIELD_LAST_MOVE, _FIELD_TERRAIN, _MOVENAME_METRONOME, _MOVENAME_MIRROR_MOVE,
    _MOVENAME_COPYCAT, _MOVENAME_NATURE_POWER, _MOVENAME_SLEEP_TALK, _MOVENAME_ENCORE,
    _MOVENAME_EARTHQUAKE, _MOVENAME_SEED_BOMB, _MOVENAME_ROCK_SLIDE, _MOVENAME_BLIZZARD,
    _MOVENAME_HYDRO_PUMP, _MOVENAME_ICE_BEAM, _MOVENAME_TRI_ATTACK, _MOVENAME_MUD_BOMB,
    _MOVENAME_AIR_SLASH, _TERRAIN_SPECIAL, _FLAGS_MIRROR, _TYPES_TYPELESS,
    _ABILITYNAMES_STURDY, _ABILITYNAMES_NO_GUARD, _ABILITYNAMES_COMPOUND_EYES,
    _ABILITYNAMES_SNOW_CLOAK, _ABILITYNAMES_TANGLED_FEET, _ABILITYNAMES_SUPER_LUCK,
    _ABILITYNAMES_SERENE_GRACE, _ABILITYNAMES_SHIELD_DUST, _ABILITYNAMES_UNAWARE,
    _HOLDEFFECT_ACC_REDUCE, _HOLDEFFECT_CRITRATE_UP, _ABILITYNAMES_STATIC, _ABILITYNAMES_FLAME_BODY,
    _ABILITYNAMES_CUTE_CHARM, _ABILITYNAMES_EFFECT_SPORE, _ABILITYNAMES_ROUGH_SKIN,
    _ABILITYNAMES_AFTERMATH, _FLAGS_CONTACT, _ABILITYACTIVATION_ON_CONTACT,
    _HOLDEFFECT_PSN_RESTORE, _HOLDEFFECT_SLP_RESTORE, _HOLDEFFECT_STATUS_RESTORE,
    _HOLDEFFECT_HEAL_INFATUATION, _ABILITYNAMES_EARLY_BIRD, _ABILITYNAMES_NATURAL_CURE,
    _ABILITYNAMES_SHED_SKIN, _VOLSTATUS2_FLASH_FIRE,
    _ABILITYNAMES_VOLT_ABSORB, _ABILITYNAMES_MOTOR_DRIVE, _ABILITYNAMES_DRY_SKIN,
    _ABILITYNAMES_FLASH_FIRE, _ABILITYNAMES_WONDER_GUARD, _TYPES_ELECTRIC, _MOVENAME_FIRE_FANG,
    _MOVENAME_WILL_O_WISP, _MOVE_PP, _POK_SPECIAL_DEFENSE, _POK_SPECIAL_DEFENSE_STAT_STAGE,
    _ABILITYNAMES_TRACE, _ABILITYNAMES_DOWNLOAD, _ABILITYNAMES_PRESSURE, _ABILITYNAMES_FORECAST,
    _ABILITYNAMES_OWN_TEMPO, _ABILITYNAMES_OBLIVIOUS, _POK_AB_KNOWN,
    _ABILITYNAMES_ANTICIPATION, _ABILITYNAMES_FOREWARN,
    _ABILITYNAMES_STALL, _ABILITYNAMES_UNBURDEN, _VOLSTATUS2_CAN_UNBURDEN, _ABILITYNAMES_SLOW_START,
    _ABILITYNAMES_DRIZZLE, _ABILITYNAMES_DROUGHT, _ABILITYNAMES_SAND_STREAM,
    _ABILITYNAMES_SNOW_WARNING, _ABILITYNAMES_ICE_BODY, _FIELD_WEATHER_DURATION,
    _HOLDEFFECT_SWITCH, _VOLSTATUS_INGRAIN, _ABILITYNAMES_SHADOW_TAG, _ABILITYNAMES_MAGNET_PULL,
    _ABILITYNAMES_ARENA_TRAP, _HOLDEFFECT_MAYBE_ENDURE, _HOLDEFFECT_BOOST_REPEATED,
    _POK_METRONOME_COUNT, _ABILITYNAMES_LIQUID_OOZE, _HOLDEFFECT_CHARGE_SKIP,
    _POK_SUB_HP, _VOLSTATUS2_SUBSTITUTE, _FLAGS_BYPASS_SUB, _MOVENAME_CURSE, _TYPES_GHOST,
    _MOVENAME_SWAGGER, _MOVENAME_FLATTER, _VOLSTATUS_YAWN, _MOVE_STATUS, _MOVE_VOL_STATUS,
    _MOVENAME_BELLY_DRUM, _MOVENAME_ACUPRESSURE, _MOVENAME_CAPTIVATE, _POK_GENDER,
    _MOVENAME_POWER_SWAP, _MOVENAME_GUARD_SWAP, _VOLSTATUS2_POWER_TRICK,
    _GENDER_GENDERLESS,
    _HOLDEFFECT_CHANSEY_CRITRATE_UP, _HOLDEFFECT_FARFETCHD_CRITRATE_UP, _ITEMNAMES_GRISEOUS_ORB,
    _POK_ID, _HOLDEFFECT_PRIORITY_DOWN, _HOLDEFFECT_ACCURACY_UP, _HOLDEFFECT_ACCURACY_UP_SLOWER,
    _HOLDEFFECT_SOMETIMES_FLINCH, _ITEM_EFFECT_PARAM, _HOLDEFFECT_ENDURE,
    _HOLDEFFECT_STATDOWN_RESTORE, _HOLDEFFECT_DMG_USER_CONTACT_XFR, _HOLDEFFECT_HP_RESTORE_ON_DMG,
    _HOLDEFFECT_HP_DRAIN_ON_ATK, _MOVENAME_KNOCK_OFF,
    _HOLDEFFECT_PRZ_RESTORE, _HOLDEFFECT_BRN_RESTORE, _HOLDEFFECT_FRZ_RESTORE,
    _HOLDEFFECT_CONFUSE_RESTORE, _HOLDEFFECT_PP_RESTORE, _HOLDEFFECT_HP_RESTORE_SPICY,
    _HOLDEFFECT_HP_RESTORE_DRY, _HOLDEFFECT_HP_RESTORE_SWEET, _HOLDEFFECT_HP_RESTORE_BITTER,
    _HOLDEFFECT_HP_RESTORE_SOUR, _HOLDEFFECT_PINCH_ATK_UP, _HOLDEFFECT_PINCH_DEF_UP,
    _HOLDEFFECT_PINCH_SPEED_UP, _HOLDEFFECT_PINCH_SPATK_UP, _HOLDEFFECT_PINCH_SPDEF_UP,
    _HOLDEFFECT_PINCH_CRITRATE_UP, _HOLDEFFECT_PINCH_RANDOM_UP, _HOLDEFFECT_PINCH_ACC_UP,
    _HOLDEFFECT_HP_RESTORE_SE, _HOLDEFFECT_RECOIL_PHYSICAL, _HOLDEFFECT_RECOIL_SPECIAL,
    _POK_NATURE_MINUS, _VOLSTATUS2_MICLE, _MOVE_PP_UP, _MOVECATEGORY_SPECIAL,
    _POK_CHOICE_LOCK, _HOLDEFFECT_CHOICE_ATK, _HOLDEFFECT_CHOICE_SPATK, _HOLDEFFECT_CHOICE_SPEED,
    _POK_EMBARGO_TURNS, _VOLSTATUS2_EMBARGO, _ITEM_FLING_POWER, _ITEM_FLING_STATUS,
    _ITEM_FLING_VOLATILE, _ITEM_ITEM_TYPE, _ITEMTYPE_BERRY, _SEC_STATUS, _SEC_VOL_STATUS, _SEC_TARGET,
    _POK_RAMPAGE_TURNS, _VOLSTATUS_HEAL_BLOCK, _MOVENAME_RECOVER, _MOVENAME_SOFT_BOILED,
    _MOVENAME_MILK_DRINK, _MOVENAME_SLACK_OFF, _MOVENAME_HEAL_ORDER, _MOVENAME_ROOST,
    _MOVENAME_MOONLIGHT, _MOVENAME_MORNING_SUN, _POK_HEAL_BLOCK_TURNS,
    _SIDECONDITION_SPIKES, _POK_MAGNET_RISE_TURNS, _VOLSTATUS2_MAGNET_RISE, _ABILITYNAMES_LEVITATE,
    _MOVENAME_MAGNET_RISE, _VOLSTATUS2_GRUDGE, _MOVENAME_HEALING_WISH, _SIDECONDITION_HEALING_WISH,
    _MOVENAME_MEMENTO, _MOVENAME_GRUDGE,
)
from DataBase.PkDB import PokemonName


SANDSTORM_IM = (_TYPES_ROCK, _TYPES_GROUND, _TYPES_STEEL)
CHANSEY = PokemonName.CHANSEY
FARFETCHD = PokemonName.FARFETCHD
DAMP_IGNORES = (_MOVENAME_EXPLOSION, _MOVENAME_SELFDESTRUCT)
WEATHER_NOT_END_OF_TURN = (0, _WEATHER_RAIN)
HP_RESTORE_EFFECTS = (_HOLDEFFECT_HP_RESTORE, _HOLDEFFECT_HP_PCT_RESTORE)
METRONOME_MAX_COUNT = 10
# Choice Band, Choice Specs and Choice Scarf
CHOICE_EFFECTS = (_HOLDEFFECT_CHOICE_ATK, _HOLDEFFECT_CHOICE_SPATK, _HOLDEFFECT_CHOICE_SPEED)
# Pecha, Chesto, Lum, Mental Herb, Cheri, Rawst, Aspear and Persim
STATUS_CURE_EFFECTS = (
    _HOLDEFFECT_PSN_RESTORE, _HOLDEFFECT_SLP_RESTORE, _HOLDEFFECT_STATUS_RESTORE,
    _HOLDEFFECT_HEAL_INFATUATION, _HOLDEFFECT_PRZ_RESTORE, _HOLDEFFECT_BRN_RESTORE,
    _HOLDEFFECT_FRZ_RESTORE, _HOLDEFFECT_CONFUSE_RESTORE
)
# Figy, Iapapa, Wiki, Aguav, Mago: the flavor of each Pok.NATURE_MINUS stat (pokeplatinum FLAVOR_*)
FLAVOR_EFFECTS = (
    _HOLDEFFECT_HP_RESTORE_SPICY, _HOLDEFFECT_HP_RESTORE_SOUR, _HOLDEFFECT_HP_RESTORE_DRY,
    _HOLDEFFECT_HP_RESTORE_BITTER, _HOLDEFFECT_HP_RESTORE_SWEET
)
# Liechi, Ganlon, Petaya, Apicot, Salac in stat stage order
PINCH_STAT_EFFECTS = (
    _HOLDEFFECT_PINCH_ATK_UP, _HOLDEFFECT_PINCH_DEF_UP, _HOLDEFFECT_PINCH_SPATK_UP,
    _HOLDEFFECT_PINCH_SPDEF_UP, _HOLDEFFECT_PINCH_SPEED_UP
)
# The stat ones, Lansat, Starf and Micle (Custap works from the turn order)
PINCH_EFFECTS = PINCH_STAT_EFFECTS + (
    _HOLDEFFECT_PINCH_CRITRATE_UP, _HOLDEFFECT_PINCH_RANDOM_UP, _HOLDEFFECT_PINCH_ACC_UP
)
MICLE_ACC_BOOST = 120
MAX_PP_UPS = 3
RECORD_DAMAGE = (_DAMAGESOURCES_COUNTER, _DAMAGESOURCES_MAGIC_COAT)
# pokeplatinum BattleSystem_TriggerAbilityOnHit: RandNext % 3 picks poison, paralysis, sleep
EFFECT_SPORE_STATUSES = (_STATUS_POISON, _STATUS_PARALYSIS, _STATUS_SLEEP)
# Gravity's accuracy boost, x5/3 as 6840/4096
GRAVITY_ACC_NUM = 6840
GRAVITY_ACC_DEN = 4096
SIDE_OR_FIELD_TARGETS = (Target.ALL, Target.FOE_SIDE, Target.ALLY_TEAM)
# Confusion moves whose pokeplatinum subscript checks the Substitute before Own Tempo
SUB_FIRST_CONFUSERS = (_MOVENAME_SWAGGER, _MOVENAME_FLATTER)
PROTECT_COUNT_MAX = 3  # Success chance 1, 1/2, 1/4, then 1/8 from here on
# Stealth Rock takes max HP * Rock effectiveness / STEALTH_ROCK_DIV, 1/8 when neutral
STEALTH_ROCK_DIV = 8
# Synthesis heals a quarter of max HP in these weathers
HEAL_QUARTER_WEATHER = (_WEATHER_RAIN, _WEATHER_SANDSTORM, _WEATHER_HAIL)
# Synthesis's weather-dependent heal (pokeplatinum BATTLE_EFFECT_HEAL_HALF_MORE_IN_SUN)
SUN_HEAL_MOVES = (_MOVENAME_SYNTHESIS, _MOVENAME_MOONLIGHT, _MOVENAME_MORNING_SUN)
# pokeplatinum sMovesAffectedByHealBlock, the ones in MoveDB
HEAL_BLOCK_MOVES = SUN_HEAL_MOVES + (
    _MOVENAME_RECOVER, _MOVENAME_SOFT_BOILED, _MOVENAME_MILK_DRINK, _MOVENAME_SLACK_OFF,
    _MOVENAME_HEAL_ORDER, _MOVENAME_ROOST, _MOVENAME_REST, _MOVENAME_SWALLOW, _MOVENAME_WISH,
    _MOVENAME_HEALING_WISH
)
# Pok.STOCKPILE packs the count with the Defense and Sp. Def stages it gave (pokeplatinum
# stockpileCount, stockpileDefBoosts, stockpileSpDefBoosts)
STOCKPILE_MAX = 3
STOCKPILE_COUNT_MASK = 3
STOCKPILE_DEF_STEP = 4
STOCKPILE_SPDEF_STEP = 16
# Spit Up's power per stockpile (pokeplatinum effect 0161)
SPIT_UP_POWER = 100
# Refresh cures these, not sleep or freeze
REFRESH_CURES = (_STATUS_BURN, _STATUS_POISON, _STATUS_TOXIC, _STATUS_PARALYSIS)
WORRY_SEED_FAILS = (_ABILITYNAMES_TRUANT, _ABILITYNAMES_MULTITYPE)
# pokeplatinum ChooseTraceTarget
TRACE_FAILS = (_ABILITYNAMES_TRACE, _ABILITYNAMES_MULTITYPE, _ABILITYNAMES_FORECAST)
SWITCH_IN_MESSAGE_ABS = (_ABILITYNAMES_SLOW_START, _ABILITYNAMES_MOLD_BREAKER, _ABILITYNAMES_PRESSURE)
# The weather each ability sets on switch-in (pokeplatinum SWITCH_IN_CHECK_STATE_WEATHER_ABILITIES)
WEATHER_ABILITIES = (
    (_ABILITYNAMES_DRIZZLE, _WEATHER_RAIN), (_ABILITYNAMES_DROUGHT, _WEATHER_SUN),
    (_ABILITYNAMES_SAND_STREAM, _WEATHER_SANDSTORM), (_ABILITYNAMES_SNOW_WARNING, _WEATHER_HAIL),
)
PERISH_SONG_TURNS = 3
EMBARGO_TURNS = 5
MAGNET_RISE_TURNS = 5
# A flung item's status or flinch goes to the target
FLING_SEC_TARGET = Target.NORMAL
# Columns of an ITEM_TABLE row
ITEM_HOLD_EFFECT_COL = _ITEM_HOLD_EFFECT - _ITEM_ID
ITEM_EFFECT_PARAM_COL = _ITEM_EFFECT_PARAM - _ITEM_ID
ITEM_TYPE_COL = _ITEM_ITEM_TYPE - _ITEM_ID
# Moves that call another move
CALLER_MOVES = (
    _MOVENAME_METRONOME, _MOVENAME_MIRROR_MOVE, _MOVENAME_COPYCAT, _MOVENAME_NATURE_POWER,
    _MOVENAME_SLEEP_TALK
)
# pokeplatinum Move_IsInvoker (Assist and Me First aren't in MoveDB), Copycat fails on them too
INVOKER_MOVES = (
    _MOVENAME_SLEEP_TALK, _MOVENAME_COPYCAT, _MOVENAME_MIRROR_MOVE, _MOVENAME_METRONOME
)
# pokeplatinum sCannotEncoreMoves, Mirror Move shares it (Transform, Mimic and Sketch aren't in
# MoveDB)
CANT_MIRROR_MOVES = (_MOVENAME_MIRROR_MOVE, _MOVENAME_ENCORE, _MOVENAME_STRUGGLE)
# pokeplatinum sTerrainMove, indexed by Terrain
NATURE_POWER_MOVES = (
    _MOVENAME_EARTHQUAKE, _MOVENAME_EARTHQUAKE, _MOVENAME_SEED_BOMB, _MOVENAME_SEED_BOMB,
    _MOVENAME_ROCK_SLIDE, _MOVENAME_ROCK_SLIDE, _MOVENAME_BLIZZARD, _MOVENAME_HYDRO_PUMP,
    _MOVENAME_ICE_BEAM, _MOVENAME_TRI_ATTACK, _MOVENAME_MUD_BOMB, _MOVENAME_AIR_SLASH,
    _MOVENAME_TRI_ATTACK
)


# ── Volatile bookkeeping ───────────────────────────────────────────────────────

@njit
def mark_hurt(pok):
    """The Pokemon lost HP this turn (read by Assurance)"""
    pok[_POK_VOL_STATUS] |= _VOLSTATUS_HURT_THIS_TURN


@njit
def unlock_move(pok):
    """
    Ends a lock (Rollout, Ice Ball), a charge (Bounce) and the Fury Cutter/Rollout counter when
    the move doesn't go through. Bide keeps its own pause rule. Uproar ends at this turn's residual.
    A rampage (Thrash) ends without confusion (pokeplatinum BattleContext_MoveFailed)
    """
    if pok[_POK_VOL_STATUS] & _VOLSTATUS_BIDE:
        return
    if pok[_POK_VOL_STATUS] & _VOLSTATUS_UPROAR:
        pok[_POK_UPROAR_TURNS] = 1
    if pok[_POK_CHARGE_RECHARGE] > 0:
        pok[_POK_CHARGE_RECHARGE] = 0
    pok[_POK_LOCKED_MOVE] = -1
    pok[_POK_CONSEC_COUNT] = 0
    pok[_POK_VOL_STATUS] &= ~_VOLSTATUS_SEMI_INVULNERABLE
    pok[_POK_SEMI_INV_MOVE] = 0
    pok[_POK_RAMPAGE_TURNS] = 0


@njit
def move_blocked(pok, slot, gravity=False):
    """
    Disable, Encore or Taunt keep this move slot from being selected, and so does Gravity for
    its moves, Heal Block for its moves and a choice item for every slot but the locked one (PP is
    checked apart)
    """
    if gravity and pok[OFFSET_MOVE + slot * MOVE_STRIDE + _FLAGS_GRAVITY]:
        return True
    if heal_block_stops(pok, pok[OFFSET_MOVE + slot * MOVE_STRIDE + _MOVE_ID]):
        return True
    lock = pok[_POK_CHOICE_LOCK]
    if lock and slot != lock - 1 and pok[_ITEM_HOLD_EFFECT] in CHOICE_EFFECTS:
        return True
    vol = pok[_POK_VOL_STATUS]
    if vol & _VOLSTATUS_DISABLE and slot == pok[_POK_DISABLE_TURNS] & SLOT_MASK:
        return True
    if vol & _VOLSTATUS_ENCORE and slot != pok[_POK_ENCORE_TURNS] & SLOT_MASK:
        return True
    return bool(
        vol & _VOLSTATUS_TAUNT
        and pok[OFFSET_MOVE + slot * MOVE_STRIDE + _MOVE_CATEGORY] == _MOVECATEGORY_STATUS
    )


@njit
def update_choice_lock(pok, slot):
    """
    After a move that got past the can't-move checks, a choice item holder is locked into the
    selected slot (a caller like Metronome locks itself, Struggle keeps the lock it had) and
    without one the lock ends. The item is read after the move, so a Covet that steals one locks
    into Covet (pokeplatinum BattleControllerPlayer_UpdateMoveBuffers)
    """
    if pok[_POK_CURRENT_HP] <= 0 or pok[_POK_LAST_MOVE_ID] == 0:
        return
    if pok[_ITEM_HOLD_EFFECT] not in CHOICE_EFFECTS:
        pok[_POK_CHOICE_LOCK] = 0
    elif slot < 4:
        pok[_POK_CHOICE_LOCK] = slot + 1


@njit
def clear_target_choice_lock(target, user):
    """
    After a move its user got to use, the target's lock ends if it holds no choice item, so a lock
    left from a lost item can't come back with one Trick hands it (pokeplatinum
    BattleControllerPlayer_UpdateMoveBuffers, the defender's side)
    """
    if user[_POK_LAST_MOVE_ID] != 0 and target[_ITEM_HOLD_EFFECT] not in CHOICE_EFFECTS:
        target[_POK_CHOICE_LOCK] = 0


@njit
def try_protect(pok, move_id, is_last):
    """
    Protect and Endure share the consecutive-use count. They fail when nothing acts after the
    user, a failure resets the count
    """
    count = pok[_POK_PROTECT_COUNT]
    if is_last or (count > 0 and random.getrandbits(count) != 0):
        pok[_POK_PROTECT_COUNT] = 0
        return
    pok[_POK_VOL_STATUS] |= _VOLSTATUS_PROTECT if move_id == _MOVENAME_PROTECT else _VOLSTATUS_ENDURE
    pok[_POK_PROTECT_COUNT] = min(count + 1, PROTECT_COUNT_MAX)


@njit
def focus_band(pok, damage):
    """
    Focus Band rolls on every hit its holder takes, lethal or not: 10% (its effect_param) to hold
    on (pokeplatinum BattleControllerPlayer_UpdateHP, BtlCmd_CheckHoldOnWith1HP)
    """
    return (
        damage > 0
        and pok[_ITEM_HOLD_EFFECT] == _HOLDEFFECT_MAYBE_ENDURE
        and random.randint(0, 99) < pok[_ITEM_EFFECT_PARAM]
    )


@njit
def focus_sash_ready(pok):
    """A Focus Sash holder at full HP, checked on every hit that reaches it (pokeplatinum
    BattleControllerPlayer_UpdateHP)"""
    return pok[_ITEM_HOLD_EFFECT] == _HOLDEFFECT_ENDURE and pok[_POK_CURRENT_HP] == pok[_POK_MAX_HP]


@njit
def endure_damage(defender, damage, sash=False):
    """Endure leaves the defender at 1 HP from a hit that would KO it, without Endure a Focus Band
    can do the same. sash: a Focus Sash found its holder at full HP on a hit of this move, so every
    lethal hit left of the move leaves 1 HP, and the first one uses the Sash up (pokeplatinum
    focusItemActivated lasts the move, subscript_move_followup_message; Showdown gen4 focussash)"""
    endure = (defender[_POK_VOL_STATUS] & _VOLSTATUS_ENDURE) != 0
    if endure or sash:
        holds_on = True
    else:
        holds_on = focus_band(defender, damage)
    if holds_on and damage >= defender[_POK_CURRENT_HP]:
        if not endure and defender[_ITEM_HOLD_EFFECT] == _HOLDEFFECT_ENDURE:
            defender[_POK_CONSUMED_ITEM] = defender[_ITEM_ID]
            clear_item(defender)
        return defender[_POK_CURRENT_HP] - 1
    return damage


@njit
def has_substitute(pok):
    """pok is behind a Substitute"""
    return (pok[_POK_VOL_STATUS2] & _VOLSTATUS2_SUBSTITUTE) != 0


@njit
def substitute_cost(pok):
    """The HP a Substitute costs and has, a quarter of max HP and at least 1 (pokeplatinum
    BtlCmd_TrySubstitute, BattleSystem_Divide)"""
    return max(1, pok[_POK_MAX_HP] // 4)


@njit
def substitute_fails(pok):
    """Substitute fails while one is up or when the user has no more HP than it costs"""
    return has_substitute(pok) or pok[_POK_CURRENT_HP] <= substitute_cost(pok)


@njit
def make_substitute(pok):
    """
    The user pays the Substitute's HP, which isn't damage (no Focus Band, Assurance doesn't see
    it), and is freed from a bind (pokeplatinum BtlCmd_TrySubstitute)
    """
    if substitute_fails(pok):
        return
    cost = substitute_cost(pok)
    pok[_POK_CURRENT_HP] -= cost
    pok[_POK_SUB_HP] = cost
    pok[_POK_VOL_STATUS2] |= _VOLSTATUS2_SUBSTITUTE
    pok[_POK_VOL_STATUS] &= ~_VOLSTATUS_PARTIALLY_TRAPPED
    pok[_POK_TRAP_TURNS] = 0


@njit
def hit_substitute(pok, damage):
    """
    A damaging hit on pok's Substitute: it takes the damage up to its HP and breaks at 0, the rest
    is lost. Returns the HP the Substitute lost, which recoil and drain read (pokeplatinum
    BattleControllerPlayer_UpdateHP, hitDamage)
    """
    sub_hp = pok[_POK_SUB_HP]
    if damage >= sub_hp:
        pok[_POK_SUB_HP] = 0
        pok[_POK_VOL_STATUS2] &= ~_VOLSTATUS2_SUBSTITUTE
        return sub_hp
    pok[_POK_SUB_HP] = sub_hp - max(0, damage)
    return max(0, damage)


@njit
def sub_blocks_move(move, attacker, defender):
    """
    A status move aimed at the foe fails against its Substitute unless it bypasses it (Gen IV: no
    sound exception). Moves aimed at a side or the field aren't, and neither is a non-Ghost's
    Curse, which boosts the user ([SD] gen4 Substitute onTryPrimaryHit, [pp] CheckSubstitute)
    """
    if (
        not has_substitute(defender)
        or move[_MOVE_CATEGORY] != _MOVECATEGORY_STATUS
        or move[_FLAGS_BYPASS_SUB]
        or move[_MOVE_TARGET] in TARGET_SELF_SIDE
        or move[_MOVE_TARGET] in SIDE_OR_FIELD_TARGETS
    ):
        return False
    if move[_MOVE_ID] == _MOVENAME_CURSE:
        return attacker[_POK_TYPE1] == _TYPES_GHOST or attacker[_POK_TYPE2] == _TYPES_GHOST
    return True


@njit
def sub_blocks_status_move(move, attacker, defender, weather):
    """
    sub_blocks_move, and the target's ability that would also stop the status is still revealed:
    pokeplatinum's status, confusion and Yawn subscripts and Captivate check it before the
    Substitute. Swagger and Flatter check the Substitute first
    """
    if not sub_blocks_move(move, attacker, defender):
        return False
    status = move[_MOVE_STATUS]
    vol = move[_MOVE_VOL_STATUS]
    blocked = False
    if status:
        blocked = ability_blocks_status(defender, attacker, status, weather)
    elif vol & _VOLSTATUS_YAWN:
        blocked = ability_blocks_status(defender, attacker, _STATUS_SLEEP, weather)
    elif vol & _VOLSTATUS_CONFUSION and move[_MOVE_ID] not in SUB_FIRST_CONFUSERS:
        blocked = (
            defender[_POK_AB_ID] == _ABILITYNAMES_OWN_TEMPO and ignorable_ability(defender, attacker)
        )
    # Captivate's Oblivious check comes before its stat drop's Substitute check (effect 265)
    elif move[_MOVE_ID] == _MOVENAME_CAPTIVATE:
        blocked = (
            defender[_POK_AB_ID] == _ABILITYNAMES_OBLIVIOUS and ignorable_ability(defender, attacker)
        )
    if blocked:
        reveal_ability(defender)
    return True


@njit
def confuse_boost_fails(move, defender):
    """Swagger and Flatter fail with their stat at +6 on a target already confused (pokeplatinum
    subscript_swagger, subscript_flatter)"""
    move_id = move[_MOVE_ID]
    if move_id == _MOVENAME_SWAGGER:
        stage = defender[_POK_ATTACK_STAT_STAGE]
    elif move_id == _MOVENAME_FLATTER:
        stage = defender[_POK_SPECIAL_ATTACK_STAT_STAGE]
    else:
        return False
    return stage >= 6 and defender[_POK_VOL_STATUS] & _VOLSTATUS_CONFUSION != 0


@njit
def stage_move_fails(move, attacker, defender):
    """
    Belly Drum at +6 Attack or at half its max HP or less (pokeplatinum subscript_belly_drum),
    Acupressure behind the user's Substitute or with every stat at +6 (effect 226,
    BtlCmd_BoostRandomStatBy2), Captivate on an Oblivious target unless Mold Breaker (the ability
    is revealed), a genderless one or one of the user's gender (effect 265)
    """
    move_id = move[_MOVE_ID]
    if move_id == _MOVENAME_BELLY_DRUM:
        return (
            attacker[_POK_ATTACK_STAT_STAGE] >= 6
            or attacker[_POK_CURRENT_HP] <= attacker[_POK_MAX_HP] // 2
        )
    if move_id == _MOVENAME_ACUPRESSURE:
        if has_substitute(attacker):
            return True
        for idx in range(_POK_ATTACK_STAT_STAGE, _POK_EVASION_STAT_STAGE + 1):
            if attacker[idx] < 6:
                return False
        return True
    if move_id == _MOVENAME_CAPTIVATE:
        if defender[_POK_AB_ID] == _ABILITYNAMES_OBLIVIOUS and ignorable_ability(defender, attacker):
            reveal_ability(defender)
            return True
        atk_gender = attacker[_POK_GENDER]
        def_gender = defender[_POK_GENDER]
        return (
            atk_gender == _GENDER_GENDERLESS or def_gender == _GENDER_GENDERLESS
            or atk_gender == def_gender
        )
    return False


@njit
def haze(atk, defn):
    """Every stat stage of both actives back to 0, and Focus Energy gone (pokeplatinum
    BtlCmd_ResetAllStatChanges, Showdown gen4 haze)"""
    atk[_POK_ATTACK_STAT_STAGE:_POK_EVASION_STAT_STAGE + 1] = 0
    defn[_POK_ATTACK_STAT_STAGE:_POK_EVASION_STAT_STAGE + 1] = 0
    atk[_POK_VOL_STATUS] &= ~_VOLSTATUS_FOCUS_ENERGY
    defn[_POK_VOL_STATUS] &= ~_VOLSTATUS_FOCUS_ENERGY


@njit
def psych_up(atk, defn):
    """The user takes the target's seven stat stages. Only the stages: copying Focus Energy came in
    Gen VI (Showdown gen5 psychup)"""
    atk[_POK_ATTACK_STAT_STAGE:_POK_EVASION_STAT_STAGE + 1] = (
        defn[_POK_ATTACK_STAT_STAGE:_POK_EVASION_STAT_STAGE + 1]
    )


@njit
def _swap_stage(atk, defn, idx):
    """Trade one stat stage"""
    stage = atk[idx]
    atk[idx] = defn[idx]
    defn[idx] = stage


@njit
def swap_stages(atk, defn, move_id):
    """Power Swap trades the Attack and SpAtk stages, Guard Swap Defense and SpDef, Heart Swap all
    seven. Focus Energy stays where it is (Showdown powerswap, guardswap, heartswap)"""
    if move_id == _MOVENAME_POWER_SWAP:
        _swap_stage(atk, defn, _POK_ATTACK_STAT_STAGE)
        _swap_stage(atk, defn, _POK_SPECIAL_ATTACK_STAT_STAGE)
    elif move_id == _MOVENAME_GUARD_SWAP:
        _swap_stage(atk, defn, _POK_DEFENSE_STAT_STAGE)
        _swap_stage(atk, defn, _POK_SPECIAL_DEFENSE_STAT_STAGE)
    else:
        for idx in range(_POK_ATTACK_STAT_STAGE, _POK_EVASION_STAT_STAGE + 1):
            _swap_stage(atk, defn, idx)


@njit
def swap_atk_def(pok):
    """Power Trick's Attack and Defense trade"""
    attack = pok[_POK_ATTACK]
    pok[_POK_ATTACK] = pok[_POK_DEFENSE]
    pok[_POK_DEFENSE] = attack


@njit
def power_trick(pok):
    """Attack and Defense trade places, using it again trades them back (pokeplatinum
    subscript_user_swap_atk_and_def). Switch-out trades them back, Baton Pass hands it over"""
    pok[_POK_VOL_STATUS2] ^= _VOLSTATUS2_POWER_TRICK
    swap_atk_def(pok)


@njit
def belly_drum(pok):
    """+6 Attack for half the max HP, which isn't damage, like a Substitute's cost (pokeplatinum
    subscript_belly_drum). stage_move_fails checks it first"""
    pok[_POK_ATTACK_STAT_STAGE] = 6
    pok[_POK_CURRENT_HP] -= pok[_POK_MAX_HP] // 2


@njit
def acupressure(pok):
    """+2 to one of the stats below +6, at random (pokeplatinum BtlCmd_BoostRandomStatBy2).
    stage_move_fails checks there is one"""
    count = 0
    for idx in range(_POK_ATTACK_STAT_STAGE, _POK_EVASION_STAT_STAGE + 1):
        if pok[idx] < 6:
            count += 1
    pick = random.randrange(count)
    for idx in range(_POK_ATTACK_STAT_STAGE, _POK_EVASION_STAT_STAGE + 1):
        if pok[idx] < 6:
            if pick == 0:
                pok[idx] = min(6, pok[idx] + 2)
                return
            pick -= 1


@njit
def metronome_count(pok, move_id):
    """
    The Metronome item counts the selected move's uses in a row, up to 10, another move starts over
    at 0. Locked turns and turns that don't reach the move don't count (pokeplatinum
    BattleSystem_UpdateMetronomeCount). Packed as move id * 16 + count
    """
    packed = pok[_POK_METRONOME_COUNT]
    if pok[_ITEM_HOLD_EFFECT] != _HOLDEFFECT_BOOST_REPEATED:
        pok[_POK_METRONOME_COUNT] = packed & ~METRONOME_COUNT_MASK
    elif packed >> METRONOME_MOVE_SHIFT == move_id:
        if packed & METRONOME_COUNT_MASK < METRONOME_MAX_COUNT:
            pok[_POK_METRONOME_COUNT] = packed + 1
    else:
        pok[_POK_METRONOME_COUNT] = move_id << METRONOME_MOVE_SHIFT


@njit
def metronome_fail(pok, move_id):
    """A counted move that fails gives back its Metronome count (pokeplatinum
    BattleSystem_VerifyMetronomeCount)"""
    packed = pok[_POK_METRONOME_COUNT]
    if (
        pok[_ITEM_HOLD_EFFECT] == _HOLDEFFECT_BOOST_REPEATED
        and packed >> METRONOME_MOVE_SHIFT == move_id
        and packed & METRONOME_COUNT_MASK
    ):
        pok[_POK_METRONOME_COUNT] = packed - 1


# ── Item / berry helpers ───────────────────────────────────────────────────────

@njit
def clear_item(pok):
    """
    If the item was used reset it
    """
    pok[_ITEM_ID:(_ITEM_ID+ITEM_LEN)] = 0


@njit
def _apply_berry_effect(source, target, plucked=False):
    """Apply the effect of source's held item to target. target = the beneficiary, which is
    'pok' for a self-trigger, or 'attacker' for Bug Bite (plucked: no HP check for the pinch
    berries, pokeplatinum BattleSystem_PluckBerry)."""
    berry_effect(source[_ITEM_HOLD_EFFECT], source[_ITEM_EFFECT_PARAM], target, plucked)


@njit
def berry_effect(effect, param, target, plucked=False):
    """_apply_berry_effect from the berry's hold effect and param, also for a berry no one holds
    anymore (a flung one)"""
    cur_hp = target[_POK_CURRENT_HP]
    max_hp = target[_POK_MAX_HP]
    if effect == _HOLDEFFECT_HP_RESTORE:
        cur_hp = min(cur_hp + param, max_hp)
    elif effect == _HOLDEFFECT_HP_PCT_RESTORE:
        # Needs to be with min because of bug bite
        cur_hp = min(cur_hp + max(1, max_hp * param // 100), max_hp)
    elif effect in FLAVOR_EFFECTS:
        if cur_hp < max_hp:
            cur_hp = min(cur_hp + max(1, max_hp // param), max_hp)
            if dislikes_flavor(target, effect):
                _flavor_confuse(target)
    elif plucked and effect == _HOLDEFFECT_CONFUSE_RESTORE and target[_POK_ATTACK_STAT_STAGE] < 6:
        # pokeplatinum PluckBerry: PLUCK_EFFECT_CNF_RESTORE has no break and falls into ATK_UP,
        # so below +6 Attack goes up instead of the confusion being cured
        target[_POK_ATTACK_STAT_STAGE] += 1
    elif effect in STATUS_CURE_EFFECTS:
        item_cure(effect, target)
    elif effect == _HOLDEFFECT_PP_RESTORE:
        leppa(target, param, plucked)
    elif effect in PINCH_EFFECTS:
        pinch_boost(effect, target)
    target[_POK_CURRENT_HP] = cur_hp


@njit
def dislikes_flavor(pok, effect):
    """The nature lowers the stat whose flavor this confusion berry is"""
    minus = pok[_POK_NATURE_MINUS]
    return minus > 0 and FLAVOR_EFFECTS[minus - 1] == effect


@njit
def _flavor_confuse(pok):
    """
    A disliked flavor confuses for 2-5 turns. Own Tempo stops it without a message, so does an
    existing confusion (pokeplatinum subscript_confuse, SIDE_EFFECT_TYPE_HELD_ITEM). Safeguard
    doesn't: the eater is its own source (Showdown safeguard onTryAddVolatile)
    """
    if pok[_POK_AB_ID] == _ABILITYNAMES_OWN_TEMPO or pok[_POK_VOL_STATUS] & _VOLSTATUS_CONFUSION:
        return
    pok[_POK_VOL_STATUS] |= _VOLSTATUS_CONFUSION
    pok[_POK_CONFUSION_COUNTER] = TURNS_2_5[random.getrandbits(2)]


@njit
def pinch_boost(effect, pok):
    """
    Liechi, Ganlon, Petaya, Apicot and Salac +1 to their stat, Lansat sets Focus Energy, Starf +2 to
    a random stat from Attack to Speed, Micle boosts the next accuracy roll. Returns False when it
    has nothing to do: its stat at +6, Focus Energy already on, every Starf stat at +6
    (pokeplatinum BattleSystem_TriggerHeldItem, the RandNext % 5 loop for Starf)
    """
    for i in range(5):
        if effect == PINCH_STAT_EFFECTS[i]:
            idx = _POK_ATTACK_STAT_STAGE + i
            if pok[idx] >= 6:
                return False
            pok[idx] += 1
            return True
    if effect == _HOLDEFFECT_PINCH_CRITRATE_UP:
        if pok[_POK_VOL_STATUS] & _VOLSTATUS_FOCUS_ENERGY:
            return False
        pok[_POK_VOL_STATUS] |= _VOLSTATUS_FOCUS_ENERGY
        return True
    if effect == _HOLDEFFECT_PINCH_RANDOM_UP:
        can_raise = False
        for i in range(5):
            if pok[_POK_ATTACK_STAT_STAGE + i] < 6:
                can_raise = True
        if not can_raise:
            return False
        idx = _POK_ATTACK_STAT_STAGE + random.randint(0, 4)
        while pok[idx] >= 6:
            idx = _POK_ATTACK_STAT_STAGE + random.randint(0, 4)
        pok[idx] = min(6, pok[idx] + 2)
        return True
    if effect == _HOLDEFFECT_PINCH_ACC_UP:
        pok[_POK_VOL_STATUS2] |= _VOLSTATUS2_MICLE
        return True
    return False


@njit
def max_pp(pok, slot):
    """A move's max PP: base + 20% per PP Up, up to 3 (pokeplatinum MoveTable_CalcMaxPP)"""
    off = OFFSET_MOVE + slot * MOVE_STRIDE
    base = MOVE_TABLE[pok[off + _MOVE_ID], _MOVE_PP]
    return base + base * 20 * min(MAX_PP_UPS, pok[off + _MOVE_PP_UP]) // 100


@njit
def leppa(pok, amount, plucked=False):
    """
    Leppa Berry gives a move back amount PP, up to its max. Held, it waits for a move at 0 PP and
    takes the first one; plucked, it takes the move missing the most PP (pokeplatinum
    BattleSystem_TriggerHeldItem, BattleSystem_PluckBerry). Returns True if it restored any
    """
    slot = -1
    most = 0
    for i in range(4):
        off = OFFSET_MOVE + i * MOVE_STRIDE
        if not pok[off + _MOVE_ID]:
            continue
        if plucked:
            missing = max_pp(pok, i) - pok[off + _MOVE_PP]
            if missing > most:
                most = missing
                slot = i
        elif pok[off + _MOVE_PP] == 0:
            slot = i
            break
    if slot < 0:
        return False
    off = OFFSET_MOVE + slot * MOVE_STRIDE
    pok[off + _MOVE_PP] = min(max_pp(pok, slot), pok[off + _MOVE_PP] + amount)
    return True


@njit
def item_cure(effect, pok):
    """
    Pecha cures poison, Chesto sleep, Cheri paralysis, Rawst burn, Aspear freeze, Persim confusion,
    Lum any status and confusion, Mental Herb only Attract in Gen IV (pokeplatinum
    BattleSystem_TriggerHeldItemOnStatus, Showdown gen4 Mental Herb). Returns True if it cured
    something
    """
    status = pok[_POK_STATUS]
    if effect == _HOLDEFFECT_PSN_RESTORE:
        if status != _STATUS_POISON and status != _STATUS_TOXIC:
            return False
    elif effect == _HOLDEFFECT_SLP_RESTORE:
        if status != _STATUS_SLEEP:
            return False
    elif effect == _HOLDEFFECT_PRZ_RESTORE:
        if status != _STATUS_PARALYSIS:
            return False
    elif effect == _HOLDEFFECT_BRN_RESTORE:
        if status != _STATUS_BURN:
            return False
    elif effect == _HOLDEFFECT_FRZ_RESTORE:
        if status != _STATUS_FREEZE:
            return False
    elif effect == _HOLDEFFECT_CONFUSE_RESTORE:
        if not pok[_POK_VOL_STATUS] & _VOLSTATUS_CONFUSION:
            return False
        pok[_POK_VOL_STATUS] &= ~_VOLSTATUS_CONFUSION
        return True
    elif effect == _HOLDEFFECT_STATUS_RESTORE:
        if status == 0 and not pok[_POK_VOL_STATUS] & _VOLSTATUS_CONFUSION:
            return False
        pok[_POK_VOL_STATUS] &= ~_VOLSTATUS_CONFUSION
    elif effect == _HOLDEFFECT_HEAL_INFATUATION:
        if not pok[_POK_VOL_STATUS] & _VOLSTATUS_ATTRACT:
            return False
        pok[_POK_VOL_STATUS] &= ~_VOLSTATUS_ATTRACT
        return True
    else:
        return False
    cure_status(pok)
    return True


@njit
def sleep_talk_move(pok, gravity):
    """
    The move Sleep Talk calls at random from the user's slots, 0 if none or if it's awake. It skips
    the moves [SD] flags nosleeptalk (the callers, Focus Punch, Uproar, Chatter, Bide and most charge
    moves), every charge move ([pp] Move_IsMultiTurn, Fly too) and the slots move_blocked stops, so
    a choice lock or Encore makes it fail. PP doesn't matter ([pp] TrySleepTalk skips that check)
    """
    if pok[_POK_STATUS] != _STATUS_SLEEP:
        return 0
    count = 0
    for slot in range(4):
        if _sleep_talk_pick(pok, slot, gravity):
            count += 1
    if count == 0:
        return 0
    pick = random.randint(0, count - 1)
    for slot in range(4):
        if _sleep_talk_pick(pok, slot, gravity):
            if pick == 0:
                return pok[OFFSET_MOVE + slot * MOVE_STRIDE + _MOVE_ID]
            pick -= 1
    return 0


@njit
def _sleep_talk_pick(pok, slot, gravity):
    """Sleep Talk can call the move in this slot"""
    base = OFFSET_MOVE + slot * MOVE_STRIDE
    return (
        pok[base + _MOVE_ID] != 0
        and not pok[base + _FLAGS_NO_SLEEP_TALK]
        and pok[base + _MOVE_CHARGE_RECHARGE] <= 0
        and not move_blocked(pok, slot, gravity)
    )


@njit
def status_move_fails(move, attacker, defender):
    """
    Rest on a user already asleep, at full HP, with Insomnia or Vital Spirit (revealed) or in an
    uproar it isn't Soundproof against; Leaf Guard doesn't stop it ([SD] gen4 rest onTry, Leaf Guard).
    Nightmare on a target that isn't asleep or already has one. Psycho Shift with no status on the
    user or one on the target ([pp] CheckCanShareStatus; the Substitute is sub_blocks_status_move's).
    Magnet Rise while up, with Levitate or under Ingrain
    """
    move_id = move[_MOVE_ID]
    if move_id == _MOVENAME_REST:
        if attacker[_POK_STATUS] == _STATUS_SLEEP:
            return True
        if attacker[_POK_CURRENT_HP] >= attacker[_POK_MAX_HP]:
            return True
        ability = attacker[_POK_AB_ID]
        if ability == _ABILITYNAMES_INSOMNIA or ability == _ABILITYNAMES_VITAL_SPIRIT:
            reveal_ability(attacker)
            return True
        return sleep_blocked(attacker, defender)
    if move_id == _MOVENAME_NIGHTMARE:
        return (
            defender[_POK_STATUS] != _STATUS_SLEEP
            or defender[_POK_VOL_STATUS] & _VOLSTATUS_NIGHTMARE != 0
        )
    if move_id == _MOVENAME_PSYCHO_SHIFT:
        return attacker[_POK_STATUS] == 0 or defender[_POK_STATUS] != 0
    if move_id == _MOVENAME_MAGNET_RISE:
        return magnet_rise_fails(attacker)
    return False


@njit
def rest(pok):
    """Rest: full HP and 2 turns of sleep (a counter of 3), the old status and its counters gone and
    a Nightmare ended ([SD] rest onHit, statusState.time = 3; slp onStart)"""
    cure_status(pok)
    pok[_POK_STATUS] = _STATUS_SLEEP
    pok[_POK_SLEEP_COUNTER] = 3
    pok[_POK_VOL_STATUS] &= ~_VOLSTATUS_NIGHTMARE
    pok[_POK_CURRENT_HP] = pok[_POK_MAX_HP]


@njit
def psycho_shift(move, attacker, defender, side, weather):
    """
    Psycho Shift gives the user's status to the target through the usual checks (types, ability,
    Safeguard, uproar), as a status move does, so a blocking ability is revealed. Sleep rolls a new
    count and toxic starts over. The user is cured only once the target has it ([SD] psychoshift).
    side is the target's Field.SIDE_COND
    """
    shifted = move.copy()
    shifted[_MOVE_STATUS] = attacker[_POK_STATUS]
    apply_status(shifted, defender, weather, attacker, False, side)
    if defender[_POK_STATUS] != 0:
        cure_status(attacker)
        attacker[_POK_VOL_STATUS] &= ~_VOLSTATUS_NIGHTMARE


@njit
def heal_bell(battle_array, user, move_id, is_mine):
    """
    Heal Bell and Aromatherapy cure the user's whole party, a Nightmare included. Heal Bell skips
    every Soundproof one, on the bench too, unless the user has Mold Breaker ([SD] gen4 healbell,
    suppressingAbility); the user's own Soundproof is revealed
    """
    soundproof_counts = (
        move_id == _MOVENAME_HEAL_BELL and user[_POK_AB_ID] != _ABILITYNAMES_MOLD_BREAKER
    )
    if soundproof_counts and user[_POK_AB_ID] == _ABILITYNAMES_SOUNDPROOF:
        reveal_ability(user)
    start = 0 if is_mine else 6
    for i in range(start, start + 6):
        pok = battle_array[i * POK_LEN:(i + 1) * POK_LEN]
        if pok[_POK_CURRENT_HP] <= 0 or pok[_POK_STATUS] == 0:
            continue
        if soundproof_counts and pok[_POK_AB_ID] == _ABILITYNAMES_SOUNDPROOF:
            continue
        cure_status(pok)
        pok[_POK_VOL_STATUS] &= ~_VOLSTATUS_NIGHTMARE


@njit
def restore_stat_drops(pok):
    """White Herb: every lowered stage back to 0, accuracy and evasion too (pokeplatinum
    BattleSystem_TriggerHeldItemOnStatus). Returns True if one was lowered"""
    restored = False
    for idx in range(_POK_ATTACK_STAT_STAGE, _POK_EVASION_STAT_STAGE + 1):
        if pok[idx] < 0:
            pok[idx] = 0
            restored = True
    return restored


@njit
def status_item(pok):
    """
    A status berry, Mental Herb or White Herb is used up once its holder has the condition it cures,
    Leppa once a move is at 0 PP, and the HP and pinch berries get another look (eat_berry). A
    fainted Pokemon doesn't use it. pokeplatinum checks after every move, on switch-in and after Yawn
    """
    effect = pok[_ITEM_HOLD_EFFECT]
    if pok[_POK_CURRENT_HP] <= 0:
        return
    if (
        (effect in STATUS_CURE_EFFECTS and item_cure(effect, pok))
        or (effect == _HOLDEFFECT_STATDOWN_RESTORE and restore_stat_drops(pok))
        or (effect == _HOLDEFFECT_PP_RESTORE and leppa(pok, pok[_ITEM_EFFECT_PARAM]))
    ):
        pok[_POK_CONSUMED_ITEM] = pok[_ITEM_ID]
        clear_item(pok)
    else:
        eat_berry(pok)


@njit
def eat_berry(pok):
    """Self-triggered berry eat at low HP (on receiving damage, after every move, end of turn).
    The HP and confusion berries at half HP, the pinch berries at a quarter (Gluttony: half) once
    they have something to do. A fainted Pokemon doesn't eat it (pokeplatinum
    BattleSystem_TriggerHeldItem)"""
    effect = pok[_ITEM_HOLD_EFFECT]
    if pok[_POK_CURRENT_HP] <= 0:
        return
    if effect in HP_RESTORE_EFFECTS or effect in FLAVOR_EFFECTS:
        if pok[_POK_CURRENT_HP] * 2 > pok[_POK_MAX_HP]:
            return
        _apply_berry_effect(pok, pok)
    elif effect in PINCH_EFFECTS:
        if not pinch_hp(pok) or not pinch_boost(effect, pok):
            return
    else:
        return
    pok[_POK_CONSUMED_ITEM] = pok[_ITEM_ID]
    clear_item(pok)


@njit
def custap(pok):
    """
    Custap Berry in a pinch is eaten when both sides use a move, whatever their priority, and its
    holder goes first in its bracket (pokeplatinum CompareBattlerSpeed and
    subscript_check_quick_claw, Showdown gen4 custapberry). Returns True if it activated
    """
    if not custap_ready(pok):
        return False
    pok[_POK_CONSUMED_ITEM] = pok[_ITEM_ID]
    clear_item(pok)
    return True


@njit
def resist_berry(attacker, defender, move, damage, gravity=False):
    """
    A resist berry halves a super effective hit of its type and Chilan any Normal hit, then it's
    eaten. Showdown onSourceModifyDamage, a final modifier that leaves at least 1
    """
    effect = defender[_ITEM_HOLD_EFFECT]
    if damage <= 0 or (effect != _HOLDEFFECT_WEAKEN_SE and effect != _HOLDEFFECT_WEAKEN_NORMAL):
        return damage
    # Not on a hit its Substitute takes (Showdown gen4 resist berries)
    if has_substitute(defender):
        return damage
    m_type = normalized_type(attacker, move)
    if m_type != defender[_ITEM_EFFECT_TYPE]:
        return damage
    if effect == _HOLDEFFECT_WEAKEN_SE:
        def_type1, def_type2 = matchup_types(m_type, defender, gravity, is_scrappy(attacker))
        effectiveness, _ = get_type_effectiveness(m_type, def_type1, 0)
        effectiveness2 = 2
        if def_type2:
            effectiveness2, _ = get_type_effectiveness(m_type, def_type2, 0)
        if effectiveness * effectiveness2 <= 4:
            return damage
    defender[_POK_CONSUMED_ITEM] = defender[_ITEM_ID]
    clear_item(defender)
    return max(1, damage // 2)


@njit
def eat_berry_bug_bite(attacker, defender):
    """Bug Bite forces the target to eat its berry immediately; attacker gets the benefit.
    Pluck too. An Embargoed target's berry works, an Embargoed attacker only takes it away
    (pokeplatinum BattleSystem_PluckBerry)"""
    defender[_ITEM_ID:_ITEM_ID + ITEM_LEN] = ITEM_TABLE[defender[_ITEM_ID]]
    if not embargoed(attacker):
        _apply_berry_effect(defender, attacker, True)
    clear_item(defender)


@njit
def switch_items(pok1, pok2):
    """Switch items"""
    item_slice = slice(_ITEM_ID, _ITEM_ID + ITEM_LEN)
    item_copy = np.copy(pok1[item_slice])
    pok1[item_slice] = pok2[item_slice]
    pok2[item_slice] = item_copy
    # An Embargoed Pokemon's new item does nothing either
    refresh_item(pok1)
    refresh_item(pok2)


@njit
def power_herb(pok, move):
    """Power Herb is used up to skip a charge turn, Bide's turns aren't one (pokeplatinum
    subscript_item_skip_charge_turn). Returns True if it skipped"""
    if pok[_ITEM_HOLD_EFFECT] != _HOLDEFFECT_CHARGE_SKIP or move[_MOVE_ID] == _MOVENAME_BIDE:
        return False
    pok[_POK_CONSUMED_ITEM] = pok[_ITEM_ID]
    clear_item(pok)
    return True


@njit
def sticky_hold(defender, attacker):
    """Sticky Hold keeps the item from Covet and Bug Bite, Mold Breaker ignores it (pokeplatinum
    BtlCmd_TryStealItem, BtlCmd_TryPluck)"""
    return defender[_POK_AB_ID] == _ABILITYNAMES_STICKY_HOLD and ignorable_ability(defender, attacker)


@njit
def takeable_item(pok):
    """pok holds an item another Pokemon can take: anything but a Griseous Orb (pokeplatinum
    BtlCmd_TryStealItem, subscript_knock_off, subscript_exchange_items)"""
    return pok[_ITEM_ID] != 0 and pok[_ITEM_ID] != _ITEMNAMES_GRISEOUS_ORB


@njit
def knock_off(attacker, defender):
    """
    Knock Off removes the target's item. Gen IV marks the Pokemon for the rest of the battle: it
    can't get a new item and the knocked off one isn't recyclable. Sticky Hold keeps the item
    unless the user has Mold Breaker
    """
    if not takeable_item(defender):
        return
    if (
        defender[_POK_AB_ID] == _ABILITYNAMES_STICKY_HOLD
        and attacker[_POK_AB_ID] != _ABILITYNAMES_MOLD_BREAKER
    ):
        return
    clear_item(defender)
    defender[_POK_ITEM_KNOCKED_OFF] = 1


@njit
def carry_recycle(old, new):
    """Gen IV keeps the recyclable item with the battle slot, so the Pokemon coming in gets it"""
    item_id = old[_POK_CONSUMED_ITEM]
    old[_POK_CONSUMED_ITEM] = 0
    new[_POK_CONSUMED_ITEM] = item_id


@njit
def recycle(pok):
    """
    Recycle gives back the last item used up in this slot if the user holds none. A berry it
    restores at low HP is eaten right away
    """
    item_id = pok[_POK_CONSUMED_ITEM]
    if pok[_ITEM_ID] or item_id == 0:
        return
    pok[_ITEM_ID:_ITEM_ID + ITEM_LEN] = ITEM_TABLE[item_id]
    refresh_item(pok)
    pok[_POK_CONSUMED_ITEM] = 0
    item_on_rdmg(pok)


@njit
def swap_items(attacker, defender):
    """
    Trick and Switcheroo trade the held items. They fail if either side has Multitype, holds a
    Griseous Orb or had its item knocked off, or if neither holds one. Sticky Hold stops them even
    with no item on the target, unless the user has Mold Breaker. The AI swaps too, like Covet; the
    Substitute is checked before (pokeplatinum subscript_exchange_items, BtlCmd_TrySwapItems).
    Returns True if they swapped
    """
    if (
        attacker[_POK_AB_ID] == _ABILITYNAMES_MULTITYPE
        or defender[_POK_AB_ID] == _ABILITYNAMES_MULTITYPE
        or attacker[_ITEM_ID] == _ITEMNAMES_GRISEOUS_ORB
        or defender[_ITEM_ID] == _ITEMNAMES_GRISEOUS_ORB
        or attacker[_POK_ITEM_KNOCKED_OFF]
        or defender[_POK_ITEM_KNOCKED_OFF]
        or (attacker[_ITEM_ID] == 0 and defender[_ITEM_ID] == 0)
    ):
        return False
    if sticky_hold(defender, attacker):
        reveal_ability(defender)
        return False
    switch_items(attacker, defender)
    return True


@njit
def embargo(target):
    """
    Embargo: the target's held item does nothing for 5 turns. Fails on a target already under it,
    with Multitype or holding a Griseous Orb, not on one holding nothing; the Substitute is checked
    before (pokeplatinum subscript_embargo_start). Returns True if it started
    """
    if (
        embargoed(target)
        or target[_POK_AB_ID] == _ABILITYNAMES_MULTITYPE
        or target[_ITEM_ID] == _ITEMNAMES_GRISEOUS_ORB
    ):
        return False
    target[_POK_VOL_STATUS2] |= _VOLSTATUS2_EMBARGO
    target[_POK_EMBARGO_TURNS] = EMBARGO_TURNS
    refresh_item(target)
    return True


@njit
def embargo_count(pok):
    """End of turn: Embargo counts down and the item works again once it ends (pokeplatinum
    MON_COND_CHECK_STATE_EMBARGO)"""
    if not embargoed(pok):
        return
    pok[_POK_EMBARGO_TURNS] -= 1
    if pok[_POK_EMBARGO_TURNS] <= 0:
        pok[_POK_EMBARGO_TURNS] = 0
        pok[_POK_VOL_STATUS2] &= ~_VOLSTATUS2_EMBARGO
        refresh_item(pok)


@njit
def magnet_rise_fails(pok):
    """Magnet Rise fails while up, with Levitate or under Ingrain (pokeplatinum effect_script_0252).
    Gravity stops it before it runs (its gravity flag)"""
    return (
        pok[_POK_MAGNET_RISE_TURNS] > 0
        or pok[_POK_AB_ID] == _ABILITYNAMES_LEVITATE
        or (pok[_POK_VOL_STATUS] & _VOLSTATUS_INGRAIN) != 0
    )


@njit
def start_magnet_rise(pok):
    """Magnet Rise: 5 turns of Ground immunity. Returns True if it started"""
    if magnet_rise_fails(pok):
        return False
    pok[_POK_VOL_STATUS2] |= _VOLSTATUS2_MAGNET_RISE
    pok[_POK_MAGNET_RISE_TURNS] = MAGNET_RISE_TURNS
    return True


@njit
def end_magnet_rise(pok):
    """Magnet Rise wears off, or Gravity brings the Pokemon down"""
    pok[_POK_MAGNET_RISE_TURNS] = 0
    pok[_POK_VOL_STATUS2] &= ~_VOLSTATUS2_MAGNET_RISE


@njit
def magnet_rise_count(pok):
    """End of turn: Magnet Rise counts down (pokeplatinum MON_COND_CHECK_STATE_MAGNET_RISE)"""
    if pok[_POK_MAGNET_RISE_TURNS] > 0:
        pok[_POK_MAGNET_RISE_TURNS] -= 1
        if pok[_POK_MAGNET_RISE_TURNS] == 0:
            end_magnet_rise(pok)


@njit
def fling_fails(pok):
    """
    Fling fails with nothing to throw: no item or one with no Fling power, under Embargo (its block
    reads no item), with Multitype or holding a Griseous Orb (pokeplatinum BATTLE_EFFECT_FLING,
    BattleSystem_FlingItem). The item stays then
    """
    return (
        pok[_ITEM_FLING_POWER] == 0
        or pok[_POK_AB_ID] == _ABILITYNAMES_MULTITYPE
        or pok[_ITEM_ID] == _ITEMNAMES_GRISEOUS_ORB
    )


@njit
def fling_move(pok, target, move):
    """
    The move Fling hits with: the item's Fling power, and its status (Flame Orb, Toxic Orb, Poison
    Barb, Light Ball) or flinch (King's Rock, Razor Fang) as a sure secondary effect (Showdown fling
    onPrepareHit). None into an Embargoed target (pokeplatinum BattleSystem_FlingItem)
    """
    mv = move.copy()
    mv[_MOVE_POWER] = pok[_ITEM_FLING_POWER]
    if not embargoed(target) and (pok[_ITEM_FLING_STATUS] or pok[_ITEM_FLING_VOLATILE]):
        mv[_SEC_CHANCE] = 100
        mv[_SEC_TARGET] = FLING_SEC_TARGET
        mv[_SEC_STATUS] = pok[_ITEM_FLING_STATUS]
        mv[_SEC_VOL_STATUS] = pok[_ITEM_FLING_VOLATILE]
    return mv


@njit
def fling_throw(pok):
    """The flung item is gone after the damage, or on a miss, and Recycle can bring it back
    (pokeplatinum RemoveItem sets recycleItem, Showdown's fling volatile)"""
    pok[_POK_CONSUMED_ITEM] = pok[_ITEM_ID]
    clear_item(pok)


@njit
def fling_hit(attacker, defender):
    """
    A flung berry or herb works on the target the hit reached, if it survived: the berry as if it ate
    it (Leppa takes the move missing the most PP, Persim cures confusion), White Herb restores its
    lowered stats, Mental Herb cures infatuation. Not on an Embargoed target (Showdown fling onHit,
    pokeplatinum BattleSystem_FlingItem). The item is the attacker's last used one
    """
    if defender[_POK_CURRENT_HP] <= 0 or embargoed(defender):
        return
    row = ITEM_TABLE[attacker[_POK_CONSUMED_ITEM]]
    effect = row[ITEM_HOLD_EFFECT_COL]
    if effect == _HOLDEFFECT_STATDOWN_RESTORE:
        restore_stat_drops(defender)
    elif effect == _HOLDEFFECT_CONFUSE_RESTORE or effect == _HOLDEFFECT_HEAL_INFATUATION:
        item_cure(effect, defender)
    elif row[ITEM_TYPE_COL] == _ITEMTYPE_BERRY:
        berry_effect(effect, row[ITEM_EFFECT_PARAM_COL], defender, True)


@njit
def item_on_rdmg(pok):
    """
    Check what item it is and apply it
    """
    eat_berry(pok)


# ── Speed & turn order ──────────────────────────────────────────────────────────

@njit
def truant_loafs(pok):
    """
    Truant acts on its first full turn and loafs every other turn after, by turn parity rather
    than by what it did (pokeplatinum Battler_CheckTruant, truant = (totalTurns + 1) & 1 on entry)
    """
    return pok[_POK_AB_ID] == _ABILITYNAMES_TRUANT and pok[_POK_TURNS_ACTIVE] % 2 == 0


@njit
def move_order(
        p1, my_move, p2, opp_move, p1_switch, p2_switch, weather, tail1=False, tail2=False,
        trick_room=False
):
    """
    Calculates who acts first this turn. tail1 / tail2: Tailwind is up on that side. Trick Room
    flips the speed compare, after priority, Quick Claw, Lagging Tail and Stall (Showdown: both
    activated Quick Claws are flipped too, pokeplatinum doesn't)
    Returns (mv1_slot, mv2_slot, count, first_is_mine):
      mv1_slot / mv2_slot — move index for whoever acts in that position
                            (-1 = switch, dummy value if count < 2)
      count               — how many of the two slots actually act (0, 1, or 2)
      first_is_mine       — whether slot 1 belongs to my side
    """
    if p1_switch and p2_switch:
        return -1, -1, 0, False  # count=0, rest are dummies

    if p1_switch:
        return opp_move, -1, 1, False
    if p2_switch:
        return my_move, -1, 1, True

    p1_speed, p2_speed = check_speed(p1, p2, weather, tail1, tail2)
    custap1 = custap(p1)
    custap2 = custap(p2)

    move1_prio = (p1[my_move  * MOVE_STRIDE + OFFSET_MOVE + _MOVE_PRIORITY]
              if my_move  != 10 else 0)
    move2_prio = (p2[opp_move * MOVE_STRIDE + OFFSET_MOVE + _MOVE_PRIORITY]
              if opp_move != 10 else 0)

    if (
        (move1_prio != 0 or move2_prio != 0)
        and move1_prio != move2_prio
    ):
        if move1_prio > move2_prio:
            return my_move, opp_move, 2, True
        return opp_move, my_move, 2, False
    # Same bracket (Showdown gen4): an activated Quick Claw or Custap goes first, then a lone
    # Lagging Tail / Full Incense holder last, then a lone Stall holder last at priority >= 0. Both
    # Quick Claws, both items or both Stalls fall back to speed
    claw1 = custap1 or quick_claw(p1)
    claw2 = custap2 or quick_claw(p2)
    if claw1 != claw2:
        if claw1:
            return my_move, opp_move, 2, True
        return opp_move, my_move, 2, False
    lag1 = p1[_ITEM_HOLD_EFFECT] == _HOLDEFFECT_PRIORITY_DOWN
    lag2 = p2[_ITEM_HOLD_EFFECT] == _HOLDEFFECT_PRIORITY_DOWN
    if lag1 != lag2:
        if lag2:
            return my_move, opp_move, 2, True
        return opp_move, my_move, 2, False
    stall1 = p1[_POK_AB_ID] == _ABILITYNAMES_STALL
    stall2 = p2[_POK_AB_ID] == _ABILITYNAMES_STALL
    if not claw1 and move1_prio >= 0 and stall1 != stall2:
        if stall2:
            return my_move, opp_move, 2, True
        return opp_move, my_move, 2, False
    if goes_first(p1_speed, p2_speed, trick_room):
        return my_move, opp_move, 2, True
    return opp_move, my_move, 2, False


# ── Accuracy & crit ─────────────────────────────────────────────────────────────

@njit
def ohko_fails(attacker, defender):
    """An OHKO move can't work from a lower level or into Sturdy (Mold Breaker ignores it)"""
    if attacker[_POK_LEVEL] < defender[_POK_LEVEL]:
        return True
    return defender[_POK_AB_ID] == _ABILITYNAMES_STURDY and ignorable_ability(defender, attacker)


@njit
def damp_blocks(attacker, defender):
    """
    Damp on either side stops Explosion and Selfdestruct, Mold Breaker ignores the target's
    (pokeplatinum CheckIgnorableAbility on all battlers)
    """
    if attacker[_POK_AB_ID] == _ABILITYNAMES_DAMP:
        return True
    return defender[_POK_AB_ID] == _ABILITYNAMES_DAMP and ignorable_ability(defender, attacker)


@njit
def absorb_abi(defender):
    """
    Absorb abilities restore 1/4 of max hp on try hitting instead of the move
    """
    defender[_POK_CURRENT_HP] = min(
        defender[_POK_MAX_HP], (defender[_POK_CURRENT_HP] + defender[_POK_MAX_HP]//4)
    )


@njit
def ab_on_try_move(move, attacker, defender, accuracy:int):
    """
    Abilities that make the move fail before the accuracy roll: Damp, Soundproof (Mold Breaker
    ignores the target's, pokeplatinum TriggerImmunityAbility). The absorbing abilities come after
    the hit in calculate_hit_miss, accuracy modifiers live in move_accuracy
    """
    atk_ab = attacker[_POK_AB_ID]
    def_ab = defender[_POK_AB_ID]
    target = move[_MOVE_TARGET]
    if move[_MOVE_ID] in DAMP_IGNORES and damp_blocks(attacker, defender):
        # The message names whoever holds Damp (pokeplatinum effect_script_0007, ABILITY_MON)
        reveal_ability(attacker if atk_ab == _ABILITYNAMES_DAMP else defender)
        return 0
    if move[_FLAGS_SOUND] and def_ab == _ABILITYNAMES_SOUNDPROOF and ignorable_ability(defender, attacker):
        reveal_ability(defender)
        return 0
    if move[_FLAGS_SOUND] and atk_ab == _ABILITYNAMES_SOUNDPROOF and target in TARGET_SELF_SIDE:
        return 0

    return accuracy


@njit
def ability_immune(move, attacker, defender, gravity=False):
    """
    Which of the defender's abilities stops a move that hit, 0 if none (pokeplatinum
    TriggerImmunityAbility and the Wonder Guard check of ApplyTypeChart, Showdown gen4 runs them
    after the accuracy). Volt Absorb and Motor Drive take any Electric move, Water Absorb and Dry
    Skin damaging Water moves, Flash Fire damaging Fire moves and Will-O-Wisp unless frozen.
    Wonder Guard lets only super effective damaging moves through, and Fire Fang (Gen IV bug).
    No side effects, Mold Breaker ignores all of them
    """
    if (
        move[_MOVE_TARGET] in TARGET_SELF_SIDE
        or move[_MOVE_TARGET] in SIDE_OR_FIELD_TARGETS
        or not ignorable_ability(defender, attacker)
    ):
        return 0
    ability = defender[_POK_AB_ID]
    m_type = normalized_type(attacker, move)
    damaging = move[_MOVE_CATEGORY] != _MOVECATEGORY_STATUS
    if m_type == _TYPES_ELECTRIC and (
        ability == _ABILITYNAMES_VOLT_ABSORB or ability == _ABILITYNAMES_MOTOR_DRIVE
    ):
        return ability
    if m_type == _TYPES_WATER and damaging and (
        ability == _ABILITYNAMES_WATER_ABSORB or ability == _ABILITYNAMES_DRY_SKIN
    ):
        return ability
    if (
        ability == _ABILITYNAMES_FLASH_FIRE
        and m_type == _TYPES_FIRE
        and (damaging or move[_MOVE_ID] == _MOVENAME_WILL_O_WISP)
        and defender[_POK_STATUS] != _STATUS_FREEZE
    ):
        return ability
    if (
        ability == _ABILITYNAMES_WONDER_GUARD
        and damaging
        and m_type != _TYPES_TYPELESS
        and move[_MOVE_ID] != _MOVENAME_STRUGGLE
        and move[_MOVE_ID] != _MOVENAME_FIRE_FANG
    ):
        def_t1, def_t2 = matchup_types(m_type, defender, gravity, is_scrappy(attacker))
        eff, den = get_type_effectiveness(m_type, def_t1, def_t2)
        if eff <= den:
            return ability
    return 0


@njit
def absorb_move(move, attacker, defender, gravity=False):
    """
    The defender's ability takes a move that hit: the absorbs heal 1/4 of max HP, Motor Drive
    raises Speed, Flash Fire powers up its Fire moves, Wonder Guard just blocks. Returns True if
    the move does nothing else
    """
    ability = ability_immune(move, attacker, defender, gravity)
    if ability == 0:
        return False
    if (
        ability == _ABILITYNAMES_VOLT_ABSORB
        or ability == _ABILITYNAMES_WATER_ABSORB
        or ability == _ABILITYNAMES_DRY_SKIN
    ):
        absorb_abi(defender)
    elif ability == _ABILITYNAMES_MOTOR_DRIVE:
        defender[_POK_SPEED_STAT_STAGE] = min(6, defender[_POK_SPEED_STAT_STAGE] + 1)
    elif ability == _ABILITYNAMES_FLASH_FIRE:
        defender[_POK_VOL_STATUS2] |= _VOLSTATUS2_FLASH_FIRE
    return True


@njit
def semi_inv_reaches(move_id, defender):
    """
    Gust, Hurricane, Sky Uppercut and Thunder reach a Pokemon in the air (Fly, Bounce), Earthquake
    and Magnitude one underground (Dig), Surf and Whirlpool one underwater (Dive). Only Memento
    reaches all four, Shadow Force included (pokeplatinum SYSCTL_HIT_DURING_*, effect 0168)
    """
    if move_id == _MOVENAME_MEMENTO:
        return True
    hidden = defender[_POK_SEMI_INV_MOVE]
    if hidden in AIRBORNE_MOVES:
        return move_id in HITS_AIRBORNE
    if hidden in UNDERGROUND_MOVES:
        return move_id in HITS_UNDERGROUND
    if hidden in UNDERWATER_MOVES:
        return move_id in HITS_UNDERWATER
    return False


@njit
def no_guard(attacker, defender):
    """
    No Guard on either side: the move skips the accuracy roll and reaches a semi-invulnerable
    target (pokeplatinum BattleControllerPlayer_CheckMoveHitOverrides)
    """
    return (
        attacker[_POK_AB_ID] == _ABILITYNAMES_NO_GUARD
        or defender[_POK_AB_ID] == _ABILITYNAMES_NO_GUARD
    )


@njit
def move_accuracy(move, attacker, defender, move_acc, weather, gravity=False, target_moved=False):
    """
    Hit rate out of 100 in pokeplatinum BattleControllerPlayer_CheckMoveHitAccuracy order: stages
    (Simple doubles them, Unaware ignores the foe's), Compound Eyes, Sand Veil, Snow Cloak, Hustle,
    Tangled Feet, Bright Powder / Lax Incense, Wide Lens, Zoom Lens (the target already acted this
    turn), Gravity. Mold Breaker ignores the defender's abilities
    """
    atk_ab = attacker[_POK_AB_ID]
    def_ab = defender[_POK_AB_ID] if ignorable_ability(defender, attacker) else 0
    acc_stage = attacker[_POK_ACCURACY_STAT_STAGE]
    ev_stage = defender[_POK_EVASION_STAT_STAGE]
    if atk_ab == _ABILITYNAMES_SIMPLE:
        acc_stage *= 2
    if def_ab == _ABILITYNAMES_SIMPLE:
        ev_stage *= 2
    if def_ab == _ABILITYNAMES_UNAWARE:
        acc_stage = 0
    if atk_ab == _ABILITYNAMES_UNAWARE:
        ev_stage = 0
    # Foresight ignores the target's evasion boosts
    if defender[_POK_VOL_STATUS] & _VOLSTATUS_FORESIGHT and ev_stage > 0:
        ev_stage = 0
    acc_stage = acc_stage - ev_stage
    acc_stage = max(-6, min(6, acc_stage))
    if acc_stage == 0:
        accuracy = move_acc
    elif acc_stage < 0:
        accuracy = move_acc*(3)//(3-acc_stage)
    else:
        accuracy = move_acc*(acc_stage+3)//3

    if atk_ab == _ABILITYNAMES_COMPOUND_EYES:
        accuracy = accuracy * 130 // 100
    if def_ab == _ABILITYNAMES_SAND_VEIL and weather == _WEATHER_SANDSTORM:
        accuracy = accuracy * 80 // 100
    if def_ab == _ABILITYNAMES_SNOW_CLOAK and weather == _WEATHER_HAIL:
        accuracy = accuracy * 80 // 100
    if atk_ab == _ABILITYNAMES_HUSTLE and move[_MOVE_CATEGORY] == _MOVECATEGORY_PHYSICAL:
        accuracy = accuracy * 80 // 100
    if def_ab == _ABILITYNAMES_TANGLED_FEET and defender[_POK_VOL_STATUS] & _VOLSTATUS_CONFUSION:
        accuracy = accuracy * 50 // 100
    if defender[_ITEM_HOLD_EFFECT] == _HOLDEFFECT_ACC_REDUCE:
        accuracy = accuracy * (100 - defender[_ITEM_EFFECT_PARAM]) // 100
    atk_item = attacker[_ITEM_HOLD_EFFECT]
    if atk_item == _HOLDEFFECT_ACCURACY_UP or (
        atk_item == _HOLDEFFECT_ACCURACY_UP_SLOWER and target_moved
    ):
        accuracy = accuracy * (100 + attacker[_ITEM_EFFECT_PARAM]) // 100
    if attacker[_POK_VOL_STATUS2] & _VOLSTATUS2_MICLE:
        accuracy = accuracy * MICLE_ACC_BOOST // 100

    if gravity:
        return accuracy * GRAVITY_ACC_NUM / GRAVITY_ACC_DEN
    return accuracy * 1.0


@njit
def calculate_hit_miss(move, attacker, defender, weather, gravity=False, target_moved=False):
    '''
    The move's outcome. A move that hit can still be taken by the target's ability (Volt Absorb,
    Flash Fire, Wonder Guard...), which makes it INVULNERABLE (pokeplatinum and Showdown gen4 check
    them after the type chart and the accuracy roll). target_moved: the target already acted this
    turn (Zoom Lens)
    '''
    outcome = _hit_outcome(move, attacker, defender, weather, gravity, target_moved)
    if outcome == _MOVEOUTCOME_HIT and absorb_move(move, attacker, defender, gravity):
        reveal_ability(defender)
        return _MOVEOUTCOME_INVULNERABLE
    return outcome


@njit
def record_last_resort(pok, slot, move_id):
    """Last Resort counts each move slot used since switch-in once its move got past the can't-move
    checks, a miss included. Last Resort itself and Struggle don't count (pokeplatinum
    BattleSystem_UpdateLastResort)"""
    if move_id != _MOVENAME_LAST_RESORT and move_id != _MOVENAME_STRUGGLE and 0 <= slot < 4:
        pok[_POK_LAST_RESORT] |= 1 << slot


@njit
def last_resort_works(pok):
    """It needs at least 2 known moves and every one but one used: Last Resort itself when the user
    knows it (pokeplatinum BtlCmd_TryLastResort, AICmd_IfCanUseLastResort)"""
    known = 0
    used = 0
    for slot in range(4):
        if pok[OFFSET_MOVE + slot * MOVE_STRIDE + _MOVE_ID] != 0:
            known += 1
            if pok[_POK_LAST_RESORT] & (1 << slot):
                used += 1
    return known >= 2 and used >= known - 1


@njit
def kick_hits(move, attacker, defender, weather, gravity=False, target_moved=False):
    """Triple Kick rolls accuracy again for each kick after the first, nothing else (pokeplatinum
    SetMultiHit without SKIP_ACCURACY_CHECK, Showdown multiaccuracy). No Guard always hits"""
    if no_guard(attacker, defender):
        return True
    accuracy = move_accuracy(
        move, attacker, defender, move[_MOVE_ACCURACY], weather, gravity, target_moved
    )
    return accuracy == 100 or random.randint(1, 100) <= accuracy


@njit
def _hit_outcome(move, attacker, defender, weather, gravity=False, target_moved=False):
    '''Protect, semi-invulnerability, type immunities and the accuracy roll'''
    guard = no_guard(attacker, defender)
    if defender[_POK_VOL_STATUS] & _VOLSTATUS_PROTECT and move[_FLAGS_PROTECT]:
        return _MOVEOUTCOME_PROTECTED
    if (
        not guard
        and defender[_POK_VOL_STATUS] & _VOLSTATUS_SEMI_INVULNERABLE
        and not semi_inv_reaches(move[_MOVE_ID], defender)
        and move[_MOVE_ID] != _MOVENAME_BIDE
        and move[_MOVE_TARGET] not in TARGET_SELF_SIDE
        and move[_MOVE_TARGET] not in SIDE_OR_FIELD_TARGETS
    ):
        return _MOVEOUTCOME_SEMI_INVULNERABLE
    # Dream Eater only affects a sleeping target without a Substitute, before the accuracy roll
    # ([SD] gen4 onTryImmunity, [pp] effect 8)
    if move[_MOVE_ID] == _MOVENAME_DREAM_EATER and (
        defender[_POK_STATUS] != _STATUS_SLEEP or has_substitute(defender)
    ):
        return _MOVEOUTCOME_INVULNERABLE
    if move[_MOVE_ID] == _MOVENAME_STRUGGLE or move[_MOVE_ID] == _MOVENAME_BIDE:
        return _MOVEOUTCOME_HIT
    # Sturdy makes OHKO moves fail, Mold Breaker ignores it (pokeplatinum BtlCmd_TryOHKOMove)
    if (
        move[_MOVE_OH_KO]
        and defender[_POK_AB_ID] == _ABILITYNAMES_STURDY
        and ignorable_ability(defender, attacker)
    ):
        reveal_ability(defender)
        return _MOVEOUTCOME_INVULNERABLE
    if move[_MOVE_ID] == _MOVENAME_FAKE_OUT and attacker[_POK_TURNS_ACTIVE] > 1:
        return _MOVEOUTCOME_MISS
    move_acc = move[_MOVE_ACCURACY]
    ab_a = attacker[_POK_AB_WHEN]
    ab_d = defender[_POK_AB_WHEN]
    if ab_a & _ABILITYACTIVATION_ON_TRY_MOVE or ab_d & _ABILITYACTIVATION_ON_TRY_MOVE:
        move_acc = ab_on_try_move(move, attacker, defender, move_acc)
    # Gen IV Blizzard can't miss in hail
    if move[_MOVE_ID] == _MOVENAME_BLIZZARD and weather == _WEATHER_HAIL:
        move_acc = -1
    # Thunder can't miss in rain and has 50 accuracy in sun, before the stages (pokeplatinum
    # CheckMoveHitOverrides, CheckMoveHitAccuracy)
    if move[_MOVE_ID] == _MOVENAME_THUNDER:
        if weather == _WEATHER_RAIN:
            move_acc = -1
        elif weather == _WEATHER_SUN:
            move_acc = 50

    if move[_MOVE_TARGET] not in TARGET_SELF_SIDE and not move[_MOVE_IGNORE_IMMUNITY]:
        m_type = normalized_type(attacker, move)
        def_t1, def_t2 = matchup_types(m_type, defender, gravity, is_scrappy(attacker))
        eff, _ = get_type_effectiveness(m_type, def_t1, def_t2)
        if eff == 0:
            return _MOVEOUTCOME_INVULNERABLE
        if m_type == _TYPES_GROUND and levitates(defender, attacker, gravity):
            reveal_ability(defender)
            return _MOVEOUTCOME_INVULNERABLE
        if m_type == _TYPES_GROUND and magnet_risen(defender):
            return _MOVEOUTCOME_INVULNERABLE

    # OHKO moves hit on accuracy + the level difference out of 100 and always fail from a lower
    # level. Stat stages, Gravity and the accuracy abilities don't apply (pokeplatinum
    # BtlCmd_TryOHKOMove). No Guard skips the roll, not the level check
    #TODO: Lock-On
    if move[_MOVE_OH_KO]:
        if attacker[_POK_LEVEL] < defender[_POK_LEVEL]:
            return _MOVEOUTCOME_INVULNERABLE
        if guard:
            return _MOVEOUTCOME_HIT
        hit = move[_MOVE_ACCURACY] + attacker[_POK_LEVEL] - defender[_POK_LEVEL]
        if random.randint(0, 99) < hit:
            return _MOVEOUTCOME_HIT
        return _MOVEOUTCOME_MISS

    if move_acc == -1:
        return _MOVEOUTCOME_HIT
    if move_acc == 0:
        return _MOVEOUTCOME_MISS
    if guard:
        return _MOVEOUTCOME_HIT

    accuracy = move_accuracy(move, attacker, defender, move_acc, weather, gravity, target_moved)
    # Micle's boost is used up by the next accuracy roll, OHKO and always-hit moves keep it
    attacker[_POK_VOL_STATUS2] &= ~_VOLSTATUS2_MICLE

    if accuracy == 100 or random.randint(1,100) <= accuracy:
        return _MOVEOUTCOME_HIT
    return _MOVEOUTCOME_MISS


@njit
def calculate_crit(attacker, defender, move=None, def_side=0):
    """Returns a boolean if the move passed the crit check based on Gen IV mechanics.
    def_side is the defender's Field.SIDE_COND, Lucky Chant there blocks crits. Battle Armor and
    Shell Armor block them unless the attacker has Mold Breaker. Focus Energy +2, the move's ratio,
    Scope Lens +1, Super Luck +1, Lucky Punch (Chansey) / Stick (Farfetch'd) +2 (pokeplatinum
    BattleSystem_CalcCriticalMulti)"""
    if (
        defender[_POK_AB_WHEN] & _ABILITYACTIVATION_ON_CRITICAL
        and ignorable_ability(defender, attacker)
    ):
        return False
    if def_side & _SIDECONDITION_LUCKY_CHANT:
        return False

    if move is not None and move[_MOVE_WILL_CRIT]:
        return True

    stage = 0
    if attacker[_POK_VOL_STATUS] & _VOLSTATUS_FOCUS_ENERGY:
        stage += 2

    if move is not None:
        crit_ratio = move[_MOVE_CRIT_RATIO]
        if crit_ratio > 1:
            stage += (crit_ratio - 1)
    effect = attacker[_ITEM_HOLD_EFFECT]
    if effect == _HOLDEFFECT_CRITRATE_UP:
        stage += 1
    elif effect == _HOLDEFFECT_CHANSEY_CRITRATE_UP and attacker[_POK_ID] == CHANSEY:
        stage += 2
    elif effect == _HOLDEFFECT_FARFETCHD_CRITRATE_UP and attacker[_POK_ID] == FARFETCHD:
        stage += 2
    if attacker[_POK_AB_ID] == _ABILITYNAMES_SUPER_LUCK:
        stage += 1

    if stage <= 0:
        return random.getrandbits(4) == 0      # 1/16 (6.25%)
    elif stage == 1:
        return random.getrandbits(3) == 0      # 1/8  (12.5%)
    elif stage == 2:
        return random.getrandbits(2) == 0      # 1/4  (25.0%)
    elif stage == 3:
        return random.randint(1, 3) == 1       # 1/3  (33.33%)
    else:
        return random.getrandbits(1) == 0      # 1/2  (50.0%)


# ── Switch handling ──────────────────────────────────────────────────────────────

@njit
def reset_switch_out(pok):
    """If a pokemon swithces out it needs to reset these conditions"""
    # Natural Cure, or its own ability forbids the status Worry Seed let in
    # (pokeplatinum BtlCmd_TryRestoreStatusOnSwitch)
    if pok[_POK_CURRENT_HP] > 0 and pok[_POK_STATUS] and (
        pok[_POK_AB_ID] == _ABILITYNAMES_NATURAL_CURE
        or (pok[_POK_BASE_AB_ID] and ability_forbids_status(pok[_POK_BASE_AB_ID], pok[_POK_STATUS]))
    ):
        cure_status(pok)
    pok[_POK_ATTACK_STAT_STAGE : _POK_EVASION_STAT_STAGE + 1] = 0
    pok[_POK_VOL_STATUS] = 0
    pok[_POK_BADLY_POISON] = 1 if pok[_POK_STATUS] == _STATUS_TOXIC else 0
    pok[_POK_DMG_TAKEN] = 0
    pok[_POK_CHARGE_RECHARGE] = 0
    pok[_POK_TURNS_ACTIVE] = 0
    pok[_POK_LOCKED_MOVE] = -1
    pok[_POK_CONSEC_COUNT] = 0
    pok[_POK_PROTECT_COUNT] = 0
    pok[_POK_YAWN_TURNS] = 0
    pok[_POK_TRAP_TURNS] = 0
    pok[_POK_TAUNT_TURNS] = 0
    pok[_POK_ENCORE_TURNS] = 0
    pok[_POK_DISABLE_TURNS] = 0
    pok[_POK_UPROAR_TURNS] = 0
    pok[_POK_LAST_MOVE_ID] = 0
    pok[_POK_PERISH_TURNS] = 0
    pok[_POK_CALLED_MOVE] = 0
    pok[_POK_MIRROR_MOVE] = 0
    pok[_POK_SEMI_INV_MOVE] = 0
    pok[_POK_METRONOME_COUNT] = 0
    # Power Trick ends: back to its own Attack and Defense
    if pok[_POK_VOL_STATUS2] & _VOLSTATUS2_POWER_TRICK:
        swap_atk_def(pok)
    pok[_POK_VOL_STATUS2] = 0
    pok[_POK_SUB_HP] = 0
    pok[_POK_CHOICE_LOCK] = 0
    pok[_POK_EMBARGO_TURNS] = 0
    pok[_POK_HEAL_BLOCK_TURNS] = 0
    pok[_POK_MAGNET_RISE_TURNS] = 0
    pok[_POK_RAMPAGE_TURNS] = 0
    pok[_POK_LAST_RESORT] = 0
    pok[_POK_STOCKPILE] = 0
    refresh_item(pok)
    pok[_POK_AB_KNOWN] = 0
    # Worry Seed's ability lasts until the Pokemon leaves the field
    if pok[_POK_BASE_AB_ID]:
        pok[_POK_AB_ID:_POK_AB_ID + AB_LEN] = ABILITY_TABLE[pok[_POK_BASE_AB_ID]]
        pok[_POK_BASE_AB_ID] = 0
    # Castform leaves in its normal form, pokeplatinum reloads the party's types
    if pok[_POK_AB_ID] == _ABILITYNAMES_FORECAST:
        pok[_POK_TYPE1] = _TYPES_NORMAL
        pok[_POK_TYPE2] = 0


@njit
def side_base(is_mine):
    """Field.SIDE_COND of my side or the opponent's, the per-side slots follow it"""
    return _FIELD_MY_SIDE_COND if is_mine else _FIELD_OPP_SIDE_COND


@njit
def pressure_pp(mv, defender):
    """
    After the move's PP is taken: one more while the defender is an alive Pressure holder, unless
    the move aims at the user's side (pokeplatinum BattleControllerPlayer_DecrementPP). Metronome,
    Mirror Move and Copycat target the user, so they don't pay it
    """
    if (
        mv[_MOVE_PP] > 0
        and defender[_POK_CURRENT_HP] > 0
        and defender[_POK_AB_ID] == _ABILITYNAMES_PRESSURE
        and mv[_MOVE_TARGET] not in TARGET_SELF_SIDE
    ):
        mv[_MOVE_PP] -= 1


@njit
def is_grounded(pok, gravity=False):
    """Spikes and Toxic Spikes only reach a grounded Pokemon, Ingrain switches Levitate off (not the
    Flying type, pokeplatinum BattlerIsGrounded). Magnet Rise keeps it up even under Ingrain"""
    if gravity or grounded_by_item(pok):
        return True
    return not (
        pok[_POK_TYPE1] == _TYPES_FLYING
        or pok[_POK_TYPE2] == _TYPES_FLYING
        or levitates(pok, pok)
        or pok[_POK_MAGNET_RISE_TURNS] > 0
    )


@njit
def is_trapped(pok, foe, gravity=False):
    """
    pokeplatinum Battler_IsTrapped: Shed Shell always lets the holder switch, bind and Ingrain
    trap it, and a living foe's Shadow Tag (unless it has Shadow Tag too), Magnet Pull (Steel
    types) or Arena Trap (grounded) do
    """
    if pok[_ITEM_HOLD_EFFECT] == _HOLDEFFECT_SWITCH:
        return False
    if pok[_POK_VOL_STATUS] & (_VOLSTATUS_INGRAIN | _VOLSTATUS_PARTIALLY_TRAPPED):
        return True
    if foe[_POK_CURRENT_HP] <= 0:
        return False
    foe_ab = foe[_POK_AB_ID]
    if foe_ab == _ABILITYNAMES_SHADOW_TAG:
        return pok[_POK_AB_ID] != _ABILITYNAMES_SHADOW_TAG
    if foe_ab == _ABILITYNAMES_MAGNET_PULL:
        return pok[_POK_TYPE1] == _TYPES_STEEL or pok[_POK_TYPE2] == _TYPES_STEEL
    if foe_ab == _ABILITYNAMES_ARENA_TRAP:
        return is_grounded(pok, gravity)
    return False


@njit
def _toxic_spikes(pok, battle_array, side, weather):
    """
    A grounded Poison type absorbs the spikes, otherwise 1 layer poisons and 2 badly poison.
    Steel types, Immunity, Leaf Guard in sun, Safeguard and a status already there block it
    """
    if pok[_POK_TYPE1] == _TYPES_POISON or pok[_POK_TYPE2] == _TYPES_POISON:
        battle_array[side] &= ~_SIDECONDITION_TOXIC_SPIKES
        battle_array[side + SIDE_TOXIC_SPIKES] = 0
        return
    if (
        pok[_POK_STATUS] != 0
        or pok[_POK_TYPE1] == _TYPES_STEEL
        or pok[_POK_TYPE2] == _TYPES_STEEL
    ):
        return
    if ability_blocks_status(pok, pok, _STATUS_POISON, weather):
        reveal_ability(pok)
        return
    # A Substitute Baton Pass brought in, after the ability (pokeplatinum subscript_poison)
    if has_substitute(pok):
        return
    if battle_array[side] & _SIDECONDITION_SAFEGUARD:
        return
    if battle_array[side + SIDE_TOXIC_SPIKES] >= 2:
        pok[_POK_STATUS] = _STATUS_TOXIC
        pok[_POK_BADLY_POISON] = 1
    else:
        pok[_POK_STATUS] = _STATUS_POISON


@njit
def stealth_rock_damage(pok):
    """Max HP / 32 up to / 2 by Rock effectiveness, at least 1"""
    eff, den = get_type_effectiveness(_TYPES_ROCK, pok[_POK_TYPE1], pok[_POK_TYPE2])
    return max(1, pok[_POK_MAX_HP] * eff // (den * STEALTH_ROCK_DIV))


@njit
def spikes_damage(pok, layers):
    """Max HP / 8, / 6 or / 4 for 1, 2 or 3 layers, at least 1 (pokeplatinum BtlCmd_CheckSpikes)"""
    return max(1, pok[_POK_MAX_HP] // ((5 - layers) * 2))


@njit
def _hazard_hit(pok, dmg):
    """A hazard's damage. Returns True if it fainted pok"""
    mark_hurt(pok)
    if dmg >= pok[_POK_CURRENT_HP]:
        pok[_POK_CURRENT_HP] = 0
        return True
    pok[_POK_CURRENT_HP] -= dmg
    if pok[_ITEM_WHEN] & _ITEMACTIVATION_ON_RECEIVE_DAMAGE:
        item_on_rdmg(pok)
    return False


@njit
def apply_hazards(pok, battle_array, side):
    """
    Entry hazards of the side pok just came into (pokeplatinum subscript_hazards_check):
    Toxic Spikes, Spikes, then Stealth Rock. Magic Guard skips them all, only the spikes need the
    Pokemon grounded
    """
    cond = battle_array[side]
    if cond == 0 or pok[_POK_AB_ID] == _ABILITYNAMES_MAGIC_GUARD:
        return
    grounded = is_grounded(pok, battle_array[_FIELD_GRAVITY_TURNS] > 0)
    if cond & _SIDECONDITION_TOXIC_SPIKES and grounded:
        _toxic_spikes(pok, battle_array, side, effective_weather(battle_array))
    if cond & _SIDECONDITION_SPIKES and grounded:
        if _hazard_hit(pok, spikes_damage(pok, battle_array[side + SIDE_SPIKES])):
            return
    if cond & _SIDECONDITION_STEALTH_ROCK:
        _hazard_hit(pok, stealth_rock_damage(pok))


@njit
def trace(pok, foe):
    """
    Trace copies the foe's ability until pok switches out (Worry Seed's mechanism). It fails on a
    fainted foe and on Trace, Multitype and Forecast, then tries again when the next foe comes in
    (pokeplatinum ChooseTraceTarget, traceAnnounced stays FALSE). Returns True if it copied
    """
    if (
        pok[_POK_AB_ID] != _ABILITYNAMES_TRACE
        or pok[_POK_CURRENT_HP] <= 0
        or foe[_POK_CURRENT_HP] <= 0
        or foe[_POK_AB_ID] in TRACE_FAILS
    ):
        return False
    if pok[_POK_BASE_AB_ID] == 0:
        pok[_POK_BASE_AB_ID] = pok[_POK_AB_ID]
    pok[_POK_AB_ID:_POK_AB_ID + AB_LEN] = ABILITY_TABLE[foe[_POK_AB_ID]]
    return True


@njit
def intimidate(foe, source, foe_side):
    """Intimidate lowers the foe's Attack by one unless it fainted, Mist covers its side (foe_side
    is its Field.SIDE_COND), it's behind a Substitute or its ability blocks the drop (pokeplatinum
    subscript_intimidate)"""
    if (
        foe[_POK_CURRENT_HP] > 0
        and not has_substitute(foe)
        and not foe_side & _SIDECONDITION_MIST
        and not stat_drop_blocked(foe, source, _POK_ATTACK_STAT_STAGE)
    ):
        foe[_POK_ATTACK_STAT_STAGE] = max(-6, foe[_POK_ATTACK_STAT_STAGE] - 1)


@njit
def download(pok, foe):
    """Download: +1 Sp. Atk if the foe's Defense is at least its Sp. Def (both with their stages),
    otherwise +1 Attack, nothing against a fainted foe or one behind a Substitute (pokeplatinum
    SWITCH_IN_CHECK_STATE_DOWNLOAD skips it, so both sums are 0)"""
    if foe[_POK_CURRENT_HP] <= 0 or has_substitute(foe):
        return
    defense = apply_stat_stage(foe[_POK_DEFENSE], foe[_POK_DEFENSE_STAT_STAGE], False)
    sp_def = apply_stat_stage(
        foe[_POK_SPECIAL_DEFENSE], foe[_POK_SPECIAL_DEFENSE_STAT_STAGE], False
    )
    if defense >= sp_def:
        pok[_POK_SPECIAL_ATTACK_STAT_STAGE] = min(6, pok[_POK_SPECIAL_ATTACK_STAT_STAGE] + 1)
    else:
        pok[_POK_ATTACK_STAT_STAGE] = min(6, pok[_POK_ATTACK_STAT_STAGE] + 1)


@njit
def weather_ability(pok, battle_array):
    """
    Drizzle, Drought, Sand Stream and Snow Warning set their weather with no turn count, so it
    lasts until another one replaces it. Only the same weather already set by an ability stops
    them, silently (pokeplatinum SWITCH_IN_CHECK_STATE_WEATHER_ABILITIES, subscript_drizzle)
    """
    for ability, weather in WEATHER_ABILITIES:
        if pok[_POK_AB_ID] == ability:
            if battle_array[_FIELD_WEATHER] == weather and battle_array[_FIELD_WEATHER_DURATION] == 0:
                return
            battle_array[_FIELD_WEATHER] = weather
            battle_array[_FIELD_WEATHER_DURATION] = 0
            reveal_ability(pok)
            return


@njit
def anticipation_shudders(pok, foe, gravity, weather=0):
    """
    One of the foe's moves is super effective on pok, or is an OHKO move from a foe at pok's
    level or higher. A status move is never super effective, the fixed-damage moves and Counter /
    Mirror Coat don't count, and an immune move doesn't either (pokeplatinum
    SWITCH_IN_CHECK_STATE_ANTICIPATION, ApplyTypeChart on CalcMoveType: the move's data type, the
    foe's Normalize or Weather Ball's weather type)
    """
    if foe[_POK_CURRENT_HP] <= 0:
        return False
    for i in range(4):
        mv = foe[OFFSET_MOVE + i * MOVE_STRIDE:OFFSET_MOVE + (i + 1) * MOVE_STRIDE]
        if not mv[_MOVE_ID] or mv[_MOVE_DAMAGE]:
            continue
        m_type = slot_move_type(foe, mv, weather)
        def_t1, def_t2 = matchup_types(m_type, pok, gravity, is_scrappy(foe))
        eff, den = get_type_effectiveness(m_type, def_t1, def_t2)
        if eff == 0:
            continue
        if eff > den and mv[_MOVE_CATEGORY] != _MOVECATEGORY_STATUS:
            return True
        if mv[_MOVE_OH_KO] and pok[_POK_LEVEL] <= foe[_POK_LEVEL]:
            return True
    return False


@njit
def switch_in_ability(pok, foe, battle_array, is_mine):
    """
    pok's own switch-in abilities, in pokeplatinum's order after Trace: the weather abilities,
    Intimidate, Download, then Slow Start, Mold Breaker and Pressure, whose messages tell the AI
    my ability (BattleMessage_AbilityTag). So do Anticipation's shudder and Forewarn's alert,
    when they show up; Frisk's message doesn't name the ability.
    is_mine: pok is on my side
    """
    if not pok[_POK_AB_WHEN] & _ABILITYACTIVATION_ON_SWITCH_IN:
        return
    ability = pok[_POK_AB_ID]
    if ability == _ABILITYNAMES_INTIMIDATE:
        intimidate(foe, pok, battle_array[side_base(not is_mine)])
    elif ability == _ABILITYNAMES_DOWNLOAD:
        download(pok, foe)
    elif ability in SWITCH_IN_MESSAGE_ABS:
        reveal_ability(pok)
    elif ability == _ABILITYNAMES_ANTICIPATION:
        if anticipation_shudders(
            pok, foe, battle_array[_FIELD_GRAVITY_TURNS] > 0, effective_weather(battle_array)
        ):
            reveal_ability(pok)
    elif ability == _ABILITYNAMES_FOREWARN:
        # It names one of the foe's moves whenever a foe is out
        if foe[_POK_CURRENT_HP] > 0:
            reveal_ability(pok)
    else:
        weather_ability(pok, battle_array)


@njit
def recover_status_by_ability(pok):
    """
    Cures a status, confusion or Attract that pok's current ability forbids, reachable through
    Trace or a Mold Breaker foe (pokeplatinum BattleSystem_RecoverStatusByAbility, run for every
    active on switch-in and after every move). Unburden there marks a holder that still has its
    item: losing it later doubles its speed
    """
    if pok[_POK_CURRENT_HP] <= 0:
        return
    ability = pok[_POK_AB_ID]
    if pok[_POK_STATUS] and ability_forbids_status(ability, pok[_POK_STATUS]):
        cure_status(pok)
    elif ability == _ABILITYNAMES_OWN_TEMPO:
        pok[_POK_VOL_STATUS] &= ~_VOLSTATUS_CONFUSION
    elif ability == _ABILITYNAMES_OBLIVIOUS:
        pok[_POK_VOL_STATUS] &= ~_VOLSTATUS_ATTRACT
    elif ability == _ABILITYNAMES_UNBURDEN and pok[_ITEM_ID]:
        pok[_POK_VOL_STATUS2] |= _VOLSTATUS2_CAN_UNBURDEN


@njit
def healing_wish_heal(pok, battle_array, side):
    """
    Healing Wish's replacement: full HP and no status, even if it was already healthy, after the
    hazards and only for one that survived them (pokeplatinum subscript_healing_wish, Showdown gen4
    onEntryHazardPriority -1). side is pok's Field.SIDE_COND
    """
    if not battle_array[side] & _SIDECONDITION_HEALING_WISH:
        return
    battle_array[side] &= ~_SIDECONDITION_HEALING_WISH
    pok[_POK_CURRENT_HP] = pok[_POK_MAX_HP]
    cure_status(pok)


@njit
def switch_in(attacker, defender, battle_array, is_mine, foe_entering=False):
    """
    What happens when a pokemon switches in so, abilities, hazards.
    is_mine: attacker is coming into my side
    foe_entering: the defender comes in at the same time and runs its own switch_in right after
    (start of battle, both replacing a fainted Pokemon), so its Trace doesn't try again here
    """
    # The foe's infatuation was with the Pokemon that just left
    defender[_POK_VOL_STATUS] &= ~_VOLSTATUS_ATTRACT
    # and so was the bind
    defender[_POK_VOL_STATUS] &= ~_VOLSTATUS_PARTIALLY_TRAPPED
    # and Mirror Move can't copy a move from a Pokemon that left
    defender[_POK_MIRROR_MOVE] = 0
    # Gen IV: a Pokemon whose item was knocked off loses any item it got back (Recycle)
    if attacker[_POK_ITEM_KNOCKED_OFF] and attacker[_ITEM_ID]:
        clear_item(attacker)
    apply_hazards(attacker, battle_array, side_base(is_mine))
    if attacker[_POK_CURRENT_HP] <= 0:
        return
    healing_wish_heal(attacker, battle_array, side_base(is_mine))
    # pokeplatinum runs Trace for every active before the other switch-in abilities, so a copied
    # Intimidate or Download fires. A Trace already out that found nothing copies the newcomer
    traced = trace(attacker, defender)
    foe_traced = not foe_entering and trace(defender, attacker)
    if traced or foe_traced:
        # The Trace message names both abilities (pokeplatinum BattleMessage_AbilityTag)
        reveal_ability(attacker)
        reveal_ability(defender)
    switch_in_ability(attacker, defender, battle_array, is_mine)
    if foe_traced:
        switch_in_ability(defender, attacker, battle_array, not is_mine)
    # pokeplatinum SWITCH_IN_CHECK_STATE_FORM_CHANGE, after the weather abilities
    forecast_actives(battle_array)
    # pokeplatinum SWITCH_IN_CHECK_STATE_FORBIDDEN_STATUS
    recover_status_by_ability(attacker)
    recover_status_by_ability(defender)
    # A status from the hazards, a drop from Intimidate (pokeplatinum
    # SWITCH_IN_CHECK_STATE_HELD_ITEM_STATUS, every active)
    status_item(attacker)
    status_item(defender)


# ── In-battle status / contact effects ────────────────────────────────────────────

@njit
def flinch_checker(move, attacker, defender, second=False, chance=-1):
    """
    Returns true or false if move has a flinch percent and it should flinch. Inner Focus and Shield
    Dust stop it unless the attacker has Mold Breaker, Serene Grace doubles the chance
    (pokeplatinum subscript_flinch_mon, BtlCmd_CheckEffectActivation). chance: King's Rock's, in
    place of the move's
    """
    if ignorable_ability(defender, attacker) and (
        defender[_POK_AB_ID] == _ABILITYNAMES_INNER_FOCUS
        or defender[_POK_AB_ID] == _ABILITYNAMES_SHIELD_DUST
    ):
        # Only Fake Out prints Inner Focus's message (pokeplatinum subscript_flinch_mon)
        if defender[_POK_AB_ID] == _ABILITYNAMES_INNER_FOCUS and move[_MOVE_ID] == _MOVENAME_FAKE_OUT:
            reveal_ability(defender)
        return False
    if chance < 0:
        chance = move[_SEC_CHANCE2] if second else move[_SEC_CHANCE]
    if attacker[_POK_AB_ID] == _ABILITYNAMES_SERENE_GRACE:
        chance *= 2
    if random.randint(1,100) <= chance:
        return True
    return False


@njit
def kings_rock(move, attacker):
    """
    King's Rock and Razor Fang give the moves on Showdown gen4's list a flinch chance (the item's
    param), rolled per hit like a secondary effect, so Serene Grace doubles it
    """
    return (
        attacker[_ITEM_HOLD_EFFECT] == _HOLDEFFECT_SOMETIMES_FLINCH
        and KINGS_ROCK_MOVES[move[_MOVE_ID]]
    )


@njit
def thaw(attacker, move, defender):
    """Check if a move thaws"""
    if normalized_type(attacker, move) == _TYPES_FIRE:
        defender[_POK_STATUS] = 0
        return True
    return False


@njit
def confusion(pok):
    """
    If the pokemon gets hit by confusion, it's kinda the same as ps_core,
    but since the damage calculation is different and it doesn't have a "move"
    Better have a own thing to apply everything
    Magic Guard doesn't stop it, Focus Band can hold on (pokeplatinum subscript_hurt_self_in_confusion)
    """
    damage = calculate_damage_confusion(pok)
    if focus_band(pok, damage) and damage >= pok[_POK_CURRENT_HP]:
        damage = pok[_POK_CURRENT_HP] - 1
    pok[_POK_CURRENT_HP] = max(0, (pok[_POK_CURRENT_HP]-damage))
    if damage > 0:
        mark_hurt(pok)
    if pok[_ITEM_WHEN] & _ITEMACTIVATION_ON_RECEIVE_DAMAGE:
        item_on_rdmg(pok)


@njit
def _contact_damage(pok, dmg):
    """Rough Skin / Aftermath / Liquid Ooze damage to the attacker, its berry can still trigger"""
    mark_hurt(pok)
    if dmg < pok[_POK_CURRENT_HP]:
        pok[_POK_CURRENT_HP] -= dmg
        if pok[_ITEM_WHEN] & _ITEMACTIVATION_ON_RECEIVE_DAMAGE:
            item_on_rdmg(pok)
    else:
        pok[_POK_CURRENT_HP] = 0


@njit
def on_hit_abilities(attacker, defender, move, dealt, weather):
    """
    The defender's abilities that react to a contact hit, after the hit's recoil, drain and
    secondary effect, the KO hit included (pokeplatinum BattleSystem_TriggerAbilityOnHit). The
    attacker has to be alive. Statuses from them ignore Safeguard
    """
    def_ab = defender[_POK_AB_ID]
    if (
        not move[_FLAGS_CONTACT]
        or attacker[_POK_CURRENT_HP] <= 0
        or not (
            defender[_POK_AB_WHEN] & _ABILITYACTIVATION_ON_CONTACT
            or def_ab == _ABILITYNAMES_AFTERMATH
        )
    ):
        return
    atk_ab = attacker[_POK_AB_ID]
    if def_ab == _ABILITYNAMES_AFTERMATH:
        if (
            defender[_POK_CURRENT_HP] <= 0
            and atk_ab != _ABILITYNAMES_MAGIC_GUARD
            and atk_ab != _ABILITYNAMES_DAMP
        ):
            _contact_damage(attacker, max(1, attacker[_POK_MAX_HP] // 4))
            reveal_ability(defender)
        return
    if dealt <= 0:
        return
    if def_ab == _ABILITYNAMES_ROUGH_SKIN:
        if atk_ab != _ABILITYNAMES_MAGIC_GUARD:
            _contact_damage(attacker, max(1, attacker[_POK_MAX_HP] // 8))
            reveal_ability(defender)
        return
    if def_ab == _ABILITYNAMES_CUTE_CHARM:
        if (
            defender[_POK_CURRENT_HP] > 0
            and not attacker[_POK_VOL_STATUS] & _VOLSTATUS_ATTRACT
            and random.randint(0, 9) < 3
        ):
            infatuate(attacker, defender)
            if attacker[_POK_VOL_STATUS] & _VOLSTATUS_ATTRACT:
                reveal_ability(defender)
        return

    if def_ab == _ABILITYNAMES_STATIC:
        status = _STATUS_PARALYSIS
    elif def_ab == _ABILITYNAMES_FLAME_BODY:
        status = _STATUS_BURN
    elif def_ab == _ABILITYNAMES_POISON_POINT:
        status = _STATUS_POISON
    elif def_ab == _ABILITYNAMES_EFFECT_SPORE:
        status = -1
    else:
        return
    if attacker[_POK_STATUS] != 0 or random.randint(0, 9) >= 3:
        return
    if status == -1:
        status = EFFECT_SPORE_STATUSES[random.randint(0, 2)]
    apply_status(move, attacker, weather, defender, False, 0, status)
    # "X's Static paralyzed Y!" only when the status lands (pokeplatinum, SIDE_EFFECT_TYPE_ABILITY)
    if attacker[_POK_STATUS]:
        reveal_ability(defender)


@njit
def sticky_barb_transfer(attacker, defender, move, dealt):
    """
    A contact hit that dealt damage to the Sticky Barb holder moves the barb to an attacker with no
    item, the KO hit included. Not on Knock Off, not to a Pokemon whose item was knocked off, Sticky Hold
    doesn't stop it (pokeplatinum BattleSystem_TriggerHeldItemOnHit, Showdown stickybarb)
    """
    if (
        defender[_ITEM_HOLD_EFFECT] == _HOLDEFFECT_DMG_USER_CONTACT_XFR
        and dealt > 0
        and move[_FLAGS_CONTACT]
        and move[_MOVE_ID] != _MOVENAME_KNOCK_OFF
        and attacker[_POK_CURRENT_HP] > 0
        and not attacker[_ITEM_ID]
        and not attacker[_POK_ITEM_KNOCKED_OFF]
    ):
        switch_items(attacker, defender)


@njit
def _super_effective(attacker, defender, move, gravity):
    """The hit's type is super effective on the defender"""
    m_type = normalized_type(attacker, move)
    def_type1, def_type2 = matchup_types(m_type, defender, gravity, is_scrappy(attacker))
    effectiveness, _ = get_type_effectiveness(m_type, def_type1, 0)
    effectiveness2 = 2
    if def_type2:
        effectiveness2, _ = get_type_effectiveness(m_type, def_type2, 0)
    return effectiveness * effectiveness2 > 4


@njit
def on_hit_berries(attacker, defender, move, dealt, gravity=False):
    """
    The defender's berries that react to a hit on it, per hit after the contact abilities (Showdown
    onHit / onDamagingHit). Enigma heals 1/4 of max HP after a super effective hit the holder
    survives, only from a move with a damage roll (Showdown's typeMod is never set for fixed damage
    or OHKO moves). Jaboca (physical) and Rowap (special) cost a live attacker 1/8 of its max HP,
    even from a fainted holder; Magic Guard stops it (pokeplatinum TriggerHeldItemOnHit)
    """
    effect = defender[_ITEM_HOLD_EFFECT]
    if dealt <= 0:
        return
    if effect == _HOLDEFFECT_HP_RESTORE_SE:
        if (
            defender[_POK_CURRENT_HP] <= 0
            or move[_MOVE_DAMAGE]
            or move[_MOVE_OH_KO]
            or move[_MOVE_ID] == _MOVENAME_STRUGGLE
            or not _super_effective(attacker, defender, move, gravity)
        ):
            return
        max_hp = defender[_POK_MAX_HP]
        heal = max(1, max_hp // defender[_ITEM_EFFECT_PARAM])
        defender[_POK_CURRENT_HP] = min(max_hp, defender[_POK_CURRENT_HP] + heal)
    elif (
        (effect == _HOLDEFFECT_RECOIL_PHYSICAL and move[_MOVE_CATEGORY] == _MOVECATEGORY_PHYSICAL)
        or (effect == _HOLDEFFECT_RECOIL_SPECIAL and move[_MOVE_CATEGORY] == _MOVECATEGORY_SPECIAL)
    ):
        if attacker[_POK_CURRENT_HP] <= 0 or attacker[_POK_AB_ID] == _ABILITYNAMES_MAGIC_GUARD:
            return
        damage = max(1, attacker[_POK_MAX_HP] // defender[_ITEM_EFFECT_PARAM])
        defender[_POK_CONSUMED_ITEM] = defender[_ITEM_ID]
        clear_item(defender)
        _contact_damage(attacker, damage)
        return
    else:
        return
    defender[_POK_CONSUMED_ITEM] = defender[_ITEM_ID]
    clear_item(defender)


@njit
def after_move_hit_items(attacker, move, dealt, hit_pok):
    """
    Once per move, after Destiny Bond, for a move whose hit reached the Pokemon, not only its
    Substitute (pokeplatinum AFTER_MOVE_HIT_STATE_SHELL_BELL / LIFE_ORB, SYSCTL_MOVE_HIT).
    Shell Bell heals 1/8 of the damage dealt, the Substitute's included. Life Orb costs 1/10 of max
    HP, only after a move with a base power: fixed damage, OHKO, Counter and co. skip it (Showdown
    gen4 lifeorb onBasePower). Magic Guard skips it, a fainted holder gets neither
    """
    if not hit_pok or attacker[_POK_CURRENT_HP] <= 0:
        return
    effect = attacker[_ITEM_HOLD_EFFECT]
    if effect == _HOLDEFFECT_HP_RESTORE_ON_DMG:
        max_hp = attacker[_POK_MAX_HP]
        if dealt > 0 and attacker[_POK_CURRENT_HP] < max_hp:
            heal = max(1, dealt // attacker[_ITEM_EFFECT_PARAM])
            attacker[_POK_CURRENT_HP] = min(max_hp, attacker[_POK_CURRENT_HP] + heal)
    elif (
        effect == _HOLDEFFECT_HP_DRAIN_ON_ATK
        and attacker[_POK_AB_ID] != _ABILITYNAMES_MAGIC_GUARD
        and not move[_MOVE_OH_KO]
        and not move[_MOVE_DAMAGE]
    ):
        apply_recoil(attacker, max(1, attacker[_POK_MAX_HP] // 10))


# ── The turn-blocking gate ───────────────────────────────────────────────────────

@njit
def _tick_charge_if_blocked(attacker):
    """
    When something blocks the move outright (sleep, freeze, ...), the charge/recharge
    counter still ticks down so a two-turn move doesn't stall out waiting extra turns
    once the status finally lifts.
    """
    if attacker[_POK_CHARGE_RECHARGE] > 0 and not attacker[_POK_VOL_STATUS] & _VOLSTATUS_BIDE:
        attacker[_POK_CHARGE_RECHARGE] -= 1


@njit
def early_returns(attacker, defender, idx: int, flinch: bool, move, gravity=False):
    """Early returns to see if an attack goes through or not"""
    """
    Priorities, highest go first:
    Recharge:  11
    Sleep:     10
    Freeze:    10
    Truant:    9
    Flinch:    8
    Disable:   7
    Gravity:   6
    Taunt:     5
    Confusion: 3
    Attract:   2
    Paralysis: 1
    Default:   0

    A blocked turn (sleep, Truant, flinch, confusion self-hit, infatuation, full paralysis) ends charge
    moves and locks via unlock_move, Bide pauses instead, freeze keeps the lock.
    Destiny Bond ends as soon as the user tries to move again, even if the turn is blocked.
    Grudge too (pokeplatinum CHECK_STATUS_START).
    """
    attacker[_POK_VOL_STATUS] &= ~_VOLSTATUS_DESTINY_BOND
    attacker[_POK_VOL_STATUS2] &= ~_VOLSTATUS2_GRUDGE
    # A recharge lasts only this turn: whatever blocks the turn first uses it up (pokeplatinum
    # clears VOLATILE_CONDITION_RECHARGING at the next turn's setup either way)
    recharging = attacker[_POK_CHARGE_RECHARGE] < 0
    if recharging:
        attacker[_POK_CHARGE_RECHARGE] = 0
        unlock_move(attacker)
    # A sleeping Pokemon wakes up when it tries to move during an uproar
    if attacker[_POK_STATUS] == _STATUS_SLEEP and sleep_blocked(attacker, defender):
        attacker[_POK_STATUS] = 0
        attacker[_POK_SLEEP_COUNTER] = 0
    atker_status = attacker[_POK_STATUS]
    # Check for Sleep and if the attacker wakes up
    # The counter drops first and it wakes at 0, so 2-5 sleeps 1-4 turns. Early Bird drops it by 2
    # (pokeplatinum CHECK_STATUS_STATE_SLEEP)
    if atker_status == _STATUS_SLEEP:
        # A rampage keeps counting, the next turn's setup ends it (pokeplatinum SetupNextTurn)
        if attacker[_POK_RAMPAGE_TURNS] == 0:
            unlock_move(attacker)
        attacker[_POK_SLEEP_COUNTER] -= 2 if attacker[_POK_AB_ID] == _ABILITYNAMES_EARLY_BIRD else 1
        if attacker[_POK_SLEEP_COUNTER] > 0:
            return not move[_MOVE_SLEEP_USABLE]
        attacker[_POK_SLEEP_COUNTER] = 0
        attacker[_POK_STATUS] = 0
    # Freeze
    if atker_status == _STATUS_FREEZE:
        # A defrost move thaws its user when the roll fails (pokeplatinum CHECK_STATUS_STATE_SELF_THAW)
        if freeze() and not move[_FLAGS_DEFROST]:
            _tick_charge_if_blocked(attacker)
            return True
        attacker[_POK_STATUS] = 0
    # Truant, its script unlocks the move choice (pokeplatinum subscript_loafing_around), a
    # rampage's lock is separate and keeps counting
    if truant_loafs(attacker):
        if attacker[_POK_RAMPAGE_TURNS] == 0:
            unlock_move(attacker)
        return True
    # Recharge, after Truant (pokeplatinum CHECK_STATUS_STATE_RECHARGING)
    if recharging:
        return True
    # Flinch. A Pokemon focusing for Focus Punch can't flinch, it loses its focus instead
    # (Showdown gen4 focuspunch condition onTryAddVolatile)
    if flinch and idx >= 2 and move[_MOVE_ID] != _MOVENAME_FOCUS_PUNCH:
        unlock_move(attacker)
        if attacker[_POK_AB_ID] == _ABILITYNAMES_STEADFAST:
            attacker[_POK_SPEED_STAT_STAGE] = min(6, attacker[_POK_SPEED_STAT_STAGE] + 1)
        return True
    # Disable and Taunt, a move picked before they landed fails
    if (
        attacker[_POK_VOL_STATUS] & _VOLSTATUS_DISABLE
        and move[_MOVE_ID] == attacker[
            OFFSET_MOVE + (attacker[_POK_DISABLE_TURNS] & SLOT_MASK) * MOVE_STRIDE + _MOVE_ID
        ]
    ):
        unlock_move(attacker)
        return True
    # Gravity, a move it stops picked before it was set fails (Showdown onBeforeMovePriority 6)
    if gravity and move[_FLAGS_GRAVITY]:
        unlock_move(attacker)
        return True
    # Heal Block, after Gravity (pokeplatinum CHECK_STATUS_STATE_HEAL_BLOCK)
    if heal_block_stops(attacker, move[_MOVE_ID]):
        unlock_move(attacker)
        return True
    if attacker[_POK_VOL_STATUS] & _VOLSTATUS_TAUNT and move[_MOVE_CATEGORY] == _MOVECATEGORY_STATUS:
        unlock_move(attacker)
        return True
    # Confusion
    if attacker[_POK_VOL_STATUS] & _VOLSTATUS_CONFUSION:
        attacker[_POK_CONFUSION_COUNTER] -= 1
        if attacker[_POK_CONFUSION_COUNTER] > 0:
            if random.getrandbits(1):
                unlock_move(attacker)
                confusion(attacker)
                return True
        else:
            attacker[_POK_VOL_STATUS] -= _VOLSTATUS_CONFUSION
    # Attract, immobilized by love half of the time
    if attacker[_POK_VOL_STATUS] & _VOLSTATUS_ATTRACT and random.getrandbits(1):
        unlock_move(attacker)
        return True
    # Paralysis — Magic Guard still allows getting PAR, it just blocks the roll
    # into full paralysis (Gen 4 specific)
    if (
        atker_status == _STATUS_PARALYSIS
        and paralysis()
        and attacker[_POK_AB_ID] != _ABILITYNAMES_MAGIC_GUARD
    ):
        unlock_move(attacker)
        return True
    # Charging poke e.g. solarbeam, bide
    if attacker[_POK_CHARGE_RECHARGE] > 0 and not attacker[_POK_VOL_STATUS] & _VOLSTATUS_BIDE:
        attacker[_POK_CHARGE_RECHARGE] -= 1
        if attacker[_POK_CHARGE_RECHARGE] > 0:
            return True
    # Bide has a special case since it pauses the counter if any of the above is true,
    # so it needs to be below them
    if attacker[_POK_VOL_STATUS] & _VOLSTATUS_BIDE:
        attacker[_POK_CHARGE_RECHARGE] -= 1
        if attacker[_POK_CHARGE_RECHARGE] > 0:
            return True
    return False


@njit
def counter_fails(attacker, move, idx):
    """
    Counter, Mirror Coat and Metal Burst fail when the user moved first or took no damage this
    turn. Checked after the PP is spent, like a move that fails (pokeplatinum
    BEFORE_MOVE_STATE_DECREMENT_PP runs before the move's script, BtlCmd_TryMetalBurst)
    """
    return (
        (
            move[_MOVE_DAMAGE] == _DAMAGESOURCES_COUNTER
            or move[_MOVE_DAMAGE] == _DAMAGESOURCES_MAGIC_COAT
            or move[_MOVE_DAMAGE] == _DAMAGESOURCES_METAL_BURST
        )
        and (idx == 1 or attacker[_POK_DMG_TAKEN] == 0)
    )


@njit
def target_acted(idx, target_action):
    """The target used its turn before this move: it moved first, or switched or used an item
    (pokeplatinum DEFENDER_ACTION == BATTLE_CONTROL_MOVE_END, Showdown gen4 queue.willMove)"""
    return idx >= 2 or target_action < 0


@njit
def sucker_punch_fails(defender, move, idx, target_action):
    """
    Sucker Punch fails if the target already acted, picked a status move or is recharging, after the
    PP is spent (Showdown gen4 onTry, pokeplatinum BtlCmd_TrySuckerPunch). Struggle counts as an attack
    """
    if move[_MOVE_ID] != _MOVENAME_SUCKER_PUNCH:
        return False
    if target_acted(idx, target_action) or defender[_POK_CHARGE_RECHARGE] < 0:
        return True
    if target_action == 10:  # Struggle
        return False
    return defender[OFFSET_MOVE + target_action * MOVE_STRIDE + _MOVE_CATEGORY] == _MOVECATEGORY_STATUS


@njit
def lost_focus(attacker, move):
    """Focus Punch fails if a damaging move hit the user this turn, a hit on its Substitute doesn't
    count (pokeplatinum effect 0170, BattleControllerPlayer_UpdateHP)"""
    return (
        move[_MOVE_ID] == _MOVENAME_FOCUS_PUNCH
        and attacker[_POK_VOL_STATUS2] & _VOLSTATUS2_DAMAGED_BY_MOVE != 0
    )


@njit
def turn_order_doubles(attacker, move, idx, target_action):
    """
    Payback doubles when the target already acted (pokeplatinum BtlCmd_CalcPaybackPower), Revenge
    and Avalanche when a damaging move hit the user this turn (BtlCmd_CalcRevengePowerMul). Both
    double the base power before Charge and Technician
    """
    move_id = move[_MOVE_ID]
    if move_id == _MOVENAME_PAYBACK:
        return target_acted(idx, target_action)
    if move_id == _MOVENAME_REVENGE or move_id == _MOVENAME_AVALANCHE:
        return attacker[_POK_VOL_STATUS2] & _VOLSTATUS2_DAMAGED_BY_MOVE != 0
    return False


@njit
def endeavor_fails(attacker, defender, move):
    """Endeavor fails unless the target has more HP than the user, before the hit check
    (pokeplatinum effect 0189, Showdown gen4 onTry)"""
    return (
        move[_MOVE_DAMAGE] == _DAMAGESOURCES_ENDEAVOR
        and attacker[_POK_CURRENT_HP] >= defender[_POK_CURRENT_HP]
    )


# ── Battle start & end-of-turn residuals ───────────────────────────────────────

def start_of_battle(array):
    """Select the two first pokemon of each team and does ability effects on switch in
    for each following their speed"""
    # Order of entry is in account for things like Drought against Drizzle
    current_pokemon = array[
            (array[_FIELD_MY_POK] * POK_LEN):((array[_FIELD_MY_POK]+1) * POK_LEN)
        ]
    current_opp = array[
            ((array[_FIELD_OPP_POK]+6) * POK_LEN):((array[_FIELD_OPP_POK]+7) * POK_LEN)
        ]
    weather = effective_weather(array)
    p1_speed, p2_speed = check_speed(current_pokemon, current_opp, weather)
    speed_tie = 0
    if p1_speed == p2_speed:
        speed_tie = random.getrandbits(1)
    if p1_speed > p2_speed or speed_tie:
        switch_in(current_pokemon, current_opp, array, True, True)
        switch_in(current_opp, current_pokemon, array, False)
    else:
        switch_in(current_opp, current_pokemon, array, False, True)
        switch_in(current_pokemon, current_opp, array, True)
    current_pokemon[_POK_TURNS] = 1
    current_opp[_POK_TURNS] = 1
    current_opp[_POK_TURNS_ACTIVE] = 1
    current_pokemon[_POK_TURNS_ACTIVE] = 1
    array[_FIELD_TURN] = 1


@njit
def heal_weather(self_, weather, underground=False):
    """
    Heals after turns, from items, abilities and volatile conditions.
    Rain Dish 1/16 and Dry Skin 1/8 in rain, Ice Body 1/16 in hail unless underground or underwater, at least 1
    (pokeplatinum BtlCmd_EndOfTurnWeatherEffect)
    """
    heal = 0
    max_hp = self_[_POK_MAX_HP]
    ability = self_[_POK_AB_ID]
    if weather == _WEATHER_RAIN:
        if ability == _ABILITYNAMES_RAIN_DISH:
            heal = max(1, max_hp // 16)
        elif ability == _ABILITYNAMES_DRY_SKIN:
            heal = max(1, max_hp // 8)
    elif weather == _WEATHER_HAIL and ability == _ABILITYNAMES_ICE_BODY and not underground:
        heal = max(1, max_hp // 16)

    if heal:
        hp_missing = max_hp - self_[_POK_CURRENT_HP]
        heal = min(heal,hp_missing)
        self_[_POK_CURRENT_HP] += heal
        if heal:
            reveal_ability(self_)


@njit
def on_residual(pokemon, _switch_in):
    """
    On residual abilities at end of turn
    """
    abi = pokemon[_POK_AB_ID]
    if abi == _ABILITYNAMES_SPEED_BOOST and not _switch_in:
        pokemon[_POK_SPEED_STAT_STAGE] = min(6, pokemon[_POK_SPEED_STAT_STAGE] + 1)
    # Gen IV is 30% (pokeplatinum BattleSystem_TriggerTurnEndAbility)
    elif abi == _ABILITYNAMES_SHED_SKIN and pokemon[_POK_STATUS] and random.randint(0, 9) < 3:
        cure_status(pokemon)
        reveal_ability(pokemon)


@njit
def weather_dmg(pokemon, weather, max_hp:int):
    """
    Weather damage calc
    """
    type1 = pokemon[_POK_TYPE1]
    type2 = pokemon[_POK_TYPE2]
    abi = pokemon[_POK_AB_ID]
    if weather == _WEATHER_SANDSTORM:
        if (
            type1 not in SANDSTORM_IM
            and type2 not in SANDSTORM_IM
            and abi != _ABILITYNAMES_SAND_VEIL
        ):
            return max(1, max_hp//16)
        return 0
    # Ice Body heals in hail instead (heal_weather)
    if weather == _WEATHER_HAIL:
        if (
            type1 != _TYPES_ICE and type2!= _TYPES_ICE
            and abi != _ABILITYNAMES_SNOW_CLOAK and abi != _ABILITYNAMES_ICE_BODY
        ):
            return max(1, max_hp//16)
        return 0
    if weather == _WEATHER_SUN:
        if abi == _ABILITYNAMES_SOLAR_POWER or abi == _ABILITYNAMES_DRY_SKIN:
            return max(1, max_hp//8)
        return 0
    return 0


# ── Trainer items, drain, struggle ──────────────────────────────────────────────

@njit
def trainer_ai_items(pok, item):
    """
    Usage of potions, full heals and x specials
    """
    cur_hp = pok[_POK_CURRENT_HP]
    max_hp = pok[_POK_MAX_HP]
    if item == _POTIONS_POTION:
        pok[_POK_CURRENT_HP] = min(max_hp, cur_hp+20)
    elif item == _POTIONS_SUPER_POTION:
        pok[_POK_CURRENT_HP] = min(max_hp, cur_hp+50)
    elif item == _POTIONS_HYPER_POTION:
        pok[_POK_CURRENT_HP] = min(max_hp, cur_hp+200)
    elif item == _POTIONS_FULL_RESTORE:
        pok[_POK_CURRENT_HP] = max_hp
        pok[_POK_STATUS] = 0
        pok[_POK_BADLY_POISON] = 0
    elif item == _POTIONS_FULL_HEAL:
        pok[_POK_STATUS] = 0
        pok[_POK_BADLY_POISON] = 0
    elif item == _POTIONS_X_DEFEND:
        pok[_POK_DEFENSE_STAT_STAGE] = min(6, pok[_POK_DEFENSE_STAT_STAGE] + 1)
    elif item == _POTIONS_X_SPECIAL:
        pok[_POK_SPECIAL_ATTACK_STAT_STAGE] = min(6, pok[_POK_SPECIAL_ATTACK_STAT_STAGE] + 1)
    elif item == _POTIONS_X_SPEED:
        pok[_POK_SPEED_STAT_STAGE] = min(6, pok[_POK_SPEED_STAT_STAGE] + 1)


@njit
def big_root(pok, heal):
    """
    A Big Root holder's drain, Leech Seed, Ingrain and Aqua Ring heal x(100+30)/100, before
    Liquid Ooze turns it into damage (pokeplatinum HOLD_EFFECT_LEECH_BOOST in
    subscript_drain_half_damage_dealt and the other heal subscripts)
    """
    if pok[_ITEM_HOLD_EFFECT] == _HOLDEFFECT_LEECH_BOOST:
        return heal * (100 + pok[_ITEM_EFFECT_PARAM]) // 100
    return heal


@njit
def drain(pok, defender, move, dmg):
    """
    Drain calculation and application. A Liquid Ooze target hurts the drainer by the same amount
    instead, a Magic Guard drainer gets nothing (pokeplatinum subscript_drain_half_damage_dealt)
    """
    if pok[_POK_CURRENT_HP] <= 0:
        return
    drain_pct = move[_MOVE_DRAIN]
    heal = (dmg*drain_pct)//4
    if heal == 0:
        heal = 1
    heal = big_root(pok, heal)
    if defender[_POK_AB_ID] == _ABILITYNAMES_LIQUID_OOZE:
        if pok[_POK_AB_ID] != _ABILITYNAMES_MAGIC_GUARD:
            _contact_damage(pok, heal)
        return
    # Heal Block stops the heal after the Liquid Ooze check
    if heal_blocked(pok):
        return
    pok[_POK_CURRENT_HP] = min(pok[_POK_CURRENT_HP]+heal, pok[_POK_MAX_HP])


@njit
def struggle(attacker, defender, rec=True, def_side=0, weather=0):
    """
    Struggle damage to the defender, plus recoil to the attacker. rec=False skips
    the recoil application — used by rollout heuristics that only want a damage
    estimate without mutating the attacker's HP. def_side is the defender's Field.SIDE_COND
    """
    crit = calculate_crit(attacker, defender, None, def_side)
    damage = struggle_damage(attacker, defender, crit, def_side, weather)
    if rec:
        apply_recoil(attacker, struggle_recoil(attacker))
    return damage


@njit
def struggle_damage(attacker, defender, crit, def_side=0, weather=0):
    """Struggle's damage with the crit already rolled, so the battle can pass it to Anger Point"""
    atk_is_simple = attacker[_POK_AB_ID] == _ABILITYNAMES_SIMPLE
    def_is_simple = (
        defender[_POK_AB_ID] == _ABILITYNAMES_SIMPLE and ignorable_ability(defender, attacker)
    )
    atk_stage = attacker[_POK_ATTACK_STAT_STAGE]
    def_stage = defender[_POK_DEFENSE_STAT_STAGE]
    level = attacker[_POK_LEVEL]

    atk_stage, def_stage = unaware_stages(attacker, defender, atk_stage, def_stage)
    if crit:
        def_stage = min(def_stage, 0)
        atk_stage = max(atk_stage, 0)

    raw_attack = item_attack(attacker, attacker[_POK_ATTACK])
    atk_ab = attacker[_POK_AB_ID]
    is_guts = atk_ab == _ABILITYNAMES_GUTS
    if is_guts and attacker[_POK_STATUS] != 0:
        raw_attack = (raw_attack * 3) // 2
    elif atk_ab in DOUBLE_ATK_AB:
        raw_attack *= 2
    elif slow_start_active(attacker):
        raw_attack //= 2
    elif atk_ab == _ABILITYNAMES_HUSTLE:
        raw_attack = (raw_attack * 3) // 2
    elif atk_ab == _ABILITYNAMES_FLOWER_GIFT and weather == _WEATHER_SUN:
        raw_attack = (raw_attack * 3) // 2

    attack = apply_stat_stage(raw_attack, atk_stage, atk_is_simple)
    raw_defense = ab_modify_def(
        attacker, defender, item_defense(defender, defender[_POK_DEFENSE]), True, weather
    )
    defense = apply_stat_stage(raw_defense, def_stage, def_is_simple)

    # Base damage formula for Struggle with power 50. It's typeless, so no type item
    power = item_power(attacker, _TYPES_TYPELESS, _MOVECATEGORY_PHYSICAL, 50)
    power = rivalry_power(attacker, defender, power)
    damage = attack * power * (level * 2 // 5 + 2) // defense // 50

    # Burn
    if attacker[_POK_STATUS] == _STATUS_BURN and not is_guts:
        damage //= 2

    damage = screen_damage(_MOVECATEGORY_PHYSICAL, _MOVENAME_STRUGGLE, def_side, crit, damage)

    # Adding 2 after the above
    damage += 2

    if crit:
        damage *= crit_multiplier(attacker)
    # Struggle runs the normal damage command, so Life Orb boosts it (pokeplatinum BtlCmd_CalcDamage)
    damage = life_orb_damage(attacker, damage)

    return (damage * MULTIPLIERS[random.getrandbits(4)]) // 100


@njit
def natural_gift(pok, move):
    """
    Natural Gift takes its type and power from the held berry and uses it up, even if it misses
    later. Returns False (move fails) without a berry
    """
    power = pok[_ITEM_NATURAL_GIFT_POWER]
    if power == 0:
        return False
    move[_MOVE_TYPE] = pok[_ITEM_NATURAL_GIFT_TYPE]
    move[_MOVE_POWER] = power
    pok[_POK_CONSUMED_ITEM] = pok[_ITEM_ID]
    clear_item(pok)
    return True


@njit
def struggle_recoil(pok):
    """Struggle recoil, a quarter of max HP that ignores Rock Head and Magic Guard"""
    return max(1, pok[_POK_MAX_HP] // 4)


@njit
def move_recoil(move, dealt):
    """Recoil from a recoil move (Take Down), from the HP the target actually lost. Move.RECOIL
    is the divisor (pokeplatinum subscript_recoil_1_4 / 1_3 / 1_2)"""
    if dealt <= 0:
        return 0
    return max(1, dealt // move[_MOVE_RECOIL])


@njit
def apply_recoil(pok, recoil):
    """Recoil damage to the attacker"""
    if recoil <= 0:
        return
    mark_hurt(pok)
    if recoil >= pok[_POK_CURRENT_HP]:
        pok[_POK_CURRENT_HP] = 0
        return
    pok[_POK_CURRENT_HP] -= recoil
    if pok[_ITEM_WHEN] & _ITEMACTIVATION_ON_RECEIVE_DAMAGE:
        item_on_rdmg(pok)


# ── Healing, Worry Seed and Perish Song ─────────────────────────────────────────

@njit
def heal_move(pok, move_id, weather):
    """
    Recover, Soft-Boiled, Milk Drink, Slack Off, Heal Order and Roost heal 1/2 of max HP. Synthesis,
    Moonlight and Morning Sun 1/2 with no weather, 2/3 in sun and 1/4 in rain, sand or hail
    (pokeplatinum BtlCmd_WeatherHPRecovery). Rounded down, at least 1, nothing at full HP. Returns
    True if it healed
    """
    max_hp = pok[_POK_MAX_HP]
    if pok[_POK_CURRENT_HP] >= max_hp:
        return False
    heal = max_hp // 2
    if move_id in SUN_HEAL_MOVES:
        if weather == _WEATHER_SUN:
            heal = max_hp * 20 // 30
        elif weather in HEAL_QUARTER_WEATHER:
            heal = max_hp // 4
    pok[_POK_CURRENT_HP] = min(max_hp, pok[_POK_CURRENT_HP] + max(1, heal))
    return True


@njit
def stockpile_count(pok):
    """How many times pok stockpiled since it came in"""
    return pok[_POK_STOCKPILE] & STOCKPILE_COUNT_MASK


@njit
def stockpile(pok):
    """
    Stockpile fails at 3. Otherwise the count goes up, even with both stats at +6, then Defense and
    Sp. Def +1, each remembered only if it went up (pokeplatinum subscript_stockpile)
    """
    if stockpile_count(pok) >= STOCKPILE_MAX:
        return
    pok[_POK_STOCKPILE] += 1
    if pok[_POK_DEFENSE_STAT_STAGE] < 6:
        pok[_POK_DEFENSE_STAT_STAGE] += 1
        pok[_POK_STOCKPILE] += STOCKPILE_DEF_STEP
    if pok[_POK_SPECIAL_DEFENSE_STAT_STAGE] < 6:
        pok[_POK_SPECIAL_DEFENSE_STAT_STAGE] += 1
        pok[_POK_STOCKPILE] += STOCKPILE_SPDEF_STEP


@njit
def release_stockpile(pok):
    """
    Spit Up and Swallow empty the stockpile and take back the stages it gave, down to -6 at most
    (pokeplatinum effects 0161 and 0162, OPCODE_SUB_TO_ZERO). Returns the count it had
    """
    packed = pok[_POK_STOCKPILE]
    count = packed & STOCKPILE_COUNT_MASK
    def_gained = (packed // STOCKPILE_DEF_STEP) & STOCKPILE_COUNT_MASK
    spdef_gained = (packed // STOCKPILE_SPDEF_STEP) & STOCKPILE_COUNT_MASK
    pok[_POK_DEFENSE_STAT_STAGE] = max(-6, pok[_POK_DEFENSE_STAT_STAGE] - def_gained)
    pok[_POK_SPECIAL_DEFENSE_STAT_STAGE] = max(-6, pok[_POK_SPECIAL_DEFENSE_STAT_STAGE] - spdef_gained)
    pok[_POK_STOCKPILE] = 0
    return count


@njit
def spit_up_move(move, pok):
    """Spit Up with the power pok's stockpile would give it, every other move as is (for the
    rollout's estimates)"""
    if move[_MOVE_ID] != _MOVENAME_SPIT_UP:
        return move
    mv = move.copy()
    mv[_MOVE_POWER] = SPIT_UP_POWER * stockpile_count(pok)
    return mv


@njit
def swallow(pok):
    """
    Swallow fails with nothing stockpiled. Otherwise it empties the stockpile first, then heals
    max HP / 4, / 2 or all of it for 1, 2 or 3, at least 1, nothing at full HP (pokeplatinum effect
    0162, subscript_recover_hp)
    """
    count = release_stockpile(pok)
    if count == 0 or pok[_POK_CURRENT_HP] >= pok[_POK_MAX_HP]:
        return
    heal = max(1, pok[_POK_MAX_HP] // (1 << (STOCKPILE_MAX - count)))
    pok[_POK_CURRENT_HP] = min(pok[_POK_MAX_HP], pok[_POK_CURRENT_HP] + heal)


@njit
def future_hit_lands(move, attacker, defender, weather, gravity=False):
    """
    The Future Sight / Doom Desire hit at the end of the turn: No Guard always hits, a
    semi-invulnerable target dodges, else the accuracy roll with the attacking side's active's
    stages. No Protect, type or ability check (pokeplatinum subscript_future_sight_damage,
    CheckMoveHit)
    """
    if no_guard(attacker, defender):
        return True
    if defender[_POK_VOL_STATUS] & _VOLSTATUS_SEMI_INVULNERABLE:
        return False
    return kick_hits(move, attacker, defender, weather, gravity)


@njit
def heal_blocked(pok):
    """Heal Block is up: its moves can't be used and drain, Leech Seed, Ingrain, Aqua Ring and
    Present don't heal (pokeplatinum healBlockTurns)"""
    return pok[_POK_VOL_STATUS] & _VOLSTATUS_HEAL_BLOCK != 0


@njit
def heal_block_stops(pok, move_id):
    """Heal Block stops this move (pokeplatinum Move_HealBlocked)"""
    return heal_blocked(pok) and move_id in HEAL_BLOCK_MOVES


@njit
def heal_block_count(pok):
    """End of turn: Heal Block counts down (pokeplatinum MON_COND_CHECK_STATE_HEAL_BLOCK)"""
    if not heal_blocked(pok):
        return
    pok[_POK_HEAL_BLOCK_TURNS] -= 1
    if pok[_POK_HEAL_BLOCK_TURNS] <= 0:
        pok[_POK_HEAL_BLOCK_TURNS] = 0
        pok[_POK_VOL_STATUS] &= ~_VOLSTATUS_HEAL_BLOCK


@njit
def refresh(pok):
    """Refresh cures burn, poison and paralysis"""
    if pok[_POK_STATUS] in REFRESH_CURES:
        pok[_POK_STATUS] = 0
        pok[_POK_BADLY_POISON] = 0


@njit
def worry_seed(target):
    """
    The target's ability becomes Insomnia until it switches out and a sleeping target wakes up
    right away (Showdown). Fails on Truant and Multitype. Returns True if the ability changed
    """
    if target[_POK_AB_ID] in WORRY_SEED_FAILS:
        return False
    if target[_POK_BASE_AB_ID] == 0:
        target[_POK_BASE_AB_ID] = target[_POK_AB_ID]
    target[_POK_AB_ID:_POK_AB_ID + AB_LEN] = ABILITY_TABLE[_ABILITYNAMES_INSOMNIA]
    if target[_POK_STATUS] == _STATUS_SLEEP:
        target[_POK_STATUS] = 0
        target[_POK_SLEEP_COUNTER] = 0
    return True


@njit
def _start_perish(pok, user):
    """Skips one that already has it, a fainted one, a Soundproof one (unless the user has Mold
    Breaker) and, like Showdown, a semi-invulnerable one"""
    if (
        pok[_POK_CURRENT_HP] <= 0
        or pok[_POK_VOL_STATUS] & (_VOLSTATUS_PERISH_SONG | _VOLSTATUS_SEMI_INVULNERABLE)
        or (
            pok[_POK_AB_ID] == _ABILITYNAMES_SOUNDPROOF
            and user[_POK_AB_ID] != _ABILITYNAMES_MOLD_BREAKER
        )
    ):
        return
    pok[_POK_VOL_STATUS] |= _VOLSTATUS_PERISH_SONG
    pok[_POK_PERISH_TURNS] = PERISH_SONG_TURNS


@njit
def perish_song(user, foe):
    """Perish Song gives both actives a count of 3 (pokeplatinum BtlCmd_TryPerishSong)"""
    _start_perish(user, user)
    _start_perish(foe, user)


@njit
def perish_count(pok):
    """
    End of turn, after every other residual: a count of 0 faints the Pokemon, else it drops by 1
    (pokeplatinum SIDE_COND_CHECK_STATE_PERISH_SONG). It faints at the 4th end of turn
    """
    if pok[_POK_CURRENT_HP] <= 0 or not pok[_POK_VOL_STATUS] & _VOLSTATUS_PERISH_SONG:
        return
    if pok[_POK_PERISH_TURNS] == 0:
        pok[_POK_VOL_STATUS] &= ~_VOLSTATUS_PERISH_SONG
        pok[_POK_CURRENT_HP] = 0
    else:
        pok[_POK_PERISH_TURNS] -= 1


# ── Move-calling moves ────────────────────────────────────────────────────────────

@njit
def metronome_move(pok):
    """
    pokeplatinum BtlCmd_Metronome: a uniform pick from the pool, rerolled while it's one of the
    user's own moves
    """
    while True:
        move_id = METRONOME_POOL[random.randrange(len(METRONOME_POOL))]
        known = False
        for i in range(4):
            if pok[OFFSET_MOVE + i * MOVE_STRIDE + _MOVE_ID] == move_id:
                known = True
        if not known:
            return move_id


@njit
def copycat_move(battle_array):
    """
    The last move anyone used (the outer one for a called move), 0 if there's none, it calls
    other moves or Metronome can't call it (pokeplatinum BtlCmd_TryCopycat)
    """
    last = battle_array[_FIELD_LAST_MOVE]
    if last == 0 or last in INVOKER_MOVES or last in METRONOME_FORBIDDEN:
        return 0
    return last


@njit
def nature_power_move(battle_array):
    """The battle terrain's move (pokeplatinum BtlCmd_GetTerrainMove)"""
    return NATURE_POWER_MOVES[min(battle_array[_FIELD_TERRAIN], _TERRAIN_SPECIAL)]


@njit
def secret_power_move(mv, battle_array):
    """Secret Power's 30% secondary from the battle terrain (pokeplatinum sTerrainSideEffect): plain or
    sand accuracy -1, grass or puddle sleep, mountain or cave flinch, snow or ice freeze, water Attack
    -1, building or special paralysis, Great Marsh Speed -1, bridge evasion -1"""
    terrain = min(battle_array[_FIELD_TERRAIN], _TERRAIN_SPECIAL)
    sp = mv.copy()
    sp[_SEC_STATUS] = 0
    if terrain == _TERRAIN_PLAIN or terrain == _TERRAIN_SAND:
        sp[_SEC_BOOST_ACC] = -1
    elif terrain == _TERRAIN_GRASS or terrain == _TERRAIN_PUDDLE:
        sp[_SEC_STATUS] = _STATUS_SLEEP
    elif terrain == _TERRAIN_MOUNTAIN or terrain == _TERRAIN_CAVE:
        sp[_SEC_VOL_STATUS] = _VOLSTATUS_FLINCH
    elif terrain == _TERRAIN_SNOW or terrain == _TERRAIN_ICE:
        sp[_SEC_STATUS] = _STATUS_FREEZE
    elif terrain == _TERRAIN_WATER:
        sp[_SEC_BOOST_ATK] = -1
    elif terrain == _TERRAIN_GREAT_MARSH:
        sp[_SEC_BOOST_SPEED] = -1
    elif terrain == _TERRAIN_BRIDGE:
        sp[_SEC_BOOST_EV] = -1
    else:
        sp[_SEC_STATUS] = _STATUS_PARALYSIS
    return sp


@njit
def called_move(pok, move_id, battle_array):
    """The move Metronome, Mirror Move, Copycat, Nature Power or Sleep Talk calls, 0 if it fails"""
    if move_id == _MOVENAME_SLEEP_TALK:
        return sleep_talk_move(pok, battle_array[_FIELD_GRAVITY_TURNS] > 0)
    if move_id == _MOVENAME_METRONOME:
        return metronome_move(pok)
    if move_id == _MOVENAME_MIRROR_MOVE:
        return pok[_POK_MIRROR_MOVE]
    if move_id == _MOVENAME_COPYCAT:
        return copycat_move(battle_array)
    return nature_power_move(battle_array)


@njit
def mirror_record(move, defender, called):
    """
    A move that hit the foe is what its Mirror Move copies. A move that can't be mirrored, or one
    another move called, leaves nothing to copy (Showdown: the user doesn't know it)
    """
    if called or not move[_FLAGS_MIRROR] or move[_MOVE_ID] in CANT_MIRROR_MOVES:
        defender[_POK_MIRROR_MOVE] = 0
    else:
        defender[_POK_MIRROR_MOVE] = move[_MOVE_ID]
