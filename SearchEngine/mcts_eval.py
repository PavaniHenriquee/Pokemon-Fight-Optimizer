"""Evaluation of terminal and current state"""
import random
import numpy as np
from Utils.jit import njit
from Utils.helper import get_type_effectiveness
from Models.idx_const import(
    Pok, POK_LEN, OFFSET_MOVE, MOVE_STRIDE, SIDE_TOXIC_SPIKES
)
from Models.constants import (
    _FIELD_MY_POK, _FIELD_OPP_POK, _FIELD_WEATHER, _POK_CURRENT_HP, _POK_MAX_HP,
    _POK_SPEED, _MOVE_TYPE, _ACTIONTYPE_MOVE, _MOVECATEGORY_STATUS, _MOVE_CATEGORY,
    _POK_TYPE1, _POK_TYPE2, _MOVE_POWER, _SEC_CHANCE, _FIELD_TURN, _FIELD_PHASE,
    _BATTLEPHASE_DEATH_END_OF_TURN, _FIELD_MY_SIDE_COND, _FIELD_OPP_SIDE_COND, _MOVE_ID,
    _MOVE_SIDE_CONDITION, _MOVE_TARGET, _SIDECONDITION_TOXIC_SPIKES
)
from Models.helper import count_party, count_Id
from Models.trainer_ai_helper import check_immunity_pty, check_resistance_pty
from Models.trainer_ai import return_idx
from SearchEngine.models import valid_actions_array, is_terminal_arr, step_arr
from Engine.damage_calc import calculate_damage
from Engine.engine_helper import calculate_crit, struggle
from Engine.battle import _move_weather, FOE_SIDE_TARGET, TOXIC_SPIKES_MAX


@njit
def party_hp_fraction(battle_array, offset, maxp):
    """Compute sum(current_hp / max_hp) across a party (0..6)"""
    total_frac = 0.0
    for i in range(maxp):
        start = offset + i * POK_LEN
        curr = battle_array[start + _POK_CURRENT_HP]
        mx = battle_array[start + _POK_MAX_HP]
        if mx <= 0:
            frac = 0.0
        else:
            frac = max(0.0, curr) / mx
        total_frac += frac
    return total_frac / maxp  # normalized 0..1

def count_fainted(battle_array, offset, maxp):
    """ Opposite of count party"""
    fallen = 0
    for i in range(maxp):
        start = offset + i * POK_LEN
        if battle_array[start + Pok.CURRENT_HP] <= 0:
            fallen += 1
    return fallen


@njit
def evaluate_terminal(battle_array):
    """
    Terminal evaluation for MCTS backprop.
    - Loss => 0
    - draw => 0
    - Win starts at 1
    - Win value gets reduced value for each death, where 1 its a heavy penalty and each death
    after that is a linear small value
    - Win values gets a small penalty for larger number of turns, so it don't stall unnecessarily
    """
    my_pty = battle_array[0:(6 * POK_LEN)]
    opp_pty = battle_array[(6 * POK_LEN):(12 * POK_LEN)]
    my_pty_count = count_Id(my_pty)
    my_alive = count_party(my_pty)
    dead = my_pty_count - my_alive
    if my_alive == 0:
        return 0.0, 0, dead
    opp_alive = count_party(opp_pty)
    if dead:
        win_value = 0.67 - (0.1 * dead)
    else:
        win_value = 1.0

    if opp_alive == 0:
        turn = battle_array[_FIELD_TURN]
        turn_penalty = min(0.10, turn * 0.0005)
        return win_value - turn_penalty, 1, dead

    # Fallback to if the game haven't finished yet, but max depth reached
    opp_pty_count = count_Id(opp_pty)
    my_hp = party_hp_fraction(battle_array, 0, my_pty_count)
    opp_hp = party_hp_fraction(battle_array, 6 * POK_LEN, opp_pty_count)
    heuristic = my_hp / (my_hp + opp_hp + 1e-9)  # 0..1 continuous
    return heuristic * 0.35, 0, dead


