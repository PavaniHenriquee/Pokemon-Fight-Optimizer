"""Helpers that are only needed in the engine directory"""
import random
import numpy as np
from Utils.jit import njit
from Utils.helper import get_type_effectiveness
from Engine.speed import check_speed, slow_start_active, quick_claw
from Engine.status_calc import  freeze, paralysis, sleep_blocked, SLOT_MASK
from Engine.status_calc import (
    apply_status, infatuate, cure_status, ability_blocks_status, ability_forbids_status,
    stat_drop_blocked
)
from Engine.damage_calc import (
    calculate_damage_confusion, apply_stat_stage, MULTIPLIERS, matchup_types, screen_damage,
    item_power, item_attack, unaware_stages, ab_modify_def, rivalry_power, crit_multiplier,
    AIRBORNE_MOVES, HITS_AIRBORNE, HITS_UNDERGROUND, DOUBLE_ATK_AB, is_scrappy,
    METRONOME_MOVE_SHIFT, METRONOME_COUNT_MASK
)
from Engine.ability_helper import (
    ignorable_ability, levitates, reveal_ability, effective_weather, normalized_type,
)
from Models.idx_const import ITEM_LEN, POK_LEN, MOVE_STRIDE, OFFSET_MOVE, SIDE_TOXIC_SPIKES, AB_LEN
from Models.helper import TARGET_SELF_SIDE, Target
from Models.item import ITEM_TABLE
from Models.ability import ABILITY_TABLE
from Models.move import METRONOME_POOL, METRONOME_FORBIDDEN
from Models.constants import (
    _POK_STATUS, _STATUS_PARALYSIS, _POK_SPEED_STAT_STAGE, _POK_AB_WHEN,
    _WEATHER_SUN, _MOVENAME_FAKE_OUT,
    _POK_AB_ID, _MOVE_PRIORITY, _MOVE_ID, _MOVEOUTCOME_HIT, _MOVEOUTCOME_INVULNERABLE,
    _MOVEOUTCOME_MISS, _TYPES_ROCK, _TYPES_GROUND, _TYPES_STEEL, _TYPES_FIRE, _TYPES_ICE,
    _MOVENAME_EXPLOSION, _MOVENAME_SELFDESTRUCT, _MOVENAME_STRUGGLE, _WEATHER_RAIN,
    _WEATHER_SANDSTORM, _WEATHER_HAIL, _MOVE_TARGET, _MOVE_CATEGORY, _MOVE_OH_KO, _MOVE_ACCURACY,
    _MOVE_TYPE, _ABILITYNAMES_DAMP, _ABILITYNAMES_HUSTLE, _ABILITYNAMES_SAND_VEIL,
    _ABILITYNAMES_SOUNDPROOF, _ABILITYNAMES_INNER_FOCUS, _ABILITYNAMES_INTIMIDATE,
    _ABILITYNAMES_SOLAR_POWER, _ABILITYNAMES_MAGIC_GUARD, _ABILITYNAMES_STEADFAST,
    _ABILITYNAMES_POISON_POINT, _ABILITYNAMES_RAIN_DISH, _ABILITYNAMES_SPEED_BOOST,
    _MOVECATEGORY_PHYSICAL, _FLAGS_SOUND, _ABILITYACTIVATION_ON_TRY_MOVE, _ABILITYACTIVATION_ON_SWITCH_IN,
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
)


