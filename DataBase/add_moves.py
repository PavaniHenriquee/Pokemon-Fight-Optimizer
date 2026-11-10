"""
Build MoveDB entries for moves the engine doesn't have yet (ENGINE_PLAN.md 1.4), and insert them into
MoveDB.json and MoveName (DataBase/MoveDB.py) in alphabetical order.

The data comes from [SD] pokemon-showdown's moves.ts, with every inheritance layer applied in order (base,
then the gen8, gen7, gen6, gen5 and gen4 mods: each mod's scripts.ts inherits the next one). Only plain data
fields are read; a handler (onHit, basePowerCallback, condition, ...) is listed as engine work, never
written. Type, category, power, accuracy and PP come from the RP sheet's MOVES tab, and the tab's MOVE
MODIFICATIONS line for a move is printed for review. A value MoveDB can't hold (a volatile with no VolStatus
member, a self stat drop) is left out and listed, so every entry written converts.

Usage: python -m DataBase.add_moves [--sheet workbook.xlsx | moves.csv] [--write] Move [Move ...]
       python -m DataBase.add_moves --check [--sheet ...]
Without --write it only prints the entries and notes. --write inserts them and runs generate_constants.py.
--check compares every MoveDB entry with what this would build (the Phase 3 audit's starting point).
Without --sheet it downloads the workbook (File > Download > xlsx if the sheet asks for a login).
"""
import csv
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

from DataBase.import_learnsets import clean_text, move_key
from DataBase.import_trainers import WORKBOOK_URL, _download, read_workbook
from Models.helper import SideCondition, Target, VolStatus

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MOVE_DB = HERE / "MoveDB.json"
MOVE_NAME = HERE / "MoveDB.py"
TRAINER_DB = HERE / "TrainerDB.json"
SD_URL = "https://raw.githubusercontent.com/smogon/pokemon-showdown/master/data/{}moves.ts"
# Applied in this order, base first
SD_LAYERS = ("", "mods/gen8/", "mods/gen7/", "mods/gen6/", "mods/gen5/", "mods/gen4/")
SD_ALIAS = {"vicegrip": "visegrip"}  # move_key -> [SD]'s id, where they differ
MOVES_TAB = "MOVES"

# The MOVES tab (0-based columns, as read_workbook gives them)
NAME_COL, TYPE_COL, CATEGORY_COL, POWER_COL, ACCURACY_COL, PP_COL = 1, 3, 6, 8, 9, 10
MODIFICATIONS_COL = 9  # "Name // Power: 65 >> 75 // ...", above the move list
OLD_COL, NEW_COL = 1, 3  # MOVE REPLACEMENTS: "Old Move" -> "New Move"
PP_CELL = re.compile(r"(\d+)PP")
NO_VALUE = ("-", "--")

FUNCTION = "<function>"  # what the parser leaves for a handler

# [SD] field -> MoveDB field, for the ones that copy over as they are
SAME_VALUE = {
    "priority": "priority", "drain": "drain", "forceSwitch": "force_switch", "sleepUsable": "sleep_usable",
    "willCrit": "will_crit", "ignoreDefensive": "ignore_def", "hasCrashDamage": "has_crash_damage",
    "smartTarget": "smart_target",
}
# Read elsewhere or only cosmetic
SKIPPED = {
    "num", "name", "desc", "shortDesc", "contestType", "isNonstandard", "inherit", "zMove", "maxMove", "isZ",
    "isMax", "gen", "realMove", "type", "category", "basePower", "accuracy", "pp", "flags", "target",
    "secondary", "secondaries", "boosts", "status", "volatileStatus", "sideCondition", "selfSwitch", "ohko",
    "ignoreImmunity", "overrideOffensiveStat", "overrideDefensiveStat", "damage", "critRatio", "recoil",
    "multihit", "self", *SAME_VALUE,
}
BOOST = {"atk": "atk", "def": "def", "spa": "spatk", "spd": "spdef", "spe": "speed", "accuracy": "acc",
         "evasion": "ev"}  # [SD] boost -> MoveDB's boost_* suffix
