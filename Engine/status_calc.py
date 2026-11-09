"""Calculate Status effects moves"""
import random
from Utils.jit import njit
from Models.helper import TARGET_OPP_SIDE, TARGET_SELF_SIDE, STEEL_POISON, Target
from Models.constants import (
    _POK_STATUS, _STATUS_BURN, _STATUS_POISON, _STATUS_TOXIC, _STATUS_SLEEP, _STATUS_FREEZE,
    _MOVE_BOOST_ATK, _MOVE_BOOST_DEF, _MOVE_BOOST_SPATK, _MOVE_BOOST_SPDEF, _MOVE_BOOST_SPEED,
    _MOVE_BOOST_EV, _MOVE_BOOST_ACC, _MOVE_STATUS, _MOVE_TARGET,  _WEATHER_SUN, _TYPES_GHOST,
    _SEC_STATUS, _SEC_CHANCE, _SEC_BOOST_ATK, _SEC_BOOST_DEF, _SEC_BOOST_SPATK, _VOLSTATUS_CURSE,
    _SEC_BOOST_EV, _SEC_BOOST_SPDEF, _SEC_BOOST_SPEED, _POK_ATTACK_STAT_STAGE, _POK_DEFENSE_STAT_STAGE,
    _POK_SPECIAL_ATTACK_STAT_STAGE, _POK_SPECIAL_DEFENSE_STAT_STAGE, _POK_SPEED_STAT_STAGE,
    _POK_EVASION_STAT_STAGE, _POK_BADLY_POISON, _POK_SLEEP_COUNTER, _POK_ACCURACY_STAT_STAGE,
    _POK_AB_ID, _POK_MAX_HP, _POK_TYPE1, _POK_TYPE2, _STATUS_PARALYSIS, _MOVENAME_CURSE,
    _TYPES_FIRE, _TYPES_ICE, _POK_CURRENT_HP, _SEC_BOOST_ACC, _MOVE_ID, _SEC_TARGET,
    _ABILITYNAMES_KEEN_EYE, _ABILITYNAMES_SYNCHRONIZE, _VOLSTATUS_DEFENSE_CURL, _VOLSTATUS_FOCUS_ENERGY,
    _ABILITYNAMES_IMMUNITY, _ABILITYNAMES_LIMBER, _ABILITYNAMES_WATER_VEIL, _MOVE_VOL_STATUS,
    _VOLSTATUS_CONFUSION, _POK_VOL_STATUS, _POK_CONFUSION_COUNTER, _SEC_VOL_STATUS,
    _VOLSTATUS_FORESIGHT, _VOLSTATUS_INGRAIN, _VOLSTATUS_AQUA_RING, _VOLSTATUS_LEECH_SEED,
    _VOLSTATUS_ATTRACT, _VOLSTATUS_DESTINY_BOND, _VOLSTATUS_YAWN, _VOLSTATUS_CHARGE,
    _VOLSTATUS_MUD_SPORT, _VOLSTATUS_WATER_SPORT, _TYPES_GRASS, _POK_GENDER, _POK_YAWN_TURNS,
    _GENDER_GENDERLESS, _VOLSTATUS_TAUNT, _VOLSTATUS_ENCORE, _VOLSTATUS_DISABLE, _POK_TAUNT_TURNS,
    _POK_ENCORE_TURNS, _POK_DISABLE_TURNS, _POK_LAST_MOVE_ID, _VOLSTATUS_UPROAR, _MOVE_PP,
    _ABILITYNAMES_SOUNDPROOF, _MOVENAME_ENCORE, _MOVENAME_MIRROR_MOVE, _MOVENAME_STRUGGLE,
    _SIDECONDITION_MIST, _SIDECONDITION_SAFEGUARD, _ABILITYNAMES_INSOMNIA, _ABILITYNAMES_VITAL_SPIRIT,
    _MOVENAME_TRI_ATTACK, _ABILITYNAMES_SERENE_GRACE,
    _ABILITYNAMES_SHIELD_DUST, _ABILITYNAMES_MAGMA_ARMOR, _ABILITYNAMES_LEAF_GUARD,
    _ABILITYNAMES_OWN_TEMPO, _ABILITYNAMES_OBLIVIOUS, _ABILITYNAMES_CLEAR_BODY,
    _ABILITYNAMES_WHITE_SMOKE, _ABILITYNAMES_HYPER_CUTTER, _ITEM_HOLD_EFFECT,
    _HOLDEFFECT_RECIPROCATE_INFAT,
)
from Models.idx_const import OFFSET_MOVE, MOVE_STRIDE
from Models.move import CURSE_BOOST
from Engine.ability_helper import ignorable_ability, reveal_ability

