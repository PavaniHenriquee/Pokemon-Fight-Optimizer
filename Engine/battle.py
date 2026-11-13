"""Battle class where it follows battle flow, doing the sequence selection, start of turn, actions,
end of turn and repeat"""
import random
from Utils.jit import njit
from Engine.speed import field_speeds, trick_room_up, goes_first, has_tailwind
from Engine.engine_helper import (
    move_order, calculate_hit_miss, calculate_crit, reset_switch_out,
    flinch_checker, kings_rock, thaw, early_returns, switch_in, SIDE_OR_FIELD_TARGETS,
    on_hit_abilities, heal_weather, on_residual, trainer_ai_items, drain,
    item_on_rdmg, eat_berry_bug_bite, struggle_damage, switch_items,
    RECORD_DAMAGE, weather_dmg, WEATHER_NOT_END_OF_TURN,
    mark_hurt, unlock_move, apply_recoil, move_recoil, struggle_recoil, natural_gift,
    try_protect, endure_damage, side_base, knock_off, carry_recycle, recycle, heal_move, refresh,
    update_choice_lock,
    worry_seed, perish_song, perish_count, called_move, mirror_record, CALLER_MOVES, resist_berry,
    damp_blocks, status_item, pressure_pp, truant_loafs, metronome_count, metronome_fail,
    power_herb, sticky_hold, big_root, recover_status_by_ability, counter_fails, endeavor_fails,
    has_substitute, hit_substitute, make_substitute, sub_blocks_status_move, takeable_item,
    focus_sash_ready, sticky_barb_transfer, after_move_hit_items, on_hit_berries,
    clear_target_choice_lock, swap_items, embargo, embargo_count, fling_fails, fling_move,
    heal_blocked, heal_block_stops, heal_block_count,
    fling_throw, fling_hit, _flavor_confuse, kick_hits, record_last_resort, last_resort_works,
    secret_power_move, sucker_punch_fails, lost_focus, turn_order_doubles, confuse_boost_fails,
    stage_move_fails, belly_drum, acupressure, haze, psych_up, swap_stages, power_trick, swap_atk_def,
    status_move_fails, rest, psycho_shift, heal_bell, start_magnet_rise, end_magnet_rise,
    magnet_rise_count, stockpile, release_stockpile, swallow, future_hit_lands, SPIT_UP_POWER,
    spite, TRAP_MOVES, lock_on_count, LOCK_ON_MOVES, LOCK_ON_DURATION,
    suppress_ability, role_play, skill_swap, conversion, conversion2, camouflage, type_move_fails,
    mimic, sketch, transform,
)
from Engine.status_calc import (
    sec_effects, calculate_effects, TURNS_2_5, sleep_blocked, SLOT_MASK, SLOT_STEP,
    ability_blocks_status, cure_status, stat_changes,
)
from Engine.ability_helper import (
    reveal_ability, effective_weather, normalized_type, weather_ball_move, forecast_actives
)
from Engine.damage_calc import (
    calculate_damage, ROLLOUT_MOVES, AIRBORNE_MOVES, EXPLODE_MOVES, SEMI_INVULNERABLE_MOVES,
    NO_WEATHER_MOVES, beat_up_damage, TRIPLE_KICK_STEP, future_damage,
)
from Models.trainer_ai import sub_after_death
from Models.idx_const import (
    POK_LEN, MOVE_STRIDE, OFFSET_MOVE, SIDE_REFLECT_TURNS, SIDE_LIGHT_SCREEN_TURNS,
    SIDE_MIST_TURNS, SIDE_SAFEGUARD_TURNS, SIDE_LUCKY_CHANT_TURNS, SIDE_TOXIC_SPIKES, SIDE_TAILWIND_TURNS,
    SIDE_SPIKES, SIDE_WISH_TURNS, SIDE_FUTURE_TURNS, SIDE_FUTURE_DAMAGE, SIDE_FUTURE_MOVE,
)
from Models.helper import (
    count_party, PHYSICAL_SPECIAL, Target, TARGET_SELF_SIDE, TARGET_OPP_SIDE
)
from Models.constants import (
    _FLAGS_FUTURE_MOVE, _MOVENAME_SPIT_UP, _MOVENAME_STOCKPILE, _MOVENAME_SWALLOW, _MOVENAME_WISH,
    _SIDECONDITION_FUTURE_SIGHT, _SIDECONDITION_WISH,
    _FIELD_OPP_POK, _FIELD_MY_POK, _FIELD_AI_TOOK_DMG_LAST_TURN, _FIELD_AI_ITEM1, _FIELD_WEATHER,
    _FIELD_AI_KNOWS, _FIELD_MY_LAST_MOVE, _FIELD_OPP_ENTER_FIELD, _FIELD_TURN,
    _POK_AB_WHEN, _POK_CURRENT_HP, _POK_AB_ID, _POK_MAX_HP, _POK_STATUS, _POK_TURNS, _MOVECATEGORY_SPECIAL,
    _ABILITYACTIVATION_ON_RESIDUAL, _DAMAGESOURCES_COUNTER, _POK_TURNS_ACTIVE,
    _MOVE_ID, _MOVE_PP, _MOVENAME_COVET,
    _MOVENAME_SMELLING_SALTS, _MOVENAME_WAKE_UP_SLAP, _STATUS_PARALYSIS, _MOVENAME_PRESENT,
    _MOVENAME_TRIPLE_KICK, _MOVENAME_BEAT_UP, _MOVENAME_LAST_RESORT, _MOVENAME_SECRET_POWER,
    _POK_RAMPAGE_TURNS, _MOVENAME_THRASH, _MOVENAME_OUTRAGE, _MOVENAME_PETAL_DANCE,
    _MOVE_CATEGORY, _MOVE_TYPE, _SEC_CHANCE, _SEC_VOL_STATUS, _MOVENAME_STRUGGLE, _MOVEOUTCOME_HIT,
    _SEC_VOL_STATUS2,
    _VOLSTATUS_FLINCH, _STATUS_FREEZE, _ACTIONTYPE_MOVE, _BATTLEPHASE_TURN_START, _MOVECATEGORY_PHYSICAL,
    _BATTLEPHASE_DEATH_END_OF_TURN, _FIELD_PHASE, _MOVE_DRAIN, _MOVE_MULTI_HIT_MIN, _MOVE_MULTI_HIT_MAX,
    _POK_VOL_STATUS, _VOLSTATUS_BIDE, _POK_DMG_TAKEN, _MOVE_CHARGE_RECHARGE, _POK_CHARGE_RECHARGE,
    _POK_LOCKED_MOVE, _ITEM_WHEN, _ITEMACTIVATION_ON_RECEIVE_DAMAGE, _MOVE_DAMAGE, _MOVE_VOL_STATUS,
    _MOVENAME_BUG_BITE, _ITEMTYPE_BERRY, _DAMAGESOURCES_BIDE, _DAMAGESOURCES_MAGIC_COAT,
    _STATUS_POISON, _STATUS_TOXIC, _STATUS_BURN, _VOLSTATUS_CURSE, _ABILITYNAMES_MAGIC_GUARD,
    _POK_BADLY_POISON, _DAMAGESOURCES_LEVEL, _DAMAGESOURCES_PSYWAVE, _POK_LEVEL, _MOVE_RECOIL,
    _MOVENAME_FURY_CUTTER, _MOVENAME_NATURAL_GIFT, _POK_CONSEC_COUNT,
    _VOLSTATUS_SEMI_INVULNERABLE, _VOLSTATUS_HURT_THIS_TURN, _VOLSTATUS_PROTECT, _VOLSTATUS_ENDURE,
    _VOLSTATUS_RAGE, _VOLSTATUS_DESTINY_BOND, _VOLSTATUS_CHARGE, _VOLSTATUS_INGRAIN,
    _VOLSTATUS_AQUA_RING, _VOLSTATUS_LEECH_SEED, _VOLSTATUS_YAWN, _VOLSTATUS_ATTRACT,
    _VOLSTATUS_CONFUSION, _VOLSTATUS_UPROAR, _VOLSTATUS_PARTIALLY_TRAPPED,
    _VOLSTATUS_FOCUS_ENERGY, _VOLSTATUS_NIGHTMARE, _VOLSTATUS_FORESIGHT, _VOLSTATUS_DEFENSE_CURL,
    _MOVENAME_PROTECT, _MOVENAME_ENDURE, _MOVENAME_FEINT, _MOVENAME_RAGE, _MOVENAME_CHARGE,
    _POK_PROTECT_COUNT, _POK_ATTACK_STAT_STAGE, _POK_YAWN_TURNS, _POK_SLEEP_COUNTER, _STATUS_SLEEP,
    _ENEMY_AI_KNOWS_MOVE1, _ENEMY_AI_KNOWS_MOVE2, _ENEMY_AI_KNOWS_MOVE3, _ENEMY_AI_KNOWS_MOVE4,
    _POK_LAST_MOVE_ID, _MOVENAME_UPROAR, _POK_UPROAR_TURNS, _POK_TRAP_TURNS, _POK_TAUNT_TURNS,
    _POK_ENCORE_TURNS, _POK_DISABLE_TURNS, _VOLSTATUS_TAUNT, _VOLSTATUS_ENCORE, _VOLSTATUS_DISABLE,
    _MOVEOUTCOME_MISS, _MOVEOUTCOME_SEMI_INVULNERABLE, _MOVEOUTCOME_PROTECTED,
    _ABILITYNAMES_SOUNDPROOF, _FIELD_MY_SIDE_COND, _FIELD_OPP_SIDE_COND, _FIELD_WEATHER_DURATION,
    _MOVE_SIDE_CONDITION, _MOVE_TARGET, _SIDECONDITION_REFLECT, _SIDECONDITION_LIGHT_SCREEN,
    _SIDECONDITION_MIST, _SIDECONDITION_SAFEGUARD, _SIDECONDITION_LUCKY_CHANT,
    _SIDECONDITION_TOXIC_SPIKES, _SIDECONDITION_STEALTH_ROCK, _SIDECONDITION_SPIKES,
    _MOVENAME_BRICK_BREAK, _MOVENAME_RAPID_SPIN, _MOVENAME_RAIN_DANCE, _MOVENAME_SANDSTORM,
    _WEATHER_RAIN, _WEATHER_SANDSTORM, _WEATHER_SUN, _MOVE_FORCE_SWITCH, _MOVE_SELF_SWITCH, _MOVE_POWER,
    _ABILITYNAMES_SUCTION_CUPS, _ABILITYNAMES_MOLD_BREAKER, _MOVENAME_PURSUIT, _POK_CONFUSION_COUNTER,
    _POK_EVASION_STAT_STAGE, _VOLSTATUS_MUD_SPORT, _VOLSTATUS_WATER_SPORT, _VOLSTATUS_HEAL_BLOCK,
    _BATTLEPHASE_BATON_PASS, _FIELD_PENDING_OPP_MOVE, _VOLSTATUS_PERISH_SONG, _POK_PERISH_TURNS,
    _MOVENAME_MEMENTO, _MOVENAME_HEALING_WISH, _MOVENAME_GRUDGE, _VOLSTATUS2_GRUDGE,
    _SIDECONDITION_HEALING_WISH, _VOLSTATUS2_U_TURN, _VOLSTATUS2_TORMENT, _VOLSTATUS2_IMPRISON,
    _VOLSTATUS2_MEAN_LOOK, _MOVENAME_TORMENT, _MOVENAME_IMPRISON, _MOVENAME_SPITE,
    _MOVENAME_DETECT, _MOVENAME_MIRACLE_EYE, _VOLSTATUS2_LOCK_ON, _VOLSTATUS2_MIRACLE_EYE,
    _POK_LOCK_ON_TURNS,
    _MOVENAME_KNOCK_OFF, _POK_ITEM_KNOCKED_OFF, _MOVENAME_RECOVER, _MOVENAME_SYNTHESIS,
    _MOVENAME_REFRESH, _MOVENAME_RECYCLE, _MOVENAME_WORRY_SEED, _MOVENAME_PERISH_SONG,
    _ENEMY_AI_KNOWS_ABILITY, _POK_CALLED_MOVE, _FIELD_LAST_MOVE, _MOVENAME_HIDDEN_POWER,
    _POK_HIDDEN_POWER_TYPE, _POK_HIDDEN_POWER_POWER, _POK_SEMI_INV_MOVE, _FIELD_GRAVITY_TURNS,
    _MOVENAME_GRAVITY, _SIDECONDITION_TAILWIND, _FIELD_TRICKROOM, _MOVENAME_TRICK_ROOM, _MOVENAME_MINIMIZE, _POK_VOL_STATUS2, _VOLSTATUS2_MINIMIZE, _FLAGS_GRAVITY,
    _ITEM_HOLD_EFFECT, _ITEM_EFFECT_PARAM, _HOLDEFFECT_EXTEND_SCREENS, _HOLDEFFECT_EXTEND_SANDSTORM,
    _HOLDEFFECT_EXTEND_RAIN, _HOLDEFFECT_EXTEND_TRAPPING, _HOLDEFFECT_EXTEND_SUN, _HOLDEFFECT_EXTEND_HAIL,
    _MOVENAME_SUNNY_DAY, _MOVENAME_HAIL, _WEATHER_HAIL, _MOVENAME_WEATHER_BALL,
    _HOLDEFFECT_BRN_USER, _POK_TYPE1, _POK_TYPE2, _TYPES_FIRE,
    _FIELD_MY_ENTER_FIELD, _ABILITYNAMES_ROCK_HEAD,
    _MOVE_OH_KO, _ABILITYNAMES_ANGER_POINT, _ABILITYNAMES_SKILL_LINK, _ABILITYNAMES_HYDRATION,
    _HOLDEFFECT_HP_RESTORE_GRADUAL, _HOLDEFFECT_HP_RESTORE_PSN_TYPE, _TYPES_POISON,
    _ABILITYNAMES_POISON_HEAL, _ABILITYNAMES_HEATPROOF, _ABILITYNAMES_BAD_DREAMS,
    _ABILITYNAMES_LIQUID_OOZE, _FIELD_OPP_MOVE_RAN,
    _POK_SUB_HP, _VOLSTATUS2_SUBSTITUTE, _MOVENAME_SUBSTITUTE, _SEC_TARGET,
    _HOLDEFFECT_PSN_USER, _HOLDEFFECT_DMG_USER_CONTACT_XFR, _TYPES_STEEL,
    _MOVENAME_THIEF, _MOVENAME_PLUCK, _MOVENAME_TRICK, _MOVENAME_SWITCHEROO, _MOVENAME_EMBARGO,
    _MOVENAME_FLING, _VOLSTATUS2_EMBARGO, _POK_EMBARGO_TURNS, _ITEM_ID,
    _MOVENAME_SOLAR_BEAM, _MOVENAME_SKULL_BASH, _POK_DEFENSE_STAT_STAGE, _MOVENAME_SHADOW_FORCE,
    _MOVE_HAS_CRASH_DAMAGE, _DAMAGESOURCES_HALVE_HP, _DAMAGESOURCES_ENDEAVOR,
    _DAMAGESOURCES_METAL_BURST, _MOVENAME_FALSE_SWIPE, _MOVENAME_PAIN_SPLIT, _MOVENAME_BELLY_DRUM, _MOVENAME_ACUPRESSURE,
    _MOVENAME_HAZE, _MOVENAME_PSYCH_UP, _MOVENAME_POWER_SWAP, _MOVENAME_GUARD_SWAP,
    _MOVENAME_HEART_SWAP, _MOVENAME_POWER_TRICK, _VOLSTATUS2_POWER_TRICK,
    _VOLSTATUS2_DAMAGED_BY_MOVE, _MOVE_SLEEP_USABLE, _MOVENAME_REST, _MOVENAME_PSYCHO_SHIFT,
    _MOVENAME_HEAL_BELL, _MOVENAME_AROMATHERAPY, _MOVENAME_SOFT_BOILED, _MOVENAME_MILK_DRINK,
    _MOVENAME_SLACK_OFF, _MOVENAME_HEAL_ORDER, _MOVENAME_ROOST, _MOVENAME_MOONLIGHT,
    _MOVENAME_MORNING_SUN, _VOLSTATUS2_ROOST, _POK_HEAL_BLOCK_TURNS, _POK_MAGNET_RISE_TURNS,
    _VOLSTATUS2_MAGNET_RISE, _MOVENAME_MAGNET_RISE, _MOVENAME_DEFOG,
    _MOVENAME_MAGIC_COAT, _MOVENAME_SNATCH, _VOLSTATUS2_MAGIC_COAT, _VOLSTATUS2_SNATCH,
    _FLAGS_REFLECTABLE, _FLAGS_SNATCH, _ABILITYNAMES_PRESSURE,
)
from Models.move import STRUGGLE, MOVE_TABLE, DEFOG_DROP
from Models.constants import (
    _VOLSTATUS2_GASTRO_ACID, _MOVENAME_GASTRO_ACID, _MOVENAME_ROLE_PLAY, _MOVENAME_SKILL_SWAP,
    _MOVENAME_CONVERSION, _MOVENAME_CONVERSION_2, _MOVENAME_CAMOUFLAGE, _FIELD_TERRAIN,
    _MOVENAME_MIMIC, _MOVENAME_SKETCH, _MOVENAME_TRANSFORM,
)
from Models.item import refresh_item, raw_item_type


