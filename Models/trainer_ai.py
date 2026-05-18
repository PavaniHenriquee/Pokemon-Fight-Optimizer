"""Gives the class for the trainer Ai to be what the game would do"""
import random
import numpy as np
from Engine.damage_calc import calculate_damage, calculate_ai_logic_damage
from Utils.helper import (
    get_type_effectiveness, batch_independent_score_from_rand
)
from DataBase.MoveDB import MoveName
from DataBase.PkDB import POKEMON_ABILITY_POOL
from Models.idx_const import (
    Pok, Move, POK_LEN
)
from Models.helper import (
    MoveCategory, Enemy_AI_Knows
)
from Models.trainer_ai_helper import (
    trainer_ai_effectiveness,
    POKEMON_HAS_RELEVANT_ABILITY,
    basic_flag,
    evaluate_attack_flag,
    expert_flag
)

# mov_excep = ['Razor Wind', 'Sky Attack', 'Recharge', 'Hyper Beam', 'Giga Impact',
#             'Skull Bash', 'Solarbeam', 'Solar Blade', 'Spit Up', 'Superpower', 'Eruption',
#             'Water Spout','Head Smash']
MOVE_EXCEP = [
    0, MoveName.EXPLOSION, MoveName.SELFDESTRUCT, MoveName.DREAM_EATER,
    MoveName.FOCUS_PUNCH, MoveName.SUCKER_PUNCH
]


def add_adjustment(arr, move_id, delta, chance):
    """Add a [delta, chance] pair to the first free slot."""
    # Find the first index where chance is NaN (unused)
    arr[move_id].append((delta, chance))

class TrainerAI:
    """
    Trainer AI, where it is used by using the def where it
    returns what the original ai would have done
    """

    def choose_move(
            self,
            ai_pok: np.ndarray[1,np.int32],
            user_pok,
            turn,
            weather,
            ai_know
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
        moves = ai_pok[Pok.MOVE1_ID:Pok.ITEM_ID].reshape(4, -1)

        pok_id = user_pok[Pok.ID]
        if not POKEMON_HAS_RELEVANT_ABILITY[pok_id] or (ai_know & Enemy_AI_Knows.ABILITY):
            ability = user_pok[Pok.AB_ID]
        else:
            ability = random.choice(POKEMON_ABILITY_POOL[pok_id])

        rand = [[] for _ in range(4)]
        max_damage = 0

        # Use a list to store valid moves instead of a dictionary
        evaluated_moves = []

        for i, move in enumerate(moves):
            # Cache NumPy scalar extractions locally to prevent repeated C-API calls
            move_id = move[Move.ID]
            if move_id == 0:
                break

            move_pp = move[Move.PP]
            if move_pp <= 0:
                continue

            move_category = move[Move.CATEGORY]
            move_is_status = move_category == MoveCategory.STATUS

            effectiveness = trainer_ai_effectiveness(move, ai_pok, user_pok)

            if not move_is_status:
                final_damage = calculate_ai_logic_damage(effectiveness, ai_pok, user_pok, move, weather)
            else:
                final_damage = 0

            eval_atk, rand = evaluate_attack_flag(final_damage, effectiveness, user_pok, move, i, rand)
            score = eval_atk + basic_flag(move, ability, ai_pok, user_pok, effectiveness, weather)

            expert, rand = expert_flag(ai_pok, user_pok, move, turn, i, rand, weather)
            score += expert

            # Check exceptions once
            is_damaging = move_id not in MOVE_EXCEP and not move_is_status
            if is_damaging and final_damage > max_damage:
                max_damage = final_damage

            score += batch_independent_score_from_rand(rand, i)

            # Append only what is necessary for the next step
            evaluated_moves.append([i, score, final_damage, is_damaging])

        # Apply penalty only to the already-filtered valid moves
        current_hp = user_pok[Pok.CURRENT_HP]
        for info in evaluated_moves:
            # info[3] is is_damaging_excep, info[4] is category
            if info[3]:
                # info[2] is dmg
                if info[2] < max_damage and info[2] < current_hp:
                    info[1] -= 1 # info[1] is score

        return evaluated_moves

    def return_idx(self, ai_pok, user_pok, turn, weather, ai_know):
        """
        It transform the highest moving score to the index of the move
        """
        move_scores = self.choose_move(ai_pok, user_pok, turn, weather, ai_know)

        # Single-pass max check and collection (eliminates generator and list comprehensions)
        max_score = -float('inf')
        best_moves = []

        for info in move_scores:
            score = info[1]
            if score > max_score:
                max_score = score
                best_moves = [info[0]]
            elif score == max_score:
                best_moves.append(info[0])

        # Fallback in case no moves are valid (prevents random.choice index errors)
        if not best_moves:
            return 10 # Struggle

        if len(best_moves) == 1:
            return best_moves[0]

        return random.choice(best_moves)

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
                eff, den = get_type_effectiveness(mv_type, user_pok[Pok.TYPE1], user_pok[Pok.TYPE2])
                if eff//den >= 2:
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
