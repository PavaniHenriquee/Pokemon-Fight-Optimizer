"""
Write TrainerDB.json from the Renegade Platinum documentation sheet: every singles fight from the Roark split
to the Champion, in story order, with the split it's first met in. The source is the nine split tabs (ROARK
SPLiT to CHAMPiON SPLiT) and the Pokemon Center fights on the NPC/TRADES tab.

The sheet is read as xlsx because a Pokemon's gender is a formula (=MALE(), =FEMALE(), =ASEXUAL()) next
to its name, and a CSV export drops formula cells. A team is found by its "HP Atk Def" label row: the name,
gender and level are two rows above it, then item and ability, nature and IVs, and the moves below. The
trainer headers ("YOUNGSTER DARIUS [245]") at its left own it, Lucas and Dawn share one team (Dawn's nature
is in a note). Double and multi battles are skipped and listed, and so are the Pokemon Center teams that
come after the Champion.

Checks against [pp] (pret/pokeplatinum src/trainer_data.c): a trainer Pokemon's personality comes from its
ivScale, level, species and the trainer's id, through the LCRNG run once per trainer class index, so the
sheet's nature has to come out of it for some ivScale that gives the sheet's IV. That also picks the class
where the sheet's name fits several (Galactic Grunt, School Kid, Swimmer), and fills a nature or IV the
sheet leaves out when only one value fits. The personality's low byte is 120 for a female class and 136 for
a male one, which gives the gender from the species' ratio ([SD] pokedex.ts). The sheet's mark only decides
where the trainer's gender does (a 50% species) and the species can have it. The run lists every nature
that doesn't fit, every gap filled and every mark not taken.

Usage: python -m DataBase.import_trainers [workbook.xlsx]
Without a file it downloads the workbook (File > Download > xlsx if the sheet asks for a login). It always
downloads [pp]'s trainer class tables and [SD]'s pokedex.
"""
import io
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from DataBase.import_encounters import ENCOUNTER_SPECIES_ALIAS
from DataBase.import_learnsets import SHEET_ID, clean_text, move_key, species_name

HERE = Path(__file__).resolve().parent
TRAINER_DB = HERE / "TrainerDB.json"
WORKBOOK_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx"
PP_RAW = "https://raw.githubusercontent.com/pret/pokeplatinum/main"
PP_CLASS_NAMES = f"{PP_RAW}/res/text/trainer_class_names.json"
PP_CLASSES = f"{PP_RAW}/generated/trainer_classes.txt"
PP_CLASS_GENDERS = f"{PP_RAW}/include/data/trainer_class_genders.h"
SD_POKEDEX = "https://raw.githubusercontent.com/smogon/pokemon-showdown/master/data/pokedex.ts"

# (split, tab), in story order. The tab names are the xlsx's, some end in a space there
SPLITS = (
    ("Roark", "ROARK SPLiT"),
    ("Gardenia", "GARDENiA SPLiT"),
    ("Fantina", "FANTINA SPLiT"),
    ("Maylene", "MAYLENE SPLiT"),
    ("Wake", "WAKE SPLiT"),
    ("Byron", "BYRON SPLiT"),
    ("Candice", "CANDICE SPLiT"),
    ("Volkner", "VOLKNER SPLiT"),
    ("Champion", "CHAMPiON SPLiT"),
)
CENTER_TAB = "NPCTRADES"
# Pokemon Center teams by the tier note under the trainer's name, None: after the Champion, skipped
CENTER_TIERS = {
    "": "Roark",
    "(TEAM AFTER 3 BADGES)": "Maylene",
    "(TEAM AFTER 5 BADGES)": "Byron",
    "(TEAM AFTER 8 BADGES)": "Champion",
    "(TEAM AFTER CYNTHIA)": None,
    "(TEAM AFTER STARK MOUNTAIN)": None,
}

# A team block, from its "HP" label cell at (row, col)
NAME_ROW, NAME_COL = -2, 1
GENDER_COL, LEVEL_COL = 5, 6
ITEM_ROW, ITEM_COL, ABILITY_COL = 2, 1, 4
NATURE_ROW, IV_COL = 3, 6
MOVES_ROW = 4
BLOCK_WIDTH = 8
# How far above its label row a trainer header can be (Lucas's is on the name row), and how far below it the
# notes in the header's column go (Roark's second trainer item is on the last move row)
HEADER_ABOVE = 3
HEADER_BELOW = 1  # the Interviewers'
NOTES_BELOW = 8
# The most rows a team's second row of blocks can be under its first
CONTINUATION_ROWS = 13
TEMPLATE_NAME = "#000 Pokemon"
NO_ITEM = "No Item"
# A nature or IV cell the sheet left as its template's text, filled from the personality (_fill_gaps)
NATURE_PLACEHOLDER, IV_PLACEHOLDER = "Nature", "IV"

# Sheet name -> PkDB name, on top of import_encounters' ENCOUNTER_SPECIES_ALIAS
TRAINER_SPECIES_ALIAS = {
    "Wormadam (S)": "Wormadam_sandy",
    "Wormadam (T)": "Wormadam_trash",
}
GENDER_MARKS = {"MALE()": "Male", "FEMALE()": "Female", "ASEXUAL()": None}
NATURES = (
    "Hardy", "Lonely", "Brave", "Adamant", "Naughty", "Bold", "Docile", "Relaxed", "Impish", "Lax",
    "Timid", "Hasty", "Serious", "Jolly", "Naive", "Modest", "Mild", "Quiet", "Bashful", "Rash",
    "Calm", "Gentle", "Sassy", "Careful", "Quirky",
)
STATS = ("HP", "Attack", "Defense", "Special Attack", "Special Defense", "Speed")
STARTERS = ("Turtwig", "Chimchar", "Piplup")
# A rival fight's variants get a letter by their order in the sheet, which is P, T, C for every one so far
VARIANT_LETTERS = "PTC"
RIVALS = ("BARRY", "LUCAS", "DAWN")
# The player characters' [pp] classes, when they're the rival. Barry is TRAINER_CLASS_RIVAL
PLAYER_CLASSES = {"LUCAS": "PLAYER_MALE", "DAWN": "PLAYER_FEMALE"}
# The sheet's Lucas natures are a placeholder: Hasty on every Pokemon, which no class gives. His fights
# mirror Dawn's, whose natures fit PLAYER_FEMALE at one ivScale per fight (250 at IV 30, 255 at IV 31), so
# his natures and IVs come from PLAYER_MALE at that scale. Lucas 1: a Naughty Turtwig, Adamant Chimchar and
# Lax Piplup, as the game has them
MIRROR_RIVALS = {"LUCAS": "DAWN"}
# The note that numbers each team a trainer picks at random when the fight starts (Elite Four, Cynthia)
RANDOM_TEAM_RE = re.compile(r"(\d+)(?:\.0)?")

