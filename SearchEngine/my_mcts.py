"""
MCTS which is done in 4 steps:
1. Selection: The algorithm travels from the root of the tree to a leaf node,
using heuristics like the Upper Confidence Bound (UCB) to balance exploration and exploitation
2. Expansion: If the selected node isn/'t terminal,
MCTS expands the tree by adding child nodes representing possible future actions.
3. Simulation (Rollout): A random playout is run from the new node to a terminal state,
estimating its potential value.
4. Backpropagation: The results of the simulation are then propagated up the tree…"""
import math
import builtins
import random
from typing import List, Tuple
from types import SimpleNamespace
import numpy as np
from Models.idx_const import (
    Pok, Field, POK_LEN, MOVE_STRIDE
)
from Models.helper import count_party
from Models.trainer_ai import TrainerAI
from Engine.new_battle import Battle
from SearchEngine.mcts_eval import evaluate_terminal, rollout_pref


ActionType = SimpleNamespace(
    MOVE = "move",
    SWITCH = "switch"
)


BattlePhase = SimpleNamespace(
    TURN_START = 0,
    DEATH_END_OF_TURN = 1
)



class GameState():
    """Screenshot of the current gamestate"""
    __slots__ = (
        'battle_array', 'my_active', 'opp_active', 'turn', 'phase', '_opp_ai', '_opp_move'
    )
    def __init__(self, battle_array, share_array=False):
        if share_array:
            self.battle_array = battle_array
        else:
            self.battle_array = np.copy(battle_array)
        self.my_active = int(self.battle_array[Field.MY_POK])  # Index of 0..5
        self.opp_active = int(self.battle_array[Field.OPP_POK])  # Index of 0..5
        self.turn = self.battle_array[Field.TURN]
        self.phase = self.battle_array[Field.PHASE]
        self._opp_ai = None
        self._opp_move = None

    @property
    def opp_ai(self):
        """Only apply Trainer AI to states that are necessary"""
        if self._opp_ai is None:
            self._opp_ai = TrainerAI()
        return self._opp_ai

    @property
    def opp_move(self):
        """Only do opp ai moves when necessary"""
        if self._opp_move is None and self.phase != BattlePhase.DEATH_END_OF_TURN:
            self._opp_move = self.opp_move_choice()
        return self._opp_move

    @property
    def my_pty(self):
        """My party"""
        return self.battle_array[0:(6 * POK_LEN)]

    @property
    def opp_pty(self):
        """Opp party"""
        return self.battle_array[(6 * POK_LEN):(12 * POK_LEN)]

    def clone(self):
        """Clone"""
        return GameState(self.battle_array)

    def get_my_pokemon(self, idx: int) -> np.ndarray:
        """Get pokemon from my party by index (0-5)"""
        start = idx * POK_LEN
        end = (idx + 1) * POK_LEN
        return self.battle_array[int(start):int(end)]

    def get_opp_pokemon(self, idx: int) -> np.ndarray:
        """Get pokemon from opponent party by index (0-5)"""
        start = (6 + idx) * POK_LEN
        end = (7 + idx) * POK_LEN
        return self.battle_array[int(start):int(end)]

    def get_my_active(self) -> np.ndarray:
        """Get my active pokemon"""
        return self.get_my_pokemon(self.my_active)

    def get_opp_active(self) -> np.ndarray:
        """Get opponent's active pokemon"""
        return self.get_opp_pokemon(self.opp_active)

    def is_terminal(self) -> bool:
        """Check if battle is over"""
        my_alive = count_party(self.my_pty)
        opp_alive = count_party(self.opp_pty)
        return my_alive == 0 or opp_alive == 0

    def get_valid_actions(self, is_player: bool = True) -> List[Tuple[str, int]]:
        """Get all valid actions for current player"""
        actions = []

        # Handle death phase first and return immediately
        if self.phase == BattlePhase.DEATH_END_OF_TURN:
            for i in range(6):
                pokemon = self.get_my_pokemon(i) if is_player else self.get_opp_pokemon(i)
                if pokemon[Pok.CURRENT_HP] > 0 and i != (self.my_active if is_player else self.opp_active):
                    actions.append((ActionType.SWITCH, i))
            return actions  # Return here to prevent adding move actions

        # Normal turn phase - get active pokemon
        if is_player:
            active = self.get_my_active()
        else:
            active = self.get_opp_active()

        # Check each move slot
        for i in range(4):
            move_id_idx = Pok.MOVE1_ID + (i * MOVE_STRIDE)
            if active[move_id_idx] != 0:  # Move exists
                actions.append((ActionType.MOVE, i))

        # Add switch actions for normal turn
        for i in range(6):
            pokemon = self.get_my_pokemon(i) if is_player else self.get_opp_pokemon(i)
            # Can switch if pokemon is alive and not currently active
            if pokemon[Pok.CURRENT_HP] > 0 and i != (self.my_active if is_player else self.opp_active):
                actions.append((ActionType.SWITCH, i))

        return actions

    def opp_move_choice(self) -> int:
        """Uses the trainer AI to choose the move"""
        opp_idx = self.opp_ai.return_idx(
            self.battle_array[0:(6 * POK_LEN)],
            self.battle_array[(6 * POK_LEN):(12 * POK_LEN)],
            self.get_my_active(),
            self.get_opp_active(),
            self.turn,
            self.get_opp_active()[Pok.MOVE1_ID:Pok.MOVE2_ID],
            self.get_opp_active()[Pok.MOVE2_ID:Pok.MOVE3_ID],
            self.get_opp_active()[Pok.MOVE3_ID:Pok.MOVE4_ID],
            self.get_opp_active()[Pok.MOVE4_ID:Pok.ITEM_ID]
        )
        return opp_idx

    def step(self, my_move_idx):
        """Simulate the entire turn"""
        new = self.clone()
        battle = Battle(
            battle_array=new.battle_array
        )
        if new.phase == BattlePhase.DEATH_END_OF_TURN:
            battle.end_of_turn(search=my_move_idx[1])
            if my_move_idx[0] == "switch":
                new.my_active = my_move_idx[1]
                new.battle_array[Field.MY_POK] = my_move_idx[1]
            new.phase = int(BattlePhase.TURN_START)
            new.battle_array[Field.PHASE] = BattlePhase.TURN_START
            return new
        opp_move_idx = self.opp_move
        orig_print = builtins.print
        try:
            builtins.print = lambda *a, **k: None
            new.phase, opp_idx = battle.turn_sim(opp_move_idx, my_move_idx)
            new.battle_array[Field.PHASE] = new.phase
            if opp_idx:
                new.opp_active = opp_idx
            if my_move_idx[0] == 'switch':
                new.my_active = my_move_idx[1]
                new.battle_array[Field.MY_POK] = my_move_idx[1]
            if new.my_active != new.battle_array[Field.MY_POK] or new.my_active >= 2:
                pass
        finally:
            builtins.print = orig_print

        return new


