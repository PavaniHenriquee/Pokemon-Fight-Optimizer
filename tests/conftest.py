"""Shared pytest setup.

JIT is disabled for the whole test session BEFORE any project import, so tests start
instantly, can be debugged, and Python's `random` drives every roll. The real compiled
code is covered separately by test_jit_smoke.py (marker `jit`).
Set PYTEST_KEEP_JIT=1 to run the suite with JIT on instead.
"""
import os

if os.environ.get("PYTEST_KEEP_JIT") != "1":
    os.environ["NUMBA_DISABLE_JIT"] = "1"

# pylint: disable=wrong-import-position
import random
import numpy as np
import pytest
from battle_driver import _p, build


def pytest_addoption(parser):
    """--update-golden rewrites tests/golden/*.json instead of comparing against them"""
    parser.addoption(
        "--update-golden", action="store_true", default=False,
        help="Regenerate the engine golden snapshots",
    )


@pytest.fixture
def update_golden(request):
    """True when the run should rewrite golden files"""
    return request.config.getoption("--update-golden")


@pytest.fixture(autouse=True)
def _seed():
    """Every test starts from the same RNG state"""
    random.seed(1234)
    np.random.seed(1234)


@pytest.fixture
def make_pokemon():
    """Pokemon factory with sane defaults: make_pokemon("Pikachu", 10, "Static", ["Tackle"])"""
    return _p


@pytest.fixture
def poke(make_pokemon):
    """Pokemon array factory: poke("Charmander", 50, "Blaze", ["Ember"])"""
    def _make(*args, **kwargs):
        return make_pokemon(*args, **kwargs).to_np()
    return _make


@pytest.fixture
def make_battle():
    """Battle array factory: make_battle([my pokes], [opp pokes], trainer_items=())"""
    return build


@pytest.fixture
def one_v_one(make_pokemon, make_battle):
    """Charmander L5 (Oran Berry) vs Squirtle L5, the smallest useful battle"""
    def _build():
        my = [make_pokemon("Charmander", 5, "Blaze", ["Scratch", "Growl", "Ember"],
                           item="Oran Berry")]
        opp = [make_pokemon("Squirtle", 5, "Torrent", ["Tackle", "Tail Whip"])]
        return make_battle(my, opp)
    return _build
