"""Calculate Status effects moves"""
import random
import numpy as np
from Models.idx_const import Pok, Move, Sec
from Models.helper import Status, MoveCategory, Target, Weather


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
            pok_status = m_status
            if m_status == Status.TOXIC:
                pok[Pok.BADLY_POISON] = 1
            return
        return
    if pok_status == Status.SLEEP:
        return
    pok[Pok.STATUS] = m_status
    pok[Pok.SLEEP_COUNTER] = random.getrandbits(2) + 1
    return


def drain_effect(attacker, dmg, drain_amount):
    """Calculates how much should it drain"""
    drain_hp = np.floor(dmg * drain_amount)
    if drain_hp <= 0:
        drain_hp = 1
    if attacker[Pok.CURRENT_HP] + drain_hp > attacker[Pok.MAX_HP]:
        drain_hp = attacker[Pok.MAX_HP] - attacker[Pok.CURRENT_HP]
    if drain_hp <= 0:
        return
    attacker[Pok.CURRENT_HP] += drain_hp


def calculate_effects(attacker, defender, move, weather):
    """Calculate the effect parts of the moves"""
    if move[Move.CATEGORY] != MoveCategory.STATUS:
        return

    # Stat boost and reducing
    if any(move[Move.BOOST_ATK: Move.BOOST_EV + 1]):
        if move[Move.TARGET] in (
            Target.ADJACENT_ALLY,
            Target.ADJACENT_ALLY_OR_SELF,
            Target.ALLIES,
            Target.ALLY_SIDE,
            Target.SELF
        ):
            if move[Move.BOOST_ATK]:
                attacker[Pok.ATTACK_STAT_STAGE] += move[Move.BOOST_ATK]
            if move[Move.BOOST_DEF]:
                attacker[Pok.DEFENSE_STAT_STAGE] += move[Move.BOOST_DEF]
            if move[Move.BOOST_SPATK]:
                attacker[Pok.SPECIAL_ATTACK_STAT_STAGE] += move[Move.BOOST_SPATK]
            if move[Move.BOOST_SPDEF]:
                attacker[Pok.SPECIAL_DEFENSE_STAT_STAGE] += move[Move.BOOST_SPDEF]
            if move[Move.BOOST_SPEED]:
                attacker[Pok.SPEED_STAT_STAGE] += move[Move.BOOST_SPEED]
            if move[Move.BOOST_ACC]:
                attacker[Pok.ACCURACY_STAT_STAGE] += move[Move.BOOST_ACC]
            if move[Move.BOOST_EV]:
                attacker[Pok.EVASION_STAT_STAGE] += move[Move.BOOST_EV]

        if move[Move.TARGET] in (
            Target.NORMAL,
            Target.ADJACENT_FOE,
            Target.ALL_ADJACENT_FOES,
            Target.ANY,
            Target.FOE_SIDE,
            Target.RANDOM_NORMAL,
            Target.SCRIPTED
        ):
            if move[Move.BOOST_ATK]:
                defender[Pok.ATTACK_STAT_STAGE] += move[Move.BOOST_ATK]
            if move[Move.BOOST_DEF]:
                defender[Pok.DEFENSE_STAT_STAGE] += move[Move.BOOST_DEF]
            if move[Move.BOOST_SPATK]:
                defender[Pok.SPECIAL_ATTACK_STAT_STAGE] += move[Move.BOOST_SPATK]
            if move[Move.BOOST_SPDEF]:
                defender[Pok.SPECIAL_DEFENSE_STAT_STAGE] += move[Move.BOOST_SPDEF]
            if move[Move.BOOST_SPEED]:
                defender[Pok.SPEED_STAT_STAGE] += move[Move.BOOST_SPEED]
            if move[Move.BOOST_ACC]:
                defender[Pok.ACCURACY_STAT_STAGE] += move[Move.BOOST_ACC]
            if move[Move.BOOST_EV]:
                defender[Pok.EVASION_STAT_STAGE] += move[Move.BOOST_EV]
    # Status
    if move[Move.STATUS] != 0:
        if move[Move.TARGET] in (
            Target.NORMAL,
            Target.ADJACENT_FOE,
            Target.ALL_ADJACENT_FOES,
            Target.ANY,
            Target.FOE_SIDE,
            Target.RANDOM_NORMAL,
            Target.SCRIPTED
        ):
            apply_status(move, defender, weather)
        raise ValueError("Shouldn't have self status change")


def sec_effects(move, attacker, defender, dmg, weather):
    """Calculate the secondary effects, like 10% of burning,
    30% of increasing attacking, Drain moves etc."""
    chance = move[Sec.CHANCE] / 100
    roll = random.random() if chance < 1 else 0
    if roll <= chance:
        if move[Move.TARGET] in (
            Target.NORMAL,
            Target.ADJACENT_FOE,
            Target.ALL_ADJACENT_FOES,
            Target.ANY,
            Target.FOE_SIDE,
            Target.RANDOM_NORMAL,
            Target.SCRIPTED
        ):
            a = move[Sec.STATUS]
            if a != 0:
                apply_status(move, defender, weather, sec=True)
        if move[Move.TARGET] in (
            Target.ADJACENT_ALLY,
            Target.ADJACENT_ALLY_OR_SELF,
            Target.ALLIES,
            Target.ALLY_SIDE,
            Target.SELF
        ):
            if any(move[Sec.BOOST_ATK: Sec.BOOST_EV + 1]):
                if move[Sec.BOOST_ATK]:
                    attacker[Pok.ATTACK_STAT_STAGE] += move[Sec.BOOST_ATK]
                if move[Sec.BOOST_DEF]:
                    attacker[Pok.DEFENSE_STAT_STAGE] += move[Sec.BOOST_DEF]
                if move[Sec.BOOST_SPATK]:
                    attacker[Pok.SPECIAL_ATTACK_STAT_STAGE] += move[Sec.BOOST_SPATK]
                if move[Sec.BOOST_SPDEF]:
                    attacker[Pok.SPECIAL_DEFENSE_STAT_STAGE] += move[Sec.BOOST_SPDEF]
                if move[Sec.BOOST_SPEED]:
                    attacker[Pok.SPEED_STAT_STAGE] += move[Sec.BOOST_SPEED]
                if move[Sec.BOOST_ACC]:
                    attacker[Pok.ACCURACY_STAT_STAGE] += move[Sec.BOOST_ACC]
                if move[Sec.BOOST_EV]:
                    attacker[Pok.EVASION_STAT_STAGE] += move[Sec.BOOST_EV]
            if move[Move.DRAIN]:
                drain_effect(attacker, dmg, move[Move.DRAIN])


def after_turn_status(pok):
    """Calculate damage after turn like burn, poison, volatile status"""
    # TODO: Magic Guard
    status = pok[Pok.STATUS]
    badly = pok[Pok.BADLY_POISON]
    max_hp = pok[Pok.MAX_HP]
    if status:
        if status in B_P:
            if badly >= 1:
                dmg = max_hp * badly // 16
                pok[Pok.BADLY_POISON] += 1
            else:
                dmg = max_hp // 8
            return dmg
    return 0


def paralysis():
    """Check if Pokemon is fully paralysed"""
    if random.getrandbits(2):
        return True
    return False


def freeze():
    """Check if it thaws"""
    if random.random() <= 0.2:
        return False
    return True
