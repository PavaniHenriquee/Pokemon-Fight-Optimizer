"""Every JSON database entry converts to its array form, and saved teams build"""
import csv
import io
import json
import os
import pytest
from DataBase.loader import moveDB, abDB, itemDB, pkDB
from DataBase.import_learnsets import move_key, parse_dex, species_name, with_learnsets
from DataBase.import_encounters import (
    STATS_EVOLUTION_COL, STATS_EVOLUTION_TITLE, db_text, parse_encounters, parse_evolution_lines,
    parse_evolutions,
)
from DataBase import import_items
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


# The starter each rival has, by the starter you chose (the sheet's ROARK SPLIT tab, "IF YOU CHOSE ...").
# Barry takes the one that beats yours, Lucas / Dawn the one left. The key's letter is Barry's rule for
# all of them, so it's wrong for Lucas and Dawn: Lucas 1-P has Turtwig, met if you chose Chimchar
RIVAL_STARTER = {
    "Barry": {"Turtwig": "Chimchar", "Chimchar": "Piplup", "Piplup": "Turtwig"},
    "Lucas": {"Turtwig": "Piplup", "Chimchar": "Turtwig", "Piplup": "Chimchar"},
    "Dawn": {"Turtwig": "Piplup", "Chimchar": "Turtwig", "Piplup": "Chimchar"},
}


def _rival_entries():
    return {name: t for name, t in TRAINER_DB.items() if name.split()[0] in RIVAL_STARTER}


def test_rival_variants_match_the_starter():
    """if_starter on every rival variant says which team the sheet gives that starter"""
    rivals = _rival_entries()
    assert len(rivals) == 12
    for name, trainer in rivals.items():
        species = [p["name"] for p in trainer["team"]]
        assert RIVAL_STARTER[name.split()[0]][trainer["if_starter"]] in species, name
    others = [name for name, t in TRAINER_DB.items() if name not in rivals and "if_starter" in t]
    assert not others


@pytest.mark.parametrize("starter", ["Turtwig", "Chimchar", "Piplup"])
def test_a_starter_leaves_one_of_each_rival(starter):
    """A starter leaves Barry 1, Lucas 1, Dawn 1, Barry 2. Choosing a gender then drops Lucas or Dawn"""
    left = {
        name: t for name, t in TRAINER_DB.items() if t.get("if_starter") == starter
    }
    assert sorted(name.rsplit("-", 1)[0] for name in left) == [
        "Barry 1", "Barry 2", "Dawn 1", "Lucas 1",
    ]
    for player, kept in (("Female", "Lucas"), ("Male", "Dawn")):
        names = [n for n, t in left.items() if t.get("if_player", player) == player]
        assert sorted(n.split()[0] for n in names) == sorted(["Barry", "Barry", kept])


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


def test_genderless_species():
    """[SD] pokedex gender "N" and [pp] GENDER_RATIO_NO_GENDER agree on every species, forms included"""
    assert {name for name, entry in pkDB.items() if entry.get("genderless") is True} == {
        "Magnemite", "Magneton", "Magnezone", "Voltorb", "Electrode", "Staryu", "Starmie", "Ditto",
        "Porygon", "Porygon2", "Porygon_z", "Articuno", "Zapdos", "Moltres", "Mewtwo", "Mew", "Unown",
        "Raikou", "Entei", "Suicune", "Lugia", "Ho_oh", "Celebi", "Shedinja", "Lunatone", "Solrock",
        "Baltoy", "Claydol", "Beldum", "Metang", "Metagross", "Regirock", "Regice", "Registeel", "Kyogre",
        "Groudon", "Rayquaza", "Jirachi", "Deoxys", "Deoxys_attack", "Deoxys_defense", "Deoxys_speed",
        "Bronzor", "Bronzong", "Rotom", "Rotom_heat", "Rotom_wash", "Rotom_frost", "Rotom_fan", "Rotom_mow",
        "Uxie", "Mesprit", "Azelf", "Dialga", "Palkia", "Regigigas", "Giratina", "Giratina_origin",
        "Phione", "Manaphy", "Darkrai", "Shaymin", "Shaymin_sky", "Arceus",
    }
    assert not any("genderless" in entry and entry["genderless"] is not True for entry in pkDB.values())


def test_trainer_genders_follow_the_species():
    """A trainer's Pokemon has no gender only if its species has none"""
    def check(entry):
        assert (not entry.get("gender")) == bool(pkDB[entry["name"]].get("genderless")), entry["gender"]
    trainers = _load_json("DataBase", "TrainerDB.json")
    team = [(f"{name} {m['name']}", m) for name, trainer in trainers.items() for m in trainer["team"]]
    assert not _failures(team, check)


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


