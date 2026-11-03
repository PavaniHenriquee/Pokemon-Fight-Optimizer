"""Numba compile cache keyed by a hash of the sources.

Numba's own cache doesn't notice edits to callees in other files, so every source change gets a
fresh folder (.numba_cache/<name>/<hash>) and older folders are deleted. Must run before
Utils.jit is imported, since that module reads NUMBA_CACHE_ON at import time.
"""
import hashlib
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIRS = ("DataBase", "Engine", "Models", "SearchEngine", "Utils", "backend")


def source_hash(dirs, root=ROOT) -> str:
    """Short hash of every .py / .json file under the given folders"""
    digest = hashlib.sha256()
    for folder in dirs:
        for base, _, files in sorted(os.walk(os.path.join(root, folder))):
            for f in sorted(files):
                if f.endswith((".py", ".json")):
                    with open(os.path.join(base, f), "rb") as fh:
                        digest.update(f.encode() + fh.read())
    return digest.hexdigest()[:12]


def cache_dir(name: str, dirs, root=ROOT, cache_root: str | None = None) -> str:
    """.numba_cache/<name>/<source hash> (or <cache_root>/<name>/<hash>), deleting the folders
    of older sources"""
    base = os.path.join(cache_root or os.path.join(root, ".numba_cache"), name)
    key = source_hash(dirs, root)
    if os.path.isdir(base):
        for old in os.listdir(base):
            if old != key:
                shutil.rmtree(os.path.join(base, old), ignore_errors=True)
    return os.path.join(base, key)


def use_cache(name: str, dirs=BACKEND_DIRS) -> str | None:
    """Turn the cache on for this process. NUMBA_CACHE_ON=0 opts out; nothing happens with
    NUMBA_DISABLE_JIT=1 (the pytest suite). PBO_CACHE_ROOT moves it out of the repo (the
    Electron app, whose install folder may not be writable)."""
    if os.environ.get("NUMBA_CACHE_ON") == "0" or os.environ.get("NUMBA_DISABLE_JIT") == "1":
        return None
    path = cache_dir(name, dirs, cache_root=os.environ.get("PBO_CACHE_ROOT") or None)
    os.environ["NUMBA_CACHE_ON"] = "1"
    os.environ["NUMBA_CACHE_DIR"] = path
    return path
