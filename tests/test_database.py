"""Every JSON database entry converts to its array form, and saved teams build"""
import json
import os
import pytest
from DataBase.loader import moveDB, abDB, itemDB, pkDB
from Models.move import Moves
from Models.ability import ability_to_np
from Models.item import item_to_np
from Models.pokemon import Pokemon
from Models.idx_const import MOVE_STRIDE, AB_LEN, ITEM_LEN, POK_LEN, Move, Item
from Models.helper import HoldEffect

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Moves in MoveDB.json whose VolStatus/SideCondition/damage type isn't in the engine yet. They
# must still fail to convert: once you implement one, test_move_converts fails and tells you to
# drop it from this set. Trainer and box Pokemon using them are skipped the same way.
UNSUPPORTED_MOVES = set()


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


def _failures(items, check):
    """Runs check(item) on every item, returns {label: error} for the ones that raise or fail"""
    bad = {}
    for label, item in items:
        try:
            check(item)
        except Exception as e:
            bad[label] = repr(e)
    return bad


def _move_block(entry):
    return Moves(entry).to_array()


def _species_block(name):
    return Pokemon(name, "Male", 50, "Blaze", "Hardy", ["Tackle"]).to_np()


def _team_block(entry):
    return _team_entry_to_pokemon(entry).to_np()


def _block_check(convert, length):
    """Converted block has the right length and a non-zero id (0 means an empty slot)"""
    def check(entry):
        arr = convert(entry)
        assert arr.shape == (length,) and arr[0] != 0, arr[:1]
    return check


def test_move_converts():
    """Every MoveDB entry → move block, and every UNSUPPORTED_MOVES entry still fails"""
    check = _block_check(_move_block, MOVE_STRIDE)
    supported = [(n, moveDB[n]) for n in sorted(moveDB) if n not in UNSUPPORTED_MOVES]
    assert not _failures(supported, check)
    unsupported = [(n, moveDB[n]) for n in sorted(UNSUPPORTED_MOVES)]
    converts = set(UNSUPPORTED_MOVES) - set(_failures(unsupported, check))
    assert not converts, f"Implemented now, drop from UNSUPPORTED_MOVES: {sorted(converts)}"


def test_ability_converts():
    """Every AbilitiesDB entry → ability block"""
    items = [(n, abDB[n]) for n in sorted(abDB)]
    assert not _failures(items, _block_check(ability_to_np, AB_LEN))


def test_item_converts():
    """Every ItemDB entry → item block"""
    items = [(n, itemDB[n]) for n in sorted(itemDB)]
    assert not _failures(items, _block_check(item_to_np, ITEM_LEN))


def test_item_hold_effects():
    """Every ItemDB entry has a hold effect, and the per-type ones (type items, resist berries)
    carry their type"""
    typed = (HoldEffect.TYPE_BOOST, HoldEffect.WEAKEN_SE, HoldEffect.WEAKEN_NORMAL)
    def check(entry):
        arr = item_to_np(entry)
        effect, effect_type = arr[Item.HOLD_EFFECT - Item.ID], arr[Item.EFFECT_TYPE - Item.ID]
        assert effect != 0
        assert (effect_type != 0) == (effect in typed), (effect, effect_type)
    items = [(n, itemDB[n]) for n in sorted(itemDB)]
    assert not _failures(items, check)


def test_species_converts():
    """Every species in PkDB can be built and serialised"""
    items = [(n, n) for n in sorted(pkDB)]
    assert not _failures(items, _block_check(_species_block, POK_LEN))


def _team_items(entries, label):
    """(label, entry) for the team entries that don't use an unsupported move"""
    return [
        (f"{label}-{i}-{e['name']}", e) for i, e in enumerate(entries)
        if not set(e["moves"]) & UNSUPPORTED_MOVES
    ]


TRAINER_DB = _load_json("DataBase", "TrainerDB.json")


def test_trainer_pokemon_build():
    """Every TrainerDB Pokemon builds, catches typos in names/moves/items/abilities"""
    items = [
        it for trainer, data in TRAINER_DB.items() for it in _team_items(data["team"], trainer)
    ]
    assert not _failures(items, _block_check(_team_block, POK_LEN))


def test_trainer_db_shape():
    """Each trainer has a sprite and 1-6 Pokemon"""
    for trainer, data in TRAINER_DB.items():
        assert "sprite" in data, trainer
        assert 1 <= len(data["team"]) <= 6, trainer
        for p in data["team"]:
            assert len(p["moves"]) <= 4, (trainer, p["name"])


def test_box_pokemon_build():
    """Every saved box entry builds"""
    items = _team_items(_load_json("UserData", "box.json"), "box")
    assert not _failures(items, _block_check(_team_block, POK_LEN))



@pytest.mark.parametrize("name, expected", [
    ("Growl", 1),         # Status: defaults to ignoring type immunity
    ("Sand Attack", 1),
    ("Thunder Wave", 0),  # explicit ignoreImmunity: false
    ("Tackle", 0),        # damaging moves respect immunity
])
def test_ignore_immunity_flag(name, expected):
    """Move.IGNORE_IMMUNITY follows Showdown's ignoreImmunity default"""
    assert Moves(moveDB[name]).to_array()[Move.IGNORE_IMMUNITY] == expected


def test_growth_is_gen4():
    """Gen IV Growth raises only Sp. Atk (RP sheet, Showdown gen4 mod)"""
    arr = Moves(moveDB["Growth"]).to_array()
    assert (arr[Move.BOOST_ATK], arr[Move.BOOST_SPATK]) == (0, 1)
