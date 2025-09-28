"""Gives the class for the trainer Ai to be what the game would do"""
import random
import numpy as np
from Engine.damage_calc import calculate_damage
from Utils.helper import get_type_effectiveness, batch_independent_score_from_rand, stage_to_multiplier
from DataBase.loader import pkDB
from DataBase.MoveDB import MoveName
from DataBase.AbilitiesDB import AbilityNames
from Models.idx_nparray import MoveArray, PokArray, MoveFlags
from Models.helper import MoveCategory, Types, Status, VolStatus, Gender, Target, count_party


def add_adjustment(arr, move_id, delta, chance):
    """Add a [delta, chance] pair to the first free slot."""
    # Find the first index where chance is NaN (unused)
    free_idx = np.where(np.isnan(arr[move_id, :, 1]))[0]
    if free_idx.size == 0:
        raise ValueError("No free slots left for this move, needs to add more")
    arr[move_id, free_idx[0]] = [delta, chance]


class TrainerAI:
    """
    Trainer AI, where it is used by using the def where it returns what the original ai would have done
    """
    def __init__(self, difficulty=None, gen=4):
        self.gen = gen
        self.difficulty = difficulty
        self.current_pok_ab = False

    def basic_flag(
            self, move, ability, ai_pok, user_pok, effectiveness, user_party_alive,
            ai_party_alive, turn  # pylint: disable=W0613
    ) -> int:
        """
        Basic Flag, every trainer has this,
        it discourages moves that would have no effect or that would make no sense
        """
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
        if move[MoveArray.CATEGORY] != MoveCategory.STATUS and effectiveness == 0:
            return -10
        # Check for abilities
        if ai_pok[PokArray.AB_ID] != AbilityNames.MOLD_BREAKER:
            if move[MoveArray.TYPE] == Types.ELECTRIC and ability in ("VOLT_ABSORB", "MOTOR_DRIVE"):
                return -10
            if move[MoveArray.TYPE] == Types.WATER and ability == "WATER_ABSORB":
                return -10
            if move[MoveArray.TYPE] == Types.FIRE and ability == "FLASH_FIRE":
                return -10
            if move[MoveArray.TYPE] == Types.GROUND and ability == "LEVITATE":
                return -10
            if move[len(MoveArray) + MoveFlags.SOUND] and ability == "SOUNDPROOF":
                return -10
            if (
                effectiveness < 2 and ability == "WONDER_GUARD"
                and move[MoveArray.CATEGORY] != MoveCategory.STATUS
            ):
                return -10
        if move[MoveArray.CATEGORY] == MoveCategory.STATUS:
            # TODO: Safeguard for all conditions
            if move[MoveArray.STATUS] != 0:
                # Sleep
                if (
                    move[MoveArray.STATUS] == Status.SLEEP
                    and (
                        user_pok[PokArray.STATUS] != 0
                        or ability == "VITAL_SPIRIT"
                    )
                ):
                    return -10
                # Poison
                if (
                    move[MoveArray.STATUS] in (Status.POISON, Status.TOXIC)
                    and (
                        user_pok[PokArray.STATUS] != 0
                        or ability in ("IMMUNITY", "MAGIC_GUARD", "POISON_HEAL")
                        or Types.STEEL in (user_pok[PokArray.TYPE1], user_pok[PokArray.TYPE2])
                        or Types.POISON in (user_pok[PokArray.TYPE1], user_pok[PokArray.TYPE2])
                    )
                ):
                    # TODO: weather
                    return -10
                # Paralysis
                if (
                    move[MoveArray.STATUS] == Status.PARALYSIS
                    and (
                        user_pok[PokArray.STATUS] != 0
                        or (
                            move[MoveArray.TYPE] == Types.ELECTRIC
                            and (
                                Types.GROUND in (user_pok[PokArray.TYPE1], user_pok[PokArray.TYPE2])
                                or (
                                    ability in ('VOLT_ABSORB', 'MOTOR_DRIVE')
                                    and ai_pok[PokArray.AB_ID] != AbilityNames.MOLD_BREAKER
                                )
                            )
                        )
                        or ability in ('LIMBER', 'MAGIC_GUARD')
                    )
                ):
                    return -10
                # Burn
                if (
                    move[MoveArray.STATUS] == Status.BURN
                    and (
                        user_pok[PokArray.STATUS] != 0
                        or ability in ("WATER_VEIL", "MAGIC_GUARD")
                        or Types.FIRE in (user_pok[PokArray.TYPE1], user_pok[PokArray.TYPE2])
                    )
                ):
                    return -10
            if move[MoveArray.VOL_STATUS] != 0:
                # Confusion
                if move[MoveArray.VOL_STATUS] == VolStatus.CONFUSION:
                    if user_pok[PokArray.VOL_STATUS] & VolStatus.CONFUSION:
                        return -5
                    if ability == "OWN_TEMPO":
                        return -10
                # Attract
                if move[MoveArray.VOL_STATUS] == VolStatus.ATTRACT:
                    if (
                        user_pok[PokArray.VOL_STATUS] & VolStatus.ATTRACT
                        or ability == "OBLIVIOUS"
                        or (
                            user_pok[PokArray.GENDER] == ai_pok[PokArray.GENDER]
                            or user_pok[PokArray.GENDER] == Gender.GENDERLESS
                        )
                    ):
                        return -10
            if any(move[MoveArray.BOOST_ATK: MoveArray.BOOST_EV + 1]):
                # Stat Boosting Moves
                if move[MoveArray.TARGET] in (
                    Target.ADJACENT_ALLY,
                    Target.ADJACENT_ALLY_OR_SELF,
                    Target.ALLIES,
                    Target.ALLY_SIDE,
                    Target.SELF
                ):
                    # TODO Trick room
                    if (
                        ai_pok[PokArray.AB_ID] == AbilityNames.NO_GUARD
                        and (
                            move[MoveArray.BOOST_ACC] > 0 or move[MoveArray.BOOST_EV] > 0
                        )
                    ):
                        return -10
                    if ai_pok[PokArray.AB_ID] == AbilityNames.SIMPLE:
                        if move[MoveArray.BOOST_ATK] > 0 and ai_pok[PokArray.ATTACK_STAT_STAGE] >= 3:
                            return -10
                        if move[MoveArray.BOOST_DEF] > 0 and ai_pok[PokArray.DEFENSE_STAT_STAGE] >= 3:
                            return -10
                        if move[MoveArray.BOOST_SPATK] > 0 and ai_pok[PokArray.SPECIAL_ATTACK_STAT_STAGE] >= 3:
                            return -10
                        if move[MoveArray.BOOST_SPDEF] > 0 and ai_pok[PokArray.SPECIAL_DEFENSE_STAT_STAGE] >= 3:
                            return -10
                        if move[MoveArray.BOOST_SPEED] > 0 and ai_pok[PokArray.SPEED_STAT_STAGE] >= 3:
                            return -10
                        if move[MoveArray.BOOST_ACC] > 0 and ai_pok[PokArray.ACCURACY_STAT_STAGE] >= 3:
                            return -10
                        if move[MoveArray.BOOST_EV] > 0 and ai_pok[PokArray.EVASION_STAT_STAGE] >= 3:
                            return -10
                    if move[MoveArray.BOOST_ATK] > 0 and ai_pok[PokArray.ATTACK_STAT_STAGE] == 6:
                        return -10
                    if move[MoveArray.BOOST_DEF] > 0 and ai_pok[PokArray.DEFENSE_STAT_STAGE] == 6:
                        return -10
                    if move[MoveArray.BOOST_SPATK] > 0 and ai_pok[PokArray.SPECIAL_ATTACK_STAT_STAGE] == 6:
                        return -10
                    if move[MoveArray.BOOST_SPDEF] > 0 and ai_pok[PokArray.SPECIAL_DEFENSE_STAT_STAGE] == 6:
                        return -10
                    if move[MoveArray.BOOST_SPEED] > 0 and ai_pok[PokArray.SPEED_STAT_STAGE] == 6:
                        return -10
                    if move[MoveArray.BOOST_ACC] > 0 and ai_pok[PokArray.ACCURACY_STAT_STAGE] == 6:
                        return -10
                    if move[MoveArray.BOOST_EV] > 0 and ai_pok[PokArray.EVASION_STAT_STAGE] == 6:
                        return -10
                # Stat Reducing Moves
                if move[MoveArray.TARGET] in (
                    Target.NORMAL,
                    Target.ADJACENT_FOE,
                    Target.ALL_ADJACENT_FOES,
                    Target.ANY,
                    Target.FOE_SIDE,
                    Target.RANDOM_NORMAL,
                    Target.SCRIPTED
                ):
                    # TODO Trick Room
                    if move[MoveArray.BOOST_ATK] and ability == "HYPER_CUTTER":
                        return -10
                    if move[MoveArray.BOOST_SPEED] and ability == "SPEED_BOOST":
                        return -10
                    if (
                        (move[MoveArray.BOOST_ACC] or move[MoveArray.BOOST_EV])
                        and (ability == "NO_GUARD" or ai_pok[PokArray.AB_ID] == AbilityNames.NO_GUARD)
                    ):
                        return -10
                    if move[MoveArray.BOOST_ACC] and ai_pok[PokArray.AB_ID] == AbilityNames.KEEN_EYE:
                        return -10
                    if ability in ("CLEAR_BODY", "WHITE_SMOKE"):
                        return -10
                    if move[MoveArray.BOOST_ATK] < 0 and user_pok[PokArray.ATTACK_STAT_STAGE] == -6:
                        return -10
                    if move[MoveArray.BOOST_DEF] < 0 and user_pok[PokArray.DEFENSE_STAT_STAGE] == -6:
                        return -10
                    if move[MoveArray.BOOST_SPATK] < 0 and user_pok[PokArray.SPECIAL_ATTACK_STAT_STAGE] == -6:
                        return -10
                    if move[MoveArray.BOOST_SPDEF] < 0 and user_pok[PokArray.SPECIAL_DEFENSE_STAT_STAGE] == -6:
                        return -10
                    if move[MoveArray.BOOST_SPEED] < 0 and user_pok[PokArray.SPEED_STAT_STAGE] == -6:
                        return -10
                    if move[MoveArray.BOOST_ACC] < 0 and user_pok[PokArray.ACCURACY_STAT_STAGE] == -6:
                        return -10
                    if move[MoveArray.BOOST_EV] < 0 and user_pok[PokArray.EVASION_STAT_STAGE] == -6:
                        return -10
            # Moves Which Force Switches
            if (
                move[MoveArray.FORCE_SWITCH]
                and (
                    count_party(user_party_alive) > 1
                    or (
                        ability == 'SUCTION_CUPS'
                        and ai_pok[PokArray.AB_ID] == AbilityNames.MOLD_BREAKER
                    )
                )
            ):
                return -10
            # Recovery Moves
            if move[len(MoveArray) + MoveFlags.HEAL] and ai_pok[PokArray.CURRENT_HP] == ai_pok[PokArray.MAX_HP]:
                return -10
            # OH-KO
            if (
                move[MoveArray.OH_KO]
                and (
                    user_pok[PokArray.LEVEL] > ai_pok[PokArray.LEVEL]
                    or (
                        ability == "STURDY" and ai_pok[PokArray.AB_ID] == AbilityNames.MOLD_BREAKER
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

    def evaluate_attack_flag(self, final_damage, effectiveness, user_pok, move, idx, rand) -> tuple[int, dict]:
        """
        For damage moves it sees if it kill and some move exceptions then add to score
        For non-damaging moves it checks if its 4x effective, for some reason
        """
        score = 0
        # Check for kill
        if final_damage >= user_pok[PokArray.CURRENT_HP]:
            if move[MoveArray.ID] in (MoveName.EXPLOSION, MoveName.SELFDESTRUCT):
                score += 0
            elif move[MoveArray.ID] in (MoveName.SUCKER_PUNCH, MoveName.FOCUS_PUNCH, MoveName.FUTURE_SIGHT):
                add_adjustment(rand, idx, 4, 85)
                return score, rand
            elif move[MoveArray.PRIORITY] >= 1 and move[MoveArray.ID] != MoveName.FAKE_OUT:
                score = 6
                return score, rand
            else:
                score = 4
                return score, rand

        if (
            move[MoveArray.ID] in (
                MoveName.SUCKER_PUNCH,
                MoveName.FOCUS_PUNCH,
                MoveName.EXPLOSION,
                MoveName.SELFDESTRUCT
            )
        ):
            add_adjustment(rand, idx, -2, 176)
        if effectiveness == 4:
            add_adjustment(rand, idx, 2, 176)
        return score, rand

    def expert_flag(self, damage, eff, ai_pok, u_pok, move, ai_pt, u_pt, turn, idx, rand):  # pylint: disable=W0613
        """
        It shows the incentives and disincentives for the best trainer ai out there, for ROM HACKS every trainer has it
        """
        score = 0
        hp_pct_ai = np.floor(ai_pok[PokArray.CURRENT_HP] / ai_pok[PokArray.MAX_HP] * 100)
        hp_pct_u = np.floor(u_pok[PokArray.CURRENT_HP] / u_pok[PokArray.MAX_HP] * 100)
        # Check if move first (TODO add Trick room logic here)
        if (
            ai_pok[PokArray.SPEED] * stage_to_multiplier(ai_pok[PokArray.SPEED_STAT_STAGE])
            > u_pok[PokArray.SPEED] * stage_to_multiplier(u_pok[PokArray.SPEED_STAT_STAGE])
        ):
            move_first = True
        elif (
            ai_pok[PokArray.SPEED] * stage_to_multiplier(ai_pok[PokArray.SPEED_STAT_STAGE])
            < u_pok[PokArray.SPEED] * stage_to_multiplier(u_pok[PokArray.SPEED_STAT_STAGE])
        ):
            move_first = False
        else:
            move_first = random.choice([True, False])

        if move[MoveArray.CATEGORY] == MoveCategory.STATUS:
            if move[MoveArray.STATUS] != 0:
                # Poison-Inducing
                if (
                    move[MoveArray.STATUS] == Status.POISON
                    and (hp_pct_ai < 50 or hp_pct_u <= 50)
                ):
                    score = -1
                    return score, rand
                    # Sleep-Inducing
                if (
                    move[MoveArray.STATUS] == Status.SLEEP
                    and any(
                        m in [MoveName.DREAM_EATER, MoveName.NIGHTMARE]
                        for m in [
                            ai_pok[PokArray.MOVE1_ID],
                            ai_pok[PokArray.MOVE2_ID],
                            ai_pok[PokArray.MOVE3_ID],
                            ai_pok[PokArray.MOVE4_ID],
                        ]
                    )
                ):
                    add_adjustment(rand, idx, 1, 128)
                    return score, rand
                # Paralyzing-Inducing
                if move[MoveArray.STATUS] == Status.PARALYSIS and not move_first:
                    add_adjustment(rand, idx, 3, 236)
                    return score, rand
            if move[MoveArray.VOL_STATUS]:
                # Confusion-Inducing
                if move[MoveArray.VOL_STATUS] == VolStatus.CONFUSION:
                    if move[MoveArray.ID] == MoveName.SWAGGER:
                        psych_up = False
                        if any(
                            m == MoveName.PSYCH_UP
                            for m in [
                                ai_pok[PokArray.MOVE1_ID],
                                ai_pok[PokArray.MOVE2_ID],
                                ai_pok[PokArray.MOVE3_ID],
                                ai_pok[PokArray.MOVE4_ID],
                            ]
                        ):
                            psych_up = True
                        if psych_up:
                            if u_pok[PokArray.ATTACK_STAT_STAGE] <= -3:
                                if turn == 1:
                                    score += 5
                                else:
                                    score += 3
                            else:
                                score += -5
                            return score, rand
                    if move[MoveArray.ID] in (MoveName.SWAGGER, MoveName.FLATTER):
                        add_adjustment(rand, idx, -1, 128)
                    if hp_pct_u <= 70:
                        add_adjustment(rand, idx, -1, 128)
                        if hp_pct_u <= 30:
                            score += -1
                        if hp_pct_u <= 50:
                            score += -1
                    return score, rand
            if any(move[MoveArray.BOOST_ATK: MoveArray.BOOST_EV + 1]):
                # Stat-Boosting moves
                # atk = ['Attack', 'Special Attack']
                # de = ['Defense', 'Special Defense']
                if move[MoveArray.TARGET] in (
                    Target.ADJACENT_ALLY,
                    Target.ADJACENT_ALLY_OR_SELF,
                    Target.ALLIES,
                    Target.ALLY_SIDE,
                    Target.SELF
                ):
                    if any(move[MoveArray.BOOST_ATK: MoveArray.BOOST_SPDEF + 1]):
                        if (
                            (move[MoveArray.BOOST_ATK] and ai_pok[PokArray.ATTACK_STAT_STAGE]>= 3)
                            or (move[MoveArray.BOOST_SPATK] and ai_pok[PokArray.SPECIAL_ATTACK_STAT_STAGE]>= 3)
                            or (move[MoveArray.BOOST_DEF] and ai_pok[PokArray.DEFENSE_STAT_STAGE]>= 3)
                            or (move[MoveArray.BOOST_SPDEF] and ai_pok[PokArray.SPECIAL_DEFENSE_STAT_STAGE]>= 3)
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
                    if move[MoveArray.BOOST_SPEED] and move[MoveArray.ID] != MoveName.DRAGON_DANCE:
                        if move_first:
                            score += -3
                        else:
                            add_adjustment(rand, idx, 3, 186)
                        return score, rand
                    if move[MoveArray.BOOST_EV]:
                        if hp_pct_ai > 89:
                            add_adjustment(rand, idx, 3, 186)
                        if ai_pok[PokArray.EVASION_STAT_STAGE]>= 3:
                            add_adjustment(rand, idx, -1, 128)
                        if u_pok[PokArray.STATUS] == Status.TOXIC:
                            if hp_pct_ai > 50:
                                add_adjustment(rand, idx, 3, 206)
                            else:
                                add_adjustment(rand, idx, 3, 142)
                        if u_pok[PokArray.VOL_STATUS] & VolStatus.LEECH_SEED:
                            add_adjustment(rand, idx, 3, 186)
                        if u_pok[PokArray.VOL_STATUS] & VolStatus.CURSE:
                            add_adjustment(rand, idx, 3, 186)
                        if hp_pct_ai > 70 or u_pok[PokArray.EVASION_STAT_STAGE] == 0:
                            return score, rand
                        if hp_pct_ai < 40 or hp_pct_u < 40:
                            score += -2
                            return score, rand
                        add_adjustment(rand, idx, -2, 186)
                        # TODO: Ingrain, Aqua Ring
                if move[MoveArray.TARGET] in (
                    Target.NORMAL,
                    Target.ADJACENT_FOE,
                    Target.ALL_ADJACENT_FOES,
                    Target.ANY,
                    Target.FOE_SIDE,
                    Target.RANDOM_NORMAL,
                    Target.SCRIPTED
                ):
                    # Attack and Special Attack
                    if move[MoveArray.BOOST_ATK] or move[MoveArray.BOOST_SPATK]:
                        if (
                            (move[MoveArray.BOOST_ATK]< 0 and u_pok[PokArray.ATTACK_STAT_STAGE]!= 0)
                            or (move[MoveArray.BOOST_SPATK] and u_pok[PokArray.SPECIAL_ATTACK_STAT_STAGE]!= 0)
                        ):
                            score += -1
                        if hp_pct_ai <= 90:
                            score += -1
                        if (
                            (move[MoveArray.BOOST_ATK] and u_pok[PokArray.ATTACK_STAT_STAGE]<= -3)
                            or (move[MoveArray.BOOST_SPATK] and u_pok[PokArray.SPECIAL_ATTACK_STAT_STAGE]<= -3)
                        ):
                            add_adjustment(rand, idx, -2, 206)
                        if hp_pct_u <= 70:
                            score += -2
                        # TODO: Last move check: If the move last used by the target was not of the corresponding
                        # class (Physical/Special), 50% chance of score -2.
                        return score, rand
                    # Defense and Special Defense
                    if move[MoveArray.BOOST_DEF] or move[MoveArray.BOOST_SPDEF]:
                        if hp_pct_ai < 70:
                            add_adjustment(rand, idx, -2, 206)
                        if (
                            (move[MoveArray.BOOST_DEF] and ai_pok[PokArray.DEFENSE_STAT_STAGE]<= -3)
                            or (move[MoveArray.BOOST_SPDEF] and ai_pok[PokArray.SPECIAL_DEFENSE_STAT_STAGE]<= -3)
                        ):
                            add_adjustment(rand, idx, -2, 206)
                        if hp_pct_u < 70:
                            score += -2
                        return score, rand
                    # Speed
                    if move[MoveArray.BOOST_SPEED]:
                        if not move_first:
                            add_adjustment(rand, idx, 2, 186)
                        else:
                            score += -3
                        return score, rand
                    # Accuracy
                    if move[MoveArray.BOOST_ACC]:
                        # Check this, think it's wrong
                        if hp_pct_u <= 70 and not hp_pct_ai >= 70:
                            add_adjustment(rand, idx, -1, 156)
                        if ai_pok[PokArray.ACCURACY_STAT_STAGE] <= -2:
                            add_adjustment(rand, idx, 2, 176)
                        if u_pok[PokArray.STATUS] == Status.TOXIC:
                            add_adjustment(rand, idx, 2, 186)
                        if u_pok[PokArray.VOL_STATUS] & VolStatus.LEECH_SEED:
                            add_adjustment(rand, idx, 2, 186)
                        if u_pok[PokArray.VOL_STATUS] & VolStatus.CURSE:
                            add_adjustment(rand, idx, 2, 186)
                        if hp_pct_ai >= 70 or ai_pok[PokArray.ACCURACY_STAT_STAGE] == 0:
                            return score, rand
                        if hp_pct_ai <= 40 or hp_pct_u <= 40:
                            score += -2
                        else:
                            add_adjustment(rand, idx, -2, 186)
                        return score, rand
                        # TODO: Ingrain, Aqua Ring
                    # Evasion
                    if move[MoveArray.BOOST_EV]:
                        if hp_pct_ai < 70:
                            add_adjustment(rand, idx, -2, 206)
                        if u_pok.stat_stages['Evasion'] <= -3:
                            add_adjustment(rand, idx, -2, 206)
                        if hp_pct_u <= 70:
                            score += -2
                        return score, rand

        # Moves Ignoring Accuracy (e.g. Aerial Ace, Shock Wave)
        if move[MoveArray.ACCURACY] == -1:  # -1 is how always hit moves is represented, being equal to acc: true
            if ai_pok[PokArray.ACCURACY_STAT_STAGE] <= -5 or u_pok[PokArray.EVASION_STAT_STAGE] >= 5:
                score += 1
            if ai_pok[PokArray.ACCURACY_STAT_STAGE] <= -3 or u_pok[PokArray.EVASION_STAT_STAGE] >= 3:
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
            ai_party_alive,
            turn,
            move1,
            move2,
            move3,
            move4
    ):
        """
        Calculates the score of the moves and sees what has the highest score
        search is used for me to get the raw values of score and rand, so i can see what percentage of chance each move has
        """
        """The AI always knows what item you're holding. It cheats to see it.

        The AI always knows your exact current HP and max HP.

        The AI does not know your moves until it sees you use them. Other methods that expose moves, such as Sleep Talk or the Forewarn
        ability, do not count.

        The AI does not know your ability until it sees a text box with the ability name, such as: "... makes ground moves miss using LEVITATE"
        , or "... FLASH FIRE made Flamethrower useless". If the AI does not know your ability, then most times it tries to check what your
        ability is, it will randomly guess one of the possible abilities your Pokémon's species can normally have. Abilities that modify
        damage but do not generate text, like Heatproof or Solid Rock, are not known to the AI even after damage is dealt. However, the AI
        is aware of the reduced damage that will be inflicted (e.g., for a Heatproof Bronzong, it will assume Levitate 50% of the time, but
        also will know that the Bronzong may survive a high-damage Fire attack that would KO if it had Levitate).

        Rarely, the AI must specifically see your ability, or your species must not have any other possible ability, in order for a check to
        succeed; these cases are worded as "If the target's ability is certainly...".

        There is one exception to this: the AI knows if your ability is Shadow Tag, Magnet Pull, or Arena Trap preventing it from switching.

        The AI always knows the attack order of all Pokémon on the field, barring speed ties or Quick Claws. It knows if there will be a
        speed tie, but does not know who will win it. If the AI is checking if it will attack before or after another target, and there
        is a speed tie, it will randomly guess the outcome of the tie. For any Pokémon on the field with a Quick Claw, it will randomly
        guess the Quick Claw will activate 20% of the time, independent of if the Quick Claw will actually activate.

        If you switch out, the AI will forget its knowledge of your moves and abilities.
        """
        move_scores = {}
        if self.current_pok_ab is True:
            ability = AbilityNames(user_pok[PokArray.AB_ID]).name
        else:
            try:
                ability = AbilityNames[random.choice(pkDB[user_pok.name]['abilities']).upper()].name
            except Exception:
                ability = AbilityNames(user_pok[PokArray.AB_ID]).name
        max_rand = 5
        rand = np.full((4, max_rand, 2), np.nan)
        max_damage = 0
        # Moves to not consider in damage calc
        # mov_excep = ['Razor Wind', 'Sky Attack', 'Recharge', 'Hyper Beam', 'Giga Impact',
        #             'Skull Bash', 'Solarbeam', 'Solar Blade', 'Spit Up', 'Superpower', 'Eruption', 'Water Spout',
        #             'Head Smash']
        mov_excep = [0, MoveName.EXPLOSION, MoveName.SELFDESTRUCT, MoveName.DREAM_EATER, MoveName.FOCUS_PUNCH,
                     MoveName.SUCKER_PUNCH]

        for i, move in enumerate((move1, move2, move3, move4)):

            if move[MoveArray.ID] == 0:
                break
            score = 0
            final_damage, _ = calculate_damage(ai_pok, user_pok, move)
            effectiveness = get_type_effectiveness(
                move[MoveArray.TYPE],
                user_pok[PokArray.TYPE1],
                user_pok[PokArray.TYPE2]
            )
            eval_atk, rand = self.evaluate_attack_flag(final_damage, effectiveness, user_pok, move, i, rand)
            score += eval_atk
            score += self.basic_flag(
                move, ability, ai_pok, user_pok, effectiveness, user_party_alive, ai_party_alive, turn
            )
            expert, rand = self.expert_flag(
                final_damage, effectiveness, ai_pok, user_pok, move, ai_party_alive, user_party_alive, turn, i, rand
            )
            score += expert

            # Find max damage among best moves
            if move[MoveArray.ID] not in mov_excep and final_damage > max_damage:
                max_damage = final_damage

            # TODO: Finish expert flag
            score += batch_independent_score_from_rand(rand, i)

            move_scores[i] = {"score": score, "dmg": final_damage, "idx": i}

        # Apply penalty for moves that don't reach max damage
        for i, move in enumerate((move1, move2, move3, move4)):
            if move[MoveArray.ID] not in mov_excep and move[MoveArray.CATEGORY] != MoveCategory.STATUS:
                if (
                    move_scores[i]['dmg'] < max_damage
                    and not move_scores[i]['dmg'] >= user_pok[PokArray.CURRENT_HP]
                ):
                    move_scores[i]["score"] -= 1

        return move_scores

    def return_idx(self, ai_pok, user_pok, user_party, ai_party, turn, move1, move2, move3, move4):
        """
        It transform the highest moving score to the index of the move
        """
        move_scores= self.choose_move(
            ai_pok, user_pok, user_party, ai_party, turn, move1, move2, move3, move4
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
          * If no Phase 1 candidate, for each non-fainted teammate compute the max damage any of its moves would do to user_pok
          (use calculate_damage). Apply the "255 overflow" rule: if damage > 255 -> damage = damage - 255.
          * Choose teammate with highest such max move damage. Ties broken by party order.

        Returns:
        -------
                index of chosen teammate in ai_party (int) or None if no valid candidate.

        """
        # filter non-fainted teammates and keep original party indices for tie-breaks
        candidates = np.where(ai_party[PokArray.CURRENT_HP:: len(PokArray)] > 0)[0].tolist()
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]

        # Phase 1: find mons that have at least one move that is SE (>1) vs user_pok
        phase1 = []
        for idx in candidates:
            pok = ai_party[(len(PokArray)*idx):(len(PokArray)*(idx + 1))]
            has_se_move = False
            m1 = pok[PokArray.MOVE1_ID:PokArray.MOVE2_ID]
            m2 = pok[PokArray.MOVE2_ID:PokArray.MOVE3_ID]
            m3 = pok[PokArray.MOVE3_ID:PokArray.MOVE4_ID]
            m4 = pok[PokArray.MOVE4_ID:PokArray.ITEM_ID]
            for mv in (m1, m2, m3, m4):
                mv_type = mv[MoveArray.TYPE]
                if mv_type == 0:
                    break
                eff = get_type_effectiveness(mv_type, user_pok[PokArray.TYPE1], user_pok[PokArray.TYPE2])
                if eff > 1:
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
                type1 = mon[PokArray.TYPE1]
                # single-typed counted twice
                type2 = mon[PokArray.TYPE2] if mon[PokArray.TYPE2] != 0 else mon[PokArray.TYPE1]
                total += get_type_effectiveness(type1, user_pok[PokArray.TYPE1], user_pok[PokArray.TYPE2])
                total += get_type_effectiveness(type2, user_pok[PokArray.TYPE1], user_pok[PokArray.TYPE2])
                if total == 8:
                    total = 1.75
                scored.append({'index': idx, 'mon': mon, 'score': total})

            # choose highest score, tie-break by party order (lower index wins)
            best = max(scored, key=lambda x: (x['score'], -x['index']))
            return best['index']

        # Phase 2: simulate moves as if used on the (full) user pok and pick mon with max single-move damage

        scored_phase2 = []
        for idx in candidates:
            mon = ai_party[(len(PokArray)*idx):(len(PokArray)*(idx + 1))]
            max_move_dmg = 0
            m1 = pok[PokArray.MOVE1_ID:PokArray.MOVE2_ID]
            m2 = pok[PokArray.MOVE2_ID:PokArray.MOVE3_ID]
            m3 = pok[PokArray.MOVE3_ID:PokArray.MOVE4_ID]
            m4 = pok[PokArray.MOVE4_ID:PokArray.ITEM_ID]
            for mv in (m1, m2, m3, m4):
                # build move object shape expected by calculate_damage
                try:
                    raw_dmg, _ = calculate_damage(deadmon, user_pok, mv, roll_multiplier=1)
                except Exception:
                    # if damage calc fails, skip move
                    continue
                # apply overflow bug: if damage > 255, it overflows by subtracting 255
                dmg = raw_dmg - 255 if raw_dmg > 255 else raw_dmg
                max_move_dmg = max(max_move_dmg, dmg)
            scored_phase2.append({'index': idx, 'max_dmg': max_move_dmg})

        if not scored_phase2:  # Defensive, shouldn't get here
            raise ValueError("Shouldn't get here, check flow of code, because at least one pok should be avaliable")

        # choose highest max_dmg, tie-break by party order (lower index wins)
        best2 = max(scored_phase2, key=lambda x: (x['max_dmg'], -x['index']))
        return best2['index']
