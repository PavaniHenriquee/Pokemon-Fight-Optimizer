"""
Root-parallel MCTS using multiprocessing.
 
Strategy: N independent processes each run a full MCTS search from the same
root state (with different random seeds).  Their root-level visit counts are
combined at the end.  This avoids all shared-state complexity and works well
with Python's GIL because each process has its own interpreter.
 
Tradeoff vs shared-tree parallelism:
  - Pro:  zero locking, zero coordination overhead, trivial to implement
  - Con:  processes can't learn from each other mid-search (less UCB efficiency)
  - Net:  for the iteration counts you're running locally this is the right call
"""
import random
import multiprocessing as mp
from multiprocessing import Pool
from typing import Dict, Tuple

import numpy as np

# These imports happen inside the worker process, so they're fine
from SearchEngine.my_mcts import (
    GameState, Node,
    mcts_loop, recursive_backup
)


def _extract_best_path(root) -> list:
    """Walk the backpropagated tree following the best win_chance at each depth."""
    path = []
    node = root
    while node.children:
        best_action, best_nodes = max(
            node.children.items(),
            key=lambda x: sum(n.win_chance * n.visits for n in x[1]) /
                          max(sum(n.visits for n in x[1]), 1)
        )
        total_visits = sum(n.visits for n in best_nodes)
        total_wins   = sum(n.wins   for n in best_nodes)
        win_chance   = sum(n.win_chance * n.visits for n in best_nodes) / total_visits if total_visits else 0
        dead_avg     = sum(n.dead_avg * n.wins for n in best_nodes) / total_wins if total_wins else 0

        path.append({
            'action':     best_action,
            'visits':     total_visits,
            'win_chance': win_chance,
            'dead_avg':   dead_avg,
        })
        # follow the most visited node for the next depth
        node = max(best_nodes, key=lambda n: n.visits)
    return path


# ── Worker (must be a module-level function to be picklable) ─────────────────

def _mcts_worker(args: Tuple) -> Dict[Tuple, Dict[str, float]]:
    """
    Runs in a separate process.
    Returns a serialisable summary of root-child stats — NOT the full Node tree,
    because shipping the whole tree over a pipe would be very slow.
    """
    battle_array, max_iterations, terminal_iterations, seed = args

    # Each worker gets its own seed so they explore different parts of the tree
    random.seed(seed)
    np.random.seed(seed)

    root_state = GameState(battle_array)   # GameState copies the array in __init__
    root = Node(root_state)
    mcts_loop(root, root_state, max_iterations, terminal_iterations)
    recursive_backup(root)

    # Serialize only what we need to combine results
    summary: Dict[Tuple, Dict[str, float]] = {}
    for action, node_list in root.children.items():
        total_visits = sum(n.visits for n in node_list)
        total_wins   = sum(n.wins   for n in node_list)
        # win_chance was set by _recursive_backup — use it, not raw wins/visits
        win_chance = (
            sum(n.win_chance * n.visits for n in node_list) / total_visits
            if total_visits else 0.0
        )
        dead_avg = (
            sum(n.dead_avg * n.wins for n in node_list) / total_wins
            if total_wins else 0.0
        )
        summary[action] = {
            'visits':     total_visits,
            'win_chance': win_chance,
            'dead_avg':   dead_avg,
        }
    return {'root': summary, 'best_path': _extract_best_path(root)}

# ── Combiner ─────────────────────────────────────────────────────────────────

# _combine_results — weighted average instead of summing raw counts
def _combine_results(worker_results):
    root_stats = {}
    best_paths = []
    for result in worker_results:
        best_paths.append(result['best_path'])          # separate it out first
        for action, stats in result['root'].items():    # then iterate the actual stats
            if action not in root_stats:
                root_stats[action] = {'visits': 0, 'win_chance': 0.0, 'dead_avg': 0.0}
            old_v = root_stats[action]['visits']
            new_v = old_v + stats['visits']
            if new_v > 0:
                root_stats[action]['win_chance'] = (
                    root_stats[action]['win_chance'] * old_v +
                    stats['win_chance'] * stats['visits']
                ) / new_v
                root_stats[action]['dead_avg'] = (
                    root_stats[action]['dead_avg'] * old_v +
                    stats['dead_avg'] * stats['visits']
                ) / new_v
            root_stats[action]['visits'] = new_v
    return root_stats, best_paths


def _best_action(combined):
    return max(
        combined.items(),
        key=lambda x: (x[1]['win_chance'], x[1]['visits'])
    )[0]


def _print_combined(combined, best_paths):
    print("\n=== Parallel MCTS — combined root stats ===")
    print("--- Depth 0 (combined across all workers) ---")
    for action in sorted(combined, key=lambda a: (a[0], a[1])):
        s = combined[action]
        print(f"  {action}  visits={s['visits']:>6}  "
              f"win%={s['win_chance']*100:5.1f}%  avg_dead={s['dead_avg']:.2f}")

    best = _best_action(combined)
    print(f"\n  => Best action: {best}")

    # Find the worker whose best path starts with the combined winner
    matching = next(
        (p for p in best_paths if p and p[0]['action'] == best),
        best_paths[0] if best_paths else []
    )
    for depth, step in enumerate(matching[1:], start=1):  # root already printed above
        indent = " " * depth
        print(f"\n{indent}--- Depth {depth} (single worker) ---")
        print(f"{indent}  {step['action']}  visits={step['visits']:>6}  "
              f"win%={step['win_chance']*100:5.1f}%  avg_dead={step['dead_avg']:.2f}")
        print(f"{indent}  ==> Best action at depth {depth}: {step['action']}")


# ── Public API ────────────────────────────────────────────────────────────────

def parallel_mcts(
    root_state: GameState,
    num_workers: int = None,
    total_iterations: int = 400_000,
    terminal_iterations: int = 1_500,
) -> Tuple[Dict, Tuple]:
    """
    Run MCTS across `num_workers` processes and combine the results.
 
    Args:
        root_state:          Starting GameState (not modified).
        num_workers:         Number of parallel processes.
                             Defaults to os.cpu_count() - 1 (leave one core free).
        total_iterations:    Total MCTS iterations spread across all workers.
        terminal_iterations: Per-worker early-exit threshold.
 
    Returns:
        (combined_stats, best_action)
        combined_stats: {action: {'visits', 'wins', 'total_value', 'dead'}}
        best_action:    The action with the highest combined win rate.
    """
    if num_workers is None:
        # Leave one core free so the OS stays responsive
        num_workers = max(1, (mp.cpu_count() or 2) - 1)

    iters_per_worker = max(1, total_iterations // num_workers)
    base_seed = random.randint(0, 2**31 - 1)

    print(f"[parallel_mcts] {num_workers} workers × {iters_per_worker} iterations "
          f"(total ≈ {num_workers * iters_per_worker})")

    args = [
        (
            root_state.battle_array.copy(),  # each worker gets its own copy
            iters_per_worker,
            terminal_iterations,
            base_seed + i,                   # different seed per worker
        )
        for i in range(num_workers)
    ]

    with Pool(processes=num_workers) as pool:
        worker_results = pool.map(_mcts_worker, args)

    root_stats, best_paths = _combine_results(worker_results)
    _print_combined(root_stats, best_paths)

    return