def _encounter_csv(*groups) -> str:
    """The ENCOUNTERS tab's CSV: each group a list of rows, each row its first cells. Row 0 is empty and
    the master table marks where the groups end, like in the sheet"""
    height = max(len(g) for g in groups) + 1
    width = 4 + 7 * len(groups) + 1
    rows = [[""] * width for _ in range(height)]
    rows[1][width - 1] = "MT CORONET MASTER TABLE"
    for g, group in enumerate(groups):
        for r, cells in enumerate(group, start=1):
            rows[r][4 + 7 * g:4 + 7 * g + len(cells)] = cells
    out = io.StringIO()
    csv.writer(out).writerows(rows)
    return out.getvalue()


STARTER_BLOCK = [
    ["ROUTE 201"],
    ["Gift from Professor Rowan"],
    ["", "#387 Turtwig", "5", "-"],
    ["", "#390 Chimchar", "5", "-"],
    ["Grass (4-5)", "", "", "M", "D", "N"],
    ["", "#396 Starly", "4-5", "30", "30", "30"],
]
ENCOUNTER_SPECIES = {
    "Turtwig", "Chimchar", "Starly", "Bidoof", "Spheal", "Ponyta", "Heatran", "Golbat", "Regirock",
}


def _parse_encounters(*groups) -> dict:
    return parse_encounters(_encounter_csv(STARTER_BLOCK, *groups), ENCOUNTER_SPECIES)


def _names(table: dict) -> list:
    return [mon["name"] for mon in table["mons"]]


def test_encounters_starters_leave_route_201():
    """Rowan's gift becomes the starters, and Route 201 only keeps its own encounters"""
    db = _parse_encounters()
    assert db["starters"] == ["Turtwig", "Chimchar"]
    assert [t["method"] for t in db["locations"]["Route 201"]] == ["Grass (4-5)"]


def test_encounters_merge_a_location_split_in_blocks():
    """Two blocks of one met location are one location, each table keeping its area"""
    db = _parse_encounters([
        ["ROUTE 204 (SOUTH)"],
        ["Grass (6-7)"],
        ["", "#396 Starly", "6-6"],
        ["ROUTE 204 (NORTH)"],
        ["Grass (11-12)"],
        ["", "#399 Bidoof", "11-11"],
    ])
    assert [(t["area"], _names(t)) for t in db["locations"]["Route 204"]] == [
        ("South", ["Starly"]), ("North", ["Bidoof"]),
    ]
    assert db["locations"]["Route 204"][0]["mons"][0]["level"] == "6-6"


def test_encounters_alias_is_a_met_location():
    """A heading [pp] gives another location's label joins that location"""
    db = _parse_encounters(
        [["ROUTE 209"], ["Grass (24-26)"], ["", "#396 Starly", "24-24"]],
        [["LOST TOWER"], ["Details on how to encounter it here :"], ["", "#399 Bidoof", "70", "-"]],
    )
    assert "Lost Tower" not in db["locations"]
    assert [t["area"] for t in db["locations"]["Route 209"]] == ["", "Lost Tower"]


def test_encounters_trail_headings_are_not_locations():
    """A heading with no Pokemon under it is only the sheet's trail between places"""
    db = _parse_encounters([
        ["BICYCLE SHOP"],
        [""],
        ["ROUTE 206"],
        ["Grass (20-22)"],
        ["", "#396 Starly", "21-21"],
    ])
    assert "Bicycle Shop" not in db["locations"] and "Route 206" in db["locations"]


def test_encounters_trade_gets_only_what_you_receive():
    """A trade's 'you give' row isn't an encounter, and the '(details :' link text is dropped"""
    db = _parse_encounters([
        ["OREBURGH CITY"],
        ["Trade with a Schoolgirl (details :", "", "", "?"],
        ["", "#077 Ponyta", "-", "you give"],
        ["", "#363 Spheal", "-", "you get"],
    ])
    table = db["locations"]["Oreburgh City"][0]
    assert table["method"] == "Trade with a Schoolgirl"
    assert table["mons"] == [{"name": "Spheal", "level": ""}]


def test_encounters_continuation_group_belongs_to_the_left_block():
    """A group with nothing in row 1 continues the block on its left at the same row: a method line
    joins that location, a Pokemon with no method line wraps into its last table"""
    db = _parse_encounters(
        [
            ["ROUTE 209"],
            ["Surf (20-40)"],
            ["", "#396 Starly", "20-30"],
        ],
        [
            [""],
            [""],
            [""],
            ["", "#399 Bidoof", "20-40"],
            ["Rods (O-10, G-25, S-50)", "", "", "O", "G", "S"],
            ["", "#363 Spheal", "", "100", "0", "0"],
        ],
    )
    assert [(t["method"], _names(t)) for t in db["locations"]["Route 209"]] == [
        ("Surf (20-40)", ["Starly", "Bidoof"]), ("Old Rod (10)", ["Spheal"]),
    ]


