"""
Helper to make the trainer ai more readable and everything more organized
"""
import random
import numpy as np
from numba import njit
from Utils.loader import TYPE_CHART
from Utils.helper import get_type_effectiveness
from DataBase.PkDB import POKEMON_ABILITY_POOL, POKEMON_LENGTH
from DataBase.MoveDB import PHYSICAL, SPECIAL, FIRE_MOVES, WATER_MOVES, ELECTRIC_MOVES
from DataBase.AbilitiesDB import AbilityNames
from DataBase.loader import abDB
from Engine.engine_helper import check_speed
from Models.idx_const import POK_LEN
from Models.helper import TARGET_SELF_SIDE, TARGET_OPP_SIDE, STEEL_POISON
from Models.constants import (
    _ABILITYNAMES_VOLT_ABSORB, _ABILITYNAMES_MOTOR_DRIVE, _ABILITYNAMES_IMMUNITY,
    _ABILITYNAMES_MAGIC_GUARD, _ABILITYNAMES_POISON_POINT, _ABILITYNAMES_LIMBER,
    _ABILITYNAMES_WATER_VEIL, _ABILITYNAMES_CLEAR_BODY, _ABILITYNAMES_WHITE_SMOKE,
    _ABILITYNAMES_WATER_ABSORB, _ABILITYNAMES_FLASH_FIRE, _ABILITYNAMES_LEVITATE,
    _ABILITYNAMES_SOUNDPROOF, _ABILITYNAMES_WONDER_GUARD,
    _MOVENAME_EXPLOSION, _MOVE_SELFDESTRUCT, _MOVENAME_SUCKER_PUNCH, _MOVENAME_FOCUS_PUNCH,
    _MOVENAME_FUTURE_SIGHT, _MOVENAME_DREAM_EATER, _MOVENAME_NIGHTMARE, _MOVENAME_SWAGGER,
    _MOVENAME_FLATTER, _ABILITYNAMES_VITAL_SPIRIT, _ABILITYNAMES_LEAF_GUARD,
    _ABILITYNAMES_HYDRATION, _ABILITYNAMES_OWN_TEMPO, _ABILITYNAMES_OBLIVIOUS,
    _ABILITYNAMES_SUCTION_CUPS, _ABILITYNAMES_STURDY, _ABILITYNAMES_HYPER_CUTTER,
    _ABILITYNAMES_SPEED_BOOST, _ABILITYNAMES_NO_GUARD, _ABILITYNAMES_KEEN_EYE,
    _ABILITYNAMES_SIMPLE, _MOVE_TYPE, _MOVE_CATEGORY,_POK_TYPE1, _POK_TYPE2, _POK_AB_ID,
    _ABILITYNAMES_ADAPTABILITY, _MOVECATEGORY_STATUS, _TYPES_ELECTRIC, _TYPES_WATER,
    _TYPES_FIRE, _TYPES_GROUND, _FLAGS_SOUND, _MOVE_STATUS, _POK_STATUS, _STATUS_SLEEP,
    _STATUS_POISON, _STATUS_TOXIC, _WEATHER_SUN, _WEATHER_RAIN, _STATUS_PARALYSIS,
    _ABILITYNAMES_MOLD_BREAKER, _STATUS_BURN, _MOVE_VOL_STATUS, _POK_VOL_STATUS,
    _VOLSTATUS_CONFUSION, _VOLSTATUS_ATTRACT, _POK_GENDER, _GENDER_GENDERLESS,
    _MOVE_BOOST_ATK, _MOVE_BOOST_DEF, _MOVE_BOOST_SPATK,_MOVE_BOOST_SPDEF, _MOVE_BOOST_SPEED,
    _MOVE_BOOST_ACC, _MOVE_BOOST_EV, _MOVE_TARGET, _POK_ATTACK_STAT_STAGE, _POK_DEFENSE_STAT_STAGE,
    _POK_SPECIAL_ATTACK_STAT_STAGE, _POK_SPECIAL_DEFENSE_STAT_STAGE, _POK_SPEED_STAT_STAGE,
    _POK_ACCURACY_STAT_STAGE, _POK_EVASION_STAT_STAGE, _MOVE_ID, _POK_CURRENT_HP,
    _MOVE_PRIORITY, _MOVENAME_FAKE_OUT, _POK_MOVE1_ID, _POK_MOVE2_ID, _POK_MOVE3_ID,
    _POK_MOVE4_ID, _MOVENAME_PSYCH_UP, _MOVENAME_DRAGON_DANCE, _VOLSTATUS_LEECH_SEED,
    _VOLSTATUS_CURSE, _POK_MAX_HP, _MOVE_ACCURACY, _POK_ITEM_ID, _MOVE_DRAIN, _MOVENAME_BIDE,
    _MOVENAME_BRICK_BREAK, _MOVENAME_BUG_BITE, _POK_TURNS
)



ELEC_AB_IM = (_ABILITYNAMES_VOLT_ABSORB, _ABILITYNAMES_MOTOR_DRIVE)
POISON_AB_IM = (_ABILITYNAMES_IMMUNITY, _ABILITYNAMES_MAGIC_GUARD, _ABILITYNAMES_POISON_POINT)
PARA_AB_IM = (_ABILITYNAMES_LIMBER, _ABILITYNAMES_MAGIC_GUARD)
BURN_AB_IM = (_ABILITYNAMES_WATER_VEIL, _ABILITYNAMES_MAGIC_GUARD)
STAT_AB_IM = (_ABILITYNAMES_CLEAR_BODY, _ABILITYNAMES_WHITE_SMOKE)
ABILITY_BASIC_FLAG = (
    _ABILITYNAMES_VOLT_ABSORB, _ABILITYNAMES_MOTOR_DRIVE, _ABILITYNAMES_WATER_ABSORB,
    _ABILITYNAMES_FLASH_FIRE, _ABILITYNAMES_LEVITATE, _ABILITYNAMES_SOUNDPROOF,
    _ABILITYNAMES_WONDER_GUARD
)
ABSORB_ABI = (
    _ABILITYNAMES_WATER_ABSORB, _ABILITYNAMES_VOLT_ABSORB, _ABILITYNAMES_FLASH_FIRE
)

