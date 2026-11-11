"""
Add each species' base friendship from pokeplatinum to PkDB.json, as "base friendship": n, right before its
abilities line. A trainer's Pokemon battles with it ([pp] trainer_data.c builds them with Pokemon_InitWith,
which sets the species' base friendship and nothing changes it), so it gives their Return and Frustration
power. A form uses its species' value. Rerun it to refresh: only those lines change.

The source is [pp] res/pokemon/<species>/data.json, downloaded one by one.
Usage: python -m DataBase.import_friendship
"""
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
PK_DB = HERE / "PkDB.json"
SPECIES_URL = "https://raw.githubusercontent.com/pret/pokeplatinum/main/res/pokemon/{}/data.json"
LINE = '    "base friendship": '


# Species whose PkDB name carries a form after an underscore ("Deoxys_attack")
FORM_SPECIES = ("Deoxys", "Wormadam", "Rotom", "Giratina", "Shaymin")


def species_dir(name: str) -> str:
    """pokeplatinum's folder for a PkDB name: lower case, a form uses its species' folder
    ("Mr_mime" → mr_mime, "Deoxys_attack" → deoxys)"""
    base = name.split("_")[0]
    return (base if base in FORM_SPECIES else name).lower()


def _fetch(folder: str) -> int:
    with urllib.request.urlopen(SPECIES_URL.format(folder), timeout=60) as res:
        return json.loads(res.read().decode("utf-8"))["base_friendship"]


def with_friendship(db_text: str, friendship: dict) -> str:
    """PkDB.json's text with each species' base friendship line before its abilities line, replacing
    the one a previous run added, so the rest of the file stays exactly as it is"""
    out = []
    species = None
    for line in db_text.splitlines(keepends=True):
        head = re.match(r'  "(.+)": \{', line)
        if head:
            species = head[1]
        if line.startswith(LINE):
            continue
        if line.startswith('    "abilities": '):
            eol = "\r\n" if line.endswith("\r\n") else "\n"
            out.append(f"{LINE}{friendship[species]},{eol}")
        out.append(line)
    return "".join(out)


def _without_friendship(database: dict) -> dict:
    return {
        name: {k: v for k, v in entry.items() if k != "base friendship"}
        for name, entry in database.items()
    }


def main() -> None:
    """Download every species' value, write the lines, check nothing else changed"""
    with open(PK_DB, encoding="utf-8", newline="") as f:
        old_text = f.read()
    old = json.loads(old_text)
    folders = {name: species_dir(name) for name in old}
    with ThreadPoolExecutor(16) as pool:
        values = dict(zip(sorted(set(folders.values())), pool.map(_fetch, sorted(set(folders.values())))))
    friendship = {name: values[folder] for name, folder in folders.items()}

    new_text = with_friendship(old_text, friendship)
    new = json.loads(new_text)
    if _without_friendship(new) != _without_friendship(old) or any(
        new[name].get("base friendship") != friendship[name] for name in new
    ):
        raise SystemExit("Something other than the base friendship changed, PkDB.json left as it was")
    if new_text != old_text:
        with open(PK_DB, "w", encoding="utf-8", newline="") as f:
            f.write(new_text)
    counts = {}
    for value in friendship.values():
        counts[value] = counts.get(value, 0) + 1
    print(f"{len(friendship)} species, base friendship counts: {dict(sorted(counts.items()))}")


if __name__ == "__main__":
    main()
