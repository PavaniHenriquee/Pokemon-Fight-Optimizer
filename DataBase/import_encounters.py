"""
Write EncounterDB.json from the Renegade Platinum documentation sheet's ENCOUNTERS tab: what can be
met at each location, in the sheet's story order. The Nuzlocke tracker reads it.

A location is the met location a caught Pokemon's summary shows. [pp] gives Pokemon_SetCatchData the
map's label (battle_lib.c, battle_main.c, field_battle_data_transfer.c), and the label is each map's
locationName in res/field/maps/<map>/header.json. So Route 204's south and north maps, or Route 209 and
the Lost Tower, are one location however the sheet's blocks split them. [pp] is vanilla, RP's ROM wasn't
read, but the sheet's own "met location" notes agree on every location they mention.

The tab is a free-form grid. Groups of GROUP_WIDTH columns run top to bottom, each with block headings
and method lines in its first column and Pokemon in the next one. A group with nothing in row 1
continues the block on its left at the same row. Text it doesn't know raises, so a change in the sheet's
layout fails here instead of writing bad data.

The species clause needs evolution lines too: those come from the STATS tab's last column.
Usage: python -m DataBase.import_encounters [encounters.csv stats.csv]
Without files it downloads the tabs, export them by hand if the sheet asks for a login.
"""
import csv
import io
import json
import re
import sys
import urllib.request
from pathlib import Path

from DataBase.import_learnsets import SHEET_ID, clean_text, species_name

HERE = Path(__file__).resolve().parent
ENCOUNTER_DB = HERE / "EncounterDB.json"
ENCOUNTERS_GID = "515626425"
STATS_GID = "304097162"

FIRST_COL = 4
GROUP_WIDTH = 7
HEADING_ROW = 1
# Where the groups end: it repeats the Mt. Coronet tables in a layout of its own
MASTER_TABLE = "MT CORONET MASTER TABLE"

STARTER_LOCATION = "Route 201"
STARTER_METHOD = "Gift from Professor Rowan"
GREAT_MARSH = "Great Marsh"
DEFAULT_METHOD = "Static Encounter"
# Groups that only list legendaries by location, repeating some the location's own block has. They're
# read last, so a location that's also on the story path keeps its place there
LEGENDARY_LISTS = ("POST DISTORTION WORLD LEGENDARIES", "AFTER CREDITS LEGENDARIES")
# (group, row) of a method line that belongs to the block on the left despite its group having a heading
# above it. Moltres: Victory Road's block is two groups wide here, under Route 223's
HANDED_LEFT = {(305, 15)}

# Sheet heading -> [pp] location name, the rest are the heading in title case
MET_ALIAS = {
    "MT CORONET": "Mt. Coronet",
    "LOST TOWER": "Route 209",
    "TRAINER SCHOOL": "Trainers' School",
    "GALACTIC BUILDING": "T.G. Eterna Bldg",
    "AREA 1 AND 2": GREAT_MARSH,
    "AREA 3 AND 4": GREAT_MARSH,
    "AREA 5 AND 6": GREAT_MARSH,
    "POKEMON LEAGUE": "Pokémon League",
    "POKEMON MANSION": "Pokémon Mansion",
    "HALL OF ORIGIN": "Hall of Origin",
}
# Headings that are an area of a location without saying so in parentheses
AREA_ALIAS = {
    "LOST TOWER": "Lost Tower",
    "AREA 1 AND 2": "Areas 1 and 2",
    "AREA 3 AND 4": "Areas 3 and 4",
    "AREA 5 AND 6": "Areas 5 and 6",
}
# Sheet name -> PkDB name, on top of import_learnsets' SPECIES_ALIAS
ENCOUNTER_SPECIES_ALIAS = {
    "Deoxys (N)": "Deoxys",
    "Magikarp (GER)": "Magikarp",
    "Wormadam (P)": "Wormadam",
}

# First-column text that starts a table. Pok Radar: clean_text drops the accent
METHOD_RE = re.compile(
    r"(Grass|Cave|Surf|Rods|Ground|Honey Tree|Pok Radar|Static|Gift|Egg gifted|Mr\. Backlot"
    r"|Inside Rowan|Revive|Trade with|Lost Tower|After the Events|CHANGING POKEMON)"
)
# First-column text that says nothing about what's caught
NOTE_RE = re.compile(
    r"(Details|More details|On fridays|One of these|Mt\. Coronet master|link to|the Lost Tower"
    r"|Talk to|Get the two|Remember|If you|Every day|That 10%|The probabilities|Good luck"
    r"|[\d-]+$)"
)

# STATS tab columns of a species row. Its evolution cell reads "#001 Lv. 16 - Can evolve into #003"
STATS_NAME_COL = 1
STATS_EVOLUTION_COL = 43
STATS_EVOLUTION_TITLE = "EVOLUTION METHODS"
# The sheet's numbers for the Hoppip line are off by one: Hoppip "evolves into #187" (itself), Skiploom
# comes "from #186" (Politoed) and Jumpluff "from #187". Taken as written that puts Skiploom in Poliwag's
# line. Showdown has Hoppip -> Skiploom -> Jumpluff, and agrees with the sheet on all the other lines
EVOLUTION_FIXES = {187: (188,), 188: (187, 189), 189: (188,)}


