"""Runs the real Numba-compiled engine + search in a subprocess (the rest of the suite has
JIT disabled). This is what catches typing errors, untyped None, unsupported Python in
@njit code, and errors that only exist compiled (e.g. ZeroDivisionError instead of inf).

    pytest -m jit

First run compiles everything (~1 min). The compile cache lives in
.numba_cache/tests/<hash of all project .py files>, so an unchanged codebase reruns in
seconds and ANY source edit forces a clean compile (Numba's own cache doesn't notice edits
to functions called from another file).
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import pytest

pytestmark = pytest.mark.jit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_BASE = os.path.join(ROOT, ".numba_cache", "tests")
SOURCE_DIRS = ("DataBase", "Engine", "Models", "SearchEngine", "Utils", "tests")

SCRIPT = r"""
import json, random, sys
import numpy as np
import numba
sys.path.insert(0, "tests")
import battle_driver as bd
from SearchEngine.models import GameState, Node
from SearchEngine.my_mcts import mcts_loop
from SearchEngine.mcts_eval import rollout_arr


# Numba has its own RNG, random.seed in Python doesn't reach compiled code.
# Plain numba.njit on purpose: a function defined in a -c script can't be cached.
@numba.njit
def seed_numba(seed):
    random.seed(seed)
    np.random.seed(seed)


results = {}
for name in bd.SCENARIOS:
    try:
        for seed in range(30):
            seed_numba(seed)
            arr = bd.build_scenario(name)
            bd.play_battle(arr, seed)
            assert bd.is_over(arr), f"seed {seed} didn't finish"
        seed_numba(1234)
        for _ in range(30):
            value, win, dead = rollout_arr(bd.build_scenario(name))
            assert 0.0 <= value <= 1.0
        results[name] = "ok"
    except Exception as exc:
        results[name] = f"{type(exc).__name__}: {exc}"

try:
    seed_numba(37)
    state = GameState(bd.build_scenario("starters"))
    root = Node(state)
    mcts_loop(root, state, max_iterations=600, terminal_iterations=10**9)
    assert root.visits == 600, root.visits
    results["mcts"] = "ok"
except Exception as exc:
    results["mcts"] = f"{type(exc).__name__}: {exc}"

print("JIT_RESULTS=" + json.dumps(results))
"""

CASES = ["starters", "status", "damage_sources", "multihit_items", "weather_charge", "mcts"]


def _source_hash():
    digest = hashlib.sha256()
    for folder in SOURCE_DIRS:
        for base, _, files in sorted(os.walk(os.path.join(ROOT, folder))):
            for f in sorted(files):
                if f.endswith((".py", ".json")):
                    with open(os.path.join(base, f), "rb") as fh:
                        digest.update(f.encode() + fh.read())
    return digest.hexdigest()[:12]


@pytest.fixture(scope="module", name="jit_results")
def fixture_jit_results():
    """Run the compiled smoke script once for the whole module"""
    key = _source_hash()
    if os.path.isdir(CACHE_BASE):
        for old in os.listdir(CACHE_BASE):
            if old != key:
                shutil.rmtree(os.path.join(CACHE_BASE, old), ignore_errors=True)
    env = {k: v for k, v in os.environ.items() if k != "NUMBA_DISABLE_JIT"}
    env["NUMBA_CACHE_ON"] = "1"
    env["NUMBA_CACHE_DIR"] = os.path.join(CACHE_BASE, key)
    proc = subprocess.run(
        [sys.executable, "-W", "ignore", "-c", SCRIPT],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=900, check=False,
    )
    line = next((l for l in proc.stdout.splitlines() if l.startswith("JIT_RESULTS=")), None)
    assert line, f"JIT subprocess crashed (exit {proc.returncode}):\n{proc.stderr[-4000:]}"
    return json.loads(line[len("JIT_RESULTS="):])


@pytest.mark.parametrize("case", CASES)
def test_compiled(jit_results, case):
    """Seeded battles + rollouts per scenario, and a short MCTS, all compiled"""
    assert jit_results[case] == "ok", jit_results[case]
