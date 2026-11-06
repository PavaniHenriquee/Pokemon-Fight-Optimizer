"""Where the time goes: the backend's search loop and stop rule (backend/main.py _mcts_worker) on
one process, timed per phase, on the trees a long search in the app builds."""
import gc
import time
import psutil
from SearchEngine.helper import prune_dominated
from SearchEngine.models import GameState, Node
from SearchEngine.my_mcts import _backprop, _rollout, _select_expand, find_best_terminal_node
from benchmarks.fights import FIGHTS, fight, seed_all

pc = time.perf_counter
_MAX_ITERATIONS = 350_000  # BattleConfig's default
_CHECK_EVERY = 2500
_CONVERGED_VISITS = 5000
_COMPARED = ("iter_s", "select_us", "rollout_us", "backprop_us", "tree_kb_per_it")


def _iteration(root_state, root):
    """One iteration of the backend's loop. Returns the seconds of its 3 phases"""
    t0 = pc()
    state, path, actions = _select_expand(root_state.clone(), root)
    t1 = pc()
    value, win, dead = _rollout(state)
    t2 = pc()
    _backprop(path, actions, value, win, dead)
    return t1 - t0, t2 - t1, pc() - t2


def _converged(root):
    """The backend's periodic check: prunes, then asks whether the best path has settled"""
    terminal_node, _, _ = find_best_terminal_node(root)
    prune_dominated(root)
    return terminal_node.snapshot.terminal and terminal_node.visits >= _CONVERGED_VISITS


def _busy_seconds(proc):
    """CPU seconds used so far, by the whole machine and by this process"""
    cpu = psutil.cpu_times()
    return cpu.user + cpu.system, sum(proc.cpu_times()[:2])


def _pass(name, seconds):
    """One timed search, with the numbers of one row"""
    gc.collect()
    proc = psutil.Process()
    root_state = GameState(fight(name))
    seed_all(37)
    root = Node(root_state)
    memory_before = proc.memory_info().rss
    machine_before, own_before = _busy_seconds(proc)
    select = rollout = backprop = 0.0
    converged = 0.0
    iterations = 0
    start = pc()
    for i in range(_MAX_ITERATIONS):
        select_s, rollout_s, backprop_s = _iteration(root_state, root)
        select += select_s
        rollout += rollout_s
        backprop += backprop_s
        iterations = i + 1
        if i % _CHECK_EVERY == 0 and i > 0 and _converged(root):
            converged = pc() - start
            break
        if pc() - start > seconds:
            break
    wall = pc() - start
    machine_after, own_after = _busy_seconds(proc)
    busy = machine_after - machine_before
    visits = [sum(c.visits for c in nodes) for nodes in root.children.values()]
    return {
        "iter_s": iterations / wall,
        "select_us": select / iterations * 1e6,
        "rollout_us": rollout / iterations * 1e6,
        "backprop_us": backprop / iterations * 1e6,
        "select_share": 100 * select / wall,
        "converged_s": converged,
        "best_action_share": 100 * max(visits) / sum(visits),
        "tree_kb_per_it": (proc.memory_info().rss - memory_before) / iterations / 1024,
        "background": 100 * (busy - (own_after - own_before)) / (wall * psutil.cpu_count()),
    }


def run(report, budget):
    """One row per fight, the mean of the passes"""
    report.heading("Where the time goes")
    report.text(f"Backend loop and stop rule, {budget.search_seconds:.0f} s limit, one process, "
                f"mean of {budget.search_passes} runs.")
    rows = []
    for name in FIGHTS:
        passes = [_pass(name, budget.search_seconds) for _ in range(budget.search_passes)]
        row = {k: sum(p[k] for p in passes) / len(passes) for k in passes[0]}
        converged = all(p["converged_s"] for p in passes)
        for key in _COMPARED + (("converged_s",) if converged else ()):
            report.metric(f"search/{name}/{key}", row[key])
        status = f"Yes, {row['converged_s']:.1f} s" if converged else "No"
        rows.append((
            name, f"{row['iter_s']:,.0f}", f"{row['select_us']:.1f} µs ({row['select_share']:.0f}%)",
            f"{row['rollout_us']:.1f} µs", f"{row['backprop_us']:.1f} µs", status,
            f"{row['best_action_share']:.0f}%", f"{row['tree_kb_per_it']:.2f}",
            f"{row['background']:.0f}%",
        ))
    report.table(("Fight", "Iter/s", "select/expand", "rollout", "backprop", "Converged?",
                  "Best action", "Tree KB/it", "Background"), rows)
