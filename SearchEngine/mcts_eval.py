"""Evaluation of terminal and current state"""
import random
from Models.idx_nparray import PokArray, BaseArray, AbilityIdx, MoveArray, MoveFlags, SecondaryArray
from Models.helper import count_party
from Engine.damage_calc import calculate_damage


# hyperparameters (tweak these)
ALPHA_DEATH = 1.6       # penalty per fainted Pokemon (strong)
BETA_HP = 0.8           # weight for HP advantage
GAMMA_WIN = 1.0         # extra bonus for winning (already covered by terminal)

def party_hp_fraction(battle_array, offset, maxp):
    """Compute sum(current_hp / max_hp) across a party (0..6)"""
    total_frac = 0.0
    for i in range(maxp):
        start = offset + i * len(PokArray)
        curr = battle_array[start + PokArray.CURRENT_HP]
        mx = battle_array[start + PokArray.MAX_HP]
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
        start = offset + i * len(PokArray)
        if battle_array[start + PokArray.CURRENT_HP] <= 0:
            fallen += 1
    return fallen

def evaluate_terminal(sim_state) -> float:
    """
    Terminal evaluation for MCTS backprop.
    - Win  => +1
    - Loss => -1
    - draw => 0
    """
    # quick terminal check
    my_alive = count_party(sim_state.battle_array[0:(6 * len(PokArray))])
    opp_alive = count_party(sim_state.battle_array[(6 * len(PokArray)):(12 * len(PokArray))])

    if opp_alive == 0 and my_alive > 0:
        return +1.0
    if my_alive == 0 and opp_alive > 0:
        return -1.0

    # Rare draw case (both 0)
    return 0.0

def evaluate_state(sim_state, root) -> float:
    """
    Non-terminal heuristic evaluation, return in [-1, 1].
    Combines: normalized HP advantage and per-death penalty.
    """
    battle = sim_state.battle_array

    # Total Pokemon
    my_max = count_party(root.state.my_pty)
    opp_max = count_party(root.state.opp_pty)

    my_hp_frac  = party_hp_fraction(battle, 0, my_max)
    opp_hp_frac = party_hp_fraction(battle, 6 * len(PokArray), opp_max)

    # HP advantage in [-1, 1]
    hp_adv = my_hp_frac - opp_hp_frac   # range [-1, 1]

    # count fainted (0..6)
    my_fainted  = count_fainted(battle, 0, my_max)
    opp_fainted = count_fainted(battle, 6 * len(PokArray), my_max)

    # death penalty (player deaths hurt much more than opponent deaths help)
    death_score = (opp_fainted - ALPHA_DEATH * my_fainted) / ((my_max+opp_max) / 2)

    value = BETA_HP * hp_adv + death_score
    return value


def rollout_pref(c_pok, o_pok, o_idx, actions) -> tuple:
    """Prefer certain moves to reduce noise"""
    off = len(BaseArray) + len(AbilityIdx)
    off_ma = len(MoveArray)
    off_m = off_ma + len(MoveFlags) + len(SecondaryArray)
    ev = []

    for a in actions:
        o_move = o_pok[off + o_idx * off_m: off + o_idx * off_m + off_m]
        o_dmg, _ = calculate_damage(o_pok, c_pok, o_move)
        weight = 1
        if a[0] == 'move':
            move = c_pok[off + a[1] * off_m: off + a[1] * off_m + off_m]
            dmg, _ = calculate_damage(c_pok, o_pok, move)
            if (
                dmg >= o_pok[PokArray.CURRENT_HP]
                and (
                    c_pok[PokArray.SPEED] > o_pok[PokArray.SPEED]
                    or o_dmg < c_pok[PokArray.CURRENT_HP]
                )
            ):
                weight += 100
            if move[off_ma + len(MoveFlags) + SecondaryArray.CHANCE]:
                weight += 10
        else:
            # Need to work on that, because it need to be way more complex
            if (
                o_dmg >= c_pok[PokArray.CURRENT_HP]
                and (
                    o_pok[PokArray.SPEED] >= c_pok[PokArray.SPEED]
                )
            ):
                weight += 50
        ev.append((a, weight))

    return random.choices([e[0] for e in ev], weights=[e[1] for e in ev])[0]