SELF_KILL_MOVE = (_MOVENAME_EXPLOSION, _MOVE_SELFDESTRUCT)
WEIRD_PRIO_MOVE = (_MOVENAME_SUCKER_PUNCH, _MOVENAME_FOCUS_PUNCH, _MOVENAME_FUTURE_SIGHT)
MAYBE_BAD_MOVES = (
    _MOVENAME_SUCKER_PUNCH,
    _MOVENAME_FOCUS_PUNCH,
    _MOVENAME_EXPLOSION,
    _MOVE_SELFDESTRUCT
)
SLEEP_MOVES = (_MOVENAME_DREAM_EATER, _MOVENAME_NIGHTMARE)
CONFUSE_SPECIAL_CASES = (_MOVENAME_SWAGGER, _MOVENAME_FLATTER)

# --- Abilities explicitly checked in basic_flag / expert_flag ---
_EXPLICIT_RELEVANT: set = {
    _ABILITYNAMES_VOLT_ABSORB,
    _ABILITYNAMES_MOTOR_DRIVE,
    _ABILITYNAMES_WATER_ABSORB,
    _ABILITYNAMES_FLASH_FIRE,
    _ABILITYNAMES_LEVITATE,
    _ABILITYNAMES_SOUNDPROOF,
    _ABILITYNAMES_WONDER_GUARD,
    _ABILITYNAMES_VITAL_SPIRIT,
    _ABILITYNAMES_IMMUNITY,
    _ABILITYNAMES_MAGIC_GUARD,
    _ABILITYNAMES_POISON_POINT,
    _ABILITYNAMES_LEAF_GUARD,
    _ABILITYNAMES_HYDRATION,
    _ABILITYNAMES_LIMBER,
    _ABILITYNAMES_WATER_VEIL,
    _ABILITYNAMES_CLEAR_BODY,
    _ABILITYNAMES_WHITE_SMOKE,
    _ABILITYNAMES_OWN_TEMPO,
    _ABILITYNAMES_OBLIVIOUS,
    _ABILITYNAMES_SUCTION_CUPS,
    _ABILITYNAMES_STURDY,
    _ABILITYNAMES_HYPER_CUTTER,
    _ABILITYNAMES_SPEED_BOOST,
    _ABILITYNAMES_NO_GUARD,
    _ABILITYNAMES_KEEN_EYE,
    _ABILITYNAMES_SIMPLE,
}

_DAMAGE_RELEVANT_WHEN = {"on_try_move"}

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
            pass

# Final constant - this is what Numba sees, and it's a tuple
RELEVANT_ABILITIES: tuple = tuple(_EXPLICIT_RELEVANT | _activation_relevant)


# --- Pre-compute per pokemon whether ANY of its pool abilities are relevant ---
POKEMON_HAS_RELEVANT_ABILITY = np.zeros(POKEMON_LENGTH + 1, dtype=np.bool_)
for pk_id in range(POKEMON_LENGTH + 1):
    for ab_id in POKEMON_ABILITY_POOL[pk_id]:
        if ab_id in RELEVANT_ABILITIES:  # still a set here, build-time only
            POKEMON_HAS_RELEVANT_ABILITY[pk_id] = True
            break


#--------------Move tuples-----------------------------
EXPERT_SPECIFIC_M = (_MOVENAME_BIDE, _MOVENAME_BRICK_BREAK, _MOVENAME_BUG_BITE)


@njit
def match_2tuple_any(tup1, tup2):
    """check tuples with 2 elements for if any of them is equal"""
    # Check first element against both
    if tup1[0] == tup2[0] or tup1[0] == tup2[1]:
        return True
    # Check second element against both
    if tup1[1] == tup2[0] or tup1[1] == tup2[1]:
        return True
    return False



@njit
def add_adjustment(arr, move_id, delta, chance):
    """Add a [delta, chance] pair to the first free slot (slot is free when chance == 0)."""
    for i in range(5):
        if arr[move_id, i, 1] == 0:   # chance == 0 means slot unused
            arr[move_id, i, 0] = delta
            arr[move_id, i, 1] = chance
            return
    raise ValueError("Insufficient slots in rand")


@njit
def trainer_ai_effectiveness(move, ai_pok, user_pok):
    """
    How the AI consider type effectivness, which has some differences from
    how it usually goes
    """


    """If the user has the ability Normalize, the move's type is changed to Normal.
    Otherwise, if the move is Natural Gift, Hidden Power, Judgment, or Weather Ball,
    the move is adjusted to its correct type."""
    effectiveness = 1.0
    move_type = move[_MOVE_TYPE]
    move_cat = move[_MOVE_CATEGORY]
    ai_type1 = ai_pok[_POK_TYPE1]
    ai_type2 = ai_pok[_POK_TYPE2]
    ai_ability = ai_pok[_POK_AB_ID]
    user_type1 = user_pok[_POK_TYPE1]
    user_type2 = user_pok[_POK_TYPE2]

    # STAB
    if move_type == ai_type1 or move_type == ai_type2:  # pylint: disable=consider-using-in
        effectiveness *= 1.5 if ai_ability != _ABILITYNAMES_ADAPTABILITY else 2

    # Common type effectiveness
    # TODO: Scrappy, Mold Breaker, Odor Sleuth, Foresight,
    # Gastro Acid, Miracle Eye, Iron Ball
    # Gravity, Magnet Rise, Levitate, Wonder Guard, more...
    s_e = False
    ef_t1 = TYPE_CHART[(move_type*19)+user_type1] / 2
    effectiveness *= ef_t1
    if user_type2:
        ef_t2 = TYPE_CHART[(move_type*19)+user_type2] / 4
        effectiveness *= ef_t2
        if ef_t1*ef_t2 >= 2:
            s_e = True
    elif ef_t1 == 2:
        s_e = True


    if move_cat != _MOVECATEGORY_STATUS:
        # TODO: Tinted Lens, Filter/Solid Rock, Expert Belt
        pass



    # Correct for the right effectiveness
    if effectiveness == 0.375:
        effectiveness = 0.25
    elif effectiveness == 0.75:
        effectiveness = 0.5
    elif effectiveness == 3.0:
        effectiveness = 2.0
    elif effectiveness == 6.0:
        effectiveness = 4.0

    return effectiveness, s_e


