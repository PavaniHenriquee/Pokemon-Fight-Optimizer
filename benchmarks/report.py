"""What a benchmark run records: the machine, its tables, and the change against earlier runs."""
import glob
import importlib.metadata
import json
import os
import platform
import subprocess
from dataclasses import dataclass
from datetime import datetime
import psutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "benchmarks", "results")
_PACKAGES = ("numba", "llvmlite", "numpy", "torch")
_NOTABLE_CHANGE = 15.0  # Percent. Timings moved 5-30% between runs with no code change


@dataclass(frozen=True)
class Budget:
    """How much each section measures. The default is short enough to run after any change"""
    name: str = "default"
    smoke: bool = False
    full_tables: bool = False  # Every row of NN_PLAN.md's tables, not only the telling ones
    search_seconds: float = 20
    search_passes: int = 1
    worker_seconds: float = 10
    rate_seconds: float = 8
    bringup_seconds: float = 10
    rollouts: int = 20_000
    battle_fraction: float = 0.1
    max_iters: int = 25_000
    states: int = 20_000
    train_seconds: float = 3
    vram_states: int = 200_000
    rounds: int = 5


# The plan's full tables and battle counts, about 1.5 hours
LONG = Budget(
    name="long", full_tables=True, search_seconds=30, search_passes=2, worker_seconds=30,
    rate_seconds=20, bringup_seconds=20, battle_fraction=1.0, states=40_000, train_seconds=6,
    vram_states=400_000, rounds=7,
)
# Checks that every section still works. Its numbers mean nothing and aren't saved
SMOKE = Budget(
    name="smoke", smoke=True, search_seconds=2, worker_seconds=2, rate_seconds=2,
    bringup_seconds=2, rollouts=200, battle_fraction=0.01, max_iters=200, states=2000,
    train_seconds=0.5, vram_states=4000, rounds=1,
)


