"""
Helper to make the trainer ai more readable and everthing more organized
"""
import random
from Models.idx_const import Pok, Move, Flags
from Models.helper import (
    MoveCategory, Types, Status, Weather, VolStatus, Gender,
    TARGET_OPP_SIDE, TARGET_SELF_SIDE
)
from Utils.loader import TYPE_CHART
from Utils.helper import get_type_effectiveness
from DataBase.AbilitiesDB import AbilityNames
from DataBase.PkDB import POKEMON_ABILITY_POOL
from DataBase.MoveDB import MoveName
from DataBase.loader import abDB
from Engine.engine_helper import check_speed


ELEC_AB_IM = {AbilityNames.VOLT_ABSORB, AbilityNames.MOTOR_DRIVE}
POISON_AB_IM = {AbilityNames.IMMUNITY, AbilityNames.MAGIC_GUARD, AbilityNames.POISON_POINT}
PARA_AB_IM = {AbilityNames.LIMBER, AbilityNames.MAGIC_GUARD}
BURN_AB_IM = {AbilityNames.WATER_VEIL, AbilityNames.MAGIC_GUARD}
STAT_AB_IM = {AbilityNames.CLEAR_BODY, AbilityNames.WHITE_SMOKE}
ABILITY_BASIC_FLAG = {
    AbilityNames.VOLT_ABSORB, AbilityNames.MOTOR_DRIVE, AbilityNames.WATER_ABSORB,
    AbilityNames.FLASH_FIRE, AbilityNames.LEVITATE, AbilityNames.SOUNDPROOF,
    AbilityNames.WONDER_GUARD
}

STEEL_POISON = {Types.STEEL, Types.POISON}

SELF_KILL_MOVE = {MoveName.EXPLOSION, MoveName.SELFDESTRUCT}
WEIRD_PRIO_MOVE = {MoveName.SUCKER_PUNCH, MoveName.FOCUS_PUNCH, MoveName.FUTURE_SIGHT}
MAYBE_BAD_MOVES = {
    MoveName.SUCKER_PUNCH,
    MoveName.FOCUS_PUNCH,
    MoveName.EXPLOSION,
    MoveName.SELFDESTRUCT
}
SLEEP_MOVES = {MoveName.DREAM_EATER, MoveName.NIGHTMARE}
CONFUSE_SPECIAL_CASES = {MoveName.SWAGGER, MoveName.FLATTER}

STAB_CORRECTNESS = {
    0.375: 0.25,
    0.75: 0.5,
    3.0: 2.0,
    6.0: 4.0
}
STAB_C = {0.375, 0.75, 3.0, 6.0}

# --- Abilities explicitly checked in basic_flag / expert_flag ---
_EXPLICIT_RELEVANT: frozenset = frozenset({
    AbilityNames.VOLT_ABSORB,
    AbilityNames.MOTOR_DRIVE,
    AbilityNames.WATER_ABSORB,
    AbilityNames.FLASH_FIRE,
    AbilityNames.LEVITATE,
    AbilityNames.SOUNDPROOF,
    AbilityNames.WONDER_GUARD,
    AbilityNames.VITAL_SPIRIT,
    AbilityNames.IMMUNITY,
    AbilityNames.MAGIC_GUARD,
    AbilityNames.POISON_POINT,
    AbilityNames.LEAF_GUARD,
    AbilityNames.HYDRATION,
    AbilityNames.LIMBER,
    AbilityNames.WATER_VEIL,
    AbilityNames.CLEAR_BODY,
    AbilityNames.WHITE_SMOKE,
    AbilityNames.OWN_TEMPO,
    AbilityNames.OBLIVIOUS,
    AbilityNames.SUCTION_CUPS,
    AbilityNames.STURDY,
    AbilityNames.HYPER_CUTTER,
    AbilityNames.SPEED_BOOST,
    AbilityNames.NO_GUARD,
    AbilityNames.KEEN_EYE,
    AbilityNames.SIMPLE,
})

# --- Abilities that will affect damage calc / effectiveness---
# Derived from abDB using their `when` activation strings
_DAMAGE_RELEVANT_WHEN: frozenset = frozenset({
    "on_try_move"       # DAMP, SOUNDPROOF, WATER_ABSORB, STURDY, ...
})