# --- Global Tuples ---
B_P_P = (_STATUS_BURN, _STATUS_POISON, _STATUS_TOXIC, _STATUS_PARALYSIS)
TURNS_2_5 = (2, 3, 4, 5)
# Volatiles without extra conditions, set only if the target doesn't have them yet
SET_ONCE_VOLS = (
    _VOLSTATUS_FORESIGHT, _VOLSTATUS_INGRAIN, _VOLSTATUS_AQUA_RING, _VOLSTATUS_DESTINY_BOND,
    _VOLSTATUS_CHARGE, _VOLSTATUS_MUD_SPORT, _VOLSTATUS_WATER_SPORT
)
# Mud Sport and Water Sport target the field but the volatile goes on the user
SELF_VOL_TARGETS = TARGET_SELF_SIDE + (Target.ALL,)
YAWN_DURATION = 2
# Encore and Disable keep the move slot in the low bits of their counter: turns * SLOT_STEP + slot
SLOT_STEP = 4
SLOT_MASK = 3
# Gen IV Encore fails on these last moves (Transform, Mimic, Sketch aren't in MoveDB)
ENCORE_FAIL_MOVES = (_MOVENAME_ENCORE, _MOVENAME_MIRROR_MOVE, _MOVENAME_STRUGGLE)
SLEEP_AB_IM = (_ABILITYNAMES_INSOMNIA, _ABILITYNAMES_VITAL_SPIRIT)
# Block every stat drop the foe causes
STAT_DROP_AB_IM = (_ABILITYNAMES_CLEAR_BODY, _ABILITYNAMES_WHITE_SMOKE)
# Tri Attack's secondary picks one of these at random
TRI_ATTACK_STATUSES = (_STATUS_BURN, _STATUS_PARALYSIS, _STATUS_FREEZE)

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
def cure_status(pok):
    """Clears the non-volatile status and its counters"""
    pok[_POK_STATUS] = 0
    pok[_POK_BADLY_POISON] = 0
    pok[_POK_SLEEP_COUNTER] = 0


@njit
def ability_forbids_status(ability, status):
    """The ability can't have this status (pokeplatinum Ability_ForbidsStatus)"""
    if status == _STATUS_PARALYSIS:
        return ability == _ABILITYNAMES_LIMBER
    if status == _STATUS_POISON or status == _STATUS_TOXIC:
        return ability == _ABILITYNAMES_IMMUNITY
    if status == _STATUS_BURN:
        return ability == _ABILITYNAMES_WATER_VEIL
    if status == _STATUS_FREEZE:
        return ability == _ABILITYNAMES_MAGMA_ARMOR
    if status == _STATUS_SLEEP:
        return ability in SLEEP_AB_IM
    return False


@njit
def ability_blocks_status(pok, source, status, weather):
    """
    pok's ability keeps the status off: Limber, Immunity, Water Veil, Magma Armor, Insomnia, Vital
    Spirit, and Leaf Guard against every status in sun. A Mold Breaker source ignores them. With no
    user (hazards, items, Yawn's sleep) pass pok as the source (pokeplatinum status subscripts)
    """
    if not ignorable_ability(pok, source):
        return False
    ability = pok[_POK_AB_ID]
    if ability == _ABILITYNAMES_LEAF_GUARD and weather == _WEATHER_SUN:
        return True
    return ability_forbids_status(ability, status)