@njit
def basic_ability(move, ability, user_pok, move_category) -> bool:
    """
    Checks to see if ability triggers on basic flag
    """
    move_type = move[_MOVE_TYPE]
    if move_type == _TYPES_ELECTRIC and ability in ELEC_AB_IM:
        return True
    if move_type == _TYPES_WATER and ability == _ABILITYNAMES_WATER_ABSORB:
        return True
    if move_type == _TYPES_FIRE and ability == _ABILITYNAMES_FLASH_FIRE:
        return True
    if move_type == _TYPES_GROUND and ability == _ABILITYNAMES_LEVITATE:
        return True
    if move[_FLAGS_SOUND] and ability == _ABILITYNAMES_SOUNDPROOF:
        return True
    if ability == _ABILITYNAMES_WONDER_GUARD and move_category != _MOVECATEGORY_STATUS:
        eff, den = get_type_effectiveness(move_type, user_pok[_POK_TYPE1], user_pok[_POK_TYPE2])
        if eff // den >= 2:
            return True
    return False


@njit
def basic_move_status(move, ability, user_pok, ai_pok, weather):
    """
    Checks to see if any of the conditions for move status being irrelevant comes back as true
    """
    # TODO: Safeguard
    u_type12 = (user_pok[_POK_TYPE1],user_pok[_POK_TYPE2])
    move_status = move[_MOVE_STATUS]
    user_status = user_pok[_POK_STATUS] != 0

    if user_status:
        return True

    # Sleep
    if (
        move_status == _STATUS_SLEEP
        and ability == _ABILITYNAMES_VITAL_SPIRIT
    ):
        return True

    # Poison
    if (
        move_status in (_STATUS_POISON, _STATUS_TOXIC)
    ):
        if not match_2tuple_any(STEEL_POISON, u_type12):
            return True
        if ability in POISON_AB_IM:
            return True
        if weather:
            if (
                weather == _WEATHER_SUN
                and ability == _ABILITYNAMES_LEAF_GUARD
            ):
                return True
            if (
                weather == _WEATHER_RAIN
                and ability == _ABILITYNAMES_HYDRATION
            ):
                return True

    # Paralysis
    if move_status == _STATUS_PARALYSIS:
        has_para_immunity = ability in PARA_AB_IM
        # Electric-specific immunities
        is_electric_fail = False
        if move[_MOVE_TYPE] == _TYPES_ELECTRIC:
            is_ground = _TYPES_GROUND in u_type12
            is_elec_immune_ability = (
                ability in ELEC_AB_IM
                and ai_pok[_POK_AB_ID] != _ABILITYNAMES_MOLD_BREAKER
            )
            is_electric_fail = is_ground or is_elec_immune_ability

        if has_para_immunity or is_electric_fail:
            return True

    # Burn
    if (
        move_status == _STATUS_BURN
        and (
            ability in BURN_AB_IM
            or _TYPES_FIRE in u_type12
        )
    ):
        return True

    return False


@njit
def basic_move_vol_status(move, ability, user_pok, ai_pok):
    """
    Checks to see if any of the conditions for a move that has volatile status
    is irrelevant
    """
    # TODO: Every volatile status
    vol_status = move[_MOVE_VOL_STATUS]
    user_vol_status = user_pok[_POK_VOL_STATUS]

    if vol_status == _VOLSTATUS_CONFUSION:
        # TODO: Safeguard
        if user_vol_status & _VOLSTATUS_CONFUSION:
            return -5
        if ability == _ABILITYNAMES_OWN_TEMPO:
            return -10
    # Attract
    elif vol_status == _VOLSTATUS_ATTRACT:
        if (
            user_vol_status & _VOLSTATUS_ATTRACT
            or ability == _ABILITYNAMES_OBLIVIOUS
            or (
                user_pok[_POK_GENDER] == ai_pok[_POK_GENDER]
                or user_pok[_POK_GENDER] == _GENDER_GENDERLESS
            )
        ):
            return -10

    return 0


