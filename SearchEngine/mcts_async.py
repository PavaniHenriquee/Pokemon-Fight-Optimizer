"""Run MCTS loop in asynchronous way with a single tree, so it can run faster but smarter"""
import multiprocessing as mp
from SearchEngine.my_mcts import (
    mixed_rollout, _select_expand, _backprop,
    recursive_backup, print_best_path
)
from SearchEngine.models import GameState, Node
from SearchEngine.mcts_eval import evaluate_terminal
from SearchEngine.helper import find_best_terminal_node


def _async_worker(task_queue: mp.Queue, result_queue: mp.Queue):
    """
    Runs continuously — never stops between iterations.
    Gets (task_id, battle_array), does rollout, returns result.
    Stops on None poison pill.
    """

    while True:
        item = task_queue.get()  # blocks until work is available, not busy-waiting
        if item is None:
            break
        task_id, battle_array = item
        state = GameState(battle_array)
        if state.is_terminal():
            result = evaluate_terminal(state)
        else:
            sim_state = mixed_rollout(state)
            result = evaluate_terminal(sim_state)
        result_queue.put((task_id, *result))


def mcts_async(
        root_state: GameState,
        max_iterations: int=750_000,
        terminal_iterations: int=2_000,
        num_workers: int=None
):
    """Main tree workflow"""
    if num_workers is None:
        num_workers = max(1, (mp.cpu_count() or 2) - 1)

    # The queues for the rollout worker import and export
    task_queue   = mp.Queue()
    result_queue = mp.Queue()

    workers = [
        mp.Process(target=_async_worker, args=(task_queue, result_queue), daemon=True)
        for _ in range(num_workers)
    ]
    for w in workers:
        w.start()

    root         = Node(root_state)
    in_flight    = {}   # task_id → path (so we can backprop when result arrives)
    next_task_id = 0
    iterations   = 0
    # Keep enough tasks ahead so workers never starve while main process selects
    pipeline_depth = num_workers * 2

    try:
        while iterations < max_iterations or in_flight:
            # Feed tasks until pipeline is full or iterations exhausted
            while len(in_flight) < pipeline_depth and iterations < max_iterations:
                state, path = _select_expand(root_state, root)
                for n in path:                  # virtual loss, so ucb dont keep choosing the same
                    n.visits      += 1
                    n.total_value -= 1
                in_flight[next_task_id] = path
                task_queue.put((next_task_id, state.battle_array.copy()))
                next_task_id += 1
                iterations   += 1

            # Collect completed results — block briefly to avoid busy-waiting
            try:
                task_id, value, win, dead = result_queue.get(timeout=0.001)
                path = in_flight.pop(task_id)
                # remove virtual loss to do the proper backdrop
                for n in path:
                    n.visits      -= 1
                    n.total_value += 1
                _backprop(path, value, win, dead)

                # Drain anything else already ready (no extra waiting)
                while not result_queue.empty():
                    task_id, value, win, dead = result_queue.get_nowait()
                    path = in_flight.pop(task_id)
                    for n in path:
                        n.visits      -= 1
                        n.total_value += 1
                    _backprop(path, value, win, dead)

            except Exception:
                pass

            if iterations % 500 == 0 and iterations > 0:
                terminal_node, terminal_path, actions = find_best_terminal_node(root)
                if terminal_node.snapshot.terminal and terminal_node.visits >= terminal_iterations:
                    print(f"Converged at {iterations} iterations, "
                          f"depth {len(terminal_path)-1}, visits {terminal_node.visits}")
                    print(f"Convergence path: {actions}")
                    break
    finally:
        for _ in workers:
            task_queue.put(None)   # Stop the waiting workers
        for w in workers:
            w.join()

    recursive_backup(root)
    print_best_path(root, root_state.battle_array)