@njit
def synchronize_reflect(recipient, applied_status, source, weather=0):
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
        if t1 == _TYPES_FIRE or t2 == _TYPES_FIRE:
            return
    elif applied_status != _STATUS_PARALYSIS:
        if t1 in STEEL_POISON or t2 in STEEL_POISON:
            return
        # Synchronize always inflicts standard Poison, even if triggered by Toxic
        applied_status = _STATUS_POISON
    if ability_blocks_status(source, recipient, applied_status, weather):
        return
    source[_POK_STATUS] = applied_status
    reveal_ability(recipient)


@njit
def uproar_active(p1, p2):
    """Either active is making an uproar"""
    return bool(
        (p1[_POK_VOL_STATUS] & _VOLSTATUS_UPROAR and p1[_POK_CURRENT_HP] > 0)
        or (p2[_POK_VOL_STATUS] & _VOLSTATUS_UPROAR and p2[_POK_CURRENT_HP] > 0)
    )


@njit
def sleep_blocked(pok, foe):
    """Nobody falls asleep during an uproar, except a Soundproof Pokemon"""
    return pok[_POK_AB_ID] != _ABILITYNAMES_SOUNDPROOF and uproar_active(pok, foe)


@njit
def last_move_slot(pok):
    """Slot of the move the Pokemon used last, -1 if none or it isn't one of its moves (Struggle)"""
    last = pok[_POK_LAST_MOVE_ID]
    if last == 0:
        return -1
    for i in range(4):
        if pok[OFFSET_MOVE + i * MOVE_STRIDE + _MOVE_ID] == last:
            return i
    return -1


@njit
def apply_status(move, pok, weather, source, sec=False, side=0, status=0):
    """Apply non-volatile status effects. side is pok's Field.SIDE_COND, Safeguard blocks it.
    status, when set, is used instead of the move's: only an ability's status (Static and co.)
    passes it without sec"""
    m_status = status if status else (move[_SEC_STATUS] if sec else move[_MOVE_STATUS])
    if m_status == 0:
        return
    # pokeplatinum's status subscripts check the ability first; a status move's message names it,
    # a secondary effect or an ability's status stays silent
    if ability_blocks_status(pok, source, m_status, weather):
        if not sec and not status:
            reveal_ability(pok)
        return

    # Gen 4: Cannot apply a new status if one already exists
    if pok[_POK_STATUS] != 0:
        return
    if side & _SIDECONDITION_SAFEGUARD:
        return

    t1 = pok[_POK_TYPE1]
    t2 = pok[_POK_TYPE2]
    if m_status == _STATUS_BURN and (t1 == _TYPES_FIRE or t2 == _TYPES_FIRE):
        return
    if m_status == _STATUS_FREEZE and (t1 == _TYPES_ICE or t2 == _TYPES_ICE):
        return
    if (m_status == _STATUS_POISON or m_status == _STATUS_TOXIC) and (
        t1 in STEEL_POISON or t2 in STEEL_POISON
    ):
        return

    if m_status == _STATUS_FREEZE and weather == _WEATHER_SUN:
        return
    if m_status == _STATUS_SLEEP and sleep_blocked(pok, source):
        return

    pok[_POK_STATUS] = m_status

    if m_status == _STATUS_TOXIC:
        pok[_POK_BADLY_POISON] = 1
    elif m_status == _STATUS_SLEEP:
        pok[_POK_SLEEP_COUNTER] = TURNS_2_5[random.getrandbits(2)]

    if m_status in B_P_P:
        synchronize_reflect(pok, m_status, source, weather)