@njit
def basic_stat_change(move, ability, user_pok, ai_pok) -> bool:
    """
    Checks to see if any of the bad uses for a buff or debuff stat move
    happens and returns the check if the do
    """
    # TODO: Trick room
    b_atk   = move[_MOVE_BOOST_ATK]
    b_def   = move[_MOVE_BOOST_DEF]
    b_spatk = move[_MOVE_BOOST_SPATK]
    b_spdef = move[_MOVE_BOOST_SPDEF]
    b_spe   = move[_MOVE_BOOST_SPEED]
    b_acc   = move[_MOVE_BOOST_ACC]
    b_ev    = move[_MOVE_BOOST_EV]
    if move[_MOVE_TARGET] in TARGET_SELF_SIDE:
        s_atk   = ai_pok[_POK_ATTACK_STAT_STAGE]
        s_def   = ai_pok[_POK_DEFENSE_STAT_STAGE]
        s_spatk = ai_pok[_POK_SPECIAL_ATTACK_STAT_STAGE]
        s_spdef = ai_pok[_POK_SPECIAL_DEFENSE_STAT_STAGE]
        s_spe   = ai_pok[_POK_SPEED_STAT_STAGE]
        s_acc   = ai_pok[_POK_ACCURACY_STAT_STAGE]
        s_ev    = ai_pok[_POK_EVASION_STAT_STAGE]

        # Unify Simple (cap=3) and normal (cap=6) into one threshold
        cap = 3 if ai_pok[_POK_AB_ID] == _ABILITYNAMES_SIMPLE else 6

        if (b_atk   > 0 and s_atk   >= cap) \
        or (b_def   > 0 and s_def   >= cap) \
        or (b_spatk > 0 and s_spatk >= cap) \
        or (b_spdef > 0 and s_spdef >= cap) \
        or (b_spe   > 0 and s_spe   >= cap) \
        or (b_acc   > 0 and s_acc   >= cap) \
        or (b_ev    > 0 and s_ev    >= cap):
            return True

    elif move[_MOVE_TARGET] in TARGET_OPP_SIDE:  # your already-extracted set
        s_atk   = user_pok[_POK_ATTACK_STAT_STAGE]
        s_def   = user_pok[_POK_DEFENSE_STAT_STAGE]
        s_spatk = user_pok[_POK_SPECIAL_ATTACK_STAT_STAGE]
        s_spdef = user_pok[_POK_SPECIAL_DEFENSE_STAT_STAGE]
        s_spe   = user_pok[_POK_SPEED_STAT_STAGE]
        s_acc   = user_pok[_POK_ACCURACY_STAT_STAGE]
        s_ev    = user_pok[_POK_EVASION_STAT_STAGE]

        if (b_atk   < 0 and s_atk   == -6) \
        or (b_def   < 0 and s_def   == -6) \
        or (b_spatk < 0 and s_spatk == -6) \
        or (b_spdef < 0 and s_spdef == -6) \
        or (b_spe   < 0 and s_spe   == -6) \
        or (b_acc   < 0 and s_acc   == -6) \
        or (b_ev    < 0 and s_ev    == -6):
            return True

        # Ability immunity checks (HYPER_CUTTER, KEEN_EYE etc.) use local b_* from above
        # TODO: Clear Body, White smoke
        if b_atk  and ability == _ABILITYNAMES_HYPER_CUTTER:  return True
        if b_spe  and ability == _ABILITYNAMES_SPEED_BOOST:   return True
        if ability in STAT_AB_IM:                            return True
        if (b_acc or b_ev) and (
            ability == _ABILITYNAMES_NO_GUARD
            or ai_pok[_POK_AB_ID] == _ABILITYNAMES_NO_GUARD
        ):
            return True
        if b_acc and ai_pok[_POK_AB_ID] == _ABILITYNAMES_KEEN_EYE: return True
    return False


@njit
def basic_flag(
            move, ability, ai_pok, user_pok, effectiveness,
            weather
    ):
    """
    Basic Flag, every trainer has this,
    it discourages moves that would have no effect or that would make no sense
    """

    move_category = move[_MOVE_CATEGORY]
    # Check for immunity types
    if move_category != _MOVECATEGORY_STATUS and effectiveness == 0:
        return -10
    # Check for abilities
    if ai_pok[_POK_AB_ID] != _ABILITYNAMES_MOLD_BREAKER and ability in ABILITY_BASIC_FLAG:
        if basic_ability(move, ability, user_pok, move_category):
            return -10
    if move_category == _MOVECATEGORY_STATUS:
        # TODO: Safeguard for all conditions
        if move[_MOVE_STATUS] != 0:
            if basic_move_status(move, ability, user_pok, ai_pok, weather):
                return -10
        if move[_MOVE_VOL_STATUS] != 0:
            vol_status = basic_move_vol_status(move, ability, user_pok, ai_pok)
            if vol_status:
                return vol_status
        if (
            move[_MOVE_BOOST_ATK]
            or move[_MOVE_BOOST_DEF]
            or move[_MOVE_BOOST_SPATK]
            or move[_MOVE_BOOST_SPDEF]
            or move[_MOVE_BOOST_SPEED]
            or move[_MOVE_BOOST_ACC]
            or move[_MOVE_BOOST_EV]
        ):
            if basic_stat_change(move, ability, user_pok, ai_pok):
                return -10

    '''
    TODO:
    --------------Specific Moves---------------
    Selfdestruct/Explosion
    Nightmare
    Dream Eater
    Belly Drum
    Reflect / Light Screen / Mist / Safeguard
    Focus Energy / Ingrain / Mud Sport / Water Sport / Camouflage / Power Trick / Lucky Chant / Aqua Ring / Magnet Rise
    Substitute
    Leech Seed
    Disable / Encore
    Snore / Sleep Talk
    Lock On / Mean Look / Foresight / Perish Song / Torment / Miracle Eye / Heal Block / Gastro Acid
    Curse
    Future Sight / Doom Desire
    Baton Pass
    Fake Out
    Stockpile
    Spit Up / Swallow
    Memento
    Helping Hand
    Trick / Switcheroo / Knock Off
    Imprison
    Refresh
    Tickle
    Cosmic Power / Bulk Up / Calm Mind / Dragon Dance
    Gravity / Tailwind
    Trick Room
    Healing Wish / Lunar Dance
    Natural Gift
    Acupressure
    Metal Burst
    Embargo
    Fling
    Psycho Shift
    Copycat
    Power Swap / Guard Swap
    Last Resort
    Worry Seed
    Defog
    Captivate
    --------------Effect Moves-----------------
    Stat Stage Resetting/Copying/Swapping Moves(Example: Haze, Psych Up, Heart Swap)
    Non-Standard Damage and Charge Turn Moves(
    Charge Turn Moves:
        -Razor Wind
        -Sky Attack
        -Blast Burn
        -Frenzy Plant
        -Giga Impact
        -Hydro Cannon
        -Hyper Beam
        -Roar of Time
        -Rock Wrecker
        -Skull Bash
        -Focus Punch
        -Superpower (for some reason)
    Variable Power / Flat Damage Moves:
        -Bide
        -Super Fang
        -Dragon Rage
        -Night Shade
        -Seismic Toss
        -Psywave
        -Counter
        -Flail
        -Reversal
        -Return
        -Present
        -Frustration
        -Sonic Boom
        -Hidden Power
        -Mirror Coat
        -Endeavor
        -Low Kick
        -Grass Knot
        -Gyro Ball
        -Trump Card
        -Crush Grip
        -Wring Out
        -Punishment
        -Magnitude
    )
    Force Switches(Example moves: Roar, Whirlwind)
    Recovery Moves(Example moves: Roost, Synthesis, Recover)
    OHKO Moves(Example moves: Horn Drill, Fissure, Sheer Cold, Guillotine)
    Hazard-Setting Moves (Spikes, Toxic Spikes, Stealth Rock)
    Weather-Setting Moves (Sandstorm, Rain Dance, Sunny Day, Hail)
    '''

    return 0


