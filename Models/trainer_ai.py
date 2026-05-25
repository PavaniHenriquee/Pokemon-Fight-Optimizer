"""Gives the class for the trainer Ai to be what the game would do"""
import random
import numpy as np
from numba import njit
from Engine.damage_calc import calculate_damage, calculate_ai_logic_damage
from Utils.helper import (
    get_type_effectiveness, batch_independent_score_from_rand
)
from DataBase.MoveDB import MoveName, FIRE_WATER_ELECTRIC
from DataBase.PkDB import POKEMON_ABILITY_POOL
from Models.idx_const import (
    POK_LEN
)
from Models.constants import (
    _POK_MOVE1_ID, _POK_ITEM_ID, _POK_ID, _POK_AB_ID, _POK_CURRENT_HP, _POK_TYPE1,
    _POK_TYPE2, _ENEMY_AI_KNOWS_ABILITY, _MOVE_ID, _MOVE_PP, _MOVE_CATEGORY,
    _MOVECATEGORY_STATUS, _MOVE_TYPE, _ABILITYNAMES_WONDER_GUARD, _POK_STATUS,
    _STATUS_SLEEP, _ABILITYNAMES_NATURAL_CURE, _POK_MAX_HP, _POK_ATTACK_STAT_STAGE,
    _POK_EVASION_STAT_STAGE,_FIELD_OPP_POK, _FIELD_MY_POK, _FIELD_TURN, _FIELD_WEATHER,
    _FIELD_AI_KNOWS, _FIELD_MY_LAST_MOVE, _FIELD_AI_TOOK_DMG_LAST_TURN
)
from Models.trainer_ai_helper import (
    trainer_ai_effectiveness,
    POKEMON_HAS_RELEVANT_ABILITY,
    basic_flag,
    evaluate_attack_flag,
    expert_flag,
    check_super_ef_move_pty,
    check_any_damaging_move_pty,
    ABSORB_ABI,
    check_absorb_abi_pty,
    check_immunity_pty, check_resistence_pty
)

# mov_excep = ['Razor Wind', 'Sky Attack', 'Recharge', 'Hyper Beam', 'Giga Impact',
#             'Skull Bash', 'Solarbeam', 'Solar Blade', 'Spit Up', 'Superpower', 'Eruption',
#             'Water Spout','Head Smash']
MOVE_EXCEP = (
    0, MoveName.EXPLOSION, MoveName.SELFDESTRUCT, MoveName.DREAM_EATER,
    MoveName.FOCUS_PUNCH, MoveName.SUCKER_PUNCH
)


_RAND = np.zeros((4, 5, 2), dtype=np.int16)
_EVALUATED_MOVES = np.zeros((4,4),dtype=np.int16)
_BEST_MOVES = np.zeros(4, dtype=np.int16)


@njit
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
    candidates = np.where(ai_party[_POK_CURRENT_HP::off] > 0)[0]
    if len(candidates) == 1:
        return candidates[0]

    user_t1 = user_pok[_POK_TYPE1]
    user_t2 = user_pok[_POK_TYPE2]

    # Phase 1: collect indices of mons with at least one SE move
    phase1_indices = []
    for idx in candidates:
        pok = ai_party[off * idx: off * (idx + 1)]
        moves = pok[_POK_MOVE1_ID:_POK_ITEM_ID].reshape(4, -1)
        for mv in moves:
            mv_type = mv[_MOVE_TYPE]
            if mv_type == 0:
                break
            eff, den = get_type_effectiveness(mv_type, user_t1, user_t2)
            if eff // den >= 2:
                phase1_indices.append(idx)
                break

    if len(phase1_indices) > 0:
        # TODO: Check bugged list of Pokemon in document:
        # https://drive.google.com/file/d/1MpWJWc4wNTz2oA6QiPMmstLpSwHBlpRk/view
        # Score each mon by summing the effectiveness of each of its types vs user_pok
        if len(phase1_indices) == 1:
            return phase1_indices[0]

        # Score by type effectiveness, manual max (no key= in njit)
        best_idx = phase1_indices[0]
        best_score = -1.0
        for idx in phase1_indices:
            mon = ai_party[off * idx: off * (idx + 1)]
            t1 = mon[_POK_TYPE1]
            # single-typed counted twice
            t2 = mon[_POK_TYPE2] if mon[_POK_TYPE2] != 0 else mon[_POK_TYPE1]
            e1, d1 = get_type_effectiveness(t1, user_t1, user_t2)
            e2, d2 = get_type_effectiveness(t2, user_t1, user_t2)
            total = e1 / d1 + e2 / d2
            if total == 8.0:
                total = 1.75
            # Higher score wins; tie-break: lower index wins (idx < best_idx)
            if total > best_score or (total == best_score and idx < best_idx):
                best_score = total
                best_idx = idx
        return best_idx

    # Phase 2: pick mon with highest single-move damage
    user_hp = user_pok[_POK_CURRENT_HP]
    best_idx2 = candidates[0]
    best_dmg = -1
    for idx in candidates:
        mon = ai_party[off * idx: off * (idx + 1)]
        moves = mon[_POK_MOVE1_ID:_POK_ITEM_ID].reshape(4, -1)
        max_move_dmg = 0
        for mv in moves:
            if mv[_MOVE_ID] == 0:
                break
            if mv[_MOVE_CATEGORY] == _MOVECATEGORY_STATUS:
                continue
            raw_dmg = calculate_damage(deadmon, user_pok, mv, 0, False, 1)
            #overflow bug:
            dmg = raw_dmg - 255 if raw_dmg > 255 else raw_dmg
            dmg = min(dmg, user_hp)
            if dmg > max_move_dmg:
                max_move_dmg = dmg
        if max_move_dmg > best_dmg or (max_move_dmg == best_dmg and idx < best_idx2):
            best_dmg = max_move_dmg
            best_idx2 = idx
    return best_idx2