MULTIHIT_PROB=(2,2,2,3,3,3,4,5)
ROLLOUT_MAX_USES = 5
FURY_CUTTER_MAX_COUNT = 5
STALL_MOVES = (_MOVENAME_PROTECT, _MOVENAME_DETECT, _MOVENAME_ENDURE)
# Volatiles that only last for the turn they were set in
TURN_VOLATILES = _VOLSTATUS_HURT_THIS_TURN | _VOLSTATUS_PROTECT | _VOLSTATUS_ENDURE
# Bits of pokeplatinum's statusVolatile that the Gen IV Rage glitch wipes. Bide is left out so
# its lock (CHARGE_RECHARGE) stays consistent
RAGE_GLITCH_CLEARS = (
    _VOLSTATUS_FLINCH | _VOLSTATUS_CONFUSION | _VOLSTATUS_UPROAR | _VOLSTATUS_PARTIALLY_TRAPPED
    | _VOLSTATUS_ATTRACT | _VOLSTATUS_FOCUS_ENERGY | _VOLSTATUS_DESTINY_BOND | _VOLSTATUS_NIGHTMARE
    | _VOLSTATUS_CURSE | _VOLSTATUS_FORESIGHT | _VOLSTATUS_DEFENSE_CURL
)
# Bit in Field.AI_KNOWS for each of my move slots, set once the AI sees the move used
AI_KNOWS_MOVES = (
    _ENEMY_AI_KNOWS_MOVE1, _ENEMY_AI_KNOWS_MOVE2, _ENEMY_AI_KNOWS_MOVE3, _ENEMY_AI_KNOWS_MOVE4
)
# An uproar keeps going through these, only a blocked turn or an immune target ends it early
UPROAR_KEEPS_ON = (_MOVEOUTCOME_MISS, _MOVEOUTCOME_SEMI_INVULNERABLE, _MOVEOUTCOME_PROTECTED)
# Lock in for 2-3 turns, then confuse the user (pokeplatinum BATTLE_EFFECT_CONTINUE_AND_CONFUSE_SELF)
RAMPAGE_MOVES = (_MOVENAME_THRASH, _MOVENAME_OUTRAGE, _MOVENAME_PETAL_DANCE)
SIDES = (_FIELD_MY_SIDE_COND, _FIELD_OPP_SIDE_COND)
# Timed side conditions and their turn counter, in the order the end of turn counts them down
TIMED_SIDE_CONDITIONS = (
    (_SIDECONDITION_REFLECT, SIDE_REFLECT_TURNS),
    (_SIDECONDITION_LIGHT_SCREEN, SIDE_LIGHT_SCREEN_TURNS),
    (_SIDECONDITION_MIST, SIDE_MIST_TURNS),
    (_SIDECONDITION_SAFEGUARD, SIDE_SAFEGUARD_TURNS),
    (_SIDECONDITION_TAILWIND, SIDE_TAILWIND_TURNS),
    (_SIDECONDITION_LUCKY_CHANT, SIDE_LUCKY_CHANT_TURNS),
)
SCREENS = _SIDECONDITION_REFLECT | _SIDECONDITION_LIGHT_SCREEN
TIMED_SIDE_MASK = (
    _SIDECONDITION_REFLECT | _SIDECONDITION_LIGHT_SCREEN | _SIDECONDITION_MIST
    | _SIDECONDITION_SAFEGUARD | _SIDECONDITION_LUCKY_CHANT | _SIDECONDITION_TAILWIND
)
RAPID_SPIN_CLEARS = _SIDECONDITION_STEALTH_ROCK | _SIDECONDITION_SPIKES | _SIDECONDITION_TOXIC_SPIKES
# Defog clears these from the target's side (pokeplatinum subscript_defog)
DEFOG_CLEARS = SCREENS | _SIDECONDITION_MIST | _SIDECONDITION_SAFEGUARD | RAPID_SPIN_CLEARS
# Screens, Mist, Safeguard, Lucky Chant and move weather
FIELD_EFFECT_TURNS = 5
# Tailwind, counting the turn it's used in (pokeplatinum subscript_tailwind_start, SIDE_CONDITION_TAILWIND)
TAILWIND_TURNS = 3
# Future Sight / Doom Desire hit at the end of the turn after next, Wish heals at the end of the next
# turn, both counting the turn they're used in (pokeplatinum BtlCmd_TryFutureSight, BtlCmd_TryWish)
FUTURE_ATTACK_TURNS = 3
WISH_TURNS = 2
# The top damage roll, for Spit Up
MAX_ROLL = 100
TOXIC_SPIKES_MAX = 2
SPIKES_MAX = 3
# Leftovers, and Black Sludge on a Poison type
GRADUAL_HEAL_EFFECTS = (_HOLDEFFECT_HP_RESTORE_GRADUAL, _HOLDEFFECT_HP_RESTORE_PSN_TYPE)
WEATHER_MOVES = (
    (_MOVENAME_RAIN_DANCE, _WEATHER_RAIN), (_MOVENAME_SANDSTORM, _WEATHER_SANDSTORM),
    (_MOVENAME_SUNNY_DAY, _WEATHER_SUN), (_MOVENAME_HAIL, _WEATHER_HAIL)
)
# The held rock that lengthens each weather: Damp Rock, Smooth Rock, Heat Rock, Icy Rock
WEATHER_ROCKS = (
    (_WEATHER_RAIN, _HOLDEFFECT_EXTEND_RAIN), (_WEATHER_SANDSTORM, _HOLDEFFECT_EXTEND_SANDSTORM),
    (_WEATHER_SUN, _HOLDEFFECT_EXTEND_SUN), (_WEATHER_HAIL, _HOLDEFFECT_EXTEND_HAIL)
)
# Stealth Rock and Toxic Spikes go on the foe's side, the other side conditions on the user's
FOE_SIDE_TARGET = Target.FOE_SIDE
# Self, side and field moves still work against a fainted foe
NO_FOE_TARGETS = TARGET_SELF_SIDE + SIDE_OR_FIELD_TARGETS
STAGE_SWAP_MOVES = (_MOVENAME_POWER_SWAP, _MOVENAME_GUARD_SWAP, _MOVENAME_HEART_SWAP)
# What Baton Pass hands over besides the stat stages (pokeplatinum VOLATILE_CONDITION_BATON_PASSED
# and MOVE_EFFECT_BATON_PASSED, the ones the engine has)
BATON_PASS_VOLS = (
    _VOLSTATUS_CONFUSION | _VOLSTATUS_FOCUS_ENERGY | _VOLSTATUS_CURSE | _VOLSTATUS_LEECH_SEED
    | _VOLSTATUS_INGRAIN | _VOLSTATUS_AQUA_RING | _VOLSTATUS_MUD_SPORT | _VOLSTATUS_WATER_SPORT
    | _VOLSTATUS_HEAL_BLOCK | _VOLSTATUS_PERISH_SONG
)
# Baton Pass also hands over these VOL_STATUS2 bits (the Substitute goes with its HP, Embargo
# with its turns, Power Trick by trading the receiver's Attack and Defense)
BATON_PASS_VOLS2 = (
    _VOLSTATUS2_SUBSTITUTE | _VOLSTATUS2_EMBARGO | _VOLSTATUS2_POWER_TRICK | _VOLSTATUS2_MAGNET_RISE
    | _VOLSTATUS2_MEAN_LOOK | _VOLSTATUS2_LOCK_ON | _VOLSTATUS2_GASTRO_ACID
)
# A move or switch already resolved before action (Pursuit on a switching Pokemon)
NO_ACTION = -50
# Field.OPP_MOVE_RAN: the foe's move slot + 1, plus this for every PP the move paid
OPP_RAN_PP_STEP = 16
# Field.PENDING_OPP_MOVE: added to the slot + 1 when my move made the foe flinch (U-turn with King's Rock)
PENDING_FLINCH = 16
HEAL_MOVES = (
    _MOVENAME_RECOVER, _MOVENAME_SYNTHESIS, _MOVENAME_SOFT_BOILED, _MOVENAME_MILK_DRINK,
    _MOVENAME_SLACK_OFF, _MOVENAME_HEAL_ORDER, _MOVENAME_ROOST, _MOVENAME_MOONLIGHT,
    _MOVENAME_MORNING_SUN
)
# VOL_STATUS2 bits that last only the turn
TURN_VOLATILES2 = (
    _VOLSTATUS2_DAMAGED_BY_MOVE | _VOLSTATUS2_ROOST | _VOLSTATUS2_MAGIC_COAT | _VOLSTATUS2_SNATCH
)
RECOIL_IMMUNE_AB = (_ABILITYNAMES_ROCK_HEAD, _ABILITYNAMES_MAGIC_GUARD)
# Covet and Thief take the target's item, Bug Bite and Pluck eat its berry
STEAL_MOVES = (_MOVENAME_COVET, _MOVENAME_THIEF)
PLUCK_MOVES = (_MOVENAME_BUG_BITE, _MOVENAME_PLUCK)
SWAP_MOVES = (_MOVENAME_TRICK, _MOVENAME_SWITCHEROO)
# They rewrite the user's move slots, the one being run included
COPY_MOVES = (_MOVENAME_MIMIC, _MOVENAME_SKETCH, _MOVENAME_TRANSFORM)

@njit
def _pass_baton(old, new):
    """Baton Pass: the stat stages and the passable volatiles go to the Pokemon coming in"""
    new[_POK_ATTACK_STAT_STAGE:_POK_EVASION_STAT_STAGE + 1] = (
        old[_POK_ATTACK_STAT_STAGE:_POK_EVASION_STAT_STAGE + 1]
    )
    new[_POK_VOL_STATUS] = old[_POK_VOL_STATUS] & BATON_PASS_VOLS
    new[_POK_VOL_STATUS2] |= old[_POK_VOL_STATUS2] & BATON_PASS_VOLS2
    new[_POK_SUB_HP] = old[_POK_SUB_HP]
    new[_POK_CONFUSION_COUNTER] = old[_POK_CONFUSION_COUNTER]
    new[_POK_PERISH_TURNS] = old[_POK_PERISH_TURNS]
    # Embargo goes on with its turns, now over the new Pokemon's item (pokeplatinum embargoTurns)
    new[_POK_EMBARGO_TURNS] = old[_POK_EMBARGO_TURNS]
    # Heal Block too (pokeplatinum healBlockTurns)
    new[_POK_HEAL_BLOCK_TURNS] = old[_POK_HEAL_BLOCK_TURNS]
    # Magnet Rise too (pokeplatinum magnetRiseTurns)
    new[_POK_MAGNET_RISE_TURNS] = old[_POK_MAGNET_RISE_TURNS]
    # A passed Lock-On starts its turns again (pokeplatinum LOCK_ON_INITIAL_DURATION)
    if new[_POK_VOL_STATUS2] & _VOLSTATUS2_LOCK_ON:
        new[_POK_LOCK_ON_TURNS] = LOCK_ON_DURATION
    # The receiver's own Attack and Defense trade (pokeplatinum BattleSystem_UpdateAfterSwitch)
    if new[_POK_VOL_STATUS2] & _VOLSTATUS2_POWER_TRICK:
        swap_atk_def(new)
    # Gastro Acid goes on over the receiver's ability (pokeplatinum MOVE_EFFECT_BATON_PASSED)
    if new[_POK_VOL_STATUS2] & _VOLSTATUS2_GASTRO_ACID:
        suppress_ability(new)
    refresh_item(new)


@njit
def _bench_alive(battle_array, is_mine):
    """How many of that side's Pokemon besides the active are still alive"""
    base = 0 if is_mine else 6
    active = battle_array[_FIELD_MY_POK] if is_mine else battle_array[_FIELD_OPP_POK]
    n = 0
    for i in range(6):
        if i != active and battle_array[(base + i) * POK_LEN + _POK_CURRENT_HP] > 0:
            n += 1
    return n


@njit
def _random_bench(battle_array, is_mine, n):
    """Uniform pick among the n alive Pokemon on that side's bench, like pokeplatinum's reroll"""
    base = 0 if is_mine else 6
    active = battle_array[_FIELD_MY_POK] if is_mine else battle_array[_FIELD_OPP_POK]
    pick = random.randrange(n)
    for i in range(6):
        if i != active and battle_array[(base + i) * POK_LEN + _POK_CURRENT_HP] > 0:
            if pick == 0:
                return i
            pick -= 1
    return -1


@njit
def _force_switch(atk, defn, battle_array, target_is_mine):
    """
    Roar and Whirlwind: Suction Cups (unless Mold Breaker), Ingrain or an empty bench make them
    fail, and so does the level roll when the user is lower level (pokeplatinum
    BattleSystem_CanWhirlwind, also in trainer battles). The target is replaced by a random
    Pokemon from its bench. Returns True if it was dragged out
    """
    if defn[_POK_AB_ID] == _ABILITYNAMES_SUCTION_CUPS and atk[_POK_AB_ID] != _ABILITYNAMES_MOLD_BREAKER:
        reveal_ability(defn)
        return False
    if defn[_POK_VOL_STATUS] & _VOLSTATUS_INGRAIN:
        return False
    n = _bench_alive(battle_array, target_is_mine)
    if n == 0:
        return False
    atk_lv = atk[_POK_LEVEL]
    def_lv = defn[_POK_LEVEL]
    if atk_lv < def_lv and ((random.randrange(256) * (atk_lv + def_lv)) >> 8) + 1 <= def_lv // 4:
        return False
    slot = _random_bench(battle_array, target_is_mine, n)
    if target_is_mine:
        _switch_my_side(battle_array, defn, atk, slot)
    else:
        _switch_opp_side(battle_array, defn, atk, slot)
    return True


@njit
def _switch_my_side(battle_array, current_pokemon, current_opp, switch_idx, baton=False):
    """Perform my-side switch-in bookkeeping, return the new active slice"""
    if baton:
        _pass_baton(current_pokemon, battle_array[(switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)])
    else:
        # The trapper leaving frees the one it trapped, the target leaving ends the foe's Lock-On
        # (pokeplatinum BattleSystem_UpdateAfterSwitch)
        current_opp[_POK_VOL_STATUS2] &= ~(_VOLSTATUS2_MEAN_LOOK | _VOLSTATUS2_LOCK_ON)
    reset_switch_out(current_pokemon)
    battle_array[_FIELD_MY_POK] = switch_idx
    battle_array[_FIELD_AI_KNOWS] = 0
    battle_array[_FIELD_MY_LAST_MOVE] = 0
    battle_array[_FIELD_MY_ENTER_FIELD] = 1
    new_pokemon = battle_array[
        (switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)
    ]
    carry_recycle(current_pokemon, new_pokemon)
    switch_in(new_pokemon, current_opp, battle_array, True)
    return new_pokemon


@njit
def _switch_opp_side(battle_array, current_opp, current_pokemon, opp_switch, baton=False):
    """Perform opp-side switch-in bookkeeping, return the new active slice"""
    if baton:
        _pass_baton(
            current_opp, battle_array[((opp_switch+6) * POK_LEN):((opp_switch+7) * POK_LEN)]
        )
    else:
        current_pokemon[_POK_VOL_STATUS2] &= ~(_VOLSTATUS2_MEAN_LOOK | _VOLSTATUS2_LOCK_ON)
    reset_switch_out(current_opp)
    battle_array[_FIELD_OPP_POK] = opp_switch
    battle_array[_FIELD_OPP_ENTER_FIELD] = 1
    new_opp = battle_array[
        ((opp_switch+6) * POK_LEN):((opp_switch+7) * POK_LEN)
    ]
    carry_recycle(current_opp, new_opp)
    switch_in(new_opp, current_pokemon, battle_array, False)
    return new_opp