_activation_relevant: set = set()
for ab_name, ab_data in abDB.items():
    when = ab_data.get("when")
    if not when:
        continue
    whens = when if isinstance(when, list) else [when]
    if any(w in _DAMAGE_RELEVANT_WHEN for w in whens):
        try:
            _activation_relevant.add(
                getattr(AbilityNames, ab_name.upper().replace(" ", "_"))
            )
        except AttributeError:
            pass  # ability in DB not yet in AbilityNames, skip

RELEVANT_ABILITIES: frozenset = _EXPLICIT_RELEVANT | _activation_relevant


# --- Pre-compute per pokemon whether ANY of its pool abilities are relevant ---
POKEMON_HAS_RELEVANT_ABILITY: tuple = tuple(
    any(ab_id in RELEVANT_ABILITIES for ab_id in pool)
    for pool in POKEMON_ABILITY_POOL  # reuses the tuple you already built
)


def add_adjustment(arr, move_id, delta, chance):
    """Add a [delta, chance] pair to the first free slot."""
    # Find the first index where chance is NaN (unused)
    arr[move_id].append((delta, chance))


def trainer_ai_effectiveness(move, ai_pok, user_pok):
    """
    How the AI consider type effectivness, which has some differences from
    how it usually goes
    """


    """If the user has the ability Normalize, the move's type is changed to Normal.
    Otherwise, if the move is Natural Gift, Hidden Power, Judgment, or Weather Ball,
    the move is adjusted to its correct type."""
    effectiveness = 1.0
    move_type = move[Move.TYPE]
    move_cat = move[Move.CATEGORY]
    ai_type1 = ai_pok[Pok.TYPE1]
    ai_type2 = ai_pok[Pok.TYPE2]
    ai_ability = ai_pok[Pok.AB_ID]
    user_type1 = user_pok[Pok.TYPE1]
    user_type2 = user_pok[Pok.TYPE2]

    # STAB
    if move_type == ai_type1 or move_type == ai_type2:  # pylint: disable=consider-using-in
        effectiveness *= 1.5 if ai_ability != AbilityNames.ADAPTABILITY else 2

    # Common type effectiveness
    # TODO: Scrappy, Mold Breaker, Odor Sleuth, Foresight,
    # Gastro Acid, Miracle Eye, Iron Ball
    # Gravity, Magnet Rise, Levitate, Wonder Guard, more...
    effectiveness *= TYPE_CHART[(move_type*19)+user_type1] / 2
    if user_type2:
        effectiveness *= TYPE_CHART[(move_type*19)+user_type2] / 4

    if move_cat != MoveCategory.STATUS:
        # TODO: Tinted Lens, Filter/Solid Rock, Expert Belt
        pass



    # Correct for the right effectiveness
    if effectiveness in STAB_C:
        effectiveness = STAB_CORRECTNESS[effectiveness]

    return effectiveness


def basic_ability(move, ability, user_pok, move_category) -> bool:
    """
    Checks to see if ability triggers on basic flag
    """
    move_type = move[Move.TYPE]
    if move_type == Types.ELECTRIC and ability in ELEC_AB_IM:
        return True
    if move_type == Types.WATER and ability == AbilityNames.WATER_ABSORB:
        return True
    if move_type == Types.FIRE and ability == AbilityNames.FLASH_FIRE:
        return True
    if move_type == Types.GROUND and ability == AbilityNames.LEVITATE:
        return True
    if move[Flags.SOUND] and ability == AbilityNames.SOUNDPROOF:
        return True
    if (
        ability == AbilityNames.WONDER_GUARD
        and move_category != MoveCategory.STATUS
        and get_type_effectiveness(move_type, user_pok[Pok.TYPE1],user_pok[Pok.TYPE2]) >= 2
    ):
        return True
    return False