@njit
def evaluate_attack_flag(
            final_damage, effectiveness, user_pok, move, idx, rand
    ) -> tuple[int, list]:
    """
    For damage moves it sees if it kill and some move exceptions then add to score
    For non-damaging moves it checks if its 4x effective, for some reason
    """
    score = 0
    move_id = move[_MOVE_ID]
    # Check for kill
    if final_damage >= user_pok[_POK_CURRENT_HP]:
        if (
            move_id
            in SELF_KILL_MOVE
        ):
            pass
        elif (
            move_id
            in WEIRD_PRIO_MOVE
        ):
            add_adjustment(rand, idx, 4, 85)
        elif move[_MOVE_PRIORITY] >= 1 and move_id != _MOVENAME_FAKE_OUT:
            score = 6
        else:
            score = 4
        return score

    if (
        move_id in MAYBE_BAD_MOVES
    ):
        add_adjustment(rand, idx, -2, 205)
    if effectiveness >= 4:
        add_adjustment(rand, idx, 2, 176)
    return score

@njit
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
    m_status = move[_MOVE_STATUS]

    # Burn
    if m_status == _STATUS_BURN:
        return 0

    # Poison, but not badly poison
    if (
        m_status == _STATUS_POISON
        and (hp_pct_ai < 50 or hp_pct_u < 51)
    ):
        return -1

    # Paralyzing-Inducing
    if m_status == _STATUS_PARALYSIS and not move_first:
        add_adjustment(rand, idx, 3, 236)
        return 0

    # TODO: Badly poison
    if m_status == _STATUS_TOXIC:
        return 0

    # Sleep-Inducing
    if (
        m_status == _STATUS_SLEEP
        and (
            ai_pok[_POK_MOVE1_ID] in SLEEP_MOVES
            or ai_pok[_POK_MOVE2_ID] in SLEEP_MOVES
            or ai_pok[_POK_MOVE3_ID] in SLEEP_MOVES
            or ai_pok[_POK_MOVE4_ID] in SLEEP_MOVES
        )
    ):
        add_adjustment(rand, idx, 1, 128)
        return 0

    raise ValueError("Expert Status is receiving a improper status condition")


@njit
def expert_vol_status(move, ai_pok, u_pok, turn, rand, idx, hp_pct_u):
    """
    Expert flag volatile status checks
    """
    # Confusion-Inducing
    if move[_MOVE_VOL_STATUS] == _VOLSTATUS_CONFUSION:
        score = 0
        if move[_MOVE_ID] == _MOVENAME_SWAGGER:
            psych_up = False
            if (
                ai_pok[_POK_MOVE1_ID] == _MOVENAME_PSYCH_UP  #pylint: disable=R1714
                or ai_pok[_POK_MOVE2_ID] == _MOVENAME_PSYCH_UP
                or ai_pok[_POK_MOVE3_ID] == _MOVENAME_PSYCH_UP
                or ai_pok[_POK_MOVE4_ID] == _MOVENAME_PSYCH_UP
            ):
                psych_up = True
            if psych_up:
                if u_pok[_POK_ATTACK_STAT_STAGE] <= -3:
                    if turn == 1:
                        score += 5
                    else:
                        score += 3
                else:
                    score += -5
                return score
        if move[_MOVE_ID] in CONFUSE_SPECIAL_CASES:
            add_adjustment(rand, idx, 1, 128)
        if hp_pct_u <= 70:
            add_adjustment(rand, idx, -1, 128)
            if hp_pct_u < 31:
                score += -1
            if hp_pct_u < 51:
                score += -1
        return score
    raise ValueError("Need implementation")