SECONDARY_BOOST = {"atk": "atk", "def": "def", "spa": "spa", "spd": "spd", "spe": "speed",
                   "accuracy": "accuracy", "evasion": "evasion"}  # [SD] boost -> MoveDB secondary key
STATUS = {"slp": "sleep", "frz": "freeze", "par": "paralysis", "brn": "burn", "psn": "poison", "tox": "toxic"}
STAT = {"atk": "attack", "def": "defense", "spa": "special_attack", "spd": "special_defense", "spe": "speed"}
DAMAGE = ("level",)  # the [SD] damage strings Models/move.py reads; a number copies over
# Shadow Force, the last Gen IV move by [SD] num. RP's damaging moves from later generations trigger King's
# Rock (Models/move.py KINGS_ROCK_MOVES), the Gen IV ones only when [SD] gen4's list has them
LAST_GEN4_MOVE = 467
FLAG = {  # [SD] flag -> MoveDB's spelling, where it isn't the same
    "bypasssub": "bypass_sub", "cantusetwice": "cant_use_twice", "failcopycat": "fail_copycat",
    "failencore": "fail_encore", "failinstruct": "fail_instruct", "failmefirst": "fail_me_first",
    "failmimic": "fail_mimic", "futuremove": "future_move", "mustpressure": "must_pressure",
    "noassist": "no_assist", "nonsky": "non_sky", "noparentalbond": "no_parental_bond",
    "nosketch": "no_sketch", "nosleeptalk": "no_sleep_talk", "pledgecombo": "pledge_combo",
}


# ----- [SD] moves.ts -----

TOKEN = re.compile(r"""
    (?P<skip>\s+|//[^\n]*|/\*.*?\*/)
  | (?P<str>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)
  | (?P<num>\d+(?:\.\d+)?)
  | (?P<word>[A-Za-z_$][\w$]*)
  | (?P<punct>[{}\[\]():,])
  | (?P<other>.)
""", re.X | re.S)
OPEN, CLOSE = "{[(", "}])"


def _tokens(text: str) -> list:
    return [(m.lastgroup, m.group()) for m in TOKEN.finditer(text) if m.lastgroup != "skip"]


def _skip_group(toks: list, i: int) -> int:
    """Index after the bracket group that starts at toks[i]"""
    depth = 0
    while True:
        kind, tok = toks[i]
        if kind == "punct" and tok in OPEN:
            depth += 1
        elif kind == "punct" and tok in CLOSE:
            depth -= 1
            if not depth:
                return i + 1
        i += 1


def _skip_expression(toks: list, i: int) -> int:
    """Index of the , or closing bracket that ends the expression at toks[i]"""
    while not (toks[i][0] == "punct" and toks[i][1] in ",}]"):
        i = _skip_group(toks, i) if toks[i][0] == "punct" and toks[i][1] in OPEN else i + 1
    return i


def _string(tok: str) -> str:
    return tok[1:-1].replace("\\'", "'").replace('\\"', '"')


def _value(toks: list, i: int) -> tuple:
    """(value, index after it). Anything that isn't plain data is FUNCTION"""
    kind, tok = toks[i]
    if kind == "punct" and tok == "{":
        value, j = _object(toks, i)
    elif kind == "punct" and tok == "[":
        value, j = [], i + 1
        while toks[j][1] != "]":
            item, j = _value(toks, j)
            value.append(item)
            j += toks[j][1] == ","
        j += 1
    elif kind == "other" and tok == "-" and toks[i + 1][0] == "num":
        value, j = -_number(toks[i + 1][1]), i + 2
    elif kind == "num":
        value, j = _number(tok), i + 1
    elif kind == "str":
        value, j = _string(tok), i + 1
    elif kind == "word" and tok in ("true", "false", "null", "undefined"):
        value, j = {"true": True, "false": False}.get(tok), i + 1
    else:
        return FUNCTION, _skip_expression(toks, i)
    if not (toks[j][0] == "punct" and toks[j][1] in ",}]"):  # the literal starts an expression
        return FUNCTION, _skip_expression(toks, j)
    return value, j