def basic_move_status(move, ability, user_pok, ai_pok, weather):
    """
    Checks to see if any of the conditions for move status being irrelevant comes back as true
    """
    # TODO: Safeguard
    u_type12 = (user_pok[Pok.TYPE1],user_pok[Pok.TYPE2])
    move_status = move[Move.STATUS]
    user_status = user_pok[Pok.STATUS] != 0

    if user_status:
        return True

    # Sleep
    if (
        move_status == Status.SLEEP
        and ability == AbilityNames.VITAL_SPIRIT
    ):
        return True

    # Poison
    if (
        move_status in (Status.POISON, Status.TOXIC)
    ):
        if not STEEL_POISON.isdisjoint(u_type12):
            return True
        elif ability in POISON_AB_IM:
            return True
        elif weather:
            if (
                weather == Weather.SUN
                and ability == AbilityNames.LEAF_GUARD
            ):
                return True
            elif (
                weather == Weather.RAIN
                and ability == AbilityNames.HYDRATION
            ):
                return True

    # Paralysis
    if move_status == Status.PARALYSIS:
        has_para_immunity = ability in PARA_AB_IM
        # Electric-specific immunities
        is_electric_fail = False
        if move[Move.TYPE] == Types.ELECTRIC:
            is_ground = Types.GROUND in u_type12
            is_elec_immune_ability = (
                ability in ELEC_AB_IM
                and ai_pok[Pok.AB_ID] != AbilityNames.MOLD_BREAKER
            )
            is_electric_fail = is_ground or is_elec_immune_ability

        if has_para_immunity or is_electric_fail:
            return True

    # Burn
    if (
        move_status == Status.BURN
        and (
            ability in BURN_AB_IM
            or Types.FIRE in u_type12
        )
    ):
        return True

    return False


def basic_move_vol_status(move, ability, user_pok, ai_pok):
    """
    Checks to see if any of the conditions for a move that has volatile status
    is irrelevant
    """
    # TODO: Every volatile status
    vol_status = move[Move.VOL_STATUS]
    user_vol_status = user_pok[Pok.VOL_STATUS]

    if vol_status == VolStatus.CONFUSION:
        if user_vol_status & VolStatus.CONFUSION:
            return -5
        if ability == AbilityNames.OWN_TEMPO:
            return -10
    # Attract
    elif vol_status == VolStatus.ATTRACT:
        if (
            user_vol_status & VolStatus.ATTRACT
            or ability == AbilityNames.OBLIVIOUS
            or (
                user_pok[Pok.GENDER] == ai_pok[Pok.GENDER]
                or user_pok[Pok.GENDER] == Gender.GENDERLESS
            )
        ):
            return -10

    return 0


def basic_stat_change(move, ability, user_pok, ai_pok) -> bool:
    """
    Checks to see if any of the bad uses for a buff or debuff stat move
    happens and returns the check if the do
    """
    # TODO: Trick room
    b_atk   = move[Move.BOOST_ATK]
    b_def   = move[Move.BOOST_DEF]
    b_spatk = move[Move.BOOST_SPATK]
    b_spdef = move[Move.BOOST_SPDEF]
    b_spe   = move[Move.BOOST_SPEED]
    b_acc   = move[Move.BOOST_ACC]
    b_ev    = move[Move.BOOST_EV]
    if move[Move.TARGET] in TARGET_SELF_SIDE:  # your already-extracted set
        s_atk   = ai_pok[Pok.ATTACK_STAT_STAGE]
        s_def   = ai_pok[Pok.DEFENSE_STAT_STAGE]
        s_spatk = ai_pok[Pok.SPECIAL_ATTACK_STAT_STAGE]
        s_spdef = ai_pok[Pok.SPECIAL_DEFENSE_STAT_STAGE]
        s_spe   = ai_pok[Pok.SPEED_STAT_STAGE]
        s_acc   = ai_pok[Pok.ACCURACY_STAT_STAGE]
        s_ev    = ai_pok[Pok.EVASION_STAT_STAGE]

        # Unify Simple (cap=3) and normal (cap=6) into one threshold
        cap = 3 if ai_pok[Pok.AB_ID] == AbilityNames.SIMPLE else 6

        if (b_atk   > 0 and s_atk   >= cap) \
        or (b_def   > 0 and s_def   >= cap) \
        or (b_spatk > 0 and s_spatk >= cap) \
        or (b_spdef > 0 and s_spdef >= cap) \
        or (b_spe   > 0 and s_spe   >= cap) \
        or (b_acc   > 0 and s_acc   >= cap) \
        or (b_ev    > 0 and s_ev    >= cap):
            return True

    elif move[Move.TARGET] in TARGET_OPP_SIDE:  # your already-extracted set
        s_atk   = user_pok[Pok.ATTACK_STAT_STAGE]
        s_def   = user_pok[Pok.DEFENSE_STAT_STAGE]
        s_spatk = user_pok[Pok.SPECIAL_ATTACK_STAT_STAGE]
        s_spdef = user_pok[Pok.SPECIAL_DEFENSE_STAT_STAGE]
        s_spe   = user_pok[Pok.SPEED_STAT_STAGE]
        s_acc   = user_pok[Pok.ACCURACY_STAT_STAGE]
        s_ev    = user_pok[Pok.EVASION_STAT_STAGE]

        if (b_atk   < 0 and s_atk   == -6) \
        or (b_def   < 0 and s_def   == -6) \
        or (b_spatk < 0 and s_spatk == -6) \
        or (b_spdef < 0 and s_spdef == -6) \
        or (b_spe   < 0 and s_spe   == -6) \
        or (b_acc   < 0 and s_acc   == -6) \
        or (b_ev    < 0 and s_ev    == -6):
            return True

        # Ability immunity checks (HYPER_CUTTER, KEEN_EYE etc.) use local b_* from above
        if b_atk  and ability == AbilityNames.HYPER_CUTTER:  return True
        if b_spe  and ability == AbilityNames.SPEED_BOOST:   return True
        if ability in STAT_AB_IM:                             return True
        if (b_acc or b_ev) and (
            ability == AbilityNames.NO_GUARD
            or ai_pok[Pok.AB_ID] == AbilityNames.NO_GUARD
        ):
            return True
        if b_acc and ai_pok[Pok.AB_ID] == AbilityNames.KEEN_EYE: return True
    return False


