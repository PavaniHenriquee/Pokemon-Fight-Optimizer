"""Calculate Status effects moves"""
import random
from numba import njit
from Models.helper import TARGET_OPP_SIDE, TARGET_SELF_SIDE, STEEL_POISON
from Models.constants import (
    _POK_STATUS, _STATUS_BURN, _STATUS_POISON, _STATUS_TOXIC, _STATUS_SLEEP, _STATUS_FREEZE,
    _MOVE_BOOST_ATK, _MOVE_BOOST_DEF, _MOVE_BOOST_SPATK, _MOVE_BOOST_SPDEF, _MOVE_BOOST_SPEED,
    _MOVE_BOOST_EV, _MOVE_BOOST_ACC, _MOVE_STATUS, _MOVE_TARGET,  _WEATHER_SUN,
    _SEC_STATUS, _SEC_CHANCE, _SEC_BOOST_ATK, _SEC_BOOST_DEF, _SEC_BOOST_SPATK,
    _SEC_BOOST_EV, _SEC_BOOST_SPDEF, _SEC_BOOST_SPEED, _POK_ATTACK_STAT_STAGE, _POK_DEFENSE_STAT_STAGE,
    _POK_SPECIAL_ATTACK_STAT_STAGE, _POK_SPECIAL_DEFENSE_STAT_STAGE, _POK_SPEED_STAT_STAGE,
    _POK_EVASION_STAT_STAGE, _POK_BADLY_POISON, _POK_SLEEP_COUNTER, _POK_ACCURACY_STAT_STAGE,
    _POK_AB_ID, _POK_MAX_HP, _POK_TYPE1, _POK_TYPE2, _STATUS_PARALYSIS,
    _TYPES_FIRE, _TYPES_ELECTRIC, _POK_CURRENT_HP, _SEC_BOOST_ACC,
    _ABILITYNAMES_KEEN_EYE, _ABILITYNAMES_MAGIC_GUARD, _ABILITYNAMES_SYNCHRONIZE,
    _ABILITYNAMES_IMMUNITY, _ABILITYNAMES_LIMBER, _ABILITYNAMES_WATER_VEIL, _MOVE_VOL_STATUS,
    _VOLSTATUS_CONFUSION, _POK_VOL_STATUS, _POK_CONFUSION_COUNTER
)


B_P = (_STATUS_BURN, _STATUS_POISON, _STATUS_TOXIC)
B_P_P = (_STATUS_BURN, _STATUS_POISON, _STATUS_TOXIC, _STATUS_PARALYSIS)
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
TURNS_2_5 = (2, 3, 4, 5)


@njit
def synchronize_reflect(recipient, applied_status, source):
    """
    Generation IV Synchronize: when burned, paralyzed, poisoned, or badly poisoned by
    another Pokemon's move effect, the inflicting Pokemon gains the same status if able.
    Sleep and freeze are not reflected (Gen V+ extended Synchronize to sleep).
    """
    if recipient[_POK_AB_ID] != _ABILITYNAMES_SYNCHRONIZE:
        return
    if applied_status not in B_P_P:
        return
    if source[_POK_STATUS] != 0:
        return
    if applied_status == _STATUS_BURN:
        if (
            source[_POK_TYPE1] == _TYPES_FIRE
            or (source[_POK_TYPE2] != 0 and source[_POK_TYPE2] == _TYPES_FIRE)
        ):
            return
        if source[_POK_AB_ID] == _ABILITYNAMES_WATER_VEIL:
            return
    elif applied_status == _STATUS_PARALYSIS:
        if (
            source[_POK_TYPE1] == _TYPES_ELECTRIC
            or (source[_POK_TYPE2] != 0 and source[_POK_TYPE2] == _TYPES_ELECTRIC)
        ):
            return
        if source[_POK_AB_ID] == _ABILITYNAMES_LIMBER:
            return
    else:
        # poison or toxic
        t1 = source[_POK_TYPE1]
        t2 = source[_POK_TYPE2]
        if t1 in STEEL_POISON:
            return
        if t2 != 0 and (t2 in STEEL_POISON):
            return
        if source[_POK_AB_ID] == _ABILITYNAMES_IMMUNITY:
            return
    source[_POK_STATUS] = _STATUS_POISON


@njit
def apply_status(move, pok, weather, source, sec=False):
    """Apply status effects. ``source`` is the Pokemon whose move inflicted the status (for Synchronize)."""
    pok_status = pok[_POK_STATUS]
    if sec:
        m_status = move[_SEC_STATUS]
    else:
        m_status = move[_MOVE_STATUS]
    if m_status != _STATUS_SLEEP:
        if pok_status == 0:
            if m_status == _STATUS_FREEZE and weather == _WEATHER_SUN:
                return
            pok[_POK_STATUS] = m_status
            if m_status == _STATUS_TOXIC:
                pok[_POK_BADLY_POISON] = 1
            synchronize_reflect(pok, m_status, source)
            return
        return
    if pok_status == _STATUS_SLEEP:
        return
    pok[_POK_STATUS] = m_status
    pok[_POK_SLEEP_COUNTER] = random.getrandbits(2) + 1
    return