def _number(tok: str):
    return float(tok) if "." in tok else int(tok)


def _object(toks: list, i: int) -> tuple:
    """Parse the {...} at toks[i]: (dict, index after it). A method becomes FUNCTION"""
    out, i = {}, i + 1
    while toks[i][1] != "}":
        if toks[i][0] == "word" and toks[i][1] in ("get", "async") and toks[i + 1][0] in ("word", "str"):
            i += 1
        key = _string(toks[i][1]) if toks[i][0] == "str" else toks[i][1]
        if toks[i + 1][1] == "(":  # key(args) { body }
            out[key], i = FUNCTION, _skip_group(toks, _skip_group(toks, i + 1))
        else:
            out[key], i = _value(toks, i + 2)
        i += toks[i][1] == ","
    return out, i + 1


def parse_moves_ts(text: str) -> dict:
    """{id: fields} from a Showdown moves.ts"""
    toks = _tokens(text)
    start = next(i for i, (_, tok) in enumerate(toks) if tok == "=") + 1
    moves, _ = _object(toks, start)
    expected = len(re.findall(r"^\t[\w\"]+: \{", text, re.M))
    if len(moves) != expected:
        raise ValueError(f"Parsed {len(moves)} moves, the file has {expected}: the parser needs a fix")
    return moves


def merge_layers(layers: list) -> dict:
    """[SD]'s inheritance: each layer, base first, overrides the fields it lists (inherit: true) or replaces
    the move"""
    moves = {}
    for layer in layers:
        for move_id, fields in layer.items():
            if fields.get("inherit") and move_id in moves:
                moves[move_id] = {**moves[move_id], **fields}
            else:
                moves[move_id] = dict(fields)
    return moves


def load_showdown() -> dict:
    """Every move, from [SD]'s files with the gen4 inheritance applied"""
    texts = []
    for layer in SD_LAYERS:
        with urllib.request.urlopen(SD_URL.format(layer), timeout=60) as res:
            texts.append(res.read().decode("utf-8"))
    return merge_layers([parse_moves_ts(t) for t in texts])


# ----- the sheet's MOVES tab -----

def parse_moves_tab(cells: dict) -> tuple:
    """({move_key: row}, {move_key: modification line}, {move_key of an old move: its replacement}) from the
    tab's {(row, col): text}"""
    rows = {}
    for (r, c), text in cells.items():
        rows.setdefault(r, {})[c] = clean_text(text)
    moves, modifications, replaced = {}, {}, {}
    header = next(r for r, row in rows.items() if row.get(NAME_COL) == "NAME")
    old_header = next(r for r, row in rows.items() if row.get(OLD_COL) == "Old Move")
    for r in sorted(rows):
        row = rows[r]
        if r > header and PP_CELL.fullmatch(row.get(PP_COL, "")):
            moves[move_key(row[NAME_COL])] = row
        elif r < header and " // " in row.get(MODIFICATIONS_COL, ""):
            line = row[MODIFICATIONS_COL]
            modifications[move_key(line.split(" // ")[0].rstrip(":"))] = line
        if old_header < r < header and row.get(OLD_COL) and row.get(NEW_COL):
            replaced[move_key(row[OLD_COL])] = row[NEW_COL]
    return moves, modifications, replaced


def read_moves_tab(path) -> dict:
    """The MOVES tab's cells, from an xlsx (the whole workbook), a CSV of the tab, or a download"""
    if path and str(path).lower().endswith(".csv"):
        with open(path, encoding="utf-8", newline="") as f:
            return {(r, c): text for r, row in enumerate(csv.reader(f)) for c, text in enumerate(row) if text}
    data = Path(path).read_bytes() if path else _download(WORKBOOK_URL, binary=True)
    values, _ = read_workbook(data, [MOVES_TAB])[MOVES_TAB]
    return values


