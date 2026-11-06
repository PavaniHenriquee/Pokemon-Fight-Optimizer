"""Measures the numbers in NN_PLAN.md again and compares them with earlier runs.

    python -m benchmarks.run quick            search speed and network kernels, about 1.5 minutes
    python -m benchmarks.run all              everything but the extras, about 10 minutes
    python -m benchmarks.run search quality   any sections by name
    python -m benchmarks.run all --smoke      checks every section still works, saves nothing
    python -m benchmarks.run all compile quality25k --long    the plan's tables, about 1.5 hours

Sections: search, network, workers, rates, data, training (needs torch, see
requirements-train.txt) and quality. Extras, only when named: compile, quality25k and tuning (values
for the search's c, NN_PLAN.md Step 1a, about 2 hours). quality uses
fixed seeds, so with no code change it repeats exactly. Reports go to benchmarks/results/ and only
compare with runs of the same length. Keep the machine quiet for the timing sections.
"""
import argparse
import importlib
import importlib.util
import os
import sys
import time
import warnings
from Utils.jit_cache import use_cache

# Numba's own cache misses edits to callees in other files, so the cache folder follows a hash of
# the sources. benchmarks/ stays out of the hash because every report it saves would change it.
_CACHE_DIRS = ("DataBase", "Engine", "Models", "NeuralNetwork", "SearchEngine", "Utils")
_SECTIONS = {
    "search": ("search", "run"),
    "network": ("network", "run"),
    "workers": ("workers", "run_scaling"),
    "rates": ("workers", "run_rates"),
    "data": ("data", "run"),
    "training": ("training", "run"),
    "quality": ("quality", "run"),
    "compile": ("compile_cost", "run"),
    "quality25k": ("quality", "run_25k"),
    "tuning": ("tuning", "run"),
}
_PRESETS = {
    "quick": ("search", "network"),
    "all": ("search", "network", "workers", "rates", "data", "training", "quality"),
}


def _keep_awake():
    """The PC sleeps after 45 idle minutes otherwise. Lasts while this process runs, changes no
    setting"""
    if os.name == "nt":
        import ctypes
        es_continuous, es_system_required = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(es_continuous | es_system_required)


def _section_names(requested):
    names = []
    for item in requested:
        for name in _PRESETS.get(item, (item,)):
            if name not in _SECTIONS:
                raise SystemExit(f"Unknown section {name}. Sections: {', '.join(_SECTIONS)}")
            if name not in names:
                names.append(name)
    return names


def main():
    """Runs the requested sections and saves the report after each one"""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("sections", nargs="+", help="quick, all, or section names")
    length = parser.add_mutually_exclusive_group()
    length.add_argument("--smoke", action="store_true", help="tiny budgets, nothing saved")
    length.add_argument("--long", action="store_true", help="the plan's full tables, much slower")
    args = parser.parse_args()
    names = _section_names(args.sections)

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    warnings.simplefilter("ignore")
    os.environ["PYTHONWARNINGS"] = "ignore"
    use_cache("benchmarks", _CACHE_DIRS)
    _keep_awake()

    from benchmarks.play import warm
    from benchmarks.report import LONG, RESULTS, SMOKE, Budget, Report

    budget = SMOKE if args.smoke else LONG if args.long else Budget()
    report = Report(names, budget.name, results_dir=None if args.smoke else RESULTS)
    for key, value in report.machine.items():
        print(f"{key}: {value}")
    start = time.perf_counter()
    print("\nCompiling or loading the engine (about 90 s after a source change)", flush=True)
    warm()
    print(f"Engine ready in {time.perf_counter() - start:.1f} s", flush=True)

    for name in names:
        if name == "training" and importlib.util.find_spec("torch") is None:
            report.heading("Training")
            report.text("Skipped, torch isn't installed: pip install -r requirements-train.txt")
            continue
        section_start = time.perf_counter()
        module, function = _SECTIONS[name]
        getattr(importlib.import_module(f"benchmarks.{module}"), function)(report, budget)
        report.text(f"This section took {time.perf_counter() - section_start:.0f} s.")
        report.save()
    report.save()
    report.print_summary()
    print(f"Total {(time.perf_counter() - start) / 60:.1f} minutes")


if __name__ == "__main__":
    main()