# Fixes to the sheet by trainer id, {block: fields}. Each one passes the personality check
SHEET_FIXES = {
    38: {2: {"iv": 24}},  # Battle Girl Helen's Hariyama: its nature fits IV 24, as its teammates' do
    340: {2: {"iv": 24}},  # School Kid Chance's second Duskull, the same
    372: {0: {"iv": 12, "nature": "Timid"}, 1: {"iv": 12, "nature": "Quiet"}},  # Battle Girl Tyler: blank
}
# A team whose blocks belong to different trainers, {trainer id: blocks}. Pokemon Mansion's "Master Liam [892]
# or Lady Celeste [893]" fight lists one Blissey each, Liam's is the first (Rash)
TEAM_BLOCKS = {892: (0,), 893: (1,)}
# [pp] class by trainer id where the personality can't tell and no gender depends on it: the sprite's
CLASS_FIXES = {494: "SWIMMER_FEMALE", 193: "SWIMMER_FEMALE"}  # Swimmers Claire and Cassandra

# Notes that make a fight a double or multi battle, or a partner's team. A trainer who "Can be fought alone or
# with ..." stays, whatever the rest says ("... but has to be fought" is cut short in the sheet)
DOUBLE_NOTES = re.compile(
    r"^\(?(DOUBLE|MULTI) BATTLE\)?$|Has to be fought in a double|Your partner|^Partner to|"
    r"initiate a double battle|Double battle against them|side of the double battle|"
    r"takes part in wild encounters|^Partner for"
)
ALONE_NOTE = re.compile(r"^Can be fought alone", re.I)
# [pp] classes that only fight double battles
DOUBLE_CLASSES = ("TWINS", "YOUNG_COUPLE", "DOUBLE_TEAM", "BELLE_AND_PA", "INTERVIEWERS", "SIS_AND_BRO")

# Sheet class -> [pp] class display name ("PKMN" is [pp]'s ₧₦), the rest are the same in capitals
CLASS_ALIAS = {
    "GYM LEADER": "LEADER",
    "RIVAL": "PKMN TRAINER",
    "GALACTIC GRUNT": "GALACTIC",
    "PICKNICKER": "PICNICKER",
    "POKÉKID": "POKÉ KID",
    "POKÉ FAN": "POKÉFAN",
    "YNG COUPLE": "YOUNG COUPLE",
    "MASTER": "RICH BOY",  # Pokemon Mansion's "great Master Liam" is Rich Boy Liam
}
# Sheet class -> the key's spelling, the rest are in title case
KEY_CLASS = {
    "GYM LEADER": "Gym Leader",
    "PICKNICKER": "Picnicker",
    "POKÉKID": "Poké Kid",
    "POKÉ FAN": "Pokéfan",
    "PI": "PI",
    "MASTER": "Rich Boy",
}
LEAGUE_PREFIX = "SINNOH POKEMON LEAGUE"
# A header: the class and name in capitals, then the trainer id
HEADER_RE = re.compile(r"\s*(?:" + LEAGUE_PREFIX + r"\s+)?([^a-z\[\]]+?)\s*\[(\d+)\]\s*")
# A header the sheet forgot the id of (JOGGER CRAIG), taken only where a team has no other
BARE_HEADER_RE = re.compile(r"\s*[A-Z][A-Z .'&-]+[A-Z]\s*")
IF_STARTER_RE = re.compile(r"\(IF YOU CHOSE (\w+)\)")
SHARED_PLAYER_RE = re.compile(r"(LUCAS|DAWN) if you play as a (girl|boy)")
IF_PLAYER_RE = re.compile(r"\(IF YOU PLAY AS A (GIRL|BOY)\)")
ITEMS_RE = re.compile(r"can use\s*:\s*(.*)", re.I)
# "1 SUPER POTION", "2 HYPER POTIONS", "X DEFEND" (one), "1 X SP. DEF"
ITEM_LINE_RE = re.compile(r"(?:(\d+)\s+)?([A-Z][A-Z .'-]*[A-Z])")
SHARED_NATURE_RE = re.compile(r"\((\w+)'s ([\w .'-]+?) is (\w+) \(")

