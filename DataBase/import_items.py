"""
Write ItemLocationDB.json from the Renegade Platinum documentation sheet's iTEMS/TMs tab: where each hold
item, evolution item, TM and HM is picked up, by location in story order. The Tracker's Items tab reads it.

The tab is a free-form grid of side-by-side tables, found by their header cells: an item table is an
"Item" cell with "Locations" two to its right, a TM table a "TM" cell with "Type" next to it. Of the key
items only the rods are kept (KEY_ITEMS). The plates are left out, they only come after the Champion (from
Master Trainers or the Underground) when a Nuzlocke is over, and so are the notes on changed items. A place
is one
of the Tracker's locations, so the order and the gift and trade Pokemon come from EncounterDB.json (run
DataBase.import_encounters first), plus the places with nothing to catch (PLACED_AFTER). Text it doesn't
know raises, so a change in the sheet's layout fails here instead of writing bad data.

Usage: python -m DataBase.import_items [items.csv]
Without a file it downloads the tab, export it by hand if the sheet asks for a login.
"""
import csv
import io
import json
import re
import sys
import urllib.request
from pathlib import Path

from DataBase.import_learnsets import SHEET_ID

HERE = Path(__file__).resolve().parent
ENCOUNTER_DB = HERE / "EncounterDB.json"
ITEM_LOCATION_DB = HERE / "ItemLocationDB.json"
ITEMS_GID = "1939055360"

ITEM_HEADER, LOCATIONS_HEADER = "Item", "Locations"
TM_HEADER, TYPE_HEADER = "TM", "Type"
ITEM_TABLES, TM_TABLES = 5, 3
TM_COUNT = 100  # TM01-92 and HM01-08
KINDS = ("item", "key", "tm")  # the order they're listed in at a location
# The key items the Tracker reads: each unlocks the encounter tables of its method. The rest are left out
KEY_ITEMS = ("Old Rod", "Good Rod", "Super Rod")
KEY_LOCATION_HEADER = "Location"
TYPES = (
    "Normal", "Fighting", "Flying", "Poison", "Ground", "Rock", "Bug", "Ghost", "Steel", "Fire",
    "Water", "Grass", "Electric", "Psychic", "Ice", "Dragon", "Dark", "Fairy",
)

# Places with items but nothing to catch, missing from EncounterDB, each go right after the location named.
# Veilstone City is there, but last: the sheet's encounter tab lists it among the legendaries
PLACED_AFTER = {
    "Hearthome City": "Route 208",
    "Solaceon Town": "Route 209",
    "Veilstone City": "Route 215",
    "Snowpoint City": "Acuity Lakefront",
    "Galactic HQ": "Lake Acuity",
    "Fight Area": "Flower Paradise",
}
# Sheet place -> (location, area, how). The rest are a location as written, an area or a note in parentheses
PLACE_ALIAS = {
    "Jubilife City (Trainer School)": ("Trainers' School", "", ""),
    "Route 204 North": ("Route 204", "North", ""),
    "Eterna Forest Outside": ("Eterna Forest", "Outside", ""),
    "Eterna Galactic Building": ("T.G. Eterna Bldg", "", ""),
    "Eterna Galactic Bldg": ("T.G. Eterna Bldg", "", ""),
    "Galactic Eterna Building": ("T.G. Eterna Bldg", "", ""),
    "Lost Tower": ("Route 209", "Lost Tower", ""),  # the Tracker's Lost Tower too ([pp] header.json)
    "Amity Square": ("Hearthome City", "Amity Square", ""),
    "Hotel Grand Lake (Route 213)": ("Route 213", "Hotel Grand Lake", ""),
    "Game Corner": ("Veilstone City", "Game Corner", ""),
    "Veilstone Game Corner Prize": ("Veilstone City", "Game Corner", "Prize"),
    "Veilstone Dept. Store": ("Veilstone City", "Dept. Store", ""),
    "Veilstone City Dept. Store": ("Veilstone City", "Dept. Store", ""),
    "Galactic Warehouse": ("Veilstone City", "Galactic Warehouse", ""),
    "Veilstone Galactic HQ": ("Galactic HQ", "", ""),
}
# "Oreburgh Gym" -> Oreburgh City, area Gym
GYM_RE = re.compile(r"(\S+) Gym")
# Parenthesised text that says how an item is found. AREAS are a part of the place instead
NOTES = {
    "Hidden": "Hidden",
    "Buyable": "Buyable",
    "from NPC at Morning": "From an NPC in the morning",
    "Gift from Bike Shop Owner": "Gift from the Bike Shop owner",
    "NPC in Pokémon Center": "From an NPC in the Pokémon Center",
}
AREAS = {"North", "South", "East", "West", "Route 211 entrance", "Moss Rock", "Ice Rock"}
# "Pastoria City, attached to Squirtle, Totodile and Mudkip gifts": one pickup where each one is given
GIFTS_RE = re.compile(r",?\s*attached to (.+?) gifts")
TRADE_RE = re.compile(r"Trade for (\S+) in (\S+)")
TM_RE = re.compile(r"((?:TM|HM)\d{2}) (.+)")
# Sheet name -> ItemDB's, for the hold items ItemDB spells the later way
ITEM_ALIAS = {
    "SilverPowder": "Silver Powder",
    "NeverMeltIce": "Never-Melt Ice",
    "TwistedSpoon": "Twisted Spoon",
    "BlackGlasses": "Black Glasses",
    "DeepSeaTooth": "Deep Sea Tooth",
    "DeepSeaScale": "Deep Sea Scale",
}


