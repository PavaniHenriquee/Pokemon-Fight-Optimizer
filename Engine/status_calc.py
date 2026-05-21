"""Calculate Status effects moves"""
import random
from Models.idx_const import Pok, Move, Sec
from Models.helper import Status, MoveCategory, Weather, TARGET_OPP_SIDE, TARGET_SELF_SIDE
from DataBase.AbilitiesDB import AbilityNames


B_P = {Status.BURN, Status.POISON, Status.TOXIC}

def apply_status(move, pok, weather, sec=False):
    """Apply status effects"""
    pok_status = pok[Pok.STATUS]
    if sec:
        m_status = move[Sec.STATUS]
    else:
        m_status = move[Move.STATUS]
    if m_status != Status.SLEEP:
        if pok_status == 0:
            if m_status == Status.FREEZE and weather == Weather.SUN:
                return
            pok[Pok.STATUS] = m_status
            if m_status == Status.TOXIC:
                pok[Pok.BADLY_POISON] = 1
            return
        return
    if pok_status == Status.SLEEP:
        return
    pok[Pok.STATUS] = m_status
    pok[Pok.SLEEP_COUNTER] = random.getrandbits(2) + 1
    return


def calculate_effects(attacker, defender, move, weather):
    """Calculate the effect parts of the moves"""
    if move[Move.CATEGORY] != MoveCategory.STATUS:
        return

    # Stat boost and reducing
    b_atk = move[Move.BOOST_ATK]
    b_def = move[Move.BOOST_DEF]
    b_spatk = move[Move.BOOST_SPATK]
    b_spdef = move[Move.BOOST_SPDEF]
    b_speed = move[Move.BOOST_SPEED]
    b_acc = move[Move.BOOST_ACC]
    b_ev = move[Move.BOOST_EV]
    if (b_atk
        or b_def
        or b_spatk
        or b_spdef
        or b_speed
        or b_acc
        or b_ev
    ):
        m_target = move[Move.TARGET]
        if m_target in TARGET_SELF_SIDE:
            if b_atk:
                attacker[Pok.ATTACK_STAT_STAGE] += b_atk
            if b_def:
                attacker[Pok.DEFENSE_STAT_STAGE] += b_def
            if b_spatk:
                attacker[Pok.SPECIAL_ATTACK_STAT_STAGE] += b_spatk
            if b_spdef:
                attacker[Pok.SPECIAL_DEFENSE_STAT_STAGE] += b_spdef
            if b_speed:
                attacker[Pok.SPEED_STAT_STAGE] += b_speed
            if b_acc:
                attacker[Pok.ACCURACY_STAT_STAGE] += b_acc
            if b_ev:
                attacker[Pok.EVASION_STAT_STAGE] += b_ev

        if m_target in TARGET_OPP_SIDE:
            if b_atk:
                defender[Pok.ATTACK_STAT_STAGE] += b_atk
            if b_def:
                defender[Pok.DEFENSE_STAT_STAGE] += b_def
            if b_spatk:
                defender[Pok.SPECIAL_ATTACK_STAT_STAGE] += b_spatk
            if b_spdef:
                defender[Pok.SPECIAL_DEFENSE_STAT_STAGE] += b_spdef
            if b_speed:
                defender[Pok.SPEED_STAT_STAGE] += b_speed
            if b_acc and defender[Pok.AB_ID] == AbilityNames.KEEN_EYE:
                defender[Pok.ACCURACY_STAT_STAGE] += b_acc
            if b_ev:
                defender[Pok.EVASION_STAT_STAGE] += b_ev
    # Status
    if move[Move.STATUS] != 0:
        if move[Move.TARGET] in TARGET_OPP_SIDE:
            apply_status(move, defender, weather)
        raise ValueError("Shouldn't have self status change")


def sec_effects(move, attacker, defender, weather):
    """Calculate the secondary effects, like 10% of burning,
    30% of increasing attacking, Drain moves etc."""
    chance = move[Sec.CHANCE]
    roll = random.random()*100 if chance < 100 else 0
    if roll <= chance:
        m_target = move[Move.TARGET]
        if m_target in TARGET_OPP_SIDE:
            if move[Sec.STATUS] != 0:
                apply_status(move, defender, weather, sec=True)
        if m_target in TARGET_SELF_SIDE:
            b_atk = move[Move.BOOST_ATK]
            b_def = move[Move.BOOST_DEF]
            b_spatk = move[Move.BOOST_SPATK]
            b_spdef = move[Move.BOOST_SPDEF]
            b_speed = move[Move.BOOST_SPEED]
            b_acc = move[Move.BOOST_ACC]
            b_ev = move[Move.BOOST_EV]
            if (b_atk
                or b_def
                or b_spatk
                or b_spdef
                or b_speed
                or b_acc
                or b_ev
            ):
                if b_atk:
                    attacker[Pok.ATTACK_STAT_STAGE] += b_atk
                if b_def:
                    attacker[Pok.DEFENSE_STAT_STAGE] += b_def
                if b_spatk:
                    attacker[Pok.SPECIAL_ATTACK_STAT_STAGE] += b_spatk
                if b_spdef:
                    attacker[Pok.SPECIAL_DEFENSE_STAT_STAGE] += b_spdef
                if b_speed:
                    attacker[Pok.SPEED_STAT_STAGE] += b_speed
                if b_acc:
                    attacker[Pok.ACCURACY_STAT_STAGE] += b_acc
                if b_ev:
                    attacker[Pok.EVASION_STAT_STAGE] += b_ev


def after_turn_status(pok):
    """Calculate damage after turn like burn, poison, volatile status"""
    # TODO: Magic Guard
    status = pok[Pok.STATUS]
    badly = pok[Pok.BADLY_POISON]
    max_hp = pok[Pok.MAX_HP]
    dmg = 0
    if status:
        if status in B_P:
            if badly >= 1:
                if pok[Pok.AB_ID] != AbilityNames.MAGIC_GUARD:
                    dmg = max_hp * badly // 16
                pok[Pok.BADLY_POISON] += 1
            elif pok[Pok.AB_ID] != AbilityNames.MAGIC_GUARD:
                dmg = max_hp // 8
            return dmg
    return dmg


def paralysis():
    """Check if Pokemon is fully paralysed"""
    if random.getrandbits(2):  #25%
        return True
    return False


def freeze():
    """Check if it thaws"""
    if random.random() <= 0.2:
        return False
    return True