# Sprite ([SD] play.pokemonshowdown.com/sprites/trainers) by [pp] class: the -gen4dp one where [SD] has it,
# then -gen4, then the plain one. [SD] calls the PI a gambler. Then by name for the player characters
CLASS_SPRITE = {
    "ACE_TRAINER_FEMALE": "acetrainerf-gen4dp",
    "ACE_TRAINER_MALE": "acetrainer-gen4dp",
    "ACE_TRAINER_SNOW_FEMALE": "acetrainersnowf",
    "ACE_TRAINER_SNOW_MALE": "acetrainersnow",
    "ARCADE_STAR": "dahlia",
    "AROMA_LADY": "aromalady",
    "ARTIST": "artist-gen4",
    "BATTLE_GIRL": "battlegirl-gen4",
    "BEAUTY": "beauty-gen4dp",
    "BIRD_KEEPER": "birdkeeper-gen4dp",
    "BLACK_BELT": "blackbelt-gen4dp",
    "BREEDER_FEMALE": "pokemonbreederf-gen4",
    "BREEDER_MALE": "pokemonbreeder-gen4",
    "BUG_CATCHER": "bugcatcher-gen4dp",
    "CAMERAMAN": "cameraman",
    "CAMPER": "camper",
    "CASTLE_VALET": "darach",
    "CHAMPION_CYNTHIA": "cynthia-gen4",
    "CLOWN": "clown",
    "COLLECTOR": "collector",
    "COMMANDER_JUPITER": "jupiter",
    "COMMANDER_MARS": "mars",
    "COMMANDER_SATURN": "saturn",
    "COWGIRL": "cowgirl",
    "CYCLIST_FEMALE": "cyclistf-gen4",
    "CYCLIST_MALE": "cyclist-gen4",
    "DRAGON_TAMER": "dragontamer",
    "ELITE_FOUR_AARON": "aaron",
    "ELITE_FOUR_BERTHA": "bertha",
    "ELITE_FOUR_FLINT": "flint",
    "ELITE_FOUR_LUCIAN": "lucian",
    "FISHERMAN": "fisherman-gen4",
    "GALACTIC_BOSS": "cyrus",
    "GALACTIC_GRUNT_FEMALE": "galacticgruntf",
    "GALACTIC_GRUNT_MALE": "galacticgrunt",
    "GENTLEMAN": "gentleman-gen4dp",
    "GUITARIST": "guitarist-gen4",
    "HIKER": "hiker-gen4",
    "IDOL": "idol",
    "JOGGER": "jogger",
    "LADY": "lady-gen4",
    "LASS": "lass-gen4dp",
    "LEADER_BYRON": "byron",
    "LEADER_CANDICE": "candice",
    "LEADER_FANTINA": "fantina",
    "LEADER_GARDENIA": "gardenia",
    "LEADER_MAYLENE": "maylene",
    "LEADER_ROARK": "roark",
    "LEADER_VOLKNER": "volkner",
    "LEADER_WAKE": "crasherwake",
    "MAID": "maid-gen4",
    "NINJA_BOY": "ninjaboy",
    "PARASOL_LADY": "parasollady-gen4",
    "PI": "gambler",
    "PICNICKER": "picnicker",
    "POKEFAN_FEMALE": "pokefanf-gen4",
    "POKEFAN_MALE": "pokefan-gen4",
    "POKE_KID": "pokekid",
    "POLICEMAN": "policeman-gen4",
    "PSYCHIC_FEMALE": "psychicf-gen4",
    "PSYCHIC_MALE": "psychic-gen4",
    "RANCHER": "rancher",
    "RANGER_FEMALE": "pokemonrangerf-gen4",
    "RANGER_MALE": "pokemonranger-gen4",
    "REPORTER": "reporter",
    "RICH_BOY": "richboy-gen4",
    "RIVAL": "barry",
    "ROUGHNECK": "roughneck-gen4",
    "RUIN_MANIAC": "ruinmaniac",
    "SAILOR": "sailor",
    "SCHOOL_KID_FEMALE": "schoolkidf-gen4",
    "SCHOOL_KID_MALE": "schoolkid-gen4dp",
    "SCIENTIST": "scientist-gen4dp",
    "SKIER_FEMALE": "skierf-gen4dp",
    "SKIER_MALE": "skier",
    "SOCIALITE": "madame-gen4dp",
    "SWIMMER_FEMALE": "swimmerf-gen4dp",
    "SWIMMER_MALE": "swimmer-gen4dp",
    "TRAINER_BUCK": "buck",
    "TRAINER_CHERYL": "cheryl",
    "TRAINER_MARLEY": "marley",
    "TRAINER_MIRA": "mira",
    "TRAINER_RILEY": "riley",
    "TUBER_FEMALE": "tuberf",
    "TUBER_MALE": "tuber",
    "VETERAN": "veteran-gen4",
    "WAITER": "waiter-gen4dp",
    "WAITRESS": "waitress-gen4",
    "WORKER": "worker-gen4",
    "YOUNGSTER": "youngster-gen4dp",
}
PLAYER_SPRITE = {"Lucas": "lucas-gen4pt", "Dawn": "dawn-gen4pt"}
# Battle terrain ([pp] TERRAIN_*, Models.helper.Terrain) by the sheet's location heading, read only for a
# trainer with a move that depends on it. [pp] CalcTerrain takes it from the tile the player stands on (tall
# grass, sand, snow, mud, cave floor, water) and else from the map's battleBackground (header.json, through
# sTerrainForBackground). These are the backgrounds; Route 223's trainers are met surfing
TERRAIN_MOVES = ("Nature Power", "Secret Power", "Camouflage")
LOCATION_TERRAIN = {
    "OREBURGH GATE": "cave",
    "ROUTE 208": "mountain",
    "ROUTE 212 ~ SOUTH": "plain",
    "ROUTE 214": "mountain",
    "ROUTE 216": "snow",
    "LAKE VERITY": "grass",
    "ROUTE 223": "water",
}
CENTER_TERRAIN = "building"

M_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"


# ─── Workbook ─────────────────────────────────────────────────────────────────────────────────────────


def _cell_ref(ref: str) -> tuple:
    """'AB12' -> (11, 27), 0-based (row, col)"""
    letters = re.match(r"[A-Z]+", ref)[0]
    col = 0
    for ch in letters:
        col = col * 26 + ord(ch) - 64
    return int(ref[len(letters):]) - 1, col - 1


def _string_item(si) -> str:
    """A shared string's text: its runs, without phonetic hints"""
    return "".join(t.text or "" for t in si.findall(f"{M_NS}t") + si.findall(f"{M_NS}r/{M_NS}t"))


def read_workbook(data: bytes, tabs) -> dict:
    """{tab: (values, formulas)}, both {(row, col): text}. Tabs are found by name, trailing spaces ignored"""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = z.namelist()
        shared = []
        if "xl/sharedStrings.xml" in names:
            shared = [_string_item(si) for si in ET.fromstring(z.read("xl/sharedStrings.xml"))]
        rels = {
            rel.get("Id"): rel.get("Target")
            for rel in ET.fromstring(z.read("xl/_rels/workbook.xml.rels")).iter(f"{PKG_NS}Relationship")
        }
        sheets = {
            sheet.get("name").strip(): rels[sheet.get(f"{R_NS}id")]
            for sheet in ET.fromstring(z.read("xl/workbook.xml")).iter(f"{M_NS}sheet")
        }
        out = {}
        for tab in tabs:
            if tab.strip() not in sheets:
                raise ValueError(f"No tab {tab!r} in the workbook: {sorted(sheets)}")
            target = sheets[tab.strip()].lstrip("/").removeprefix("xl/")
            values, formulas = {}, {}
            for cell in ET.fromstring(z.read(f"xl/{target}")).iter(f"{M_NS}c"):
                pos = _cell_ref(cell.get("r"))
                formula, value = cell.find(f"{M_NS}f"), cell.find(f"{M_NS}v")
                if formula is not None and formula.text:
                    formulas[pos] = formula.text
                if cell.get("t") == "inlineStr":
                    values[pos] = _string_item(cell.find(f"{M_NS}is"))
                elif value is not None and value.text is not None:
                    values[pos] = shared[int(value.text)] if cell.get("t") == "s" else value.text
            out[tab] = (values, formulas)
        return out


# ─── Reference data ([pp] classes, [SD] gender ratios) ────────────────────────────────────────────────


