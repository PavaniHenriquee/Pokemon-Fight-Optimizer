"""Actual run-through"""
import itertools
from Models.trainer_ai import TrainerAI


def search_best_move(my_pty, ai_pty, cur_pok, cur_opp_pok, turn):
    """
    Returns a dict like {move_idx: {'move': move_idx, 'chance': percent_float}, ...}
    Assumes ai_rand_scores uses independent Bernoulli sub-events where chance is out of 256.
    Ties are split uniformly (50/50 for two-way ties, etc).
    """

    denom = 256
    opp_ai = TrainerAI()
    ai_m_scores, ai_rand_scores = opp_ai.choose_move(cur_opp_pok, cur_pok, my_pty, ai_pty, turn, search=True)

    def pmf_for_move(base, vals, chances):
        """Build exact PMF for a move given independent (value, chance) pairs."""
        pmf = {0: 1.0}  # contribution-only pmf
        for v, c in zip(vals, chances):
            p = c / denom
            new = {}
            for s, prob in pmf.items():
                # event does NOT occur
                new[s] = new.get(s, 0.0) + prob * (1 - p)
                # event occurs, add v
                new[s + v] = new.get(s + v, 0.0) + prob * p
            pmf = new
        # shift by base deterministic score
        return {s + base: prob for s, prob in pmf.items()}

    # build PMFs for each move
    pmfs = {}
    for idx, base_info in ai_m_scores.items():
        base = base_info.get('score', 0)
        rand = ai_rand_scores.get(idx, {'score': [], 'chance': []})
        vals = list(rand.get('score', []))
        chances = list(rand.get('chance', []))
        if not vals:
            pmfs[idx] = {base: 1.0}
        else:
            pmfs[idx] = pmf_for_move(base, vals, chances)

    moves = sorted(pmfs.keys())
    outcomes_per_move = [list(pmfs[m].items()) for m in moves]

    # enumerate joint outcomes across moves and accumulate choice probabilities
    choice_probs = {m: 0.0 for m in moves}
    for combo in itertools.product(*outcomes_per_move):
        # combo: ((value,prob), (value,prob), ...)
        vals = [v for v, p in combo]
        probs = [p for v, p in combo]
        joint_prob = 1.0
        for p in probs:
            joint_prob *= p
        if joint_prob == 0:
            continue
        max_val = max(vals)
        winners = [i for i, v in enumerate(vals) if v == max_val]
        share = joint_prob / len(winners)
        for wi in winners:
            choice_probs[moves[wi]] += share

    # normalize to avoid tiny floating drift (should be ~1 already)
    total = sum(choice_probs.values())
    if total > 0:
        for k in choice_probs:
            choice_probs[k] /= total

    # format return as requested: {move: {'move': idx, 'chance': percent}}
    result = {}
    for k, v in choice_probs.items():
        result[k] = {'move': k, 'chance': round(v * 100.0, 6)}

    print(result)
    return result
