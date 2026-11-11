"""
Download every sprite the frontend shows into frontend/public/sprites/, so the app works offline
(Electron build). Run it once before `npm run build`; later runs only fetch what's missing.

The URLs and file names match frontend/src/lib/sprites.ts (local first, these remotes as fallback).
Usage: python fetch_sprites.py [--workers N]
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from DataBase.PkDB import PokIdToName, sprite_id, CASTFORM_SPRITE_ID

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "frontend" / "public" / "sprites"
POKEAPI = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites"
SHOWDOWN = "https://play.pokemonshowdown.com/sprites"
TYPE_COUNT = 18  # PokeAPI type ids 1..18 (Normal..Fairy)


# Showdown names these icons without hyphens (same list as sprites.ts)
ITEM_SLUG_OVERRIDES = {
    "bright-powder": "brightpowder",
    "never-melt-ice": "nevermeltice",
    "silver-powder": "silverpowder",
    "thunder-stone": "thunderstone",
    "twisted-spoon": "twistedspoon",
}


def hyphenated(name: str) -> str:
    """"King's Rock" -> "kings-rock", "Exp. Share" -> "exp-share" (same as sprites.ts)"""
    return "-".join(re.sub(r"[^a-z0-9\s_-]", "", name.lower()).replace("_", " ").split())


def item_slug(name: str) -> str:
    """Same rule as itemSlug in sprites.ts"""
    slug = hyphenated(name)
    return ITEM_SLUG_OVERRIDES.get(slug, slug)


def item_icon_job(name: str) -> tuple[tuple[str, ...], Path]:
    """Showdown's icon, PokeAPI's for the few it doesn't have (Ice Stone, the Fairy TM)"""
    slug = item_slug(name)
    urls = (f"{SHOWDOWN}/itemicons/{slug}.png", f"{POKEAPI}/items/{hyphenated(name)}.png")
    return urls, OUT / "items" / f"{slug}.png"


def jobs() -> list[tuple[str | tuple[str, ...], Path]]:
    """(url, destination) for every sprite. A tuple of urls is tried in order"""
    out = []
    poke = f"{POKEAPI}/pokemon"
    for pid in sorted({sprite_id(i) for i in PokIdToName} | set(CASTFORM_SPRITE_ID.values())):
        out += [
            (f"{poke}/versions/generation-v/black-white/animated/{pid}.gif", OUT / "front" / f"{pid}.gif"),
            (f"{poke}/versions/generation-v/black-white/animated/back/{pid}.gif", OUT / "back" / f"{pid}.gif"),
            (f"{poke}/{pid}.png", OUT / "front-static" / f"{pid}.png"),
            (f"{poke}/back/{pid}.png", OUT / "back-static" / f"{pid}.png"),
            (f"{poke}/versions/generation-vii/icons/{pid}.png", OUT / "icons" / f"{pid}.png"),
        ]

    with open(ROOT / "DataBase" / "ItemDB.json", encoding="utf-8") as f:
        items = set(json.load(f))
    # The Tracker's Items tab: a TM or HM shows its type's disc
    with open(ROOT / "DataBase" / "ItemLocationDB.json", encoding="utf-8") as f:
        pickups = [p for ps in json.load(f)["locations"].values() for p in ps]
    items |= {f"{p['item'][:2]} {p['type']}" if p["kind"] == "tm" else p["item"] for p in pickups}
    out += [item_icon_job(name) for name in sorted(items)]

    with open(ROOT / "DataBase" / "TrainerDB.json", encoding="utf-8") as f:
        trainers = json.load(f)
    for sprite in sorted({t["sprite"] for t in trainers.values() if t.get("sprite")}):
        out.append((f"{SHOWDOWN}/trainers/{sprite}.png", OUT / "trainers" / f"{sprite}.png"))

    for tid in range(1, TYPE_COUNT + 1):
        out.append((f"{POKEAPI}/types/generation-ix/scarlet-violet/{tid}.png", OUT / "types" / f"{tid}.png"))
        out.append((
            f"{POKEAPI}/types/generation-viii/legends-arceus/small/{tid}.png",
            OUT / "types-small" / f"{tid}.png",
        ))
    return out


def fetch(job: tuple[str | tuple[str, ...], Path]) -> str:
    """'ok', 'skip' (already there), 'missing' (404 on every url) or an error message"""
    urls, dest = job
    if dest.exists():
        return "skip"
    data = None
    for url in (urls,) if isinstance(urls, str) else urls:
        req = urllib.request.Request(url, headers={"User-Agent": "nuzlocke-optimizer-sprite-fetch"})
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                data = res.read()
            break
        except urllib.error.HTTPError as e:
            if e.code != 404:
                return f"HTTP {e.code} {url}"
        except (urllib.error.URLError, TimeoutError) as e:
            return f"{e} {url}"
    if data is None:
        return "missing"
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")  # an interrupted run never leaves half a file
    tmp.write_bytes(data)
    os.replace(tmp, dest)
    return "ok"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--workers", type=int, default=16, help="parallel downloads (default 16)")
    args = parser.parse_args()

    todo = jobs()
    counts = {"ok": 0, "skip": 0, "missing": 0}
    errors = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for i, result in enumerate(pool.map(fetch, todo), 1):
            if result in counts:
                counts[result] += 1
            else:
                errors.append(result)
            if i % 250 == 0 or i == len(todo):
                print(f"\r{i}/{len(todo)}", end="", flush=True)
    print()
    print(f"downloaded {counts['ok']}, already had {counts['skip']}, "
          f"not on the server {counts['missing']} (the app falls back for those)")
    for err in errors:
        print("  failed:", err)
    if errors:
        print("Run it again to retry the failed ones.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