def parse_classes(names_json: str, classes_txt: str, genders_h: str) -> list:
    """[(index, constant, display name in capitals, female)] for every [pp] trainer class"""
    names = [m["en_US"] for m in json.loads(names_json)["messages"]]
    constants = classes_txt.split()
    genders = dict(re.findall(r"\[TRAINER_CLASS_(\w+)\]\s*=\s*GENDER_(\w+)", genders_h))
    if len(names) != len(constants):
        raise ValueError(f"{len(names)} class names for {len(constants)} classes")
    out = []
    for index, (name, constant) in enumerate(zip(names, constants)):
        constant = constant.removeprefix("TRAINER_CLASS_")
        display = name.replace("₧₦", "PKMN").replace("♂", "").replace("♀", "").upper()
        out.append((index, constant, display, genders.get(constant) == "FEMALE"))
    return out


def _dex_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def parse_gender_ratios(pokedex_ts: str) -> dict:
    """{species key: [pp] gender ratio}: 0 male only, 254 female only, 255 genderless, else the female
    threshold the personality's low byte is compared with (31 for 87.5% male)"""
    ratios = {}
    for match in re.finditer(r"\n\t(\w+): \{(.*?)\n\t\}", pokedex_ts, re.S):
        species_id, body = match[1], match[2]
        gender = re.search(r'\bgender: "(\w)"', body)
        ratio = re.search(r"\bgenderRatio: \{\s*M: ([\d.]+),\s*F: ([\d.]+)\s*\}", body)
        if gender:
            value = {"M": 0, "F": 254, "N": 255}[gender[1]]
        elif ratio:
            value = round(float(ratio[2]) * 256) - 1
        else:
            value = 127
        ratios[species_id] = value
    return ratios


def pp_gender(ratio: int, female_class: bool):
    """[pp] SpeciesData_GetGenderOf on a trainer Pokemon's personality, whose low byte is 120 or 136"""
    if ratio == 0:
        return "Male"
    if ratio == 254:
        return "Female"
    if ratio == 255:
        return None
    return "Female" if ratio > (120 if female_class else 136) else "Male"


def _possible_genders(ratio: int) -> tuple:
    return {0: ("Male",), 254: ("Female",), 255: (None,)}.get(ratio, ("Male", "Female"))


def personality_nature(iv_scale: int, level: int, dex: int, trainer_id: int, class_index: int, female) -> str:
    """[pp] TrainerData_BuildParty's personality for one Pokemon, as a nature"""
    seed = (iv_scale + level + dex + trainer_id) & 0xFFFFFFFF
    rnd = seed
    for _ in range(class_index):
        seed = (seed * 0x41C64E6D + 0x6073) & 0xFFFFFFFF
        rnd = seed >> 16
    personality = ((rnd << 8) + (120 if female else 136)) & 0xFFFFFFFF
    return NATURES[personality % 25]


