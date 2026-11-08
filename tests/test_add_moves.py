"""The MoveDB entry helper (DataBase/add_moves.py): the Showdown parser, the mapping, the MOVES tab, the
inserts. Offline: the Showdown text below is copied from [SD] data/moves.ts and its gen6 / gen5 mods"""
import json

import pytest

from DataBase import add_moves as am
from DataBase.loader import moveDB

BASE = """// a comment { with a brace
export const Moves: import('../sim/dex-moves').MoveDataTable = {
	acid: {
		num: 51,
		accuracy: 100,
		basePower: 40,
		category: "Special",
		name: "Acid",
		pp: 30,
		priority: 0,
		flags: { protect: 1, mirror: 1, metronome: 1 },
		secondary: {
			chance: 10,
			boosts: {
				spd: -1,
			},
		},
		target: "allAdjacentFoes",
		type: "Poison",
		contestType: "Clever",
	},
	batonpass: {
		num: 226,
		accuracy: true,
		basePower: 0,
		category: "Status",
		name: "Baton Pass",
		pp: 40,
		priority: 0,
		flags: { metronome: 1 },
		onHit(target) {
			if (!this.canSwitch(target.side) || target.volatiles['commanded']) {
				this.attrLastMove('[still]');
				this.add('-fail', target);
				return this.NOT_FAIL;
			}
		},
		self: {
			onHit(source) {
				source.skipPursuit = true;
			},
		},
		selfSwitch: 'copyvolatile',
		target: "self",
		type: "Normal",
		zMove: { effect: 'clearnegativeboost' },
		contestType: "Cute",
	},
	bounce: {
		num: 340,
		accuracy: 85,
		basePower: 85,
		category: "Physical",
		name: "Bounce",
		pp: 5,
		priority: 0,
		flags: {
			contact: 1, charge: 1, protect: 1, mirror: 1, gravity: 1, distance: 1,
			metronome: 1, nosleeptalk: 1, noassist: 1, failinstruct: 1,
		},
		onTryMove(attacker, defender, move) {
			if (attacker.removeVolatile(move.id)) {
				return;
			}
			this.add('-prepare', attacker, move.name);
			attacker.addVolatile('twoturnmove', defender);
			return null;
		},
		condition: {
			duration: 2,
			onInvulnerability(target, source, move) {
				if (['gust', 'twister', 'skyuppercut', 'thunder', 'hurricane', 'smackdown'].includes(move.id)) {
					return;
				}
				return false;
			},
		},
		secondary: {
			chance: 30,
			status: 'par',
		},
		target: "any",
		type: "Flying",
		contestType: "Cute",
	},
	closecombat: {
		num: 370,
		accuracy: 100,
		basePower: 120,
		category: "Physical",
		name: "Close Combat",
		pp: 5,
		priority: 0,
		flags: { contact: 1, protect: 1, mirror: 1, metronome: 1 },
		self: {
			boosts: {
				def: -1,
				spd: -1,
			},
		},
		target: "normal",
		type: "Fighting",
		contestType: "Tough",
	},
	firefang: {
		num: 424,
		accuracy: 95,
		basePower: 65,
		category: "Physical",
		name: "Fire Fang",
		pp: 15,
		priority: 0,
		flags: { contact: 1, protect: 1, mirror: 1, metronome: 1, bite: 1 },
		secondaries: [
			{
				chance: 10,
				status: 'brn',
			}, {
				chance: 10,
				volatileStatus: 'flinch',
			},
		],
		target: "normal",
		type: "Fire",
		contestType: "Cool",
	},
	metalclaw: {
		num: 232,
		accuracy: 95,
		basePower: 50,
		category: "Physical",
		name: "Metal Claw",
		pp: 35,
		priority: 0,
		flags: { contact: 1, protect: 1, mirror: 1, metronome: 1 },
		secondary: {
			chance: 10,
			self: {
				boosts: {
					atk: 1,
				},
			},
		},
		target: "normal",
		type: "Steel",
		contestType: "Cool",
	},
	thunderwave: {
		num: 86,
		accuracy: 90,
		basePower: 0,
		category: "Status",
		name: "Thunder Wave",
		pp: 20,
		priority: 0,
		flags: { protect: 1, reflectable: 1, mirror: 1, metronome: 1 },
		status: 'par',
		ignoreImmunity: false,
		target: "normal",
		type: "Electric",
		zMove: { boost: { spd: 1 } },
		contestType: "Cool",
	},
};
"""
GEN6 = """export const Moves: import('../../../sim/dex-moves').ModdedMoveDataTable = {
	thunderwave: {
		inherit: true,
		accuracy: 100,
	},
};
"""
GEN5 = """export const Moves: import('../../../sim/dex-moves').ModdedMoveDataTable = {
	bounce: {
		inherit: true,
		flags: {
			contact: 1, charge: 1, protect: 1, mirror: 1, gravity: 1, distance: 1, metronome: 1, nosleeptalk: 1,
		},
	},
};
"""
# The MOVES tab's rows for them, as parse_moves_tab keeps them (0-based columns)
ROWS = {
    "acid": {1: "Acid", 3: "POISON", 6: "SPECIAL", 8: "40.0", 9: "1.0", 10: "30PP"},
    "batonpass": {1: "Baton Pass", 3: "NORMAL", 6: "STATUS", 8: "--", 9: "--", 10: "40PP"},
    "bounce": {1: "Bounce", 3: "FLYING", 6: "PHYSICAL", 8: "85.0", 9: "0.85", 10: "5PP"},
    "closecombat": {1: "Close Combat", 3: "FIGHTING", 6: "PHYSICAL", 8: "120.0", 9: "1.0", 10: "5PP"},
    "firefang": {1: "Fire Fang", 3: "FIRE", 6: "PHYSICAL", 8: "65.0", 9: "0.95", 10: "15PP"},
    "metalclaw": {1: "Metal Claw", 3: "STEEL", 6: "PHYSICAL", 8: "50.0", 9: "0.95", 10: "35PP"},
    "thunderwave": {1: "Thunder Wave", 3: "ELECTRIC", 6: "STATUS", 8: "--", 9: "90%", 10: "20PP"},
}


