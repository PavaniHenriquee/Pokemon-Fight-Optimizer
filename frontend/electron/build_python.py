"""
Bundle the backend for the Electron app: python.org's embeddable Python (same version as the
.venv), the runtime packages pinned to the .venv's versions, and the engine source as plain .py
files (the Numba cache needs real source files to work).

Output: frontend/build/backend/{python,src}, which electron-builder copies into the app as
resources/backend. Run it with the repo's .venv Python (`npm run dist` does):
    ..\\.venv\\Scripts\\python.exe electron\\build_python.py
"""
import compileall
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

FRONTEND = Path(__file__).resolve().parent.parent
REPO = FRONTEND.parent
BUILD = FRONTEND / "build"
OUT = BUILD / "backend"
sys.path.insert(0, str(REPO))

from Utils.jit_cache import BACKEND_DIRS  # pylint: disable=wrong-import-position

# What the backend needs at runtime; pip pulls their dependencies (pytest, py-spy stay out).
# websockets / httptools are the uvicorn extras the .venv has (uvicorn[standard] also wants
# PyYAML, which has no Python 3.15 wheel)
RUNTIME = ["fastapi", "uvicorn", "websockets", "httptools", "numba", "numpy"]


def constraints() -> str:
    """The .venv's exact versions, so the app runs what the tests ran"""
    frozen = subprocess.run([sys.executable, "-m", "pip", "freeze"], check=True,
                            capture_output=True, text=True).stdout
    return "".join(line + "\n" for line in frozen.splitlines() if "==" in line)


def embeddable_zip(version: str) -> Path:
    """python.org's embeddable package, downloaded once into build/cache"""
    name = f"python-{version}-embed-amd64.zip"
    dest = BUILD / "cache" / name
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://www.python.org/ftp/python/{version}/{name}"
        print("downloading", url)
        tmp = dest.with_suffix(".part")
        with urllib.request.urlopen(url, timeout=120) as res:
            tmp.write_bytes(res.read())
        os.replace(tmp, dest)
    return dest


def build_python(stamp: str) -> None:
    """Embeddable Python + site-packages; skipped when nothing changed since the last build"""
    py = OUT / "python"
    stamp_file = py / ".bundle-stamp"
    if stamp_file.exists() and stamp_file.read_text(encoding="utf-8") == stamp:
        print("python: up to date")
        return
    shutil.rmtree(py, ignore_errors=True)
    with zipfile.ZipFile(embeddable_zip(platform.python_version())) as z:
        z.extractall(py)

    # The ._pth file sets sys.path for the embeddable Python (and ignores PYTHONPATH/PYTHONHOME)
    pth = next(py.glob("python*._pth"))
    stdlib = next(py.glob("python*.zip")).name
    pth.write_text(f"{stdlib}\n.\nLib\\site-packages\n..\\src\nimport site\n", encoding="utf-8")

    req = BUILD / "cache" / "constraints.txt"
    req.write_text(stamp.split("\n", 1)[1], encoding="utf-8")
    subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                    "--no-warn-script-location", "--only-binary=:all:", "--target", str(py / "Lib" / "site-packages"),
                    "--constraint", str(req), *RUNTIME], check=True)
    stamp_file.write_text(stamp, encoding="utf-8")


def copy_sources() -> None:
    """The engine and backend as plain .py files, compiled to .pyc for a faster start"""
    src = OUT / "src"
    shutil.rmtree(src, ignore_errors=True)
    for folder in BACKEND_DIRS:
        shutil.copytree(REPO / folder, src / folder,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    compileall.compile_dir(str(src), quiet=1)

    # UserData stays out of the app: it starts with an empty box and run. This removes the seed
    # folder older builds made, so its test box doesn't ship
    shutil.rmtree(OUT / "seed", ignore_errors=True)


def smoke_test() -> None:
    """The bundled Python must import the whole backend (JIT off: no compile needed here)"""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "NUMBA"))}
    env["NUMBA_DISABLE_JIT"] = "1"
    subprocess.run([str(OUT / "python" / "python.exe"), "-c", "import backend.main"],
                   cwd=OUT / "src", env=env, check=True)
    print("smoke test: bundled Python imports backend.main")


def main() -> None:
    if platform.machine().lower() not in ("amd64", "x86_64"):
        sys.exit("Only 64-bit Windows builds are supported")
    stamp = f"{platform.python_version()}\n{constraints()}"
    build_python(stamp)
    copy_sources()
    smoke_test()
    print("backend bundle ready:", OUT)


if __name__ == "__main__":
    main()