def test_encounters_pokemon_for_a_method_line_on_the_left():
    """A method line whose Pokemon sit in the next group gets them, even with newer tables around
    (Heatran), and a heading's scope ends at a blank row in a continuation group"""
    db = _parse_encounters(
        [
            ["STARK MOUNTAIN"],
            ["After the Events of Stark Mountain. Talk to Buck"],
            [""],
            [""],
            [""],
            [""],
            ["HALL OF ORIGIN"],
            ["Details on how to encounter it here :", "", "", "?"],
        ],
        [
            [""],
            ["STARK MOUNTAIN (INSIDE)"],
            ["Cave (67-69)", "", "", "M", "D", "N"],
            ["", "#042 Golbat", "67-67"],
            [""],
            ["", "#485 Heatran", "68", "-"],
            [""],
            ["", "#377 Regirock", "80", "-"],
        ],
    )
    tables = db["locations"]["Stark Mountain"]
    assert [(t["area"], t["method"], _names(t)) for t in tables] == [
        ("", "After the Events of Stark Mountain. Talk to Buck", ["Heatran"]),
        ("Inside", "Cave (67-69)", ["Golbat"]),
    ]
    assert _names(db["locations"]["Hall of Origin"][0]) == ["Regirock"]


def test_encounters_legendary_lists_repeat_nothing_and_keep_the_story_order():
    """The sheet's lists of legendaries are read last, repeats dropped, so a location keeps its place"""
    db = _parse_encounters(
        [
            ["POST DISTORTION WORLD LEGENDARIES"],
            ["VICTORY ROAD"],
            ["Details on how to encounter it here :", "", "", "?"],
            ["", "#396 Starly", "60", "-"],
            ["ROCK PEAK RUINS"],
            ["Details on how to encounter it here :", "", "", "?"],
            ["", "#377 Regirock", "60", "-"],
        ],
        [
            ["ROUTE 206"],
            ["Grass (20-22)"],
            ["", "#399 Bidoof", "21-21"],
        ],
        [
            ["VICTORY ROAD"],
            ["Static Encounter"],
            ["", "#396 Starly", "60", "-"],
        ],
    )
    assert list(db["locations"]) == ["Route 201", "Route 206", "Victory Road", "Rock Peak Ruins"]
    assert [_names(t) for t in db["locations"]["Victory Road"]] == [["Starly"]]


def test_encounters_rates_follow_the_level():
    """Morning, day and night, or a single rate. A gift's '-' is no rate"""
    db = _parse_encounters([
        ["ROUTE 206"],
        ["Grass (20-22)", "", "", "M", "D", "N"],
        ["", "#396 Starly", "21-21", "30", "20", "0"],
        ["Surf (20-40)"],
        ["", "#399 Bidoof", "20-40", "90"],
        ["Static Encounter"],
        ["", "#377 Regirock", "60", "-"],
    ])
    assert [t["mons"][0] for t in db["locations"]["Route 206"]] == [
        {"name": "Starly", "level": "21-21", "rates": [30, 20, 0]},
        {"name": "Bidoof", "level": "20-40", "rates": [90]},
        {"name": "Regirock", "level": "60"},
    ]


def test_encounters_rods_split_into_one_table_per_rod():
    """Each rod gets its own table with what it can hook, its level in the method"""
    db = _parse_encounters([
        ["ROUTE 206"],
        ["Rods (O-10, G-25, S-50)", "", "", "O", "G", "S"],
        ["", "#363 Spheal", "", "60", "40", "0"],
        ["", "#399 Bidoof", "", "40", "60", "100"],
    ])
    assert [(t["method"], t["mons"]) for t in db["locations"]["Route 206"]] == [
        ("Old Rod (10)", [{"name": "Spheal", "level": "", "rates": [60]},
                          {"name": "Bidoof", "level": "", "rates": [40]}]),
        ("Good Rod (25)", [{"name": "Spheal", "level": "", "rates": [40]},
                           {"name": "Bidoof", "level": "", "rates": [60]}]),
        ("Super Rod (50)", [{"name": "Bidoof", "level": "", "rates": [100]}]),
    ]


def test_encounters_a_repeat_with_more_rates_replaces_them():
    """Route 218: an Old Rod preview early on, then the full Rods table of the same location"""
    db = _parse_encounters(
        [["ROUTE 206"], ["Rods (O-10, G-25, S-50)", "", "", "O"], ["", "#363 Spheal", "", "100"]],
        [["ROUTE 206"], ["Rods (O-10, G-25, S-50)", "", "", "O", "G", "S"],
         ["", "#363 Spheal", "", "100", "100", "100"]],
    )
    assert [(t["method"], t["mons"][0]["rates"]) for t in db["locations"]["Route 206"]] == [
        ("Old Rod (10)", [100]), ("Good Rod (25)", [100]), ("Super Rod (50)", [100]),
    ]


