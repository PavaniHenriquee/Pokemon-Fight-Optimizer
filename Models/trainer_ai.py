"""Gives the class for the trainer Ai to be what the game would do"""
import random
import numpy as np
from numba import njit
from Engine.damage_calc import calculate_damage, calculate_ai_logic_damage
from Utils.helper import (
    get_type_effectiveness, batch_independent_score_from_rand
)
from DataBase.MoveDB import MoveName
from DataBase.PkDB import POKEMON_ABILITY_POOL
from Models.idx_const import (
    POK_LEN
)
from Models.constants import (
    _POK_MOVE1_ID, _POK_ITEM_ID, _POK_ID, _POK_AB_ID, _POK_CURRENT_HP, _POK_TYPE1,
    _POK_TYPE2, _ENEMY_AI_KNOWS_ABILITY, _MOVE_ID, _MOVE_PP, _MOVE_CATEGORY,
    _MOVECATEGORY_STATUS, _MOVE_TYPE, _ABILITYNAMES_WONDER_GUARD
)
from Models.trainer_ai_helper import (
    trainer_ai_effectiveness,
    POKEMON_HAS_RELEVANT_ABILITY,
    basic_flag,
    evaluate_attack_flag,
    expert_flag,
    check_super_ef_move_pty
)

# mov_excep = ['Razor Wind', 'Sky Attack', 'Recharge', 'Hyper Beam', 'Giga Impact',
#             'Skull Bash', 'Solarbeam', 'Solar Blade', 'Spit Up', 'Superpower', 'Eruption',
#             'Water Spout','Head Smash']
MOVE_EXCEP = (
    0, MoveName.EXPLOSION, MoveName.SELFDESTRUCT, MoveName.DREAM_EATER,
    MoveName.FOCUS_PUNCH, MoveName.SUCKER_PUNCH
)