@njit
def stat_drop_blocked(pok, source, stat_idx):
    """
    pok's ability keeps off a drop of stat_idx caused by the foe source: Clear Body and White Smoke
    every stat, Hyper Cutter Attack, Keen Eye accuracy. A Mold Breaker source ignores them
    (pokeplatinum BtlCmd_ChangeStatStage)
    """
    if not ignorable_ability(pok, source):
        return False
    ability = pok[_POK_AB_ID]
    if ability in STAT_DROP_AB_IM:
        return True
    if ability == _ABILITYNAMES_HYPER_CUTTER:
        return stat_idx == _POK_ATTACK_STAT_STAGE
    if ability == _ABILITYNAMES_KEEN_EYE:
        return stat_idx == _POK_ACCURACY_STAT_STAGE
    return False


@njit
def stat_changes(move, attacker, defender, sec=False, def_side=0):
    """Check and apply stat changes. def_side is the defender's Field.SIDE_COND, Mist there
    blocks the drops this move causes it, and so do the defender's stat_drop_blocked abilities"""
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
    m_target = move[_SEC_TARGET] if sec else move[_MOVE_TARGET]
    target_pok = attacker if m_target in TARGET_SELF_SIDE else defender
    targets_foe = m_target not in TARGET_SELF_SIDE
    misted = targets_foe and (def_side & _SIDECONDITION_MIST) != 0

    # 3. Apply stats safely to the evaluated target
    for move_idx, stat_idx in stat_map:
        boost = move[move_idx]
        if boost != 0 and not (
            boost < 0 and (misted or (targets_foe and stat_drop_blocked(defender, attacker, stat_idx)))
        ):
            target_pok[stat_idx] = max(-6, min(6, target_pok[stat_idx] + boost))

    # Apply Accuracy (Requires Keen Eye exception for Opponent target)
    if acc_boost != 0:
        if misted and acc_boost < 0:
            pass  # Blocked
        elif (
            targets_foe and acc_boost < 0
            and stat_drop_blocked(defender, attacker, _POK_ACCURACY_STAT_STAGE)
        ):
            pass  # Blocked
        else:
            target_pok[_POK_ACCURACY_STAT_STAGE] = (
                max(-6, min(6, target_pok[_POK_ACCURACY_STAT_STAGE] + acc_boost))
            )


@njit
def _can_infatuate(pok, source):
    """Only between a male and a female, not twice (pokeplatinum BtlCmd_TryAttract)"""
    pok_gender = pok[_POK_GENDER]
    src_gender = source[_POK_GENDER]
    return (
        not pok[_POK_VOL_STATUS] & _VOLSTATUS_ATTRACT
        and pok_gender != _GENDER_GENDERLESS
        and src_gender != _GENDER_GENDERLESS
        and pok_gender != src_gender
    )


@njit
def infatuate(pok, source):
    """Attract and Cute Charm: only between a male and a female. Oblivious stops it unless the
    source has Mold Breaker (pokeplatinum subscript_infatuate). An infatuated Destiny Knot holder
    infatuates the source back, under the same rules (pokeplatinum, after Synchronize; Showdown
    destinyknot onAttract)"""
    if pok[_POK_AB_ID] == _ABILITYNAMES_OBLIVIOUS and ignorable_ability(pok, source):
        return
    if _can_infatuate(pok, source):
        pok[_POK_VOL_STATUS] |= _VOLSTATUS_ATTRACT
        if pok[_ITEM_HOLD_EFFECT] == _HOLDEFFECT_RECIPROCATE_INFAT:
            # "X's Oblivious made the item ineffective!" names the ability
            if source[_POK_AB_ID] == _ABILITYNAMES_OBLIVIOUS and ignorable_ability(source, pok):
                reveal_ability(source)
            elif _can_infatuate(source, pok):
                source[_POK_VOL_STATUS] |= _VOLSTATUS_ATTRACT