def clean(text: str) -> str:
    """A cell without invisible Unicode (U+180E and others) or doubled spaces. Unlike import_learnsets'
    clean_text it keeps the accents: the places are shown as written ("Pokémon Mansion")"""
    text = "".join(ch for ch in text.replace("’", "'") if ch.isprintable())
    return " ".join(text.split())


def location_order(encounter_locations) -> list:
    """The Tracker's locations in story order, with PLACED_AFTER's places put in"""
    order = [name for name in encounter_locations if name not in PLACED_AFTER]
    for place, after in PLACED_AFTER.items():
        if after not in order:
            raise ValueError(f"{after!r} isn't a location, it can't place {place!r}")
        order.insert(order.index(after) + 1, place)
    return order


def _gives(encounter_locations: dict, method: str, species: str, cell: str) -> str:
    """The location whose `method` table ('Gift', 'Trade') has the species"""
    found = [
        name for name, tables in encounter_locations.items()
        for table in tables
        if table["method"].startswith(method) and any(mon["name"] == species for mon in table["mons"])
    ]
    if len(found) != 1:
        raise ValueError(f"{method} of {species} in {cell!r}: EncounterDB has it at {found or 'no location'}")
    return found[0]


def _place(text: str, order: list) -> tuple:
    """(location, area, how) of one place: 'Route 210 (North) (Hidden)' -> ('Route 210', 'North', 'Hidden')"""
    if text in PLACE_ALIAS:
        return PLACE_ALIAS[text]
    base, notes = text, []
    while match := re.fullmatch(r"(.*?)\s*\(([^()]*)\)", base):
        base, notes = match[1], [match[2], *notes]
    gym = GYM_RE.fullmatch(base)
    location, area, how = PLACE_ALIAS.get(base) or (gym and (f"{gym[1]} City", "Gym", "")) or (base, "", "")
    if location not in order:
        raise ValueError(f"Unknown place {text!r}")
    areas, hows = [area] if area else [], [how] if how else []
    for note in notes:
        if note in NOTES:
            hows.append(NOTES[note])
        elif note in AREAS:
            areas.append(note)
        else:
            raise ValueError(f"Unknown note ({note}) in {text!r}")
    return location, " · ".join(areas), " · ".join(hows)


def _item_places(cell: str, order: list, encounter_locations: dict) -> list:
    """[(location, area, how)] of an item table's Locations cell"""
    places = []
    gifts = GIFTS_RE.search(cell)
    if gifts:
        cell = cell[:gifts.start()] + cell[gifts.end():]
        for species in re.split(r",\s*|\s+and\s+", gifts[1]):
            location = _gives(encounter_locations, "Gift", species, cell)
            places.append((location, "", f"Held by the gift {species}"))
    for text in (part.strip() for part in cell.split(",")):
        if not text:
            continue
        trade = TRADE_RE.fullmatch(text)
        if trade:
            location = _gives(encounter_locations, "Trade", trade[1], text)
            if not location.startswith(trade[2]):
                raise ValueError(f"{text!r}: EncounterDB has the trade at {location}")
            places.append((location, "", f"Held by the traded {trade[1]}"))
        else:
            places.append(_place(text, order))
    return places


def _cell(rows: list, row: int, col: int) -> str:
    return clean(rows[row][col]) if row < len(rows) and col < len(rows[row]) else ""


def _headers(rows: list, first: str, offset: int, second: str) -> list:
    """(row, col) of every `first` cell with `second` `offset` columns to its right"""
    return [
        (r, c) for r, row in enumerate(rows) for c in range(len(row))
        if _cell(rows, r, c) == first and _cell(rows, r, c + offset) == second
    ]


def _pickup(location: str, area: str, how: str, item: str, kind: str, **extra) -> tuple:
    """(location, the pickup's entry). The id is what the run keeps, so it's the same on every import"""
    entry = {"id": "|".join((location, area, item, how)), "item": item, "kind": kind}
    return location, {**entry, "area": area, "how": how, **extra}


def _read_items(rows: list, order: list, encounter_locations: dict) -> list:
    """Every hold and evolution item pickup. A table ends at a heading in its first column (the plates')"""
    headers = _headers(rows, ITEM_HEADER, 2, LOCATIONS_HEADER)
    if len(headers) != ITEM_TABLES:
        raise ValueError(f"{len(headers)} item tables, expected {ITEM_TABLES}: the sheet's layout changed")
    pickups = []
    for top, col in sorted(headers, key=lambda h: h[1]):
        for r in range(top + 1, len(rows)):
            if _cell(rows, r, col):
                break
            item, places = _cell(rows, r, col + 1), _cell(rows, r, col + 2)
            if bool(item) != bool(places):
                raise ValueError(f"Row {r + 1}: an item without places or places without an item")
            if item:
                item = ITEM_ALIAS.get(item, item)
                for place in _item_places(places, order, encounter_locations):
                    pickups.append(_pickup(*place, item, "item"))
    return pickups


