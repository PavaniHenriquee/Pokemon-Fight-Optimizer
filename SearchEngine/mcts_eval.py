"""Evaluation of terminal and current state"""
import random
import numpy as np
from numba import njit
from Models.idx_const import(
    Pok, POK_LEN, OFFSET_MOVE, MOVE_STRIDE, Field
)
from Models.constants import (
    _FIELD_MY_POK, _FIELD_OPP_POK, _FIELD_WEATHER, _POK_CURRENT_HP, _POK_MAX_HP,
    _POK_SPEED, _MOVE_TYPE, _ACTIONTYPE_MOVE, _MOVECATEGORY_STATUS, _MOVE_CATEGORY,
    _POK_TYPE1, _POK_TYPE2, _MOVE_POWER, _SEC_CHANCE
)
from Models.helper import count_party, count_Id
from Models.trainer_ai_helper import check_immunity_pty, check_resistence_pty
from Engine.damage_calc import calculate_damage, struggle
from Utils.helper import get_type_effectiveness


def party_hp_fraction(battle_array, offset, maxp):
    """Compute sum(current_hp / max_hp) across a party (0..6)"""
    total_frac = 0.0
    for i in range(maxp):
        start = offset + i * POK_LEN
        curr = battle_array[start + Pok.CURRENT_HP]
        mx = battle_array[start + Pok.MAX_HP]
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

'''def evaluate_terminal(sim_state) -> tuple[float, int, int]:
    """
    Terminal evaluation for MCTS backprop with strictly segregated reward tiers.
    Guaranteed Win (0-death) > Guaranteed Win (Casualties) > Incomplete Rollout > Loss
    """
    my_pty_count = count_Id(sim_state.battle_array[0:(6 * POK_LEN)])
    my_alive = count_party(sim_state.battle_array[0:(6 * POK_LEN)])
    opp_alive = count_party(sim_state.battle_array[(6 * POK_LEN):(12 * POK_LEN)])
    dead = my_pty_count - my_alive

    # 1. ACTUAL VICTORY
    if opp_alive == 0 and my_alive > 0:
        # Base value starts at 0.50 for winning, and scales up to 1.0 based on survival
        # 6/6 alive = 1.0 | 5/6 alive = 0.916 | 1/6 alive = 0.583
        win_value = 0.36 + (0.64 * (my_alive / my_pty_count)**2)

        # Turn penalty is tightly constrained (max 0.05) so it can NEVER
        # cross the gap between survival counts (which is 0.50 / 6 = 0.0833)
        turn = sim_state.battle_array[Field.TURN]
        turn_penalty = min(0.05, turn * 0.0005)

        return win_value - turn_penalty, 1, dead

    # 2. ACTUAL LOSS / DRAW
    if my_alive == 0:
        return 0.0, 0, dead

    # 3. INCOMPLETE ROLLOUT (Max Depth Reached)
    # Scaled to exist strictly between 0.01 and 0.35
    opp_pty_count = count_Id(sim_state.battle_array[(6 * POK_LEN):(12 * POK_LEN)])
    my_hp = party_hp_fraction(sim_state.battle_array, 0, my_pty_count)
    opp_hp = party_hp_fraction(sim_state.battle_array, 6 * POK_LEN, opp_pty_count)

    heuristic = my_hp / (my_hp + opp_hp + 1e-9)
    incomplete_value = 0.01 + (heuristic * 0.34)  # Range: 0.01 to 0.35

    return incomplete_value, 0, dead
'''
def evaluate_terminal(sim_state) -> tuple[float, int, int]:
    """
    Terminal evaluation for MCTS backprop.
    - Win  => +1
    - Loss => 0
    - draw => 0
    """
    # quick terminal check
    my_pty_count = count_Id(sim_state.battle_array[0:(6 * POK_LEN)])
    my_alive = count_party(sim_state.battle_array[0:(6 * POK_LEN)])
    dead = my_pty_count - my_alive
    if my_alive == 0:
        return 0.0, 0, dead
    opp_alive = count_party(sim_state.battle_array[(6 * POK_LEN):(12 * POK_LEN)])
    if dead:
        win_value = 0.65 - (0.1*dead)
    else:
        win_value = 1.0

    if opp_alive == 0 and my_alive > 0:
        turn = sim_state.battle_array[Field.TURN]
        turn_penalty = min(0.10, turn * 0.0005)  # caps at 0.1, never flips a win
        return win_value-turn_penalty, 1, dead

    # Fallback to if the game haven't finished yet, but max depth reached
    opp_pty_count = count_Id(sim_state.battle_array[(6 * POK_LEN):(12 * POK_LEN)])
    my_hp = party_hp_fraction(sim_state.battle_array, 0, my_pty_count)
    opp_hp = party_hp_fraction(sim_state.battle_array, 6 * POK_LEN, opp_pty_count)
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
    imnty = IMNTY.copy()
    res = RES.copy()
    # Arbitrary number to accomadate when i died and need to switch, so AI don't have an action
    if opp_choice is None:
        opp_choice = -50

    if opp_choice != 10 and opp_choice>=0:  # Struggle
        o_move = o_pok[OFFSET_MOVE + opp_choice * MOVE_STRIDE: OFFSET_MOVE + (opp_choice + 1) * MOVE_STRIDE]
        o_dmg = calculate_damage(o_pok, c_pok, o_move, weather, False, 100)  # still worth it for 1 calc
        o_mv_type = o_move[_MOVE_TYPE]
        imnty = check_immunity_pty(my_pty, o_pok, o_mv_type, my_idx)
        res   = check_resistence_pty(my_pty, o_pok, o_mv_type, my_idx)
    elif opp_choice < 0:  # Switch or potion
        o_dmg = 0
    else:
        o_dmg = struggle(o_pok, c_pok, rec=False)
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
                # Status moves: give a small base weight so they're not excluded
                weight = 1

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
                        dmg = calculate_damage(c_pok, o_pok, move, weather)
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