def _showdown():
    return am.merge_layers([am.parse_moves_ts(text) for text in (BASE, GEN6, GEN5)])


def test_parse_moves_ts():
    """Plain data comes through; handlers, methods and expressions become FUNCTION; a comment or string with a
    brace doesn't break it"""
    moves = am.parse_moves_ts(BASE)
    assert list(moves) == list(ROWS)
    assert moves["acid"]["secondary"] == {"chance": 10, "boosts": {"spd": -1}}
    assert moves["bounce"]["onTryMove"] == am.FUNCTION
    assert moves["bounce"]["condition"] == {"duration": 2, "onInvulnerability": am.FUNCTION}
    assert moves["batonpass"]["self"] == {"onHit": am.FUNCTION} and moves["batonpass"]["accuracy"] is True
    expression = am.parse_moves_ts("x = {\n\tfoo: {\n\t\tbasePower: a + 1,\n\t},\n};")
    assert expression["foo"] == {"basePower": am.FUNCTION}
    with pytest.raises(ValueError):  # the parser and the file's "\tid: {" lines disagree
        am.parse_moves_ts("x = {\n\tfoo: {\n\t},\n\tbar: 1,\n};")


def test_merge_layers():
    """Base first, then each mod: inherit: true overrides only the fields it lists"""
    moves = _showdown()
    assert moves["thunderwave"]["accuracy"] == 100 and moves["thunderwave"]["status"] == "par"
    assert "noassist" not in moves["bounce"]["flags"] and moves["bounce"]["secondary"]["status"] == "par"
    replaced = am.merge_layers([{"a": {"x": 1, "y": 2}}, {"a": {"x": 3}}])
    assert replaced == {"a": {"x": 3}}  # no inherit: the mod's move replaces it


