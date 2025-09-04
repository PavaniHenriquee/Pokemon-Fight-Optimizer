"""Actual run-through"""
import itertools
import math
import random
import copy
import builtins                                  # added
from Engine.battle import Battle
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

    # format return: {move: {'move': idx, 'chance': percent}}
    result = {}
    for k, v in choice_probs.items():
        result[k] = {'move': k, 'chance': round(v * 100.0, 4)}

    return result


EXPLORATION_C = math.sqrt(2)


class GameState:
    """Game State"""
    def __init__(self, my_party, opp_party, cur_my_idx=0, cur_opp_idx=0, turn=0):
        # Deep copy so simulations don't mutate your real battle
        self.my_party = copy.deepcopy(my_party)
        self.opp_party = copy.deepcopy(opp_party)
        self.cur_my_idx = cur_my_idx
        self.cur_opp_idx = cur_opp_idx
        self.turn = turn

    def clone(self):
        """Clone"""
        return GameState(self.my_party, self.opp_party, self.cur_my_idx, self.cur_opp_idx, self.turn)

    # Convenience
    def my_active(self):
        """My current pok"""
        return self.my_party[self.cur_my_idx]

    def opp_active(self):
        """My opp pokemon"""
        return self.opp_party[self.cur_opp_idx]

    def get_legal_moves(self, for_me=True):
        """Get legal moves"""
        pok = self.my_active() if for_me else self.opp_active()
        # Accept both dict-style moves and objects; check pp defensively
        legal = []
        if pok.fainted:
            return legal
        for i, mv in enumerate(pok.moves):
            if isinstance(mv, dict):
                pp = mv.get('pp', 1)
            else:
                pp = getattr(mv, 'pp', 1)
            if pp > 0:
                legal.append(i)
        return legal

    def _sample_opp_move(self):
        """Use the EXISTING AI to get the opponent move distribution and sample one."""
        probs = search_best_move(
            self.my_party, self.opp_party,
            self.my_active(), self.opp_active(),
            self.turn
        )
        # probs format you implemented: {idx: {'move': idx, 'chance': percent}}
        items = list(probs.items())
        if not items:
            # Fallback: uniform over legal opponent moves
            legal = self.get_legal_moves(for_me=False)
            return random.choice(legal) if legal else None
        # Extract move indices and numeric weights (chance may be percent)
        moves = []
        weights = []
        for m, info in items:
            w = info.get('chance', 0.0)
            try:
                w = float(w)
            except Exception:
                w = 0.0
            if w > 0:
                moves.append(m)
                weights.append(w)
        if not moves:
            legal = self.get_legal_moves(for_me=False)
            return random.choice(legal) if legal else None
        return random.choices(moves, weights=weights, k=1)[0]

    def step(self, my_move_idx):
        """
        Apply ONE full turn:
        - Our chosen move: my_move_idx (the action in MCTS).
        - Opponent move: sampled from their AI distribution.
        """
        new = self.clone()
        opp_move_idx = new._sample_opp_move()  # pylint: disable=W0212
        if opp_move_idx is None:
            return new  # no legal opp move; edge-case fallback
        battle = Battle(new.my_party, new.opp_party)
        # Run the actual battle_turn silently for simulations to avoid huge console spam
        orig_print = builtins.print
        if my_move_idx >= len(new.my_active().moves) or opp_move_idx >= len(new.opp_active().moves):
            return new  # invalid move index; edge-case fallback
        try:
            builtins.print = lambda *a, **k: None
            battle.battle_turn(
                new.my_active(),
                new.my_active().moves[my_move_idx],
                new.opp_active(),
                new.opp_active().moves[opp_move_idx]
            )
        finally:
            builtins.print = orig_print

        # If an active fainted, pick replacements for the simulation:
        # -- opponent: use TrainerAI.sub_after_death when possible
        # -- our side: pick first non-fainted teammate (simple deterministic policy)
        # NOTE: sub_after_death expects ai_party, user_pok, deadmon and returns an index into ai_party
        try:
            # Opponent replacement
            if new.opp_active().fainted:
                opp_ai = TrainerAI()
                idx = opp_ai.sub_after_death(new.opp_party, new.my_active(), new.opp_active())
                # if ai returned a valid index use it; otherwise fallback to first alive
                if isinstance(idx, int) and 0 <= idx < len(new.opp_party) and not new.opp_party[idx].fainted:
                    new.cur_opp_idx = idx
                else:
                    for i, p in enumerate(new.opp_party):
                        if not p.fainted:
                            new.cur_opp_idx = i
                            break
            # Our replacement
            if new.my_active().fainted:
                # Prefer the first non-fainted different from current index
                replacement = None
                for i, p in enumerate(new.my_party):
                    if not p.fainted and i != new.cur_my_idx:
                        replacement = i
                        break
                if replacement is not None:
                    new.cur_my_idx = replacement
        except Exception:
            # Defensive: if replacement logic errors, leave indices as-is and let is_terminal handle outcome
            pass

        new.turn += 1
        return new

    def is_terminal(self):
        """Anyone died?"""
        my_dead = all(p.fainted for p in self.my_party)
        opp_dead = all(p.fainted for p in self.opp_party)
        return my_dead or opp_dead

    def evaluate(self):
        """Terminal reward from OUR perspective: +1 win, -1 loss, 0 draw."""
        my_dead = all(p.fainted for p in self.my_party)
        opp_dead = all(p.fainted for p in self.opp_party)
        if opp_dead and not my_dead:
            return 1.0
        if my_dead and not opp_dead:
            return -1.0
        return 0.0  # rare draw / non-terminal safeguard