SANDSTORM_IM = (_TYPES_ROCK, _TYPES_GROUND, _TYPES_STEEL)
DAMP_IGNORES = (_MOVENAME_EXPLOSION, _MOVENAME_SELFDESTRUCT)
WEATHER_NOT_END_OF_TURN = (0, _WEATHER_RAIN)
HP_RESTORE_EFFECTS = (_HOLDEFFECT_HP_RESTORE, _HOLDEFFECT_HP_PCT_RESTORE)
METRONOME_MAX_COUNT = 10
# Pecha, Chesto, Lum and Mental Herb
STATUS_CURE_EFFECTS = (
    _HOLDEFFECT_PSN_RESTORE, _HOLDEFFECT_SLP_RESTORE, _HOLDEFFECT_STATUS_RESTORE,
    _HOLDEFFECT_HEAL_INFATUATION
)
RECORD_DAMAGE = (_DAMAGESOURCES_COUNTER, _DAMAGESOURCES_MAGIC_COAT)
# pokeplatinum BattleSystem_TriggerAbilityOnHit: RandNext % 3 picks poison, paralysis, sleep
EFFECT_SPORE_STATUSES = (_STATUS_POISON, _STATUS_PARALYSIS, _STATUS_SLEEP)
# Gravity's accuracy boost, x5/3 as 6840/4096
GRAVITY_ACC_NUM = 6840
GRAVITY_ACC_DEN = 4096
SIDE_OR_FIELD_TARGETS = (Target.ALL, Target.FOE_SIDE, Target.ALLY_TEAM)
PROTECT_COUNT_MAX = 3  # Success chance 1, 1/2, 1/4, then 1/8 from here on
# Stealth Rock takes max HP * Rock effectiveness / STEALTH_ROCK_DIV, 1/8 when neutral
STEALTH_ROCK_DIV = 8
# Synthesis heals a quarter of max HP in these weathers
HEAL_QUARTER_WEATHER = (_WEATHER_RAIN, _WEATHER_SANDSTORM, _WEATHER_HAIL)
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
# Moves that call another move
CALLER_MOVES = (_MOVENAME_METRONOME, _MOVENAME_MIRROR_MOVE, _MOVENAME_COPYCAT, _MOVENAME_NATURE_POWER)
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
    the move doesn't go through. Bide keeps its own pause rule. Uproar ends at this turn's residual
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


