"""What the training data costs: shard size and speed on real states, encoding with the shell, and
Step 5's bring-up rate (rollout-play states labelled by 16 of today's rollouts each)."""
import multiprocessing as mp
import os
import random
import tempfile
import time
import numpy as np
import psutil
from Models.constants import _BATTLEPHASE_TURN_START, _FIELD_PHASE
from Models.trainer_ai import return_idx
from SearchEngine.mcts_eval import rollout_arr, rollout_pref
from SearchEngine.models import is_terminal_arr, step_arr, valid_actions_array
from Utils.jit import njit
from benchmarks.fights import FIGHTS, fight, seed_all
from benchmarks.play import core_cpus, warm

pc = time.perf_counter
_LABEL_ROLLOUTS = 16


@njit
def _next_state(battle_array, heuristic_prob=0.48):
    """One step of today's rollout policy, in place. False once the battle is over"""
    if is_terminal_arr(battle_array):
        return False
    actions = valid_actions_array(battle_array)
    n = len(actions)
    if n == 0:
        return False
    if battle_array[_FIELD_PHASE] != _BATTLEPHASE_TURN_START:
        opp_move = -50
    else:
        opp_move = return_idx(battle_array)
    if random.random() < heuristic_prob:
        act = rollout_pref(battle_array, opp_move, actions)
        a_type, a_idx = act[0], act[1]
    else:
        r = random.randrange(n)
        a_type, a_idx = actions[r, 0], actions[r, 1]
    step_arr(battle_array, int(a_type), int(a_idx), opp_move)
    return True


def collect_states(n_target):
    """Real states in the order a worker would write them: battle by battle, fights mixed"""
    seed_all(11)
    out = np.empty((n_target, fight("Dallas").size), dtype=np.int32)
    n = 0
    while n < n_target:
        for name in FIGHTS:
            arr = fight(name)
            while n < n_target and _next_state(arr) and not is_terminal_arr(arr):
                out[n] = arr
                n += 1
    return out


def _shards(report, states, folder):
    rows = []
    shuffled = states[np.random.default_rng(5).permutation(states.shape[0])]
    for label, data in (("battle order", states), ("shuffled", shuffled)):
        path = os.path.join(folder, f"{label.replace(' ', '_')}.npz")
        start = pc()
        np.savez_compressed(path, states=data)
        written = pc()
        with np.load(path) as shard:
            _ = shard["states"]
        read = pc()
        size = os.path.getsize(path)
        per_state = size / data.shape[0]
        write_rate = data.shape[0] / (written - start)
        read_rate = data.shape[0] / (read - written)
        key = f"data/{label}"
        report.metric(f"{key}/bytes_per_state", per_state)
        report.metric(f"{key}/write_states_s", write_rate)
        report.metric(f"{key}/read_states_s", read_rate)
        rows.append((label, f"{per_state:.0f} bytes", f"{write_rate:,.0f}", f"{read_rate:,.0f}"))
        os.remove(path)
    report.text(f"{states.shape[0]:,} real states from the test fights, {states.shape[1]} int32, "
                f"{states.shape[1] * 4 / 1024:.1f} KB each raw.")
    report.table(("Shard order", "Compressed", "Write states/s", "Read states/s"), rows)


def _encode(report, states):
    from NeuralNetwork.models import to_nn_input
    count = min(50_000, len(states))
    to_nn_input(states[0])
    start = pc()
    for i in range(count):
        to_nn_input(states[i])
    per_state = (pc() - start) / count
    report.metric("data/shell_encode_us", per_state * 1e6)
    report.text(f"Shell encode on real states, from Python: {per_state * 1e6:.2f} µs "
                f"({1 / per_state:,.0f} states/s per core).")


def _bringup_worker(args):
    cpu, seconds, seed, barrier = args
    psutil.Process().cpu_affinity([cpu])
    warm()
    seed_all(seed)
    battles = [fight(name) for name in FIGHTS]
    barrier.wait()
    start = pc()
    states = i = 0
    while pc() - start < seconds:
        arr = battles[i % len(battles)].copy()
        i += 1
        while _next_state(arr) and not is_terminal_arr(arr) and pc() - start < seconds:
            for _ in range(_LABEL_ROLLOUTS):
                rollout_arr(arr.copy())
            states += 1
    return states / (pc() - start)


def _bringup(report, budget):
    cores = core_cpus()
    rows = []
    for n in (1, len(cores)) if budget.full_tables else (len(cores),):
        with mp.Manager() as manager:
            barrier = manager.Barrier(n + 1)
            args = [(cores[i], budget.bringup_seconds, 3000 + i, barrier) for i in range(n)]
            with mp.Pool(n) as pool:
                pending = pool.map_async(_bringup_worker, args, chunksize=1)
                barrier.wait()
                total = sum(pending.get())
        report.metric(f"data/bringup/{n} pinned/states_s", total)
        rows.append((n, f"{total:,.0f}", f"{1e6 / total / 60:.1f} min"))
    report.table(("Pinned workers", "Bring-up states/s", "1M states"), rows)


def run(report, budget):
    """Shards, encoding and bring-up"""
    report.heading("Data")
    states = collect_states(budget.states)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        _shards(report, states, folder)
    _encode(report, states)
    del states
    _bringup(report, budget)