def sheet_numbers(row: dict, sd: dict) -> dict:
    """Type, category, power, accuracy and PP from the tab, [SD]'s where the tab has none"""
    out = {}
    out["type"] = sd["type"] if row[TYPE_COL] in NO_VALUE else row[TYPE_COL].title()
    out["category"] = "Status" if row[CATEGORY_COL] == "OTHER" else row[CATEGORY_COL].title()
    power = row.get(POWER_COL, "--")
    power = sd.get("basePower", 0) if power in NO_VALUE else int(float(power))
    if power:
        out["power"] = power
    accuracy = row.get(ACCURACY_COL, "--")
    if accuracy in NO_VALUE:
        out["accuracy"] = True
    else:
        out["accuracy"] = int(accuracy[:-1]) if accuracy.endswith("%") else round(float(accuracy) * 100)
    out["pp"] = int(PP_CELL.fullmatch(row[PP_COL])[1])
    return out


# ----- [SD] fields -> a MoveDB entry -----

def _enum_value(enum, sd_value: str):
    """'partiallytrapped' -> 'partially_trapped' when the enum has PARTIALLY_TRAPPED, else None"""
    names = {k.replace("_", "").lower(): k.lower() for k in vars(enum) if not k.startswith("_")}
    return names.get(re.sub(r"[^a-z0-9]", "", str(sd_value).lower()))


def _secondary(sd_sec: dict, notes: list, where: str) -> dict:
    """One [SD] secondary in MoveDB's keys, a note for what it can't hold"""
    out = {}
    for key, value in sd_sec.items():
        if key == "chance":
            out["chance"] = value
        elif key == "boosts":
            out.update({SECONDARY_BOOST[s]: n for s, n in value.items()})
        elif key == "self" and set(value) == {"boosts"}:
            out["target"] = "self"
            out.update({SECONDARY_BOOST[s]: n for s, n in value["boosts"].items()})
        elif key == "status" and value in STATUS:
            out["status"] = STATUS[value]
        elif key == "volatileStatus" and _enum_value(VolStatus, value):
            out["vol_status"] = _enum_value(VolStatus, value)
        else:
            notes.append(f"{where}.{key}: {_show(value)}")
    return out


def _show(value) -> str:
    return value if isinstance(value, str) else json.dumps(value)


def _numbers(sd: dict, row, notes: list) -> dict:
    """Type, category, power, accuracy and PP: the tab's row, or [SD]'s for a move the tab doesn't have"""
    if row is not None:
        return sheet_numbers(row, sd)
    notes.append("not on the MOVES tab: [SD]'s type, category, power, accuracy and PP")
    entry = {"type": sd["type"], "category": sd["category"], "accuracy": sd["accuracy"], "pp": sd["pp"]}
    if sd.get("basePower"):
        entry["power"] = sd["basePower"]
    return entry


def _basics(sd: dict, entry: dict, notes: list) -> None:
    """Target, flags, the charge / recharge turn, and the fields that need little or no translation"""
    target = _enum_value(Target, sd["target"])
    if target:
        entry["target"] = target
    else:
        notes.append(f"target: {sd['target']}")
    flags = {FLAG.get(f, f): True for f, on in sorted(sd.get("flags", {}).items()) if on}
    if flags:
        entry["flags"] = flags
    if flags.get("charge"):
        entry["charge"] = 1  # the flag alone does nothing (CLAUDE.md)
    if flags.get("recharge"):
        entry["recharge"] = 1
    entry.update({db_key: sd[sd_key] for sd_key, db_key in SAME_VALUE.items() if sd.get(sd_key)})
    if sd.get("critRatio", 1) != 1:
        entry["crit_ratio"] = sd["critRatio"]
    if sd.get("recoil"):
        entry["recoil"] = sd["recoil"][1] // sd["recoil"][0]  # the divisor: 4, 3 or 2
    if sd.get("multihit"):
        hits = sd["multihit"]
        entry["multi_hit"] = hits if isinstance(hits, list) else [hits, hits]
    for sd_key, db_key in (("selfSwitch", "self_switch"), ("ohko", "oh_ko")):
        if sd.get(sd_key):
            entry[db_key] = True  # Baton Pass's "copyvolatile" and Sheer Cold's "Ice" too