def _heading(text: str):
    """(location, area) of a block heading such as 'ROUTE 204 (SOUTH)', None for any other text"""
    match = re.fullmatch(r"([^()]*?)\s*(?:\((.*)\))?", text)
    if not match or not re.search(r"[A-Z]{3}", match[1]) or match[1] != match[1].upper():
        return None
    base, suffix = match[1], match[2]
    area = suffix.title() if suffix else AREA_ALIAS.get(base, "")
    return MET_ALIAS.get(base, base.title()), area


def _method_label(text: str) -> str:
    """A method line as it's shown: 'Trade with a Beauty (details :' -> 'Trade with a Beauty'"""
    text = re.sub(r"\s*\(details :?$", "", text).replace("Pok Radar", "Poké Radar")
    return "Changing Pokemon" if text == "CHANGING POKEMON" else text


def _table(tables: list, area: str, method: str) -> dict:
    """The location's table for this area and method, added if it's new"""
    for table in tables:
        if table["area"] == area and table["method"] == method:
            return table
    table = {"area": area, "method": method, "mons": []}
    tables.append(table)
    return table


def _mon_cell(cells: list) -> int:
    """Column of a Pokemon in a group's cells, -1 if the row has none. It's almost always the second
    one: Giratina in the Distortion World is in the third"""
    for col in (1, 2):
        if clean_text(cells[col]).startswith("#"):
            return col
    return -1


def _table_for_row(tables: list, place: tuple, own_heading: bool) -> dict:
    """The table of a Pokemon with no method line above it in its group. Under its own heading it's a
    static encounter. In a continuation it's a table on the left: one still waiting for its Pokemon
    (Heatran, Manaphy), else the location's last, which wrapped around (Route 222's Surf)"""
    if not own_heading:
        for table in tables:
            if not table["mons"]:
                return table
        if tables:
            return tables[-1]
    return _table(tables, place[1], DEFAULT_METHOD)


def _add_mon(tables: list, table: dict, cells: list, col: int, is_list: bool) -> None:
    """Add the row's Pokemon to the table. A trade's 'you give' row isn't an encounter. A Pokemon only
    counts once per table, and once per location in a list of legendaries"""
    if "you give" in (clean_text(cell) for cell in cells):
        return
    name = species_name(cells[col])
    name = ENCOUNTER_SPECIES_ALIAS.get(name, name)
    seen = [mon for other in tables for mon in other["mons"]] if is_list else table["mons"]
    if all(mon["name"] != name for mon in seen):
        level = clean_text(cells[col + 1])
        table["mons"].append({"name": name, "level": level if level[:1].isdigit() else ""})


def _read_group(rows: list, start: int, left: dict, locations: dict, is_list: bool) -> dict:
    """Add one column group's tables to locations. Returns {row: (location, area)} for the next group"""
    continues_left = _heading(clean_text(rows[HEADING_ROW][start])) is None
    here = {}
    own = table = None
    for r, row in enumerate(rows):
        if r < HEADING_ROW:
            continue
        cells = (row[start:start + GROUP_WIDTH] + [""] * GROUP_WIDTH)[:GROUP_WIDTH]
        first = clean_text(cells[0])
        if METHOD_RE.match(first):
            if (start, r) in HANDED_LEFT:
                own = None
            place = own or left.get(r)
            if place is None:
                raise ValueError(f"Method line outside any block, row {r}: {first!r}")
            # The sheet draws the Great Marsh's Surf and Rods under its last area, they aren't that
            # area's. Everywhere else a table belongs to the heading above it
            area = place[1] if place[0] != GREAT_MARSH or first.startswith("Grass") else ""
            table = _table(locations.setdefault(place[0], []), area, _method_label(first))
        elif first:
            heading = _heading(first)
            if heading:
                own, table = heading, None
            elif not NOTE_RE.match(first):
                raise ValueError(f"Unknown text in column {start}, row {r}: {first!r}")
        place = here[r] = own or left.get(r)

        col = _mon_cell(cells)
        if col >= 0:
            if place is None:
                raise ValueError(f"Pokemon outside any block, row {r}: {cells[col]!r}")
            tables = locations.setdefault(place[0], [])
            if table is None:
                table = _table_for_row(tables, place, own is not None)
            _add_mon(tables, table, cells, col, is_list)
        elif continues_left and not any(clean_text(cell) for cell in cells):
            own = table = None  # a blank row hands the rows below back to the block on the left
    return here


