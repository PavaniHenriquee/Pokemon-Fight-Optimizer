"""
Download every sprite the frontend shows into frontend/public/sprites/, so the app works offline
(Electron build). Run it once before `npm run build`; later runs only fetch what's missing.

The URLs and file names match frontend/src/lib/sprites.ts (local first, these remotes as fallback).
Usage: python fetch_sprites.py [--workers N]
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from DataBase.PkDB import PokIdToName, sprite_id

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
    "twisted-spoon": "twistedspoon",
}


def item_slug(name: str) -> str:
    """Same rule as itemSlug in sprites.ts"""
    slug = "-".join(name.lower().replace("_", " ").split())
    return ITEM_SLUG_OVERRIDES.get(slug, slug)


def jobs() -> list[tuple[str, Path]]:
    """(url, destination) for every sprite"""
    out = []
    poke = f"{POKEAPI}/pokemon"
    for pid in sorted({sprite_id(i) for i in PokIdToName}):
        out += [
            (f"{poke}/versions/generation-v/black-white/animated/{pid}.gif", OUT / "front" / f"{pid}.gif"),
            (f"{poke}/versions/generation-v/black-white/animated/back/{pid}.gif", OUT / "back" / f"{pid}.gif"),
            (f"{poke}/{pid}.png", OUT / "front-static" / f"{pid}.png"),
            (f"{poke}/back/{pid}.png", OUT / "back-static" / f"{pid}.png"),
            (f"{poke}/versions/generation-vii/icons/{pid}.png", OUT / "icons" / f"{pid}.png"),
        ]

    with open(ROOT / "DataBase" / "ItemDB.json", encoding="utf-8") as f:
        items = json.load(f)
    for name in items:
        slug = item_slug(name)
        out.append((f"{SHOWDOWN}/itemicons/{slug}.png", OUT / "items" / f"{slug}.png"))

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


def fetch(job: tuple[str, Path]) -> str:
    """'ok', 'skip' (already there), 'missing' (404) or an error message"""
    url, dest = job
    if dest.exists():
        return "skip"
    req = urllib.request.Request(url, headers={"User-Agent": "nuzlocke-optimizer-sprite-fetch"})
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            data = res.read()
    except urllib.error.HTTPError as e:
        return "missing" if e.code == 404 else f"HTTP {e.code} {url}"
    except (urllib.error.URLError, TimeoutError) as e:
        return f"{e} {url}"
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
