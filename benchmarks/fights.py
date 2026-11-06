"""The test fights behind the numbers in NN_PLAN.md, and the helpers to build and seed them.

TrainerDB entries are used whole with only the level changed, and foes keep their TrainerDB items.
build_battle does what backend/main.py _build_battle does. backend isn't imported here because
importing it turns on its own Numba cache and deletes old cache folders.
"""
import json
import os
import random
import numpy as np
from Engine.engine_helper import start_of_battle
from Models.constants import (
    _FIELD_AI_ITEM1, _FIELD_AI_ITEM2, _FIELD_AI_ITEM3, _FIELD_AI_ITEM4, _FIELD_TERRAIN, _FIELD_TURN,
    _POTIONS_FULL_HEAL, _POTIONS_FULL_RESTORE, _POTIONS_HYPER_POTION, _POTIONS_POTION,
    _POTIONS_SUPER_POTION, _POTIONS_X_DEFEND, _POTIONS_X_SPECIAL, _POTIONS_X_SPEED,
)
from Models.helper import Terrain
from Models.pokemon import Pokemon
from Utils.helper import to_battle_array
from Utils.jit import njit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT, "DataBase", "TrainerDB.json"), encoding="utf-8") as _f:
    TRAINERS = json.load(_f)

_ITEM_FIELDS = (_FIELD_AI_ITEM1, _FIELD_AI_ITEM2, _FIELD_AI_ITEM3, _FIELD_AI_ITEM4)
_ITEMS = {
    "Potion": _POTIONS_POTION, "Super Potion": _POTIONS_SUPER_POTION,
    "Hyper Potion": _POTIONS_HYPER_POTION, "Full Restore": _POTIONS_FULL_RESTORE,
    "Full Heal": _POTIONS_FULL_HEAL, "X Special": _POTIONS_X_SPECIAL,
    "X Defend": _POTIONS_X_DEFEND, "X Speed": _POTIONS_X_SPEED,
}
_IVS_30 = {
    "HP": 30, "Attack": 30, "Defense": 30, "Special Attack": 30, "Special Defense": 30, "Speed": 30,
}


@njit
def seed_numba(seed):
    """Numba's RNG is separate from Python's and NumPy's"""
    random.seed(seed)
    np.random.seed(seed)


def seed_all(seed):
    """Seeds every RNG a process uses"""
    random.seed(seed)
    np.random.seed(seed)
    seed_numba(seed)


def _mon(name, level, ability, moves, nature="Hardy", ivs=None, item=None, gender="Male"):
    return {
        "name": name, "level": level, "ability": ability, "moves": moves, "nature": nature,
        "ivs": ivs, "item": item, "gender": gender,
    }


def _from_trainer(trainer, species, level):
    """A whole TrainerDB entry with the level replaced"""
    for p in TRAINERS[trainer]["team"]:
        if p["name"] == species:
            return _mon(
                p["name"], level, p["ability"], p["moves"], p["nature"], p.get("ivs"),
                p.get("item"), p.get("gender", "Male"),
            )
    raise KeyError(f"{species} isn't in {trainer}")


_WEAK_TEAM = (
    ("Camper Curtis 1", "Diglett"), ("Barry 2-C", "Piplup"), ("Worker Colin 1", "Geodude"),
    ("Youngster Sebastian 1", "Makuhita"), ("Lass Madeline 1", "Psyduck"),
    ("Reporter Helen 1", "Torchic"),
)


def _weak_team(size, level):
    return [_from_trainer(t, s, level) for t, s in _WEAK_TEAM[:size]]


def _good_team():
    return [
        _mon("Grotle", 18, "Overgrow", ["Razor Leaf", "Curse", "Tackle"]),
        _mon("Prinplup", 18, "Torrent", ["Water Pulse", "Peck", "Pound"], nature="Gentle",
             ivs=_IVS_30, item="Oran Berry"),
        _from_trainer("Lass Madeline 1", "Psyduck", 17),
        _from_trainer("Youngster Sebastian 1", "Makuhita", 17),
    ]


FIGHTS = {
    "Roark good": (_good_team, "Gym Leader Roark 1"),
    "Roark weak": (lambda: _weak_team(6, 16), "Gym Leader Roark 1"),
    "Barry 2-P": (lambda: _weak_team(3, 14), "Barry 2-P"),
    "Dallas": (lambda: _weak_team(2, 12), "Youngster Dallas 1"),
}


def _pokemon(p):
    moves = [m for m in p["moves"] if m]
    return Pokemon(
        p["name"], p["gender"], p["level"], p["ability"], p["nature"], moves,
        ivs=p["ivs"], item=p["item"] or None,
    )


def fight(name):
    """A fresh battle array for a named fight"""
    team, trainer = FIGHTS[name]
    entry = TRAINERS[trainer]
    foes = [
        _pokemon(_mon(
            p["name"], p["level"], p["ability"], p["moves"], p["nature"], p.get("ivs"),
            p.get("item"), p.get("gender", "Male"),
        )) for p in entry["team"]
    ]
    battle = to_battle_array([_pokemon(p) for p in team()], foes)
    if battle[_FIELD_TURN] == 0:
        start_of_battle(battle)
    for i, item in enumerate(entry.get("trainer_items", [])[:4]):
        value = _ITEMS.get(item, 0)
        if value:
            battle[_ITEM_FIELDS[i]] = value
    battle[_FIELD_TERRAIN] = getattr(Terrain, entry.get("terrain", "plain").upper())
    return battle