@njit
def vol_status(move, pok, source, sec=False, side=0, weather=0):
    """Check and apply volatile status. side is pok's Field.SIDE_COND, Safeguard there blocks
    confusion and Yawn. Own Tempo blocks confusion unless the source has Mold Breaker"""
    v_status = move[_SEC_VOL_STATUS] if sec else move[_MOVE_VOL_STATUS]
    safeguard = side & _SIDECONDITION_SAFEGUARD

    own_tempo = pok[_POK_AB_ID] == _ABILITYNAMES_OWN_TEMPO and ignorable_ability(pok, source)
    # A confusion or Attract move names the ability that stops it (pokeplatinum subscript_confuse,
    # subscript_infatuate), a secondary effect doesn't
    if v_status & _VOLSTATUS_CONFUSION and own_tempo and not sec:
        reveal_ability(pok)
    if (
        v_status & _VOLSTATUS_CONFUSION
        and not safeguard
        and not own_tempo
    ):
        if not pok[_POK_VOL_STATUS] & _VOLSTATUS_CONFUSION:
            pok[_POK_VOL_STATUS] += _VOLSTATUS_CONFUSION
            pok[_POK_CONFUSION_COUNTER] = TURNS_2_5[random.getrandbits(2)]

    if v_status & _VOLSTATUS_CURSE:
        if not pok[_POK_VOL_STATUS] & _VOLSTATUS_CURSE:
            pok[_POK_VOL_STATUS] += _VOLSTATUS_CURSE
            source[_POK_CURRENT_HP] = max(0, source[_POK_CURRENT_HP]-(source[_POK_MAX_HP]//2))

    if v_status & _VOLSTATUS_DEFENSE_CURL:
        if not pok[_POK_VOL_STATUS] & _VOLSTATUS_DEFENSE_CURL:
            pok[_POK_VOL_STATUS] += _VOLSTATUS_DEFENSE_CURL

    if v_status & _VOLSTATUS_FOCUS_ENERGY:
        if not pok[_POK_VOL_STATUS] & _VOLSTATUS_FOCUS_ENERGY:
            pok[_POK_VOL_STATUS] += _VOLSTATUS_FOCUS_ENERGY

    for vol in SET_ONCE_VOLS:
        if v_status & vol and not pok[_POK_VOL_STATUS] & vol:
            pok[_POK_VOL_STATUS] |= vol

    # Grass types can't be seeded
    if v_status & _VOLSTATUS_LEECH_SEED:
        if (
            not pok[_POK_VOL_STATUS] & _VOLSTATUS_LEECH_SEED
            and pok[_POK_TYPE1] != _TYPES_GRASS
            and pok[_POK_TYPE2] != _TYPES_GRASS
        ):
            pok[_POK_VOL_STATUS] |= _VOLSTATUS_LEECH_SEED

    if v_status & _VOLSTATUS_ATTRACT:
        if pok[_POK_AB_ID] == _ABILITYNAMES_OBLIVIOUS and ignorable_ability(pok, source):
            reveal_ability(pok)
        infatuate(pok, source)

    # Fails on a target that already has a status or is already drowsy, and during an uproar unless
    # the target is Soundproof. pokeplatinum subscript_yawn checks the ability first and its message
    # names it
    if v_status & _VOLSTATUS_YAWN and ability_blocks_status(pok, source, _STATUS_SLEEP, weather):
        reveal_ability(pok)
    elif v_status & _VOLSTATUS_YAWN and not safeguard and not sleep_blocked(pok, source):
        if not pok[_POK_VOL_STATUS] & _VOLSTATUS_YAWN and pok[_POK_STATUS] == 0:
            pok[_POK_VOL_STATUS] |= _VOLSTATUS_YAWN
            pok[_POK_YAWN_TURNS] = YAWN_DURATION

    # Gen IV: 3-5 turns, counting down from the end of this turn
    if v_status & _VOLSTATUS_TAUNT:
        if not pok[_POK_VOL_STATUS] & _VOLSTATUS_TAUNT:
            pok[_POK_VOL_STATUS] |= _VOLSTATUS_TAUNT
            pok[_POK_TAUNT_TURNS] = random.randint(3, 5)

    # Both lock onto the target's last move, which needs PP left. Encore 3-7 turns, Disable 3-6
    if v_status & _VOLSTATUS_ENCORE:
        slot = last_move_slot(pok)
        if (
            not pok[_POK_VOL_STATUS] & _VOLSTATUS_ENCORE
            and slot >= 0
            and pok[_POK_LAST_MOVE_ID] not in ENCORE_FAIL_MOVES
            and pok[OFFSET_MOVE + slot * MOVE_STRIDE + _MOVE_PP] > 0
        ):
            pok[_POK_VOL_STATUS] |= _VOLSTATUS_ENCORE
            pok[_POK_ENCORE_TURNS] = random.randint(3, 7) * SLOT_STEP + slot

    if v_status & _VOLSTATUS_DISABLE:
        slot = last_move_slot(pok)
        if (
            not pok[_POK_VOL_STATUS] & _VOLSTATUS_DISABLE
            and slot >= 0
            and pok[OFFSET_MOVE + slot * MOVE_STRIDE + _MOVE_PP] > 0
        ):
            pok[_POK_VOL_STATUS] |= _VOLSTATUS_DISABLE
            pok[_POK_DISABLE_TURNS] = random.randint(3, 6) * SLOT_STEP + slot


@njit
def calculate_effects(attacker, defender, move, weather, def_side=0):
    """Calculate primary move effects. def_side is the defender's Field.SIDE_COND"""
    # Curse different moves
    if move[_MOVE_ID] == _MOVENAME_CURSE:
        if attacker[_POK_TYPE1] != _TYPES_GHOST and attacker[_POK_TYPE2] != _TYPES_GHOST:
            move = CURSE_BOOST
    stat_changes(move, attacker, defender, False, def_side)

    if move[_MOVE_STATUS] != 0:
        if move[_MOVE_TARGET] in TARGET_OPP_SIDE:
            apply_status(move, defender, weather, attacker, False, def_side)
        else:
            raise ValueError("Shouldn't have self status change in this block")

    if move[_MOVE_VOL_STATUS] != 0:
        if move[_MOVE_TARGET] in SELF_VOL_TARGETS:
            vol_status(move, attacker, attacker)
        else:
            vol_status(move, defender, attacker, False, def_side, weather)


@njit
def sec_effects(move, attacker, defender, weather, def_side=0):
    """Calculate secondary move effects (e.g., 10% Burn). def_side is the defender's Field.SIDE_COND.
    Shield Dust blocks the ones aimed at its holder unless the attacker has Mold Breaker, Serene
    Grace doubles the chance (pokeplatinum BtlCmd_CheckEffectActivation)"""
    m_target = move[_SEC_TARGET]
    target_opp = m_target in TARGET_OPP_SIDE

    if target_opp and defender[_POK_CURRENT_HP] <= 0:
        return
    if (
        target_opp
        and defender[_POK_AB_ID] == _ABILITYNAMES_SHIELD_DUST
        and ignorable_ability(defender, attacker)
    ):
        return

    chance = move[_SEC_CHANCE]
    if attacker[_POK_AB_ID] == _ABILITYNAMES_SERENE_GRACE:
        chance *= 2

    if chance == 100 or random.randint(1, 100) <= chance:
        stat_changes(move, attacker, defender, True, def_side)

        if target_opp:
            if move[_MOVE_ID] == _MOVENAME_TRI_ATTACK:
                apply_status(
                    move, defender, weather, attacker, True, def_side,
                    TRI_ATTACK_STATUSES[random.randrange(3)]
                )
            if move[_SEC_STATUS] != 0:
                apply_status(move, defender, weather, attacker, True, def_side)
            if move[_SEC_VOL_STATUS] != 0:
                vol_status(move, defender, attacker, True, def_side, weather)


@njit
def paralysis():
    """Returns True if the Pokémon is fully paralyzed (25% chance)."""
    return random.getrandbits(2) == 0


@njit
def freeze():
    """Returns True if the Pokémon thaws from ice (20% chance)."""
    return random.random() <= 0.2