def basic_flag(
            move, ability, ai_pok, user_pok, effectiveness,
            weather
    ) -> int:
    """
    Basic Flag, every trainer has this,
    it discourages moves that would have no effect or that would make no sense
    """

    move_category = move[Move.CATEGORY]
    # Check for immunity types
    if move_category != MoveCategory.STATUS and effectiveness == 0:
        return -10
    # Check for abilities
    if ai_pok[Pok.AB_ID] != AbilityNames.MOLD_BREAKER and ability in ABILITY_BASIC_FLAG:
        if basic_ability(move, ability, user_pok, move_category):
            return -10
    if move_category == MoveCategory.STATUS:
        # TODO: Safeguard for all conditions
        if move[Move.STATUS] != 0:
            if basic_move_status(move, ability, user_pok, ai_pok, weather):
                return -10
        if move[Move.VOL_STATUS] != 0:
            vol_status = basic_move_vol_status(move, ability, user_pok, ai_pok)
            if vol_status:
                return vol_status
        boost_slice = move[Move.BOOST_ATK: Move.BOOST_EV + 1]
        if boost_slice.any():
            if basic_stat_change(move, ability, user_pok, ai_pok):
                return -10

    '''
    TODO:
    Captivate
    Worry Seed (need to implement if know about Snore and Sleep Talk)
    Guard Swap
    Power Swap
    Copycat
    Metal Burst
    Acupressure
    Tickle
    Refresh
    Trick / Switcheroo / Knock Off
    Helping Hand
    Baton Pass
    Curse
    Snore / Sleep Talk
    Leech Seed
    Substitute
    Belly Drum
    Dream Eater
    Explosion / Selfdestruct
    Stat Stage Resetting/Copying/Swapping Moves
    Nightmare,
    Reflect / Light Screen / Mist / Safeguard,
    Focus Energy / Ingrain / Mud Sport / Water Sport / Camouflage / Power Trick / Lucky Chant / Aqua Ring / Magnet Rise
    Disable / Encore
    Lock On / Mean Look / Foresight / Perish Song / Torment / Miracle Eye / Heal Block / Gastro Acid
    Hazard-Setting Moves (Spikes, Toxic Spikes, Stealth Rock)
    Weather-Setting Moves (Sandstorm, Rain Dance, Sunny Day, Hail)
    Future Sight / Doom Desire
    Fake Out
    Stockpile
    Spit UP / Swallow
    Memento
    Imprison
    Cosmic Power / Bulk Up / Calm Mind / Dragon Dance
    Gravity / Tailwind
    Trick Room
    Healing Wish / Lunar Dance
    Natural Gift
    Embargo
    Fling
    Psycho Shift
    Last Resort
    Defog
    # Moves Which Force Switches
    if (
        move[Move.FORCE_SWITCH]
        and (
            count_party(user_party_alive) > 1
            or (
                ability == AbilityNames.SUCTION_CUPS
                and ai_pok[Pok.AB_ID] == AbilityNames.MOLD_BREAKER
            )
        )
    ):
        return -10
    # Recovery Moves
    if move[Flags.HEAL] and ai_pok[Pok.CURRENT_HP] == ai_pok[Pok.MAX_HP]:
        return -10
    # OH-KO
    if (
        move[Move.OH_KO]
        and (
            user_pok[Pok.LEVEL] > ai_pok[Pok.LEVEL]
            or (
                ability == AbilityNames.STURDY and ai_pok[Pok.AB_ID] == AbilityNames.MOLD_BREAKER
            )
        )
    ):
        return -10
    '''

    return 0


