"""
Coverage report (ENGINE_PLAN.md 1.3): every move, held item, ability and trainer item the trainers up to the
Champion use, whether the engine supports it, and how ENGINE_PLAN.md covers it. It only prints.

- Trainers per split: how many the engine runs now, and after each phase if they're done in the plan's order.
- What trainers use: the first split, how many trainers, supported or not, the plan's step.
- Plan check: what's missing from the plan, the `*` marks (a plan entry no trainer uses that my own Pokemon
  can get), entries nothing uses, and lines that aren't a move, item or ability.
- To check: where each entry of the plan's "To check" list goes, or that nothing has it.

What my Pokemon can get, post-game included (it's there if I explore after the Champion): the species
EncounterDB lists (and the starters) with their whole evolution lines, their level-up and tutor moves and
abilities (PkDB), the TMs, HMs and items ItemLocationDB has, and PP_ITEM_SOURCES for the items the sheet
doesn't list.
Usage: python -m DataBase.coverage
"""
import json
import re
from pathlib import Path

from DataBase.loader import moveDB, itemDB, abDB, pkDB
from DataBase.support import NOT_IMPLEMENTED, TRAINER_ITEMS
from DataBase.import_trainers import SPLITS

HERE = Path(__file__).resolve().parent
PLAN = HERE.parent / "ENGINE_PLAN.md"
SPLIT_NAMES = tuple(name for name, _ in SPLITS)
PLAN_PHASES = tuple(range(3, 13))  # the phases that list moves, items and abilities
TO_CHECK_TITLE = "To check in 1.3"
KINDS = ("move", "item", "ability", "trainer item")
ITEM_PHASE = 4  # a plan entry there is an item, even one no file has (most berries)
# Items the sheet doesn't list (ItemLocationDB has no berries), from [pp] pret/pokeplatinum, which RP keeps:
# the berries its berry trees start with (include/data/berry_init.h) and Razor Fang, a hidden item
# (include/data/field/hidden_items.h). The sheet's NPCTRADES tab says a Route 208 seller sells rare berries
# "such as the Liechi and Salac": every rare berry counts as sold there (no tree or [pp] script gives the rest)
PP_BERRY_TREES = (
    "Aguav", "Aspear", "Bluk", "Cheri", "Chesto", "Figy", "Grepa", "Hondew", "Iapapa", "Kelpsy", "Leppa",
    "Lum", "Mago", "Nanab", "Oran", "Pecha", "Persim", "Pinap", "Pomeg", "Qualot", "Rawst", "Razz",
    "Sitrus", "Tamato", "Wepear", "Wiki",
)
PP_RARE_BERRIES = (
    "Liechi", "Salac", "Ganlon", "Apicot", "Lansat", "Micle", "Custap", "Enigma", "Jaboca", "Rowap",
)
PP_ITEM_SOURCES = {
    **{f"{berry} Berry": "berry trees ([pp] berry_init.h)" for berry in PP_BERRY_TREES},
    "Razor Fang": "hidden on Route 214 ([pp] hidden_items.h)",
    **{f"{berry} Berry": "Route 208 seller (NPCTRADES)" for berry in PP_RARE_BERRIES},
}

PLAN_SECTION = re.compile(r"## (?:Phase (\d+)\b|(.+))")
PLAN_STEP = re.compile(r"### (\d+\.\d+)\b")
PLAN_ENTRY = re.compile(r"- \[([ xX])\] ([^(!*]+?)\s*(\(|!|\*|$)(.*)")
TO_CHECK_TARGET = re.compile(r"\(→ (\d+(?:\.\d+)?)\)")


def _json(name: str):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def load() -> dict:
    """Everything the report reads"""
    return {
        "trainers": _json("TrainerDB.json"),
        "encounters": _json("EncounterDB.json"),
        "item_locations": _json("ItemLocationDB.json")["locations"],
        "plan": PLAN.read_text(encoding="utf-8"),
        "pk": pkDB,
        "moves": set(moveDB),
        "items": set(itemDB),
        "abilities": set(abDB),
    }