def test_build_entry_rebuilds_movedb():
    """The [SD] data plus the tab's numbers gives the current MoveDB entries exactly"""
    moves = _showdown()
    for k, row in ROWS.items():
        if row[1] in moveDB:
            entry, _ = am.build_entry(row[1], moves[k], row)
            assert entry == moveDB[row[1]], row[1]
    entry, _ = am.build_entry("Thunder Wave", moves["thunderwave"], ROWS["thunderwave"])
    assert entry["accuracy"] == 90  # the tab wins over gen6's 100


def test_build_entry_notes():
    """What MoveDB can't hold is left out and listed"""
    moves = _showdown()
    entry, notes = am.build_entry("Close Combat", moves["closecombat"], ROWS["closecombat"])
    assert "self" not in entry and notes == ['self: {"boosts": {"def": -1, "spd": -1}}']
    entry, notes = am.build_entry("Bounce", moves["bounce"], ROWS["bounce"])
    assert entry["charge"] == 1 and notes == ["engine work: condition, onTryMove"]
    entry, notes = am.build_entry("Bounce", moves["bounce"], None)
    assert notes[0].startswith("not on the MOVES tab") and (entry["power"], entry["pp"]) == (85, 5)
    _, notes = am.build_entry("X", {**moves["acid"], "volatileStatus": "substitute"}, ROWS["acid"])
    assert notes == ["volatileStatus: substitute (no VolStatus member)"]


def test_sheet_numbers():
    """The tab's spellings: -- is always-hit or [SD]'s power, % or a fraction, - type is [SD]'s, OTHER is
    Status"""
    sd = {"type": "Normal", "basePower": 60}
    row = {3: "-", 6: "OTHER", 8: "--", 9: "--", 10: "15PP"}
    assert am.sheet_numbers(row, sd) == {
        "type": "Normal", "category": "Status", "power": 60, "accuracy": True, "pp": 15,
    }
    row = {3: "FAIRY", 6: "SPECIAL", 8: "95", 9: "0.85", 10: "10PP"}
    assert am.sheet_numbers(row, sd) == {
        "type": "Fairy", "category": "Special", "power": 95, "accuracy": 85, "pp": 10,
    }
    assert am.sheet_numbers({**row, 9: "30%"}, sd)["accuracy"] == 30


def test_parse_moves_tab():
    """The move list under NAME, the MOVE MODIFICATIONS lines above it, and the old -> new moves"""
    cells = {
        (11, 9): "Poison Fang // Power: 50 >> 65", (12, 9): "Strength: // Power: 80 >> 100",
        (16, 1): "Old Move", (16, 3): "New Move", (17, 1): "Barrage        ", (17, 3): "Draining Kiss",
        (30, 1): "NAME", (30, 3): "TYPE", (30, 10): "PP",
        (32, 1): "Poison Fang", (32, 3): "POISON", (32, 6): "PHYSICAL", (32, 8): "65", (32, 9): "95%᠎",
        (32, 10): "15PP᠋",
    }
    moves, modifications, replaced = am.parse_moves_tab(cells)
    assert moves == {
        "poisonfang": {1: "Poison Fang", 3: "POISON", 6: "PHYSICAL", 8: "65", 9: "95%", 10: "15PP"},
    }
    assert set(modifications) == {"poisonfang", "strength"} and replaced == {"barrage": "Draining Kiss"}


def test_resolve():
    """The key is TrainerDB's spelling, else the tab's; an old move is refused; Vice Grip is [SD]'s Vise
    Grip"""
    moves = {**_showdown(), "visegrip": {"name": "Vise Grip"}}
    tab = ({"acid": ROWS["acid"]}, {"acid": "Acid // PP: 30"}, {"barrage": "Draining Kiss"})
    assert am.resolve("ACID", moves, tab, {})[::2] == ("Acid", ROWS["acid"])
    assert am.resolve("acid", moves, tab, {"acid": "AcId"})[0] == "AcId"
    assert am.resolve("acid", moves, tab, {})[3] == "Acid // PP: 30"
    assert am.resolve("Vice Grip", moves, tab, {})[:3] == ("Vise Grip", moves["visegrip"], None)
    for name in ("Barrage", "Not A Move"):
        with pytest.raises(ValueError):
            am.resolve(name, moves, tab, {})