def evaluate_attack_flag(
            final_damage, effectiveness, user_pok, move, idx, rand
    ) -> tuple[int, dict]:
    """
    For damage moves it sees if it kill and some move exceptions then add to score
    For non-damaging moves it checks if its 4x effective, for some reason
    """
    score = 0
    move_id = move[Move.ID]
    # Check for kill
    if final_damage >= user_pok[Pok.CURRENT_HP]:
        if (
            move_id
            in SELF_KILL_MOVE
        ):
            score += 0
        elif (
            move_id
            in WEIRD_PRIO_MOVE
        ):
            add_adjustment(rand, idx, 4, 85)
        elif move[Move.PRIORITY] >= 1 and move_id != MoveName.FAKE_OUT:
            score = 6
        else:
            score = 4
        return score, rand

    if (
        move_id in MAYBE_BAD_MOVES
    ):
        add_adjustment(rand, idx, -2, 176)
    if effectiveness >= 4:
        add_adjustment(rand, idx, 2, 176)
    return score, rand


def expert_status(
        move,
        hp_pct_ai,
        hp_pct_u,
        rand,
        ai_pok,
        move_first,
        idx
):
    """
    Expert flag status checks
    """
    m_status = move[Move.STATUS]

    # Burn
    if m_status == Status.BURN:
        return 0, rand

    # Poison, but not badly poison
    if (
        m_status == Status.POISON
        and (hp_pct_ai < 50 or hp_pct_u < 51)
    ):
        return -1, rand

    # Paralyzing-Inducing
    if m_status == Status.PARALYSIS and not move_first:
        add_adjustment(rand, idx, 3, 236)
        return 0, rand

    # TODO: Badly poison
    if m_status == Status.TOXIC:
        return 0, rand

    # Sleep-Inducing
    if (
        m_status == Status.SLEEP
        and (
            ai_pok[Pok.MOVE1_ID] in SLEEP_MOVES
            or ai_pok[Pok.MOVE2_ID] in SLEEP_MOVES
            or ai_pok[Pok.MOVE3_ID] in SLEEP_MOVES
            or ai_pok[Pok.MOVE4_ID] in SLEEP_MOVES
        )
    ):
        add_adjustment(rand, idx, 1, 128)
        return 0, rand

    raise ValueError("Expert Status is receiving a improper status condition")


def expert_vol_status(move, ai_pok, u_pok, turn, rand, idx, hp_pct_u):
    """
    Expert flag volatile status checks
    """
    # Confusion-Inducing
    if move[Move.VOL_STATUS] == VolStatus.CONFUSION:
        score = 0
        if move[Move.ID] == MoveName.SWAGGER:
            psych_up = False
            if (
                ai_pok[Pok.MOVE1_ID] == MoveName.PSYCH_UP  #pylint: disable=R1714
                or ai_pok[Pok.MOVE2_ID] == MoveName.PSYCH_UP
                or ai_pok[Pok.MOVE3_ID] == MoveName.PSYCH_UP
                or ai_pok[Pok.MOVE4_ID] == MoveName.PSYCH_UP
            ):
                psych_up = True
            if psych_up:
                if u_pok[Pok.ATTACK_STAT_STAGE] <= -3:
                    if turn == 1:
                        score += 5
                    else:
                        score += 3
                else:
                    score += -5
                return score, rand
        if move[Move.ID] in CONFUSE_SPECIAL_CASES:
            add_adjustment(rand, idx, 1, 128)
        if hp_pct_u <= 70:
            add_adjustment(rand, idx, -1, 128)
            if hp_pct_u < 31:
                score += -1
            if hp_pct_u < 51:
                score += -1
        return score, rand
    raise ValueError("Need implementation")


