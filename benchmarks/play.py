"""Full battles played by search, and worker processes that play them.

One decision is one call of mcts_loop on a fresh tree from the real state, then the most visited
root action is played. Single-action decisions skip the search, as Step 2's arena will.
"""
import time
import psutil
from SearchEngine.mcts_eval import evaluate_terminal, rollout_arr
from SearchEngine.models import ACTION_ORDER, N_SLOTS, GameState, Node, valid_action_mask
from SearchEngine.my_mcts import mcts_loop
from benchmarks.fights import fight, seed_all

pc = time.perf_counter
MAX_DECISIONS = 300
_NEVER = 10**9  # A terminal_iterations no search reaches, so every decision gets its whole budget


def _search(state, iters):
    """The most visited root action after iters iterations on a fresh tree"""
    root = Node(state)
    mcts_loop(root, state, max_iterations=iters, terminal_iterations=_NEVER)
    best, best_visits = None, -1
    for action, nodes in root.children.items():
        visits = sum(n.visits for n in nodes)
        if visits > best_visits:
            best, best_visits = action, visits
    return best


def _only_action(state):
    """The single valid action, or None when there's a real decision to make"""
    mask = valid_action_mask(state.battle_array)
    actions = [ACTION_ORDER[s] for s in range(N_SLOTS) if mask >> s & 1]
    return actions[0] if len(actions) == 1 else None


def play(battle, iters):
    """Plays one battle. Returns value, win, dead, decisions, searched decisions, search seconds"""
    state = GameState(battle)
    decisions = searched = 0
    search_time = 0.0
    while decisions < MAX_DECISIONS and not state.is_terminal():
        action = _only_action(state)
        if action is None:
            start = pc()
            action = _search(state, iters)
            search_time += pc() - start
            searched += 1
        state.step(action)
        decisions += 1
    value, win, dead = evaluate_terminal(state.battle_array)
    return float(value), int(win), int(dead), decisions, searched, search_time


def warm():
    """Compiles or loads everything a search runs, so no timing pays for it"""
    seed_all(1)
    play(fight("Dallas"), 64)
    rollout_arr(fight("Dallas"))
    rollout_arr(fight("Dallas"), 100, 0.48)


def core_cpus():
    """One logical CPU per physical core. Windows numbers hyper-threading siblings side by side"""
    logical = psutil.cpu_count()
    physical = psutil.cpu_count(logical=False) or logical
    return list(range(0, logical, logical // physical))


def init_pinned_worker(counter):
    """Pool initializer: its own physical core, below normal so the desktop stays usable"""
    with counter.get_lock():
        index = counter.value
        counter.value += 1
    proc = psutil.Process()
    proc.cpu_affinity([core_cpus()[index]])
    proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    warm()


def battle_task(task):
    """One seeded battle. Seeds are fixed per cell, so how long a battle takes can't bias a result"""
    name, iters, seed = task
    seed_all(seed)
    return play(fight(name), iters)


def timed_worker(args):
    """Plays a fight until time is up, for throughput only. All workers start on a barrier"""
    name, iters, seconds, cpu, seed, barrier = args
    proc = psutil.Process()
    if cpu is not None:
        proc.cpu_affinity(cpu)
    warm()
    seed_all(seed)
    barrier.wait()
    start = pc()
    decisions = 0
    while pc() - start < seconds:
        state = GameState(fight(name))
        made = 0
        while made < MAX_DECISIONS and not state.is_terminal() and pc() - start < seconds:
            action = _only_action(state)
            if action is None:
                action = _search(state, iters)
                decisions += 1
            state.step(action)
            made += 1
    memory = proc.memory_info()
    return decisions, pc() - start, getattr(memory, "peak_wset", memory.rss)
