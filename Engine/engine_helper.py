"""Helpers that are only needed in the engine directory"""
import random
import numpy as np
from Utils.jit import njit
from Utils.helper import stage_to_multiplier, get_type_effectiveness
from Engine.status_calc import  freeze, paralysis, synchronize_reflect
from Engine.damage_calc import (
    calculate_damage_confusion, apply_stat_stage, MULTIPLIERS, matchup_types
)
from Models.idx_const import ITEM_LEN, POK_LEN, MOVE_STRIDE, OFFSET_MOVE
from Models.helper import TARGET_SELF_SIDE, STEEL_POISON, Target
from Models.constants import (
    _POK_SPEED, _POK_STATUS, _STATUS_PARALYSIS, _POK_SPEED_STAT_STAGE, _POK_AB_WHEN,
    _ABILITYACTIVATION_ON_MODIFY_SPEED, _WEATHER_SUN,_ABILITYNAMES_CHLOROPHYLL, _MOVENAME_FAKE_OUT,
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
    _SEC_CHANCE2, _MOVE_IGNORE_IMMUNITY,
    _FIELD_MY_POK, _FIELD_OPP_POK, _FIELD_WEATHER, _FIELD_TURN, _STATUS_TOXIC, _STATUS_POISON,
    _STATUS_SLEEP, _STATUS_FREEZE, _VOLSTATUS_CONFUSION, _POTIONS_FULL_HEAL,
    _POTIONS_FULL_RESTORE, _POTIONS_HYPER_POTION, _POTIONS_POTION, _POTIONS_SUPER_POTION,
    _POTIONS_X_DEFEND, _POTIONS_X_SPECIAL, _POTIONS_X_SPEED, _ABILITYNAMES_SWIFT_SWIM,
    _ABILITYNAMES_WATER_ABSORB, _MOVE_DAMAGE, _DAMAGESOURCES_COUNTER, _DAMAGESOURCES_MAGIC_COAT,
    _TYPES_WATER, _ABILITYACTIVATION_ON_CRITICAL, _MOVE_DRAIN, _POK_DMG_TAKEN,
    _POK_CHARGE_RECHARGE, _MOVE_CHARGE_RECHARGE, _POK_LOCKED_MOVE, _ITEMNAMES_ORAN_BERRY,
    _ITEM_ID, _ITEMNAMES_SITRUS_BERRY, _MOVENAME_BIDE, _VOLSTATUS_BIDE, _VOLSTATUS_FOCUS_ENERGY, _MOVE_CRIT_RATIO, _MOVE_WILL_CRIT, _ITEMTYPE_BERRY,
    _ITEM_ITEM_TYPE, _POK_CONFUSION_COUNTER, _ITEM_WHEN, _ITEMACTIVATION_ON_RECEIVE_DAMAGE,
    _ABILITYNAMES_SIMPLE, _POK_LEVEL, _POK_ATTACK, _POK_DEFENSE, _STATUS_BURN,
    _MOVEOUTCOME_SEMI_INVULNERABLE, _VOLSTATUS_SEMI_INVULNERABLE, _VOLSTATUS_HURT_THIS_TURN,
    _POK_CONSEC_COUNT, _MOVENAME_GUST, _ABILITYNAMES_GUTS, _ABILITYNAMES_HUGE_POWER, _MOVE_RECOIL,
    _ITEM_NATURAL_GIFT_POWER, _ITEM_NATURAL_GIFT_TYPE, _POK_CONSUMED_ITEM, _MOVE_POWER,
    _MOVEOUTCOME_PROTECTED, _VOLSTATUS_PROTECT, _VOLSTATUS_ENDURE, _VOLSTATUS_FORESIGHT,
    _VOLSTATUS_DESTINY_BOND, _VOLSTATUS_ATTRACT, _FLAGS_PROTECT, _POK_PROTECT_COUNT,
    _POK_YAWN_TURNS, _MOVENAME_PROTECT
)


