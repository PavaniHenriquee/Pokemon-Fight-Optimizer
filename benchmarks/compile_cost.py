"""Engine compile cost: the same work as backend/main.py _warm_up, each time in a fresh process."""
import json
import os
import subprocess
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _warm_up_battle():
    """The battle of backend/main.py _WARMUP_CONFIG"""
    from Engine.engine_helper import start_of_battle
    from Models.constants import _FIELD_AI_ITEM1, _FIELD_TURN, _POTIONS_POTION
    from Models.pokemon import Pokemon
    from Utils.helper import to_battle_array
    my_team = [Pokemon("Charmander", "Male", 5, "Blaze", "Hardy", ["Scratch", "Growl", "Ember"],
                       item="Oran Berry")]
    opp_team = [Pokemon("Squirtle", "Male", 5, "Torrent", "Hardy", ["Tackle", "Tail Whip"]),
                Pokemon("Bulbasaur", "Male", 5, "Overgrow", "Hardy", ["Tackle", "Growl"])]
    battle = to_battle_array(my_team, opp_team)
    if battle[_FIELD_TURN] == 0:
        start_of_battle(battle)
    battle[_FIELD_AI_ITEM1] = _POTIONS_POTION
    return battle


def _short_search(battle):
    """300 iterations of the backend's loop, which reaches everything a search compiles"""
    from SearchEngine.helper import prune_dominated
    from SearchEngine.models import GameState, Node
    from SearchEngine.my_mcts import (
        _backprop, _rollout, _select_expand, find_best_terminal_node,
    )
    from benchmarks.fights import seed_all
    state = GameState(battle)
    root = Node(state)
    seed_all(37)
    for i in range(300):
        s, path, actions = _select_expand(state.clone(), root)
        value, win, dead = _rollout(s)
        _backprop(path, actions, value, win, dead)
        if i % 250 == 0 and i > 0:
            find_best_terminal_node(root)
            prune_dominated(root)


def _probe():
    """What the fresh process runs. Its environment decides whether the Numba cache is on"""
    start = time.perf_counter()
    import psutil
    _short_search(_warm_up_battle())
    memory = psutil.Process().memory_info()
    print(json.dumps({
        "seconds": time.perf_counter() - start,
        "peak_mb": getattr(memory, "peak_wset", memory.rss) / 2**20,
    }))


def _measure(**env_changes):
    env = dict(os.environ, **env_changes)
    if env.get("NUMBA_CACHE_ON") == "0":
        env.pop("NUMBA_CACHE_DIR", None)
    done = subprocess.run(
        [sys.executable, "-m", "benchmarks.compile_cost"],
        cwd=_ROOT, env=env, capture_output=True, text=True, check=True,
    )
    return json.loads(done.stdout.strip().splitlines()[-1])


def _folder_mb(path):
    return sum(
        os.path.getsize(os.path.join(base, f)) for base, _, files in os.walk(path) for f in files
    ) / 2**20


def run(report, budget):
    """No cache, then loading the current cache. A smoke run skips the slow one"""
    report.heading("Engine compile")
    rows = []

    def add(label, key, result):
        rows.append((label, f"{result['seconds']:.1f} s", f"{result['peak_mb']:,.0f} MB"))
        report.metric(f"compile/{key}_s", result["seconds"])
        report.metric(f"compile/{key}_peak_mb", result["peak_mb"])

    if not budget.smoke:
        add("Without cache", "no_cache", _measure(NUMBA_CACHE_ON="0"))
    best = min((_measure() for _ in range(3)), key=lambda r: r["seconds"])
    size = _folder_mb(os.environ.get("NUMBA_CACHE_DIR", ""))
    add(f"Loading the Numba cache ({size:.0f} MB), best of 3", "cache_load", best)
    report.table(("Engine start", "Time", "Peak memory"), rows)


if __name__ == "__main__":
    _probe()
