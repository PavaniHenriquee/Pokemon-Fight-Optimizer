"""Gives the class for the trainer Ai to be what the game would do"""
import random
import numpy as np
from Engine.damage_calc import calculate_damage
from Utils.helper import (
    get_type_effectiveness, batch_independent_score_from_rand, stage_to_multiplier
)
from DataBase.loader import pkDB
from DataBase.MoveDB import MoveName
from DataBase.AbilitiesDB import AbilityNames
from DataBase.PkDB import PokIdToName
from Models.idx_const import (
    Pok, Move, Flags, POK_LEN
)
from Models.helper import (
    MoveCategory, Types, Status, VolStatus, Gender, Target, count_party, Weather
)


ELEC_AB_IM = {AbilityNames.VOLT_ABSORB, AbilityNames.MOTOR_DRIVE}
POISON_AB_IM = {AbilityNames.IMMUNITY, AbilityNames.MAGIC_GUARD, AbilityNames.POISON_POINT}
PARA_AB_IM = {AbilityNames.LIMBER, AbilityNames.MAGIC_GUARD}
BURN_AB_IM = {AbilityNames.WATER_VEIL, AbilityNames.MAGIC_GUARD}
STAT_AB_IM = {AbilityNames.CLEAR_BODY, AbilityNames.WHITE_SMOKE}
STEEL_POISON = {Types.STEEL, Types.POISON}


class _Effectiviness:
    """Effectiviness helper, to check for how much"""
    X2 = 1
    X4 = 2
    IM = 3


def add_adjustment(arr, move_id, delta, chance):
    """Add a [delta, chance] pair to the first free slot."""
    # Find the first index where chance is NaN (unused)
    arr[move_id].append((delta, chance))