def _special_values(sd: dict, entry: dict, notes: list) -> None:
    """ignoreImmunity, the stat overrides and damage: copied when MoveDB can hold them, else a note"""
    if isinstance(sd.get("ignoreImmunity"), bool):
        entry["ignore_immunity"] = sd["ignoreImmunity"]
    elif "ignoreImmunity" in sd:
        notes.append(f"ignoreImmunity: {_show(sd['ignoreImmunity'])}")
    for sd_key, db_key in (("overrideOffensiveStat", "override_off_stat"),
                           ("overrideDefensiveStat", "override_def_stat")):
        if sd.get(sd_key) in STAT:
            entry[db_key] = STAT[sd[sd_key]]
        elif sd_key in sd:
            notes.append(f"{sd_key}: {_show(sd[sd_key])}")
    if isinstance(sd.get("damage"), int) or sd.get("damage") in DAMAGE:
        entry["damage"] = sd["damage"]
    elif "damage" in sd:
        notes.append(f"damage: {_show(sd['damage'])}")


def _effects(sd: dict, entry: dict, notes: list) -> None:
    """Stat changes, status, a volatile or side condition, and the self effect"""
    for stat, n in (sd.get("boosts") or {}).items():
        entry[f"boost_{BOOST[stat]}"] = n
    if sd.get("status") in STATUS:
        entry["status"] = STATUS[sd["status"]]
    elif sd.get("status"):
        notes.append(f"status: {sd['status']}")
    for sd_key, db_key, enum in (("volatileStatus", "vol_status", VolStatus),
                                 ("sideCondition", "side_condition", SideCondition)):
        if sd.get(sd_key) and _enum_value(enum, sd[sd_key]):
            entry[db_key] = _enum_value(enum, sd[sd_key])
        elif sd.get(sd_key):
            notes.append(f"{sd_key}: {sd[sd_key]} (no {enum.__name__} member)")
    if _sure_self_boosts(sd):  # _secondaries holds it
        return
    if sd.get("self") and sd["self"] != {"volatileStatus": "mustrecharge"}:  # the recharge flag has that one
        notes.append(f"self: {_show(sd['self'])}")


def _sure_self_boosts(sd: dict) -> dict:
    """A damaging move's own sure stat change (Close Combat), when it has no secondary to share the slot with"""
    own = sd.get("self") or {}
    if set(own) != {"boosts"} or sd.get("category") == "Status" or sd.get("secondary") or sd.get("secondaries"):
        return {}
    return own["boosts"]


def _secondaries(sd: dict, entry: dict, notes: list) -> None:
    """The secondary effect. A second one (the fangs' flinch) goes in chance2 / vol_status2. A damaging move's
    sure stat change on its user goes there too, as a 100% one aimed at the user"""
    secondaries = sd.get("secondaries") or ([sd["secondary"]] if sd.get("secondary") else [])
    if _sure_self_boosts(sd):
        secondaries = [{"chance": 100, "self": {"boosts": _sure_self_boosts(sd)}}]
    if not secondaries:
        return
    secondary = _secondary(secondaries[0], notes, "secondary")
    for extra in secondaries[1:]:
        more = _secondary(extra, notes, "secondaries[1]")
        if set(more) <= {"chance", "vol_status"} and "chance2" not in secondary:
            secondary["chance2"] = more.get("chance", 0)
            if "vol_status" in more:
                secondary["vol_status2"] = more["vol_status"]
        else:
            notes.append(f"secondaries: {_show(extra)}")
    entry["secondary"] = dict(sorted(secondary.items()))