@njit
def move_blocked(pok, slot, gravity=False):
    """
    Disable, Encore or Taunt keep this move slot from being selected, and so does Gravity for
    its moves (PP is checked apart)
    """
    if gravity and pok[OFFSET_MOVE + slot * MOVE_STRIDE + _FLAGS_GRAVITY]:
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
def endure_damage(defender, damage):
    """Endure leaves the defender at 1 HP from a hit that would KO it, without Endure a Focus Band
    can do the same"""
    if defender[_POK_VOL_STATUS] & _VOLSTATUS_ENDURE:
        holds_on = True
    else:
        holds_on = focus_band(defender, damage)
    if holds_on and damage >= defender[_POK_CURRENT_HP]:
        return defender[_POK_CURRENT_HP] - 1
    return damage


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
def _apply_berry_effect(source, target):
    """Apply the effect of source's held item to target. target = the beneficiary, which is
    'pok' for a self-trigger, or 'attacker' for Bug Bite."""
    cur_hp = target[_POK_CURRENT_HP]
    max_hp = target[_POK_MAX_HP]
    effect = source[_ITEM_HOLD_EFFECT]
    if effect == _HOLDEFFECT_HP_RESTORE:
        cur_hp = min(cur_hp + source[_ITEM_EFFECT_PARAM], max_hp)
    elif effect == _HOLDEFFECT_HP_PCT_RESTORE:
        # Needs to be with min because of bug bite
        cur_hp = min(cur_hp + max(1, max_hp * source[_ITEM_EFFECT_PARAM] // 100), max_hp)
    elif effect in STATUS_CURE_EFFECTS:
        item_cure(effect, target)
    target[_POK_CURRENT_HP] = cur_hp


@njit
def item_cure(effect, pok):
    """
    Pecha cures poison, Chesto sleep, Lum any status and confusion, Mental Herb only Attract in
    Gen IV (pokeplatinum BattleSystem_TriggerHeldItemOnStatus, Showdown gen4 Mental Herb).
    Returns True if it cured something
    """
    status = pok[_POK_STATUS]
    if effect == _HOLDEFFECT_PSN_RESTORE:
        if status != _STATUS_POISON and status != _STATUS_TOXIC:
            return False
    elif effect == _HOLDEFFECT_SLP_RESTORE:
        if status != _STATUS_SLEEP:
            return False
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
def status_item(pok):
    """
    A status berry or Mental Herb is used up once its holder has the condition it cures. A fainted
    Pokemon doesn't use it. pokeplatinum checks after every move, on switch-in and after Yawn
    """
    effect = pok[_ITEM_HOLD_EFFECT]
    if effect in STATUS_CURE_EFFECTS and pok[_POK_CURRENT_HP] > 0 and item_cure(effect, pok):
        pok[_POK_CONSUMED_ITEM] = pok[_ITEM_ID]
        clear_item(pok)


@njit
def eat_berry(pok):
    """Self-triggered berry eat at low HP (end of turn / on receiving damage). A fainted
    Pokemon doesn't eat it (pokeplatinum BattleSystem_TriggerHeldItem)"""
    if (
        pok[_ITEM_HOLD_EFFECT] in HP_RESTORE_EFFECTS
        and 0 < pok[_POK_CURRENT_HP]
        and pok[_POK_CURRENT_HP] * 2 <= pok[_POK_MAX_HP]
    ):
        _apply_berry_effect(pok, pok)
        pok[_POK_CONSUMED_ITEM] = pok[_ITEM_ID]
        clear_item(pok)


@njit
def resist_berry(attacker, defender, move, damage, gravity=False):
    """
    A resist berry halves a super effective hit of its type and Chilan any Normal hit, then it's
    eaten. Showdown onSourceModifyDamage, a final modifier that leaves at least 1
    """
    effect = defender[_ITEM_HOLD_EFFECT]
    if damage <= 0 or (effect != _HOLDEFFECT_WEAKEN_SE and effect != _HOLDEFFECT_WEAKEN_NORMAL):
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
    """Bug Bite forces the target to eat its berry immediately; attacker gets the benefit"""
    _apply_berry_effect(defender, attacker)
    clear_item(defender)


@njit
def switch_items(pok1, pok2):
    """Switch items"""
    item_slice = slice(_ITEM_ID, _ITEM_ID + ITEM_LEN)
    item_copy = np.copy(pok1[item_slice])
    pok1[item_slice] = pok2[item_slice]
    pok2[item_slice] = item_copy


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
def knock_off(attacker, defender):
    """
    Knock Off removes the target's item. Gen IV marks the Pokemon for the rest of the battle: it
    can't get a new item and the knocked off one isn't recyclable. Sticky Hold keeps the item
    unless the user has Mold Breaker
    """
    if not defender[_ITEM_ID]:
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
    pok[_POK_CONSUMED_ITEM] = 0
    item_on_rdmg(pok)


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
def move_order(p1, my_move, p2, opp_move, p1_switch, p2_switch, weather):
    """
    Calculates who acts first this turn.
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

    p1_speed, p2_speed = check_speed(p1, p2, weather)

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
    # Same bracket (Showdown gen4): an activated Quick Claw goes first, a lone Stall holder last at
    # priority >= 0, both Quick Claws or both Stalls fall back to speed
    claw1 = quick_claw(p1)
    claw2 = quick_claw(p2)
    if claw1 != claw2:
        if claw1:
            return my_move, opp_move, 2, True
        return opp_move, my_move, 2, False
    stall1 = p1[_POK_AB_ID] == _ABILITYNAMES_STALL
    stall2 = p2[_POK_AB_ID] == _ABILITYNAMES_STALL
    if not claw1 and move1_prio >= 0 and stall1 != stall2:
        if stall2:
            return my_move, opp_move, 2, True
        return opp_move, my_move, 2, False
    speed_t = False
    if p1_speed == p2_speed and random.getrandbits(1):
        speed_t = True
    if p1_speed > p2_speed or speed_t:
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
    """Gust reaches a Pokemon in the air (Bounce), Earthquake and Magnitude one underground (Dig)"""
    if defender[_POK_SEMI_INV_MOVE] in AIRBORNE_MOVES:
        return move_id in HITS_AIRBORNE
    return move_id in HITS_UNDERGROUND


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
def move_accuracy(move, attacker, defender, move_acc, weather, gravity=False):
    """
    Hit rate out of 100 in pokeplatinum BattleControllerPlayer_CheckMoveHitAccuracy order: stages
    (Simple doubles them, Unaware ignores the foe's), Compound Eyes, Sand Veil, Snow Cloak, Hustle,
    Tangled Feet, Bright Powder / Lax Incense, Gravity. Mold Breaker ignores the defender's abilities
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

    if gravity:
        return accuracy * GRAVITY_ACC_NUM / GRAVITY_ACC_DEN
    return accuracy * 1.0


@njit
def calculate_hit_miss(move, attacker, defender, weather, gravity=False):
    '''
    The move's outcome. A move that hit can still be taken by the target's ability (Volt Absorb,
    Flash Fire, Wonder Guard...), which makes it INVULNERABLE (pokeplatinum and Showdown gen4 check
    them after the type chart and the accuracy roll)
    '''
    outcome = _hit_outcome(move, attacker, defender, weather, gravity)
    if outcome == _MOVEOUTCOME_HIT and absorb_move(move, attacker, defender, gravity):
        reveal_ability(defender)
        return _MOVEOUTCOME_INVULNERABLE
    return outcome


@njit
def _hit_outcome(move, attacker, defender, weather, gravity=False):
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

    if move[_MOVE_TARGET] not in TARGET_SELF_SIDE and not move[_MOVE_IGNORE_IMMUNITY]:
        m_type = normalized_type(attacker, move)
        def_t1, def_t2 = matchup_types(m_type, defender, gravity, is_scrappy(attacker))
        eff, _ = get_type_effectiveness(m_type, def_t1, def_t2)
        if eff == 0:
            return _MOVEOUTCOME_INVULNERABLE
        if m_type == _TYPES_GROUND and levitates(defender, attacker, gravity):
            reveal_ability(defender)
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

    accuracy = move_accuracy(move, attacker, defender, move_acc, weather, gravity)

    if accuracy == 100 or random.randint(1,100) <= accuracy:
        return _MOVEOUTCOME_HIT
    return _MOVEOUTCOME_MISS


@njit
def calculate_crit(attacker, defender, move=None, def_side=0):
    """Returns a boolean if the move passed the crit check based on Gen IV mechanics.
    def_side is the defender's Field.SIDE_COND, Lucky Chant there blocks crits. Battle Armor and
    Shell Armor block them unless the attacker has Mold Breaker. Focus Energy +2, the move's ratio,
    Scope Lens +1, Super Luck +1 (pokeplatinum BattleSystem_CalcCriticalMulti)"""
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
    if attacker[_ITEM_HOLD_EFFECT] == _HOLDEFFECT_CRITRATE_UP:
        stage += 1
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
    pok[_POK_VOL_STATUS2] = 0
    pok[_POK_AB_KNOWN] = 0
    # Worry Seed's ability lasts until the Pokemon leaves the field
    if pok[_POK_BASE_AB_ID]:
        pok[_POK_AB_ID:_POK_AB_ID + AB_LEN] = ABILITY_TABLE[pok[_POK_BASE_AB_ID]]
        pok[_POK_BASE_AB_ID] = 0


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
    Flying type, pokeplatinum BattlerIsGrounded). TODO: Magnet Rise, Iron Ball"""
    if gravity:
        return True
    return not (
        pok[_POK_TYPE1] == _TYPES_FLYING
        or pok[_POK_TYPE2] == _TYPES_FLYING
        or levitates(pok, pok)
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
def apply_hazards(pok, battle_array, side):
    """
    Entry hazards of the side pok just came into (pokeplatinum subscript_hazards_check):
    Toxic Spikes, then Stealth Rock. Magic Guard skips them all, only the spikes need the
    Pokemon grounded. TODO: Spikes damage once the move is in MoveDB
    """
    cond = battle_array[side]
    if cond == 0 or pok[_POK_AB_ID] == _ABILITYNAMES_MAGIC_GUARD:
        return
    if cond & _SIDECONDITION_TOXIC_SPIKES and is_grounded(pok, battle_array[_FIELD_GRAVITY_TURNS] > 0):
        _toxic_spikes(pok, battle_array, side, effective_weather(battle_array))
    if cond & _SIDECONDITION_STEALTH_ROCK:
        dmg = stealth_rock_damage(pok)
        mark_hurt(pok)
        if dmg >= pok[_POK_CURRENT_HP]:
            pok[_POK_CURRENT_HP] = 0
            return
        pok[_POK_CURRENT_HP] -= dmg
        if pok[_ITEM_WHEN] & _ITEMACTIVATION_ON_RECEIVE_DAMAGE:
            item_on_rdmg(pok)


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
    is its Field.SIDE_COND) or its ability blocks the drop (pokeplatinum subscript_intimidate)"""
    if (
        foe[_POK_CURRENT_HP] > 0
        and not foe_side & _SIDECONDITION_MIST
        and not stat_drop_blocked(foe, source, _POK_ATTACK_STAT_STAGE)
    ):
        foe[_POK_ATTACK_STAT_STAGE] = max(-6, foe[_POK_ATTACK_STAT_STAGE] - 1)


@njit
def download(pok, foe):
    """Download: +1 Sp. Atk if the foe's Defense is at least its Sp. Def (both with their stages),
    otherwise +1 Attack, nothing against a fainted foe (pokeplatinum
    SWITCH_IN_CHECK_STATE_DOWNLOAD)"""
    if foe[_POK_CURRENT_HP] <= 0:
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
def anticipation_shudders(pok, foe, gravity):
    """
    One of the foe's moves is super effective on pok, or is an OHKO move from a foe at pok's
    level or higher. A status move is never super effective, the fixed-damage moves and Counter /
    Mirror Coat don't count, and an immune move doesn't either (pokeplatinum
    SWITCH_IN_CHECK_STATE_ANTICIPATION, ApplyTypeChart on the move's data type or the foe's Normalize)
    """
    if foe[_POK_CURRENT_HP] <= 0:
        return False
    for i in range(4):
        mv = foe[OFFSET_MOVE + i * MOVE_STRIDE:OFFSET_MOVE + (i + 1) * MOVE_STRIDE]
        if not mv[_MOVE_ID] or mv[_MOVE_DAMAGE]:
            continue
        m_type = normalized_type(foe, mv)
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
        if anticipation_shudders(pok, foe, battle_array[_FIELD_GRAVITY_TURNS] > 0):
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
    # pokeplatinum SWITCH_IN_CHECK_STATE_FORBIDDEN_STATUS
    recover_status_by_ability(attacker)
    recover_status_by_ability(defender)
    # A status from the hazards (pokeplatinum SWITCH_IN_CHECK_STATE_HELD_ITEM_STATUS)
    status_item(attacker)


# ── In-battle status / contact effects ────────────────────────────────────────────

@njit
def flinch_checker(move, attacker, defender, second=False):
    """
    Returns true or false if move has a flinch percent and it should flinch. Inner Focus and Shield
    Dust stop it unless the attacker has Mold Breaker, Serene Grace doubles the chance
    (pokeplatinum subscript_flinch_mon, BtlCmd_CheckEffectActivation)
    """
    if ignorable_ability(defender, attacker) and (
        defender[_POK_AB_ID] == _ABILITYNAMES_INNER_FOCUS
        or defender[_POK_AB_ID] == _ABILITYNAMES_SHIELD_DUST
    ):
        # Only Fake Out prints Inner Focus's message (pokeplatinum subscript_flinch_mon)
        if defender[_POK_AB_ID] == _ABILITYNAMES_INNER_FOCUS and move[_MOVE_ID] == _MOVENAME_FAKE_OUT:
            reveal_ability(defender)
        return False
    chance = move[_SEC_CHANCE2] if second else move[_SEC_CHANCE]
    if attacker[_POK_AB_ID] == _ABILITYNAMES_SERENE_GRACE:
        chance *= 2
    if random.randint(1,100) <= chance:
        return True
    return False


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
    """
    attacker[_POK_VOL_STATUS] &= ~_VOLSTATUS_DESTINY_BOND
    # A sleeping Pokemon wakes up when it tries to move during an uproar
    if attacker[_POK_STATUS] == _STATUS_SLEEP and sleep_blocked(attacker, defender):
        attacker[_POK_STATUS] = 0
        attacker[_POK_SLEEP_COUNTER] = 0
    atker_status = attacker[_POK_STATUS]
    # Check for Sleep and if the attacker wakes up, TODO: Sleep Talk and Snore
    # The counter drops first and it wakes at 0, so 2-5 sleeps 1-4 turns. Early Bird drops it by 2
    # (pokeplatinum CHECK_STATUS_STATE_SLEEP)
    if atker_status == _STATUS_SLEEP:
        unlock_move(attacker)
        attacker[_POK_SLEEP_COUNTER] -= 2 if attacker[_POK_AB_ID] == _ABILITYNAMES_EARLY_BIRD else 1
        if attacker[_POK_SLEEP_COUNTER] > 0:
            return True
        attacker[_POK_SLEEP_COUNTER] = 0
        attacker[_POK_STATUS] = 0
    # Freeze
    if atker_status == _STATUS_FREEZE:
        # TODO: a small set of specific moves (Flame Wheel, Sacred Fire, Scald, ...)
        # auto-thaw the user on use regardless of the roll below. None exist in
        # MoveDB yet — once added, gate this on a move-id tuple in DataBase/MoveDB.py
        # (same pattern as FIRE_MOVES / FIRE_WATER_ELECTRIC), not on move[_MOVE_TYPE].
        if freeze():
            _tick_charge_if_blocked(attacker)
            return True
        attacker[_POK_STATUS] = 0
    # Truant, its script unlocks the move choice (pokeplatinum subscript_loafing_around)
    if truant_loafs(attacker):
        unlock_move(attacker)
        return True
    # Flinch
    if flinch and idx >= 2:
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
    Counter and Mirror Coat fail when the user moved first or took no damage this turn. Checked
    after the PP is spent, like a move that fails (pokeplatinum BEFORE_MOVE_STATE_DECREMENT_PP
    runs before the move's script)
    """
    return (
        (move[_MOVE_DAMAGE] == _DAMAGESOURCES_COUNTER or move[_MOVE_DAMAGE] == _DAMAGESOURCES_MAGIC_COAT)
        and (idx == 1 or attacker[_POK_DMG_TAKEN] == 0)
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
    Rain Dish 1/16 and Dry Skin 1/8 in rain, Ice Body 1/16 in hail unless underground, at least 1
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
    raw_defense = ab_modify_def(attacker, defender, defender[_POK_DEFENSE], True, weather)
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
    """Recoil from a recoil move (Take Down), from the HP the target actually lost"""
    if dealt <= 0:
        return 0
    return max(1, dealt * move[_MOVE_RECOIL] // 100)


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
    Recover heals 1/2 of max HP. Synthesis 1/2 with no weather, 2/3 in sun and 1/4 in rain, sand
    or hail (pokeplatinum BtlCmd_WeatherHPRecovery). Rounded down, at least 1, nothing at full HP
    """
    max_hp = pok[_POK_MAX_HP]
    if pok[_POK_CURRENT_HP] >= max_hp:
        return
    heal = max_hp // 2
    if move_id == _MOVENAME_SYNTHESIS:
        if weather == _WEATHER_SUN:
            heal = max_hp * 20 // 30
        elif weather in HEAL_QUARTER_WEATHER:
            heal = max_hp // 4
    pok[_POK_CURRENT_HP] = min(max_hp, pok[_POK_CURRENT_HP] + max(1, heal))


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
def called_move(pok, move_id, battle_array):
    """The move Metronome, Mirror Move, Copycat or Nature Power calls, 0 if it fails"""
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