# ─── Reading ──────────────────────────────────────────────────────────────────────────────────────────


def parse_plan(text: str) -> dict:
    """{name: {"step", "phase", "star", "ticked", "to_check"}} for each checkbox line of Phases 3-12 and the
    "To check" list. step is the line's ### step ('5.1'), or the phase ('3') when it has none. A "To check"
    line takes the step its '(→ 6.1)' names, phase None when it names none. The name is the text before the
    first '(', '!' or '*'; a '*' anywhere after it marks it as mine only"""
    entries = {}
    phase, step, to_check = None, None, False
    for line in text.splitlines():
        section = PLAN_SECTION.match(line)
        if section and not line.startswith("###"):
            phase = int(section[1]) if section[1] else None
            phase = phase if phase in PLAN_PHASES else None
            to_check = section[2] == TO_CHECK_TITLE
            step = str(phase) if phase else None
            continue
        sub = PLAN_STEP.match(line)
        if sub:
            step = sub[1]
            continue
        entry = PLAN_ENTRY.match(line)
        if not entry or not (phase or to_check) or (to_check and entry[1] != " "):
            continue  # a ticked "To check" line is settled: placed in its step or dropped
        rest = entry[3] + entry[4]
        if to_check:
            target = TO_CHECK_TARGET.search(rest)
            line_step = target[1] if target else None
        else:
            line_step = step
        entries[entry[2].strip()] = {
            "step": line_step,
            "phase": int(line_step.split(".")[0]) if line_step else None,
            "star": "*" in rest,
            "ticked": entry[1] != " ",
            "to_check": to_check,
        }
    return entries


def supported(kind: str, name: str, data: dict) -> bool:
    """The engine can run it: in its database and not NOT_IMPLEMENTED, or a trainer item the AI uses"""
    if kind == "trainer item":
        return name in TRAINER_ITEMS
    known = {"move": data["moves"], "item": data["items"], "ability": data["abilities"]}[kind]
    return name in known and name not in NOT_IMPLEMENTED


def trainer_uses(trainers: dict) -> dict:
    """{(kind, name): {"first": split, "trainers": [keys]}}, in the order the trainers first use them"""
    uses = {}
    for key, trainer in trainers.items():
        names = {("trainer item", i) for i in trainer.get("trainer_items", []) if i}
        for p in trainer["team"]:
            names |= {("move", m) for m in p["moves"] if m}
            names |= {("item", p["item"])} if p.get("item") else set()
            names |= {("ability", p["ability"])} if p.get("ability") else set()
        for name in sorted(names):
            uses.setdefault(name, {"first": trainer["split"], "trainers": []})["trainers"].append(key)
    return uses


def my_species(encounters: dict) -> list:
    """The species I can have, in the order the game first offers them: what EncounterDB lists, then the rest
    of each one's evolution line"""
    met = list(encounters["starters"])
    met += [m["name"] for tables in encounters["locations"].values() for t in tables for m in t["mons"]]
    lines = {species: line for line in encounters["evolution_lines"] for species in line}
    out = {}
    for species in met:
        for member in lines.get(species, [species]):
            out.setdefault(member, None)
    return list(out)


def my_sources(data: dict) -> dict:
    """{(kind, name): where my Pokemon get it}, the first place found: a TM/HM or item's location, a species'
    learnset, tutor list or ability, then PP_ITEM_SOURCES"""
    sources = {}
    for location, entries in data["item_locations"].items():
        for e in entries:
            if e["kind"] == "tm":
                sources.setdefault(("move", e["move"]), f"{e['item']} ({location})")
            elif e["kind"] == "item":
                sources.setdefault(("item", e["item"]), location)
    for species in my_species(data["encounters"]):
        entry = data["pk"][species]
        for _, move in entry.get("learnset", []):
            sources.setdefault(("move", move), f"{species}'s learnset")
        for move in entry.get("tutor", []):
            sources.setdefault(("move", move), f"{species}'s tutor")
        for ability in entry.get("abilities", []):
            sources.setdefault(("ability", ability), species)
    for item, source in PP_ITEM_SOURCES.items():
        sources.setdefault(("item", item), source)
    return sources


