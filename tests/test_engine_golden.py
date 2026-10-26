"""Golden snapshots of whole seeded battles, ENGINE ONLY.

Each scenario/seed is played with random legal actions vs the trainer AI and the final
battle_array is hashed. Any change to engine/AI behaviour or to the RNG call order changes
the hash. That's the point: it should only move when you implement a move or fix a bug.

When the change is intended, re-bless with:
    pytest tests/test_engine_golden.py --update-golden
and review the diff of tests/golden/engine_battles.json (turns and HPs are stored next to
the hash so you can see what moved).
"""
import hashlib
import json
import os
import pytest
from Models.idx_const import Pok
from battle_driver import SCENARIOS, build_scenario, play_battle, pok_slice

GOLDEN_PATH = os.path.join(os.path.dirname(__file__), "golden", "engine_battles.json")
SEEDS = range(20)

# Numba has its own RNG stream, the snapshots are recorded with Python's (JIT disabled)
pytestmark = pytest.mark.skipif(
    os.environ.get("NUMBA_DISABLE_JIT") != "1", reason="golden data is recorded with JIT off"
)


def run_snapshot(name, seed):
    """Play one battle and summarise its final state"""
    arr = build_scenario(name)
    turns = play_battle(arr, seed)
    return {
        "turns": turns,
        "my_hp": [int(pok_slice(arr, i)[Pok.CURRENT_HP]) for i in range(6)],
        "opp_hp": [int(pok_slice(arr, i, True)[Pok.CURRENT_HP]) for i in range(6)],
        "hash": hashlib.sha256(arr.astype("<i4").tobytes()).hexdigest()[:16],
    }


def _dump(data):
    """One line per seed so a re-bless diff shows exactly which battles moved"""
    lines = ["{"]
    for i, name in enumerate(sorted(data)):
        lines.append(f"  {json.dumps(name)}: {{")
        seeds = sorted(data[name], key=int)
        for j, seed in enumerate(seeds):
            comma = "," if j < len(seeds) - 1 else ""
            lines.append(f"    {json.dumps(seed)}: {json.dumps(data[name][seed])}{comma}")
        lines.append("  }" + ("," if i < len(data) - 1 else ""))
    lines.append("}")
    return "\n".join(lines) + "\n"


def _load():
    if not os.path.exists(GOLDEN_PATH):
        return {}
    with open(GOLDEN_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module", name="golden")
def fixture_golden(request):
    """Stored snapshots, written back at the end of the module when updating"""
    data = _load()
    yield data
    if request.config.getoption("--update-golden"):
        os.makedirs(os.path.dirname(GOLDEN_PATH), exist_ok=True)
        with open(GOLDEN_PATH, "w", encoding="utf-8") as f:
            f.write(_dump(data))


@pytest.mark.parametrize("name", SCENARIOS)
def test_engine_matches_golden(name, golden, update_golden):
    """Every seed of the scenario ends exactly like the stored snapshot"""
    got = {str(seed): run_snapshot(name, seed) for seed in SEEDS}
    if update_golden:
        golden[name] = got
        return
    if name not in golden:
        pytest.fail(f"No golden data for '{name}', run with --update-golden")
    expected = golden[name]
    diffs = [
        f"  seed {s}: turns {expected[s]['turns']}→{got[s]['turns']}, "
        f"my_hp {expected[s]['my_hp']}→{got[s]['my_hp']}, "
        f"opp_hp {expected[s]['opp_hp']}→{got[s]['opp_hp']}"
        for s in got if s not in expected or expected[s] != got[s]
    ]
    assert not diffs, (
        f"Engine behaviour changed in scenario '{name}' ({len(diffs)}/{len(got)} seeds). "
        "If intended, re-run with --update-golden.\n" + "\n".join(diffs)
    )