@njit
def choose_move(battle_array):
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
    opp_active = battle_array[_FIELD_OPP_POK]
    my_active = battle_array[_FIELD_MY_POK]
    ai_pok = battle_array[
        ((opp_active+6) * POK_LEN):((opp_active+7) * POK_LEN)
    ]
    user_pok = battle_array[
        (my_active * POK_LEN):((my_active+1) * POK_LEN)
    ]
    turn = battle_array[_FIELD_TURN]
    weather = battle_array[_FIELD_WEATHER]
    ai_know = battle_array[_FIELD_AI_KNOWS]
    my_last_move = battle_array[_FIELD_MY_LAST_MOVE]
    took_dmg = battle_array[_FIELD_AI_TOOK_DMG_LAST_TURN]
    ai_pty = battle_array[(6 * POK_LEN):(12 * POK_LEN)]
    # TODO: 1. Perish Song about to hit 0

    _EVALUATED_MOVES.fill(10)
    # Withdraw 5 - The active Pokémon is asleep and has the ability Natural Cure
    if (
        ai_pok[_POK_AB_ID] == _ABILITYNAMES_NATURAL_CURE
        and ai_pok[_POK_STATUS] == _STATUS_SLEEP
        and ai_pok[_POK_CURRENT_HP]/ai_pok[_POK_MAX_HP] >= 0.50
    ):
        if not took_dmg and random.getrandbits(1):
            sub = sub_after_death(ai_pty, user_pok, ai_pok)
            if sub == opp_active:
                pass
            else:
                _EVALUATED_MOVES[0] = [sub-6,0,0,False]
                return _EVALUATED_MOVES
        if took_dmg:
            im = check_immunity_pty(ai_pty, user_pok, took_dmg)
            if im.size > 0:
                _EVALUATED_MOVES[0] = [im[0]-6,0,0,False]
                return _EVALUATED_MOVES
            res = check_resistence_pty(ai_pty, user_pok, took_dmg)
            if res.size > 0:
                _EVALUATED_MOVES[0] = [res[0]-6,0,0,False]
                return _EVALUATED_MOVES
            if random.getrandbits(1):
                sub = sub_after_death(ai_pty, user_pok, ai_pok)
                _EVALUATED_MOVES[0] = [sub-6,0,0,False]
                return _EVALUATED_MOVES


    moves = ai_pok[_POK_MOVE1_ID:_POK_ITEM_ID].reshape(4, -1)

    ab=user_pok[_POK_AB_ID]
    if not POKEMON_HAS_RELEVANT_ABILITY[user_pok[_POK_ID]] or (ai_know & _ENEMY_AI_KNOWS_ABILITY):
        ability = ab
    else:
        pool_row = POKEMON_ABILITY_POOL[user_pok[_POK_ID]]
        ability = pool_row[random.getrandbits(1)]

    max_damage = 0

    _RAND.fill(0)
    s_e = False
    can_hit = False
    not_status_counter = 0

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
            not_status_counter +=1
            if s_e_check:
                s_e = True
            if effectiveness != 0:
                can_hit = True
        else:
            final_damage = 0

        eval_atk = evaluate_attack_flag(final_damage, effectiveness, user_pok, move, i, _RAND)
        score = eval_atk + basic_flag(move, ability, ai_pok, user_pok, effectiveness, weather)

        expert = expert_flag(ai_pok, user_pok, move, turn, i, _RAND, weather, my_last_move)
        score += expert

        is_damaging = move_id not in MOVE_EXCEP and not move_is_status
        if is_damaging and final_damage > max_damage:
            max_damage = final_damage

        score += batch_independent_score_from_rand(_RAND, i)

        # Append only what is necessary for the next step
        _EVALUATED_MOVES[i] = [i, score, final_damage, is_damaging]

    # Withdraw 2 - The active Pokémon is facing a foe with Wonder Guard and cannot hit it supereffectively
    cand = None
    if ab == _ABILITYNAMES_WONDER_GUARD and not s_e:
        cand = check_super_ef_move_pty(ai_pty, user_pok)
        if cand.size > 0:
            for i in cand:
                if random.random() < 0.66666:
                    _EVALUATED_MOVES.fill(10)
                    _EVALUATED_MOVES[0] = [i-6,0,0,False]
                    return _EVALUATED_MOVES

    # Withdraw 3 - More than 2 damaging moves and All of them do not affect the target
    if not_status_counter>1 and not can_hit:
        if not cand:
            cand = check_super_ef_move_pty(ai_pty, user_pok)
        if cand.size> 0:
            for i in cand:
                if random.random() < 0.888:
                    _EVALUATED_MOVES.fill(10)
                    _EVALUATED_MOVES[0] = [i-6,0,0,False]
                    return _EVALUATED_MOVES
        cand_normal = check_any_damaging_move_pty(ai_pty, user_pok)
        if cand_normal.size > 0:
            for i in cand_normal:
                if random.random() < 0.75:
                    _EVALUATED_MOVES.fill(10)
                    _EVALUATED_MOVES[0] = [i-6,0,0,False]
                    return _EVALUATED_MOVES

    # Withdraw 4 - The last move the active Pokémon was hit by in the last turn was Fire, Water,
    # or Electric-type, and a party Pokémon has the ability Flash Fire, Water Absorb, or Volt Absorb
    if my_last_move in FIRE_WATER_ELECTRIC and ai_pok[_POK_AB_ID] not in ABSORB_ABI:
        if s_e and random.random()<0.6666 and not took_dmg:
            pass
        else:
            cand_abi = check_absorb_abi_pty(ai_pty, my_last_move)
            if cand_abi.size > 0:
                for i in cand_abi:
                    if random.random() < 0.50:
                        _EVALUATED_MOVES.fill(10)
                        _EVALUATED_MOVES[0] = [i-6,0,0,False]
                        return _EVALUATED_MOVES


    # Before checking the final two situations to switch, check if:
    # - The current active Pokémon is able to damage at least one foe supereffectively.
    # This is checked by the move selection effectiveness check, with variable-type moves using
    # their correct types. Only damaging moves count.
    # - The total number of positive stat boosts that the active Pokémon has is greater than or equal to 4.
    if s_e or ai_pok[_POK_ATTACK_STAT_STAGE:(_POK_EVASION_STAT_STAGE + 1)].sum()>= 4:
        pass
    else:
        if took_dmg:
            # 6. A party member is immune to the previous attack and can hit the foe supereffectively
            if random.getrandbits(1):
                im = check_immunity_pty(ai_pty, user_pok, took_dmg)
                if im.size > 0:
                    _EVALUATED_MOVES.fill(10)
                    _EVALUATED_MOVES[0] = [im[0]-6,0,0,False]
                    return _EVALUATED_MOVES
            # 7. A party member resists the previous attack and can hit the foe supereffectively
            if random.random() < 0.3333:
                res = check_resistence_pty(ai_pty, user_pok, took_dmg)
                if res.size > 0:
                    _EVALUATED_MOVES.fill(10)
                    _EVALUATED_MOVES[0] = [res[0]-6,0,0,False]
                    return _EVALUATED_MOVES

    # Apply penalty only to the already-filtered valid moves
    current_hp = user_pok[_POK_CURRENT_HP]
    for info in _EVALUATED_MOVES:
        # info[3] is is_damaging_excep
        if info[3]:
            # info[2] is dmg
            if info[2] < max_damage and info[2] < current_hp:
                info[1] -= 1 # info[1] is score

    return _EVALUATED_MOVES


@njit
def return_idx(battle_array):
    """
    It transform the highest moving score to the index of the move
    """
    move_scores = choose_move(battle_array)

    max_score = -999999
    _BEST_MOVES.fill(100)
    n_best = 0


    for info in move_scores:
        if info[0] == 10:
            continue
        score = info[1]
        if score > max_score:
            max_score = score
            _BEST_MOVES[0] = info[0]
            n_best = 1
        elif score == max_score:
            _BEST_MOVES[n_best] = info[0]
            n_best += 1

    if n_best == 0:
        return 10  #Struggle
    if n_best == 1:
        return _BEST_MOVES[0]

    return _BEST_MOVES[random.randint(0, n_best - 1)]