@pytest.mark.parametrize("group", [
    [["ROUTE 206"], ["Something new"], ["", "#396 Starly", "21-21"]],   # text it doesn't know
    [["ROUTE 206"], ["Grass (20-22)"], ["", "#999 Missingno", "21-21"]],  # species not in PkDB
    [["ROUTE 206"], ["Rods (O-10, G-25, S-50)", "", "", "O", "G", "S"],  # rates that fit no rod
     ["", "#363 Spheal", "", "100"]],
])
def test_encounters_import_fails_on_what_it_does_not_know(group):
    """A layout change in the sheet stops the import instead of writing bad data"""
    with pytest.raises(ValueError):
        _parse_encounters(group)


def test_encounters_import_needs_the_master_table():
    """No end marker means the layout changed"""
    with pytest.raises(ValueError):
        parse_encounters("a,b\n1,2\n", ENCOUNTER_SPECIES)


def test_encounters_db_text_round_trips():
    """The custom file format is plain JSON, ASCII for the platform-encoding loader"""
    db = {
        "starters": ["Turtwig"],
        "locations": {"Pokémon League": [
            {"area": "", "method": "Poké Radar", "mons": [{"name": "Starly", "level": "4-5"}]},
        ]},
        "evolution_lines": [["Starly", "Staravia"], ["Bidoof"]],
        "evolutions": {"Starly": [{"name": "Staravia", "how": "Lv. 14"}]},
    }
    text = db_text(db)
    assert json.loads(text) == db and text.isascii()


def _stats_csv(*species) -> str:
    """The STATS tab's CSV: a title row, then (name, evolution cell) per species"""
    rows = [[""] * (STATS_EVOLUTION_COL + 1) for _ in range(len(species) + 1)]
    rows[0][STATS_EVOLUTION_COL] = STATS_EVOLUTION_TITLE
    for row, (name, cell) in zip(rows[1:], species):
        row[1], row[STATS_EVOLUTION_COL] = name, cell
    out = io.StringIO()
    csv.writer(out).writerows(rows)
    return out.getvalue()


def test_evolution_lines_follow_the_links_in_both_directions():
    """Either side of a link joins the line, and a species with no links is a line of its own"""
    stats = _stats_csv(
        ("#396 Starly", "Can evolve into #397"),
        ("#397 Staravia", "#396 Lv. 14 - Can evolve into #398"),
        ("#398 Staraptor", "#397 Lv. 34"),
        ("#399 Bidoof", "-"),
    )
    assert parse_evolution_lines(stats, {"Starly", "Staravia", "Staraptor", "Bidoof"}) == [
        ["Starly", "Staravia", "Staraptor"], ["Bidoof"],
    ]


def test_evolution_lines_put_forms_with_their_species():
    """Forms share a dex number, so all of them join the line"""
    stats = _stats_csv(
        ("#412 Burmy", "Can evolve into #413, #414"),
        ("#413 Wormadam (Plant)", "#412 Female Lv. 20"),
        ("#413 Wormadam (Sandy)", "#412 Female Lv. 20"),
        ("#414 Mothim", "#412 Male Lv. 20"),
    )
    assert parse_evolution_lines(stats, {"Burmy", "Wormadam", "Wormadam_sandy", "Mothim"}) == [
        ["Burmy", "Wormadam", "Wormadam_sandy", "Mothim"],
    ]


def test_evolution_lines_correct_the_sheets_hoppip_typo():
    """The sheet's Skiploom comes 'from #186' (Politoed): it stays out of Poliwag's line"""
    stats = _stats_csv(
        ("#186 Politoed", "#061 Use King's Rock (!)"),
        ("#061 Poliwhirl", "Can evolve into #186"),
        ("#187 Hoppip", "Can evolve into #187"),
        ("#188 Skiploom", "#186 Lv. 18 - Can evolve into #188"),
        ("#189 Jumpluff", "#187 Lv. 27"),
    )
    known = {"Politoed", "Poliwhirl", "Hoppip", "Skiploom", "Jumpluff"}
    assert parse_evolution_lines(stats, known) == [
        ["Politoed", "Poliwhirl"], ["Hoppip", "Skiploom", "Jumpluff"],
    ]