@njit
def expert_stat(
        move, ai_pok, rand, idx, hp_pct_ai,
        move_first, u_pok, hp_pct_u, my_last_move
):
    """
    Moves that changes stat
    """
    move_target = move[_MOVE_TARGET]
    # Stat-Boosting moves
    if move_target in TARGET_SELF_SIDE:
        if move[_MOVE_BOOST_DEF]:
            if ai_pok[_POK_DEFENSE_STAT_STAGE]>= 3:
                add_adjustment(rand, idx, -1, 156)
            elif hp_pct_ai == 100:
                add_adjustment(rand, idx, 2, 128)
            if hp_pct_ai>69:
                if random.getrandbits(8) < 200:
                    return 0
            if hp_pct_ai < 40:
                return -2
            if my_last_move in SPECIAL:
                return -2
            if my_last_move not in PHYSICAL:
                add_adjustment(rand, idx, -2, 196)
                return 0
            add_adjustment(rand, idx, -2, 150)
            return 0

        if move[_MOVE_BOOST_SPDEF]:
            if ai_pok[_POK_SPECIAL_DEFENSE_STAT_STAGE]>= 3:
                add_adjustment(rand, idx, -1, 156)
            elif hp_pct_ai == 100:
                add_adjustment(rand, idx, 2, 128)
            if hp_pct_ai>69:
                if random.getrandbits(8) < 200:
                    return 0
            if hp_pct_ai < 40:
                return -2
            if my_last_move in PHYSICAL:
                return -2
            if my_last_move not in SPECIAL:
                add_adjustment(rand, idx, -2, 196)
                return 0
            add_adjustment(rand, idx, -2, 150)
            return 0

        if move[_MOVE_BOOST_ATK] and move[_MOVE_ID] != _MOVENAME_DRAGON_DANCE:
            if ai_pok[_POK_ATTACK_STAT_STAGE]>= 3:
                add_adjustment(rand, idx, -1, 156)
            if hp_pct_ai == 100:
                add_adjustment(rand, idx, 2, 128)
            if 39<hp_pct_ai<71:
                add_adjustment(rand, idx, -2, 216)
                return 0
            if hp_pct_ai < 40:
                return -2
            return 0

        if move[_MOVE_BOOST_SPATK]:
            if ai_pok[_POK_SPECIAL_ATTACK_STAT_STAGE]>= 3:
                add_adjustment(rand, idx, -1, 156)
            if hp_pct_ai == 100:
                add_adjustment(rand, idx, 2, 128)
            if 39<hp_pct_ai<71:
                add_adjustment(rand, idx, -2, 186)
                return 0
            if hp_pct_ai < 40:
                return -2
            return 0

        if move[_MOVE_BOOST_SPEED] and move[_MOVE_ID] != _MOVENAME_DRAGON_DANCE:
            if move_first:
                return -3
            add_adjustment(rand, idx, 3, 186)
            return 0

        if move[_MOVE_BOOST_EV]:
            # TODO: Ingrain, Aqua Ring
            ai_ev_stage = ai_pok[_POK_EVASION_STAT_STAGE]
            if hp_pct_ai > 89:
                add_adjustment(rand, idx, 3, 156)
            if ai_ev_stage >= 3:
                add_adjustment(rand, idx, -1, 128)
            if u_pok[_POK_STATUS] == _STATUS_TOXIC:
                if hp_pct_ai > 50:
                    add_adjustment(rand, idx, 3, 206)
                else:
                    add_adjustment(rand, idx, 3, 142)
            u_pok_vol_stat = u_pok[_POK_VOL_STATUS]
            if u_pok_vol_stat & _VOLSTATUS_LEECH_SEED:
                add_adjustment(rand, idx, 3, 186)
            if u_pok_vol_stat & _VOLSTATUS_CURSE:
                add_adjustment(rand, idx, 3, 186)
            if hp_pct_ai > 70 or ai_ev_stage == 0:
                return 0
            if hp_pct_ai < 40 or hp_pct_u < 40:
                return -2
            add_adjustment(rand, idx, -2, 186)
            return 0
        raise ValueError("Target self missing something")

    if move_target in TARGET_OPP_SIDE:
        if move[_MOVE_BOOST_ATK]:
            score = 0
            atk_stage = u_pok[_POK_ATTACK_STAT_STAGE]
            if atk_stage!= 0:
                score += -1
                if hp_pct_ai < 91:
                    score += -1
            if atk_stage <= -3:
                add_adjustment(rand, idx, -2, 206)
            if hp_pct_u < 71:
                score += -2
            if my_last_move in SPECIAL:
                add_adjustment(rand, idx, -2, 128)
                return score
            return score

        # No moves that are status and also reduce SP.Atk

        if move[_MOVE_BOOST_DEF]:
            score = 0
            if hp_pct_ai < 70 or u_pok[_POK_DEFENSE_STAT_STAGE] <= -3:
                add_adjustment(rand, idx, -2, 206)
            if hp_pct_u < 71:
                score += -2
            return score

        if move[_MOVE_BOOST_SPDEF]:
            score = 0
            if hp_pct_ai < 70 or ai_pok[_POK_SPECIAL_DEFENSE_STAT_STAGE] <= -3:
                add_adjustment(rand, idx, -2, 206)
            if hp_pct_u < 71:
                score += -2
            return score

        if move[_MOVE_BOOST_SPEED]:
            if move_first:
                return -3
            add_adjustment(rand, idx, 2, 186)
            return 0

        if move[_MOVE_BOOST_ACC]:
            if hp_pct_ai < 70 or hp_pct_u < 71:
                add_adjustment(rand, idx, -1, 156)
            if ai_pok[_POK_ACCURACY_STAT_STAGE] <= -2:
                add_adjustment(rand, idx, -2, 176)
            if u_pok[_POK_STATUS] == _STATUS_TOXIC:
                add_adjustment(rand, idx, 2, 186)
            if u_pok[_POK_VOL_STATUS] & _VOLSTATUS_LEECH_SEED:
                add_adjustment(rand, idx, 2, 186)
            if u_pok[_POK_VOL_STATUS] & _VOLSTATUS_CURSE:
                add_adjustment(rand, idx, 2, 186)
            if hp_pct_ai >= 70 or ai_pok[_POK_ACCURACY_STAT_STAGE] == 0:
                return 0
            if hp_pct_ai < 40 or hp_pct_u < 40:
                return -2
            add_adjustment(rand, idx, -2, 186)
            return 0
            # TODO: Ingrain, Aqua Ring

        if move[_MOVE_BOOST_EV]:
            score = 0
            if hp_pct_ai < 70 or u_pok[_POK_EVASION_STAT_STAGE] <= -3:
                add_adjustment(rand, idx, -2, 206)
            if hp_pct_u < 71:
                score += -2
            return score
        raise ValueError("Target enemy missing something")
    raise ValueError("Target no accounted for")


@njit
def expert_moves(move, ai_pok, effectiveness, rand, idx):
    """
    Expert moves that have specific logic
    """
    score = 0
    hp_pct = (ai_pok[_POK_CURRENT_HP]*100)//ai_pok[_POK_MAX_HP]
    m_id = move[_MOVE_ID]
    if m_id == _MOVENAME_BIDE:
        if hp_pct < 91:
            score += -2
    elif m_id == _MOVENAME_BUG_BITE:
        if effectiveness == 0.5 or effectiveness == 0.25 or effectiveness == 0:
            score += -1
        else:
            if ai_pok[_POK_TURNS] == 1:
                add_adjustment(rand, idx, 1, 192)
            add_adjustment(rand, idx, 1, 128)

    return score


