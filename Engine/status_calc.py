"""Calculate Status effects moves"""
import random
from numba import njit
from Models.helper import TARGET_OPP_SIDE, TARGET_SELF_SIDE, STEEL_POISON
from Models.constants import (
    _POK_STATUS, _STATUS_BURN, _STATUS_POISON, _STATUS_TOXIC, _STATUS_SLEEP, _STATUS_FREEZE,
    _MOVE_BOOST_ATK, _MOVE_BOOST_DEF, _MOVE_BOOST_SPATK, _MOVE_BOOST_SPDEF, _MOVE_BOOST_SPEED,
    _MOVE_BOOST_EV, _MOVE_BOOST_ACC, _MOVE_STATUS, _MOVE_TARGET,  _WEATHER_SUN, _TYPES_GHOST,
    _SEC_STATUS, _SEC_CHANCE, _SEC_BOOST_ATK, _SEC_BOOST_DEF, _SEC_BOOST_SPATK, _VOLSTATUS_CURSE,
    _SEC_BOOST_EV, _SEC_BOOST_SPDEF, _SEC_BOOST_SPEED, _POK_ATTACK_STAT_STAGE, _POK_DEFENSE_STAT_STAGE,
    _POK_SPECIAL_ATTACK_STAT_STAGE, _POK_SPECIAL_DEFENSE_STAT_STAGE, _POK_SPEED_STAT_STAGE,
    _POK_EVASION_STAT_STAGE, _POK_BADLY_POISON, _POK_SLEEP_COUNTER, _POK_ACCURACY_STAT_STAGE,
    _POK_AB_ID, _POK_MAX_HP, _POK_TYPE1, _POK_TYPE2, _STATUS_PARALYSIS, _MOVENAME_CURSE,
    _TYPES_FIRE, _TYPES_ELECTRIC, _POK_CURRENT_HP, _SEC_BOOST_ACC, _MOVE_ID,
    _ABILITYNAMES_KEEN_EYE, _ABILITYNAMES_MAGIC_GUARD, _ABILITYNAMES_SYNCHRONIZE,
    _ABILITYNAMES_IMMUNITY, _ABILITYNAMES_LIMBER, _ABILITYNAMES_WATER_VEIL, _MOVE_VOL_STATUS,
    _VOLSTATUS_CONFUSION, _POK_VOL_STATUS, _POK_CONFUSION_COUNTER, _SEC_VOL_STATUS
)
from Models.move import CURSE_BOOST

# --- Global Tuples ---
B_P = (_STATUS_BURN, _STATUS_POISON, _STATUS_TOXIC)
B_P_P = (_STATUS_BURN, _STATUS_POISON, _STATUS_TOXIC, _STATUS_PARALYSIS)
TURNS_2_5 = (2, 3, 4, 5)

STAT_MAPPING = (
    (_MOVE_BOOST_ATK, _POK_ATTACK_STAT_STAGE),
    (_MOVE_BOOST_DEF, _POK_DEFENSE_STAT_STAGE),
    (_MOVE_BOOST_SPATK, _POK_SPECIAL_ATTACK_STAT_STAGE),
    (_MOVE_BOOST_SPDEF, _POK_SPECIAL_DEFENSE_STAT_STAGE),
    (_MOVE_BOOST_SPEED, _POK_SPEED_STAT_STAGE),
    (_MOVE_BOOST_EV, _POK_EVASION_STAT_STAGE)
)

SECONDARY_STAT_MAPPING = (
    (_SEC_BOOST_ATK, _POK_ATTACK_STAT_STAGE),
    (_SEC_BOOST_DEF, _POK_DEFENSE_STAT_STAGE),
    (_SEC_BOOST_SPATK, _POK_SPECIAL_ATTACK_STAT_STAGE),
    (_SEC_BOOST_SPDEF, _POK_SPECIAL_DEFENSE_STAT_STAGE),
    (_SEC_BOOST_SPEED, _POK_SPEED_STAT_STAGE),
    (_SEC_BOOST_EV, _POK_EVASION_STAT_STAGE)
)


@njit
def synchronize_reflect(recipient, applied_status, source):
    """Reflects Burn, Poison, Toxic, or Paralysis back to the attacker."""
    if recipient[_POK_AB_ID] != _ABILITYNAMES_SYNCHRONIZE:
        return
    if applied_status not in B_P_P:
        return
    if source[_POK_STATUS] != 0:
        return

    t1 = source[_POK_TYPE1]
    t2 = source[_POK_TYPE2]

    # Branchless type matching for immunities
    if applied_status == _STATUS_BURN:
        if t1 == _TYPES_FIRE or t2 == _TYPES_FIRE or source[_POK_AB_ID] == _ABILITYNAMES_WATER_VEIL:
            return
        source[_POK_STATUS] = applied_status
        return
    if applied_status == _STATUS_PARALYSIS:
        if t1 == _TYPES_ELECTRIC or t2 == _TYPES_ELECTRIC or source[_POK_AB_ID] == _ABILITYNAMES_LIMBER:
            return
        source[_POK_STATUS] = applied_status
        return
    # Poison or Toxic
    if t1 in STEEL_POISON or t2 in STEEL_POISON or source[_POK_AB_ID] == _ABILITYNAMES_IMMUNITY:
        return
    # Synchronize always inflicts standard Poison, even if triggered by Toxic
    source[_POK_STATUS] = _STATUS_POISON