SANDSTORM_IM = (_TYPES_ROCK, _TYPES_GROUND, _TYPES_STEEL)
DAMP_IGNORES = (_MOVENAME_EXPLOSION, _MOVENAME_SELFDESTRUCT)
WEATHER_NOT_END_OF_TURN = (0, _WEATHER_RAIN)
ITEM_50HP = (_ITEMNAMES_ORAN_BERRY, _ITEMNAMES_SITRUS_BERRY)
RECORD_DAMAGE = (_DAMAGESOURCES_COUNTER, _DAMAGESOURCES_MAGIC_COAT)
HITS_SEMI_INVULNERABLE = (_MOVENAME_GUST,)
SIDE_OR_FIELD_TARGETS = (Target.ALL, Target.FOE_SIDE, Target.ALLY_TEAM)
PROTECT_COUNT_MAX = 3  # Success chance 1, 1/2, 1/4, then 1/8 from here on


# ── Volatile bookkeeping ───────────────────────────────────────────────────────

@njit
def mark_hurt(pok):
    """The Pokemon lost HP this turn (read by Assurance)"""
    pok[_POK_VOL_STATUS] |= _VOLSTATUS_HURT_THIS_TURN


@njit
def unlock_move(pok):
    """
    Ends a lock (Rollout, Ice Ball), a charge (Bounce) and the Fury Cutter/Rollout counter when
    the move doesn't go through. Bide keeps its own pause rule
    """
    if pok[_POK_VOL_STATUS] & _VOLSTATUS_BIDE:
        return
    if pok[_POK_CHARGE_RECHARGE] > 0:
        pok[_POK_CHARGE_RECHARGE] = 0
    pok[_POK_LOCKED_MOVE] = -1
    pok[_POK_CONSEC_COUNT] = 0
    pok[_POK_VOL_STATUS] &= ~_VOLSTATUS_SEMI_INVULNERABLE


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
def endure_damage(defender, damage):
    """Endure leaves the defender at 1 HP from a hit that would KO it"""
    if defender[_POK_VOL_STATUS] & _VOLSTATUS_ENDURE and damage >= defender[_POK_CURRENT_HP]:
        return defender[_POK_CURRENT_HP] - 1
    return damage


# ── Item / berry helpers ───────────────────────────────────────────────────────

@njit
def clear_item(pok):
    """
    If the item was used reset it
    """
    pok[_ITEM_ID:(_ITEM_ID+ITEM_LEN)] = 0