def test_evolutions_say_what_and_how():
    """Each target with its own cell minus the dex it comes from. Forms are all targets, the Hoppip typo
    is fixed, and a species that doesn't evolve isn't listed"""
    stats = _stats_csv(
        ("#396 Starly", "Can evolve into #397"),
        ("#397 Staravia", "#396 Lv. 14 - Can evolve into #398"),
        ("#398 Staraptor", "#397 Lv. 34"),
        ("#412 Burmy", "Can evolve into #413, #414"),
        ("#413 Wormadam (Plant)", "#412 Female Plant Cloak Lv. 20"),
        ("#413 Wormadam (Sandy)", "#412 Female Sand Cloak Lv. 20"),
        ("#414 Mothim", "#412 Male Lv. 20"),
        ("#187 Hoppip", "Can evolve into #187"),
        ("#188 Skiploom", "#186 Lv. 18 - Can evolve into #188"),
        ("#189 Jumpluff", "#187 Lv. 27"),
        ("#479 Rotom", "N"),
    )
    assert parse_evolutions(stats) == {
        "Starly": [{"name": "Staravia", "how": "Lv. 14"}],
        "Staravia": [{"name": "Staraptor", "how": "Lv. 34"}],
        "Burmy": [
            {"name": "Wormadam", "how": "Female Plant Cloak Lv. 20"},
            {"name": "Wormadam_sandy", "how": "Female Sand Cloak Lv. 20"},
            {"name": "Mothim", "how": "Male Lv. 20"},
        ],
        "Hoppip": [{"name": "Skiploom", "how": "Lv. 18"}],
        "Skiploom": [{"name": "Jumpluff", "how": "Lv. 27"}],
    }


@pytest.mark.parametrize("stats, known", [
    (_stats_csv(("#396 Starly", "-")), {"Starly", "Staravia"}),  # a PkDB species has no row
    (_stats_csv(("#396 Starly", "-")), set()),                   # a row isn't in PkDB
    ("a,b\n1,2\n", {"Starly"}),                                  # the column moved
])
def test_evolution_lines_fail_on_what_they_do_not_know(stats, known):
    """A layout change in the sheet stops the import instead of writing bad data"""
    with pytest.raises(ValueError):
        parse_evolution_lines(stats, known)


ENCOUNTER_DB = _load_json("DataBase", "EncounterDB.json")


def test_encounter_db_species_exist():
    """Every Pokemon in EncounterDB.json is in PkDB"""
    entries = [
        (f"{location}/{table['method']}", mon["name"])
        for location, tables in ENCOUNTER_DB["locations"].items()
        for table in tables
        for mon in table["mons"]
    ]
    assert not [entry for entry in entries if entry[1] not in pkDB]
    assert not [name for name in ENCOUNTER_DB["starters"] if name not in pkDB]


def test_encounter_db_has_every_species_in_one_evolution_line():
    """The species clause can place every species. 247 lines is what the sheet and Showdown both give"""
    lines = ENCOUNTER_DB["evolution_lines"]
    species = [name for line in lines for name in line]
    assert len(lines) == 247
    assert len(species) == len(set(species)) and set(species) == set(pkDB)


@pytest.mark.parametrize("member, line", [
    ("Eevee", {"Eevee", "Vaporeon", "Jolteon", "Flareon", "Espeon", "Umbreon", "Leafeon", "Glaceon"}),
    ("Wurmple", {"Wurmple", "Silcoon", "Beautifly", "Cascoon", "Dustox"}),  # branches
    ("Tyrogue", {"Tyrogue", "Hitmonlee", "Hitmonchan", "Hitmontop"}),
    ("Pikachu", {"Pichu", "Pikachu", "Raichu"}),                            # a baby
    ("Poliwag", {"Poliwag", "Poliwhirl", "Poliwrath", "Politoed"}),         # the sheet's typo
    ("Skiploom", {"Hoppip", "Skiploom", "Jumpluff"}),
    ("Wormadam_trash", {"Burmy", "Wormadam", "Wormadam_sandy", "Wormadam_trash", "Mothim"}),  # forms
    ("Rotom_mow", {"Rotom", "Rotom_heat", "Rotom_wash", "Rotom_frost", "Rotom_fan", "Rotom_mow"}),
    ("Manaphy", {"Manaphy"}),                                               # no evolution to Phione
    ("Phione", {"Phione"}),
    ("Nidoran_f", {"Nidoran_f", "Nidorina", "Nidoqueen"}),                  # the two are separate
    ("Nidoran_m", {"Nidoran_m", "Nidorino", "Nidoking"}),
])
def test_encounter_db_evolution_lines(member, line):
    """Branches, babies, forms and the near misses land in the right line"""
    assert set(next(l for l in ENCOUNTER_DB["evolution_lines"] if member in l)) == line


def test_encounter_db_tables_have_pokemon():
    """No empty tables or locations"""
    locations = ENCOUNTER_DB["locations"]
    assert all(locations.values())
    assert not [(name, t["method"]) for name, tables in locations.items() for t in tables if not t["mons"]]