@njit
def expert_flag(ai_pok, u_pok, move, turn, idx, rand, weather, my_last_move, effectiveness):
    """
    It shows the incentives and disincentives for the best trainer ai out there,
    for ROM HACKS every trainer has it
    """
    if move[_MOVE_ID] in EXPERT_SPECIFIC_M:
        return expert_moves(move, ai_pok, effectiveness, rand, idx)
    if move[_MOVE_CATEGORY] == _MOVECATEGORY_STATUS:
        hp_pct_ai = (ai_pok[_POK_CURRENT_HP]*100) // ai_pok[_POK_MAX_HP]
        hp_pct_u = (u_pok[_POK_CURRENT_HP]*100) // u_pok[_POK_MAX_HP]
        # Check if move first (TODO add Trick room logic here)
        ai_s, u_s = check_speed(ai_pok, u_pok, weather)
        if ai_s > u_s:
            move_first = True
        elif ai_s == u_s:
            move_first = random.getrandbits(1)
        else:
            move_first = False

        if move[_MOVE_STATUS] != 0:
            return expert_status(
                move, hp_pct_ai, hp_pct_u, rand,
                ai_pok, move_first, idx
            )
        if move[_MOVE_VOL_STATUS]:
            return expert_vol_status(
                move, ai_pok, u_pok, turn,
                rand, idx, hp_pct_u
            )
        if (move[_MOVE_BOOST_ATK]          #pylint: disable=too-many-boolean-expressions
            or move[_MOVE_BOOST_DEF]
            or move[_MOVE_BOOST_SPATK]
            or move[_MOVE_BOOST_SPDEF]
            or move[_MOVE_BOOST_SPEED]
            or move[_MOVE_BOOST_ACC]
            or move[_MOVE_BOOST_EV]):
            return expert_stat(
                move, ai_pok, rand, idx, hp_pct_ai,
                move_first, u_pok, hp_pct_u, my_last_move
            )

    # Moves Ignoring Accuracy (e.g. Aerial Ace, Shock Wave)
    if move[_MOVE_ACCURACY] == -1:  # -1 is how always hit moves is represented
        score = 0
        ai_acc = ai_pok[_POK_ACCURACY_STAT_STAGE]
        u_ev   = u_pok[_POK_EVASION_STAT_STAGE]
        if ai_acc <= -5 or u_ev >= 5:
            score += 1
        if ai_acc <= -3 or u_ev >= 3:
            add_adjustment(rand, idx, 1, 156)
        return score

    # Draining Moves (e.g. Absorb, Dream Eater)
    if move[_MOVE_DRAIN]:
        if move[_MOVE_ID] == _MOVENAME_DREAM_EATER:
            if effectiveness < 1.0:
                return -1
            if u_pok[_POK_STATUS] == _STATUS_SLEEP:
                add_adjustment(rand, idx, 3, 205)
            return 0
        if effectiveness < 1.0:
            add_adjustment(rand, idx, -3, 206)
        return 0

    """
    TODO:
    --------------Specific Moves---------------
    Selfdestruct, Explosion, Memento
    Healing Wish, Lunar Dance
    Mirror Move
    Dragon Dance
    Acupressure
    Vital Throw
    Haze
    Bide
    Conversion
    Rest
    Toxic, Leech Seed
    Light Screen
    Reflect
    Fake Out
    Spit Up
    Super Fang
    Disable
    Encore
    Counter, Mirror Coat
    Metal Burst
    Pain Split
    Nightmare
    Lock On, Mind Reader
    Sleep Talk
    Destiny Bond
    Reversal, Flail
    Heal Bell, Aromatherapy
    Thief, Covet
    Curse
    Protect, Detect
    Spikes
    Foresight, Odor Sleuth
    Miracle Eye
    Endure
    Substitute
    Baton Pass
    Pursuit
    Rain Dance
    Sunny Day
    Hail
    Gravity
    Tailwind
    Belly Drum
    Psych Up
    Facade
    Focus Punch
    Smelling Salt
    Wake-Up Slap
    Trick, Switcheroo
    Superpower
    Magic Coat
    Recycle
    Brick Break
    Knock Off
    Endeavor
    Imprison
    Refresh
    Snatch
    Mud Sport, Water Sport
    Hammer Arm
    Brine
    Feint
    Pluck, Bug Bite
    U-turn
    Close Combat
    Payback
    Assurance
    Embargo
    Fling
    Psycho Shift
    Trump Card
    Heal Block
    Wring Out, Crush Grip
    Power Trick
    Gastro Acid
    Lucky Chant
    Me First
    Copycat
    Power Swap
    Guard Swap
    Punishment
    Last Resort
    Worry Seed
    Sucker Punch
    Toxic Spikes
    Heart Swap
    Aqua Ring
    Magnet Rise
    Defog
    Trick Room
    Blizzard
    Captivate
    Stealth Rock

    --------------Effect Moves-----------------
    Moves Ignoring Accuracy (e.g. Aerial Ace, Shock Wave)
    Switch-Forcing Moves (Roar, Whirlwind)
    Recovery Moves (e.g., Recover, Synthesis, Swallow)
    OHKO Moves (Example moves: Horn Drill, Fissure, Sheer Cold, Guillotine)
    Charge Turn Moves Without Invulnerability (Razor Wind, Skull Bash, Sky Attack, Solar Beam/Blade)
    Charge Turn Moves With Invulnerability (Fly, Dive, Dig, Bounce)
    Binding Moves (e.g. Wrap, Clamp)
    High Critical Hit Rate (e.g. Slash, Razor Leaf, Cross Poison)
    Recoil Moves (e.g. Submission, Flare Blitz, Double-Edge)
    Speed-Lowering Attacks (e.g. Rock Tomb, Mud Shot, Icy Wind)
    Recharge-Turn Attacks (e.g. Hyper Beam, Giga Impact)
    Moves Which Change the User's Ability (Role Play, Skill Swap)
    Moves Which Decrease in Power With Less User HP (Water Spout, Eruption)
    Double-Power Negative-Priority Moves (Avalanche, Revenge)
    Moves Reducing the User's SpAttack by 2 (e.g., Overheat, Draco Meteor)

    --------------Mirror Move------------------
    Sleep Powder
    Lovely Kiss
    Spore
    Hypnosis
    Sing
    Grass Whistle
    Shadow Punch
    Sand Attack
    Smoke Screen
    Toxic
    Guillotine
    Horn Drill
    Fissure
    Sheer Cold
    Cross Chop
    Aeroblast
    Confuse Ray
    Sweet Kiss
    Screech
    Cotton Spore
    Scary Face
    Fake Tears
    Metal Sound
    Thunder Wave
    Glare
    Poison Powder
    Shadow Ball
    Dynamic Punch
    Hyper Beam
    Extreme Speed
    Thief
    Covet
    Attract
    Swagger
    Torment
    Flatter
    Trick
    Superpower
    Skill Swap
    Psycho Shift
    Power Swap
    Guard Swap
    Sucker Punch
    Heart Swap
    Switcheroo
    Captivate
    """
    return 0