def expert_stat(
        move, ai_pok, rand, idx, hp_pct_ai,
        move_first, u_pok, hp_pct_u
):
    """
    Moves that changes stat
    """
    move_target = move[Move.TARGET]
    # Stat-Boosting moves
    if move_target in TARGET_SELF_SIDE:
        if move[Move.BOOST_DEF]:
            if ai_pok[Pok.DEFENSE_STAT_STAGE]>= 3:
                add_adjustment(rand, idx, -1, 156)
            elif hp_pct_ai == 100:
                add_adjustment(rand, idx, 2, 128)
            if hp_pct_ai>69:
                if random.getrandbits(8) < 200:
                    return 0, rand
            if hp_pct_ai < 40:
                return -2, rand
            # TODO: If the last move used by the foe was nondamaging,
            # or the foe has not yet used a move
            # TODO: If the last move used by the foe was special
            add_adjustment(rand, idx, -2, 150)
            return 0, rand

        if move[Move.BOOST_SPDEF]:
            if ai_pok[Pok.SPECIAL_DEFENSE_STAT_STAGE]>= 3:
                add_adjustment(rand, idx, -1, 156)
            elif hp_pct_ai == 100:
                add_adjustment(rand, idx, 2, 128)
            if hp_pct_ai>69:
                if random.getrandbits(8) < 200:
                    return 0, rand
            if hp_pct_ai < 40:
                return -2, rand
            # TODO: If the last move used by the foe was nondamaging,
            # or the foe has not yet used a move
            # TODO: If the last move used by the foe was physical
            add_adjustment(rand, idx, -2, 150)
            return 0, rand

        if move[Move.BOOST_ATK] and move[Move.ID] != MoveName.DRAGON_DANCE:
            if ai_pok[Pok.ATTACK_STAT_STAGE]>= 3:
                add_adjustment(rand, idx, -1, 156)
            if hp_pct_ai == 100:
                add_adjustment(rand, idx, 2, 128)
            if 39<hp_pct_ai<71:
                add_adjustment(rand, idx, -2, 216)
                return 0, rand
            if hp_pct_ai < 40:
                return -2, rand
            return 0, rand

        if move[Move.BOOST_SPATK]:
            if ai_pok[Pok.SPECIAL_ATTACK_STAT_STAGE]>= 3:
                add_adjustment(rand, idx, -1, 156)
            if hp_pct_ai == 100:
                add_adjustment(rand, idx, 2, 128)
            if 39<hp_pct_ai<71:
                add_adjustment(rand, idx, -2, 186)
                return 0, rand
            if hp_pct_ai < 40:
                return -2, rand
            return 0, rand

        if move[Move.BOOST_SPEED] and move[Move.ID] != MoveName.DRAGON_DANCE:
            if move_first:
                return -3, rand
            add_adjustment(rand, idx, 3, 186)
            return 0, rand

        if move[Move.BOOST_EV]:
            # TODO: Ingrain, Aqua Ring
            ai_ev_stage = ai_pok[Pok.EVASION_STAT_STAGE]
            if hp_pct_ai > 89:
                add_adjustment(rand, idx, 3, 156)
            if ai_ev_stage >= 3:
                add_adjustment(rand, idx, -1, 128)
            if u_pok[Pok.STATUS] == Status.TOXIC:
                if hp_pct_ai > 50:
                    add_adjustment(rand, idx, 3, 206)
                else:
                    add_adjustment(rand, idx, 3, 142)
            u_pok_vol_stat = u_pok[Pok.VOL_STATUS]
            if u_pok_vol_stat & VolStatus.LEECH_SEED:
                add_adjustment(rand, idx, 3, 186)
            if u_pok_vol_stat & VolStatus.CURSE:
                add_adjustment(rand, idx, 3, 186)
            if hp_pct_ai > 70 or ai_ev_stage == 0:
                return 0, rand
            if hp_pct_ai < 40 or hp_pct_u < 40:
                return -2, rand
            add_adjustment(rand, idx, -2, 186)
            return 0, rand
        raise ValueError("Target self missing something")

    if move_target in TARGET_OPP_SIDE:
        if move[Move.BOOST_ATK]:
            score = 0
            atk_stage = u_pok[Pok.ATTACK_STAT_STAGE]
            if atk_stage!= 0:
                score += -1
                if hp_pct_ai < 91:
                    score += -1
            if atk_stage <= -3:
                add_adjustment(rand, idx, -2, 206)
            if hp_pct_u < 71:
                score += -2
            # TODO: Last move check:
            # If the move last used by the target was special
            return score, rand

        # No moves that are status and also reduce SP.Atk

        if move[Move.BOOST_DEF]:
            score = 0
            if hp_pct_ai < 70 or ai_pok[Pok.DEFENSE_STAT_STAGE] <= -3:
                add_adjustment(rand, idx, -2, 206)
            if hp_pct_u < 71:
                score += -2
            return score, rand

        if move[Move.BOOST_SPDEF]:
            score = 0
            if hp_pct_ai < 70 or ai_pok[Pok.SPECIAL_DEFENSE_STAT_STAGE] <= -3:
                add_adjustment(rand, idx, -2, 206)
            if hp_pct_u < 71:
                score += -2
            return score, rand

        if move[Move.BOOST_SPEED]:
            if move_first:
                return -3, rand
            add_adjustment(rand, idx, 2, 186)
            return 0, rand

        if move[Move.BOOST_ACC]:
            if hp_pct_ai < 70 or hp_pct_u < 71:
                add_adjustment(rand, idx, -1, 156)
            if ai_pok[Pok.ACCURACY_STAT_STAGE] <= -2:
                add_adjustment(rand, idx, -2, 176)
            if u_pok[Pok.STATUS] == Status.TOXIC:
                add_adjustment(rand, idx, 2, 186)
            if u_pok[Pok.VOL_STATUS] & VolStatus.LEECH_SEED:
                add_adjustment(rand, idx, 2, 186)
            if u_pok[Pok.VOL_STATUS] & VolStatus.CURSE:
                add_adjustment(rand, idx, 2, 186)
            if hp_pct_ai >= 70 or ai_pok[Pok.ACCURACY_STAT_STAGE] == 0:
                return 0, rand
            if hp_pct_ai < 40 or hp_pct_u < 40:
                return -2, rand
            add_adjustment(rand, idx, -2, 186)
            return 0, rand
            # TODO: Ingrain, Aqua Ring

        if move[Move.BOOST_EV]:
            score = 0
            if hp_pct_ai < 70 or u_pok.stat_stages['Evasion'] <= -3:
                add_adjustment(rand, idx, -2, 206)
            if hp_pct_u < 71:
                score += -2
            return score, rand
        raise ValueError("Target enemy missing something")
    raise ValueError("Target no accounted for")