def build_entry(key: str, sd: dict, row) -> tuple:
    """(MoveDB entry, notes) for one move: [SD]'s data with the tab's row's numbers (row None: [SD]'s). A
    damaging move from after Gen IV gets kings_rock"""
    notes = []
    entry = _numbers(sd, row, notes)
    entry["name"] = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
    for part in (_basics, _special_values, _effects, _secondaries):
        part(sd, entry, notes)
    if sd.get("num", 0) > LAST_GEN4_MOVE and entry["category"] != "Status":
        entry["kings_rock"] = True
    handlers = sorted(k for k, v in sd.items() if k not in SKIPPED and v is not None and v is not False)
    if handlers:
        notes.append("engine work: " + ", ".join(handlers))
    return dict(sorted(entry.items())), notes


# ----- writing MoveDB.json and MoveName -----

def format_entry(key: str, entry: dict, newline: str = "\n") -> str:
    """MoveDB.json's text for one entry, at its indent, no trailing comma: sorted keys, lists on one line"""
    text = json.dumps({key: entry}, indent=2, sort_keys=True, ensure_ascii=False)
    text = re.sub(r"\[\s+([^\[\]{}]*?)\s+\]", lambda m: "[" + ", ".join(
        x.strip() for x in m.group(1).split(",")) + "]", text)
    return newline.join(text.splitlines()[1:-1])


def _order(name: str) -> str:
    return name.lower()


def insert_json(text: str, key: str, entry: dict) -> str:
    """MoveDB.json's text with the entry before the first move that sorts after it. Nothing else changes"""
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(newline)
    starts = [(i, m[1]) for i, line in enumerate(lines) if (m := re.fullmatch(r'  "(.+)": \{', line))]
    if any(name == key for _, name in starts):
        raise ValueError(f"{key} is already in MoveDB.json")
    block = format_entry(key, entry, newline).split(newline)
    after = next((i for i, name in starts if _order(name) > _order(key)), None)
    if after is not None:
        block[-1] += ","
        lines[after:after] = block
    else:
        end = max(i for i, line in enumerate(lines) if line == "  }")
        lines[end] += ","
        lines[end + 1:end + 1] = block
    return newline.join(lines)


CHAIN = re.compile(r"(    )([A-Z0-9_]+)( +)= (?:([A-Z0-9_]+) \+ 1|1)$")


def insert_move_name(text: str, const: str, order_name: str, names: dict) -> str:
    """MoveDB.py's text with `CONST = PREV + 1` before the first MoveName that sorts after it (names:
    {CONST: MoveDB key}, for the order), and the next one pointing at it"""
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(newline)
    chain = [(i, m) for i, line in enumerate(lines) if (m := CHAIN.fullmatch(line))]
    if any(m[2] == const for _, m in chain):
        raise ValueError(f"{const} is already in MoveName")
    after = next((k for k, (_, m) in enumerate(chain) if _order(names[m[2]]) > _order(order_name)), None)
    if after is None:
        prev = chain[-1][1][2]
    else:
        prev = chain[after - 1][1][2] if after else None
    new = f"    {const:<15} = {f'{prev} + 1' if prev else '1'}"
    if after is None:
        lines.insert(chain[-1][0] + 1, new)
    else:
        i, m = chain[after]
        lines[i] = f"{m[1]}{m[2]}{m[3]}= {const} + 1"
        lines.insert(i, new)
    return newline.join(lines)


# ----- the command -----

def _trainer_spellings() -> dict:
    trainers = json.loads(TRAINER_DB.read_text(encoding="utf-8"))
    teams = trainers.values() if isinstance(trainers, dict) else trainers
    return {move_key(m): m for t in teams for p in t["team"] for m in p["moves"] if m}