def test_encounter_db_rates_fit_their_table():
    """A table's Pokemon all have the same number of rates: morning/day/night for grass, caves and the
    ground, one per Pokemon on a rod, none for a gift. No Rods table is left unsplit"""
    bad = []
    for name, tables in ENCOUNTER_DB["locations"].items():
        for t in tables:
            counts = {len(mon.get("rates", [])) for mon in t["mons"]}
            time_of_day = t["method"].startswith(("Grass", "Cave", "Ground", "Lost Tower"))
            rod = t["method"].endswith((" Rod (10)", " Rod (25)", " Rod (50)"))
            if len(counts) > 1 or (time_of_day and counts != {3}) or (rod and counts != {1}):
                bad.append((name, t["area"], t["method"], counts))
            if t["method"].startswith("Rods"):
                bad.append((name, t["area"], t["method"], "not split"))
    assert not bad


def test_encounter_db_evolutions_stay_in_the_line():
    """Every evolution is to a PkDB species of the same line, and says how"""
    line_of = {name: i for i, line in enumerate(ENCOUNTER_DB["evolution_lines"]) for name in line}
    bad = [
        (name, target["name"])
        for name, targets in ENCOUNTER_DB["evolutions"].items()
        for target in targets
        if target["name"] not in pkDB or line_of[target["name"]] != line_of[name] or not target["how"]
    ]
    assert not bad
    assert [t["name"] for t in ENCOUNTER_DB["evolutions"]["Kirlia"]] == ["Gardevoir", "Gallade"]
    assert len(ENCOUNTER_DB["evolutions"]["Eevee"]) == 7 and "Venusaur" not in ENCOUNTER_DB["evolutions"]


def test_encounter_db_is_by_met_location():
    """Locations are [pp]'s met locations, not the sheet's blocks or section titles"""
    locations = ENCOUNTER_DB["locations"]
    for not_a_location in ("Route 204 (South)", "Lost Tower", "Areas 1 and 2", "Area 1 And 2",
                           "Changing Pokemon", "Post Game", "Bicycle Shop", "Mt Coronet",
                           "Trainer School", "Galactic Building", "Hall Of Origin"):
        assert not_a_location not in locations
    assert {t["area"] for t in locations["Route 204"]} == {"South", "North"}
    assert {"East", "West"} <= {t["area"] for t in locations["Route 211"]}
    assert {"North", "South"} <= {t["area"] for t in locations["Route 210"]}
    assert any("Lost Tower" in t["method"] for t in locations["Route 209"])
    assert "Great Marsh" in locations and "Trainers' School" in locations


def test_encounter_db_starters_are_separate_from_route_201():
    """The starter doesn't use Route 201's encounter, and its gift table moved out"""
    assert ENCOUNTER_DB["starters"] == ["Turtwig", "Chimchar", "Piplup"]
    route_201 = {mon["name"] for t in ENCOUNTER_DB["locations"]["Route 201"] for mon in t["mons"]}
    assert not route_201 & set(ENCOUNTER_DB["starters"])


@pytest.mark.parametrize("species, location, wrong", [
    ("Moltres", "Victory Road", "Route 223"),   # its block is two groups wide, under Route 223's
    ("Heatran", "Stark Mountain", None),        # its method line is in the group on the left
    ("Arceus", "Hall of Origin", "Stark Mountain"),
    ("Manaphy", "Pokémon Mansion", None),
    ("Giratina", "Distortion World", None),     # one column over in the sheet
])
def test_encounter_db_layout_traps(species, location, wrong):
    """Pokemon the grid's layout doesn't put under their heading landed in the right location"""
    def has(name):
        return any(m["name"] == species for t in ENCOUNTER_DB["locations"][name] for m in t["mons"])
    assert has(location)
    assert wrong is None or not has(wrong)


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


# ─── Item locations (DataBase/import_items.py) ────────────────────────────────

# Every location PLACED_AFTER needs, plus a gift and a trade for the items they hold
ITEM_ENCOUNTERS = {
    "Jubilife City": [{"area": "", "method": "Gift from the Interviewer", "mons": [{"name": "Bulbasaur"}]}],
    "Oreburgh City": [{"area": "", "method": "Trade with a Schoolgirl", "mons": [{"name": "Spheal"}]}],
    **{name: [] for name in (
        "Route 208", "Route 209", "Route 210", "Route 215", "Acuity Lakefront", "Lake Acuity",
        "Flower Paradise", "Veilstone City",
    )},
}


