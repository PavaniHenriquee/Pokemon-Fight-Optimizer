"""Gives the class for the trainer Ai to be what the game would do"""
import random
import math
import numpy as np
from Engine.damage_calc import calculate_damage
from Utils.helper import get_type_effectiveness, batch_independent_score_from_rand, stage_to_multiplier
from DataBase.loader import pkDB
from DataBase.MoveDB import MoveName
from DataBase.AbilitiesDB import AbilityNames
from Models.idx_nparray import MoveArray, PokArray, MoveFlags
from Models.helper import MoveCategory, Types, Status, VolStatus, Gender, Target


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

    def basic_flag(self, move, ability, ai_pok, user_pok, effectiveness, user_party_alive, ai_party_alive, turn) -> int:
        """
        Basic Flag, every trainer has this, it discourages moves that would have no effect or that would make no sense
        """
        basic = 0
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
        # Check for immunity types
        if move[MoveArray.CATEGORY] != MoveCategory["STATUS"] and effectiveness == 0:
            return -10
        # Check for abilities
        if ai_pok[PokArray.AB_ID] != AbilityNames["MOLD_BREAKER"]:
            if move[MoveArray.TYPE] == Types["ELECTRIC"] and ability in ("VOLT_ABSORB", "MOTOR_DRIVE"):
                return -10
            if move[MoveArray.TYPE] == Types["WATER"] and ability == "WATER_ABSORB":
                return -10
            if move[MoveArray.TYPE] == Types["FIRE"] and ability == "FLASH_FIRE":
                return -10
            if move[MoveArray.TYPE] == Types["GROUND"] and ability == "LEVITATE":
                return -10
            if move[len(MoveArray) + MoveFlags.SOUND] and ability == "SOUNDPROOF":
                return -10
            if (
                effectiveness < 2 and ability == "WONDER_GUARD"
                and move[MoveArray.CATEGORY] != MoveCategory["STATUS"]
            ):
                return -10
        if move[MoveArray.CATEGORY] == MoveCategory["STATUS"]:
            # TODO: Safeguard for all conditions
            if move[MoveArray.STATUS] != 0:
                # Sleep
                if (
                    move[MoveArray.STATUS] == Status["SLEEP"]
                    and (
                        user_pok[PokArray.STATUS] != 0
                        or ability == "VITAL_SPIRIT"
                    )
                ):
                    return -10
                # Poison
                if (
                    move[MoveArray.STATUS] in (Status["POISON"], Status["TOXIC"])
                    and (
                        user_pok[PokArray.STATUS] != 0
                        or ability in ("IMMUNITY", "MAGIC_GUARD", "POISON_HEAL")
                        or Types["STEEL"] in (user_pok[PokArray.TYPE1], user_pok[PokArray.TYPE2])
                        or Types["POISON"] in (user_pok[PokArray.TYPE1], user_pok[PokArray.TYPE2])
                    )
                ):
                    # TODO: weather
                    return -10
                # Paralysis
                if (
                    move[MoveArray.STATUS] == Status["PARALYSIS"]
                    and (
                        user_pok[PokArray.STATUS] != 0
                        or (
                            move[MoveArray.TYPE] == Types["ELECTRIC"]
                            and (
                                Types["GROUND"] in (user_pok[PokArray.TYPE1], user_pok[PokArray.TYPE2])
                                or (
                                    ability in ('VOLT_ABSORB', 'MOTOR_DRIVE')
                                    and ai_pok[PokArray.AB_ID] != AbilityNames["MOLD_BREAKER"]
                                ) 
                            )
                        )
                        or ability in ('LIMBER', 'MAGIC_GUARD')
                    )
                ):
                    return -10
                # Burn
                if (
                    move[MoveArray.STATUS] == Status["BURN"]
                    and (
                        user_pok[PokArray.STATUS] != 0
                        or ability in ("WATER_VEIL", "MAGIC_GUARD")
                        or Types["FIRE"] in (user_pok[PokArray.TYPE1], user_pok[PokArray.TYPE2])
                    )
                ):
                    return -10
            if move[MoveArray.VOL_STATUS] != 0:
                # Confusion
                if move[MoveArray.VOL_STATUS] == VolStatus["CONFUSION"]:
                    if user_pok[PokArray.VOL_STATUS] & VolStatus["CONFUSION"]:
                        return -5
                    if ability == "OWN_TEMPO":
                        return -10
                # Attract
                if move[MoveArray.VOL_STATUS] == VolStatus["ATTRACT"]:
                    if (
                        user_pok[PokArray.VOL_STATUS] & VolStatus["ATTRACT"]
                        or ability == "OBLIVIOUS"
                        or (
                            user_pok[PokArray.GENDER] == ai_pok[PokArray.GENDER]
                            or user_pok[PokArray.GENDER] == Gender['GENDERLESS']
                        )
                    ):
                        return -10
            if any(move[MoveArray.BOOST_ATK: MoveArray.BOOST_EV + 1]):
                # Stat Boosting Moves
                if move[MoveArray.TARGET] in (
                    Target['ADJACENT_ALLY'],
                    Target['ADJACENT_ALLY_OR_SELF'],
                    Target['ALLIES'],
                    Target['ALLY_SIDE'],
                    Target['SELF']
                ):
                    # TODO Trick room
                    if (
                        ai_pok[PokArray.AB_ID] == AbilityNames["NO_GUARD"]
                        and (
                            move[MoveArray.BOOST_ACC] > 0 or move[MoveArray.BOOST_EV] > 0
                        )
                    ):
                        return -10
                    if ai_pok[PokArray.AB_ID] == AbilityNames["SIMPLE"]:
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
                    Target['NORMAL'],
                    Target['ADJACENT_FOE'],
                    Target['ALL_ADJACENT_FOES'],
                    Target['ANY'],
                    Target['FOE_SIDE'],
                    Target['RANDOM_NOTMAL'],
                    Target['SCRIPTED']
                ):
                    # TODO Trick Room
                    if move[MoveArray.BOOST_ATK] and ability == "HYPER_CUTTER":
                        return -10
                    if move[MoveArray.BOOST_SPEED] and ability == "SPEED_BOOST":
                        return -10
                    if (
                        (move[MoveArray.BOOST_ACC] or move[MoveArray.BOOST_EV])
                        and (ability == "NO_GUARD" or ai_pok[PokArray.AB_ID] == AbilityNames["NO_GUARD"])
                    ):
                        return -10
                    if move[MoveArray.BOOST_ACC] and ai_pok[PokArray.AB_ID] == AbilityNames["KEEN_EYE"]:
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
            if effect_type == "force_switch" and (len(user_party_alive) > 1 or (ability == 'Suction Cups' and ai_pok.ability['name'] == "Mold Breaker")):
                basic.append(-10)
            # Recovery Moves
            if effect_type == "recovery" and ai_pok.current_hp == ai_pok.max_hp:
                basic.append(-10)
            # OH-KO
            if effect_type == "oh_ko" and ((ability == "Sturdy" and ai_pok.ability['name'] == "Mold Breaker") or user_pok.level > ai_pok.level):
                basic.append(-10)

        # Explosion / Selfdestruct
        if move["name"] == "Selfdestruct" or move["name"] == "Explosion":
            if effectiveness == 0 or (ability == "Damp" and ai_pok.ability["name"] != "Mold Breaker"):
                basic.append(-10)
            if len(ai_party_alive) == 1:
                if len(user_party_alive) == 1:
                    basic.append(-1)
                else:
                    basic.append(-10)
        # Dream Eater
        if move["name"] == "Dream Eater":
            if user_pok.status != "Sleep":
                basic.append(-8)
            elif effectiveness == 0:
                basic.append(-10)
        # Belly Drum
        if move["name"] == "Belly Drum" and math.floor((ai_pok.current_hp / ai_pok.max_hp * 100)) <= 51:
            basic.append(-10)
        # Substitute
        if move["name"] == "Substitute":
            if ai_pok.substitute:
                basic.append(-8)
            elif (ai_pok.current_hp / ai_pok.max_hp) * 100 < 26:
                basic.append(-10)
        # Leech Seed
        if move['name'] == "Leech Seed" and (user_pok.leech_seed or 'Grass' in user_pok.types or ability == "Magic Guard"):
            basic.append(-10)
        # Snore / Sleep Talk
        if (move['name'] == "Snore" or move['name'] == "Sleep Talk") and ai_pok.status != "sleep":
            basic.append(-8)
        # Curse
        if move['name'] == "Curse":
            if "Ghost" in ai_pok.types:
                if user_pok.curse:
                    basic.append(-10)
            elif (ai_pok.ability['name'] == 'Simple' and (ai_pok.stat_stages['Attack'] >= 2 or ai_pok.stat_stages['Defense'] >= 2)) or (ai_pok.stat_stages['Attack'] >= 6 or ai_pok.stat_stages['Defense'] >= 6):
                basic.append(-10)
        # Baton Pass
        if move['name'] == "Baton Pass" and len(ai_party_alive) <= 1:
            basic.append(-10)
        # Helping Hand (Change when doubles)
        if move['name'] == "Helping Hand":
            basic.append(-10)
        # Trick / Switcheroo / Knock Off
        if (move['name'] == "Trick" or move['name'] == "Switcheroo" or move['name'] == "Knock Off") and ability == 'Sticky Hold':
            basic.append(-10)
        # Refresh
        if move['name'] == "Helping Hand" and (ai_pok.status != "burn" and ai_pok.status != "paralysis" and ai_pok.status != "poison"):
            basic.append(-10)
        # Tickle
        if move['name'] == "Tickle":
            if (ability == "Clear Body" or ability == "White Smoke") or ai_pok.stat_stages['Attack'] >= 6:
                basic.append(-10)
            elif ai_pok.stat_stages['Defense'] >= 6:
                basic.append(-8)
        # Acupressure
        if move['name'] == "Acupressure":
            for s in ai_pok.stat_stages:
                acupressure_check = True if s >= 6 else False
                if ai_pok.ability['name'] == "Simple" and s >= 3:
                    acupressure_check = True
                if acupressure_check:
                    basic.append(-10)
                    break
        # Metal Burst
        if move['name'] == "Acupressure" and (ability == "Stall" or user_pok.item['name'] == "Shiny Stone" or move_first):
            basic.append(-10)
        # Copycat
        if move['name'] == 'Copycat' and turn == 1:
            basic.append(-10)
        # Power Swap
        if move['name'] == 'Power Swap' and (ai_pok.stat_stages['Attack'] > user_pok.stat_stages['Attack'] or ai_pok.stat_stages['Special Attack'] > user_pok.stat_stages['Special Attack']):
            basic.append(-10)
        # Guard Swap
        if move['name'] == 'Guard Swap' and (ai_pok.stat_stages['Defense'] > user_pok.stat_stages['Defense'] or ai_pok.stat_stages['Special Defense'] > user_pok.stat_stages['Special Defense']):
            basic.append(-10)
        # Worry Seed (need to implement if know about Snore and Sleep Talk)
        if move['name'] == 'Worry Seed' and ability in ['Truant', 'Insomnia', 'Vital Spirit', 'Multitype']:
            basic.append(-10)
        # Captivate
        if move['name'] == 'Captivate' and ((ability in ['Oblivious', 'Clear Body', 'White Smoke'] and ai_pok.ability['name'] != 'Mold Breaker') or (user_pok.gender == ai_pok.gender or not user_pok.gender) or user_pok.stat_stages['Special Attack'] <= -6):
            basic.append(-10)

        '''
        TODO: 
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

        return min(basic) if basic else 0

    def evaluate_attack_flag(self, final_damage, effectiveness, user_pok, move, idx, rand) -> tuple[int, dict]:
        """
        For damage moves it sees if it kill and some move exceptions then add to score
        For non-damaging moves it checks if its 4x effective, for some reason
        """
        score = 0
        # Check for kill
        if final_damage >= user_pok[PokArray.CURRENT_HP]:
            if move[MoveArray.ID] in (MoveName["EXPLOSION"], MoveName["SELFDESTRUCT"]):
                score += 0
            elif move[MoveArray.ID] in (MoveName['SUCKER_PUNCH'], MoveName['FOCUS_PUNCH'], MoveName['FUTURE_SIGHT']):
                add_adjustment(rand, idx, 4, 85)
                return score, rand
            elif move[MoveArray.PRIORITY] >= 1 and move[MoveArray.ID] != MoveName['FAKE_OUT']:
                score = 6
                return score, rand
            else:
                score = 4
                return score, rand

        if (
            move[MoveArray.ID] in (
                MoveName['SUCKER_PUNCH'],
                MoveName['FOCUS_PUNCH'],
                MoveName['EXPLOSION'],
                MoveName["SELFDESTRUCT"]
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
        hp_pct_ai = math.floor(ai_pok.current_hp / ai_pok.max_hp * 100)
        hp_pct_u = math.floor(u_pok.current_hp / u_pok.max_hp * 100)
        m_name = move['name']
        effects = move['effects']
        category = move['category']
        # Check if move first (TODO add Trick room logic here)
        ai_speed_stage = get_stage(ai_pok, 'Speed')
        u_speed_stage = get_stage(u_pok, 'Speed')
        ai_speed = ai_pok.speed * stage_to_multiplier(ai_speed_stage)
        u_speed = u_pok.speed * stage_to_multiplier(u_speed_stage)
        if ai_speed > u_speed:
            move_first = True
        elif ai_speed < u_speed:
            move_first = False
        else:
            move_first = random.choice([True, False])
        if category == "Status":
            for e in effects:
                status = e.get("status", 0)
                stat_change = e.get('stat', 0)
                effect_type = e.get('effect_type', 0)
                target = e.get('target', 0)
                if effect_type == 'status_inducing':
                    # Poison-Inducing
                    if status == 'poison' and (hp_pct_ai < 50 or hp_pct_u <= 50) and m_name != 'Toxic':
                        score = -1
                        return score, rand
                    for m in ai_pok.moves:
                        # Sleep-Inducing
                        if status == 'sleep' and (m['name'] in ['Dream Eater', 'Nightmare']):
                            rand[idx]['score'].append(1)
                            rand[idx]['chance'].append(128)
                            return score, rand
                    # Paralyzing-Inducing
                    if status == 'paralysis' and not move_first:
                        rand[idx]['score'].append(3)
                        rand[idx]['chance'].append(236)
                        return score, rand
                if effect_type == 'volatile_status':
                    # Confusion-Inducing
                    if status == 'confusion':
                        if m_name == 'Swagger':
                            psych_up = False
                            for m in ai_pok.moves:
                                if m['name'] == 'Psych Up':
                                    psych_up = True
                            if psych_up:
                                if u_pok.stat_stages['Attack'] <= -3:
                                    if turn == 1:
                                        score += 5
                                    else:
                                        score += 3
                                else:
                                    score += -5
                                return score, rand
                        if m_name == 'Flatter' or m_name == 'Swagger':
                            rand[idx]['score'].append(-1)
                            rand[idx]['chance'].append(128)
                        if hp_pct_u <= 70:
                            rand[idx]['score'].append(-1)
                            rand[idx]['chance'].append(128)
                            if hp_pct_u <= 30:
                                score += -1
                            if hp_pct_u <= 50:
                                score += -1
                        return score, rand
                if effect_type == 'stat_change':
                    # Stat-Boosting moves
                    atk = ['Attack', 'Special Attack']
                    de = ['Defense', 'Special Defense']
                    if target == 'self':
                        for a in atk:
                            if stat_change == a:
                                if ai_pok.stat_stages[a] >= 3:
                                    rand[idx]['score'].append(-1)
                                    rand[idx]['chance'].append(156)
                                if hp_pct_ai >= 100:
                                    rand[idx]['score'].append(2)
                                    rand[idx]['chance'].append(128)
                                elif hp_pct_ai >= 71:
                                    break
                                elif hp_pct_ai > 39:
                                    rand[idx]['score'].append(-2)
                                    rand[idx]['chance'].append(186)
                                else:
                                    score += -2
                                return score, rand
                        for d in de:
                            if stat_change == d:
                                if ai_pok.stat_stages[d] >= 3:
                                    rand[idx]['score'].append(-1)
                                    rand[idx]['chance'].append(156)
                                if hp_pct_ai >= 100:
                                    rand[idx]['score'].append(2)
                                    rand[idx]['chance'].append(128)
                                elif hp_pct_ai >= 71:
                                    break
                                elif hp_pct_ai > 39:
                                    rand[idx]['score'].append(-2)
                                    rand[idx]['chance'].append(186)
                                else:
                                    score += -2
                                # TODO: Target last-used move
                                return score, rand
                        if stat_change == 'Speed' and m_name != "Dragon Dance":
                            if move_first:
                                score += -3
                            else:
                                rand[idx]['score'].append(3)
                                rand[idx]['chance'].append(186)
                            return score, rand
                        if stat_change == 'Evasion':
                            if hp_pct_ai > 89:
                                rand[idx]['score'].append(3)
                                rand[idx]['chance'].append(186)
                            if ai_pok.stat_stages['Evasion'] >= 3:
                                rand[idx]['score'].append(-1)
                                rand[idx]['chance'].append(128)
                            if u_pok.badly_poison:
                                if hp_pct_ai > 50:
                                    rand[idx]['score'].append(3)
                                    rand[idx]['chance'].append(206)
                                else:
                                    rand[idx]['score'].append(3)
                                    rand[idx]['chance'].append(142)
                            if u_pok.leech_seed:
                                rand[idx]['score'].append(3)
                                rand[idx]['chance'].append(186)
                            if u_pok.curse:
                                rand[idx]['score'].append(3)
                                rand[idx]['chance'].append(186)
                            if hp_pct_ai > 70 or u_pok.stat_stages['Evasion'] == 0:
                                return score, rand
                            elif hp_pct_ai < 40 or hp_pct_u < 40:
                                score += -2
                                return score, rand
                            else:
                                rand[idx]['score'].append(-2)
                                rand[idx]['chance'].append(186)
                            # TODO: Ingrain, Aqua Ring
                    if target in ['target', 'all_adjacent_opponents']:
                        # Attack and Special Attack
                        if stat_change in atk:
                            for a in atk:
                                if u_pok.stat_stages[a] != 0:
                                    score += -1
                                if hp_pct_ai <= 90:
                                    score += -1
                                if u_pok.stat_stages[a] <= -3:
                                    rand[idx]['score'].append(-2)
                                    rand[idx]['chance'].append(206)
                                if hp_pct_u <= 70:
                                    score += -2
                                # TODO: Last move check: If the move last used by the target was not of the corresponding
                                # class (Physical/Special), 50% chance of score -2.
                                return score, rand
                        # Defense and Special Defense
                        if stat_change in de:
                            for d in de:
                                if hp_pct_ai < 70:
                                    rand[idx]['score'].append(-2)
                                    rand[idx]['chance'].append(206)
                                if u_pok.stat_stages[d] <= -3:
                                    rand[idx]['score'].append(-2)
                                    rand[idx]['chance'].append(206)
                                if hp_pct_u < 70:
                                    score += -2
                                return score, rand
                        # Speed
                        if stat_change == 'Speed':
                            if not move_first:
                                rand[idx]['score'].append(2)
                                rand[idx]['chance'].append(186)
                            else:
                                score += -3
                            return score, rand
                        # Accuracy
                        if stat_change == 'Accuracy':
                            if hp_pct_u <= 70 and not hp_pct_ai >= 70:
                                rand[idx]['score'].append(-1)
                                rand[idx]['chance'].append(156)
                            if ai_pok.stat_stages['Accuracy'] <= -2:
                                rand[idx]['score'].append(-2)
                                rand[idx]['chance'].append(176)
                            if u_pok.badly_poison:
                                rand[idx]['score'].append(2)
                                rand[idx]['chance'].append(186)
                            if u_pok.leech_seed:
                                rand[idx]['score'].append(2)
                                rand[idx]['chance'].append(186)
                            if u_pok.curse:
                                rand[idx]['score'].append(2)
                                rand[idx]['chance'].append(186)
                            if hp_pct_ai >= 70 or u_pok.stat_stages['Accuracy'] == 0:
                                return score, rand
                            else:
                                if hp_pct_ai <= 40 or hp_pct_u <= 40:
                                    score += -2
                                else:
                                    rand[idx]['score'].append(-2)
                                    rand[idx]['chance'].append(186)
                                return score, rand
                            # TODO: Ingrain, Aqua Ring
                        # Evasion
                        if stat_change == 'Evasion':
                            if hp_pct_ai < 70:
                                rand[idx]['score'].append(-2)
                                rand[idx]['chance'].append(206)
                            if u_pok.stat_stages['Evasion'] <= -3:
                                rand[idx]['score'].append(-2)
                                rand[idx]['chance'].append(206)
                            if hp_pct_u <= 70:
                                score += -2
                            return score, rand

        # Moves Ignoring Accuracy (e.g. Aerial Ace, Shock Wave)
        if not isinstance(move['accuracy'], int):
            if ai_pok.stat_stages['Accuracy'] <= -5 or u_pok.stat_stages['Evasion'] >= 5:
                score += 1
            if ai_pok.stat_stages['Accuracy'] <= -3 or u_pok.stat_stages['Evasion'] >= 3:
                rand[idx]['score'].append(1)
                rand[idx]['chance'].append(156)
            return score, rand

        # Selfdestruct, explosion, memento
        if m_name in ['Selfdestruct', 'Explosion', 'Memento']:
            if u_pok.stat_stages['Evasion'] >= 1:
                score += -1
            if u_pok.stat_stages['Evasion'] >= 3:
                rand[idx]['score'].append(-1)
                rand[idx]['chance'].append(128)
            if hp_pct_ai <= 30:
                rand[idx]['score'].append(1)
                rand[idx]['chance'].append(206)
                return score, rand
            elif hp_pct_ai <= 50:
                rand[idx]['score'].append(1)
                rand[idx]['chance'].append(128)
                return score, rand
            else:
                if hp_pct_ai > 80 and move_first:
                    rand[idx]['score'].append(-3)
                    rand[idx]['chance'].append(206)
                else:
                    rand[idx]['score'].append(-1)
                    rand[idx]['chance'].append(206)
            return score, rand
        # Healing Wish, Lunar Dance
        if m_name in ['Healing Wish', 'Lunar Dance']:
            if hp_pct_ai >= 80 and move_first:
                rand[idx]['score'].append(-5)
                rand[idx]['chance'].append(64)
                return score, rand
            if hp_pct_ai > 50:
                rand[idx]['score'].append(-1)
                rand[idx]['chance'].append(206)
                return score, rand
            if random.randint(0, 255) < 64:
                score += 1
                ef = False
                for m in ai_pok.moves:
                    if m['category'] != 'Status':
                        effc = get_type_effectiveness(m['type'], u_pok.types)
                        if effc > 1:
                            ef = True
                if not ef:
                    rand[idx]['score'].append(1)
                    rand[idx]['chance'].append(64)
            if hp_pct_ai <= 30:
                rand[idx]['score'].append(1)
                rand[idx]['chance'].append(128)
            return score, rand
        # Dragon Dance
        if m_name == 'Dragon Dance':
            if not move_first:
                rand[idx]['score'].append(1)
                rand[idx]['chance'].append(128)
                return score, rand
            if hp_pct_ai <= 50:
                rand[idx]['score'].append(-1)
                rand[idx]['chance'].append(186)
                return score, rand
        # Acupressure
        if m_name == 'Acupressure':
            if hp_pct_ai <= 50:
                score += -1
                return score, rand
            if hp_pct_ai > 90:
                rand[idx]['score'].append(1)
                rand[idx]['chance'].append(192)
                return score, rand
            rand[idx]['score'].append(1)
            rand[idx]['chance'].append(96)
            return score, rand
        # a

        """
        TODO:
            Draining Attacks
            Mirror Move

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
        move_scores = {}
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
        if self.current_pok_ab is True:
            ability = AbilityNames(user_pok[PokArray.AB_ID]).name
        else:
            try:
                ability = AbilityNames[random.choice(pkDB[user_pok.name]['abilities']).upper()].name
            except Exception:
                ability = AbilityNames(user_pok[PokArray.AB_ID]).name
        max_rand = 5
        rand = np.full((4, max_rand, 2), np.nan)

        for i, move in enumerate((move1, move2, move3, move4)):

            score = 0
            final_damage, _ = calculate_damage(ai_pok, user_pok, move)
            effectiveness = get_type_effectiveness(
                move[MoveArray.TYPE],
                user_pok[PokArray.TYPE1],
                user_pok[PokArray.TYPE2]
            )
            eval_atk, rand = self.evaluate_attack_flag(final_damage, effectiveness, user_pok, move, i, rand)
            score += eval_atk
            score += self.basic_flag(move, ability, ai_pok, user_pok, effectiveness, user_party_alive, ai_party_alive, turn)
            eval_expert, rand = self.expert_flag(final_damage, effectiveness, ai_pok, user_pok, move, ai_party_alive, user_party_alive, turn, i, rand)
            score += eval_expert

            # TODO: Finish expert flag
            score += batch_independent_score_from_rand(rand, i)

            move_scores[i] = {"score": score, "dmg": final_damage, "idx": i}

        # Moves to not consider in damage calc
        mov_excep = ['Explosion', 'Selfdestruct', 'Dream Eater', 'Razor Wind', 'Sky Attack', 'Recharge', 'Hyper Beam', 'Giga Impact',
                     'Skull Bash', 'Solarbeam', 'Solar Blade', 'Spit Up', 'Focus Punch', 'Superpower', 'Eruption', 'Water Spout',
                     'Sucker Punch', 'Head Smash']

        # Find max damage among best moves
        max_damage = max(info["dmg"] for info in move_scores.values() if ai_pok.moves[info["idx"]]['name'] not in mov_excep)

        # Apply penalty for moves that don't reach max damage
        for info in move_scores.values():
            if (ai_pok.moves[info["idx"]]['name'] not in mov_excep) and ai_pok.moves[info["idx"]]['category'] != 'Status':
                if info["dmg"] < max_damage and not info['dmg'] > user_pok.current_hp:
                    info["score"] -= 1

        return move_scores, rand

    def return_idx(self, ai_pok, user_pok, user_party_alive, ai_party_alive, turn):
        """
        It transform the highest moving score to the index of the move
        """
        move_scores, _ = self.choose_move(ai_pok, user_pok, user_party_alive, ai_party_alive, turn)
        max_score = max(info["score"] for info in move_scores.values())
        best_moves = [info for info in move_scores.values() if info["score"] == max_score]
        if len(best_moves) == 1:
            idx = best_moves[0]['idx']
        else:
            choice = random.choice(best_moves)
            idx = choice['idx']
        return idx

    def sub_after_death(self, ai_party, user_pok, deadmon):
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
        candidates = [(i, mon) for i, mon in enumerate(ai_party) if not getattr(mon, 'fainted', False)]
        if not candidates:
            return None

        # Helper to read pokemon types robustly
        def pokemon_types(mon):
            # prefer attribute .types, fallback to base_data structure
            t = getattr(mon, 'types', None)
            if t:
                return t
            bd = getattr(mon, 'base_data', None)
            if bd:
                return bd.get('types', []) or bd.get('Type', []) or []
            return []

        # Phase 1: find mons that have at least one move that is SE (>1) vs user_pok
        phase1 = []
        for idx, mon in candidates:
            has_se_move = False
            for mv in getattr(mon, 'moves', []):
                mv_type = mv.get('type') if isinstance(mv, dict) else getattr(mv, 'type', None)
                if mv_type is None:
                    continue
                try:
                    eff = get_type_effectiveness(mv_type, getattr(user_pok, 'types', []))
                except Exception:
                    # if helper fails, skip this move
                    continue
                if eff > 1:
                    has_se_move = True
                    break
            if has_se_move:
                phase1.append((idx, mon))

        if phase1:
            # Score each mon by summing the effectiveness of each of its types vs user_pok
            scored = []
            for idx, mon in phase1:
                types = pokemon_types(mon)
                # single-typed counted twice
                if len(types) == 1:
                    types = [types[0], types[0]]
                # defensively handle missing types
                types = types[:2] + ([] if len(types) >= 2 else [])
                total = 0.0
                for t in types:
                    try:
                        total += get_type_effectiveness(t, getattr(user_pok, 'types', []))
                    except Exception:
                        total += 1.0
                if total == 8:
                    total = 1.75
                scored.append({'index': idx, 'mon': mon, 'score': total})

            # choose highest score, tie-break by party order (lower index wins)
            best = max(scored, key=lambda x: (x['score'], -x['index']))
            return best['index']

        # Phase 2: simulate moves as if used on the (full) user pok and pick mon with max single-move damage
        # Determine "full HP" for user_pok: prefer max_hp, fallback to base stat 'HP', else current_hp
        full_hp = getattr(user_pok, 'max_hp', None)
        if full_hp is None:
            bd = getattr(user_pok, 'base_data', {})
            full_hp = bd.get('base stats', {}).get('HP', None) if isinstance(bd, dict) else None
        if full_hp is None:
            full_hp = getattr(user_pok, 'current_hp', 0)

        scored_phase2 = []
        for idx, mon in candidates:
            max_move_dmg = 0
            for mv in getattr(mon, 'moves', []):
                # build move object shape expected by calculate_damage
                try:
                    raw_dmg, _ = calculate_damage(deadmon, user_pok, mv, roll_multiplier=1)
                except Exception:
                    # if damage calc fails, skip move
                    continue
                # apply overflow bug: if damage > 255, it overflows by subtracting 255
                dmg = raw_dmg - 255 if raw_dmg > 255 else raw_dmg
                if dmg > max_move_dmg:
                    max_move_dmg = dmg
            scored_phase2.append({'index': idx, 'mon': mon, 'max_dmg': max_move_dmg})

        if not scored_phase2:
            return None

        # choose highest max_dmg, tie-break by party order (lower index wins)
        best2 = max(scored_phase2, key=lambda x: (x['max_dmg'], -x['index']))
        return best2['index']