JSON_TEXT = '{\r\n  "Bite": {\r\n    "pp": 25\r\n  },\r\n  "Night Shade": {\r\n    "pp": 15\r\n  }\r\n}\r\n'


def test_insert_json():
    """Before the first move that sorts after it, in the file's format and line endings; nothing else moves"""
    entry = {"pp": 10, "multi_hit": [2, 5], "flags": {"protect": True, "contact": True}}
    text = am.insert_json(JSON_TEXT, "Crunch", entry)
    crunch = ('  "Crunch": {\r\n    "flags": {\r\n      "contact": true,\r\n      "protect": true\r\n    },'
              '\r\n    "multi_hit": [2, 5],\r\n    "pp": 10\r\n  },\r\n')
    assert text == JSON_TEXT.replace('  "Night Shade"', crunch + '  "Night Shade"')
    first = am.insert_json(JSON_TEXT, "Absorb", {"pp": 1})
    assert list(json.loads(first)) == ["Absorb", "Bite", "Night Shade"]
    last = am.insert_json(JSON_TEXT, "Zap Cannon", {"pp": 5})
    assert list(json.loads(last)) == ["Bite", "Night Shade", "Zap Cannon"] and last.endswith("}\r\n")
    assert list(json.loads(am.insert_json(JSON_TEXT, "Night Slash", {"pp": 1})))[1] == "Night Shade"
    with pytest.raises(ValueError):
        am.insert_json(JSON_TEXT, "Bite", {})


PY_TEXT = ("class MoveName:\r\n    BITE            = 1\r\n    NIGHT_SHADE     = BITE + 1\r\n"
           "    ZEN_HEADBUTT    = NIGHT_SHADE + 1\r\n\r\n\r\nMoveIdToName = {}\r\n")
NAMES = {"BITE": "Bite", "NIGHT_SHADE": "Night Shade", "ZEN_HEADBUTT": "Zen Headbutt"}


def test_insert_move_name():
    """CONST = PREV + 1 at its place in the chain, and the next one points at it"""
    text = am.insert_move_name(PY_TEXT, "CRUNCH", "Crunch", NAMES)
    assert text == PY_TEXT.replace("    NIGHT_SHADE     = BITE + 1",
                                   "    CRUNCH          = BITE + 1\r\n    NIGHT_SHADE     = CRUNCH + 1")
    first = am.insert_move_name(PY_TEXT, "ABSORB", "Absorb", NAMES)
    assert "    ABSORB          = 1\r\n    BITE            = ABSORB + 1\r\n" in first
    last = am.insert_move_name(PY_TEXT, "ZZZ", "Zzz", NAMES)
    assert "= NIGHT_SHADE + 1\r\n    ZZZ             = ZEN_HEADBUTT + 1\r\n\r\n" in last
    long_name = am.insert_move_name(PY_TEXT, "DISARMING_VOICE_X", "Disarming Voice X", NAMES)
    assert "    DISARMING_VOICE_X = BITE + 1\r\n" in long_name
    with pytest.raises(ValueError):
        am.insert_move_name(PY_TEXT, "BITE", "Bite", NAMES)


def test_format_entry_matches_movedb():
    """The formatter writes the current file's text for the entries whose keys are sorted"""
    text = am.MOVE_DB.read_bytes().decode("utf-8")
    newline = "\r\n" if "\r\n" in text else "\n"
    for name in ("Absorb", "Arm Thrust", "Bounce", "Fire Fang", "Metal Claw"):
        assert am.format_entry(name, moveDB[name], newline) in text, name


def test_check():
    """A MoveDB entry that differs from what the helper builds is listed with its fields"""
    moves = _showdown()
    tab = ({k: ROWS[k] for k in ("acid", "metalclaw")}, {}, {})
    db = {"Acid": moveDB["Acid"], "Metal Claw": {**moveDB["Metal Claw"], "pp": 30}, "Splash": {}}
    assert am.check(db, moves, tab) == [
        "Metal Claw: pp: MoveDB 30, built 35", "Splash: not in Showdown's data",
    ]
