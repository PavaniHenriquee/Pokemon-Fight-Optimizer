"""Win rate and value from the start of each fight, for rollouts and for full battles played by
search. Seeds are fixed, so with no code change these numbers repeat exactly, and any change in
them is a change in the search."""
import math
import multiprocessing as mp
import time
from SearchEngine.mcts_eval import rollout_arr
from benchmarks.fights import FIGHTS, fight, seed_all
from benchmarks.play import battle_task, core_cpus, init_pinned_worker

_COLUMNS = ((200, 2000), (1000, 1000), (5000, 300))
_SKIP_AT = {5000: ("Dallas",)}  # It's already won at 1000
_COLUMN_25K = (("Roark good", 80), ("Barry 2-P", 120), ("Roark weak", 120))
_ROLLOUT_PROBS = (0.48, 1.0)


def _wilson(wins, n, z=1.96):
    """95% confidence interval of a win rate"""
    if n == 0:
        return 0.0, 0.0
    p = wins / n
    denominator = 1 + z * z / n
    center = p + z * z / (2 * n)
    spread = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (center - spread) / denominator), (center + spread) / denominator


def _rollout_task(task):
    name, prob, n, seed = task
    seed_all(seed)
    battle = fight(name)
    wins = 0
    value = dead_in_wins = 0.0
    for _ in range(n):
        v, w, d = rollout_arr(battle.copy(), 100, prob)
        wins += w
        value += v
        dead_in_wins += d if w else 0
    return wins, value, dead_in_wins, n


def _rollouts(report, pool, workers, budget):
    rows = []
    for name in FIGHTS:
        for prob in _ROLLOUT_PROBS:
            tasks = [
                (name, prob, budget.rollouts // workers + 1, 7000 + i) for i in range(workers)
            ]
            done = pool.map(_rollout_task, tasks, chunksize=1)
            wins = sum(r[0] for r in done)
            value = sum(r[1] for r in done)
            dead = sum(r[2] for r in done)
            n = sum(r[3] for r in done)
            low, high = _wilson(wins, n)
            report.metric(f"quality/{name}/rollout {prob}/win", wins / n)
            report.metric(f"quality/{name}/rollout {prob}/value", value / n)
            rows.append((
                name, prob, f"{n:,}", f"{wins / n * 100:.2f}%",
                f"{low * 100:.2f}-{high * 100:.2f}%", f"{value / n:.4f}",
                f"{dead / wins:.2f}" if wins else "none",
            ))
    report.text("Rollouts from the start of the fight.")
    report.table(("Fight", "`heuristic_prob`", "Samples", "Win", "95% CI", "Value",
                  "Deaths per win"), rows)


def _battles(report, pool, name, iters, n):
    """One cell of the table: n seeded battles"""
    tasks = [(name, iters, 100_000 * iters + i) for i in range(n)]
    start = time.perf_counter()
    done = list(pool.imap_unordered(battle_task, tasks, chunksize=1))
    wall = time.perf_counter() - start
    values = sorted(r[0] for r in done)
    wins = sum(r[1] for r in done)
    value = sum(values) / n
    tail = values[:max(1, int(n * 0.15))]
    searched = sum(r[4] for r in done)
    spread = 1.96 * math.sqrt(sum((v - value) ** 2 for v in values) / max(n - 1, 1) / n)
    low, high = _wilson(wins, n)
    deaths = sum(r[2] for r in done if r[1]) / wins if wins else 0.0
    key = f"quality/{name}/{iters}"
    report.metric(f"{key}/win", wins / n)
    report.metric(f"{key}/value", value)
    report.metric(f"{key}/cvar15", sum(tail) / len(tail))
    report.metric(f"{key}/deaths_per_win", deaths)
    report.metric(f"{key}/ms_per_decision", sum(r[5] for r in done) / max(searched, 1) * 1000)
    row = (
        name, f"{iters:,}", n, f"{wins / n * 100:.1f}%", f"{low * 100:.1f}-{high * 100:.1f}%",
        f"{value:.3f} ± {spread:.3f}", f"{sum(tail) / len(tail):.3f}", f"{deaths:.2f}",
        f"{sum(r[3] for r in done) / n:.1f}",
        f"{sum(r[5] for r in done) / max(searched, 1) * 1000:.0f} ms", f"{wall:.0f} s",
    )
    report.progress(row)
    return row


_BATTLE_HEADERS = ("Fight", "It/decision", "Battles", "Win", "95% CI", "Value", "CVaR15",
                   "Deaths per win", "Decisions per battle", "Time per decision", "Wall")


def _pool():
    workers = len(core_cpus())
    return workers, mp.Pool(
        workers, initializer=init_pinned_worker, initargs=(mp.Value("i", 0),)
    )


def _count(n, budget):
    return max(2, int(n * budget.battle_fraction))


def run(report, budget):
    """Rollouts, then full battles at 200, 1000 and 5000 iterations per decision"""
    report.heading("Win rates")
    workers, pool = _pool()
    with pool:
        _rollouts(report, pool, workers, budget)
        rows = []
        for iters, n in _COLUMNS:
            for name in FIGHTS:
                if name not in _SKIP_AT.get(iters, ()):
                    rows.append(_battles(
                        report, pool, name, min(iters, budget.max_iters), _count(n, budget),
                    ))
    report.text(f"Full battles on {workers} pinned workers.")
    report.table(_BATTLE_HEADERS, rows)


def run_25k(report, budget):
    """How much room is left at about 2 s per decision"""
    report.heading("Win rates at 25,000 iterations")
    _, pool = _pool()
    with pool:
        rows = [
            _battles(report, pool, name, min(25_000, budget.max_iters), _count(n, budget))
            for name, n in _COLUMN_25K
        ]
    report.table(_BATTLE_HEADERS, rows)