def _command(*cmd):
    try:
        done = subprocess.run(
            cmd, capture_output=True, text=True, errors="replace", check=True, timeout=20, cwd=ROOT,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip()


def _cpu_name():
    if os.name == "nt":
        import winreg
        path = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
            return winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
    return platform.processor()


def _version(package):
    try:
        return f"{package} {importlib.metadata.version(package)}"
    except importlib.metadata.PackageNotFoundError:
        return f"{package} not installed"


def machine_info():
    """Everything a timing depends on, to read a report on its own later"""
    import llvmlite.binding
    memory = psutil.virtual_memory()
    gpu = _command(
        "nvidia-smi", "--query-gpu=name,driver_version,memory.total,memory.used",
        "--format=csv,noheader",
    )
    changed = _command("git", "status", "--porcelain", "--", ".", ":!benchmarks/results")
    commit = _command("git", "rev-parse", "--short", "HEAD")
    return {
        "cpu": _cpu_name(),
        "cores / threads": f"{psutil.cpu_count(logical=False)} / {psutil.cpu_count()}",
        "llvm target": llvmlite.binding.get_host_cpu_name(),
        "ram": f"{memory.total / 2**30:.1f} GB, {memory.available / 2**30:.1f} GB free",
        "gpu": gpu or "none found",
        "disk free": f"{psutil.disk_usage(ROOT).free / 2**30:.0f} GB",
        "python": platform.python_version(),
        "packages": ", ".join(_version(p) for p in _PACKAGES),
        "power plan": _command("powercfg", "/getactivescheme"),
        "commit": commit + (" with uncommitted changes" if changed else ""),
        "background load at start": f"{psutil.cpu_percent(interval=2):.0f}%",
    }


def _number(value):
    return f"{value:,.4g}"


class Report:
    """Prints as it goes and keeps everything for the report files. results_dir=None saves nothing"""
    def __init__(self, sections, budget_name="default", results_dir=RESULTS, machine=None):
        self.stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
        self.sections = list(sections)
        self.budget_name = budget_name
        self.results_dir = results_dir
        self.machine = machine if machine is not None else machine_info()
        self.body = []
        self.metrics = {}

    def _add(self, *lines):
        for line in lines:
            print(line, flush=True)
        self.body.extend(lines)

    def heading(self, title):
        """Starts a section"""
        self._add("", f"## {title}", "")

    def text(self, line):
        """A line of prose"""
        self._add(line, "")

    def table(self, headers, rows):
        """A Markdown table, aligned so it also reads well in a terminal"""
        rows = [[str(cell) for cell in row] for row in rows]
        widths = [max(len(row[i]) for row in [list(headers)] + rows) for i in range(len(headers))]

        def line(cells):
            return "| " + " | ".join(c.ljust(w) for c, w in zip(cells, widths)) + " |"

        self._add(line(headers), line(["-" * w for w in widths]), *[line(r) for r in rows], "")

    @staticmethod
    def progress(row):
        """A finished table row, shown while a long table is still running. Not kept in the report"""
        print("  " + " | ".join(str(cell) for cell in row), flush=True)

    def metric(self, key, value):
        """A number later runs get compared against"""
        self.metrics[key] = float(value)

    def _earlier_metrics(self):
        """The latest earlier value of each metric, from reports on this same CPU and budget. A
        shorter window moves the numbers by itself, so other budgets don't count"""
        earlier = {}
        if self.results_dir is None:
            return earlier
        for path in sorted(glob.glob(os.path.join(self.results_dir, "*.json"))):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            same_cpu = data["machine"].get("cpu") == self.machine.get("cpu")
            same_budget = data["budget"] == self.budget_name
            if same_cpu and same_budget and data["stamp"] != self.stamp:
                earlier.update(data["metrics"])
        return earlier

    def changes(self):
        """(metric, before, now, percent) for every metric with an earlier value"""
        earlier = self._earlier_metrics()
        rows = []
        for key, now in self.metrics.items():
            before = earlier.get(key)
            if before is not None:
                rows.append((key, before, now, 100 * (now - before) / before if before else 0.0))
        return rows

    def _markdown(self):
        out = [f"# Benchmarks {self.stamp}", "", f"Sections: {', '.join(self.sections)}", ""]
        out += [f"- budget: {self.budget_name}"]
        out += [f"- {key}: {value}" for key, value in self.machine.items()]
        out += self.body
        rows = self.changes()
        if rows:
            out += ["", "## Change against earlier runs", ""]
            out += ["| Metric | Before | Now | Change |", "| --- | --- | --- | --- |"]
            out += [f"| {k} | {_number(b)} | {_number(n)} | {p:+.1f}% |" for k, b, n, p in rows]
        return "\n".join(out) + "\n"

    def save(self):
        """Writes both files. Called after every section, so a crash keeps what was measured"""
        if self.results_dir is None:
            return
        os.makedirs(self.results_dir, exist_ok=True)
        base = os.path.join(self.results_dir, self.stamp)
        with open(base + ".json", "w", encoding="utf-8") as f:
            json.dump({
                "stamp": self.stamp, "budget": self.budget_name, "sections": self.sections,
                "machine": self.machine, "metrics": self.metrics,
            }, f, indent=1)
        with open(base + ".md", "w", encoding="utf-8") as f:
            f.write(self._markdown())

    def print_summary(self):
        """The biggest changes against earlier runs, and where the files are"""
        rows = self.changes()
        notable = [r for r in rows if abs(r[3]) >= _NOTABLE_CHANGE]
        if rows:
            print(f"\n{len(rows)} metrics compared with earlier runs, "
                  f"{len(notable)} moved {_NOTABLE_CHANGE:.0f}% or more:")
            for key, before, now, percent in sorted(notable, key=lambda r: -abs(r[3])):
                print(f"  {key}: {_number(before)} -> {_number(now)} ({percent:+.1f}%)")
            print("With no code change, timings have moved 5-30% between runs, most when other "
                  "programs were busy\n(see the Background columns). Rerun before trusting one.")
        if self.results_dir is not None:
            print(f"\nReport: {os.path.join(self.results_dir, self.stamp)}.md")