def known_names(data: dict, uses: dict) -> dict:
    """{kind: every name the files have}, before the Champion or after, to tell a plan entry from a note"""
    moves = data["moves"] | {n for k, n in uses if k == "move"}
    moves |= {e["move"] for es in data["item_locations"].values() for e in es if e["kind"] == "tm"}
    for entry in data["pk"].values():
        moves |= {move for _, move in entry.get("learnset", [])} | set(entry.get("tutor", []))
    items = data["items"] | {n for k, n in uses if k == "item"}
    items |= {e["item"] for es in data["item_locations"].values() for e in es if e["kind"] == "item"}
    abilities = data["abilities"] | {a for entry in data["pk"].values() for a in entry.get("abilities", [])}
    return {"move": moves, "item": items, "ability": abilities}


def _kind_of(name: str, entry: dict, known: dict) -> str | None:
    """A plan entry's kind: the one whose names have it, else an item in ITEM_PHASE and a move in "To check".
    None for a note (a sentence: a ',' or ':', or more than 4 words) or a line that's no move, item or
    ability"""
    for kind in ("ability", "item", "move"):
        if name in known[kind]:
            return kind
    if "," in name or ":" in name or len(name.split()) > 4:
        return None
    if entry["phase"] == ITEM_PHASE and not entry["to_check"]:
        return "item"
    return "move" if entry["to_check"] and entry["step"] else None


# ─── Report ───────────────────────────────────────────────────────────────────────────────────────────


