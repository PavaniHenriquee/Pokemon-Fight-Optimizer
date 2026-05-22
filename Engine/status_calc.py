"""Calculate Status effects moves"""
import random
from Models.idx_const import Pok, Move, Sec
from Models.helper import Status, MoveCategory, Weather, TARGET_OPP_SIDE, TARGET_SELF_SIDE
from DataBase.AbilitiesDB import AbilityNames


B_P = {Status.BURN, Status.POISON, Status.TOXIC}
STAT_MAPPING = (
    (Move.BOOST_ATK, Pok.ATTACK_STAT_STAGE),
    (Move.BOOST_DEF, Pok.DEFENSE_STAT_STAGE),
    (Move.BOOST_SPATK, Pok.SPECIAL_ATTACK_STAT_STAGE),
    (Move.BOOST_SPDEF, Pok.SPECIAL_DEFENSE_STAT_STAGE),
    (Move.BOOST_SPEED, Pok.SPEED_STAT_STAGE),
    (Move.BOOST_EV, Pok.EVASION_STAT_STAGE)
)


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



def stat_changes(move, attacker, defender):
    """
    Check and apply stat changes
    """
     # 1.Check if ANY stat change exists
    has_stat_boost = False
    for move_idx, _ in STAT_MAPPING:
        if move[move_idx] != 0:
            has_stat_boost = True
            break

    if move[Move.BOOST_ACC] != 0:
        has_stat_boost = True

    # 2. EXECUTE LOGIC if a stat boost is present
    if has_stat_boost:
        m_target = move[Move.TARGET]

        # --- Apply Stats to Self ---
        if m_target in TARGET_SELF_SIDE:
            for move_idx, stat_idx in STAT_MAPPING:
                boost = move[move_idx]
                if boost != 0:
                    attacker[stat_idx] = max(-6, min(6, attacker[stat_idx] + boost))

            acc_boost = move[Move.BOOST_ACC]
            if acc_boost != 0:
                attacker[Pok.ACCURACY_STAT_STAGE] = (
                    max(-6, min(6, attacker[Pok.ACCURACY_STAT_STAGE] + acc_boost))
                )

        # --- Apply Stats to Opponent ---
        elif m_target in TARGET_OPP_SIDE:
            for move_idx, stat_idx in STAT_MAPPING:
                boost = move[move_idx]
                if boost != 0:
                    defender[stat_idx] = max(-6, min(6, defender[stat_idx] + boost))

            acc_boost = move[Move.BOOST_ACC]
            if acc_boost != 0:
                if acc_boost < 0 and defender[Pok.AB_ID] == AbilityNames.KEEN_EYE:
                    pass # Blocked
                else:
                    defender[Pok.ACCURACY_STAT_STAGE] = (
                        max(-6, min(6, defender[Pok.ACCURACY_STAT_STAGE] + acc_boost))
                    )


def calculate_effects(attacker, defender, move, weather):
    """Calculate the effect parts of the moves"""
    if move[Move.CATEGORY] != MoveCategory.STATUS:
        return

    # Stat Buffs and Debuffs
    stat_changes(move, attacker, defender)

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

        # Stat can be both sides, so check and apply as normal
        stat_changes(move, attacker, defender)

        # Status can only be opposing side, so only enter function if necessary
        if m_target in TARGET_OPP_SIDE:
            if move[Sec.STATUS] != 0:
                apply_status(move, defender, weather, sec=True)


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