@njit
def _weighted_choice(act_types, act_idxs, weights, n):
    best_i = 0
    best_w = weights[0]
    total  = weights[0]
    for i in range(1, n):
        total += weights[i]
        if weights[i] > best_w:
            best_w = weights[i]
            best_i = i

    if best_w >= total * 0.90:
        return act_types[best_i], act_idxs[best_i]

    r = random.randrange(total)
    cum = 0
    for i in range(n):
        cum += weights[i]
        if r < cum:
            return act_types[i], act_idxs[i]
    return act_types[n - 1], act_idxs[n - 1]  # safety fallback


@njit
def field_move_fails(move, battle_array):
    """My side or weather move that would do nothing: already up, Toxic Spikes at max layers,
    or the same weather"""
    cond = move[_MOVE_SIDE_CONDITION]
    if cond:
        side = _FIELD_OPP_SIDE_COND if move[_MOVE_TARGET] == FOE_SIDE_TARGET else _FIELD_MY_SIDE_COND
        if cond == _SIDECONDITION_TOXIC_SPIKES:
            return battle_array[side + SIDE_TOXIC_SPIKES] >= TOXIC_SPIKES_MAX
        return (battle_array[side] & cond) != 0
    move_weather = _move_weather(move[_MOVE_ID])
    return move_weather != 0 and move_weather == battle_array[_FIELD_WEATHER]


IMNTY = np.full(6,-1, dtype=np.int16)
RES   = np.full(6,-1, dtype=np.int16)