@njit
def apply_status(move, pok, weather, source, sec=False):
    """Apply non-volatile status effects."""
    # Gen 4: Cannot apply a new status if one already exists
    if pok[_POK_STATUS] != 0:
        return

    m_status = move[_SEC_STATUS] if sec else move[_MOVE_STATUS]
    if m_status == 0:
        return

    if m_status == _STATUS_FREEZE and weather == _WEATHER_SUN:
        return

    pok[_POK_STATUS] = m_status

    if m_status == _STATUS_TOXIC:
        pok[_POK_BADLY_POISON] = 1
    elif m_status == _STATUS_SLEEP:
        pok[_POK_SLEEP_COUNTER] = TURNS_2_5[random.getrandbits(2)]

    if m_status in B_P_P:
        synchronize_reflect(pok, m_status, source)


@njit
def stat_changes(move, attacker, defender, sec=False):
    """Check and apply stat changes."""
    stat_map = SECONDARY_STAT_MAPPING if sec else STAT_MAPPING
    has_stat_boost = False

    # 1. Early exit check (Numba completely unrolls this tuple loop)
    for move_idx, _ in stat_map:
        if move[move_idx] != 0:
            has_stat_boost = True
            break

    acc_boost = move[_SEC_BOOST_ACC] if sec else move[_MOVE_BOOST_ACC]
    if acc_boost != 0:
        has_stat_boost = True

    if not has_stat_boost:
        return

    # 2. Assign target exactly once
    m_target = move[_MOVE_TARGET]
    target_pok = attacker if m_target in TARGET_SELF_SIDE else defender

    # 3. Apply stats safely to the evaluated target
    for move_idx, stat_idx in stat_map:
        boost = move[move_idx]
        if boost != 0:
            target_pok[stat_idx] = max(-6, min(6, target_pok[stat_idx] + boost))

    # Apply Accuracy (Requires Keen Eye exception for Opponent target)
    if acc_boost != 0:
        if m_target in TARGET_OPP_SIDE and acc_boost < 0 and defender[_POK_AB_ID] == _ABILITYNAMES_KEEN_EYE:
            pass  # Blocked
        else:
            target_pok[_POK_ACCURACY_STAT_STAGE] = (
                max(-6, min(6, target_pok[_POK_ACCURACY_STAT_STAGE] + acc_boost))
            )


@njit
def vol_status(move, pok, source, sec=False):
    """Check and apply volatile status."""
    v_status = move[_SEC_VOL_STATUS] if sec else move[_MOVE_VOL_STATUS]

    if v_status & _VOLSTATUS_CONFUSION:
        if not pok[_POK_VOL_STATUS] & _VOLSTATUS_CONFUSION:
            pok[_POK_VOL_STATUS] += _VOLSTATUS_CONFUSION
            pok[_POK_CONFUSION_COUNTER] = TURNS_2_5[random.getrandbits(2)]

    if v_status & _VOLSTATUS_CURSE:
        if not pok[_POK_VOL_STATUS] & _VOLSTATUS_CURSE:
            pok[_POK_VOL_STATUS] += _VOLSTATUS_CURSE
            source[_POK_CURRENT_HP] = max(0, source[_POK_CURRENT_HP]-(source[_POK_MAX_HP]//2))



@njit
def calculate_effects(attacker, defender, move, weather):
    """Calculate primary move effects."""
    # Curse different moves
    if move[_MOVE_ID] == _MOVENAME_CURSE:
        if attacker[_POK_TYPE1] != _TYPES_GHOST or attacker[_POK_TYPE2] != _TYPES_GHOST:
            move = CURSE_BOOST
    stat_changes(move, attacker, defender)

    if move[_MOVE_STATUS] != 0:
        if move[_MOVE_TARGET] in TARGET_OPP_SIDE:
            apply_status(move, defender, weather, attacker)
        else:
            raise ValueError("Shouldn't have self status change in this block")

    if move[_MOVE_VOL_STATUS] != 0:
        vol_status(move, defender, attacker)


@njit
def sec_effects(move, attacker, defender, weather):
    """Calculate secondary move effects (e.g., 10% Burn)."""
    m_target = move[_MOVE_TARGET]
    target_opp = m_target in TARGET_OPP_SIDE

    if target_opp and defender[_POK_CURRENT_HP] <= 0:
        return

    chance = move[_SEC_CHANCE]

    if chance == 100 or random.randint(1, 100) <= chance:
        stat_changes(move, attacker, defender, sec=True)

        if target_opp:
            if move[_SEC_STATUS] != 0:
                apply_status(move, defender, weather, attacker, sec=True)
            if move[_SEC_VOL_STATUS] != 0:
                vol_status(move, defender, attacker, sec=True)


@njit
def after_turn_status(pok):
    """Calculate end-of-turn status damage."""
    if pok[_POK_AB_ID] == _ABILITYNAMES_MAGIC_GUARD:
        return 0

    status = pok[_POK_STATUS]
    if status in B_P:
        max_hp = pok[_POK_MAX_HP]
        if pok[_POK_BADLY_POISON] >= 1:
            dmg = max_hp * pok[_POK_BADLY_POISON] // 16
            pok[_POK_BADLY_POISON] += 1
            return dmg
        return max_hp // 8

    return 0


@njit
def paralysis():
    """Returns True if the Pokémon is fully paralyzed (25% chance)."""
    return random.getrandbits(2) == 0


@njit
def freeze():
    """Returns True if the Pokémon thaws from ice (20% chance)."""
    return random.random() <= 0.2