@njit
def check_super_ef_move_pty(ai_party, user_pok, opp_active):
    """
    Check if there's any pokemon with super effective move
    """
    buf = np.zeros(6,dtype=np.int16)
    n = 0

    alive = np.where(ai_party[_POK_CURRENT_HP::POK_LEN] > 0)[0]
    if len(alive) <= 1:
        return buf[:0]

    user_t1 = user_pok[_POK_TYPE1]
    user_t2 = user_pok[_POK_TYPE2]
    for idx in alive:
        if idx == opp_active:
            continue
        pok = ai_party[(POK_LEN * idx):(POK_LEN * (idx + 1))]
        moves = pok[_POK_MOVE1_ID:_POK_ITEM_ID].reshape(4, -1)
        for mv in moves:
            mv_type = mv[_MOVE_TYPE]
            eff, den = get_type_effectiveness(mv_type, user_t1, user_t2)
            if eff // den >= 2:
                buf[n] = idx
                n += 1
                break
    return buf[:n]


@njit
def check_any_damaging_move_pty(ai_party, user_pok, opp_active):
    """
    Check party for any damaging move
    """
    buf = np.zeros(6,dtype=np.int16)
    n = 0

    alive = np.where(ai_party[_POK_CURRENT_HP::POK_LEN] > 0)[0]
    if len(alive) <= 1:
        return buf[:0]

    user_t1 = user_pok[_POK_TYPE1]
    user_t2 = user_pok[_POK_TYPE2]
    for idx in alive:
        if idx == opp_active:
            continue
        pok = ai_party[(POK_LEN * idx):(POK_LEN * (idx + 1))]
        moves = pok[_POK_MOVE1_ID:_POK_ITEM_ID].reshape(4, -1)
        for mv in moves:
            mv_type = mv[_MOVE_TYPE]
            eff, den = get_type_effectiveness(mv_type, user_t1, user_t2)
            if eff / den != 0:
                buf[n] = idx
                n += 1
                break
    return buf[:n]


@njit
def check_absorb_abi_pty(ai_party, my_last_move, opp_active):
    """
    Check if party has any pokemon with ability that absorbs types
    """
    buf = np.zeros(6,dtype=np.int16)
    n = 0

    alive = np.where(ai_party[_POK_CURRENT_HP::POK_LEN] > 0)[0]
    if len(alive) <= 1:
        return buf[:0]

    for idx in alive:
        if idx == opp_active:
            continue
        pok = ai_party[(POK_LEN * idx):(POK_LEN * (idx + 1))]
        pok_ab = pok[_POK_AB_ID]
        if pok_ab not in ABSORB_ABI:
            continue
        if my_last_move in FIRE_MOVES and pok_ab == _ABILITYNAMES_FLASH_FIRE:
            buf[n] = idx
            n += 1
        elif my_last_move in WATER_MOVES and pok_ab == _ABILITYNAMES_WATER_ABSORB:
            buf[n] = idx
            n += 1
        elif my_last_move in ELECTRIC_MOVES and pok_ab == _ABILITYNAMES_VOLT_ABSORB:
            buf[n] = idx
            n += 1
    return buf[:n]


@njit
def check_immunity_pty(ai_party, user_pok, last_move_type, opp_active):
    """
    Check if there's any pokemon with super effective move
    """
    buf = np.zeros(6,dtype=np.int16)
    n = 0

    alive = np.where(ai_party[_POK_CURRENT_HP::POK_LEN] > 0)[0]
    if len(alive) <= 1:
        return buf[:0]

    user_t1 = user_pok[_POK_TYPE1]
    user_t2 = user_pok[_POK_TYPE2]
    for idx in alive:
        if idx == opp_active:
            continue
        pok = ai_party[(POK_LEN * idx):(POK_LEN * (idx + 1))]
        ef, de = get_type_effectiveness(last_move_type, pok[_POK_TYPE1], pok[_POK_TYPE2])
        if ef/de == 0:
            moves = pok[_POK_MOVE1_ID:_POK_ITEM_ID].reshape(4, -1)
            for mv in moves:
                mv_type = mv[_MOVE_TYPE]
                eff, den = get_type_effectiveness(mv_type, user_t1, user_t2)
                if eff // den >= 2:
                    buf[n] = idx
                    n += 1
                    break
            if n == 1:
                break

    return buf[:n]


@njit
def check_resistence_pty(ai_party, user_pok, last_move_type, opp_active):
    """
    Check if there's any pokemon with super effective move
    """
    buf = np.zeros(6,dtype=np.int16)
    n = 0

    alive = np.where(ai_party[_POK_CURRENT_HP::POK_LEN] > 0)[0]
    if len(alive) <= 1:
        return buf[:0]

    user_t1 = user_pok[_POK_TYPE1]
    user_t2 = user_pok[_POK_TYPE2]
    for idx in alive:
        if idx == opp_active:
            continue
        pok = ai_party[(POK_LEN * idx):(POK_LEN * (idx + 1))]
        ef, de = get_type_effectiveness(last_move_type, pok[_POK_TYPE1], pok[_POK_TYPE2])
        if 0 < ef/de < 1:
            moves = pok[_POK_MOVE1_ID:_POK_ITEM_ID].reshape(4, -1)
            for mv in moves:
                mv_type = mv[_MOVE_TYPE]
                eff, den = get_type_effectiveness(mv_type, user_t1, user_t2)
                if eff // den >= 2:
                    buf[n] = idx
                    n += 1
                    break
            if n == 1:
                break

    return buf[:n]