def _parse_items(monkeypatch, items=(), tms=(), keys=(), kept=None) -> dict:
    """The iTEMS/TMs tab's CSV with one table of each: items (name, places) in columns 1-3, TMs (name,
    type, place, how) in 5-11, key items (name, place, how, mark) in 16-20, and like the sheet a plate under
    its heading in 13-15. KEY_ITEMS is `kept`, the key items given by default"""
    monkeypatch.setattr(import_items, "ITEM_TABLES", 1)
    monkeypatch.setattr(import_items, "TM_TABLES", 1)
    monkeypatch.setattr(import_items, "TM_COUNT", len(tms))
    monkeypatch.setattr(import_items, "KEY_ITEMS", tuple(key[0] for key in keys) if kept is None else kept)
    rows = [[""] * 21 for _ in range(max(len(items), len(tms), len(keys), 2) + 3)]
    rows[1][16], rows[1][18] = "Item", "Location"
    for r, cells in enumerate(keys, start=2):
        rows[r][17:17 + len(cells)] = cells
    rows[1][1], rows[1][3] = "Item", "Locations"
    rows[1][5], rows[1][6] = "TM                      ", "Type"
    rows[1][13] = "PLATE LOCATIONS"
    rows[2][13], rows[2][15] = "Item", "Master Trainer Location"
    rows[3][14], rows[3][15] = "Mind Plate", "Route 209 - Entrance"
    for r, (name, places) in enumerate(items, start=2):
        rows[r][2], rows[r][3] = name, places
    for r, (name, move_type, place, how) in enumerate(tms, start=2):
        rows[r][5:12] = [name, move_type, "", "", "", place, how]
    out = io.StringIO()
    csv.writer(out).writerows(rows)
    return import_items.parse_items(out.getvalue(), ITEM_ENCOUNTERS)["locations"]


def _seen(entries: list) -> list:
    return [(e["item"], e["area"], e["how"]) for e in entries]


def test_items_one_pickup_per_place_with_its_area_and_notes(monkeypatch):
    """A comma list is one pickup per place, parentheses are an area or how it's found"""
    db = _parse_items(monkeypatch, items=[
        ("Shiny Stone", "Route 210 (North) (Hidden), Veilstone Dept. Store (Buyable)"),
        ("Leftovers", "Veilstone Game Corner Prize (Buyable), Route 209"),
    ])
    assert _seen(db["Route 210"]) == [("Shiny Stone", "North", "Hidden")]
    assert _seen(db["Veilstone City"]) == [
        ("Shiny Stone", "Dept. Store", "Buyable"), ("Leftovers", "Game Corner", "Prize · Buyable"),
    ]
    assert _seen(db["Route 209"]) == [("Leftovers", "", "")]


def test_items_held_by_a_gift_or_a_trade_are_where_it_is_given(monkeypatch):
    """EncounterDB says where the gift and the traded Pokemon are, so the item is picked up there"""
    db = _parse_items(monkeypatch, items=[
        ("Miracle Seed", "Route 209, attached to Bulbasaur gifts"),
        ("NeverMeltIce", "Trade for Spheal in Oreburgh"),
    ])
    assert _seen(db["Jubilife City"]) == [("Miracle Seed", "", "Held by the gift Bulbasaur")]
    assert _seen(db["Route 209"]) == [("Miracle Seed", "", "")]
    assert _seen(db["Oreburgh City"]) == [("Never-Melt Ice", "", "Held by the traded Spheal")]  # ItemDB's


def test_items_tms_and_no_plates(monkeypatch):
    """A TM keeps its move and type, a gym is its city's. The plate table is left out (after the Champion)"""
    db = _parse_items(
        monkeypatch,
        tms=[("TM76 Stealth Rock ", "Rock", "Oreburgh Gym", "Gift from Roark"),
             ("HM06 Rock Smash", "Fighting", "Route 209 ", "Gift from NPC")],
    )
    assert db["Oreburgh City"] == [{
        "id": "Oreburgh City|Gym|TM76|Gift from Roark", "item": "TM76", "kind": "tm", "area": "Gym",
        "how": "Gift from Roark", "move": "Stealth Rock", "type": "Rock",
    }]
    assert [(e["item"], e["kind"], e["area"]) for e in db["Route 209"]] == [("HM06", "tm", "")]


def test_items_key_items_are_only_the_ones_kept(monkeypatch):
    """A kept key item is read with how it's given, past the sheet's * mark; any other is left out"""
    keys = [("Good Rod", "Route 209", "*", "Gift from NPC"), ("Town Map", "Route 209", "Gift from rival")]
    db = _parse_items(monkeypatch, keys=keys, kept=("Good Rod",))
    assert db == {"Route 209": [{
        "id": "Route 209||Good Rod|Gift from NPC", "item": "Good Rod", "kind": "key", "area": "",
        "how": "Gift from NPC",
    }]}
    with pytest.raises(ValueError):  # a kept one the sheet doesn't have
        _parse_items(monkeypatch, keys=keys, kept=("Good Rod", "Super Rod"))