def _iv_scales(iv: int) -> range:
    """The ivScale values [pp] turns into this IV (ivScale * 31 / 255)"""
    return range(-(-iv * 255 // 31), min(256, -(-(iv + 1) * 255 // 31)))


# ─── Sheet ────────────────────────────────────────────────────────────────────────────────────────────


def _text(values: dict, row: int, col: int) -> str:
    return values.get((row, col), "")


def _block_cols(values: dict, row: int, col: int):
    """Columns of the team blocks whose label row is `row`, from the first one at `col` rightwards"""
    while _text(values, row, col) == "HP" and _text(values, row, col + 1) == "Atk":
        yield col
        col += BLOCK_WIDTH


def _label_rows(values: dict) -> list:
    """(row, col) of every first block of a team: an HP label with nothing like it 8 columns to its left"""
    labels = [
        pos for pos, text in values.items()
        if text == "HP" and values.get((pos[0], pos[1] + 1)) == "Atk"
        and values.get((pos[0], pos[1] + 2)) == "Def"
    ]
    starts = []
    for row, col in labels:
        if _text(values, row, col - BLOCK_WIDTH) == "HP":
            continue
        if _text(values, row + NAME_ROW, col + NAME_COL) == TEMPLATE_NAME:
            continue
        starts.append((row, col))
    return sorted(starts)


def _species(header: str) -> str:
    """'#413 Wormadam (P)' -> 'Wormadam', the encounter tabs' aliases on top of the DEX tab's"""
    name = species_name(header)
    return TRAINER_SPECIES_ALIAS.get(name, ENCOUNTER_SPECIES_ALIAS.get(name, name))


def _int(text: str, pattern: str, what: str) -> int:
    match = re.fullmatch(pattern, clean_text(text))
    if not match:
        raise ValueError(f"Not a {what}: {text!r}")
    return int(match[1])


def _iv(text: str):
    """'30 IV' -> 30, None when the sheet left it out (an empty cell or its template's 'IV')"""
    if clean_text(text) in ("", IV_PLACEHOLDER):
        return None
    return _int(text, r"(\d+) IV", "IV")


def _pokemon(values: dict, formulas: dict, row: int, col: int) -> dict:
    """One block, as the sheet writes it"""
    header = _text(values, row + NAME_ROW, col + NAME_COL)
    dex = _int(header, r"#(\d{3}) .+", "species")
    nature = clean_text(_text(values, row + NATURE_ROW, col)).split(" ", maxsplit=1)[0]
    if nature in ("", NATURE_PLACEHOLDER):
        nature = None
    elif nature not in NATURES:
        raise ValueError(f"{header}: unknown nature {_text(values, row + NATURE_ROW, col)!r}")
    item = clean_text(_text(values, row + ITEM_ROW, col + ITEM_COL))
    ability = clean_text(_text(values, row + ITEM_ROW, col + ABILITY_COL))
    if not ability:
        raise ValueError(f"{header} at row {row + 1} has no ability")
    moves = [clean_text(_text(values, row + MOVES_ROW + i, col)) for i in range(4)]
    moves = [move if move not in ("-", "--") else "" for move in moves]
    if not any(moves):
        raise ValueError(f"{header} at row {row + 1} has no moves")
    return {
        "dex": dex,
        "name": _species(header),
        "mark": formulas.get((row + NAME_ROW, col + GENDER_COL), ""),
        "level": _int(_text(values, row + NAME_ROW, col + LEVEL_COL), r"Lv\. ?(\d+)", "level"),
        "item": item if item != NO_ITEM else "",
        "ability": ability,
        "nature": nature,
        "iv": _iv(_text(values, row + NATURE_ROW, col + IV_COL)),
        "moves": moves,
    }


def _headers(values: dict) -> list:
    """(row, col, class and name, id) of every trainer header"""
    out = []
    for (row, col), text in values.items():
        match = HEADER_RE.fullmatch(text)
        if match and re.search(r"[A-Z]{2}", match[1]):
            out.append((row, col, " ".join(match[1].upper().split()), int(match[2])))
    return sorted(out)


def _owners(values: dict, headers: list, row: int, col: int) -> list:
    """The headers at the left of a team's first block: the nearest column of them a few rows up"""
    rows = range(row - HEADER_ABOVE, row + HEADER_BELOW + 1)
    left = [h for h in headers if h[0] in rows and h[1] < col]
    if not left:
        left = [
            (r, c, " ".join(text.split()), None) for (r, c), text in values.items()
            if r in rows and c < col and BARE_HEADER_RE.fullmatch(text)
        ]
    if not left:
        return []
    header_col = max(h[1] for h in left)
    return sorted(h for h in left if h[1] == header_col)


def read_teams(values: dict) -> list:
    """Every team on a tab in sheet order: {"row", "col", "header_col", "last", "headers": [(row, name,
    id)], "notes": [text], "blocks": [(row, col)], "shared_natures": {(trainer, species): nature}}. A block
    is read only for a trainer that's kept: a partner's team can have placeholders. A team with no header
    right under another one is the rest of it (Worker Jackson's third Pokemon)"""
    headers = _headers(values)
    teams, owned = [], set()
    for row, col in _label_rows(values):
        mine = _owners(values, headers, row, col)
        blocks = [(row, c) for c in _block_cols(values, row, col)]
        if not mine:
            above = teams[-1] if teams and teams[-1]["col"] == col else None
            if above is None or not 0 < row - above["blocks"][-1][0] <= CONTINUATION_ROWS:
                raise ValueError(f"The team at row {row + 1}, column {col + 1} has no trainer")
            above["blocks"] += blocks
            continue
        owned.update(mine)
        teams.append({
            "row": row,
            "col": col,
            "header_col": mine[0][1],
            "headers": [(h[0], h[2], h[3]) for h in mine],
            "blocks": blocks,
        })
    lost = [h for h in headers if h not in owned]
    if lost:
        raise ValueError(f"Trainers with no team: {[h[2] + ' [' + str(h[3]) + ']' for h in lost]}")
    for team in teams:
        below = [t["row"] for t in teams if t["col"] == team["col"] and t["row"] > team["row"]]
        team["last"] = min([team["blocks"][-1][0] + NOTES_BELOW] + [r - HEADER_ABOVE - 1 for r in below])
        header_cells = {(h[0], team["header_col"]) for h in team["headers"]}
        notes = [
            values[(r, c)] for r in range(team["row"] + NAME_ROW, team["last"] + 1)
            for c in range(team["header_col"], team["col"])
            if values.get((r, c), "").strip() and (r, c) not in header_cells
        ]
        team["notes"] = [" ".join(clean_text(n).split()) for n in notes]
        shared = {}
        right = max(c for _, c in team["blocks"]) + 2 * BLOCK_WIDTH
        for r in range(team["row"] + NAME_ROW, team["last"] + 1):
            for c in range(team["col"], right):
                match = SHARED_NATURE_RE.search(values.get((r, c), ""))
                if match:
                    shared[(match[1].upper(), _species(match[2]))] = match[3]
        team["shared_natures"] = shared
    return teams


def _locations(values: dict, teams: list) -> list:
    """(row, heading) of the location headings in the trainers' column: capitals outside every team's rows"""
    taken = {(r, t["header_col"]) for t in teams for r in range(t["row"] + NAME_ROW - 1, t["last"] + 1)}
    cols = {t["header_col"] for t in teams}
    out = []
    for (row, col), text in values.items():
        heading = " ".join(clean_text(text).split())
        if col in cols and (row, col) not in taken and re.fullmatch(r"[A-Z0-9 .'~-]{3,}", heading):
            out.append((row, heading))
    return sorted(out)


# ─── Trainers ─────────────────────────────────────────────────────────────────────────────────────────


def _split_class(header: str, classes: list) -> tuple:
    """'YOUNGSTER DARIUS' -> ('YOUNGSTER', 'DARIUS', [pp classes]), by the longest class name in front"""
    names = {display for _, _, display, _ in classes}
    words = header.split()
    for n in range(len(words), 0, -1):
        sheet_class = " ".join(words[:n])
        pp_name = CLASS_ALIAS.get(sheet_class, sheet_class)
        if pp_name in names:
            name = " ".join(words[n:])
            if sheet_class == "RIVAL":
                found = [c for c in classes if c[1] == "RIVAL"]
            elif sheet_class == "PKMN TRAINER" and name in PLAYER_CLASSES:
                found = [c for c in classes if c[1] == PLAYER_CLASSES[name]]
            else:
                found = [c for c in classes if c[2] == pp_name]
                own = [c for c in found if name and c[1].endswith("_" + name.replace(" ", "_"))]
                found = own or found
            return sheet_class, " ".join(words[n:]), found
    raise ValueError(f"Unknown trainer class: {header!r}")


def _key_name(sheet_class: str, name: str) -> str:
    """The key without its number: 'Youngster Darius', 'Barry' for a rival"""
    if name in RIVALS and sheet_class in ("RIVAL", "PKMN TRAINER"):
        return name.title()
    words = [KEY_CLASS.get(sheet_class, sheet_class.title()), name.title()]
    text = " ".join(w for w in words if w)
    return text.replace("Pkmn ", "PKMN ")


def _scales(p: dict, trainer_id: int, cls: tuple) -> set:
    """The ivScales whose personality gives this Pokemon its nature, within its IV when the sheet has one"""
    allowed = _iv_scales(p["iv"]) if p["iv"] is not None else range(256)
    return {
        scale for scale in allowed
        if personality_nature(scale, p["level"], p["dex"], trainer_id, cls[0], cls[3]) == p["nature"]
    }


def _check_class(trainer_id: int, team: list, candidates: list) -> list:
    """The [pp] classes (index, constant, display, female) whose personality gives every sheet nature"""
    known = [p for p in team if p["nature"] is not None]
    return [cls for cls in candidates if all(_scales(p, trainer_id, cls) for p in known)]


def _fill_gaps(trainer_id: int, cls: tuple, team: list, label: str):
    """Natures and IVs the sheet left out, from the ivScales every Pokemon with a nature fits. The lines to
    report, None when one of them isn't a single value"""
    known = [p for p in team if p["nature"] is not None]
    if not known:
        return None
    scales = set.intersection(*(_scales(p, trainer_id, cls) for p in known))
    filled = []
    for p in team:
        allowed = [s for s in scales if p["iv"] is None or s in _iv_scales(p["iv"])]
        if p["iv"] is None:
            ivs = {scale * 31 // 255 for scale in allowed}
            if len(ivs) != 1:
                return None
            p["iv"] = ivs.pop()
            filled.append(f"{label} {p['name']}: no IV in the sheet, took {p['iv']}")
        if p["nature"] is None:
            natures = {
                personality_nature(s, p["level"], p["dex"], trainer_id, cls[0], cls[3]) for s in allowed
            }
            if len(natures) != 1:
                return None
            p["nature"] = natures.pop()
            filled.append(f"{label} {p['name']}: no nature in the sheet, took {p['nature']}")
    return filled


def _ratio(ratios: dict, species: str) -> int:
    return ratios[_dex_key(species)]


def _by_gender_marks(fits: list, team: list, ratios: dict, label: str, report: dict) -> list:
    """The classes of the gender whose [pp] genders agree with more of the sheet's marks, when the natures
    fit classes of both genders (a team of one or two can). The male ones when no gender depends on it"""
    def agree(female):
        marks = [GENDER_MARKS.get(p["mark"], "missing") for p in team]
        return sum(pp_gender(_ratio(ratios, p["name"]), female) == m for p, m in zip(team, marks))
    male, female = agree(False), agree(True)
    if male == female:
        if any(pp_gender(_ratio(ratios, p["name"]), False) != pp_gender(_ratio(ratios, p["name"]), True)
               for p in team):
            raise ValueError(f"{label}: classes of both genders fit, {[c[1] for c in fits]}")
        report["class_gender"].append(f"{label}: {[c[1] for c in fits]} fit, no gender depends on it")
    return [c for c in fits if c[3] == (female > male)]


def _speller(databases: dict, unknown: set):
    """spell(kind, text): sheet text -> the databases' spelling. What they don't have yet stays as the sheet
    writes it and goes in `unknown`"""
    tables = {kind: {move_key(n): n for n in databases[kind]} for kind in ("moves", "items", "abilities")}

    def spell(kind: str, text: str) -> str:
        if not text:
            return text
        found = tables[kind].get(move_key(text))
        if found is None:
            unknown.add(f"{kind}: {text}")
            return text
        return found
    return spell


def _trainer_split(split: str, center: bool, notes: list, label: str):
    """The split a fight belongs to, None for a Pokemon Center team after the Champion"""
    if not center:
        return split
    tier = next((n for n in notes if n.startswith("(TEAM AFTER")), "")
    if tier not in CENTER_TIERS:
        raise ValueError(f"{label}: unknown Pokemon Center tier {tier!r}")
    return CENTER_TIERS[tier]


def _read_pokemon(values: dict, formulas: dict, team: dict, header: tuple, report: dict) -> list:
    """The trainer's blocks of the team, with the nature a shared team's note gives it, and SHEET_FIXES"""
    _, text, trainer_id = header
    name = text.split()[-1]
    blocks = team["blocks"]
    if trainer_id in TEAM_BLOCKS:
        blocks = [blocks[i] for i in TEAM_BLOCKS[trainer_id]]
    fixes = SHEET_FIXES.get(trainer_id, {})
    out = []
    for i, (row, col) in enumerate(blocks):
        try:
            p = _pokemon(values, formulas, row, col)
        except ValueError as error:
            raise ValueError(f"{text} [{trainer_id}], row {row + 1}: {error}") from error
        p["nature"] = team["shared_natures"].get((name, p["name"]), p["nature"])
        if i in fixes:
            report["fixed"].append(f"{text} [{trainer_id}] {p['name']}: {fixes[i]}")
            p.update(fixes[i])
        out.append(p)
    return out


def _team_scales(team: list, trainer_id: int, cls: tuple) -> set:
    """The ivScales that give every Pokemon of the team its nature and IV"""
    return set.intersection(*(_scales(p, trainer_id, cls) for p in team))


def _mirror(team: list, scales: set, trainer_id: int, cls: tuple, label: str, report: dict) -> None:
    """Natures and IVs from the scale the mirror rival's fight uses (MIRROR_RIVALS)"""
    for p in team:
        natures = {personality_nature(s, p["level"], p["dex"], trainer_id, cls[0], cls[3]) for s in scales}
        ivs = {scale * 31 // 255 for scale in scales}
        if len(natures) != 1 or len(ivs) != 1:
            raise ValueError(f"{label} {p['name']}: the mirror's scales {sorted(scales)} give {natures}")
        nature, iv = natures.pop(), ivs.pop()
        if p["iv"] not in (None, iv):
            raise ValueError(f"{label} {p['name']}: IV {p['iv']}, the mirror's scale gives {iv}")
        sheet = f"sheet {p['nature']} IV {p['iv']}"
        report["mirrored"].append(f"{label} {p['name']}: {sheet}, took {nature} IV {iv}")
        p["nature"], p["iv"] = nature, iv


def _resolve_class(trainer_id, team: list, candidates: list, ratios: dict, label: str, report: dict):
    """The trainer's [pp] class, with the team's gaps filled. None when the sheet leaves too much out"""
    if trainer_id is None:
        report["no_id"].append(label)
        fits = candidates
    else:
        fits = _check_class(trainer_id, team, candidates)
    if not fits:
        report["bad_natures"].append(f"{label}: {[c[1] for c in candidates]}")
        fits = candidates
    if trainer_id in CLASS_FIXES:
        fits = [c for c in fits if c[1] == CLASS_FIXES[trainer_id]]
        if not fits:
            raise ValueError(f"{label}: the natures don't fit {CLASS_FIXES[trainer_id]}")
    if len({c[3] for c in fits}) > 1:
        fits = _by_gender_marks(fits, team, ratios, label, report)
    cls = fits[0]
    if any(p["nature"] is None or p["iv"] is None for p in team):
        filled = _fill_gaps(trainer_id, cls, team, label) if trainer_id is not None else None
        if filled is None:
            report["incomplete"].append(label)
            return None
        report["filled"] += filled
    return cls


def _starter(notes: list, label: str):
    """The starter a rival's variant is met with, None for a trainer who isn't one"""
    starters = [m[1].title() for n in notes for m in IF_STARTER_RE.finditer(n)]
    if not starters:
        return None
    if len(starters) != 1 or starters[0] not in STARTERS:
        raise ValueError(f"{label}: starter notes {starters}")
    return starters[0]


def _is_double(notes: list, candidates: list) -> bool:
    """A double or multi battle, or a partner's team"""
    double = any(DOUBLE_NOTES.search(n) for n in notes) and not any(ALONE_NOTE.match(n) for n in notes)
    return double or all(c[1] in DOUBLE_CLASSES for c in candidates)


def _variants(entry: dict, notes: list, name: str, label: str) -> None:
    """if_starter and if_player from the rival notes"""
    starter = _starter(notes, label)
    if starter:
        entry["if_starter"] = starter
    shared = {m[1]: m[2] for n in notes for m in SHARED_PLAYER_RE.finditer(n)}
    own = [m[1].lower() for n in notes for m in IF_PLAYER_RE.finditer(n)]
    player = shared.get(name) or (own[0] if own else None)
    if player:
        entry["if_player"] = "Female" if player == "girl" else "Male"


def _trainer_items(notes: list, label: str) -> list:
    """'can use : 1 SUPER POTION' and the lines under it -> ['Super Potion', ...], one per use. Not ItemDB
    items: the backend has its own table of them"""
    out = []
    reading = False
    for note in notes:
        start = ITEMS_RE.match(note)
        if start:
            found = ITEM_LINE_RE.findall(start[1])
            if not found:
                raise ValueError(f"{label}: can't read the trainer items {note!r}")
            reading = True
        elif reading and ITEM_LINE_RE.fullmatch(note):
            found = ITEM_LINE_RE.findall(note)
        else:
            reading = False
            continue
        for count, item in found:
            count = int(count or 1)
            name = item[:-1] if count > 1 and item.endswith("S") else item
            out += [name.title()] * count
    return out


def _gender(p: dict, cls: tuple, ratios: dict, label: str, report: dict):
    """[pp]'s when it doesn't depend on the trainer's gender (only a 50% species' does), else the sheet's mark
    when the species can have it. A sheet mark that differs is reported, kept or not"""
    ratio = _ratio(ratios, p["name"])
    expected = pp_gender(ratio, cls[3])
    mark = GENDER_MARKS.get(p["mark"], "missing")
    if mark == expected:
        return mark
    shown = p["mark"] or "no mark"
    if mark in _possible_genders(ratio) and pp_gender(ratio, False) != pp_gender(ratio, True):
        report["genders"].append(f"{label} {p['name']}: sheet {shown}, [pp] {expected}, kept the sheet")
        return mark
    report["genders"].append(f"{label} {p['name']}: sheet {shown}, took [pp] {expected}")
    return expected


def _team_entries(team: list, cls: tuple, ratios: dict, spell, label: str, report: dict) -> list:
    out = []
    for p in team:
        mon = {"name": p["name"], "gender": _gender(p, cls, ratios, label, report), "level": p["level"]}
        if p["item"]:
            mon["item"] = spell("items", p["item"])
        mon["ability"] = spell("abilities", p["ability"])
        mon["nature"] = p["nature"]
        mon["moves"] = [spell("moves", m) for m in p["moves"]]
        mon["ivs"] = {stat: p["iv"] for stat in STATS}
        out.append(mon)
    return out


def _terrain(team: list, center: bool, location: str, label: str, report: dict):
    """The battle terrain, only for a team with a move that reads it"""
    if not any(m in TERRAIN_MOVES for p in team for m in p["moves"]):
        return None
    if center:
        return CENTER_TERRAIN
    if location not in LOCATION_TERRAIN:
        report["no_terrain"].append(f"{label}: {location}")
        return None
    return LOCATION_TERRAIN[location]


def _trainer(context: dict, team: dict, header: tuple):
    """(key name, entry, variant) for one header of a team, None when it's skipped. The variant is a rival's
    ("starter", name) or a random team's ("random", number), None for the rest"""
    _, text, trainer_id = header
    report, notes = context["report"], team["notes"]
    sheet_class, name, candidates = _split_class(text, context["classes"])
    label = f"{text} [{trainer_id}]" if trainer_id is not None else text
    split = _trainer_split(context["split"], context["center"], notes, label)
    if split is None:
        report["post_game"].append(label)
        return None
    if _is_double(notes, candidates):
        report["doubles"].append(f"{split}: {label}")
        return None
    values, formulas = context["tab"]
    pokemon = _read_pokemon(values, formulas, team, header, report)
    unknown = [p["name"] for p in pokemon if p["name"] not in context["species"]]
    if unknown:
        raise ValueError(f"{label}: unknown species {unknown}")
    if name in MIRROR_RIVALS:
        scales = context["mirrors"].get((split, _starter(notes, label)))
        if scales is None:
            raise ValueError(f"{label}: no {MIRROR_RIVALS[name].title()} fight to mirror")
        _mirror(pokemon, scales, trainer_id, candidates[0], label, report)
    cls = _resolve_class(trainer_id, pokemon, candidates, context["ratios"], f"{split}: {label}", report)
    if cls is None:
        return None
    key_name = _key_name(sheet_class, name)
    entry = {"split": split}
    if trainer_id is not None:
        entry["id"] = trainer_id
    if cls[1] not in CLASS_SPRITE and key_name not in PLAYER_SPRITE:
        raise ValueError(f"{label}: no sprite for class {cls[1]}")
    entry["sprite"] = PLAYER_SPRITE.get(key_name) or CLASS_SPRITE[cls[1]]
    if entry["sprite"] is None:
        report["no_sprite"].append(f"{cls[1]}: {label}")
    _variants(entry, notes, name, label)
    terrain = _terrain(pokemon, context["center"], team["location"], label, report)
    if terrain:
        entry["terrain"] = terrain
    items = _trainer_items(notes, label)
    if items:
        entry["trainer_items"] = items
    entry["team"] = _team_entries(pokemon, cls, context["ratios"], context["spell"], label, report)
    random_team = [int(m[1]) for n in notes for m in [RANDOM_TEAM_RE.fullmatch(n)] if m]
    if random_team:
        return key_name, entry, ("random", random_team[0])
    return key_name, entry, ("starter", entry["if_starter"]) if "if_starter" in entry else None


def _mirror_scales(tabs: dict, classes: list) -> dict:
    """{(split, starter): ivScales} of the fights MIRROR_RIVALS mirror, the scales every Pokemon fits"""
    mirrors = set(MIRROR_RIVALS.values())
    out = {}
    for split, tab in SPLITS:
        values, formulas = tabs[tab]
        for team in read_teams(values):
            for header in team["headers"]:
                _, name, candidates = _split_class(header[1], classes)
                if name not in mirrors or _is_double(team["notes"], candidates):
                    continue
                pokemon = _read_pokemon(values, formulas, team, header, {"fixed": []})
                key = (split, _starter(team["notes"], header[1]))
                scales = _team_scales(pokemon, header[2], candidates[0])
                if not scales or key in out:
                    raise ValueError(f"{header[1]} [{header[2]}]: scales {sorted(scales)}, fight {key}")
                out[key] = scales
    return out


REPORT_TITLES = {
    "doubles": "Double and multi battles, skipped",
    "post_game": "Pokemon Center teams after the Champion, skipped",
    "incomplete": "Natures or IVs the sheet leaves out and the personality can't give, skipped",
    "bad_natures": "Natures no class of the trainer's gives ([pp] personality), kept the sheet's",
    "no_id": "No trainer id in the sheet, natures not checked",
    "class_gender": "Trainer gender unknown, took the male class",
    "filled": "Natures and IVs the sheet leaves out, from the personality",
    "fixed": "Fixes to the sheet (SHEET_FIXES)",
    "mirrored": "Lucas's natures and IVs, from Dawn's mirror fight (MIRROR_RIVALS)",
    "genders": "Genders",
    "no_terrain": "No terrain for the location, left out",
    "no_sprite": "No sprite for the class in [SD], left empty",
    "short_variants": "Rival fights missing a starter variant",
    "unknown": "Not in the databases yet",
}
REPORT_KEYS = tuple(key for key in REPORT_TITLES if key != "unknown")


def build_trainers(tabs: dict, classes: list, ratios: dict, databases: dict) -> tuple:
    """(TrainerDB dict in story order, {report key: lines})"""
    unknown = set()
    spell = _speller(databases, unknown)
    report = {key: [] for key in REPORT_KEYS}
    context = {"classes": classes, "ratios": ratios, "species": set(databases["species"]), "spell": spell,
               "report": report, "mirrors": _mirror_scales(tabs, classes)}
    entries = []
    for split, tab, center in [(s, t, False) for s, t in SPLITS] + [(None, CENTER_TAB, True)]:
        values, formulas = tabs[tab]
        try:
            teams = read_teams(values)
        except ValueError as error:
            raise ValueError(f"{tab}: {error}") from error
        locations = _locations(values, teams)
        context.update(split=split, center=center, tab=(values, formulas))
        for team in teams:
            places = [h for r, h in locations if r < team["row"]]
            team["location"] = places[-1] if places else ""
            for header in team["headers"]:
                found = _trainer(context, team, header)
                if found:
                    entries.append(found)
    report["unknown"] = sorted(unknown)
    order = [s for s, _ in SPLITS]
    entries.sort(key=lambda e: order.index(e[1]["split"]))  # stable: Pokemon Center fights end their split
    return _number(entries, report), report


def _number(entries: list, report: dict) -> dict:
    """Keys: '<name> <n>' for a name's n-th fight, plus its variant: a rival's letter by the variants' order
    in the sheet ('Barry 1-P'), a random team's number ('Champion Cynthia 1-2'). A rival fight with fewer
    than 3 variants (one was skipped) is reported"""
    counts, runs, fights, out = {}, {}, {}, {}

    def close(key_name):
        run = runs.get(key_name)
        if run and run[0] == "starter" and len(run[1]) != len(VARIANT_LETTERS):
            report["short_variants"].append(f"{key_name} {counts[key_name]}: {run[1]}")

    for key_name, entry, variant in entries:
        run = runs.get(key_name)
        same = (
            variant is not None and run is not None and run[0] == variant[0] and variant[1] not in run[1]
            and not (variant[0] == "starter" and len(run[1]) == len(VARIANT_LETTERS))
        )
        if same:
            run[1].append(variant[1])
        else:
            close(key_name)
            counts[key_name] = counts.get(key_name, 0) + 1
            run = runs[key_name] = (variant[0], [variant[1]]) if variant else None
        fight = f"{key_name} {counts[key_name]}"
        key = fight
        if variant is not None:
            key += "-" + (VARIANT_LETTERS[len(run[1]) - 1] if variant[0] == "starter" else str(variant[1]))
        if key in out:
            raise ValueError(f"Two fights for {key}")
        out[key], fights[key] = entry, fight
    for key_name in runs:
        close(key_name)
    # A fight's variants together, fights in the order their first variant comes (Lucas and Dawn share teams)
    order = list(dict.fromkeys(fights.values()))
    return {key: out[key] for fight in order for key in out if fights[key] == fight}


def db_text(database: dict) -> str:
    """The file's text: JSON with 2 spaces, a list of strings on one line (moves, trainer items)"""
    text = json.dumps(database, indent=2)
    return re.sub(
        r"\[\n\s+((?:\"[^\"\n]*\",\n\s+)*\"[^\"\n]*\")\n\s+\]",
        lambda m: "[" + ", ".join(re.split(r",\n\s+", m[1])) + "]",
        text,
    ) + "\n"


# ─── Run ──────────────────────────────────────────────────────────────────────────────────────────────


def _download(url: str, binary: bool = False):
    with urllib.request.urlopen(url, timeout=300) as res:
        if url == WORKBOOK_URL and "spreadsheetml" not in res.headers.get("Content-Type", ""):
            raise SystemExit("The sheet asked for a login: download it as xlsx and pass the file")
        data = res.read()
    return data if binary else data.decode("utf-8")


def _databases() -> dict:
    def names(file):
        return list(json.loads((HERE / file).read_text(encoding="utf-8")))
    return {
        "species": names("PkDB.json"),
        "moves": names("MoveDB.json"),
        "items": names("ItemDB.json"),
        "abilities": names("AbilitiesDB.json"),
    }


def load(workbook_path=None) -> tuple:
    """(TrainerDB dict, report) from the sheet and the reference data"""
    data = Path(workbook_path).read_bytes() if workbook_path else _download(WORKBOOK_URL, binary=True)
    tabs = read_workbook(data, [tab for _, tab in SPLITS] + [CENTER_TAB])
    classes = parse_classes(_download(PP_CLASS_NAMES), _download(PP_CLASSES), _download(PP_CLASS_GENDERS))
    ratios = parse_gender_ratios(_download(SD_POKEDEX))
    return build_trainers(tabs, classes, ratios, _databases())


def main() -> None:
    """Read the sheet, write TrainerDB.json, list what was skipped or filled in"""
    database, report = load(sys.argv[1] if len(sys.argv) > 1 else None)
    TRAINER_DB.write_text(db_text(database), encoding="ascii")
    per_split = {}
    for entry in database.values():
        per_split[entry["split"]] = per_split.get(entry["split"], 0) + 1
    print(f"{len(database)} trainers: " + ", ".join(f"{s} {n}" for s, n in per_split.items()))
    for key, title in REPORT_TITLES.items():
        print(f"\n{title} ({len(report[key])}):")
        for line in report[key]:
            print(f"  {line}")


if __name__ == "__main__":
    main()