def _table(rows: list, header: tuple) -> list:
    rows = [tuple(str(c) for c in header)] + [tuple(str(c) for c in r) for r in rows]
    widths = [max(len(r[i]) for r in rows) for i in range(len(header))]
    return ["  " + "  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip() for r in rows]


def runnable_after(trainers: dict, uses: dict, plan: dict, data: dict) -> tuple:
    """({phase: {split: trainers runnable once the plan is done up to it}}, trainers that need something the
    plan doesn't have). Phase 0 is now"""
    needs = {}
    for (kind, name), use in uses.items():
        if supported(kind, name, data):
            continue
        phase = plan[name]["phase"] if name in plan else None
        for key in use["trainers"]:
            needs.setdefault(key, []).append(phase)
    never = sorted(k for k, phases in needs.items() if None in phases)
    table = {}
    for phase in (0,) + PLAN_PHASES:
        counts = dict.fromkeys(SPLIT_NAMES, 0)
        for key, trainer in trainers.items():
            phases = needs.get(key, [])
            if None not in phases and all(p <= phase for p in phases):
                counts[trainer["split"]] += 1
        table[phase] = counts
    return table, never


def report(data: dict) -> list:
    """The report's lines"""
    trainers, plan = data["trainers"], parse_plan(data["plan"])
    uses, sources = trainer_uses(trainers), my_sources(data)
    known = known_names(data, uses)
    out = []

    totals = dict.fromkeys(SPLIT_NAMES, 0)
    for trainer in trainers.values():
        totals[trainer["split"]] += 1
    table, never = runnable_after(trainers, uses, plan, data)
    out += ["Trainers the engine runs, per split (now, then after each phase in the plan's order)"]
    rows = [("trainers", *totals.values(), sum(totals.values()))]
    rows += [
        ("now" if phase == 0 else f"phase {phase}", *counts.values(), sum(counts.values()))
        for phase, counts in table.items()
    ]
    out += _table(rows, ("", *SPLIT_NAMES, "total"))
    out += [f"  Need something the plan doesn't have ({len(never)}): {', '.join(never) or '-'}", ""]

    split_index = {s: i for i, s in enumerate(SPLIT_NAMES)}
    for kind in KINDS:
        named = [(n, u) for (k, n), u in uses.items() if k == kind]
        named.sort(key=lambda nu: (split_index[nu[1]["first"]], -len(nu[1]["trainers"]), nu[0]))
        rows = [
            (n, u["first"], len(u["trainers"]), "yes" if supported(kind, n, data) else "no",
             plan[n]["step"] if n in plan else ("-" if supported(kind, n, data) else "NOT IN PLAN"))
            for n, u in named
        ]
        missing = sum(1 for r in rows if r[3] == "no")
        plural = "abilities" if kind == "ability" else f"{kind}s"
        out += [f"What trainers use: {plural} ({len(rows)}, {missing} not supported)"]
        out += _table(rows, (kind, "first split", "trainers", "supported", "plan")) + [""]

    out += ["Plan check"]
    lacking = sorted(
        f"{n} ({k})" for (k, n) in uses if not supported(k, n, data) and n not in plan
    )
    out += [
        f"  A trainer uses it, not supported, not in the plan ({len(lacking)}): {', '.join(lacking) or '-'}"
    ]
    mine = sorted(
        f"{n} ({src})" for (k, n), src in sources.items()
        if k in ("move", "ability") and (k, n) not in uses and not supported(k, n, data) and n not in plan
    )
    out += [f"  My Pokemon can get it, not supported, not in the plan ({len(mine)}):"]
    out += [f"    {line}" for line in mine] or ["    -"]
    stars, drops, wrong_star, odd, tick = [], [], [], [], []
    for name, entry in plan.items():
        kind = _kind_of(name, entry, known)
        if kind is None and entry["to_check"]:
            continue
        if kind is None:
            odd.append(f"{name} ({entry['step'] or 'To check'})")
            continue
        used = any((k, name) in uses for k in KINDS)
        if used and entry["star"]:
            wrong_star.append(name)
        elif not used and not entry["star"] and not entry["to_check"]:
            source = sources.get((kind, name))
            (stars if source else drops).append(
                (name, entry["step"], kind, source or "no source found")
            )
        if supported(kind, name, data) and not entry["ticked"] and not entry["to_check"]:
            tick.append(name)
    out += [f"  No trainer uses it and it has no * ({len(stars)}): it gets *"]
    out += _table(stars, ("entry", "step", "kind", "where my Pokemon get it")) if stars else ["    -"]
    out += [f"  No trainer uses it and my Pokemon can't get it ({len(drops)}): drop it?"]
    out += _table(drops, ("entry", "step", "kind", "")) if drops else ["    -"]
    out += [f"  Has * but a trainer uses it ({len(wrong_star)}): {', '.join(wrong_star) or '-'}"]
    out += [f"  Supported now but not ticked ({len(tick)}): {', '.join(tick) or '-'}"]
    out += [f"  Lines that aren't a move, item or ability ({len(odd)}):"]
    out += [f"    {line}" for line in odd] or ["    -"]
    out += [""]

    rows = []
    for name, entry in plan.items():
        if not entry["to_check"]:
            continue
        kind = _kind_of(name, entry, known)
        users = len(uses.get((kind, name), {"trainers": []})["trainers"])
        source = sources.get((kind, name))
        if kind is None:
            verdict = "see the Plan check's \"My Pokemon can get it\" list"
        elif users:
            verdict = f"-> {entry['step']} ({users} trainers)"
        elif source:
            verdict = f"-> {entry['step']} * ({source})"
        else:
            verdict = "drop: no trainer, my Pokemon can't get it"
        rows.append((name, verdict))
    out += ["To check"] + (_table(rows, ("entry", "")) if rows else ["  -"])
    return out


def main() -> None:
    """Print the report"""
    print("\n".join(report(load())))


if __name__ == "__main__":
    main()