@njit
def rollout_pref(battle_array, opp_choice, actions) -> tuple:
    """
    Prefer certain moves to reduce noise
    """
    my_idx = battle_array[_FIELD_MY_POK]
    opp_idx = battle_array[_FIELD_OPP_POK]
    c_pok = battle_array[
        (my_idx * POK_LEN):
        ((my_idx+1) * POK_LEN)
    ]
    o_pok = battle_array[
        ((opp_idx+6) * POK_LEN):
        ((opp_idx+7) * POK_LEN)
    ]
    my_pty = battle_array[0:(6 * POK_LEN)]
    weather = battle_array[_FIELD_WEATHER]
    my_side = battle_array[_FIELD_MY_SIDE_COND]
    opp_side = battle_array[_FIELD_OPP_SIDE_COND]
    imnty = IMNTY.copy()
    res = RES.copy()
    # Arbitrary number to accommodate when i died and need to switch, so AI don't have an action
    if opp_choice is None:
        opp_choice = -50

    if opp_choice != 10 and opp_choice>=0:  # Struggle
        o_move = o_pok[OFFSET_MOVE + opp_choice * MOVE_STRIDE: OFFSET_MOVE + (opp_choice + 1) * MOVE_STRIDE]
        o_dmg = calculate_damage(
            o_pok, c_pok, o_move, weather, calculate_crit(o_pok, c_pok, o_move, my_side), None,
            my_side
        )
        o_mv_type = o_move[_MOVE_TYPE]
        imnty = check_immunity_pty(my_pty, o_pok, o_mv_type, my_idx)
        res   = check_resistance_pty(my_pty, o_pok, o_mv_type, my_idx)
    elif opp_choice < 0:  # Switch or potion
        o_dmg = 0
    else:
        o_dmg = struggle(o_pok, c_pok, False, my_side)
    opp_hp_ratio = o_pok[_POK_CURRENT_HP] * 4 // o_pok[_POK_MAX_HP]
    faster = c_pok[_POK_SPEED] > o_pok[_POK_SPEED]
    can_survive = o_dmg < c_pok[_POK_CURRENT_HP]
    act_types = np.empty(10, dtype=np.int16)
    act_idxs  = np.empty(10, dtype=np.int16)
    weights   = np.empty(10, dtype=np.int32)
    n_ev = 0

    for i in range(len(actions)):
        a_type = actions[i, 0]
        a_idx  = actions[i, 1]
        weight = np.int32(1)


        if a_type == _ACTIONTYPE_MOVE:
            if a_idx == 10:
                continue
            move = c_pok[OFFSET_MOVE + a_idx * MOVE_STRIDE: OFFSET_MOVE + (a_idx + 1) * MOVE_STRIDE]
            cat = move[_MOVE_CATEGORY]

            if cat == _MOVECATEGORY_STATUS:
                # Status moves: give a small base weight so they're not excluded,
                # unless it's a side or weather move that would fail
                weight = 0 if field_move_fails(move, battle_array) else 1

            else:
                # Cheap type effectiveness first — no damage calc
                move_type = move[_MOVE_TYPE]
                eff, den = get_type_effectiveness(move_type, o_pok[_POK_TYPE1], o_pok[_POK_TYPE2])
                eff_ratio = eff // den

                if eff_ratio == 0:
                    weight = 0  # immune — never pick this
                else:
                    # STAB bonus
                    stab = move_type == c_pok[_POK_TYPE1] or move_type == c_pok[_POK_TYPE2]

                    # Only do full damage calc if it looks like a KO candidate
                    likely_strong = (
                        eff_ratio >= 2                          # super effective
                        or (stab and move[_MOVE_POWER] >= 60)   # strong STAB
                        or (opp_hp_ratio == 0 and eff_ratio >= 1 and opp_choice > 0)  # <25% HP, non-resisted
                        or (opp_hp_ratio == 1 and eff_ratio >= 1 and stab)  # <50% HP, STAB neutral
                    )

                    if likely_strong:
                        dmg = calculate_damage(c_pok, o_pok, move, weather, False, None, opp_side)
                        if dmg >= o_pok[_POK_CURRENT_HP] and (faster or can_survive):
                            weight = 100  # KO when safe to do so
                        elif eff_ratio == 4:
                            weight = 30
                        elif eff_ratio == 2:
                            weight = 15
                        elif stab:
                            weight = 4
                    else:
                        # Resisted or neutral, no calc — rough signal only
                        if eff_ratio == 1:
                            weight = 2 if stab else 1
                        else:  # 0.5x
                            weight = 1

                    # Secondary effect scaled by chance
                    if move[_SEC_CHANCE]:
                        weight += move[_SEC_CHANCE] // 10

        else:  # switch
            if o_dmg >= c_pok[_POK_CURRENT_HP] and not faster:
                # Get hp from switching — only consider if it helps survive
                switch_hp = battle_array[(a_idx) * POK_LEN + _POK_CURRENT_HP]
                if switch_hp > o_dmg:
                    if a_idx in imnty:
                        weight = 110
                    elif a_idx in res:
                        weight = 80
                    else:
                        weight = 50

        if weight > 0:
            act_types[n_ev] = a_type
            act_idxs[n_ev]  = a_idx
            weights[n_ev]   = weight
            n_ev += 1

    if n_ev == 0:
        r = random.randint(0, len(actions) - 1)
        return actions[r, 0], actions[r, 1]

    return _weighted_choice(act_types, act_idxs, weights, n_ev)


@njit
def rollout_arr(battle_array, max_depth=100, heuristic_prob=0.48):
    """
    Mixed rollout fully in njit, plays on battle_array in place: sometimes uses the
    rollout heuristic, sometimes a random action, then evaluates the final state.
    Returns (value, win, dead)
    """
    depth = 0
    while depth < max_depth and not is_terminal_arr(battle_array):
        actions = valid_actions_array(battle_array)
        n = len(actions)
        if n == 0:
            break

        if battle_array[_FIELD_PHASE] == _BATTLEPHASE_DEATH_END_OF_TURN:
            opp_move = -50  # Death phase, only my replacement is chosen
        else:
            opp_move = return_idx(battle_array)

        if random.random() < heuristic_prob:
            act = rollout_pref(battle_array, opp_move, actions)
            a_type = act[0]
            a_idx = act[1]
        else:
            r = random.randrange(n)
            a_type = actions[r, 0]
            a_idx = actions[r, 1]

        step_arr(battle_array, int(a_type), int(a_idx), opp_move)
        depth += 1
    return evaluate_terminal(battle_array)
