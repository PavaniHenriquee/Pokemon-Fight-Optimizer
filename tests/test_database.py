"""Every JSON database entry converts to its array form, and saved teams build"""
import json
import os
import pytest
from DataBase.loader import moveDB, abDB, itemDB, pkDB
from Models.move import Moves
from Models.ability import ability_to_np
from Models.item import item_to_np
from Models.pokemon import Pokemon
from Models.idx_const import MOVE_STRIDE, AB_LEN, ITEM_LEN, POK_LEN

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Moves in MoveDB.json whose VolStatus/SideCondition/damage type isn't in the engine yet.
# Strict xfail: once you implement one, its test XPASSes and fails, telling you to drop it
# from this list.
UNSUPPORTED_MOVES = {
    "Aqua Ring", "Bind", "Charge", "Clamp", "Destiny Bond", "Encore", "Endure", "Fire Spin",
    "Follow Me", "Foresight", "Helping Hand", "Ingrain", "Low Kick", "Lucky Chant", "Mist",
    "Nightmare", "Odor Sleuth", "Protect", "Safeguard", "Taunt", "Whirlpool", "Wrap", "Yawn",
}


def _mark_unsupported(names):
    return [
        pytest.param(n, marks=pytest.mark.xfail(strict=True, reason="not implemented yet"))
        if n in UNSUPPORTED_MOVES else n
        for n in names
    ]


def _load_json(*parts):
    with open(os.path.join(ROOT, *parts), "r", encoding="utf-8") as f:
        return json.load(f)


def _team_entry_to_pokemon(entry):
    """Same conversion backend/main.py does for TrainerDB and box entries"""
    return Pokemon(
        entry["name"], entry.get("gender"), entry["level"], entry["ability"],
        entry.get("nature", "Hardy"), [m for m in entry["moves"] if m],
        ivs=entry.get("ivs"), item=entry.get("item"),
    )


@pytest.mark.parametrize("name", _mark_unsupported(sorted(moveDB)))
def test_move_converts(name):
    """MoveDB entry → move block of the right length"""
    arr = Moves(moveDB[name]).to_array()
    assert arr.shape == (MOVE_STRIDE,)
    assert arr[0] != 0, "Move ID must be non-zero, 0 means empty slot"


@pytest.mark.parametrize("name", sorted(abDB))
def test_ability_converts(name):
    """AbilitiesDB entry → ability block"""
    arr = ability_to_np(abDB[name])
    assert arr.shape == (AB_LEN,)
    assert arr[0] != 0


@pytest.mark.parametrize("name", sorted(itemDB))
def test_item_converts(name):
    """ItemDB entry → item block"""
    arr = item_to_np(itemDB[name])
    assert arr.shape == (ITEM_LEN,)
    assert arr[0] != 0


@pytest.mark.parametrize("name", sorted(pkDB))
def test_species_converts(name):
    """Every species in PkDB can be built and serialised"""
    arr = Pokemon(name, "Male", 50, "Blaze", "Hardy", ["Tackle"]).to_np()
    assert arr.shape == (POK_LEN,)
    assert arr[0] != 0


def _team_params(entries, label):
    params = []
    for i, entry in enumerate(entries):
        bad = sorted(set(entry["moves"]) & UNSUPPORTED_MOVES)
        marks = [pytest.mark.xfail(strict=True, reason=f"uses {bad}")] if bad else []
        params.append(pytest.param(entry, id=f"{label}-{i}-{entry['name']}", marks=marks))
    return params


TRAINER_DB = _load_json("DataBase", "TrainerDB.json")
TRAINER_POKEMON = [
    p for trainer, data in TRAINER_DB.items()
    for p in _team_params(data["team"], trainer)
]


@pytest.mark.parametrize("entry", TRAINER_POKEMON)
def test_trainer_pokemon_builds(entry):
    """Every TrainerDB Pokemon builds, catches typos in names/moves/items/abilities"""
    assert _team_entry_to_pokemon(entry).to_np().shape == (POK_LEN,)


def test_trainer_db_shape():
    """Each trainer has a sprite and 1-6 Pokemon"""
    for trainer, data in TRAINER_DB.items():
        assert "sprite" in data, trainer
        assert 1 <= len(data["team"]) <= 6, trainer
        for p in data["team"]:
            assert len(p["moves"]) <= 4, (trainer, p["name"])


@pytest.mark.parametrize("entry", _team_params(_load_json("UserData", "box.json"), "box"))
def test_box_pokemon_builds(entry):
    """Every saved box entry builds"""
    assert _team_entry_to_pokemon(entry).to_np().shape == (POK_LEN,)
