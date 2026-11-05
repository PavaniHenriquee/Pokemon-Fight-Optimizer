"""Every JSON database entry converts to its array form, and saved teams build"""
import csv
import io
import json
import os
import pytest
from DataBase.loader import moveDB, abDB, itemDB, pkDB
from DataBase.import_learnsets import move_key, parse_dex, species_name, with_learnsets
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
    """Every saved box entry builds (the committed file is empty: the app starts with an empty box)"""
    empty = os.path.getsize(os.path.join(ROOT, "UserData", "box.json")) == 0
    items = _team_items([] if empty else _load_json("UserData", "box.json"), "box")
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


@pytest.mark.parametrize("name, stats", [
    ("Azumarill", (110, 50, 80, 80, 80, 50)),
    ("Sudowoodo", (90, 115, 125, 30, 75, 30)),
    ("Qwilfish", (65, 95, 95, 45, 55, 95)),
    ("Delibird", (45, 85, 50, 110, 50, 110)),
    ("Mothim", (70, 70, 50, 110, 50, 100)),
    ("Cresselia", (120, 70, 120, 75, 130, 85)),
])
def test_base_stats_are_rp_complete(name, stats):
    """The RP sheet's DEX tab, COM line (these species held Classic or vanilla numbers)"""
    assert tuple(pkDB[name]["base stats"].values()) == stats


def test_species_learnsets():
    """Every species has level-up moves in level order, and a move the engine has uses MoveDB's spelling"""
    spelling = {move_key(name): name for name in moveDB}
    def check(entry):
        levels = [level for level, _ in entry["learnset"]]
        assert levels and levels == sorted(levels) and levels[0] >= 1 and levels[-1] <= 100, levels
        wrong = [move for _, move in entry["learnset"] if spelling.get(move_key(move), move) != move]
        assert not wrong, wrong
    assert not _failures(sorted(pkDB.items()), check)


def _dex_row(name="", level="", move=""):
    """A row of the sheet's DEX tab, with only the columns the importer reads"""
    row = [""] * 15
    row[1], row[13], row[14] = name, level, move
    return row


def _dex_csv(rows):
    out = io.StringIO()
    csv.writer(out).writerows(rows)
    return out.getvalue()


def test_import_reads_only_level_up_moves():
    """Change marks are dropped, MoveDB's spelling wins, TM rows and other blocks' cells don't count"""
    dex = _dex_csv([
        _dex_row("#003 Venusaur", "LEARNSET"),
        _dex_row(level="Level Up :"),
        _dex_row(level="1", move="Earth Power (!!)"),
        _dex_row(level="5", move="Mud-slap᠎"),
        _dex_row(level="TMs HMs :"),
        _dex_row(level="TM06", move="Toxic"),
        _dex_row("#386 Deoxys (Attack)", "LEARNSET"),
        _dex_row(level="Level Up :"),
        _dex_row(level="1", move="Leer"),
    ])
    assert parse_dex(dex, ["Mud-Slap", "Leer"]) == {
        "Venusaur": [[1, "Earth Power"], [5, "Mud-Slap"]],
        "Deoxys_attack": [[1, "Leer"]],
    }


def test_import_fails_on_an_unexpected_cell():
    """A layout change in the sheet stops the import instead of writing bad data"""
    dex = _dex_csv([_dex_row("#001 Bulbasaur", "LEARNSET"), _dex_row(level="not a level", move="Tackle")])
    with pytest.raises(ValueError):
        parse_dex(dex, [])


@pytest.mark.parametrize("header, name", [
    ("#001 Bulbasaur", "Bulbasaur"),
    ("#029 Nidoran ♀", "Nidoran_f"),
    ("#032 Nidoran ♂", "Nidoran_m"),
    ("#479 Rotom (Spin)", "Rotom_fan"),
    ("#487 Giratina (Altered)", "Giratina"),
])
def test_import_species_names(header, name):
    """Sheet headers map to PkDB names"""
    assert species_name(header) == name


def test_import_only_adds_lines():
    """The learnset goes right before weight, in the format Prettier keeps on save (a single entry
    stays inline), and a rerun replaces it instead of adding another"""
    text = '{\n  "Abra": {\n    "abilities": ["Synchronize"],\n    "weight": 19.5\n  }\n}\n'
    weight = '    "weight"'
    one = with_learnsets(text, {"Abra": [[1, "Teleport"]]})
    assert one == text.replace(weight, f'    "learnset": [[1, "Teleport"]],\n{weight}')
    two = with_learnsets(one, {"Abra": [[1, "Teleport"], [9, "Confusion"]]})
    block = '    "learnset": [\n      [1, "Teleport"],\n      [9, "Confusion"]\n    ],\n'
    assert two == text.replace(weight, f"{block}{weight}")
    assert with_learnsets(two, {"Abra": [[1, "Teleport"]]}) == one


def test_pkdb_keeps_the_importers_format():
    """Rerunning the import changes nothing, so saving PkDB.json in the editor won't either"""
    with open(os.path.join(ROOT, "DataBase", "PkDB.json"), encoding="utf-8", newline="") as f:
        text = f.read()
    assert with_learnsets(text, {name: entry["learnset"] for name, entry in pkDB.items()}) == text