def _read_tms(rows: list, order: list) -> list:
    """Every TM and HM: TM, Type, BP, ACC, PP, Location, Obtained"""
    headers = _headers(rows, TM_HEADER, 1, TYPE_HEADER)
    if len(headers) != TM_TABLES:
        raise ValueError(f"{len(headers)} TM tables, expected {TM_TABLES}: the sheet's layout changed")
    pickups = []
    for top, col in sorted(headers, key=lambda h: h[1]):
        for r in range(top + 1, len(rows)):
            name = _cell(rows, r, col)
            if not name:
                continue
            match = TM_RE.fullmatch(name)
            move_type, place, how = _cell(rows, r, col + 1), _cell(rows, r, col + 5), _cell(rows, r, col + 6)
            if not match or move_type not in TYPES or not place or not how:
                raise ValueError(f"Row {r + 1}: {name!r} isn't a TM row")
            location, area, note = _place(place, order)
            how = " · ".join(filter(None, (how, note)))
            pickups.append(_pickup(location, area, how, match[1], "tm", move=match[2], type=move_type))
    if len(pickups) != TM_COUNT:
        raise ValueError(f"{len(pickups)} TMs and HMs, expected {TM_COUNT}")
    return pickups


def _read_key_items(rows: list, order: list) -> list:
    """KEY_ITEMS from the key item tables: an "Item" cell with "Location" two to its right, the item under
    the cell after it. How it's given is the next cell that isn't the sheet's * mark"""
    pickups = []
    for top, col in _headers(rows, ITEM_HEADER, 2, KEY_LOCATION_HEADER):
        for r in range(top + 1, len(rows)):
            item = _cell(rows, r, col + 1)
            if item not in KEY_ITEMS:
                continue
            how = next((c for c in (_cell(rows, r, col + i) for i in range(3, 6)) if c and "*" not in c), "")
            pickups.append(_pickup(*_place(_cell(rows, r, col + 2), order)[:2], how, item, "key"))
    found = sorted(entry["item"] for _, entry in pickups)
    if found != sorted(KEY_ITEMS):
        raise ValueError(f"Key items found: {found}, expected each of {KEY_ITEMS} once")
    return pickups


def parse_items(text: str, encounter_locations: dict) -> dict:
    """{"locations": {location: [{"id", "item", "kind", "area", "how", ("move", "type" for a TM)}]}} from the
    tab's CSV. Locations in story order, only the ones with something to pick up; at each, items, then key
    items, then TMs and HMs, each in the sheet's order"""
    rows = list(csv.reader(io.StringIO(text)))
    order = location_order(encounter_locations)
    pickups = (
        _read_items(rows, order, encounter_locations) + _read_key_items(rows, order) + _read_tms(rows, order)
    )
    ids = [entry["id"] for _, entry in pickups]
    repeated = sorted({i for i in ids if ids.count(i) > 1})
    if repeated:
        raise ValueError(f"The same pickup twice: {repeated}")
    by_location = {name: [] for name in order}
    for location, entry in sorted(pickups, key=lambda p: KINDS.index(p[1]["kind"])):
        by_location[location].append(entry)
    return {"locations": {name: entries for name, entries in by_location.items() if entries}}


def db_text(database: dict) -> str:
    """The file's text, one pickup per row so a new import's diff shows what changed"""
    blocks = []
    for name, entries in database["locations"].items():
        rows = ",\n".join(f"      {json.dumps(entry)}" for entry in entries)
        blocks.append(f"    {json.dumps(name)}: [\n{rows}\n    ]")
    locations = ",\n".join(blocks)
    return f'{{\n  "locations": {{\n{locations}\n  }}\n}}\n'


def _download() -> str:
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={ITEMS_GID}"
    with urllib.request.urlopen(url, timeout=120) as res:
        if "text/csv" not in res.headers.get("Content-Type", ""):
            raise SystemExit("The sheet asked for a login: export the iTEMS/TMs tab as CSV and pass the file")
        return res.read().decode("utf-8")


def main() -> None:
    """Read the tab, write ItemLocationDB.json, list the counts to check by eye"""
    text = Path(sys.argv[1]).read_text(encoding="utf-8") if len(sys.argv) > 1 else _download()
    encounter_locations = json.loads(ENCOUNTER_DB.read_text(encoding="utf-8"))["locations"]
    database = parse_items(text, encounter_locations)
    ITEM_LOCATION_DB.write_text(db_text(database), encoding="ascii")
    entries = [entry for entries in database["locations"].values() for entry in entries]
    counts = ", ".join(f"{sum(e['kind'] == kind for e in entries)} {kind}s" for kind in KINDS)
    print(f"{len(entries)} pickups ({counts}) at {len(database['locations'])} locations")


if __name__ == "__main__":
    main()