@njit
def stat_changes(move, attacker, defender, sec=False):
    """
    Check and apply stat changes
    """
    # 1.Check if ANY stat change exists
    has_stat_boost = False
    if sec:
        stat_map = SECONDARY_STAT_MAPPING
    else:
        stat_map = STAT_MAPPING
    for move_idx, _ in stat_map:
        if move[move_idx] != 0:
            has_stat_boost = True
            break

    if move[_MOVE_BOOST_ACC] != 0:
        has_stat_boost = True

    # 2. EXECUTE LOGIC if a stat boost is present
    if has_stat_boost:
        m_target = move[_MOVE_TARGET]

        # --- Apply Stats to Self ---
        if m_target in TARGET_SELF_SIDE:
            for move_idx, stat_idx in stat_map:
                boost = move[move_idx]
                if boost != 0:
                    attacker[stat_idx] = max(-6, min(6, attacker[stat_idx] + boost))

            acc_boost = move[_MOVE_BOOST_ACC] if not sec else move[_SEC_BOOST_ACC]
            if acc_boost != 0:
                attacker[_POK_ACCURACY_STAT_STAGE] = (
                    max(-6, min(6, attacker[_POK_ACCURACY_STAT_STAGE] + acc_boost))
                )

        # --- Apply Stats to Opponent ---
        elif m_target in TARGET_OPP_SIDE:
            for move_idx, stat_idx in stat_map:
                boost = move[move_idx]
                if boost != 0:
                    defender[stat_idx] = max(-6, min(6, defender[stat_idx] + boost))

            acc_boost = move[_MOVE_BOOST_ACC] if not sec else move[_SEC_BOOST_ACC]
            if acc_boost != 0:
                if acc_boost < 0 and defender[_POK_AB_ID] == _ABILITYNAMES_KEEN_EYE:
                    pass # Blocked
                else:
                    defender[_POK_ACCURACY_STAT_STAGE] = (
                        max(-6, min(6, defender[_POK_ACCURACY_STAT_STAGE] + acc_boost))
                    )


@njit
def vol_status(move, pok):
    """
    Check and apply any volatile status
    """
    v_status = move[_MOVE_VOL_STATUS]
    if v_status & _VOLSTATUS_CONFUSION:
        if not pok[_POK_VOL_STATUS] & _VOLSTATUS_CONFUSION:
            pok[_POK_VOL_STATUS] += _VOLSTATUS_CONFUSION
            pok[_POK_CONFUSION_COUNTER] = TURNS_2_5[random.getrandbits(2)]


@njit
def calculate_effects(attacker, defender, move, weather):
    """Calculate the effect parts of the moves"""
    # Stat Buffs and Debuffs
    stat_changes(move, attacker, defender)

    # Status
    if move[_MOVE_STATUS]:
        if move[_MOVE_TARGET] in TARGET_OPP_SIDE:
            apply_status(move, defender, weather, attacker)
        raise ValueError("Shouldn't have self status change")

    # Vol Status
    if move[_MOVE_VOL_STATUS]:
        vol_status(move, defender)


@njit
def sec_effects(move, attacker, defender, weather):
    """Calculate the secondary effects, like 10% of burning,
    30% of increasing attacking, Drain moves etc."""
    m_target = move[_MOVE_TARGET]
    target = m_target in TARGET_OPP_SIDE
    if target and defender[_POK_CURRENT_HP] <= 0:
        return
    chance = move[_SEC_CHANCE]
    roll = random.random()*100 if chance < 100 else 0
    if roll <= chance:
        # Stat can be both sides, so check and apply as normal
        stat_changes(move, attacker, defender, sec=True)

        # Status can only be opposing side, so only enter function if necessary
        if target:
            if move[_SEC_STATUS] != 0:
                apply_status(move, defender, weather, attacker, sec=True)


@njit
def after_turn_status(pok):
    """Calculate damage after turn like burn, poison, volatile status"""
    # TODO: Magic Guard
    status = pok[_POK_STATUS]
    badly = pok[_POK_BADLY_POISON]
    max_hp = pok[_POK_MAX_HP]
    dmg = 0
    if status:
        if status in B_P:
            if badly >= 1:
                if pok[_POK_AB_ID] != _ABILITYNAMES_MAGIC_GUARD:
                    dmg = max_hp * badly // 16
                pok[_POK_BADLY_POISON] += 1
            elif pok[_POK_AB_ID] != _ABILITYNAMES_MAGIC_GUARD:
                dmg = max_hp // 8
            return dmg
    return dmg


@njit
def paralysis():
    """Check if Pokemon is fully paralysed"""
    if random.getrandbits(2):  #25%
        return True
    return False


@njit
def freeze():
    """Check if it thaws"""
    if random.random() <= 0.2:
        return False
    return True
