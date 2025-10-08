"""Evaluation of terminal and current state"""
import random
from Models.idx_const import(
    Pok, Sec, POK_LEN, OFFSET_MOVE, MOVE_STRIDE, OFFSET_SEC
)
from Models.helper import count_party, count_Id
from Engine.damage_calc import calculate_damage


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
    opp_alive = count_party(sim_state.battle_array[(6 * POK_LEN):(12 * POK_LEN)])
    dead = my_pty_count - my_alive
    if dead:
        win_value = (my_alive / my_pty_count)* 0.7
    else:
        win_value = 1.0

    if opp_alive == 0 and my_alive > 0:
        return win_value, 1, dead
    if my_alive == 0:
        return 0.0, 0, dead

    raise ValueError("Shouldn't get here")


def rollout_pref(c_pok, o_pok, o_idx, actions) -> tuple:
    """Prefer certain moves to reduce noise"""
    ev = []

    for a in actions:
        o_move = o_pok[OFFSET_MOVE + o_idx * MOVE_STRIDE: OFFSET_MOVE + o_idx * MOVE_STRIDE + MOVE_STRIDE]
        o_dmg, _ = calculate_damage(o_pok, c_pok, o_move)
        weight = 1
        if a[0] == 'move':
            move = c_pok[OFFSET_MOVE + a[1] * MOVE_STRIDE: OFFSET_MOVE + a[1] * MOVE_STRIDE + MOVE_STRIDE]
            dmg, _ = calculate_damage(c_pok, o_pok, move)
            if (
                dmg >= o_pok[Pok.CURRENT_HP]
                and (
                    c_pok[Pok.SPEED] > o_pok[Pok.SPEED]
                    or o_dmg < c_pok[Pok.CURRENT_HP]
                )
            ):
                weight += 100
            if move[OFFSET_SEC + Sec.CHANCE]:
                weight += 10
        else:
            # Need to work on that, because it need to be way more complex
            if (
                o_dmg >= c_pok[Pok.CURRENT_HP]
                and (
                    o_pok[Pok.SPEED] >= c_pok[Pok.SPEED]
                )
            ):
                weight += 50
        ev.append((a, weight))

    return random.choices([e[0] for e in ev], weights=[e[1] for e in ev])[0]