class Node:
    """Node of MCTS"""
    def __init__(self, state, parent=None, move=None):
        self.state = state
        self.parent = parent
        self.move = move  # OUR move taken at the parent to reach this node
        self.children = {}  # move_idx -> Node
        self.visits = 0
        self.total_reward = 0.0
        self.untried_moves = state.get_legal_moves(for_me=True)

    def ucb(self, c=EXPLORATION_C):
        """Method UCB"""
        if self.visits == 0:
            return float('inf')
        # Ensure parent.visits used in log is at least 1 to avoid log(0)
        if self.parent is None:
            parent_visits = 1
        else:
            parent_visits = max(1, self.parent.visits)
        return (self.total_reward / self.visits) + c * math.sqrt(math.log(parent_visits) / self.visits)

    def best_child(self, c=EXPLORATION_C):
        """Best outcome"""
        return max(self.children.values(), key=lambda n: n.ucb(c))


def mcts_decide(root_state, iterations=800):
    """What Monte carlo decides"""
    root = Node(root_state)

    for _ in range(iterations):
        node = root
        state = root_state

        # 1) Selection
        while not node.untried_moves and node.children:
            node = node.best_child()
            # node.move is the action used to reach `node` from its parent
            if node.move is not None:
                state = state.step(node.move)

        # 2) Expansion
        if node.untried_moves and not state.is_terminal():
            my_move = node.untried_moves.pop()
            state = state.step(my_move)
            child = Node(state, parent=node, move=my_move)
            node.children[my_move] = child
            node = child

        # 3) Simulation (rollout)
        rollout_state = state
        depth = 0
        while not rollout_state.is_terminal() and depth < 100:  # safety cap
            legal = rollout_state.get_legal_moves(for_me=True)
            if not legal:
                break
            # Simple rollout policy for OUR move:
            my_move = random.choice(legal)  # (upgrade later with a heuristic if you want)
            rollout_state = rollout_state.step(my_move)
            depth += 1

        # 4) Backpropagation
        reward = rollout_state.evaluate()
        while node is not None:
            node.visits += 1
            node.total_reward += reward
            node = node.parent

    # Choose the child with most visits (robust)
    if not root.children:
        return None, {}
    best_move, _ = max(root.children.items(), key=lambda kv: kv[1].visits)
    stats = {m: (n.visits, (n.total_reward/n.visits if n.visits else 0.0)) for m, n in root.children.items()}
    return best_move, stats