@njit
def choose_move(
        ai_pok,
        user_pok,
        turn,
        weather,
        ai_know,
        my_last_move,
        ai_pty
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
    # TODO: withdraw checks
    # 1. Perish Song about to hit 0
    # 3. More than 2 damaging moves and All of them do not affect the target
    # 4. The last move the active Pokémon was hit by in the last turn was Fire, Water, or Electric-type,
    # and a party Pokémon has the ability Flash Fire, Water Absorb, or Volt Absorb, respectively
    # 5. The active Pokémon is asleep and has the ability Natural Cure
    # Before checking the final two situations to switch, check if:
    # . The current active Pokémon is able to damage at least one foe supereffectively.
    # This is checked by the move selection effectiveness check, with variable-type moves using
    # their correct types. Only damaging moves count.
    # . The total number of positive stat boosts that the active Pokémon has is greater than or equal to 4.
    # 6. A party member is immune to the previous attack and can hit the foe supereffectively
    # 7. A party member resists the previous attack and can hit the foe supereffectively

    moves = ai_pok[_POK_MOVE1_ID:_POK_ITEM_ID].reshape(4, -1)

    ab=user_pok[_POK_AB_ID]
    if not POKEMON_HAS_RELEVANT_ABILITY[user_pok[_POK_ID]] or (ai_know & _ENEMY_AI_KNOWS_ABILITY):
        ability = ab
    else:
        pool_row = POKEMON_ABILITY_POOL[user_pok[_POK_ID]]
        ability = pool_row[random.getrandbits(1)]

    rand = np.zeros((4, 5, 2), dtype=np.int64)
    max_damage = 0

    evaluated_moves = []
    s_e = False

    for i, move in enumerate(moves):
        # Cache NumPy scalar extractions locally to prevent repeated C-API calls
        move_id = move[_MOVE_ID]
        if move_id == 0:
            break

        move_pp = move[_MOVE_PP]
        if move_pp < 1:
            continue

        move_category = move[_MOVE_CATEGORY]
        move_is_status = move_category == _MOVECATEGORY_STATUS

        effectiveness, s_e_check = trainer_ai_effectiveness(move, ai_pok, user_pok)

        if not move_is_status:
            final_damage = calculate_ai_logic_damage(effectiveness, ai_pok, user_pok, move, weather)
            if s_e_check:
                s_e = True
        else:
            final_damage = 0

        eval_atk, rand = evaluate_attack_flag(final_damage, effectiveness, user_pok, move, i, rand)
        score = eval_atk + basic_flag(move, ability, ai_pok, user_pok, effectiveness, weather)

        expert, rand = expert_flag(ai_pok, user_pok, move, turn, i, rand, weather, my_last_move)
        score += expert

        is_damaging = move_id not in MOVE_EXCEP and not move_is_status
        if is_damaging and final_damage > max_damage:
            max_damage = final_damage

        score += batch_independent_score_from_rand(rand, i)

        # Append only what is necessary for the next step
        evaluated_moves.append([i, score, final_damage, is_damaging])

    if ab == _ABILITYNAMES_WONDER_GUARD and not s_e:
        cand = check_super_ef_move_pty(ai_pty, user_pok)
        if cand:
            for i in cand:
                if random.random() < 0.66666:
                    return [[i-6,0,0,False]]



    # Apply penalty only to the already-filtered valid moves
    current_hp = user_pok[_POK_CURRENT_HP]
    for info in evaluated_moves:
        # info[3] is is_damaging_excep
        if info[3]:
            # info[2] is dmg
            if info[2] < max_damage and info[2] < current_hp:
                info[1] -= 1 # info[1] is score

    return evaluated_moves


@njit
def return_idx(ai_pok, user_pok, turn, weather, ai_know, my_last_move, ai_pty):
    """
    It transform the highest moving score to the index of the move
    """
    move_scores = choose_move(ai_pok, user_pok, turn, weather, ai_know, my_last_move, ai_pty)

    max_score = -999999
    best_moves = np.zeros(4, dtype=np.int32)
    n_best = 0

    if len(move_scores) == 0:
        return 10  # Struggle
    if len(move_scores) == 1:
        return move_scores[0][0]

    for info in move_scores:
        score = info[1]
        if score > max_score:
            max_score = score
            best_moves[0] = info[0]
            n_best = 1
        elif score == max_score:
            best_moves[n_best] = info[0]
            n_best += 1


    if n_best == 1:
        return best_moves[0]

    return best_moves[random.randint(0, n_best - 1)]


def sub_after_death(ai_party, user_pok, deadmon):
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
    candidates = np.where(ai_party[_POK_CURRENT_HP:: off] > 0)[0]
    if len(candidates) == 1:
        return candidates[0]

    # Phase 1: find mons that have at least one move that is SE (>1) vs user_pok
    phase1 = []
    user_t1 = user_pok[_POK_TYPE1]
    user_t2 = user_pok[_POK_TYPE2]
    for idx in candidates:
        pok = ai_party[(off*idx):(off*(idx + 1))]
        has_se_move = False
        moves = pok[_POK_MOVE1_ID:_POK_ITEM_ID].reshape(4, -1)
        for mv in moves:
            mv_type = mv[_MOVE_TYPE]
            if mv_type == 0:
                break
            eff, den = get_type_effectiveness(mv_type, user_t1, user_t2)
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
            type1 = mon[_POK_TYPE1]
            # single-typed counted twice
            type2 = mon[_POK_TYPE2] if mon[_POK_TYPE2] != 0 else mon[_POK_TYPE1]
            effec, den = get_type_effectiveness(type1, user_t1, user_t2)
            total = effec/den
            effec, den = get_type_effectiveness(type2, user_t1, user_t2)
            total += effec/den
            if total == 8:
                total = 1.75
            scored.append([idx, total])

        # choose highest score, tie-break by party order (lower index wins)
        best = max(scored, key=lambda x: (x[1], -x[0]))
        return best[0]

    # Phase 2: simulate moves as if used on the (full)
    # user pok and pick mon with max single-move damage

    scored_phase2 = []
    user_hp = user_pok[_POK_CURRENT_HP]
    for idx in candidates:
        mon = ai_party[(off*idx):(off*(idx + 1))]
        max_move_dmg = 0
        moves = mon[_POK_MOVE1_ID:_POK_ITEM_ID].reshape(4, -1)
        for mv in moves:
            if mv[_MOVE_ID] == 0:
                break
            # build move object shape expected by calculate_damage
            try:
                raw_dmg = calculate_damage(deadmon, user_pok, mv, 0, False, 1)
            except Exception:
                # if damage calc fails, skip move
                continue
            # apply overflow bug: if damage > 255, it overflows by subtracting 255
            dmg = raw_dmg - 255 if raw_dmg > 255 else raw_dmg
            dmg = min(dmg, user_hp)
            max_move_dmg = max(max_move_dmg, dmg)
        scored_phase2.append((idx, max_move_dmg))

    # choose highest max_dmg, tie-break by party order (lower index wins)
    best2 = max(scored_phase2, key=lambda x: (x[1], -x[0]))
    return best2[0]