@njit
def _apply_berry_effect(item_id, target):
    """Apply the berry's effect to target. target = the beneficiary, which is
    'pok' for a self-trigger, or 'attacker' for Bug Bite."""
    cur_hp = target[_POK_CURRENT_HP]
    max_hp = target[_POK_MAX_HP]
    if item_id == _ITEMNAMES_ORAN_BERRY:
        cur_hp = min(cur_hp + 10, max_hp)
    elif item_id == _ITEMNAMES_SITRUS_BERRY:
        # Needs to be with min because of bug bite
        cur_hp = min(cur_hp + max_hp // 4, max_hp)
    target[_POK_CURRENT_HP] = cur_hp


@njit
def eat_berry(pok):
    """Self-triggered berry eat at low HP (end of turn / on receiving damage)"""
    item_id = pok[_ITEM_ID]
    if item_id in ITEM_50HP and pok[_POK_CURRENT_HP] * 2 <= pok[_POK_MAX_HP]:
        _apply_berry_effect(item_id, pok)
        clear_item(pok)


@njit
def eat_berry_bug_bite(attacker, defender):
    """Bug Bite forces the target to eat its berry immediately; attacker gets the benefit"""
    item_id = defender[_ITEM_ID]
    _apply_berry_effect(item_id, attacker)
    clear_item(defender)


@njit
def switch_items(pok1, pok2):
    """Switch items"""
    item_slice = slice(_ITEM_ID, _ITEM_ID + ITEM_LEN)
    item_copy = np.copy(pok1[item_slice])
    pok1[item_slice] = pok2[item_slice]
    pok2[item_slice] = item_copy


@njit
def item_on_rdmg(pok):
    """
    Check what item it is and apply it
    """
    if pok[_ITEM_ITEM_TYPE] == _ITEMTYPE_BERRY:
        eat_berry(pok)


# ── Speed & turn order ──────────────────────────────────────────────────────────

@njit
def check_speed(p1, p2, weather):
    """Gives speed after modifications of stages, abilities, and paralysis (Showdown/Smogon-DP
    confirmed order: stat stage -> ability modifier -> item modifier (not yet implemented) ->
    paralysis -> tailwind (not yet implemented). Paralysis is applied last, to the already-
    truncated result of the earlier steps, not multiplied in alongside them.)"""
    p1_speed = p1[_POK_SPEED]
    p2_speed = p2[_POK_SPEED]
    # Apply Stat stages if necessary
    if p1[_POK_SPEED_STAT_STAGE] != 0:
        p1_speed = stage_to_multiplier(p1[_POK_SPEED_STAT_STAGE], p1_speed)
    if p2[_POK_SPEED_STAT_STAGE] != 0:
        p2_speed = stage_to_multiplier(p2[_POK_SPEED_STAT_STAGE], p2_speed)
    ab_w1 = p1[_POK_AB_WHEN]
    ab_w2 = p2[_POK_AB_WHEN]
    if ab_w1 & _ABILITYACTIVATION_ON_MODIFY_SPEED:
        ab = p1[_POK_AB_ID]
        if weather == _WEATHER_SUN and ab == _ABILITYNAMES_CHLOROPHYLL:
            p1_speed *= 2
        elif weather == _WEATHER_RAIN and ab == _ABILITYNAMES_SWIFT_SWIM:
            p1_speed *= 2
    if ab_w2 & _ABILITYACTIVATION_ON_MODIFY_SPEED:
        ab = p2[_POK_AB_ID]
        if weather == _WEATHER_SUN and ab == _ABILITYNAMES_CHLOROPHYLL:
            p2_speed *= 2
        elif weather == _WEATHER_RAIN and ab == _ABILITYNAMES_SWIFT_SWIM:
            p2_speed *= 2
    # TODO: item modifiers (Choice Scarf ×1.5, Iron Ball/Macho Brace/Power items ×0.5,
    # Quick Powder ×2) go here once items are wired into the speed calc — before paralysis.
    if p1[_POK_STATUS] == _STATUS_PARALYSIS:
        p1_speed //= 4
    if p2[_POK_STATUS] == _STATUS_PARALYSIS:
        p2_speed //= 4
    # TODO: Tailwind ×2 goes here, last.
    return p1_speed, p2_speed


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
    speed_t = False
    if p1_speed == p2_speed and random.getrandbits(1):
        speed_t = True
    if p1_speed > p2_speed or speed_t:
        return my_move, opp_move, 2, True
    return opp_move, my_move, 2, False


# ── Accuracy & crit ─────────────────────────────────────────────────────────────

@njit
def absorb_abi(defender):
    """
    Absorb abilities restore 1/4 of max hp on try hitting instead of the move
    """
    defender[_POK_CURRENT_HP] = min(
        defender[_POK_MAX_HP], (defender[_POK_CURRENT_HP] + defender[_POK_MAX_HP]//4)
    )


@njit
def ab_on_try_move(move, attacker, defender, accuracy:int, weather):
    """
    Check to see if the ability changes the probabilty of a move hitting
    """
    atk_ab = attacker[_POK_AB_ID]
    def_ab = defender[_POK_AB_ID]
    target = move[_MOVE_TARGET]
    if move[_MOVE_ID] in DAMP_IGNORES and (
        atk_ab == _ABILITYNAMES_DAMP  #pylint: disable=consider-using-in
        or def_ab == _ABILITYNAMES_DAMP
    ):
        return 0
    if (
        atk_ab == _ABILITYNAMES_HUSTLE
        and move[_MOVE_CATEGORY] == _MOVECATEGORY_PHYSICAL
        and not move[_MOVE_OH_KO]
    ):
        return (accuracy*3277)//4096
    if (
        def_ab == _ABILITYNAMES_SAND_VEIL
        and weather == _WEATHER_SANDSTORM
    ):
        return (accuracy*3277)//4096
    if (
        move[_FLAGS_SOUND]
        and (
            def_ab == _ABILITYNAMES_SOUNDPROOF
            or (
                atk_ab == _ABILITYNAMES_SOUNDPROOF
                and target in TARGET_SELF_SIDE
            )
        )
    ):
        return 0
    if def_ab == _ABILITYNAMES_WATER_ABSORB and move[_MOVE_TYPE] == _TYPES_WATER:
        absorb_abi(defender)
        return 0

    return accuracy


@njit
def calculate_hit_miss(move, attacker, defender, weather):
    '''Returns a boolean if the move passed the accuracy check'''
    # TODO: Semi invulnerable states, like Fly, dig etc.
    if defender[_POK_VOL_STATUS] & _VOLSTATUS_PROTECT and move[_FLAGS_PROTECT]:
        return _MOVEOUTCOME_PROTECTED
    if (
        defender[_POK_VOL_STATUS] & _VOLSTATUS_SEMI_INVULNERABLE
        and move[_MOVE_ID] not in HITS_SEMI_INVULNERABLE
        and move[_MOVE_ID] != _MOVENAME_BIDE
        and not move[_MOVE_OH_KO]
        and move[_MOVE_TARGET] not in TARGET_SELF_SIDE
        and move[_MOVE_TARGET] not in SIDE_OR_FIELD_TARGETS
    ):
        return _MOVEOUTCOME_SEMI_INVULNERABLE
    if move[_MOVE_ID] == _MOVENAME_STRUGGLE or move[_MOVE_ID] == _MOVENAME_BIDE:
        return _MOVEOUTCOME_HIT
    if move[_MOVE_ID] == _MOVENAME_FAKE_OUT and attacker[_POK_TURNS_ACTIVE] > 1:
        return _MOVEOUTCOME_MISS
    move_acc = move[_MOVE_ACCURACY]
    ab_a = attacker[_POK_AB_WHEN]
    ab_d = defender[_POK_AB_WHEN]
    if ab_a & _ABILITYACTIVATION_ON_TRY_MOVE or ab_d & _ABILITYACTIVATION_ON_TRY_MOVE:
        move_acc = ab_on_try_move(move, attacker, defender, move_acc, weather)

    if move[_MOVE_TARGET] not in TARGET_SELF_SIDE and not move[_MOVE_IGNORE_IMMUNITY]:
        def_t1, def_t2 = matchup_types(move[_MOVE_TYPE], defender)
        eff, _ = get_type_effectiveness(move[_MOVE_TYPE], def_t1, def_t2)
        if eff == 0:
            return _MOVEOUTCOME_INVULNERABLE

    if move_acc == -1:
        return _MOVEOUTCOME_HIT
    if move_acc == 0:
        return _MOVEOUTCOME_MISS

    ev_stage = defender[_POK_EVASION_STAT_STAGE]
    # Foresight ignores the target's evasion boosts
    if defender[_POK_VOL_STATUS] & _VOLSTATUS_FORESIGHT and ev_stage > 0:
        ev_stage = 0
    acc_stage = attacker[_POK_ACCURACY_STAT_STAGE] - ev_stage
    acc_stage = max(-6, min(6, acc_stage))
    if acc_stage == 0:
        accuracy = move_acc
    elif acc_stage < 0:
        accuracy = move_acc*(3)/(3-acc_stage)
    else:
        accuracy = move_acc*(acc_stage+3)/3

    if accuracy == 100 or random.randint(1,100) <= accuracy:
        return _MOVEOUTCOME_HIT
    return _MOVEOUTCOME_MISS


@njit
def calculate_crit(attacker, defender, move=None):
    """Returns a boolean if the move passed the crit check based on Gen IV mechanics."""
    if defender[_POK_AB_WHEN] & _ABILITYACTIVATION_ON_CRITICAL:
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


@njit
def switch_in(attacker, defender):
    """
    What happens when a pokemon switches in so, abilities, hazards
    """
    # The foe's infatuation was with the Pokemon that just left
    defender[_POK_VOL_STATUS] &= ~_VOLSTATUS_ATTRACT
    # TODO: Hazards damage(needs to put item on rdmg), take in consideration that the pokemon needs to
    # be alive to activiate the ability so before the ability do something like
    # if attacker[_POK_CURRENT_HP] > 0:
    if attacker[_POK_AB_WHEN] & _ABILITYACTIVATION_ON_SWITCH_IN:
        ability = attacker[_POK_AB_ID]
        if ability == _ABILITYNAMES_INTIMIDATE:
            defender[_POK_ATTACK_STAT_STAGE] = max(-6, defender[_POK_ATTACK_STAT_STAGE] - 1)


# ── In-battle status / contact effects ────────────────────────────────────────────

@njit
def flinch_checker(move, defender, second=False):
    """Returns true or false if move has a flinch percent and it should flinch"""
    if defender[_POK_AB_ID] == _ABILITYNAMES_INNER_FOCUS:
        return False
    chance = move[_SEC_CHANCE2] if second else move[_SEC_CHANCE]
    if random.randint(1,100) <= chance:
        return True
    return False


@njit
def thaw(move, defender):
    """Check if a move thaws"""
    if move[_MOVE_TYPE] == _TYPES_FIRE:
        defender[_POK_STATUS] = 0
        return True
    return False


@njit
def confusion(pok):
    """
    If the pokemon gets hit by confusion, it's kinda the same as ps_core,
    but since the damage calculation is different and it doesn't have a "move"
    Better have a own thing to apply everything
    """
    if pok[_POK_AB_ID] == _ABILITYNAMES_MAGIC_GUARD:
        return
    damage = calculate_damage_confusion(pok)
    pok[_POK_CURRENT_HP] = max(0, (pok[_POK_CURRENT_HP]-damage))
    if damage > 0:
        mark_hurt(pok)
    if pok[_ITEM_WHEN] & _ITEMACTIVATION_ON_RECEIVE_DAMAGE:
        item_on_rdmg(pok)


@njit
def contact_ability(attacker, defender):
    """
    Abilities that activate with contact
    """
    if defender[_POK_AB_ID] == _ABILITYNAMES_POISON_POINT:
        if (
            attacker[_POK_STATUS] == 0
            and attacker[_POK_TYPE1] not in STEEL_POISON
            and attacker[_POK_TYPE2] not in STEEL_POISON
            and random.random() < .30
        ):
            attacker[_POK_STATUS] = _STATUS_POISON
            synchronize_reflect(attacker, _STATUS_POISON, defender)


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
def early_returns(attacker, defender, idx: int, flinch: bool, move):
    """Early returns to see if an attack goes through or not"""
    """
    Priorities, highest go first:
    Recharge:  11
    Sleep:     10
    Freeze:    10
    Flinch:    8
    Confusion: 3
    Attract:   2
    Paralysis: 1
    Default:   0

    A blocked turn (sleep, flinch, confusion self-hit, infatuation, full paralysis) ends charge
    moves and locks via unlock_move, Bide pauses instead, freeze keeps the lock.
    Destiny Bond ends as soon as the user tries to move again, even if the turn is blocked.
    """
    attacker[_POK_VOL_STATUS] &= ~_VOLSTATUS_DESTINY_BOND
    atker_status = attacker[_POK_STATUS]
    # Check for Sleep and if the attacker wakes up, TODO: Sleep Talk and Snore
    if atker_status == _STATUS_SLEEP:
        unlock_move(attacker)
        if attacker[_POK_SLEEP_COUNTER] > 0:
            attacker[_POK_SLEEP_COUNTER] -= 1
            return True
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
    # Flinch
    if flinch and idx >= 2:
        unlock_move(attacker)
        if attacker[_POK_AB_ID] == _ABILITYNAMES_STEADFAST:
            attacker[_POK_SPEED_STAT_STAGE] = min(6, attacker[_POK_SPEED_STAT_STAGE] + 1)
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

    # Counter and Mirror Coat
    if (
        (move[_MOVE_DAMAGE] == _DAMAGESOURCES_COUNTER or move[_MOVE_DAMAGE] == _DAMAGESOURCES_MAGIC_COAT)
        and (idx == 1 or attacker[_POK_DMG_TAKEN] == 0)
    ):
        return True
    # In cases like after recoil damage, selfdestruct etc.
    if defender[_POK_CURRENT_HP] <= 0:
        # Move not targeting the defender, so don't matter its dead
        if move[_MOVE_TARGET] in TARGET_SELF_SIDE:
            return False
        # Charge move on its first turn
        if move[_MOVE_CHARGE_RECHARGE] > 0 and attacker[_POK_LOCKED_MOVE] == -1:
            return False
        #TODO: Some moves still go through, like future sight
        return True
    return False


# ── Battle start & end-of-turn residuals ───────────────────────────────────────

def start_of_battle(array):
    """Select the two first pokemon of each team and does ability effects on switch in
    for each following their speed"""
    # TODO: Switch in abilities like Intimidate, Drought etc.
    # Order of entry is in account for things like Drought against Drizzle
    current_pokemon = array[
            (array[_FIELD_MY_POK] * POK_LEN):((array[_FIELD_MY_POK]+1) * POK_LEN)
        ]
    current_opp = array[
            ((array[_FIELD_OPP_POK]+6) * POK_LEN):((array[_FIELD_OPP_POK]+7) * POK_LEN)
        ]
    weather = array[_FIELD_WEATHER]
    p1_speed, p2_speed = check_speed(current_pokemon, current_opp, weather)
    speed_tie = 0
    if p1_speed == p2_speed:
        speed_tie = random.getrandbits(1)
    if p1_speed > p2_speed or speed_tie:
        switch_in(current_pokemon, current_opp)
        switch_in(current_opp, current_pokemon)
    else:
        switch_in(current_opp, current_pokemon)
        switch_in(current_pokemon, current_opp)
    current_pokemon[_POK_TURNS] = 1
    current_opp[_POK_TURNS] = 1
    current_opp[_POK_TURNS_ACTIVE] = 1
    current_pokemon[_POK_TURNS_ACTIVE] = 1
    array[_FIELD_TURN] = 1


@njit
def heal_weather(self_, weather):
    """
    Heals after turns, from items, abilities and volatile conditions
    """
    heal = 0
    max_hp = self_[_POK_MAX_HP]
    if self_[_POK_AB_ID] == _ABILITYNAMES_RAIN_DISH and weather == _WEATHER_RAIN:
        heal += max_hp//16

    if heal:
        hp_missing = max_hp - self_[_POK_CURRENT_HP]
        heal = min(heal,hp_missing)
        self_[_POK_CURRENT_HP] += heal


@njit
def on_residual(pokemon, _switch_in):
    """
    On residual abilities at end of turn
    """
    abi = pokemon[_POK_AB_ID]
    if abi == _ABILITYNAMES_SPEED_BOOST and not _switch_in:
        pokemon[_POK_SPEED_STAT_STAGE] = min(6, pokemon[_POK_SPEED_STAT_STAGE] + 1)


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
            return max_hp//16
        return 0
    if weather == _WEATHER_HAIL:
        if type1 != _TYPES_ICE and type2!= _TYPES_ICE:
            return max_hp//16
        return 0
    if weather == _WEATHER_SUN:
        if abi == _ABILITYNAMES_SOLAR_POWER:
            return max_hp//8
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
def drain(pok, move, dmg):
    """
    Drain calculation and application
    """
    drain_pct = move[_MOVE_DRAIN]
    heal = (dmg*drain_pct)//4
    if heal == 0:
        heal = 1
    pok[_POK_CURRENT_HP] = min(pok[_POK_CURRENT_HP]+heal, pok[_POK_MAX_HP])


@njit
def struggle(attacker, defender, rec=True):
    """
    Struggle damage to the defender, plus recoil to the attacker. rec=False skips
    the recoil application — used by rollout heuristics that only want a damage
    estimate without mutating the attacker's HP.
    """
    atk_is_simple = attacker[_POK_AB_ID] == _ABILITYNAMES_SIMPLE
    def_is_simple = defender[_POK_AB_ID] == _ABILITYNAMES_SIMPLE
    atk_stage = attacker[_POK_ATTACK_STAT_STAGE]
    def_stage = defender[_POK_DEFENSE_STAT_STAGE]
    level = attacker[_POK_LEVEL]
    crit = calculate_crit(attacker, defender)

    if crit:
        def_stage = min(def_stage, 0)
        atk_stage = max(atk_stage, 0)

    raw_attack = attacker[_POK_ATTACK]
    atk_ab = attacker[_POK_AB_ID]
    is_guts = atk_ab == _ABILITYNAMES_GUTS
    if is_guts and attacker[_POK_STATUS] != 0:
        raw_attack = (raw_attack * 3) // 2
    elif atk_ab == _ABILITYNAMES_HUGE_POWER:
        raw_attack *= 2
    elif atk_ab == _ABILITYNAMES_HUSTLE:
        raw_attack = (raw_attack * 3) // 2

    attack = apply_stat_stage(raw_attack, atk_stage, atk_is_simple)
    defense = apply_stat_stage(defender[_POK_DEFENSE], def_stage, def_is_simple)

    # Base damage formula for Struggle with power 50
    damage = (((2 * level / 5) + 2) * 50 * (attack / defense)) // 50

    # Burn
    if attacker[_POK_STATUS] == _STATUS_BURN and not is_guts:
        damage //= 2

    # TODO: Screen

    # Adding 2 after the above
    damage += 2

    if crit:
        damage *= 2

    damage = (damage * MULTIPLIERS[random.getrandbits(4)]) // 100

    if rec:
        apply_recoil(attacker, struggle_recoil(attacker))

    return damage


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
