"""How many workers to use, and how many decisions a second each fight gives. Workers load from the
Numba cache and start together on a barrier, so the time window only holds search."""
import multiprocessing as mp
import time
import psutil
from benchmarks.fights import FIGHTS
from benchmarks.play import core_cpus, timed_worker

_SCALING_FIGHTS = ("Roark weak", "Barry 2-P")
_SCALING_ITERS = 1000
_RATE_ITERS = (200, 1000, 5000)
_DATA_ITERS = 1000  # What Step 5 generates at


def _background_percent(seconds):
    """Sleeps through the run and returns how busy the machine was outside these workers"""
    children = psutil.Process().children(recursive=True)

    def own_cpu():
        total = 0.0
        for child in children:
            try:
                total += sum(child.cpu_times()[:2])
            except psutil.Error:
                pass
        return total

    cpu_before, own_before = psutil.cpu_times(), own_cpu()
    start = time.perf_counter()
    time.sleep(seconds * 0.9)
    wall = time.perf_counter() - start
    cpu_after, own_after = psutil.cpu_times(), own_cpu()
    busy = cpu_after.user + cpu_after.system - cpu_before.user - cpu_before.system
    return 100 * (busy - (own_after - own_before)) / (wall * psutil.cpu_count())


def run_workers(name, iters, n, pin, seconds):
    """n workers play a fight for that long. pin is 'cores', 'skip first core' or 'free'"""
    cores = core_cpus()
    if pin == "cores":
        cpus = [[c] for c in cores[:n]]
    elif pin == "skip first core":
        cpus = [[c] for c in cores[1:n + 1]]
    else:
        cpus = [None] * n
    with mp.Manager() as manager:
        barrier = manager.Barrier(n + 1)
        args = [(name, iters, seconds, cpus[i], 1000 + i, barrier) for i in range(n)]
        with mp.Pool(n) as pool:
            pending = pool.map_async(timed_worker, args, chunksize=1)
            barrier.wait()
            background = _background_percent(seconds)
            results = pending.get()
    decisions_s = sum(decisions / wall for decisions, wall, _ in results)
    return {
        "decisions_s": decisions_s,
        "per_worker_it_s": decisions_s * iters / n,
        "peak_mb": max(peak for _, _, peak in results) / 2**20,
        "background": background,
    }


def _row(name, iters, workers, result):
    return (
        name, iters, workers, f"{result['decisions_s']:,.1f}", f"{result['per_worker_it_s']:,.0f}",
        f"{result['peak_mb']:.0f} MB", f"{result['background']:.0f}%",
    )


_HEADERS = ("Fight", "It/decision", "Workers", "Decisions/s", "It/s per worker", "Worker peak",
            "Background")


def run_scaling(report, budget):
    """Throughput against worker count, pinned and not"""
    report.heading("Workers")
    report.text("Pinned means one worker per physical core.")
    cores = len(core_cpus())
    logical = psutil.cpu_count()
    if budget.full_tables:
        plan = [(1, "free")]
        plan += [(n, "cores") for n in (2, 4, 6, 8, 12, 16) if n <= cores]
        if cores > 1:
            plan.append((cores, "free"))
        plan += [(n, "free") for n in (12, 14, 16, 24, 32) if cores < n <= logical]
    else:
        plan = [(1, "free"), (min(4, cores), "cores"), (cores, "cores"), (cores, "free"),
                (logical, "free")]
        plan = list(dict.fromkeys(plan))
    if budget.smoke:
        plan = plan[:2]
    rows = []
    for name in _SCALING_FIGHTS if budget.full_tables else _SCALING_FIGHTS[:1]:
        for n, pin in plan:
            result = run_workers(name, _SCALING_ITERS, n, pin, budget.worker_seconds)
            label = f"{n}, {'pinned' if pin == 'cores' else 'unpinned'}"
            report.metric(f"workers/{name}/{label}/decisions_s", result["decisions_s"])
            rows.append(_row(name, _SCALING_ITERS, label, result))
            report.progress(rows[-1])
    report.table(_HEADERS, rows)


def run_rates(report, budget):
    """Data rate per fight and budget, one process alone and all cores pinned"""
    report.heading("Data rates")
    cores = len(core_cpus())
    fights = list(FIGHTS)[:1] if budget.smoke else FIGHTS
    rows = []
    for name in fights:
        for iters in _RATE_ITERS if budget.full_tables else (_DATA_ITERS,):
            iters = min(iters, budget.max_iters)
            for n, pin, label in ((1, "free", "alone"), (cores, "cores", f"{cores} pinned")):
                result = run_workers(name, iters, n, pin, budget.rate_seconds)
                report.metric(f"rates/{name}/{iters}/{label}/decisions_s", result["decisions_s"])
                report.metric(f"rates/{name}/{iters}/{label}/peak_mb", result["peak_mb"])
                rows.append(_row(name, iters, label, result))
                report.progress(rows[-1])
    report.table(_HEADERS, rows)
