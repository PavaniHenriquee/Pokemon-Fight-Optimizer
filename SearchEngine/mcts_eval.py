"""Evaluation of terminal and current state"""
from Models.idx_nparray import PokArray
from Models.helper import count_party


# hyperparameters (tweak these)
ALPHA_DEATH = 1.6       # penalty per fainted Pokemon (strong)
BETA_HP = 0.8           # weight for HP advantage
GAMMA_WIN = 1.0         # extra bonus for winning (already covered by terminal)
MAX_POKEMON = 6

def party_hp_fraction(battle_array, offset):
    """Compute sum(current_hp / max_hp) across a party (0..6)"""
    total_frac = 0.0
    for i in range(6):
        start = offset + i * len(PokArray)
        curr = battle_array[start + PokArray.CURRENT_HP]
        mx = battle_array[start + PokArray.MAX_HP]
        if mx <= 0:
            frac = 0.0
        else:
            frac = max(0.0, curr) / mx
        total_frac += frac
    return total_frac / MAX_POKEMON  # normalized 0..1

def count_fainted(battle_array, offset):
    """ Opposite of count party"""
    fallen = 0
    for i in range(6):
        start = offset + i * len(PokArray)
        if battle_array[start + PokArray.CURRENT_HP] <= 0:
            fallen += 1
    return fallen

def evaluate_terminal(sim_state) -> float:
    """
    Terminal evaluation for MCTS backprop.
    - Win  => +1
    - Loss => -1
    - Otherwise combine: HP advantage minus heavy death penalty
    """
    # quick terminal check
    my_alive = count_party(sim_state.battle_array[0:(6 * len(PokArray))])
    opp_alive = count_party(sim_state.battle_array[(6 * len(PokArray)):(12 * len(PokArray))])

    if opp_alive == 0 and my_alive > 0:
        return +1.0
    if my_alive == 0 and opp_alive > 0:
        return -1.0

    # fallback (shouldn't happen for terminal): use state evaluator
    return evaluate_state(sim_state)

def evaluate_state(sim_state) -> float:
    """
    Non-terminal heuristic evaluation, return in [-1, 1].
    Combines: normalized HP advantage and per-death penalty.
    """
    battle = sim_state.battle_array

    my_hp_frac  = party_hp_fraction(battle, 0)
    opp_hp_frac = party_hp_fraction(battle, 6 * len(PokArray))

    # HP advantage in [-1, 1]
    hp_adv = my_hp_frac - opp_hp_frac   # range [-1, 1]

    # count fainted (0..6)
    my_fainted  = count_fainted(battle, 0)
    opp_fainted = count_fainted(battle, 6 * len(PokArray))

    # death penalty (player deaths hurt much more than opponent deaths help)
    death_score = (opp_fainted - ALPHA_DEATH * my_fainted) / MAX_POKEMON

    # combine
    raw = BETA_HP * hp_adv + death_score

    # squash to [-1, 1]
    return max(-1.0, min(1.0, raw))
