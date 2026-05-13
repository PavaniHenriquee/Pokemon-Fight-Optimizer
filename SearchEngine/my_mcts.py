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
import random
from typing import List
from SearchEngine.mcts_eval import evaluate_terminal, rollout_pref
from SearchEngine.helper import multiple_nodes, find_best_terminal_node
from SearchEngine.models import BattlePhase, GameState, Node
from Models.idx_const import Field


def mixed_rollout(state: GameState, max_depth=100, heuristic_prob=0.3) -> float:
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
                sim_state.battle_array[Field.WEATHER],
                valid_actions
            )
        else:
            # Pure random most of the time
            action = random.choice(valid_actions)

        sim_state = sim_state.step(action)
        depth += 1
    return sim_state



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


def propagate_stable_values(node, min_visits=70):
    """
    Choose it's child best node and propagate as that being the outcome of the parent
    """

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
        score = wilson_score - (0.1 * avg_dead if avg_dead != float('inf') else 0)

        if score > best_score:
            best_score = score
            best_win = avg_win
            best_dead = avg_dead

    node.win_chance = best_win
    node.dead_avg = best_dead

    return node.win_chance, node.dead_avg


def recursive_backup(node, min_visits=70):
    """
    Recursively backup values from leaves to root.
    
    Args:
        use_wilson: If True, use Wilson score (v3) which handles sample size naturally.
                If False, use simple top-tier selection (v1).
    """
    # Base case: terminal node (leaf) - just return its values
    if not node.children:
        return node.win_chance, node.dead_avg

    # First, recursively backup all children
    for node_list in node.children.values():
        for child in node_list:
            recursive_backup(child, min_visits=min_visits)

    # Then propagate the best child values to this node
    # Only do this if node has children (non-terminal)
    if node.children:
        propagate_stable_values(node, min_visits=min_visits)

    return node.win_chance, node.dead_avg


def print_best_path(root, depth=0, max_depth=50, min_visits=1):
    """
    Print best path using backpropagated values.
    """
    if depth > max_depth or not getattr(root, "children", None):
        return

    indent = " " * depth
    print(f"\n{indent}------ Depth {depth} ------")

    best_action = None
    best_metric = -float("inf")
    best_node = None

    for action, nodes in sorted(root.children.items(), key=lambda x: (x[0][0], x[0][1])):
        total_visits = sum(getattr(n, "visits", 0) for n in nodes)
        if total_visits < min_visits:
            print(f"{indent}Action: {action} (skipped, visits={total_visits})")
            continue

        # Use the backpropagated values directly
        avg_win = sum(n.win_chance * getattr(n, "visits", 0) for n in nodes) / total_visits
        if sum(getattr(n, "wins", 0) for n in nodes) > 0:
            avg_dead = (
                sum(n.dead_avg * getattr(n, "wins", 0) for n in nodes)
                / sum(getattr(n, "wins", 0) for n in nodes)
            )
        else:
            avg_dead = 0

        # For metric, just use avg_win directly since backprop already selected it
        metric = total_visits

        print(f"{indent}Action: {action}, visits: {total_visits}, "
            f"avg_win: {round(avg_win*100,2)}%, avg_dead: {round(avg_dead,2)}")

        if metric > best_metric:
            best_metric = metric
            best_action = action
            best_node = max(nodes, key=lambda n: getattr(n, "visits", 0))

    if best_node:
        print(f"{indent}==> Best action at depth {depth}: {best_action}")
        print_best_path(best_node, depth + 1, max_depth, min_visits)


def _select_expand(state: GameState, node: Node):
    """Phases 1 and 2 of MCTS"""
    path = [node]
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
            new_node = multiple_nodes(child, new_state)
            if not new_node:
                new_child = Node(new_state)
                child.append(new_child)
                node = new_child
            else:
                node = new_node
            state = new_state
            path.append(node)
        else:
            raise ValueError("MCTS Selection")

    # 2) Expansion (if not terminal)
    if not state.is_terminal() and untried_actions:
        action = random.choice(untried_actions)
        state = state.step(action)
        child = Node(state)
        if action not in node.children:
            node.children[action] = []
            node.children[action].append(child)
        path.append(child)

    return state, path


def _rollout(state: GameState):
    """Phase 3 of MCTS"""
    if not state.is_terminal():
        sim_state = mixed_rollout(state)
        value, win, dead = evaluate_terminal(sim_state)
    # If state is terminal there's no need to rollout
    else:
        value, win, dead = evaluate_terminal(state)

    return value, win, dead

def _backprop(path: List, value: float, win: int, dead: int):
    """Phase 4 of MCTS"""
    for node in reversed(path):
        node.visits += 1
        node.total_value += value
        node.wins += win
        node.dead += dead if win else 0
        node.dead_avg = node.dead / node.wins if node.wins else 0
        node.win_chance = node.wins/ node.visits


def mcts_loop(
        root: 'Node', root_state: GameState,
        max_iterations: int=50_000, terminal_iterations: int=1000
):
    """MCTS"""

    for iterations in range(max_iterations):
        node = root
        state = root_state.clone()
        state, path = _select_expand(state, node)
        value, win, dead = _rollout(state)
        _backprop(path, value, win, dead)

        # Cutoff when results are good enough
        if iterations % 100 == 0 and iterations > 0:
            terminal_node, terminal_path, actions = find_best_terminal_node(root)
            if terminal_node.snapshot.terminal and terminal_node.visits >= terminal_iterations:
                print(f"Converged at {iterations} iterations, \n"
                    f"terminal depth {len(terminal_path)}, \n"
                    f"terminal visits {terminal_node.visits}")
                print(f"Convergence path: {actions}")
                break


def mcts(root_state: GameState, max_iterations: int = 50_000, terminal_iterations: int = 1000):
    """
    Runs the loop uses the tree to give only the best answers back the path the prints the path
    """
    root = Node(root_state)
    mcts_loop(root, root_state, max_iterations, terminal_iterations)
    recursive_backup(root)
    print_best_path(root)