class TrainerAI:
    """
    Trainer AI, where it is used by using the def where it
    returns what the original ai would have done
    """

    def basic_flag(
            self, move, ability, ai_pok, user_pok, effectiveness, user_party_alive,
            weather
    ) -> int:
        """
        Basic Flag, every trainer has this,
        it discourages moves that would have no effect or that would make no sense
        """

        move_category = move[Move.CATEGORY]
        """
        # Check if move first (TODO add Trick room logic here)
        if (
            ai_pok[PokArray.SPEED] * stage_to_multiplier(ai_pok[PokArray.SPEED_STAT_STAGE])
            > user_pok[PokArray.SPEED] * stage_to_multiplier(user_pok[PokArray.SPEED_STAT_STAGE])
        ):
            move_first = True
        elif (
            ai_pok[PokArray.SPEED] * stage_to_multiplier(ai_pok[PokArray.SPEED_STAT_STAGE])
            < user_pok[PokArray.SPEED] * stage_to_multiplier(user_pok[PokArray.SPEED_STAT_STAGE])
        ):
            move_first = False
        else:
            move_first = random.choice([True, False])
        """
        # Check for immunity types
        if move_category != MoveCategory.STATUS and effectiveness == _Effectiviness.IM:
            return -10
        # Check for abilities
        if ai_pok[Pok.AB_ID] != AbilityNames.MOLD_BREAKER:
            move_type = move[Move.TYPE]
            if move_type == Types.ELECTRIC and ability in ELEC_AB_IM:
                return -10
            if move_type == Types.WATER and ability == AbilityNames.WATER_ABSORB:
                return -10
            if move_type == Types.FIRE and ability == AbilityNames.FLASH_FIRE:
                return -10
            if move_type == Types.GROUND and ability == AbilityNames.LEVITATE:
                return -10
            if move[Flags.SOUND] and ability == AbilityNames.SOUNDPROOF:
                return -10
            if (
                (effectiveness != _Effectiviness.X2 or effectiveness != _Effectiviness.X4)
                and ability == AbilityNames.WONDER_GUARD
                and move_category != MoveCategory.STATUS
            ):
                return -10
        if move_category == MoveCategory.STATUS:
            # TODO: Safeguard for all conditions
            if move[Move.STATUS] != 0:
                u_type12 = {user_pok[Pok.TYPE1],user_pok[Pok.TYPE2]}

                # Sleep
                if (
                    move[Move.STATUS] == Status.SLEEP
                    and (
                        user_pok[Pok.STATUS] != 0
                        or ability == AbilityNames.VITAL_SPIRIT
                    )
                ):
                    return -10
                # Poison
                if (
                    move[Move.STATUS] in (Status.POISON, Status.TOXIC)
                ):
                    if not u_type12.isdisjoint(STEEL_POISON):
                        return -10
                    if ability in POISON_AB_IM:
                        return -10
                    if weather:
                        if (
                            weather == Weather.SUN
                            and ability == AbilityNames.LEAF_GUARD
                        ):
                            return -10
                        if (
                            weather == Weather.RAIN
                            and ability == AbilityNames.HYDRATION
                        ):
                            return -10
                    if user_pok[Pok.STATUS] != 0:
                        return -10
                    # TODO: safeguard
                # Paralysis
                if (
                    move[Move.STATUS] == Status.PARALYSIS
                    and (
                        user_pok[Pok.STATUS] != 0
                        or (
                            move[Move.TYPE] == Types.ELECTRIC
                            and (
                                Types.GROUND in u_type12
                                or (
                                    ability in ELEC_AB_IM
                                    and ai_pok[Pok.AB_ID] != AbilityNames.MOLD_BREAKER
                                )
                            )
                        )
                        or ability in PARA_AB_IM
                    )
                ):
                    return -10
                # Burn
                if (
                    move[Move.STATUS] == Status.BURN
                    and (
                        user_pok[Pok.STATUS] != 0
                        or ability in BURN_AB_IM
                        or Types.FIRE in u_type12
                    )
                ):
                    return -10
            if move[Move.VOL_STATUS] != 0:
                # Confusion
                if move[Move.VOL_STATUS] == VolStatus.CONFUSION:
                    if user_pok[Pok.VOL_STATUS] & VolStatus.CONFUSION:
                        return -5
                    if ability == AbilityNames.OWN_TEMPO:
                        return -10
                # Attract
                if move[Move.VOL_STATUS] == VolStatus.ATTRACT:
                    if (
                        user_pok[Pok.VOL_STATUS] & VolStatus.ATTRACT
                        or ability == AbilityNames.OBLIVIOUS
                        or (
                            user_pok[Pok.GENDER] == ai_pok[Pok.GENDER]
                            or user_pok[Pok.GENDER] == Gender.GENDERLESS
                        )
                    ):
                        return -10
            if any(move[Move.BOOST_ATK: Move.BOOST_EV + 1]):
                # Stat Boosting Moves
                if move[Move.TARGET] in (
                    Target.ADJACENT_ALLY,
                    Target.ADJACENT_ALLY_OR_SELF,
                    Target.ALLIES,
                    Target.ALLY_SIDE,
                    Target.SELF
                ):
                    # TODO Trick room
                    if (
                        ai_pok[Pok.AB_ID] == AbilityNames.NO_GUARD
                        and (
                            move[Move.BOOST_ACC] > 0 or move[Move.BOOST_EV] > 0
                        )
                    ):
                        return -10
                    if ai_pok[Pok.AB_ID] == AbilityNames.SIMPLE:
                        if move[Move.BOOST_ATK] > 0 and ai_pok[Pok.ATTACK_STAT_STAGE] >= 3:
                            return -10
                        if move[Move.BOOST_DEF] > 0 and ai_pok[Pok.DEFENSE_STAT_STAGE] >= 3:
                            return -10
                        if move[Move.BOOST_SPATK] > 0 and ai_pok[Pok.SPECIAL_ATTACK_STAT_STAGE] >= 3:
                            return -10
                        if move[Move.BOOST_SPDEF] > 0 and ai_pok[Pok.SPECIAL_DEFENSE_STAT_STAGE] >= 3:
                            return -10
                        if move[Move.BOOST_SPEED] > 0 and ai_pok[Pok.SPEED_STAT_STAGE] >= 3:
                            return -10
                        if move[Move.BOOST_ACC] > 0 and ai_pok[Pok.ACCURACY_STAT_STAGE] >= 3:
                            return -10
                        if move[Move.BOOST_EV] > 0 and ai_pok[Pok.EVASION_STAT_STAGE] >= 3:
                            return -10
                    if move[Move.BOOST_ATK] > 0 and ai_pok[Pok.ATTACK_STAT_STAGE] == 6:
                        return -10
                    if move[Move.BOOST_DEF] > 0 and ai_pok[Pok.DEFENSE_STAT_STAGE] == 6:
                        return -10
                    if move[Move.BOOST_SPATK] > 0 and ai_pok[Pok.SPECIAL_ATTACK_STAT_STAGE] == 6:
                        return -10
                    if move[Move.BOOST_SPDEF] > 0 and ai_pok[Pok.SPECIAL_DEFENSE_STAT_STAGE] == 6:
                        return -10
                    if move[Move.BOOST_SPEED] > 0 and ai_pok[Pok.SPEED_STAT_STAGE] == 6:
                        return -10
                    if move[Move.BOOST_ACC] > 0 and ai_pok[Pok.ACCURACY_STAT_STAGE] == 6:
                        return -10
                    if move[Move.BOOST_EV] > 0 and ai_pok[Pok.EVASION_STAT_STAGE] == 6:
                        return -10
                # Stat Reducing Moves
                if move[Move.TARGET] in (
                    Target.NORMAL,
                    Target.ADJACENT_FOE,
                    Target.ALL_ADJACENT_FOES,
                    Target.ANY,
                    Target.FOE_SIDE,
                    Target.RANDOM_NORMAL,
                    Target.SCRIPTED
                ):
                    # TODO Trick Room
                    if move[Move.BOOST_ATK] and ability == AbilityNames.HYPER_CUTTER:
                        return -10
                    if move[Move.BOOST_SPEED] and ability == AbilityNames.SPEED_BOOST:
                        return -10
                    if (
                        (move[Move.BOOST_ACC] or move[Move.BOOST_EV])
                        and (ability == AbilityNames.NO_GUARD or ai_pok[Pok.AB_ID] == AbilityNames.NO_GUARD)
                    ):
                        return -10
                    if move[Move.BOOST_ACC] and ai_pok[Pok.AB_ID] == AbilityNames.KEEN_EYE:
                        return -10
                    if ability in STAT_AB_IM:
                        return -10
                    if move[Move.BOOST_ATK] < 0 and user_pok[Pok.ATTACK_STAT_STAGE] == -6:
                        return -10
                    if move[Move.BOOST_DEF] < 0 and user_pok[Pok.DEFENSE_STAT_STAGE] == -6:
                        return -10
                    if move[Move.BOOST_SPATK] < 0 and user_pok[Pok.SPECIAL_ATTACK_STAT_STAGE] == -6:
                        return -10
                    if move[Move.BOOST_SPDEF] < 0 and user_pok[Pok.SPECIAL_DEFENSE_STAT_STAGE] == -6:
                        return -10
                    if move[Move.BOOST_SPEED] < 0 and user_pok[Pok.SPEED_STAT_STAGE] == -6:
                        return -10
                    if move[Move.BOOST_ACC] < 0 and user_pok[Pok.ACCURACY_STAT_STAGE] == -6:
                        return -10
                    if move[Move.BOOST_EV] < 0 and user_pok[Pok.EVASION_STAT_STAGE] == -6:
                        return -10
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
        '''

        return 0

    def evaluate_attack_flag(
            self, final_damage, effectiveness, user_pok, move, idx, rand
    ) -> tuple[int, dict]:
        """
        For damage moves it sees if it kill and some move exceptions then add to score
        For non-damaging moves it checks if its 4x effective, for some reason
        """
        score = 0
        # Check for kill
        if final_damage >= user_pok[Pok.CURRENT_HP]:
            if (
                move[Move.ID]
                in (MoveName.EXPLOSION, MoveName.SELFDESTRUCT)
            ):
                score += 0
            elif (
                move[Move.ID]
                in (MoveName.SUCKER_PUNCH, MoveName.FOCUS_PUNCH, MoveName.FUTURE_SIGHT)
            ):
                add_adjustment(rand, idx, 4, 85)
                return score, rand
            elif move[Move.PRIORITY] >= 1 and move[Move.ID] != MoveName.FAKE_OUT:
                score = 6
                return score, rand
            else:
                score = 4
                return score, rand

        if (
            move[Move.ID] in (
                MoveName.SUCKER_PUNCH,
                MoveName.FOCUS_PUNCH,
                MoveName.EXPLOSION,
                MoveName.SELFDESTRUCT
            )
        ):
            add_adjustment(rand, idx, -2, 176)
        if effectiveness == _Effectiviness.X4:
            add_adjustment(rand, idx, 2, 176)
        return score, rand

    def expert_flag(self, ai_pok, u_pok, move, turn, idx, rand):
        """
        It shows the incentives and disincentives for the best trainer ai out there,
        for ROM HACKS every trainer has it
        """
        score = 0
        hp_pct_ai = (ai_pok[Pok.CURRENT_HP]*100) // ai_pok[Pok.MAX_HP]
        hp_pct_u = (u_pok[Pok.CURRENT_HP]*100) // u_pok[Pok.MAX_HP]
        # Check if move first (TODO add Trick room logic here)
        if (
            stage_to_multiplier(ai_pok[Pok.SPEED_STAT_STAGE], ai_pok[Pok.SPEED])
            > stage_to_multiplier(u_pok[Pok.SPEED_STAT_STAGE], u_pok[Pok.SPEED])
        ):
            move_first = True
        elif (
            stage_to_multiplier(ai_pok[Pok.SPEED_STAT_STAGE], ai_pok[Pok.SPEED])
            < stage_to_multiplier(u_pok[Pok.SPEED_STAT_STAGE], u_pok[Pok.SPEED])
        ):
            move_first = False
        else:
            move_first = random.choice([True, False])

        if move[Move.CATEGORY] == MoveCategory.STATUS:
            if move[Move.STATUS] != 0:
                # Poison-Inducing
                if (
                    move[Move.STATUS] == Status.POISON
                    and (hp_pct_ai < 50 or hp_pct_u <= 50)
                ):
                    score = -1
                    return score, rand
                    # Sleep-Inducing
                if (
                    move[Move.STATUS] == Status.SLEEP
                    and any(
                        m in [MoveName.DREAM_EATER, MoveName.NIGHTMARE]
                        for m in [
                            ai_pok[Pok.MOVE1_ID],
                            ai_pok[Pok.MOVE2_ID],
                            ai_pok[Pok.MOVE3_ID],
                            ai_pok[Pok.MOVE4_ID],
                        ]
                    )
                ):
                    add_adjustment(rand, idx, 1, 128)
                    return score, rand
                # Paralyzing-Inducing
                if move[Move.STATUS] == Status.PARALYSIS and not move_first:
                    add_adjustment(rand, idx, 3, 236)
                    return score, rand
            if move[Move.VOL_STATUS]:
                # Confusion-Inducing
                if move[Move.VOL_STATUS] == VolStatus.CONFUSION:
                    if move[Move.ID] == MoveName.SWAGGER:
                        psych_up = False
                        if any(
                            m == MoveName.PSYCH_UP
                            for m in [
                                ai_pok[Pok.MOVE1_ID],
                                ai_pok[Pok.MOVE2_ID],
                                ai_pok[Pok.MOVE3_ID],
                                ai_pok[Pok.MOVE4_ID],
                            ]
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
                    if move[Move.ID] in (MoveName.SWAGGER, MoveName.FLATTER):
                        add_adjustment(rand, idx, -1, 128)
                    if hp_pct_u <= 70:
                        add_adjustment(rand, idx, -1, 128)
                        if hp_pct_u <= 30:
                            score += -1
                        if hp_pct_u <= 50:
                            score += -1
                    return score, rand
            if any(move[Move.BOOST_ATK: Move.BOOST_EV + 1]):
                # Stat-Boosting moves
                # atk = ['Attack', 'Special Attack']
                # de = ['Defense', 'Special Defense']
                if move[Move.TARGET] in (
                    Target.ADJACENT_ALLY,
                    Target.ADJACENT_ALLY_OR_SELF,
                    Target.ALLIES,
                    Target.ALLY_SIDE,
                    Target.SELF
                ):
                    if any(move[Move.BOOST_ATK: Move.BOOST_SPDEF + 1]):
                        if (
                            (move[Move.BOOST_ATK] and ai_pok[Pok.ATTACK_STAT_STAGE]>= 3)
                            or (
                                move[Move.BOOST_SPATK]
                                and ai_pok[Pok.SPECIAL_ATTACK_STAT_STAGE]>= 3
                            )
                            or (
                                move[Move.BOOST_DEF]
                                and ai_pok[Pok.DEFENSE_STAT_STAGE]>= 3
                            )
                            or (
                                move[Move.BOOST_SPDEF]
                                and ai_pok[Pok.SPECIAL_DEFENSE_STAT_STAGE]>= 3
                            )
                        ):
                            add_adjustment(rand, idx, -1, 156)
                        if hp_pct_ai >= 100:
                            add_adjustment(rand, idx, 2, 128)
                        elif hp_pct_ai >= 71:
                            pass
                        elif hp_pct_ai > 39:
                            add_adjustment(rand, idx, -2, 186)
                        else:
                            score += -2
                        return score, rand
                    if move[Move.BOOST_SPEED] and move[Move.ID] != MoveName.DRAGON_DANCE:
                        if move_first:
                            score += -3
                        else:
                            add_adjustment(rand, idx, 3, 186)
                        return score, rand
                    if move[Move.BOOST_EV]:
                        if hp_pct_ai > 89:
                            add_adjustment(rand, idx, 3, 186)
                        if ai_pok[Pok.EVASION_STAT_STAGE]>= 3:
                            add_adjustment(rand, idx, -1, 128)
                        if u_pok[Pok.STATUS] == Status.TOXIC:
                            if hp_pct_ai > 50:
                                add_adjustment(rand, idx, 3, 206)
                            else:
                                add_adjustment(rand, idx, 3, 142)
                        if u_pok[Pok.VOL_STATUS] & VolStatus.LEECH_SEED:
                            add_adjustment(rand, idx, 3, 186)
                        if u_pok[Pok.VOL_STATUS] & VolStatus.CURSE:
                            add_adjustment(rand, idx, 3, 186)
                        if hp_pct_ai > 70 or u_pok[Pok.EVASION_STAT_STAGE] == 0:
                            return score, rand
                        if hp_pct_ai < 40 or hp_pct_u < 40:
                            score += -2
                            return score, rand
                        add_adjustment(rand, idx, -2, 186)
                        # TODO: Ingrain, Aqua Ring
                if move[Move.TARGET] in (
                    Target.NORMAL,
                    Target.ADJACENT_FOE,
                    Target.ALL_ADJACENT_FOES,
                    Target.ANY,
                    Target.FOE_SIDE,
                    Target.RANDOM_NORMAL,
                    Target.SCRIPTED
                ):
                    # Attack and Special Attack
                    if move[Move.BOOST_ATK] or move[Move.BOOST_SPATK]:
                        if (
                            (move[Move.BOOST_ATK]< 0 and u_pok[Pok.ATTACK_STAT_STAGE]!= 0)
                            or (move[Move.BOOST_SPATK] and u_pok[Pok.SPECIAL_ATTACK_STAT_STAGE]!= 0)
                        ):
                            score += -1
                        if hp_pct_ai <= 90:
                            score += -1
                        if (
                            (move[Move.BOOST_ATK] and u_pok[Pok.ATTACK_STAT_STAGE]<= -3)
                            or (
                                move[Move.BOOST_SPATK]
                                and u_pok[Pok.SPECIAL_ATTACK_STAT_STAGE]<= -3
                            )
                        ):
                            add_adjustment(rand, idx, -2, 206)
                        if hp_pct_u <= 70:
                            score += -2
                        # TODO: Last move check:
                        # If the move last used by the target was not of the corresponding
                        # class (Physical/Special), 50% chance of score -2.
                        return score, rand
                    # Defense and Special Defense
                    if move[Move.BOOST_DEF] or move[Move.BOOST_SPDEF]:
                        if hp_pct_ai < 70:
                            add_adjustment(rand, idx, -2, 206)
                        if (
                            (move[Move.BOOST_DEF] and ai_pok[Pok.DEFENSE_STAT_STAGE]<= -3)
                            or (
                                move[Move.BOOST_SPDEF]
                                and ai_pok[Pok.SPECIAL_DEFENSE_STAT_STAGE]<= -3
                            )
                        ):
                            add_adjustment(rand, idx, -2, 206)
                        if hp_pct_u < 70:
                            score += -2
                        return score, rand
                    # Speed
                    if move[Move.BOOST_SPEED]:
                        if not move_first:
                            add_adjustment(rand, idx, 2, 186)
                        else:
                            score += -3
                        return score, rand
                    # Accuracy
                    if move[Move.BOOST_ACC]:
                        # Check this, think it's wrong
                        if hp_pct_u <= 70 and not hp_pct_ai >= 70:
                            add_adjustment(rand, idx, -1, 156)
                        if ai_pok[Pok.ACCURACY_STAT_STAGE] <= -2:
                            add_adjustment(rand, idx, 2, 176)
                        if u_pok[Pok.STATUS] == Status.TOXIC:
                            add_adjustment(rand, idx, 2, 186)
                        if u_pok[Pok.VOL_STATUS] & VolStatus.LEECH_SEED:
                            add_adjustment(rand, idx, 2, 186)
                        if u_pok[Pok.VOL_STATUS] & VolStatus.CURSE:
                            add_adjustment(rand, idx, 2, 186)
                        if hp_pct_ai >= 70 or ai_pok[Pok.ACCURACY_STAT_STAGE] == 0:
                            return score, rand
                        if hp_pct_ai <= 40 or hp_pct_u <= 40:
                            score += -2
                        else:
                            add_adjustment(rand, idx, -2, 186)
                        return score, rand
                        # TODO: Ingrain, Aqua Ring
                    # Evasion
                    if move[Move.BOOST_EV]:
                        if hp_pct_ai < 70:
                            add_adjustment(rand, idx, -2, 206)
                        if u_pok.stat_stages['Evasion'] <= -3:
                            add_adjustment(rand, idx, -2, 206)
                        if hp_pct_u <= 70:
                            score += -2
                        return score, rand

        # Moves Ignoring Accuracy (e.g. Aerial Ace, Shock Wave)
        if move[Move.ACCURACY] == -1:  # -1 is how always hit moves is represented
            if ai_pok[Pok.ACCURACY_STAT_STAGE] <= -5 or u_pok[Pok.EVASION_STAT_STAGE] >= 5:
                score += 1
            if ai_pok[Pok.ACCURACY_STAT_STAGE] <= -3 or u_pok[Pok.EVASION_STAT_STAGE] >= 3:
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
        return score, rand

    def choose_move(
            self,
            ai_pok,
            user_pok,
            user_party_alive,
            turn,
            weather
    ):
        """
        Calculates the score of the moves and sees what has the highest score
        search is used for me to get the raw values of score and rand,
        so i can see what percentage of chance each move has
        """
        """The AI always knows what item you're holding. It cheats to see it.

        The AI always knows your exact current HP and max HP.

        The AI does not know your moves until it sees you use them. Other methods that expose moves,
        such as Sleep Talk or the Forewarn ability, do not count.

        The AI does not know your ability until it sees a text box with the ability name, such as:
        "... makes ground moves miss using LEVITATE", or "... FLASH FIRE made Flamethrower useless".
        If the AI does not know your ability, then most times it tries to check what your ability
        is, it will randomly guess one of the possible abilities your Pokémon's species can
        normally have. Abilities that modify damage but do not generate text, like Heatproof or
        Solid Rock, are not known to the AI even after damage is dealt. However, the AI is aware of
        the reduced damage that will be inflicted (e.g., for a Heatproof Bronzong, it will assume
        Levitate 50% of the time, but also will know that the Bronzong may survive a high-damage
        Fire attack that would KO if it had Levitate).

        Rarely, the AI must specifically see your ability, or your species must not have any other
        possible ability, in order for a check to succeed;
        these cases are worded as "If the target's ability is certainly...".

        There is one exception to this: the AI knows if your ability is Shadow Tag, Magnet Pull,
        or Arena Trap preventing it from switching.

        The AI always knows the attack order of all Pokémon on the field, barring speed ties or
        Quick Claws. It knows if there will be a speed tie, but does not know who will win it.
        If the AI is checking if it will attack before or after another target, and there is a
        speed tie, it will randomly guess the outcome of the tie. For any Pokémon on the field
        with a Quick Claw, it will randomly guess the Quick Claw will activate 20% of the time,
        independent of if the Quick Claw will actually activate.

        If you switch out, the AI will forget its knowledge of your moves and abilities.
        """
        move1 = ai_pok[Pok.MOVE1_ID:Pok.MOVE2_ID]
        move2 = ai_pok[Pok.MOVE2_ID:Pok.MOVE3_ID]
        move3 = ai_pok[Pok.MOVE3_ID:Pok.MOVE4_ID]
        move4 = ai_pok[Pok.MOVE4_ID:Pok.ITEM_ID]
        move_scores = {}

        # TODO
        if True:
            ability = user_pok[Pok.AB_ID]
        else:
            try:
                ability = random.choice(
                    pkDB[PokIdToName[user_pok[Pok.ID]].capitalize()]['abilities']
                ).upper()
            except Exception:
                ability = getattr(AbilityNames, user_pok[Pok.AB_ID])
        rand = [[] for _ in range(4)]
        max_damage = 0
        # Moves to not consider in damage calc
        # mov_excep = ['Razor Wind', 'Sky Attack', 'Recharge', 'Hyper Beam', 'Giga Impact',
        #             'Skull Bash', 'Solarbeam', 'Solar Blade', 'Spit Up', 'Superpower', 'Eruption',
        #             'Water Spout','Head Smash']
        # mov_excep = [0, MoveName.EXPLOSION, MoveName.SELFDESTRUCT, MoveName.DREAM_EATER,
        #              MoveName.FOCUS_PUNCH, MoveName.SUCKER_PUNCH]
        mov_excep = [0]

        for i, move in enumerate((move1, move2, move3, move4)):

            if move[Move.ID] == 0:
                break
            if move[Move.PP] <= 0:
                continue
            score = 0
            final_damage = calculate_damage(ai_pok, user_pok, move)
            effectiveness, den = get_type_effectiveness(
                move[Move.TYPE],
                user_pok[Pok.TYPE1],
                user_pok[Pok.TYPE2]
            )
            if effectiveness // den == 2:
                effec = _Effectiviness.X2
            elif effectiveness // den == 4:
                effec = _Effectiviness.X4
            elif effectiveness == 0:
                effec = _Effectiviness.IM
            else:
                effec = 0

            eval_atk, rand = self.evaluate_attack_flag(final_damage, effec, user_pok, move, i, rand)
            score += eval_atk
            score += self.basic_flag(
                move, ability, ai_pok, user_pok, effec, user_party_alive, weather
            )
            expert, rand = self.expert_flag(
                ai_pok, user_pok, move,
                turn, i, rand
            )
            score += expert

            # Find max damage among best moves
            if move[Move.ID] not in mov_excep and final_damage > max_damage:
                max_damage = final_damage

            # TODO: Finish expert flag
            score += batch_independent_score_from_rand(rand, i)

            move_scores[i] = {"score": score, "dmg": final_damage, "idx": i}

        # Apply penalty for moves that don't reach max damage
        for i, move in enumerate((move1, move2, move3, move4)):
            if (
                move[Move.ID] not in mov_excep
                and move[Move.CATEGORY] != MoveCategory.STATUS
                and move[Move.PP] > 0
            ):
                if (
                    move_scores[i]['dmg'] < max_damage
                    and not move_scores[i]['dmg'] >= user_pok[Pok.CURRENT_HP]
                ):
                    move_scores[i]["score"] -= 1

        return move_scores

    def return_idx(self, ai_pok, user_pok, user_party, turn, weather):
        """
        It transform the highest moving score to the index of the move
        """
        move_scores= self.choose_move(
            ai_pok, user_pok, user_party, turn, weather
        )
        max_score = max(info["score"] for info in move_scores.values())
        best_moves = [info for info in move_scores.values() if info["score"] == max_score]
        if len(best_moves) == 1:
            idx = best_moves[0]['idx']
        else:
            choice = random.choice(best_moves)
            idx = choice['idx']
        return idx

    def sub_after_death(self, ai_party, user_pok, deadmon) -> int:
        """
        Implements the switch-in logic

        Phase 1:
        --------
          * Consider only non-fainted teammates.
          * Select teammates that have at least one move that is supereffective (>1) vs user_pok.
          * If any such teammates exist, score each teammate by summing the effectiveness
            of each of their TYPE(S) versus user_pok (single-typed counted twice).
            Higher sum wins; ties broken by party order (lower index wins).

        Phase 2:
        ---------
          * If no Phase 1 candidate, for each non-fainted teammate compute the max damage any
          of its moves would do to user_pok (use calculate_damage). Apply the "255 overflow"
          rule: if damage > 255 -> damage = damage - 255.
          * Choose teammate with highest such max move damage. Ties broken by party order.

        Returns:
        -------
                index of chosen teammate in ai_party (int) or None if no valid candidate.

        """
        off = POK_LEN
        # filter non-fainted teammates and keep original party indices for tie-breaks
        candidates = np.where(ai_party[Pok.CURRENT_HP:: off] > 0)[0].tolist()
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]

        # Phase 1: find mons that have at least one move that is SE (>1) vs user_pok
        phase1 = []
        for idx in candidates:
            pok = ai_party[(off*idx):(off*(idx + 1))]
            has_se_move = False
            m1 = pok[Pok.MOVE1_ID:Pok.MOVE2_ID]
            m2 = pok[Pok.MOVE2_ID:Pok.MOVE3_ID]
            m3 = pok[Pok.MOVE3_ID:Pok.MOVE4_ID]
            m4 = pok[Pok.MOVE4_ID:Pok.ITEM_ID]
            for mv in (m1, m2, m3, m4):
                mv_type = mv[Move.TYPE]
                if mv_type == 0:
                    break
                eff = get_type_effectiveness(mv_type, user_pok[Pok.TYPE1], user_pok[Pok.TYPE2])
                if eff == _Effectiviness.X2 or eff == _Effectiviness.X4:
                    has_se_move = True
                    break
            if has_se_move:
                phase1.append((idx, pok))

        if phase1:
            # TODO: Check bugged list of Pokemon in document:
            # https://drive.google.com/file/d/1MpWJWc4wNTz2oA6QiPMmstLpSwHBlpRk/view
            # Score each mon by summing the effectiveness of each of its types vs user_pok
            if len(phase1) == 1:
                return phase1[0][0]
            scored = []
            for idx, mon in phase1:
                type1 = mon[Pok.TYPE1]
                # single-typed counted twice
                type2 = mon[Pok.TYPE2] if mon[Pok.TYPE2] != 0 else mon[Pok.TYPE1]
                effec, den = get_type_effectiveness(type1, user_pok[Pok.TYPE1], user_pok[Pok.TYPE2])
                total = effec/den
                effec, den = get_type_effectiveness(type2, user_pok[Pok.TYPE1], user_pok[Pok.TYPE2])
                total += effec/den
                if total == 8:
                    total = 1.75
                scored.append({'index': idx, 'mon': mon, 'score': total})

            # choose highest score, tie-break by party order (lower index wins)
            best = max(scored, key=lambda x: (x['score'], -x['index']))
            return best['index']

        # Phase 2: simulate moves as if used on the (full)
        # user pok and pick mon with max single-move damage

        scored_phase2 = []
        for idx in candidates:
            mon = ai_party[(off*idx):(off*(idx + 1))]
            max_move_dmg = 0
            m1 = pok[Pok.MOVE1_ID:Pok.MOVE2_ID]
            m2 = pok[Pok.MOVE2_ID:Pok.MOVE3_ID]
            m3 = pok[Pok.MOVE3_ID:Pok.MOVE4_ID]
            m4 = pok[Pok.MOVE4_ID:Pok.ITEM_ID]
            for mv in (m1, m2, m3, m4):
                # build move object shape expected by calculate_damage
                try:
                    raw_dmg = calculate_damage(deadmon, user_pok, mv, roll_multiplier=1)
                except Exception:
                    # if damage calc fails, skip move
                    continue
                # apply overflow bug: if damage > 255, it overflows by subtracting 255
                dmg = raw_dmg - 255 if raw_dmg > 255 else raw_dmg
                max_move_dmg = max(max_move_dmg, dmg)
            scored_phase2.append({'index': idx, 'max_dmg': max_move_dmg})

        if not scored_phase2:  # Defensive, shouldn't get here
            raise ValueError(
                "Shouldn't get here, check flow of code," \
                "because at least one pok should be avaliable"
            )

        # choose highest max_dmg, tie-break by party order (lower index wins)
        best2 = max(scored_phase2, key=lambda x: (x['max_dmg'], -x['index']))
        return best2['index']