class Node():
    """
    - Store: state, parent, children, visit count, total value, untried actions
    - Key: nodes represent decision points, not chance outcomes
    """
    __slots__ = (
        'state', 'parent', 'move', 'children', 'visits', 'total_value', 'legal_moves', 'wins', 'dead',
        'depth', 'win_chance', 'dead_avg'
    )
    def __init__(self, state, parent=None, move=None):
        self.state = state
        self.parent = parent
        self.move = move
        self.children = {}
        self.visits = 0
        self.total_value = 0
        self.legal_moves = state.get_valid_actions(is_player=True)
        self.wins = 0
        self.dead = 0
        self.depth = 0
        self.win_chance = 0.0
        self.dead_avg = 0

    def best_action(self, c=0.5):
        """Best outcome using UCB; break ties and unvisited bias fairly."""
        # prefer a random unvisited child to avoid insertion-order bias

        best_key, best_node = None, None
        best_val = -float("inf")

        # guard: if parent visits is 0/1, exploration term becomes 0
        log_parent_visits = math.log(self.visits) if self.visits > 1 else 0.0

        for key, child in self.children.items():
            # average value
            c_total_value = 0
            c_visits = 0
            for chi in child:
                c_total_value += chi.total_value
                c_visits += chi.visits
            avg = c_total_value / c_visits
            # UCB: avg + c * sqrt(2 * ln(N) / n)
            ucb_val = avg + c * math.sqrt(2 * (log_parent_visits) / c_visits)
            if ucb_val > best_val or (ucb_val == best_val and random.random() < 0.5):
                best_val, best_key, best_node = ucb_val, key, child

        return best_key, best_node