@njit
def start_of_turn(opp_move, switch_idx, battle_array, current_move=-1):
    """
    What happens before everything in the turn order, so switches and trainer items.
    Pursuit hits a Pokemon switching out before it leaves and uses up the pursuer's turn.
    Returns (current_move, opp_move) for action, NO_ACTION for a move already used
    """
    # TODO: Opponent Items
    opp_switch = -1
    opp_active = battle_array[_FIELD_OPP_POK]
    my_active = battle_array[_FIELD_MY_POK]
    current_pokemon = battle_array[
        (my_active * POK_LEN):((my_active+1) * POK_LEN)
    ]
    current_opp = battle_array[
        ((opp_active+6) * POK_LEN):((opp_active+7) * POK_LEN)
    ]
    battle_array[_FIELD_AI_TOOK_DMG_LAST_TURN] = 0
    if opp_move < 0:
        if opp_move <= -10:  #Item
            item_list = battle_array[_FIELD_AI_ITEM1:(_FIELD_AI_ITEM1+4)]
            slot = -(opp_move // 10) - 1  #Items are -10, -20, -30, -40
            trainer_ai_items(current_opp, item_list[slot])
            item_list[slot] = 0  # Item used, so goes to 0
        else:
            opp_switch = opp_move + 6 #Before I subtracted -6 from idx that's why +6 so it's 0..5

    if switch_idx >= 0 and opp_switch >= 0:
        my_s, opp_s = field_speeds(
            battle_array, current_pokemon, current_opp, effective_weather(battle_array)
        )
        if goes_first(my_s, opp_s, trick_room_up(battle_array)):
            current_pokemon = _switch_my_side(battle_array, current_pokemon, current_opp, switch_idx)
            _switch_opp_side(battle_array, current_opp, current_pokemon, opp_switch)
        else:
            current_opp = _switch_opp_side(battle_array, current_opp, current_pokemon, opp_switch)
            _switch_my_side(battle_array, current_pokemon, current_opp, switch_idx)
        return current_move, opp_move

    if opp_switch >= 0:
        if _pursuit(current_pokemon, current_opp, current_move, True, battle_array):
            current_move = NO_ACTION
        _switch_opp_side(battle_array, current_opp, current_pokemon, opp_switch)

    if switch_idx >= 0:
        if opp_move >= 0 and _pursuit(current_opp, current_pokemon, opp_move, False, battle_array):
            opp_move = NO_ACTION
        _switch_my_side(battle_array, current_pokemon, current_opp, switch_idx)
    return current_move, opp_move


@njit
def _pursuit(atk, defn, slot, is_mine, battle_array):
    """
    pokeplatinum BtlCmd_TryPursuit: the pursuer hasn't moved, is alive, not asleep, frozen or
    loafing (Truant), its move (the encored one if Encore holds) is Pursuit with PP left.
    It hits at double power before the switch, the other checks of a normal turn (paralysis, confusion)
    don't happen. Returns True if Pursuit was used
    """
    if slot < 0 or atk[_POK_CURRENT_HP] <= 0:
        return False
    slot = _encore_slot(atk, slot)
    if slot >= 4 or atk[_POK_STATUS] == _STATUS_SLEEP or atk[_POK_STATUS] == _STATUS_FREEZE:
        return False
    if truant_loafs(atk):
        return False
    mv = atk[OFFSET_MOVE + slot * MOVE_STRIDE : OFFSET_MOVE + (slot + 1) * MOVE_STRIDE]
    if mv[_MOVE_ID] != _MOVENAME_PURSUIT or mv[_MOVE_PP] <= 0:
        return False
    pp_before = mv[_MOVE_PP]
    mv[_MOVE_PP] -= 1
    # The switching Pressure holder costs one more (pokeplatinum, Pursuit before a switch)
    pressure_pp(mv, defn)
    atk[_POK_LAST_MOVE_ID] = mv[_MOVE_ID]
    record_last_resort(atk, slot, mv[_MOVE_ID])
    battle_array[_FIELD_LAST_MOVE] = mv[_MOVE_ID]
    if is_mine:
        battle_array[_FIELD_MY_LAST_MOVE] = mv[_MOVE_ID]
        battle_array[_FIELD_AI_KNOWS] |= AI_KNOWS_MOVES[slot]
    else:
        battle_array[_FIELD_OPP_MOVE_RAN] = slot + 1 + OPP_RAN_PP_STEP * (pp_before - mv[_MOVE_PP])
    doubled = mv.copy()
    doubled[_MOVE_POWER] *= 2
    weather = effective_weather(battle_array)
    gravity = battle_array[_FIELD_GRAVITY_TURNS] > 0
    if calculate_hit_miss(doubled, atk, defn, weather, gravity, True) == _MOVEOUTCOME_HIT:
        _, hit_pok, dealt = ps_moves(
            atk, defn, doubled, weather, False, False, battle_array[side_base(not is_mine)], gravity
        )
        if is_mine and hit_pok:
            battle_array[_FIELD_AI_TOOK_DMG_LAST_TURN] = normalized_type(atk, mv)
        if defn[_POK_CURRENT_HP] <= 0 and defn[_POK_VOL_STATUS] & _VOLSTATUS_DESTINY_BOND:
            mark_hurt(atk)
            atk[_POK_CURRENT_HP] = 0
        _grudge(atk, defn, slot)
        after_move_hit_items(atk, doubled, dealt, hit_pok)
    update_choice_lock(atk, slot)
    clear_target_choice_lock(defn, atk)
    status_item(atk)
    status_item(defn)
    return True


@njit
def _resolve_move_damage(attacker, defender, move, weather, def_side=0, gravity=False, atk_side=0):
    """Figure out how much damage this hit does, independent of applying it, and whether it
    was a critical hit. def_side is the defender's Field.SIDE_COND, atk_side the attacker's"""
    if move[_MOVE_ID] == _MOVENAME_STRUGGLE:
        crit = calculate_crit(attacker, defender, None, def_side)
        return struggle_damage(attacker, defender, crit, def_side, weather), crit
    # OHKO moves take the target's current HP (pokeplatinum BtlCmd_TryOHKOMove), its max HP on a
    # Substitute, so the Substitute always breaks (pokeplatinum BattleControllerPlayer_UpdateHP)
    if move[_MOVE_OH_KO]:
        if has_substitute(defender):
            return defender[_POK_MAX_HP], False
        return defender[_POK_CURRENT_HP], False
    move_damage = move[_MOVE_DAMAGE]
    if not move_damage:
        crit = calculate_crit(attacker, defender, move, def_side)
        # Spit Up has no roll (pokeplatinum effect 0161, CalcMaxDamage)
        roll = MAX_ROLL if move[_MOVE_ID] == _MOVENAME_SPIT_UP else None
        damage = calculate_damage(
            attacker, defender, move, weather, crit, roll, def_side, gravity, atk_side
        )
        return resist_berry(attacker, defender, move, damage, gravity), crit
    if move_damage == _DAMAGESOURCES_LEVEL:
        return attacker[_POK_LEVEL], False
    if move_damage == _DAMAGESOURCES_PSYWAVE:
        return max(1, attacker[_POK_LEVEL] * (random.randint(0, 10) + 5) // 10), False
    if move_damage == _DAMAGESOURCES_BIDE:
        # Bide damage
        dmg = attacker[_POK_DMG_TAKEN]*2
        attacker[_POK_DMG_TAKEN] = 0
        # I think this if is not needed, but just to be safe its here
        if attacker[_POK_VOL_STATUS] & _VOLSTATUS_BIDE:
            attacker[_POK_VOL_STATUS] -= _VOLSTATUS_BIDE
        return dmg, False
    if move_damage in RECORD_DAMAGE:
        dmg = attacker[_POK_DMG_TAKEN]*2
        attacker[_POK_DMG_TAKEN] = 0
        return dmg, False
    # Super Fang and Endeavor read the target's HP, also behind a Substitute (pokeplatinum
    # effect 0040, BattleSystem_Divide, and 0189)
    if move_damage == _DAMAGESOURCES_HALVE_HP:
        return max(1, defender[_POK_CURRENT_HP] // 2), False
    if move_damage == _DAMAGESOURCES_ENDEAVOR:
        return defender[_POK_CURRENT_HP] - attacker[_POK_CURRENT_HP], False
    if move_damage == _DAMAGESOURCES_METAL_BURST:
        dmg = attacker[_POK_DMG_TAKEN] * 15 // 10
        attacker[_POK_DMG_TAKEN] = 0
        return dmg, False
    # if move damage is a positive int, it means that is a fixed damage so just return it
    return move_damage, False


@njit
def _apply_move_damage(attacker, defender, move, damage, crit=False):
    """Subtracts HP, checks flinch and item-on-damage. Contact abilities come later, in
    on_hit_abilities. Returns flinch"""
    if damage > 0:
        mark_hurt(defender)
        # Revenge, Avalanche and Focus Punch see it (pokeplatinum physical/specialDamageAttackerMask)
        defender[_POK_VOL_STATUS2] |= _VOLSTATUS2_DAMAGED_BY_MOVE
    if damage < defender[_POK_CURRENT_HP]:
        defender[_POK_CURRENT_HP] -= damage
        # Rage builds on every damaging hit the user survives
        if defender[_POK_VOL_STATUS] & _VOLSTATUS_RAGE and damage > 0:
            defender[_POK_ATTACK_STAT_STAGE] = min(6, defender[_POK_ATTACK_STAT_STAGE] + 1)
        # Anger Point maxes Attack after surviving a critical hit (Showdown gen4 angerpoint)
        if crit and defender[_POK_AB_ID] == _ABILITYNAMES_ANGER_POINT:
            # pokeplatinum subscript_critical_hit: the message only shows when Attack goes up
            if defender[_POK_ATTACK_STAT_STAGE] < 6:
                reveal_ability(defender)
            defender[_POK_ATTACK_STAT_STAGE] = 6
        flinch = False
        if move[_SEC_VOL_STATUS] & _VOLSTATUS_FLINCH:
            flinch = flinch_checker(move, attacker, defender)
        elif move[_SEC_VOL_STATUS2] & _VOLSTATUS_FLINCH:
            flinch = flinch_checker(move, attacker, defender, True)
        elif kings_rock(move, attacker):
            flinch = flinch_checker(move, attacker, defender, False, attacker[_ITEM_EFFECT_PARAM])
        if defender[_ITEM_WHEN] & _ITEMACTIVATION_ON_RECEIVE_DAMAGE:
            item_on_rdmg(defender)
        return flinch

    defender[_POK_CURRENT_HP] = 0
    return False


@njit
def _ps_moves_core(
        attacker, defender, move, weather, def_side=0, gravity=False, sash=False, atk_side=0
):
    """
    Checks for damage and for flinch. Also returns the HP the defender actually lost, and whether
    its Substitute took the hit instead: then dealt is what the Substitute lost and nothing on the
    defender's side happens (no flinch, Focus Band, Rage, on-damage item or hurt flag). sash: a
    Focus Sash already found the defender at full HP earlier in this move, returned updated
    """
    raw_damage, crit = _resolve_move_damage(
        attacker, defender, move, weather, def_side, gravity, atk_side
    )
    if has_substitute(defender):
        dealt = hit_substitute(defender, raw_damage)
        return False, dealt, dealt, True, sash
    # False Swipe leaves 1 HP, before Endure and the focus items (pokeplatinum
    # BattleControllerPlayer_UpdateHP)
    if move[_MOVE_ID] == _MOVENAME_FALSE_SWIPE and raw_damage >= defender[_POK_CURRENT_HP]:
        raw_damage = defender[_POK_CURRENT_HP] - 1
    sash = sash or focus_sash_ready(defender)
    damage = endure_damage(defender, raw_damage, sash)
    dealt = min(damage, defender[_POK_CURRENT_HP])
    flinch= _apply_move_damage(attacker, defender, move, damage, crit)
    return flinch, damage, dealt, False, sash


@njit
def _cure_on_hit(defender, move):
    """Smelling Salts cures the paralysis and Wake-Up Slap the sleep of a target that survived the
    hit (pokeplatinum subscript_heal_target_paralysis / _sleep)"""
    if defender[_POK_CURRENT_HP] <= 0:
        return
    move_id = move[_MOVE_ID]
    if (
        (move_id == _MOVENAME_SMELLING_SALTS and defender[_POK_STATUS] == _STATUS_PARALYSIS)
        or (move_id == _MOVENAME_WAKE_UP_SLAP and defender[_POK_STATUS] == _STATUS_SLEEP)
    ):
        cure_status(defender)


@njit
def _present_move(mv):
    """Present rolls before the hit check: 20% heal, else power 40, 80 or 120 at 40%, 30% and
    10% (Showdown onModifyMove). Power 0 is the heal"""
    roll = random.randint(0, 9)
    present = mv.copy()
    if roll < 2:
        present[_MOVE_POWER] = 0
    elif roll < 6:
        present[_MOVE_POWER] = 40
    elif roll < 9:
        present[_MOVE_POWER] = 80
    else:
        present[_MOVE_POWER] = 120
    return present


@njit
def _present_heal(defender):
    """Present's heal: 1/4 of the target's max HP, at least 1, through a Substitute (Showdown
    infiltrates). Heal Block stops it (pokeplatinum subscript_present_heal)"""
    if heal_blocked(defender):
        return
    max_hp = defender[_POK_MAX_HP]
    defender[_POK_CURRENT_HP] = min(max_hp, defender[_POK_CURRENT_HP] + max(1, max_hp // 4))


@njit
def _beat_up_side(is_mine):
    """First Pokemon block of the user's side"""
    return 0 if is_mine else 6 * POK_LEN


@njit
def _beat_up_members(battle_array, is_mine):
    """How many Pokemon hit with Beat Up: the user and its party alive with no status (Showdown
    gen4 allies)"""
    first = _beat_up_side(is_mine)
    count = 0
    for i in range(6):
        off = first + i * POK_LEN
        if battle_array[off + _POK_CURRENT_HP] > 0 and battle_array[off + _POK_STATUS] == 0:
            count += 1
    return count


@njit
def _beat_up(attacker, defender, move, battle_array, is_mine, weather, rec_p, def_side, gravity):
    """
    One hit per Pokemon of the user's side alive with no status, in party order, each with its
    own base Attack and level (pokeplatinum BtlCmd_BeatUp). A crit roll per hit. Returns the
    flinch, whether a hit reached the Pokemon and the HP it took off, like ps_moves_multihit
    """
    first = _beat_up_side(is_mine)
    flinch = False
    hit_pok = False
    sash = False
    dealt_total = 0
    damage = 0
    for i in range(6):
        if defender[_POK_CURRENT_HP] <= 0 or attacker[_POK_CURRENT_HP] <= 0:
            break
        member = battle_array[first + i * POK_LEN:first + (i + 1) * POK_LEN]
        if member[_POK_CURRENT_HP] <= 0 or member[_POK_STATUS] != 0:
            continue
        crit = calculate_crit(attacker, defender, move, def_side)
        raw_damage = beat_up_damage(attacker, member, defender, crit)
        if has_substitute(defender):
            dealt_total += hit_substitute(defender, raw_damage)
            continue
        sash = sash or focus_sash_ready(defender)
        damage = endure_damage(defender, raw_damage, sash)
        dealt = min(damage, defender[_POK_CURRENT_HP])
        if _apply_move_damage(attacker, defender, move, damage, crit):
            flinch = True
        dealt_total += dealt
        hit_pok = True
        on_hit_abilities(attacker, defender, move, dealt, weather)
        sticky_barb_transfer(attacker, defender, move, dealt)
        on_hit_berries(attacker, defender, move, dealt, gravity)

    # The last hit on the Pokemon is the one recorded, as in ps_moves_multihit
    if hit_pok and defender[_POK_VOL_STATUS] & _VOLSTATUS_BIDE:
        defender[_POK_DMG_TAKEN] += damage
    if hit_pok and rec_p:
        defender[_POK_DMG_TAKEN] = damage
    return flinch, hit_pok, dealt_total


@njit
def _sec_reaches(move, sub_hit):
    """A hit on the Substitute keeps the secondary effects off the target, not the user's own"""
    return not (sub_hit and move[_SEC_TARGET] in TARGET_OPP_SIDE)


@njit
def _recoil(attacker, move, dealt):
    """Recoil after the hit, Struggle's comes from max HP and the rest from the damage dealt.
    Rock Head and Magic Guard skip the rest, not Struggle's (pokeplatinum subscript_recoil_1_4,
    subscript_struggle)"""
    if move[_MOVE_ID] == _MOVENAME_STRUGGLE:
        apply_recoil(attacker, struggle_recoil(attacker))
    elif move[_MOVE_RECOIL] and attacker[_POK_AB_ID] not in RECOIL_IMMUNE_AB:
        apply_recoil(attacker, move_recoil(move, dealt))


@njit
def _crash(attacker, defender, move, weather, def_side=0, gravity=False):
    """Jump Kick and High Jump Kick: a move that didn't hit costs half the damage it would have
    dealt (crit and roll included, a type immunity makes it 0), at most half the target's max HP.
    Magic Guard skips it (pokeplatinum effect 0045 calculates the damage before the hit check,
    subscript_crash_on_miss)"""
    if not move[_MOVE_HAS_CRASH_DAMAGE] or attacker[_POK_AB_ID] == _ABILITYNAMES_MAGIC_GUARD:
        return
    crit = calculate_crit(attacker, defender, move, def_side)
    damage = calculate_damage(attacker, defender, move, weather, crit, None, def_side, gravity)
    apply_recoil(attacker, min(damage // 2, defender[_POK_MAX_HP] // 2))


@njit
def ps_moves_multihit(
        attacker, defender, move, weather, rec_p, rec_s, def_side=0, gravity=False,
        target_moved=False
):
    """Physical or Special multihit moves, where I need to calculate damage and secondary effects.
    Triple Kick's kicks are 10, 20 and 30 power and each one after the first rolls accuracy, the
    first miss ends it. target_moved: the target already acted this turn (Zoom Lens)"""
    mult_hit_min = move[_MOVE_MULTI_HIT_MIN]
    mult_hit_max = move[_MOVE_MULTI_HIT_MAX]
    dmg = 0
    dealt_total = 0
    flinch = False
    hit_pok = False
    sash = False
    if mult_hit_min == 2 and mult_hit_max == 5:
        # Skill Link always hits 5 times (pokeplatinum BtlCmd_SetMultiHit)
        if attacker[_POK_AB_ID] == _ABILITYNAMES_SKILL_LINK:
            multhit = 5
        else:
            multhit = MULTIHIT_PROB[random.getrandbits(3)]
    elif mult_hit_min == mult_hit_max:
        multhit = mult_hit_min
    else:
        raise ValueError("Moves that are variable and not 2-5 shouldn't exit, check DB")
    kick = move[_MOVE_ID] == _MOVENAME_TRIPLE_KICK
    hit_mv = move
    for i in range(multhit):
        # Rough Skin can knock the user out mid-sequence
        if i and (defender[_POK_CURRENT_HP] <= 0 or attacker[_POK_CURRENT_HP] <= 0):
            break
        if kick:
            if i and not kick_hits(move, attacker, defender, weather, gravity, target_moved):
                break
            hit_mv = move.copy()
            hit_mv[_MOVE_POWER] = TRIPLE_KICK_STEP * (i + 1)
        flinch_c, damage, dealt, sub_hit, sash = _ps_moves_core(
            attacker, defender, hit_mv, weather, def_side, gravity, sash
        )
        if flinch_c:
            flinch = True
        dmg += damage
        dealt_total += dealt
        # Once the Substitute breaks the remaining hits reach the Pokemon, with their effects
        # (Showdown, each hit is its own move hit)
        if not sub_hit:
            hit_pok = True
        # Check for secondary effects and apply them
        if move[_SEC_CHANCE] and _sec_reaches(move, sub_hit):
            sec_effects(move, attacker, defender, weather, def_side)
        if not sub_hit:
            on_hit_abilities(attacker, defender, move, dealt, weather)
            sticky_barb_transfer(attacker, defender, move, dealt)
            on_hit_berries(attacker, defender, move, dealt, gravity)

    _recoil(attacker, move, dealt_total)
    if move[_MOVE_DRAIN]:
        drain(attacker, defender, move, dealt_total)

    # A hit on the Substitute isn't recorded for Bide, Counter or Mirror Coat (pokeplatinum
    # UpdateHP returns first); the last hit is on the Pokemon whenever one is
    if hit_pok and defender[_POK_VOL_STATUS] & _VOLSTATUS_BIDE:
        #Only last damage counts i think, needs check TODO
        defender[_POK_DMG_TAKEN] += damage
    if hit_pok and (
        (rec_p and move[_MOVE_CATEGORY] == _MOVECATEGORY_PHYSICAL)
        or (rec_s and move[_MOVE_CATEGORY] == _MOVECATEGORY_SPECIAL)
    ):
        #Only last damage counts i think, needs check TODO
        defender[_POK_DMG_TAKEN] = damage

    return flinch, hit_pok, dealt_total


@njit
def ps_moves(attacker, defender, move, weather, rec_p, rec_s, def_side=0, gravity=False, atk_side=0):
    """Physical or Special moves, where I need to calculate damage and secondary effects.
    def_side is the defender's Field.SIDE_COND, atk_side the attacker's (Gyro Ball's Tailwind). Returns the flinch, whether the hit reached
    the Pokemon, not its Substitute, and the HP it took off"""
    flinch, damage, dealt, sub_hit, _ = _ps_moves_core(
        attacker, defender, move, weather, def_side, gravity, False, atk_side
    )
    # The flung item still boosted the hit, then it's gone (pokeplatinum CalcDamage runs before
    # RemoveItem, Showdown's fling volatile drops it after)
    if move[_MOVE_ID] == _MOVENAME_FLING:
        fling_throw(attacker)

    _recoil(attacker, move, dealt)
    if move[_MOVE_DRAIN]:
        drain(attacker, defender, move, dealt)

    # Check for secondary effects and apply them
    if move[_SEC_CHANCE] and _sec_reaches(move, sub_hit):
        sec_effects(move, attacker, defender, weather, def_side)
    # The Substitute keeps off the rest: contact abilities, Bide / Counter's record and the
    # item moves (pokeplatinum TriggerAbilityOnHit, PluckBerry, subscript_knock_off and co.)
    if sub_hit:
        return flinch, False, dealt
    _cure_on_hit(defender, move)
    # After recoil, drain and the secondary effect (pokeplatinum after-move order)
    on_hit_abilities(attacker, defender, move, dealt, weather)
    sticky_barb_transfer(attacker, defender, move, dealt)
    on_hit_berries(attacker, defender, move, dealt, gravity)

    if defender[_POK_VOL_STATUS] & _VOLSTATUS_BIDE:
        defender[_POK_DMG_TAKEN] += damage
    if (
        (rec_p and move[_MOVE_CATEGORY] == _MOVECATEGORY_PHYSICAL)
        or (rec_s and move[_MOVE_CATEGORY] == _MOVECATEGORY_SPECIAL)
    ):
        defender[_POK_DMG_TAKEN] = damage

    # An Embargoed target's berry is still a berry
    if (
        move[_MOVE_ID] in PLUCK_MOVES
        and raw_item_type(defender) == _ITEMTYPE_BERRY
        and not sticky_hold(defender, attacker)
    ):
        eat_berry_bug_bite(attacker, defender)
    # The AI's Covet steals too: correct for RP despite pokeplatinum BtlCmd_TryStealItem failing for
    # side-1 attackers outside the Frontier (a decomp oversight). It can't take a Griseous Orb.
    # Thief is the same move ([pp] BATTLE_EFFECT_STEAL_HELD_ITEM)
    elif (
        move[_MOVE_ID] in STEAL_MOVES
        and takeable_item(defender)
        and not sticky_hold(defender, attacker)
        and not attacker[_ITEM_ID]
        and not attacker[_POK_ITEM_KNOCKED_OFF]
        and not defender[_POK_ITEM_KNOCKED_OFF]
    ):
        switch_items(attacker, defender)
    elif move[_MOVE_ID] == _MOVENAME_KNOCK_OFF:
        knock_off(attacker, defender)
    elif move[_MOVE_ID] == _MOVENAME_FLING:
        fling_hit(attacker, defender)

    return flinch, True, dealt


@njit
def _consec_before_move(atk, mv, slot):
    """Rollout/Ice Ball lock in on their first use, any other move resets Fury Cutter's count"""
    move_id = mv[_MOVE_ID]
    if move_id in ROLLOUT_MOVES:
        if atk[_POK_LOCKED_MOVE] == -1:
            atk[_POK_LOCKED_MOVE] = slot
            atk[_POK_CONSEC_COUNT] = 0
    elif move_id != _MOVENAME_FURY_CUTTER:
        atk[_POK_CONSEC_COUNT] = 0


@njit
def _consec_on_hit(atk, mv):
    """Fury Cutter, Rollout and Ice Ball count their consecutive hits, the power reads it"""
    move_id = mv[_MOVE_ID]
    if move_id == _MOVENAME_FURY_CUTTER or move_id in ROLLOUT_MOVES:
        atk[_POK_CONSEC_COUNT] = min(atk[_POK_CONSEC_COUNT] + 1, FURY_CUTTER_MAX_COUNT)


@njit
def _clear_charge(atk, mv):
    """Charge lasts until the user's next move attempt that isn't Charge"""
    if mv[_MOVE_ID] != _MOVENAME_CHARGE:
        atk[_POK_VOL_STATUS] &= ~_VOLSTATUS_CHARGE


@njit
def _held_extension(pok, effect):
    """Extra turns a held Light Clay or weather rock adds, its effect_param"""
    return pok[_ITEM_EFFECT_PARAM] if pok[_ITEM_HOLD_EFFECT] == effect else 0


@njit
def _set_side_condition(cond, battle_array, side, screen_bonus=0):
    """
    Screens, Mist, Safeguard and Lucky Chant last 5 turns and Tailwind 3, all fail while up, Stealth
    Rock fails if already set, Toxic Spikes stacks up to 2 layers and Spikes up to 3 (pokeplatinum
    BtlCmd_TrySpikes). side is that side's Field.SIDE_COND. screen_bonus is the user's Light Clay
    turns, only screens get them
    """
    if cond == _SIDECONDITION_TOXIC_SPIKES or cond == _SIDECONDITION_SPIKES:
        slot = SIDE_TOXIC_SPIKES if cond == _SIDECONDITION_TOXIC_SPIKES else SIDE_SPIKES
        cap = TOXIC_SPIKES_MAX if cond == _SIDECONDITION_TOXIC_SPIKES else SPIKES_MAX
        layers = battle_array[side + slot]
        if layers < cap:
            battle_array[side + slot] = layers + 1
            battle_array[side] |= cond
        return
    if battle_array[side] & cond:
        return
    battle_array[side] |= cond
    for bit, turns in TIMED_SIDE_CONDITIONS:
        if bit == cond:
            battle_array[side + turns] = (
                TAILWIND_TURNS if cond == _SIDECONDITION_TAILWIND else FIELD_EFFECT_TURNS
            )
            if cond & SCREENS:
                battle_array[side + turns] += screen_bonus


@njit
def _set_future_attack(atk, defn, mv, battle_array, side, weather):
    """
    Future Sight and Doom Desire on the target's side, side its Field.SIDE_COND: they fail while one
    is waiting there, else the hit comes at the end of the turn after next with the damage fixed
    now (pokeplatinum BtlCmd_TryFutureSight). Returns True if it was set up
    """
    if battle_array[side] & _SIDECONDITION_FUTURE_SIGHT:
        return False
    battle_array[side] |= _SIDECONDITION_FUTURE_SIGHT
    battle_array[side + SIDE_FUTURE_TURNS] = FUTURE_ATTACK_TURNS
    battle_array[side + SIDE_FUTURE_MOVE] = mv[_MOVE_ID]
    battle_array[side + SIDE_FUTURE_DAMAGE] = future_damage(atk, defn, mv, weather, battle_array[side])
    return True


@njit
def _set_wish(battle_array, side):
    """Wish on the user's side, side its Field.SIDE_COND: it fails while one is waiting there, else it
    heals at the end of the next turn (pokeplatinum BtlCmd_TryWish)"""
    if battle_array[side] & _SIDECONDITION_WISH:
        return
    battle_array[side] |= _SIDECONDITION_WISH
    battle_array[side + SIDE_WISH_TURNS] = WISH_TURNS


@njit
def _wish_heal(battle_array, side, pok):
    """
    The Wish on side counts down, and when it comes true it heals half of max HP of whoever is
    there now, at least 1. Nothing for a fainted, Heal Blocked or full HP one (pokeplatinum
    FIELD_COND_CHECK_STATE_WISH, subscript_wish_heal)
    """
    if not battle_array[side] & _SIDECONDITION_WISH:
        return
    battle_array[side + SIDE_WISH_TURNS] -= 1
    if battle_array[side + SIDE_WISH_TURNS] > 0:
        return
    battle_array[side] &= ~_SIDECONDITION_WISH
    battle_array[side + SIDE_WISH_TURNS] = 0
    if pok[_POK_CURRENT_HP] <= 0 or heal_blocked(pok) or pok[_POK_CURRENT_HP] >= pok[_POK_MAX_HP]:
        return
    pok[_POK_CURRENT_HP] = min(pok[_POK_MAX_HP], pok[_POK_CURRENT_HP] + max(1, pok[_POK_MAX_HP] // 2))


@njit
def _future_attack_hit(battle_array, side, target, foe, weather, gravity):
    """
    The Future Sight on side counts down, and when it's due it hits whoever is there now, unless it
    fainted. Its Substitute takes it, Endure and the focus items hold on, Rage builds. No contact,
    on-hit ability or damage record. The HP berries check right after, like a move hit ([SD]
    futuremove runs the hit as a move) (pokeplatinum SIDE_COND_CHECK_STATE_FUTURE_SIGHT,
    subscript_future_sight_damage)
    """
    if not battle_array[side] & _SIDECONDITION_FUTURE_SIGHT:
        return
    battle_array[side + SIDE_FUTURE_TURNS] -= 1
    if battle_array[side + SIDE_FUTURE_TURNS] > 0:
        return
    damage = battle_array[side + SIDE_FUTURE_DAMAGE]
    move_id = battle_array[side + SIDE_FUTURE_MOVE]
    battle_array[side] &= ~_SIDECONDITION_FUTURE_SIGHT
    battle_array[side + SIDE_FUTURE_TURNS] = 0
    battle_array[side + SIDE_FUTURE_DAMAGE] = 0
    battle_array[side + SIDE_FUTURE_MOVE] = 0
    if target[_POK_CURRENT_HP] <= 0:
        return
    if not future_hit_lands(MOVE_TABLE[move_id], foe, target, weather, gravity):
        return
    if has_substitute(target):
        hit_substitute(target, damage)
        return
    damage = endure_damage(target, damage, focus_sash_ready(target))
    if damage >= target[_POK_CURRENT_HP]:
        target[_POK_CURRENT_HP] = 0
        return
    target[_POK_CURRENT_HP] -= damage
    if target[_POK_VOL_STATUS] & _VOLSTATUS_RAGE and damage > 0:
        target[_POK_ATTACK_STAT_STAGE] = min(6, target[_POK_ATTACK_STAT_STAGE] + 1)
    if target[_ITEM_WHEN] & _ITEMACTIVATION_ON_RECEIVE_DAMAGE:
        item_on_rdmg(target)


@njit
def _move_weather(move_id):
    """Weather the move sets, 0 if it isn't a weather move"""
    for weather_move, weather in WEATHER_MOVES:
        if move_id == weather_move:
            return weather
    return 0


@njit
def _set_weather(battle_array, weather, user):
    """A weather move fails under the same weather, whatever set it (Showdown; pokeplatinum's Hail
    only fails under a move's hail), else it lasts 5 turns plus the user's matching rock
    (pokeplatinum effect scripts 0115, 0136, 0137, 0164)"""
    if battle_array[_FIELD_WEATHER] == weather:
        return
    battle_array[_FIELD_WEATHER] = weather
    battle_array[_FIELD_WEATHER_DURATION] = FIELD_EFFECT_TURNS
    for rock_weather, effect in WEATHER_ROCKS:
        if weather == rock_weather:
            battle_array[_FIELD_WEATHER_DURATION] += _held_extension(user, effect)


@njit
def _set_gravity(battle_array, atk, defn):
    """
    Gravity fails while up, else it lasts 5 turns and brings down a Pokemon in the air (Bounce),
    whose attack doesn't happen, and ends Magnet Rise (pokeplatinum subscript_gravity_start)
    """
    if battle_array[_FIELD_GRAVITY_TURNS] > 0:
        return
    battle_array[_FIELD_GRAVITY_TURNS] = FIELD_EFFECT_TURNS
    for pok in (atk, defn):
        if pok[_POK_SEMI_INV_MOVE] in AIRBORNE_MOVES:
            unlock_move(pok)
        end_magnet_rise(pok)


@njit
def _set_trick_room(battle_array):
    """Trick Room lasts 5 turns, and used while up it ends instead (pokeplatinum effect_script_0259)"""
    battle_array[_FIELD_TRICKROOM] = 0 if battle_array[_FIELD_TRICKROOM] > 0 else FIELD_EFFECT_TURNS


@njit
def _clear_side(battle_array, side, conds):
    """Removes these side conditions with their turn counters and spikes layers"""
    battle_array[side] &= ~conds
    for bit, turns in TIMED_SIDE_CONDITIONS:
        if bit & conds:
            battle_array[side + turns] = 0
    if conds & _SIDECONDITION_TOXIC_SPIKES:
        battle_array[side + SIDE_TOXIC_SPIKES] = 0
    if conds & _SIDECONDITION_SPIKES:
        battle_array[side + SIDE_SPIKES] = 0


@njit
def _defog(atk, defn, battle_array, def_side):
    """
    Defog: the target's evasion -1, then its side loses its screens, Mist, Safeguard and hazards
    (pokeplatinum subscript_defog, so Mist still blocks the drop). Behind a Substitute only the
    drop is skipped (Showdown gen5 defog onHit)
    """
    if not has_substitute(defn):
        stat_changes(DEFOG_DROP, atk, defn, False, battle_array[def_side])
    _clear_side(battle_array, def_side, DEFOG_CLEARS)


@njit
def _after_hit_field(atk, mv, battle_array, atk_side, def_side):
    """
    Brick Break shatters the target side's screens, Rapid Spin frees the user from a bind and Leech
    Seed and clears the hazards on its own side. Both only once the move hit
    """
    move_id = mv[_MOVE_ID]
    if move_id == _MOVENAME_BRICK_BREAK:
        _clear_side(battle_array, def_side, SCREENS)
    elif move_id == _MOVENAME_RAPID_SPIN:
        atk[_POK_VOL_STATUS] &= ~(_VOLSTATUS_LEECH_SEED | _VOLSTATUS_PARTIALLY_TRAPPED)
        atk[_POK_TRAP_TURNS] = 0
        _clear_side(battle_array, atk_side, RAPID_SPIN_CLEARS)


@njit
def _called_move_array(atk, move_id):
    """The called move's array, a called Hidden Power has the user's own type and power"""
    mv = MOVE_TABLE[move_id].copy()
    if move_id == _MOVENAME_HIDDEN_POWER:
        mv[_MOVE_TYPE] = atk[_POK_HIDDEN_POWER_TYPE]
        mv[_MOVE_POWER] = atk[_POK_HIDDEN_POWER_POWER]
    return mv


@njit
def _stolen_by(mv, foe):
    """The foe's turn flag that takes this move: Magic Coat for a reflectable one, Snatch for a
    snatchable one, 0 for neither"""
    if foe[_POK_CURRENT_HP] <= 0:
        return 0
    vol2 = foe[_POK_VOL_STATUS2]
    if vol2 & _VOLSTATUS2_MAGIC_COAT and mv[_FLAGS_REFLECTABLE]:
        return _VOLSTATUS2_MAGIC_COAT
    if vol2 & _VOLSTATUS2_SNATCH and mv[_FLAGS_SNATCH]:
        return _VOLSTATUS2_SNATCH
    return 0


@njit
def _stolen_pressure(taker, user, slot, taker_is_opp, battle_array):
    """The original user's Pressure costs the taker one more PP of the move it selected
    (pokeplatinum BattleSystem_DecPPForPressure in MoveStolen)"""
    if user[_POK_AB_ID] != _ABILITYNAMES_PRESSURE or slot < 0 or slot > 3:
        return
    pp_idx = OFFSET_MOVE + slot * MOVE_STRIDE + _MOVE_PP
    if taker[pp_idx] > 0:
        taker[pp_idx] -= 1
        if taker_is_opp:
            battle_array[_FIELD_OPP_MOVE_RAN] += OPP_RAN_PP_STEP


@njit
def _execute_move_slot(
        atk, defn, mv, is_mine, current_move, opp_move,
        flinch_in, slot_num, is_last, battle_array, weather,
        rec_p=False, rec_s=False
):
    """
    Run one move-slot (whichever attacker acts in this position) end to end:
    early-return checks, PP, last-move bookkeeping, charge/lock, hit check,
    damage/effects, trainer-ai bookkeeping.
    is_last: nothing acts after this slot (Protect and Endure fail).
    Returns the flinch this slot produced (False if it didn't attack/hit).
    """
    if atk[_POK_CURRENT_HP] <= 0:
        return False
    # Metronome and co. keep their slot locked, a locked turn replays the move they called
    outer_id = mv[_MOVE_ID]
    is_caller = outer_id in CALLER_MOVES
    if atk[_POK_LOCKED_MOVE] == -1:
        atk[_POK_CALLED_MOVE] = 0
    elif is_caller and atk[_POK_CALLED_MOVE]:
        mv = _called_move_array(atk, atk[_POK_CALLED_MOVE])
    gravity = battle_array[_FIELD_GRAVITY_TURNS] > 0
    if early_returns(atk, defn, slot_num, flinch_in, mv, gravity):
        # A turn without the move resets Protect's consecutive count and the last move
        atk[_POK_PROTECT_COUNT] = 0
        atk[_POK_LAST_MOVE_ID] = 0
        return False
    # A Spite before it moved took its last PP: no PP left for the move, it fails and leaves no
    # last move (pokeplatinum BattleControllerPlayer_DecrementPP, MOVE_STATUS_NO_PP)
    if atk[_POK_LOCKED_MOVE] == -1 and mv[_MOVE_ID] != _MOVENAME_STRUGGLE and mv[_MOVE_PP] <= 0:
        atk[_POK_LAST_MOVE_ID] = 0
        return False
    atk[_POK_LAST_MOVE_ID] = outer_id
    record_last_resort(atk, current_move if is_mine else opp_move, outer_id)
    if mv[_MOVE_ID] not in STALL_MOVES:
        atk[_POK_PROTECT_COUNT] = 0
    # The Metronome item counts the selected move on turns it isn't locked into. A move aimed at a
    # foe that already fainted leaves the count as it was (pokeplatinum HasNoTarget runs first)
    counted = atk[_POK_LOCKED_MOVE] == -1 and not (
        defn[_POK_CURRENT_HP] <= 0 and mv[_MOVE_TARGET] not in NO_FOE_TARGETS
    )
    if counted:
        metronome_count(atk, outer_id)

    pp_before = mv[_MOVE_PP]
    if mv[_MOVE_ID] != _MOVENAME_STRUGGLE:
        if atk[_POK_LOCKED_MOVE] == -1:
            mv[_MOVE_PP] -= 1
            pressure_pp(mv, defn)
        if is_mine:
            battle_array[_FIELD_MY_LAST_MOVE] = outer_id
            battle_array[_FIELD_AI_KNOWS] |= AI_KNOWS_MOVES[current_move]
    elif is_mine:
        battle_array[_FIELD_MY_LAST_MOVE] = -1  #-1 Means Struggle
    if not is_mine:
        battle_array[_FIELD_OPP_MOVE_RAN] = opp_move + 1 + OPP_RAN_PP_STEP * (pp_before - mv[_MOVE_PP])

    # The called move runs in the caller's turn, the caller is the last move for everything else
    if is_caller and atk[_POK_CALLED_MOVE] == 0:
        called = called_move(atk, defn, outer_id, battle_array)
        battle_array[_FIELD_LAST_MOVE] = outer_id
        if called == 0:
            metronome_fail(atk, outer_id)
            return False
        atk[_POK_CALLED_MOVE] = called
        caller_pp = mv[_MOVE_PP]
        mv = _called_move_array(atk, called)
        # A called move sees the caller's PP, for Trump Card (pokeplatinum ATTACKER_MOVE_SLOT)
        mv[_MOVE_PP] = caller_pp
        # A called move Gravity stops fails like a selected one (Showdown onModifyMove)
        # Heal Block's moves too, like Gravity's (Showdown healblock onModifyMove)
        if (gravity and mv[_FLAGS_GRAVITY]) or heal_block_stops(atk, called):
            unlock_move(atk)
            metronome_fail(atk, outer_id)
            return False
    else:
        battle_array[_FIELD_LAST_MOVE] = outer_id
    is_called = is_caller and atk[_POK_CALLED_MOVE] != 0
    # Snore fails unless the user is asleep, a turn it woke up on included (Sleep Talk's is in
    # called_move, [SD] onTry)
    if mv[_MOVE_SLEEP_USABLE] and atk[_POK_STATUS] != _STATUS_SLEEP:
        if counted:
            metronome_fail(atk, outer_id)
        return False

    # Charge moves are positive so they don't do anything first turn, Power Herb hits right away.
    # Solar Beam skips the charge in sun and keeps the Power Herb (pokeplatinum effect 0151)
    if (
        mv[_MOVE_CHARGE_RECHARGE] > 0 and atk[_POK_LOCKED_MOVE] == -1
        and not (mv[_MOVE_ID] == _MOVENAME_SOLAR_BEAM and weather == _WEATHER_SUN)
    ):
        # Skull Bash raises Defense on the charge turn, before a Power Herb hit too (pokeplatinum
        # effect 0145, subscript_power_herb_skull_bash)
        if mv[_MOVE_ID] == _MOVENAME_SKULL_BASH:
            atk[_POK_DEFENSE_STAT_STAGE] = min(6, atk[_POK_DEFENSE_STAT_STAGE] + 1)
        if not power_herb(atk, mv):
            atk[_POK_CHARGE_RECHARGE] = mv[_MOVE_CHARGE_RECHARGE]
            atk[_POK_LOCKED_MOVE] = current_move if is_mine else opp_move
            if mv[_MOVE_VOL_STATUS] & _VOLSTATUS_BIDE:
                atk[_POK_VOL_STATUS] += _VOLSTATUS_BIDE
            if mv[_MOVE_ID] in SEMI_INVULNERABLE_MOVES:
                atk[_POK_VOL_STATUS] |= _VOLSTATUS_SEMI_INVULNERABLE
                atk[_POK_SEMI_INV_MOVE] = mv[_MOVE_ID]
            return False

    # Reset locked Move
    if mv[_MOVE_CHARGE_RECHARGE] > 0:
        atk[_POK_LOCKED_MOVE] = -1
        atk[_POK_VOL_STATUS] &= ~_VOLSTATUS_SEMI_INVULNERABLE
        atk[_POK_SEMI_INV_MOVE] = 0
    # The foe fainted (recoil, Explosion...): PP is spent, a move aimed at it fails.
    # TODO: Some moves still go through, like future sight
    if defn[_POK_CURRENT_HP] <= 0 and mv[_MOVE_TARGET] not in NO_FOE_TARGETS:
        if counted:
            metronome_fail(atk, outer_id)
        return False

    # The foe's Magic Coat sends the move back, its Snatch takes it: from here the move runs with
    # the foe as its user, once per turn (pokeplatinum BattleControllerPlayer_MoveStolen, after
    # the PP and the target check)
    stolen = _stolen_by(mv, defn)
    if stolen:
        defn[_POK_VOL_STATUS2] &= ~stolen
        _stolen_pressure(defn, atk, opp_move if is_mine else current_move, is_mine, battle_array)
        atk, defn = defn, atk
        is_mine = not is_mine
        counted = False
        if heal_block_stops(atk, mv[_MOVE_ID]):
            return False

    _consec_before_move(atk, mv, current_move if is_mine else opp_move)
    if mv[_MOVE_ID] == _MOVENAME_NATURAL_GIFT and not natural_gift(atk, mv):
        metronome_fail(atk, outer_id)
        return False
    # Fling takes its power and effect from the item, which is thrown even if the move misses
    if mv[_MOVE_ID] == _MOVENAME_FLING:
        if fling_fails(atk):
            metronome_fail(atk, outer_id)
            return False
        mv = fling_move(atk, defn, mv)
    if mv[_MOVE_ID] in STALL_MOVES:
        try_protect(atk, mv[_MOVE_ID], is_last)
        return False
    # Magic Coat and Snatch fail when nothing acts after the user (pokeplatinum
    # BtlCmd_TrySetMagicCoat, BtlCmd_TrySnatch)
    if mv[_MOVE_ID] == _MOVENAME_MAGIC_COAT or mv[_MOVE_ID] == _MOVENAME_SNATCH:
        if is_last:
            if counted:
                metronome_fail(atk, outer_id)
            return False
        if mv[_MOVE_ID] == _MOVENAME_MAGIC_COAT:
            atk[_POK_VOL_STATUS2] |= _VOLSTATUS2_MAGIC_COAT
        else:
            atk[_POK_VOL_STATUS2] |= _VOLSTATUS2_SNATCH
        return False
    target_action = opp_move if is_mine else current_move
    if (
        counter_fails(atk, mv, slot_num) or endeavor_fails(atk, defn, mv)
        or sucker_punch_fails(defn, mv, slot_num, target_action) or lost_focus(atk, mv)
    ):
        if counted:
            metronome_fail(atk, outer_id)
        return False
    if turn_order_doubles(atk, mv, slot_num, target_action):
        mv = mv.copy()
        mv[_MOVE_POWER] *= 2
    # Gen IV Feint fails unless the target is protecting, then it lifts the protection
    if mv[_MOVE_ID] == _MOVENAME_FEINT:
        if not defn[_POK_VOL_STATUS] & _VOLSTATUS_PROTECT:
            metronome_fail(atk, outer_id)
            return False
        defn[_POK_VOL_STATUS] &= ~_VOLSTATUS_PROTECT
    # Perish Song has no hit check, each Pokemon is checked on its own (a Soundproof foe doesn't
    # stop the user from getting a count)
    if mv[_MOVE_ID] == _MOVENAME_PERISH_SONG:
        perish_song(atk, defn)
        return False
    # Future Sight and Doom Desire have no hit check when used, they only set up the hit
    if mv[_FLAGS_FUTURE_MOVE]:
        set_up = _set_future_attack(atk, defn, mv, battle_array, side_base(not is_mine), weather)
        if not set_up and counted:
            metronome_fail(atk, outer_id)
        return False
    # Spit Up empties the stockpile before the hit check, a miss loses it too (pokeplatinum effect 0161)
    if mv[_MOVE_ID] == _MOVENAME_SPIT_UP:
        count = release_stockpile(atk)
        if count == 0:
            if counted:
                metronome_fail(atk, outer_id)
            return False
        mv = mv.copy()
        mv[_MOVE_POWER] = SPIT_UP_POWER * count

    # Explosion and Selfdestruct faint the user before the hit check, so a miss, Protect or an
    # immune target still costs it. Damp stops the whole move (Showdown gen4 useMoveInner)
    if mv[_MOVE_ID] in EXPLODE_MOVES and not damp_blocks(atk, defn):
        atk[_POK_CURRENT_HP] = 0
    # Beat Up fails with nobody to hit (Showdown gen4, no allies)
    if mv[_MOVE_ID] == _MOVENAME_BEAT_UP and _beat_up_members(battle_array, is_mine) == 0:
        if counted:
            metronome_fail(atk, outer_id)
        return False
    # Last Resort fails until the user used its other moves (pokeplatinum effect 0246, before the hit)
    if mv[_MOVE_ID] == _MOVENAME_LAST_RESORT and not last_resort_works(atk):
        if counted:
            metronome_fail(atk, outer_id)
        return False
    if mv[_MOVE_ID] == _MOVENAME_PRESENT:
        mv = _present_move(mv)
    elif mv[_MOVE_ID] == _MOVENAME_SECRET_POWER:
        mv = secret_power_move(mv, battle_array)
    elif mv[_MOVE_ID] == _MOVENAME_WEATHER_BALL:
        mv = weather_ball_move(mv, weather)
    move_hit = calculate_hit_miss(mv, atk, defn, weather, gravity, is_last)
    if move_hit != _MOVEOUTCOME_HIT:
        if mv[_MOVE_ID] == _MOVENAME_FLING:
            fling_throw(atk)
        # A rampage keeps counting through the same outcomes as an uproar (pokeplatinum
        # BattleContext_MoveFailed only has the immunity)
        keeps_on = atk[_POK_VOL_STATUS] & _VOLSTATUS_UPROAR or atk[_POK_RAMPAGE_TURNS] > 0
        if not (keeps_on and move_hit in UPROAR_KEEPS_ON):
            unlock_move(atk)
        _crash(atk, defn, mv, weather, battle_array[side_base(not is_mine)], gravity)
        if counted:
            metronome_fail(atk, outer_id)
        return False
    # Shadow Force goes through Protect and lifts it (pokeplatinum effect 272, the Feint subscript)
    if mv[_MOVE_ID] == _MOVENAME_SHADOW_FORCE:
        defn[_POK_VOL_STATUS] &= ~_VOLSTATUS_PROTECT
    if mv[_MOVE_TARGET] not in NO_FOE_TARGETS and not stolen:
        mirror_record(mv, defn, is_called)
    if mv[_MOVE_ID] == _MOVENAME_PRESENT and mv[_MOVE_POWER] == 0:
        _present_heal(defn)
        return False

    atk_side = side_base(is_mine)
    def_side = side_base(not is_mine)
    if mv[_MOVE_CATEGORY] in PHYSICAL_SPECIAL:
        _consec_on_hit(atk, mv)
        if mv[_MOVE_ID] == _MOVENAME_BEAT_UP:
            flinch, hit_pok, dealt = _beat_up(
                atk, defn, mv, battle_array, is_mine, weather, rec_p,
                battle_array[def_side], gravity
            )
        elif mv[_MOVE_MULTI_HIT_MIN]:
            flinch, hit_pok, dealt = ps_moves_multihit(
                atk, defn, mv, weather, rec_p, rec_s, battle_array[def_side], gravity, is_last
            )
        else:
            flinch, hit_pok, dealt = ps_moves(
                atk, defn, mv, weather, rec_p, rec_s, battle_array[def_side], gravity,
                battle_array[atk_side]
            )
        _after_hit_field(atk, mv, battle_array, atk_side, def_side)
        # Hyper Beam and co. recharge after any hit, a KO or a Substitute hit included (pokeplatinum
        # MOVE_SUBSCRIPT_PTR_RECHARGE_TURN is an on-hit side effect)
        if mv[_MOVE_CHARGE_RECHARGE] < 0:
            atk[_POK_CHARGE_RECHARGE] = -1
            atk[_POK_LOCKED_MOVE] = current_move if is_mine else opp_move
        if mv[_MOVE_ID] in ROLLOUT_MOVES and atk[_POK_CONSEC_COUNT] >= ROLLOUT_MAX_USES:
            unlock_move(atk)
        if mv[_MOVE_ID] == _MOVENAME_RAGE:
            atk[_POK_VOL_STATUS] |= _VOLSTATUS_RAGE
        # Uproar locks in on its first hit for 3-6 turns, this one included
        if mv[_MOVE_ID] == _MOVENAME_UPROAR and not atk[_POK_VOL_STATUS] & _VOLSTATUS_UPROAR:
            atk[_POK_VOL_STATUS] |= _VOLSTATUS_UPROAR
            atk[_POK_UPROAR_TURNS] = random.randint(3, 6)
            atk[_POK_LOCKED_MOVE] = current_move if is_mine else opp_move
        # Thrash and co. lock in on their first hit for 2-3 turns, this one included, a KO or a
        # Substitute hit too (pokeplatinum subscript_thrash, an on-hit side effect)
        if mv[_MOVE_ID] in RAMPAGE_MOVES and atk[_POK_RAMPAGE_TURNS] == 0:
            atk[_POK_RAMPAGE_TURNS] = random.randint(2, 3)
            atk[_POK_LOCKED_MOVE] = current_move if is_mine else opp_move
        # Wrap and co. trap a target that survived for 3-6 turns, it isn't refreshed. The
        # binder's Grip Claw makes it 6, after the roll (pokeplatinum subscript_bind_start)
        if (
            mv[_MOVE_VOL_STATUS] & _VOLSTATUS_PARTIALLY_TRAPPED
            and hit_pok
            and defn[_POK_CURRENT_HP] > 0
            and not defn[_POK_VOL_STATUS] & _VOLSTATUS_PARTIALLY_TRAPPED
        ):
            defn[_POK_VOL_STATUS] |= _VOLSTATUS_PARTIALLY_TRAPPED
            defn[_POK_TRAP_TURNS] = random.randint(3, 6)
            if atk[_ITEM_HOLD_EFFECT] == _HOLDEFFECT_EXTEND_TRAPPING:
                defn[_POK_TRAP_TURNS] = 6
        # Destiny Bond, after drain and recoil like the Gen IV faint check
        if defn[_POK_CURRENT_HP] <= 0 and defn[_POK_VOL_STATUS] & _VOLSTATUS_DESTINY_BOND:
            mark_hurt(atk)
            atk[_POK_CURRENT_HP] = 0
        _grudge(atk, defn, current_move if is_mine else opp_move)
        after_move_hit_items(atk, mv, dealt, hit_pok)
        # Information for trainer ai logic, not set by a hit its Substitute took
        if is_mine and hit_pok:
            battle_array[_FIELD_AI_TOOK_DMG_LAST_TURN] = normalized_type(atk, mv)
        # Check to see if the move from the attacker thawed the defender, not through a
        # Substitute (Showdown frz onDamagingHit)
        if hit_pok and defn[_POK_STATUS] == _STATUS_FREEZE:
            thaw(atk, mv, defn)
        if mv[_MOVE_SELF_SWITCH]:
            _u_turn_start(atk, defn, battle_array, is_mine)
        return flinch

    # A status move aimed at a foe behind a Substitute fails, unless it bypasses it
    if (
        sub_blocks_status_move(mv, atk, defn, weather) or confuse_boost_fails(mv, defn)
        or stage_move_fails(mv, atk, defn) or status_move_fails(mv, atk, defn)
        or type_move_fails(mv, atk, defn, battle_array[_FIELD_TERRAIN], weather)
    ):
        if counted:
            metronome_fail(atk, outer_id)
        return False
    # Memento faints the user once it reached the target, also when the drops do nothing (Showdown
    # selfdestruct "ifHit": a miss, Protect or a Substitute spares it)
    if mv[_MOVE_ID] == _MOVENAME_MEMENTO:
        atk[_POK_CURRENT_HP] = 0
    if mv[_MOVE_ID] == _MOVENAME_HEALING_WISH:
        if not _healing_wish(atk, defn, battle_array, is_mine) and counted:
            metronome_fail(atk, outer_id)
        return False
    if mv[_MOVE_FORCE_SWITCH]:
        _force_switch(atk, defn, battle_array, not is_mine)
        return False
    if mv[_MOVE_SELF_SWITCH]:
        _baton_pass(atk, defn, battle_array, is_mine)
        return False
    if mv[_MOVE_SIDE_CONDITION]:
        _set_side_condition(
            mv[_MOVE_SIDE_CONDITION], battle_array,
            def_side if mv[_MOVE_TARGET] == FOE_SIDE_TARGET else atk_side,
            _held_extension(atk, _HOLDEFFECT_EXTEND_SCREENS)
        )
        return False
    move_weather = _move_weather(mv[_MOVE_ID])
    if move_weather:
        _set_weather(battle_array, move_weather, atk)
        return False
    if mv[_MOVE_ID] == _MOVENAME_GRAVITY:
        _set_gravity(battle_array, atk, defn)
        return False
    if mv[_MOVE_ID] == _MOVENAME_TRICK_ROOM:
        _set_trick_room(battle_array)
        return False
    if mv[_MOVE_ID] == _MOVENAME_DEFOG:
        _defog(atk, defn, battle_array, def_side)
        return False
    if mv[_MOVE_ID] in COPY_MOVES:
        _copy_move(atk, defn, mv[_MOVE_ID], is_mine, battle_array)
        return False
    _status_move(atk, defn, mv, is_mine, battle_array, weather)
    calculate_effects(atk, defn, mv, weather, battle_array[def_side])
    return False


@njit
def _copy_move(atk, defn, move_id, is_mine, battle_array):
    """
    Mimic, Sketch and Transform. The AI knows a move of mine once it saw it used, so a slot of mine
    that changed is unknown to it again (pokeplatinum TrainerAI_RecordLastMove goes by move id)
    """
    if move_id == _MOVENAME_TRANSFORM:
        transform(atk, defn, battle_array, is_mine)
        if is_mine:
            for known in AI_KNOWS_MOVES:
                battle_array[_FIELD_AI_KNOWS] &= ~known
        return
    if move_id == _MOVENAME_MIMIC:
        slot = mimic(atk, defn)
    else:
        slot = sketch(atk, defn)
    if is_mine and slot >= 0:
        battle_array[_FIELD_AI_KNOWS] &= ~AI_KNOWS_MOVES[slot]


@njit
def _status_move(atk, defn, mv, is_mine, battle_array, weather):
    """Recover, Synthesis, Refresh, Recycle, Worry Seed, Substitute, Trick, Switcheroo, Embargo,
    Pain Split, Belly Drum, Acupressure, Haze, Psych Up, Power Swap, Guard Swap, Heart Swap, Power
    Trick, Rest, Psycho Shift, Heal Bell, Aromatherapy, Magnet Rise, Torment, Imprison, Mean Look,
    Block, Spider Web, Spite and Minimize's flag (its boost is data)"""
    move_id = mv[_MOVE_ID]
    if move_id == _MOVENAME_MINIMIZE:
        atk[_POK_VOL_STATUS2] |= _VOLSTATUS2_MINIMIZE
    elif move_id == _MOVENAME_SUBSTITUTE:
        make_substitute(atk)
    elif move_id in HEAL_MOVES:
        # Roost drops the Flying type for the rest of the turn, only if it healed (pokeplatinum
        # subscript_roost, TURN_FLAG_ROOSTING)
        if heal_move(atk, move_id, weather) and move_id == _MOVENAME_ROOST:
            atk[_POK_VOL_STATUS2] |= _VOLSTATUS2_ROOST
    elif move_id == _MOVENAME_REFRESH:
        refresh(atk)
    elif move_id == _MOVENAME_RECYCLE:
        recycle(atk)
    elif move_id in SWAP_MOVES:
        swap_items(atk, defn)
    elif move_id == _MOVENAME_EMBARGO:
        embargo(defn)
    elif move_id == _MOVENAME_MAGNET_RISE:
        start_magnet_rise(atk)
    elif move_id == _MOVENAME_PAIN_SPLIT:
        _pain_split(atk, defn)
    elif move_id == _MOVENAME_BELLY_DRUM:
        belly_drum(atk)
    elif move_id == _MOVENAME_ACUPRESSURE:
        acupressure(atk)
    elif move_id == _MOVENAME_HAZE:
        haze(atk, defn)
    elif move_id == _MOVENAME_PSYCH_UP:
        psych_up(atk, defn)
    elif move_id in STAGE_SWAP_MOVES:
        swap_stages(atk, defn, move_id)
    elif move_id == _MOVENAME_POWER_TRICK:
        power_trick(atk)
    elif move_id == _MOVENAME_REST:
        rest(atk)
    elif move_id == _MOVENAME_PSYCHO_SHIFT:
        psycho_shift(mv, atk, defn, battle_array[side_base(not is_mine)], weather)
    elif move_id == _MOVENAME_HEAL_BELL or move_id == _MOVENAME_AROMATHERAPY:
        heal_bell(battle_array, atk, move_id, is_mine)
    elif move_id == _MOVENAME_STOCKPILE:
        stockpile(atk)
    elif move_id == _MOVENAME_SWALLOW:
        swallow(atk)
    elif move_id == _MOVENAME_WISH:
        _set_wish(battle_array, side_base(is_mine))
    elif move_id == _MOVENAME_GRUDGE:
        atk[_POK_VOL_STATUS2] |= _VOLSTATUS2_GRUDGE
    elif move_id == _MOVENAME_TORMENT:
        defn[_POK_VOL_STATUS2] |= _VOLSTATUS2_TORMENT
    elif move_id == _MOVENAME_IMPRISON:
        atk[_POK_VOL_STATUS2] |= _VOLSTATUS2_IMPRISON
    elif move_id in TRAP_MOVES:
        defn[_POK_VOL_STATUS2] |= _VOLSTATUS2_MEAN_LOOK
    elif move_id in LOCK_ON_MOVES:
        atk[_POK_VOL_STATUS2] |= _VOLSTATUS2_LOCK_ON
        atk[_POK_LOCK_ON_TURNS] = LOCK_ON_DURATION
    elif move_id == _MOVENAME_MIRACLE_EYE:
        defn[_POK_VOL_STATUS2] |= _VOLSTATUS2_MIRACLE_EYE
    elif move_id == _MOVENAME_SPITE:
        spite(defn)
    elif move_id == _MOVENAME_GASTRO_ACID:
        suppress_ability(defn)
    elif move_id == _MOVENAME_ROLE_PLAY:
        role_play(atk, defn, battle_array, is_mine)
    elif move_id == _MOVENAME_SKILL_SWAP:
        skill_swap(atk, defn, battle_array, is_mine)
        # The AI knows the ability it gave me
        battle_array[_FIELD_AI_KNOWS] |= _ENEMY_AI_KNOWS_ABILITY
    elif move_id == _MOVENAME_CONVERSION:
        conversion(atk)
    elif move_id == _MOVENAME_CONVERSION_2:
        conversion2(atk, defn, weather)
    elif move_id == _MOVENAME_CAMOUFLAGE:
        camouflage(atk, battle_array[_FIELD_TERRAIN])
    # The AI learns my new ability (pokeplatinum BattleAI_SetAbility)
    elif move_id == _MOVENAME_WORRY_SEED and worry_seed(defn) and not is_mine:
        battle_array[_FIELD_AI_KNOWS] |= _ENEMY_AI_KNOWS_ABILITY


@njit
def _pain_split(atk, defn):
    """Both go to the average of their HP, capped at max HP. It isn't damage, but the one that
    loses HP counts as hurt for Assurance (pokeplatinum subscript_pain_split, subscript_update_hp,
    BtlCmd_UpdateHealthBarValue)"""
    average = (atk[_POK_CURRENT_HP] + defn[_POK_CURRENT_HP]) // 2
    _set_split_hp(atk, average)
    _set_split_hp(defn, average)


@njit
def _set_split_hp(pok, average):
    """Pain Split's HP for one side"""
    if average < pok[_POK_CURRENT_HP]:
        mark_hurt(pok)
    pok[_POK_CURRENT_HP] = min(average, pok[_POK_MAX_HP])


@njit
def _baton_pass(atk, defn, battle_array, is_mine):
    """
    Fails with nobody left to switch in. Mine stops the turn in the Baton Pass phase so I pick
    the replacement, the AI picks its own right away with its post-KO logic (pokeplatinum
    Task_TrainerShowPartyMenu → BattleAI_PostKOSwitchIn)
    """
    if _bench_alive(battle_array, is_mine) == 0:
        return
    if is_mine:
        battle_array[_FIELD_PHASE] = _BATTLEPHASE_BATON_PASS
        return
    opp_idx = battle_array[_FIELD_OPP_POK]
    i = sub_after_death(
        battle_array[(6 * POK_LEN):(12 * POK_LEN)], defn, atk, battle_array[_FIELD_MY_SIDE_COND],
        effective_weather(battle_array), opp_idx, battle_array[_FIELD_GRAVITY_TURNS] > 0
    )
    _switch_opp_side(battle_array, atk, defn, i, True)


@njit
def _grudge(atk, defn, slot):
    """
    Grudge: the foe whose move KOed the Grudge user loses every PP of that slot, the caller's for a
    called move. Only if it's still standing (after Destiny Bond) and it wasn't Struggle (pokeplatinum
    BtlCmd_TryGrudge in subscript_faint_check_destiny_bond)
    """
    if (
        defn[_POK_CURRENT_HP] <= 0 and defn[_POK_VOL_STATUS2] & _VOLSTATUS2_GRUDGE
        and atk[_POK_CURRENT_HP] > 0 and 0 <= slot < 4
    ):
        atk[OFFSET_MOVE + slot * MOVE_STRIDE + _MOVE_PP] = 0


@njit
def _healing_wish(atk, defn, battle_array, is_mine):
    """
    Healing Wish fails with nobody left to switch in. Otherwise the user faints and the replacement
    comes in mid-turn, healed once it survives the hazards (healing_wish_heal); one they KO is
    replaced right away (pokeplatinum effect 0220, subscript_healing_wish). Mine waits in the Baton
    Pass phase for my pick, the AI picks with its post-KO logic. Returns False if it failed
    """
    if _bench_alive(battle_array, is_mine) == 0:
        return False
    atk[_POK_CURRENT_HP] = 0
    battle_array[side_base(is_mine)] |= _SIDECONDITION_HEALING_WISH
    if is_mine:
        battle_array[_FIELD_PHASE] = _BATTLEPHASE_BATON_PASS
        return True
    while True:
        i = sub_after_death(
            battle_array[(6 * POK_LEN):(12 * POK_LEN)], defn, atk, battle_array[_FIELD_MY_SIDE_COND],
            effective_weather(battle_array), -1, battle_array[_FIELD_GRAVITY_TURNS] > 0
        )
        atk = _switch_opp_side(battle_array, atk, defn, i)
        if atk[_POK_CURRENT_HP] > 0 or _bench_alive(battle_array, False) == 0:
            return True


@njit
def _u_turn_start(atk, defn, battle_array, is_mine):
    """
    U-turn hit, a Substitute included (an on-hit side effect): the user leaves unless it fainted
    (Rough Skin, Life Orb, Destiny Bond), its bench is empty or the target's whole side is out
    (pokeplatinum subscript_attack_then_switch_out). Marks it, _u_turn_switch does the switch
    """
    if atk[_POK_CURRENT_HP] <= 0 or _bench_alive(battle_array, is_mine) == 0:
        return
    if defn[_POK_CURRENT_HP] <= 0 and _bench_alive(battle_array, not is_mine) == 0:
        return
    atk[_POK_VOL_STATUS2] |= _VOLSTATUS2_U_TURN


@njit
def _u_turn_switch(atk, defn, battle_array, is_mine):
    """
    The marked U-turn user leaves with a plain switch, unless a Pursuit KOed it first. Mine waits
    in the Baton Pass phase for my pick (the mark tells baton_pass_action not to pass anything),
    the AI picks right away with its post-KO logic
    """
    if atk[_POK_CURRENT_HP] <= 0:
        atk[_POK_VOL_STATUS2] &= ~_VOLSTATUS2_U_TURN
        return
    if is_mine:
        battle_array[_FIELD_PHASE] = _BATTLEPHASE_BATON_PASS
        return
    i = sub_after_death(
        battle_array[(6 * POK_LEN):(12 * POK_LEN)], defn, atk, battle_array[_FIELD_MY_SIDE_COND],
        effective_weather(battle_array), battle_array[_FIELD_OPP_POK],
        battle_array[_FIELD_GRAVITY_TURNS] > 0
    )
    _switch_opp_side(battle_array, atk, defn, i)


@njit
def _encore_slot(pok, slot):
    """Encore forces the encored move when the Pokemon acts, also on the turn Encore lands"""
    if pok[_POK_VOL_STATUS] & _VOLSTATUS_ENCORE and 0 <= slot < 4:
        return pok[_POK_ENCORE_TURNS] & SLOT_MASK
    return slot


@njit
def action(current_move, opp_move, battle_array):
    """Where the moves are calculated"""
    current_pokemon = battle_array[
        (battle_array[_FIELD_MY_POK] * POK_LEN):
        ((battle_array[_FIELD_MY_POK]+1) * POK_LEN)
    ]
    current_opp = battle_array[
        ((battle_array[_FIELD_OPP_POK]+6) * POK_LEN):
        ((battle_array[_FIELD_OPP_POK]+7) * POK_LEN)
    ]
    weather = effective_weather(battle_array)
    p1_switch = False
    p2_switch = False
    flinch = False
    if current_move < 0 and opp_move < 0:
        return  # Check if neither used an action, if so early return
    if current_move < 0:
        p1_switch = True
    if opp_move < 0:  # Switches mid battle are (-6..-1) and potions are -10..-40
        # TODO: Check everything if opponent switches, specially if they die on entering
        p2_switch = True

    mv1_slot, mv2_slot, count, first_is_mine = move_order(
        current_pokemon,
        current_move,
        current_opp,
        opp_move,
        p1_switch,
        p2_switch,
        weather,
        has_tailwind(battle_array[_FIELD_MY_SIDE_COND]),
        has_tailwind(battle_array[_FIELD_OPP_SIDE_COND]),
        trick_room_up(battle_array),
    )
    if count == 0:
        return
    atk1 = current_pokemon if first_is_mine else current_opp
    def1 = current_opp     if first_is_mine else current_pokemon
    atk2 = current_opp     if first_is_mine else current_pokemon
    def2 = current_pokemon if first_is_mine else current_opp

    mv1 = (atk1[OFFSET_MOVE + mv1_slot * MOVE_STRIDE :
                OFFSET_MOVE + (mv1_slot + 1) * MOVE_STRIDE]
        if mv1_slot != 10 else STRUGGLE.copy())

    mv2 = (atk2[OFFSET_MOVE + mv2_slot * MOVE_STRIDE :
                OFFSET_MOVE + (mv2_slot + 1) * MOVE_STRIDE]
        if mv2_slot != 10 else STRUGGLE.copy())

    if mv2_slot == -1:
        record_phy = False
        record_sp  = False
    else:
        # Metal Burst takes either kind of hit (pokeplatinum lastDamageTaken)
        burst = mv2[_MOVE_DAMAGE] == _DAMAGESOURCES_METAL_BURST
        record_phy = mv2[_MOVE_DAMAGE] == _DAMAGESOURCES_COUNTER or burst
        record_sp  = mv2[_MOVE_DAMAGE] == _DAMAGESOURCES_MAGIC_COAT or burst

    my_before = battle_array[_FIELD_MY_POK]
    opp_before = battle_array[_FIELD_OPP_POK]
    if count >= 1:
        flinch = _execute_move_slot(
            atk1, def1, mv1, first_is_mine, current_move, opp_move,
            flinch, 1, count == 1, battle_array, weather, record_phy, record_sp
        )
        update_choice_lock(atk1, mv1_slot)
        clear_target_choice_lock(def1, atk1)
        _clear_charge(atk1, mv1)
        if atk1[_POK_VOL_STATUS2] & _VOLSTATUS2_U_TURN:
            # A slower Pursuit hits the U-turn user on its way out and uses up its turn
            # (pokeplatinum BATTLE_SUBSCRIPT_PURSUIT)
            if count >= 2 and _pursuit(atk2, atk1, mv2_slot, not first_is_mine, battle_array):
                count = 1
            _u_turn_switch(atk1, def1, battle_array, first_is_mine)
        _after_move_items(battle_array)

    # My Baton Pass: the turn waits for my pick, the slower opponent's move runs after it
    if battle_array[_FIELD_PHASE] == _BATTLEPHASE_BATON_PASS:
        if count >= 2:
            battle_array[_FIELD_PENDING_OPP_MOVE] = mv2_slot + 1 + (PENDING_FLINCH if flinch else 0)
        return
    if count >= 2:
        # Roar or Whirlwind dragged the slower Pokemon out, the one coming in doesn't move
        if battle_array[_FIELD_OPP_POK if first_is_mine else _FIELD_MY_POK] != (
            opp_before if first_is_mine else my_before
        ):
            return
        # The AI Baton Passed or U-turned first, my move goes into the one it sent
        if not first_is_mine and battle_array[_FIELD_OPP_POK] != opp_before:
            def2 = battle_array[
                ((battle_array[_FIELD_OPP_POK]+6) * POK_LEN):((battle_array[_FIELD_OPP_POK]+7) * POK_LEN)
            ]

    if count >= 2:
        # Encore landed before the slower Pokemon moved
        enc_slot = _encore_slot(atk2, mv2_slot)
        if enc_slot != mv2_slot:
            mv2_slot = enc_slot
            mv2 = atk2[OFFSET_MOVE + mv2_slot * MOVE_STRIDE : OFFSET_MOVE + (mv2_slot + 1) * MOVE_STRIDE]
            if first_is_mine:
                opp_move = mv2_slot
            else:
                current_move = mv2_slot
        _execute_move_slot(
            atk2, def2, mv2, not first_is_mine, current_move, opp_move,
            flinch, 2, True, battle_array, effective_weather(battle_array)
        )
        update_choice_lock(atk2, mv2_slot)
        clear_target_choice_lock(def2, atk2)
        _clear_charge(atk2, mv2)
        if atk2[_POK_VOL_STATUS2] & _VOLSTATUS2_U_TURN:
            _u_turn_switch(atk2, def2, battle_array, not first_is_mine)
        _after_move_items(battle_array)


@njit
def _after_move_items(battle_array):
    """
    Status items of both actives after a move, whoever was hit or switched in by it
    (pokeplatinum AFTER_MOVE_EFFECT_ATTACKER_ITEM / DEFENDER_ITEM / HELD_ITEM_STATUS), then a
    status their ability forbids is cured (BattleControllerPlayer_MoveEnd)
    """
    mine = battle_array[
        (battle_array[_FIELD_MY_POK] * POK_LEN):((battle_array[_FIELD_MY_POK]+1) * POK_LEN)
    ]
    opp = battle_array[
        ((battle_array[_FIELD_OPP_POK]+6) * POK_LEN):((battle_array[_FIELD_OPP_POK]+7) * POK_LEN)
    ]
    status_item(mine)
    status_item(opp)
    recover_status_by_ability(mine)
    recover_status_by_ability(opp)
    # A move or a switch it caused changed the weather (pokeplatinum BattleSystem_TriggerFormChange)
    forecast_actives(battle_array)


@njit
def _apply_residual_damage(pok, dmg, enter_field_flag_idx, battle_array, enter_field) -> bool:
    """Applies residual damage, checks faint, and triggers items. Returns True if fainted."""
    if dmg <= 0:
        return False
    hp = pok[_POK_CURRENT_HP]
    pok[_POK_CURRENT_HP] = 0 if dmg > hp else hp - dmg
    if pok[_POK_CURRENT_HP] <= 0:
        if enter_field:
            battle_array[enter_field_flag_idx] = 0
        return True
    if pok[_ITEM_WHEN] & _ITEMACTIVATION_ON_RECEIVE_DAMAGE:
        item_on_rdmg(pok)
    return False


@njit
def _residual_heal(pok):
    """Ingrain and Aqua Ring heal 1/16 of max HP, Big Root adds 30%"""
    max_hp = pok[_POK_MAX_HP]
    if pok[_POK_CURRENT_HP] < max_hp:
        pok[_POK_CURRENT_HP] = min(max_hp, pok[_POK_CURRENT_HP] + big_root(pok, max(1, max_hp // 16)))


@njit
def _yawn(pok, foe, weather=0):
    """
    Yawn counts down at the end of the turn, at 0 the target falls asleep if it has no status
    and there's no uproar
    """
    pok[_POK_YAWN_TURNS] -= 1
    if pok[_POK_YAWN_TURNS] > 0:
        return
    pok[_POK_VOL_STATUS] &= ~_VOLSTATUS_YAWN
    # No move is being used, so nothing breaks Insomnia, Vital Spirit or Leaf Guard here. The
    # ability is checked first and its message names it (pokeplatinum subscript_fall_asleep)
    if ability_blocks_status(pok, pok, _STATUS_SLEEP, weather):
        reveal_ability(pok)
    elif pok[_POK_STATUS] == 0 and not sleep_blocked(pok, foe):
        pok[_POK_STATUS] = _STATUS_SLEEP
        pok[_POK_SLEEP_COUNTER] = TURNS_2_5[random.getrandbits(2)]
        pok[_POK_VOL_STATUS] &= ~_VOLSTATUS_NIGHTMARE


@njit
def _uproar_wake(pok):
    """The uproar wakes up a sleeping Pokemon that isn't Soundproof"""
    if (
        pok[_POK_STATUS] == _STATUS_SLEEP
        and pok[_POK_CURRENT_HP] > 0
        and pok[_POK_AB_ID] != _ABILITYNAMES_SOUNDPROOF
    ):
        pok[_POK_STATUS] = 0
        pok[_POK_SLEEP_COUNTER] = 0


@njit
def _sleep_ends_rampage(pok):
    """A Pokemon asleep when the turn ends loses its rampage, no confusion"""
    if pok[_POK_STATUS] == _STATUS_SLEEP and pok[_POK_RAMPAGE_TURNS] > 0:
        pok[_POK_RAMPAGE_TURNS] = 0
        pok[_POK_LOCKED_MOVE] = -1


@njit
def _count_down_slot_lock(pok, counter_idx, vol):
    """Encore/Disable counter (turns * SLOT_STEP + slot): one less turn, ends a turn after reaching 0"""
    if pok[counter_idx] >= SLOT_STEP:
        pok[counter_idx] -= SLOT_STEP
    else:
        pok[_POK_VOL_STATUS] &= ~vol
        pok[counter_idx] = 0


@njit
def _residual_weather(pok, weather, enter_field_flag_idx, battle_array):
    """Weather heal and damage for one side, Gen IV runs it for everyone before any other residual"""
    if pok[_POK_CURRENT_HP] <= 0:
        return
    heal_weather(pok, weather, pok[_POK_SEMI_INV_MOVE] in NO_WEATHER_MOVES)
    # Hydration cures any status in rain (pokeplatinum BtlCmd_EndOfTurnWeatherEffect)
    if weather == _WEATHER_RAIN and pok[_POK_STATUS] and pok[_POK_AB_ID] == _ABILITYNAMES_HYDRATION:
        cure_status(pok)
        reveal_ability(pok)
    # Underground (Dig) or underwater (Dive) the Pokemon takes no sandstorm or hail damage
    if (
        pok[_POK_AB_ID] != _ABILITYNAMES_MAGIC_GUARD
        and weather not in WEATHER_NOT_END_OF_TURN
        and pok[_POK_SEMI_INV_MOVE] not in NO_WEATHER_MOVES
    ):
        w_dmg = weather_dmg(pok, weather, pok[_POK_MAX_HP])
        # Solar Power's and Dry Skin's sun damage names it (pokeplatinum subscript_weather_continues)
        if w_dmg and weather == _WEATHER_SUN:
            reveal_ability(pok)
        _apply_residual_damage(
            pok, w_dmg, enter_field_flag_idx, battle_array, battle_array[enter_field_flag_idx]
        )


@njit
def _flame_orb(pok, side_cond, weather):
    """
    Flame Orb burns its holder unless it's Fire type, already has a status, is under Safeguard,
    has Water Veil, or Leaf Guard in sun (pokeplatinum subscript_burn, held item branch).
    Toxic Orb badly poisons it the same way, Poison and Steel types and Immunity instead
    (pokeplatinum subscript_badly_poison)
    """
    if pok[_ITEM_HOLD_EFFECT] == _HOLDEFFECT_PSN_USER:
        status = _STATUS_TOXIC
        immune1 = _TYPES_POISON
        immune2 = _TYPES_STEEL
    else:
        status = _STATUS_BURN
        immune1 = _TYPES_FIRE
        immune2 = _TYPES_FIRE
    if pok[_POK_STATUS]:
        return
    for t in (pok[_POK_TYPE1], pok[_POK_TYPE2]):
        if t == immune1 or t == immune2:
            return
    if side_cond & _SIDECONDITION_SAFEGUARD:
        return
    if ability_blocks_status(pok, pok, status, weather):
        reveal_ability(pok)
        return
    pok[_POK_STATUS] = status
    if status == _STATUS_TOXIC:
        pok[_POK_BADLY_POISON] = 1


@njit
def _gradual_item(pok, enter_field_flag_idx, battle_array, enter_field) -> bool:
    """
    Leftovers heals 1/16 below max HP, so does Black Sludge for a Poison type; anyone else loses
    1/8 to Black Sludge unless it has Magic Guard (pokeplatinum BattleSystem_TriggerLeftovers).
    Returns True if it fainted
    """
    effect = pok[_ITEM_HOLD_EFFECT]
    max_hp = pok[_POK_MAX_HP]
    if (
        effect == _HOLDEFFECT_HP_RESTORE_PSN_TYPE
        and pok[_POK_TYPE1] != _TYPES_POISON and pok[_POK_TYPE2] != _TYPES_POISON
    ):
        if pok[_POK_AB_ID] == _ABILITYNAMES_MAGIC_GUARD:
            return False
        return _apply_residual_damage(
            pok, max(1, max_hp // 8), enter_field_flag_idx, battle_array, enter_field
        )
    if effect in GRADUAL_HEAL_EFFECTS and pok[_POK_CURRENT_HP] < max_hp:
        pok[_POK_CURRENT_HP] = min(max_hp, pok[_POK_CURRENT_HP] + max(1, max_hp // 16))
    return False


@njit
def _leech_seed_heal(seeder, seeded, dealt, seeded_flag_idx, battle_array):
    """
    The seeder heals what the seeded Pokemon lost. Liquid Ooze hurts it by that much instead, a
    Magic Guard seeder takes nothing and both abilities are named (pokeplatinum
    subscript_leech_seed_effect). The seeder's Big Root raises both
    """
    dealt = big_root(seeder, dealt)
    if seeded[_POK_AB_ID] != _ABILITYNAMES_LIQUID_OOZE:
        # Heal Block stops the heal after the Liquid Ooze check
        if not heal_blocked(seeder):
            seeder[_POK_CURRENT_HP] = min(seeder[_POK_MAX_HP], seeder[_POK_CURRENT_HP] + dealt)
    elif seeder[_POK_AB_ID] == _ABILITYNAMES_MAGIC_GUARD:
        reveal_ability(seeder)
        reveal_ability(seeded)
    else:
        flag_idx = (
            _FIELD_OPP_ENTER_FIELD if seeded_flag_idx == _FIELD_MY_ENTER_FIELD
            else _FIELD_MY_ENTER_FIELD
        )
        _apply_residual_damage(seeder, dealt, flag_idx, battle_array, battle_array[flag_idx])


@njit
def _apply_residual(pok, foe, enter_field_flag_idx, battle_array):
    """
    Per-Pokemon residuals after the weather, on-residual ability, enter-field clear — one side.
    foe is the opposing active, which Leech Seed heals
    """
    """
    Gen IV order (pokeplatinum CheckMonConditions, Showdown gen4 residual suborders):
    Ingrain, Aqua Ring, Speed Boost, Leftovers / Black Sludge, Leech Seed, Psn/Tox, Burn, Curse,
    Bind, Bad Dreams, Uproar, Disable, Encore, Taunt, Yawn, status items, Flame / Toxic Orb and
    Sticky Barb
    """
    if pok[_POK_CURRENT_HP] <= 0:
        return
    enter_field = battle_array[enter_field_flag_idx]
    is_magic_guard = pok[_POK_AB_ID] == _ABILITYNAMES_MAGIC_GUARD

    # 1. Ingrain and Aqua Ring, Heal Block stops their heal
    if pok[_POK_VOL_STATUS] & _VOLSTATUS_INGRAIN and not heal_blocked(pok):
        _residual_heal(pok)
    if pok[_POK_VOL_STATUS] & _VOLSTATUS_AQUA_RING and not heal_blocked(pok):
        _residual_heal(pok)

    # 2. Speed Boost
    if pok[_POK_AB_WHEN] & _ABILITYACTIVATION_ON_RESIDUAL:
        on_residual(pok, enter_field)

    # 2b. Leftovers and Black Sludge
    if _gradual_item(pok, enter_field_flag_idx, battle_array, enter_field):
        return

    # 3. Leech Seed
    if (
        pok[_POK_VOL_STATUS] & _VOLSTATUS_LEECH_SEED
        and not is_magic_guard
        and foe[_POK_CURRENT_HP] > 0
    ):
        dmg = max(1, pok[_POK_MAX_HP] // 8)
        dealt = min(dmg, pok[_POK_CURRENT_HP])
        fainted = _apply_residual_damage(pok, dmg, enter_field_flag_idx, battle_array, enter_field)
        _leech_seed_heal(foe, pok, dealt, enter_field_flag_idx, battle_array)
        if fainted:
            return

    # 4. Psn/Tox
    status = pok[_POK_STATUS]
    if status == _STATUS_POISON or status == _STATUS_TOXIC:
        # pokeplatinum: 1/16 at least 1, times the counter
        if status == _STATUS_TOXIC:
            badly_psn = pok[_POK_BADLY_POISON]
            if badly_psn < 1:
                badly_psn = 1
            dmg = max(1, pok[_POK_MAX_HP] // 16) * badly_psn
            pok[_POK_BADLY_POISON] = badly_psn + 1
        else:
            dmg = max(1, pok[_POK_MAX_HP] // 8)
        # Poison Heal heals 1/8 instead, the toxic counter above still goes up (pokeplatinum
        # subscript_poison_damage)
        if pok[_POK_AB_ID] == _ABILITYNAMES_POISON_HEAL:
            max_hp = pok[_POK_MAX_HP]
            if pok[_POK_CURRENT_HP] < max_hp:
                pok[_POK_CURRENT_HP] = min(max_hp, pok[_POK_CURRENT_HP] + max(1, max_hp // 8))
                reveal_ability(pok)
        elif not is_magic_guard:
            if _apply_residual_damage(pok, dmg, enter_field_flag_idx, battle_array, enter_field):
                return

    # 5. Burn, Heatproof halves it (pokeplatinum subscript_burn_damage)
    if pok[_POK_STATUS] == _STATUS_BURN:
        if not is_magic_guard:
            dmg = max(1, pok[_POK_MAX_HP] // 8)
            if pok[_POK_AB_ID] == _ABILITYNAMES_HEATPROOF:
                dmg = max(1, dmg // 2)
            if _apply_residual_damage(pok, dmg, enter_field_flag_idx, battle_array, enter_field):
                return

    # 5b. Nightmare, 1/4 at least 1 while asleep. One left on an awake Pokemon is gone, as [SD]
    # ends it when the sleep ends ([pp] MON_COND_CHECK_STATE_NIGHTMARE, [SD] cureStatus)
    if pok[_POK_VOL_STATUS] & _VOLSTATUS_NIGHTMARE:
        if pok[_POK_STATUS] != _STATUS_SLEEP:
            pok[_POK_VOL_STATUS] &= ~_VOLSTATUS_NIGHTMARE
        elif not is_magic_guard:
            dmg = max(1, pok[_POK_MAX_HP] // 4)
            if _apply_residual_damage(pok, dmg, enter_field_flag_idx, battle_array, enter_field):
                return

    # 6. Curse, at least 1 (pokeplatinum subscript_curse_damage DivideVarByValue)
    if pok[_POK_VOL_STATUS] & _VOLSTATUS_CURSE:
        if not is_magic_guard:
            dmg = max(1, pok[_POK_MAX_HP] // 4)
            if _apply_residual_damage(pok, dmg, enter_field_flag_idx, battle_array, enter_field):
                return

    # 7. Bind, freed once the binder has fainted
    if pok[_POK_VOL_STATUS] & _VOLSTATUS_PARTIALLY_TRAPPED:
        if foe[_POK_CURRENT_HP] <= 0:
            pok[_POK_VOL_STATUS] &= ~_VOLSTATUS_PARTIALLY_TRAPPED
        else:
            pok[_POK_TRAP_TURNS] -= 1
            if pok[_POK_TRAP_TURNS] <= 0:
                pok[_POK_VOL_STATUS] &= ~_VOLSTATUS_PARTIALLY_TRAPPED
            elif not is_magic_guard:
                dmg = max(1, pok[_POK_MAX_HP] // 16)
                if _apply_residual_damage(pok, dmg, enter_field_flag_idx, battle_array, enter_field):
                    return

    # 7b. Bad Dreams: a sleeper loses 1/8 to a living foe's Bad Dreams (pokeplatinum
    # MON_COND_CHECK_STATE_BAD_DREAMS)
    if (
        pok[_POK_STATUS] == _STATUS_SLEEP
        and foe[_POK_AB_ID] == _ABILITYNAMES_BAD_DREAMS
        and foe[_POK_CURRENT_HP] > 0
        and not is_magic_guard
    ):
        reveal_ability(foe)
        dmg = max(1, pok[_POK_MAX_HP] // 8)
        if _apply_residual_damage(pok, dmg, enter_field_flag_idx, battle_array, enter_field):
            return

    # 8. Uproar, wakes everyone up then counts down
    if pok[_POK_VOL_STATUS] & _VOLSTATUS_UPROAR:
        _uproar_wake(pok)
        _uproar_wake(foe)
        pok[_POK_UPROAR_TURNS] -= 1
        if pok[_POK_UPROAR_TURNS] <= 0:
            pok[_POK_VOL_STATUS] &= ~_VOLSTATUS_UPROAR
            pok[_POK_LOCKED_MOVE] = -1

    # 8b. Thrash, the last turn confuses the user. Own Tempo or a confusion stop it, Safeguard
    # doesn't (pokeplatinum MON_COND_CHECK_STATE_THRASH, subscript_thrash_end)
    if pok[_POK_RAMPAGE_TURNS] > 0:
        pok[_POK_RAMPAGE_TURNS] -= 1
        if pok[_POK_RAMPAGE_TURNS] == 0:
            pok[_POK_LOCKED_MOVE] = -1
            _flavor_confuse(pok)

    # 9. Disable
    if pok[_POK_VOL_STATUS] & _VOLSTATUS_DISABLE:
        _count_down_slot_lock(pok, _POK_DISABLE_TURNS, _VOLSTATUS_DISABLE)

    # 10. Encore, also ends when the encored move is out of PP
    if pok[_POK_VOL_STATUS] & _VOLSTATUS_ENCORE:
        slot = pok[_POK_ENCORE_TURNS] & SLOT_MASK
        if pok[OFFSET_MOVE + slot * MOVE_STRIDE + _MOVE_PP] == 0:
            pok[_POK_ENCORE_TURNS] = slot
        _count_down_slot_lock(pok, _POK_ENCORE_TURNS, _VOLSTATUS_ENCORE)

    # 10a. Lock-On / Mind Reader
    lock_on_count(pok)

    # 11. Taunt
    if pok[_POK_VOL_STATUS] & _VOLSTATUS_TAUNT:
        pok[_POK_TAUNT_TURNS] -= 1
        if pok[_POK_TAUNT_TURNS] <= 0:
            pok[_POK_VOL_STATUS] &= ~_VOLSTATUS_TAUNT

    # 11a. Magnet Rise
    magnet_rise_count(pok)

    # 11b. Heal Block
    heal_block_count(pok)

    # 11c. Embargo
    embargo_count(pok)

    # 12. Yawn
    if pok[_POK_VOL_STATUS] & _VOLSTATUS_YAWN:
        _yawn(pok, foe, effective_weather(battle_array))

    # 13. Status items, for Yawn's sleep (pokeplatinum MON_COND_CHECK_STATE_ITEM_CONDITION)
    status_item(pok)

    # 14. Flame Orb, Toxic Orb and Sticky Barb (pokeplatinum TriggerDetrimentalHeldItem)
    effect = pok[_ITEM_HOLD_EFFECT]
    if effect == _HOLDEFFECT_BRN_USER or effect == _HOLDEFFECT_PSN_USER:
        side = side_base(enter_field_flag_idx == _FIELD_MY_ENTER_FIELD)
        _flame_orb(pok, battle_array[side], effective_weather(battle_array))
    elif effect == _HOLDEFFECT_DMG_USER_CONTACT_XFR and not is_magic_guard:
        dmg = max(1, pok[_POK_MAX_HP] // pok[_ITEM_EFFECT_PARAM])
        if _apply_residual_damage(pok, dmg, enter_field_flag_idx, battle_array, enter_field):
            return

    if enter_field:
        battle_array[enter_field_flag_idx] = 0


@njit
def _count_down_field(battle_array):
    """
    pokeplatinum CheckFieldConditions, before any Pokemon's residual: Reflect, Light Screen, Mist,
    Safeguard, Tailwind and Lucky Chant of both sides, then the weather, then Gravity. Each one counts the
    turn it was set in, and a weather that ends does nothing this turn. A weather with no turns
    left set is permanent. Returns the weather for the rest of the turn
    """
    if (battle_array[_FIELD_MY_SIDE_COND] | battle_array[_FIELD_OPP_SIDE_COND]) & TIMED_SIDE_MASK:
        for bit, turns in TIMED_SIDE_CONDITIONS:
            for side in SIDES:
                if battle_array[side] & bit:
                    battle_array[side + turns] -= 1
                    if battle_array[side + turns] <= 0:
                        battle_array[side] &= ~bit
                        battle_array[side + turns] = 0
    if battle_array[_FIELD_WEATHER_DURATION] > 0:
        battle_array[_FIELD_WEATHER_DURATION] -= 1
        if battle_array[_FIELD_WEATHER_DURATION] == 0:
            battle_array[_FIELD_WEATHER] = 0
    if battle_array[_FIELD_GRAVITY_TURNS] > 0:
        battle_array[_FIELD_GRAVITY_TURNS] -= 1
    return battle_array[_FIELD_WEATHER]


@njit
def _replace_fainted_opp(battle_array, current_pokemon, current_opp):
    """
    The AI sends in a replacement for its fainted active, and keeps doing it while the one it sent
    faints to the hazards on entry. Returns the slot sent last, -1 if it had nobody left
    """
    opp_pty = battle_array[(6 * POK_LEN):(12 * POK_LEN)]
    i = -1
    for _ in range(6):
        if count_party(opp_pty) == 0:
            break
        i = sub_after_death(
            opp_pty, current_pokemon, current_opp, battle_array[_FIELD_MY_SIDE_COND],
            effective_weather(battle_array), gravity=battle_array[_FIELD_GRAVITY_TURNS] > 0
        )
        battle_array[_FIELD_OPP_POK] = i
        battle_array[_FIELD_MY_LAST_MOVE] = 0
        battle_array[_FIELD_AI_TOOK_DMG_LAST_TURN] = 0
        new_opp = opp_pty[(i * POK_LEN):((i+1) * POK_LEN)]
        carry_recycle(current_opp, new_opp)
        current_opp = new_opp
        switch_in(current_opp, current_pokemon, battle_array, False)
        if current_opp[_POK_CURRENT_HP] > 0:
            break
    return i


@njit
def end_of_turn(battle_array):
    """Does end of turn calculations like switch if dead, burn, poison, leech seed, ...,\n
    items like leftovers\n
    Weather damage like hail, sandstorm"""
    current_pokemon = battle_array[
        (battle_array[_FIELD_MY_POK] * POK_LEN):
        ((battle_array[_FIELD_MY_POK]+1) * POK_LEN)
    ]
    current_opp = battle_array[
        ((battle_array[_FIELD_OPP_POK]+6) * POK_LEN):
        ((battle_array[_FIELD_OPP_POK]+7) * POK_LEN)
    ]
    weather = battle_array[_FIELD_WEATHER]

    _count_down_field(battle_array)
    # Wish right after the side timers (pokeplatinum FIELD_COND_CHECK_STATE_WISH), the two heals
    # don't depend on each other or on the weather
    _wish_heal(battle_array, _FIELD_MY_SIDE_COND, current_pokemon)
    _wish_heal(battle_array, _FIELD_OPP_SIDE_COND, current_opp)
    forecast_actives(battle_array)
    weather = effective_weather(battle_array)

    # Gen IV re-sorts by speed before the end of the turn, then weather hits everyone before the
    # per-Pokemon residuals
    my_s, opp_s = field_speeds(battle_array, current_pokemon, current_opp, weather)
    if goes_first(my_s, opp_s, trick_room_up(battle_array)):
        first, second = current_pokemon, current_opp
        first_flag, second_flag = _FIELD_MY_ENTER_FIELD, _FIELD_OPP_ENTER_FIELD
    else:
        first, second = current_opp, current_pokemon
        first_flag, second_flag = _FIELD_OPP_ENTER_FIELD, _FIELD_MY_ENTER_FIELD
    first_side = _FIELD_MY_SIDE_COND if first_flag == _FIELD_MY_ENTER_FIELD else _FIELD_OPP_SIDE_COND
    second_side = _FIELD_OPP_SIDE_COND if first_side == _FIELD_MY_SIDE_COND else _FIELD_MY_SIDE_COND
    _residual_weather(first, weather, first_flag, battle_array)
    _residual_weather(second, weather, second_flag, battle_array)
    _apply_residual(first, second, first_flag, battle_array)
    _apply_residual(second, first, second_flag, battle_array)
    # pokeplatinum CheckSideConditions, after every Pokemon's residuals: Future Sight in speed order
    gravity = battle_array[_FIELD_GRAVITY_TURNS] > 0
    _future_attack_hit(battle_array, first_side, first, second, weather, gravity)
    _future_attack_hit(battle_array, second_side, second, first, weather, gravity)
    perish_count(first)
    perish_count(second)
    # Then Trick Room (pokeplatinum SIDE_COND_CHECK_STATE_TRICK_ROOM)
    if battle_array[_FIELD_TRICKROOM] > 0:
        battle_array[_FIELD_TRICKROOM] -= 1
    # A sleeper's rampage ends without confusion (pokeplatinum SetupNextTurn, nothing in between
    # puts a Pokemon to sleep)
    _sleep_ends_rampage(first)
    _sleep_ends_rampage(second)

    # If Opponent is dead
    if current_opp[_POK_CURRENT_HP] == 0 and current_pokemon[_POK_CURRENT_HP] != 0:
        return _replace_fainted_opp(battle_array, current_pokemon, current_opp)
    return -1


@njit
def _selected_move_id(pok, move_idx):
    """Id of the move picked this turn, 0 for a switch or an item (Battler_SelectedMove)"""
    if move_idx == 10:
        return _MOVENAME_STRUGGLE
    if move_idx < 0:
        return 0
    return pok[OFFSET_MOVE + move_idx * MOVE_STRIDE + _MOVE_ID]


@njit
def _rage_glitch(pok, move_id):
    """
    Gen IV Rage glitch (pokeplatinum PRE_MOVE_ACTION_STATE_CHECK_RAGE_FLAG): a raging Pokemon
    that picks anything but Rage keeps Rage and loses its other volatiles instead
    """
    if pok[_POK_VOL_STATUS] & _VOLSTATUS_RAGE and move_id != _MOVENAME_RAGE:
        pok[_POK_VOL_STATUS] &= ~RAGE_GLITCH_CLEARS
        # Substitute is a statusVolatile bit in pokeplatinum, so it goes too
        pok[_POK_VOL_STATUS2] &= ~_VOLSTATUS2_SUBSTITUTE
        pok[_POK_SUB_HP] = 0


@njit
def turn_sim(opp_move, current_action, battle_array):
    """One turn"""
    battle_array[_FIELD_OPP_MOVE_RAN] = 0
    if current_action[0] == _ACTIONTYPE_MOVE:
        switch_idx = -1
        current_move = current_action[1]
    else:
        current_move = -1
        switch_idx = current_action[1]
    my_pok = battle_array[
        (battle_array[_FIELD_MY_POK] * POK_LEN):((battle_array[_FIELD_MY_POK]+1) * POK_LEN)
    ]
    opp_pok = battle_array[
        ((battle_array[_FIELD_OPP_POK]+6) * POK_LEN):((battle_array[_FIELD_OPP_POK]+7) * POK_LEN)
    ]
    _rage_glitch(my_pok, _selected_move_id(my_pok, current_move))
    _rage_glitch(opp_pok, _selected_move_id(opp_pok, opp_move))
    current_move, opp_move = start_of_turn(opp_move, switch_idx, battle_array, current_move)
    action(current_move, opp_move, battle_array)
    if battle_array[_FIELD_PHASE] == _BATTLEPHASE_BATON_PASS:
        return _BATTLEPHASE_BATON_PASS, battle_array[_FIELD_OPP_POK]
    return _finish_turn(battle_array)


@njit
def _clear_damage_record(pok):
    """Counter, Mirror Coat and Metal Burst only see the damage of this turn (pokeplatinum
    turnFlags), a charging Bide keeps adding up across turns"""
    if not pok[_POK_VOL_STATUS] & _VOLSTATUS_BIDE:
        pok[_POK_DMG_TAKEN] = 0


@njit
def _finish_turn(battle_array):
    """End of turn and the turn counters, returns (phase, opp_idx) like turn_sim"""
    opp_idx = end_of_turn(battle_array)
    current_pokemon = battle_array[
        (battle_array[_FIELD_MY_POK] * POK_LEN):
        ((battle_array[_FIELD_MY_POK]+1) * POK_LEN)
    ]
    current_opp = battle_array[
        ((battle_array[_FIELD_OPP_POK]+6) * POK_LEN):
        ((battle_array[_FIELD_OPP_POK]+7) * POK_LEN)
    ]

    current_pokemon[_POK_VOL_STATUS] &= ~TURN_VOLATILES
    current_opp[_POK_VOL_STATUS] &= ~TURN_VOLATILES
    current_pokemon[_POK_VOL_STATUS2] &= ~TURN_VOLATILES2
    current_opp[_POK_VOL_STATUS2] &= ~TURN_VOLATILES2
    _clear_damage_record(current_pokemon)
    _clear_damage_record(current_opp)

    if opp_idx == -1:
        opp_idx = battle_array[_FIELD_OPP_POK]
    if current_pokemon[_POK_CURRENT_HP] <= 0:
        return _BATTLEPHASE_DEATH_END_OF_TURN, opp_idx

    battle_array[_FIELD_TURN] += 1
    current_opp[_POK_TURNS] += 1
    current_pokemon[_POK_TURNS] += 1
    current_opp[_POK_TURNS_ACTIVE] += 1
    current_pokemon[_POK_TURNS_ACTIVE] += 1
    return _BATTLEPHASE_TURN_START, opp_idx


@njit
def switch_in_action(battle_array, switch_idx: int):
    """Grab the switch idx from MCTS and progress it"""
    opp_pty = battle_array[(6 * POK_LEN):(12 * POK_LEN)]
    my_pty = battle_array[0:(6 * POK_LEN)]
    current_pokemon = battle_array[
        (battle_array[_FIELD_MY_POK] * POK_LEN):
        ((battle_array[_FIELD_MY_POK]+1) * POK_LEN)
    ]
    current_opp = battle_array[
        ((battle_array[_FIELD_OPP_POK]+6) * POK_LEN):
        ((battle_array[_FIELD_OPP_POK]+7) * POK_LEN)
    ]
    if current_opp[_POK_CURRENT_HP] <= 0:
        i = sub_after_death(
            opp_pty, current_pokemon, current_opp, battle_array[_FIELD_MY_SIDE_COND],
            effective_weather(battle_array), gravity=battle_array[_FIELD_GRAVITY_TURNS] > 0
        )
        opp_switch = opp_pty[(i * POK_LEN):((i+1) * POK_LEN)]
        my_switch = my_pty[
            (switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)
        ]
        carry_recycle(current_pokemon, my_switch)
        carry_recycle(current_opp, opp_switch)

        # I actually don't know if when both are switching in the order matters, but its better be safe
        # than sorry
        my_s, opp_s = field_speeds(
            battle_array, my_switch, opp_switch, effective_weather(battle_array)
        )
        if goes_first(my_s, opp_s, trick_room_up(battle_array)):
            # My Pokemon
            battle_array[_FIELD_MY_POK] = switch_idx
            battle_array[_FIELD_AI_KNOWS] = 0
            current_pokemon = my_pty[
                (switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)
            ]

            # Opponent Pokemon
            current_opp = opp_switch
            battle_array[_FIELD_OPP_POK] = i
            battle_array[_FIELD_MY_LAST_MOVE] = 0
            battle_array[_FIELD_AI_TOOK_DMG_LAST_TURN] = 0

            # Switch in effects after they are already switched
            switch_in(current_pokemon, current_opp, battle_array, True, True)
            switch_in(current_opp, current_pokemon, battle_array, False)
        else:
            # Opponent Pokemon
            battle_array[_FIELD_OPP_POK] = i
            battle_array[_FIELD_AI_TOOK_DMG_LAST_TURN] = 0
            current_opp = opp_switch

            # My Pokemon
            battle_array[_FIELD_MY_POK] = switch_idx
            battle_array[_FIELD_AI_KNOWS] = 0
            battle_array[_FIELD_MY_LAST_MOVE] = 0
            current_pokemon = my_pty[
                (switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)
            ]

            # Switch in effects after they are already switched
            switch_in(current_opp, current_pokemon, battle_array, False, True)
            switch_in(current_pokemon, current_opp, battle_array, True)

        # Mine fainted to the hazards: I pick again, having seen who the AI sent
        if current_pokemon[_POK_CURRENT_HP] <= 0:
            battle_array[_FIELD_PHASE] = _BATTLEPHASE_DEATH_END_OF_TURN
            return
        if current_opp[_POK_CURRENT_HP] <= 0:
            _replace_fainted_opp(battle_array, current_pokemon, current_opp)
            current_opp = opp_pty[
                (battle_array[_FIELD_OPP_POK] * POK_LEN):((battle_array[_FIELD_OPP_POK]+1) * POK_LEN)
            ]

        battle_array[_FIELD_TURN] += 1
        current_opp[_POK_TURNS] += 1
        current_pokemon[_POK_TURNS] += 1
        current_opp[_POK_TURNS_ACTIVE] += 1
        current_pokemon[_POK_TURNS_ACTIVE] += 1
        battle_array[_FIELD_PHASE] = _BATTLEPHASE_TURN_START
        return
    battle_array[_FIELD_MY_POK] = switch_idx
    new_pokemon = my_pty[
        (switch_idx * POK_LEN):((switch_idx+1) * POK_LEN)
    ]
    carry_recycle(current_pokemon, new_pokemon)
    current_pokemon = new_pokemon
    switch_in(current_pokemon, current_opp, battle_array, True)
    # Fainted to the hazards, I pick again
    if current_pokemon[_POK_CURRENT_HP] <= 0:
        battle_array[_FIELD_AI_KNOWS] = 0
        battle_array[_FIELD_MY_LAST_MOVE] = 0
        battle_array[_FIELD_PHASE] = _BATTLEPHASE_DEATH_END_OF_TURN
        return
    battle_array[_FIELD_TURN] += 1
    current_opp[_POK_TURNS] += 1
    current_pokemon[_POK_TURNS] += 1
    current_opp[_POK_TURNS_ACTIVE] += 1
    current_pokemon[_POK_TURNS_ACTIVE] += 1
    battle_array[_FIELD_AI_KNOWS] = 0
    battle_array[_FIELD_MY_LAST_MOVE] = 0
    battle_array[_FIELD_PHASE] = _BATTLEPHASE_TURN_START


@njit
def baton_pass_action(battle_array, switch_idx: int):
    """
    My pick for Baton Pass: switch with the stages and volatiles, run the opponent's move if it
    was slower, then the rest of the turn. Returns the phase, also stored in Field.PHASE.
    Healing Wish's and U-turn's picks are plain switches, and one the hazards KO is picked again before the foe moves
    """
    battle_array[_FIELD_OPP_MOVE_RAN] = 0
    current_pokemon = battle_array[
        (battle_array[_FIELD_MY_POK] * POK_LEN):((battle_array[_FIELD_MY_POK]+1) * POK_LEN)
    ]
    current_opp = battle_array[
        ((battle_array[_FIELD_OPP_POK]+6) * POK_LEN):((battle_array[_FIELD_OPP_POK]+7) * POK_LEN)
    ]
    healing_wish = battle_array[_FIELD_MY_SIDE_COND] & _SIDECONDITION_HEALING_WISH != 0
    u_turn = current_pokemon[_POK_VOL_STATUS2] & _VOLSTATUS2_U_TURN != 0
    current_pokemon = _switch_my_side(
        battle_array, current_pokemon, current_opp, switch_idx, not healing_wish and not u_turn
    )
    if healing_wish and current_pokemon[_POK_CURRENT_HP] <= 0 and _bench_alive(battle_array, True) > 0:
        return _BATTLEPHASE_BATON_PASS
    pending = battle_array[_FIELD_PENDING_OPP_MOVE] - 1
    flinch = pending >= PENDING_FLINCH
    if flinch:
        pending -= PENDING_FLINCH
    battle_array[_FIELD_PENDING_OPP_MOVE] = 0
    battle_array[_FIELD_PHASE] = _BATTLEPHASE_TURN_START
    if pending >= 0:
        slot = _encore_slot(current_opp, pending)
        mv = (current_opp[OFFSET_MOVE + slot * MOVE_STRIDE : OFFSET_MOVE + (slot + 1) * MOVE_STRIDE]
              if slot != 10 else STRUGGLE.copy())
        _execute_move_slot(
            current_opp, current_pokemon, mv, False, -1, slot, flinch, 2, True, battle_array,
            effective_weather(battle_array)
        )
        update_choice_lock(current_opp, slot)
        clear_target_choice_lock(current_pokemon, current_opp)
        _clear_charge(current_opp, mv)
        if current_opp[_POK_VOL_STATUS2] & _VOLSTATUS2_U_TURN:
            _u_turn_switch(current_opp, current_pokemon, battle_array, False)
        _after_move_items(battle_array)
    phase, _opp_idx = _finish_turn(battle_array)
    battle_array[_FIELD_PHASE] = phase
    return phase
