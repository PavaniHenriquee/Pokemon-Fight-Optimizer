"""
Add each species' level-up moves from the Renegade Platinum documentation sheet to PkDB.json, as
"learnset": [[level, "Move"], ...]. Moves the engine doesn't have yet stay in the list, the ones it
has use MoveDB's spelling. Rerun it to refresh: only the learnset lines change.

The source is the sheet's DEX tab. It has one learnset per species next to the OLD / CLA / COM lines,
and it's right where the LEARNSETS tab has errors (Twinneedle, Thrash on Wailord).
Usage: python DataBase/import_learnsets.py [dex.csv]
Without a file it downloads the tab, export one by hand if the sheet asks for a login.
"""
import csv
import io
import json
import re
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PK_DB = HERE / "PkDB.json"
SHEET_ID = "1G3MNevhLmW1sKYluM4WT9TM1RqrTAi1c4lIdTfeU-Jg"
DEX_GID = "1888238811"
DEX_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={DEX_GID}"

# DEX tab columns of a species block: its name, then the level and move of each level-up row
NAME_COL = 1
LEVEL_COL = 13
MOVE_COL = 14
BLOCK_START = "LEARNSET"
LEVEL_UP_TITLE = "Level Up :"
LEVEL_UP_END = "TMs HMs :"

# Sheet name -> PkDB name, the rest are the same
SPECIES_ALIAS = {
    "Nidoran F": "Nidoran_f",
    "Nidoran M": "Nidoran_m",
    "Farfetch'd": "Farfetchd",
    "Mime Jr.": "Mime_jr",
    "Mr. Mime": "Mr_mime",
    "Porygon-Z": "Porygon_z",
    "Ho-oh": "Ho_oh",
    "Deoxys (Normal)": "Deoxys",
    "Deoxys (Attack)": "Deoxys_attack",
    "Deoxys (Defense)": "Deoxys_defense",
    "Deoxys (Speed)": "Deoxys_speed",
    "Wormadam (Plant)": "Wormadam",
    "Wormadam (Sandy)": "Wormadam_sandy",
    "Wormadam (Trash)": "Wormadam_trash",
    "Rotom (Heat)": "Rotom_heat",
    "Rotom (Wash)": "Rotom_wash",
    "Rotom (Frost)": "Rotom_frost",
    "Rotom (Spin)": "Rotom_fan",
    "Rotom (Cut)": "Rotom_mow",
    "Giratina (Altered)": "Giratina",
    "Giratina (Origin)": "Giratina_origin",
    "Shaymin (Land)": "Shaymin",
    "Shaymin (Sky)": "Shaymin_sky",
}


def clean_text(text: str) -> str:
    """Sheet text without its change marks: (!) and (!!), and invisible Unicode (U+180E and others)"""
    text = re.sub(r"[^\x20-\x7e]", "", text.replace("’", "'"))
    return " ".join(re.sub(r"\(!+\)", "", text).split())


def move_key(name: str) -> str:
    """Spelling-independent move name: the sheet writes Mud-slap, MoveDB Mud-Slap"""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def species_name(header: str) -> str:
    """'#386 Deoxys (Attack)' -> 'Deoxys_attack'"""
    name = clean_text(header.replace("♀", "F").replace("♂", "M"))
    name = re.sub(r"^#\d+\s+", "", name)
    return SPECIES_ALIAS.get(name, name)


def parse_dex(text: str, move_names) -> dict:
    """{species: [[level, move], ...]} from the DEX tab's CSV. A cell that isn't a level and a move
    raises, so a change in the sheet's layout fails here instead of writing bad data"""
    spelling = {move_key(name): name for name in move_names}
    learnsets = {}
    current = None
    for row in csv.reader(io.StringIO(text)):
        if len(row) <= MOVE_COL:
            continue
        level, move = clean_text(row[LEVEL_COL]), clean_text(row[MOVE_COL])
        if level == BLOCK_START:
            current = learnsets.setdefault(species_name(row[NAME_COL]), [])
        elif level == LEVEL_UP_END:
            current = None
        elif current is not None and level != LEVEL_UP_TITLE and (level or move):
            if not move:
                raise ValueError(f"Level {level} has no move: {row}")
            current.append([int(level), spelling.get(move_key(move), move)])
    return learnsets


def _learnset_text(learnset: list, eol: str) -> str:
    """The format Prettier keeps when the editor formats PkDB.json on save: one [level, move] per
    line, a single entry stays inline"""
    if len(learnset) == 1:
        return f'    "learnset": {json.dumps(learnset)},{eol}'
    entries = f",{eol}".join(f"      {json.dumps(entry)}" for entry in learnset)
    return f'    "learnset": [{eol}{entries}{eol}    ],{eol}'


def with_learnsets(db_text: str, learnsets: dict) -> str:
    """PkDB.json's text with each species' learnset right before its weight line, replacing the one
    a previous run added, so the rest of the file stays exactly as it is"""
    out = []
    species = None
    in_old_block = False
    for line in db_text.splitlines(keepends=True):
        if in_old_block:
            in_old_block = not line.startswith("    ],")
            continue
        head = re.match(r'  "(.+)": \{', line)
        if head:
            species = head[1]
        if line.startswith('    "learnset": '):
            in_old_block = line.rstrip().endswith("[")
            continue
        if line.startswith('    "weight": '):
            eol = "\r\n" if line.endswith("\r\n") else "\n"
            out.append(_learnset_text(learnsets[species], eol))
        out.append(line)
    return "".join(out)


def _without_learnsets(database: dict) -> dict:
    return {
        name: {k: v for k, v in entry.items() if k != "learnset"}
        for name, entry in database.items()
    }


def _download() -> str:
    with urllib.request.urlopen(DEX_URL, timeout=120) as res:
        if "text/csv" not in res.headers.get("Content-Type", ""):
            raise SystemExit("The sheet asked for a login: export the DEX tab as CSV and pass the file")
        return res.read().decode("utf-8")


def main() -> None:
    """Read the tab, check it covers PkDB exactly, write the learnset lines"""
    dex = Path(sys.argv[1]).read_text(encoding="utf-8") if len(sys.argv) > 1 else _download()
    moves = json.loads((HERE / "MoveDB.json").read_text(encoding="utf-8"))
    with open(PK_DB, encoding="utf-8", newline="") as f:
        old_text = f.read()
    old = json.loads(old_text)

    learnsets = parse_dex(dex, moves)
    if set(learnsets) != set(old):
        raise SystemExit(
            f"Species don't match PkDB. Only in the sheet: {sorted(set(learnsets) - set(old))}. "
            f"Only in PkDB: {sorted(set(old) - set(learnsets))}"
        )
    empty = [name for name, moves_list in learnsets.items() if not moves_list]
    if empty:
        raise SystemExit(f"No level-up moves: {empty}")

    new_text = with_learnsets(old_text, learnsets)
    new = json.loads(new_text)
    if _without_learnsets(new) != _without_learnsets(old) or set(new) != set(old):
        raise SystemExit("Something other than the learnsets changed, PkDB.json left as it was")
    if new_text != old_text:
        with open(PK_DB, "w", encoding="utf-8", newline="") as f:
            f.write(new_text)

    distinct ={move for moves_list in learnsets.values() for _, move in moves_list}
    print(f"{len(learnsets)} species, {len(distinct)} distinct moves, "
          f"{len(distinct & set(moves))} of them in MoveDB")


if __name__ == "__main__":
    main()