def mixed_rollout(state: GameState, max_depth=50, heuristic_prob=0.3) -> float:
    """
    Mixed rollout: sometimes use heuristics, sometimes pure random
    This reduces bias while still getting some benefit from domain knowledge
    """
    sim_state = state.clone()
    depth = 0

    while not sim_state.is_terminal() and depth < max_depth:
        valid_actions = sim_state.get_valid_actions()
        if not valid_actions:
            break

        if random.random() < heuristic_prob and sim_state.phase != BattlePhase.DEATH_END_OF_TURN:
            # Use heuristic occasionally
            action = rollout_pref(
                sim_state.get_my_active(),
                sim_state.get_opp_active(),
                sim_state.opp_move,
                valid_actions
            )
        else:
            # Pure random most of the time
            action = random.choice(valid_actions)

        sim_state = sim_state.step(action)
        depth += 1
    return sim_state



def mcts(root_state: GameState, iterations: int, training: bool=False):
    """MCTS"""
    root = Node(root_state)

    for _ in range(iterations):
        node = root
        state = root_state.clone()
        path = [node]

        # 1) Selection
        while not state.is_terminal():
            untried_actions = [
                a for a in state.get_valid_actions() if a not in node.children
            ]

            if untried_actions:
                # We have unexplored actions, time to expand
                break
            if node.children:
                action_key, child = node.best_action()  # Pick action with best UCB
                new_state = state.step(action_key)
                if new_state.is_terminal():
                    pass
                has_phase = False
                for c in child:
                    if c.state.phase == new_state.phase:
                        c.state = new_state
                        node = c
                        has_phase = True
                if has_phase is False:
                    new_child = Node(new_state, parent=node, move=action_key)
                    child.append(new_child)
                    node = new_child
                state = new_state
                path.append(node)
            else:
                raise ValueError("MCTS Selection")

        # 2) Expansion (if not terminal)
        if not state.is_terminal() and untried_actions:
            action = random.choice(untried_actions)
            state = state.step(action)
            child = Node(state, parent=node, move=action)
            if action not in node.children:
                node.children[action] = []
                node.children[action].append(child)
            path.append(child)
            node = child

        # 3) Simulation
        if not state.is_terminal():
            sim_state = mixed_rollout(state, heuristic_prob=0.3)
            value, win, dead = evaluate_terminal(sim_state)
        else:
            value, win, dead = evaluate_terminal(state)

        # 4) Backpropagation
        for depth, node in enumerate(reversed(path)):
            node.visits += 1
            node.total_value += value
            node.wins += win
            node.dead += dead if win else 0
            node.dead_avg = node.dead / node.wins if node.wins else 0
            node.win_chance = node.wins/ node.visits

            if not hasattr(node, 'depth'):
                node.depth = depth

    def propagate_stable_values(node, min_visits=70):
        """
        Version 3: Use confidence intervals (Wilson score) to handle uncertainty.
        This properly accounts for "40 visits at 100%" being less trustworthy
        than "9000 visits at 97%".
        """
        def wilson_lower_bound(wins, total, confidence=0.95):
            """
            Calculate Wilson score interval lower bound.
            This gives a conservative estimate that accounts for sample size.
            """
            if total == 0:
                return 0

            z = 1.96 if confidence == 0.95 else 1.645  # z-score for confidence level
            phat = wins / total

            denominator = 1 + z**2 / total
            center = phat + z**2 / (2 * total)
            spread = z * math.sqrt((phat * (1 - phat) + z**2 / (4 * total)) / total)

            return (center - spread) / denominator

        if not node.children:
            return node.win_chance, node.dead_avg

        best_score = -1
        best_win = node.win_chance
        best_dead = node.dead_avg

        for _, node_list in node.children.items():
            total_visits = sum(c.visits for c in node_list if hasattr(c, "visits"))

            if total_visits < min_visits:
                continue

            total_wins = sum(c.wins for c in node_list)
            avg_win = sum(c.win_chance * c.visits for c in node_list) / total_visits

            if total_wins > 0:
                avg_dead = sum(c.dead_avg * c.wins for c in node_list) / total_wins
            else:
                avg_dead = float('inf')

            # Use Wilson score: conservative win estimate accounting for sample size
            # This naturally prefers "9000 visits at 97%" over "40 visits at 100%"
            wilson_score = wilson_lower_bound(total_wins, total_visits)

            # Add small penalty for deaths (but don't let it dominate)
            score = wilson_score - (0.01 * avg_dead if avg_dead != float('inf') else 0)

            if score > best_score:
                best_score = score
                best_win = avg_win
                best_dead = avg_dead

        node.win_chance = best_win
        node.dead_avg = best_dead

        return node.win_chance, node.dead_avg


    def recursive_backup(node, min_visits=70, use_wilson=True):
        """
        Recursively backup values from leaves to root.
        
        Args:
            use_wilson: If True, use Wilson score (v3) which handles sample size naturally.
                    If False, use simple top-tier selection (v1).
        """
        if not node.children:
            return node.win_chance, node.dead_avg

        # First, recursively backup all children
        for node_list in node.children.values():
            for child in node_list:
                recursive_backup(child, min_visits=min_visits, use_wilson=use_wilson)

        # Then propagate the best child values to this node
        if use_wilson:
            propagate_stable_values(node, min_visits=min_visits)
        else:
            propagate_stable_values(node, min_visits=min_visits)

        return node.win_chance, node.dead_avg

    recursive_backup(root)

    def print_best_path(root, depth=0, max_depth=5, min_visits=1, choose_by='wilson'):
        """
        Print all actions with enhanced metrics including confidence.
        """
        if depth > max_depth or not getattr(root, "children", None):
            return

        indent = "    " * depth
        print(f"\n{indent}------ Depth {depth} ------")

        best_action = None
        best_metric = -float("inf")
        best_node = None

        for action, nodes in root.children.items():
            total_visits = sum(getattr(n, "visits", 0) for n in nodes)
            if total_visits < min_visits:
                print(f"{indent}Action: {action} (skipped, visits={total_visits})")
                continue

            total_wins = sum(getattr(n, "wins", 0) for n in nodes)
            total_dead = sum(getattr(n, "dead", 0) for n in nodes)

            avg_win = sum(n.win_chance * getattr(n, "visits", 0) for n in nodes) / total_visits
            avg_dead = sum(n.dead_avg * getattr(n, "wins", 0) for n in nodes) / total_wins if total_wins > 0 else 0
            total_value = sum(getattr(n, "total_value", 0) for n in nodes)

            # Calculate Wilson score for display
            if choose_by == 'wilson':
                z = 1.96
                phat = total_wins / total_visits if total_visits > 0 else 0
                denominator = 1 + z**2 / total_visits if total_visits > 0 else 1
                center = phat + z**2 / (2 * total_visits) if total_visits > 0 else 0
                spread = z * math.sqrt((phat * (1 - phat) + z**2 / (4 * total_visits)) / total_visits) if total_visits > 0 else 0
                wilson = (center - spread) / denominator
                metric = wilson - (0.01 * avg_dead)
            else:
                metric = avg_win

            print(f"{indent}Action: {action}, visits: {total_visits}, "
                f"total value: {round(total_value,2)}, "
                f"avg_win: {round(avg_win*100,2)}%, avg_dead: {round(avg_dead,2)}, "
                f"total win: {total_wins}, total dead: {total_dead}")

            if metric > best_metric:
                best_metric = metric
                best_action = action
                best_node = max(nodes, key=lambda n: getattr(n, "visits", 0))

        if best_node:
            print(f"{indent}==> Best action at depth {depth}: {best_action}")
            print_best_path(best_node, depth + 1, max_depth, min_visits, choose_by)


    if not training:
        print_best_path(root, max_depth=15)
        