def resolve(name: str, sd_moves: dict, tab: tuple, trainer_names: dict) -> tuple:
    """(MoveDB key, [SD] fields, tab row or None, modification line or None) for a name in any spelling. The
    key is TrainerDB's spelling, else the tab's, else [SD]'s"""
    moves, modifications, replaced = tab
    k = move_key(name)
    if k in replaced:
        raise ValueError(f"{name}: RP replaces it with {replaced[k]}")
    sd = sd_moves.get(SD_ALIAS.get(k, k))
    if sd is None:
        raise ValueError(f"{name}: not in Showdown's data")
    row = moves.get(k)
    key = trainer_names.get(k) or (row[NAME_COL] if row else sd["name"])
    return key, sd, row, modifications.get(k)


def check(move_db: dict, sd_moves: dict, tab: tuple) -> list:
    """Every MoveDB entry next to what build_entry gives: the lines of the fields that differ"""
    out = []
    for key, current in move_db.items():
        k = move_key(key)
        sd = sd_moves.get(SD_ALIAS.get(k, k))
        if sd is None:
            out.append(f"{key}: not in Showdown's data")
            continue
        built, _ = build_entry(key, sd, tab[0].get(k))
        diffs = [f"{f}: MoveDB {_show(current.get(f, '-'))}, built {_show(built.get(f, '-'))}"
                 for f in sorted(set(current) | set(built)) if current.get(f) != built.get(f)]
        if diffs:
            out.append(f"{key}: " + "; ".join(diffs))
    return out


def _args(argv: list) -> tuple:
    """(write, check, sheet path, move names) from the command line"""
    write, run_check, sheet, names = False, False, None, []
    it = iter(argv)
    for arg in it:
        if arg == "--write":
            write = True
        elif arg == "--check":
            run_check = True
        elif arg == "--sheet":
            sheet = next(it)
        else:
            names.append(arg)
    if not (names or run_check):
        raise SystemExit(__doc__)
    return write, run_check, sheet, names


def main() -> None:
    write, run_check, sheet, names = _args(sys.argv[1:])
    sd_moves = load_showdown()
    tab = parse_moves_tab(read_moves_tab(sheet))
    move_db_text = MOVE_DB.read_bytes().decode("utf-8")
    move_db = json.loads(move_db_text)
    if run_check:
        lines = check(move_db, sd_moves, tab)
        print(f"{len(lines)} of {len(move_db)} MoveDB entries differ from what add_moves builds:")
        print("\n".join(f"  {line}" for line in lines))
    trainer_names = _trainer_spellings()
    built = []
    for name in names:
        try:
            key, sd, row, modification = resolve(name, sd_moves, tab, trainer_names)
        except ValueError as e:
            raise SystemExit(str(e)) from e
        if key in move_db:
            raise SystemExit(f"{key} is already in MoveDB")
        entry, notes = build_entry(key, sd, row)
        if modification:
            notes.append(f"MOVE MODIFICATIONS: {modification}")
        built.append((key, entry))
        print(format_entry(key, entry))
        print("\n".join(f"    # {note}" for note in notes) or "    # every [SD] field mapped, no handlers")
    if not (write and built):
        return
    names_by_const = {e["name"].upper(): k for k, e in move_db.items()}
    move_name_text = MOVE_NAME.read_bytes().decode("utf-8")
    for key, entry in built:
        move_db_text = insert_json(move_db_text, key, entry)
        move_name_text = insert_move_name(move_name_text, entry["name"].upper(), key, names_by_const)
        names_by_const[entry["name"].upper()] = key
    MOVE_DB.write_bytes(move_db_text.encode("utf-8"))
    MOVE_NAME.write_bytes(move_name_text.encode("utf-8"))
    subprocess.run([sys.executable, "generate_constants.py"], cwd=ROOT, check=True)
    print(f"Added {len(built)} moves to MoveDB.json and MoveName, and regenerated Models/constants.py")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