def test_items_follow_the_story_order(monkeypatch):
    """Locations in EncounterDB's order with PLACED_AFTER's put in (Veilstone City moves up from the end);
    at a location items, then key items, then TMs"""
    db = _parse_items(
        monkeypatch,
        items=[("Choice Band", "Veilstone City"), ("Magnet", "Route 209"), ("Up-Grade", "Hearthome City"),
               ("Big Root", "Route 210")],
        tms=[("TM01 Focus Punch", "Fighting", "Route 209", "Item on ground")],
        keys=[("Good Rod", "Route 209", "Gift from NPC")],
    )
    assert list(db) == ["Hearthome City", "Route 209", "Route 210", "Veilstone City"]
    assert [e["kind"] for e in db["Route 209"]] == ["item", "key", "tm"]


@pytest.mark.parametrize("items, tms", [
    ([("Magnet", "Somewhere New")], []),                          # a place it doesn't know
    ([("Magnet", "Route 209 (Something new)")], []),              # a note it doesn't know
    ([("Magnet", "")], []),                                       # an item with no places
    ([("Magnet", "Trade for Spheal in Jubilife")], []),           # the trade is somewhere else
    ([("Magnet", "Route 209, attached to Squirtle gifts")], []),  # a gift EncounterDB doesn't have
    ([], [("TM99 Something", "Sound", "Route 209", "Item on ground")]),  # not a type
    ([("Magnet", "Route 209"), ("Magnet", "Route 209")], []),     # the same pickup twice
])
def test_items_import_fails_on_what_it_does_not_know(monkeypatch, items, tms):
    """A layout change in the sheet stops the import instead of writing bad data"""
    with pytest.raises(ValueError):
        _parse_items(monkeypatch, items=items, tms=tms)


def test_items_import_needs_its_tables():
    """No header cells means the layout changed"""
    with pytest.raises(ValueError):
        import_items.parse_items("a,b\n1,2\n", ITEM_ENCOUNTERS)


def test_items_db_text_round_trips():
    """The custom file format is plain JSON, ASCII for the platform-encoding loader"""
    db = {"locations": {"Pokémon Mansion": [
        {"id": "Pokémon Mansion||Lucky Egg|", "item": "Lucky Egg", "kind": "item", "area": "", "how": ""},
    ]}}
    text = import_items.db_text(db)
    assert json.loads(text) == db and text.isascii()


ITEM_LOCATION_DB = _load_json("DataBase", "ItemLocationDB.json")
PICKUPS = [(name, e) for name, entries in ITEM_LOCATION_DB["locations"].items() for e in entries]


def test_item_location_db_is_in_the_trackers_story_order():
    """Every location is a Tracker location or a placed one, in location_order's order"""
    order = import_items.location_order(ENCOUNTER_DB["locations"])
    names = list(ITEM_LOCATION_DB["locations"])
    assert names == [name for name in order if name in names]


def test_item_location_db_counts_and_ids():
    """Every TM and HM, no plates, and one id per pickup for the run to keep"""
    kinds = [e["kind"] for _, e in PICKUPS]
    assert kinds.count("tm") == 100 and set(kinds) == {"item", "key", "tm"}
    # What the Pokémon tab's locks need (nuzlocke.ts METHOD_NEEDS): the rods and HM03 Surf, once each
    assert sorted(e["item"] for _, e in PICKUPS if e["kind"] == "key") == ["Good Rod", "Old Rod", "Super Rod"]
    assert [e["move"] for _, e in PICKUPS if e["item"] == "HM03"] == ["Surf"]
    ids = [e["id"] for _, e in PICKUPS]
    assert len(ids) == len(set(ids))
    assert not [e["id"] for name, e in PICKUPS if e["id"] != "|".join((name, e["area"], e["item"], e["how"]))]


def test_item_location_db_spells_hold_items_like_itemdb():
    """A hold item ItemDB has is spelled ItemDB's way, so the two can be matched by name"""
    def key(name):
        return "".join(ch for ch in name.lower() if ch.isalnum())
    spelling = {key(name): name for name in itemDB}
    assert not [e["item"] for _, e in PICKUPS if spelling.get(key(e["item"]), e["item"]) != e["item"]]


def test_item_location_db_gift_items_follow_the_gifts():
    """Miracle Seed comes with Bulbasaur in Jubilife, Treecko in Oreburgh and Chikorita in Floaroma"""
    held = [name for name, e in PICKUPS if e["item"] == "Miracle Seed" and e["how"].startswith("Held")]
    assert sorted(held) == ["Floaroma Town", "Jubilife City", "Oreburgh City"]