def parse_encounters(text: str, known_species) -> dict:
    """{"starters": [names], "locations": {location: [{"area", "method", "mons": [{"name", "level"}]}]}}
    from the ENCOUNTERS tab's CSV, in the sheet's order. A heading with no Pokemon under it is only the
    sheet's trail between places, so it doesn't become a location"""
    rows = list(csv.reader(io.StringIO(text)))
    ends = [c for row in rows for c, cell in enumerate(row) if clean_text(cell) == MASTER_TABLE]
    if not ends:
        raise ValueError(f"{MASTER_TABLE!r} not found: the sheet's layout changed")

    locations = {}
    left = {}
    starts = range(FIRST_COL, ends[0], GROUP_WIDTH)
    lists = [s for s in starts if clean_text(rows[HEADING_ROW][s]) in LEGENDARY_LISTS]
    for start in [s for s in starts if s not in lists] + lists:
        left = _read_group(rows, start, left, locations, start in lists)

    locations = {
        name: [table for table in tables if table["mons"]]
        for name, tables in locations.items()
        if any(table["mons"] for table in tables)
    }
    unknown = {mon["name"] for tables in locations.values() for t in tables for mon in t["mons"]}
    unknown -= set(known_species)
    if unknown:
        raise ValueError(f"Species not in PkDB: {sorted(unknown)}")

    gift = next(
        (t for t in locations.get(STARTER_LOCATION, []) if t["method"] == STARTER_METHOD), None
    )
    if gift is None:
        raise ValueError(f"{STARTER_METHOD!r} not found in {STARTER_LOCATION}")
    locations[STARTER_LOCATION].remove(gift)  # the starter doesn't use Route 201's encounter
    return {"starters": [mon["name"] for mon in gift["mons"]], "locations": locations}


def parse_evolution_lines(text: str, known_species) -> list:
    """[[species of one evolution line, in the sheet's order], ...] from the STATS tab's CSV. It goes by
    dex number, so a species' forms join its line. Fails unless every PkDB species is in exactly one"""
    rows = list(csv.reader(io.StringIO(text)))
    if not rows or len(rows[0]) <= STATS_EVOLUTION_COL or (
        clean_text(rows[0][STATS_EVOLUTION_COL]) != STATS_EVOLUTION_TITLE
    ):
        raise ValueError(f"{STATS_EVOLUTION_TITLE!r} not found: the sheet's layout changed")

    links = {}
    species = []
    for row in rows:
        dex = re.match(r"#(\d+)", clean_text(row[STATS_NAME_COL]))
        if dex:
            species.append((int(dex[1]), species_name(row[STATS_NAME_COL])))
            cell = clean_text(row[STATS_EVOLUTION_COL])
            links[int(dex[1])] = EVOLUTION_FIXES.get(int(dex[1]), tuple(map(int, re.findall(r"#(\d+)", cell))))

    if {name for _, name in species} != set(known_species):
        raise ValueError(
            f"Species don't match PkDB: {sorted({name for _, name in species} ^ set(known_species))}"
        )
    line_of = {dex: dex for dex in links}

    def root(dex: int) -> int:
        while line_of[dex] != dex:
            dex = line_of[dex]
        return dex

    for dex, others in links.items():
        for other in others:
            line_of[root(other)] = root(dex)

    lines = {}
    for dex, name in species:
        lines.setdefault(root(dex), []).append(name)
    return list(lines.values())


def db_text(database: dict) -> str:
    """The file's text, one table or evolution line per row so a new import's diff shows what changed"""
    blocks = []
    for name, tables in database["locations"].items():
        rows = ",\n".join(f"      {json.dumps(table)}" for table in tables)
        blocks.append(f"    {json.dumps(name)}: [\n{rows}\n    ]")
    locations = ",\n".join(blocks)
    lines = ",\n".join(f"    {json.dumps(line)}" for line in database["evolution_lines"])
    return (
        f'{{\n  "starters": {json.dumps(database["starters"])},\n'
        f'  "locations": {{\n{locations}\n  }},\n'
        f'  "evolution_lines": [\n{lines}\n  ]\n}}\n'
    )


def _download(gid: str) -> str:
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
    with urllib.request.urlopen(url, timeout=120) as res:
        if "text/csv" not in res.headers.get("Content-Type", ""):
            raise SystemExit(
                "The sheet asked for a login: export the ENCOUNTERS and STATS tabs as CSV and pass the files"
            )
        return res.read().decode("utf-8")


def main() -> None:
    """Read the tabs, write EncounterDB.json, list the locations to check by eye"""
    if len(sys.argv) > 2:
        encounters = Path(sys.argv[1]).read_text(encoding="utf-8")
        stats = Path(sys.argv[2]).read_text(encoding="utf-8")
    else:
        encounters, stats = _download(ENCOUNTERS_GID), _download(STATS_GID)
    known_species = json.loads((HERE / "PkDB.json").read_text(encoding="utf-8"))
    database = parse_encounters(encounters, known_species)
    database["evolution_lines"] = parse_evolution_lines(stats, known_species)
    ENCOUNTER_DB.write_text(db_text(database), encoding="ascii")
    print(f"{len(database['locations'])} locations: {', '.join(database['locations'])}")
    print(f"{len(database['evolution_lines'])} evolution lines")


if __name__ == "__main__":
    main()