def expert_flag(ai_pok, u_pok, move, turn, idx, rand, weather):
    """
    It shows the incentives and disincentives for the best trainer ai out there,
    for ROM HACKS every trainer has it
    """

    if move[Move.CATEGORY] == MoveCategory.STATUS:
        hp_pct_ai = (ai_pok[Pok.CURRENT_HP]*100) // ai_pok[Pok.MAX_HP]
        hp_pct_u = (u_pok[Pok.CURRENT_HP]*100) // u_pok[Pok.MAX_HP]
        # Check if move first (TODO add Trick room logic here)
        ai_s, u_s = check_speed(ai_pok, u_pok, weather)
        if ai_s > u_s:
            move_first = True
        elif ai_s == u_s:
            move_first = random.getrandbits(1)
        else:
            move_first = False

        if move[Move.STATUS] != 0:
            return expert_status(
                move, hp_pct_ai, hp_pct_u, rand,
                ai_pok, move_first, idx
            )
        if move[Move.VOL_STATUS]:
            return expert_vol_status(
                move, ai_pok, u_pok, turn,
                rand, idx, hp_pct_u
            )
        boost_slice = move[Move.BOOST_ATK: Move.BOOST_EV + 1]
        if boost_slice.any():
            return expert_stat(
                move, ai_pok, rand, idx, hp_pct_ai,
                move_first, u_pok, hp_pct_u
            )

    # Moves Ignoring Accuracy (e.g. Aerial Ace, Shock Wave)
    if move[Move.ACCURACY] == -1:  # -1 is how always hit moves is represented
        score = 0
        ai_acc = ai_pok[Pok.ACCURACY_STAT_STAGE]
        u_ev   = u_pok[Pok.EVASION_STAT_STAGE]
        if ai_acc <= -5 or u_ev >= 5:
            score += 1
        if ai_acc <= -3 or u_ev >= 3:
            add_adjustment(rand, idx, 1, 156)
        return score, rand


    """
    TODO:
        Draining Attacks
        Mirror Move
        Selfdestruct, explosion, memento
        Healing Wish, Lunar Dance
        Dragon Dance
        Acupressure

    """
    return 0, rand
