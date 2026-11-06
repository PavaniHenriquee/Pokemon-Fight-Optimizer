"""Finds values for the search's c: best_action's default and ROOT_C (NN_PLAN.md Step 1a).

Scores each set two ways. Positions: does it pick the action that playouts show is right, in spots
where the search has been seen taking a needless death risk, and one where staying in is right?
Full battles: win rate and deaths per win. Only best_action's default and my_mcts.ROOT_C change, in
the worker processes, so no source changes and nothing recompiles. Reports only: a new default needs
your OK.

The plan's tables also tried a CVaR penalty, since removed. To run those again, apply
benchmarks/results/2026-11-06_tuning_with_cvar.patch on commit 2b82d54.
"""
import math
import time
from Engine.engine_helper import start_of_battle
from Models.helper import ActionType
from Models.idx_const import Field, Pok, POK_LEN
from SearchEngine import my_mcts
from SearchEngine.helper import find_best_terminal_node, prune_dominated
from SearchEngine.mcts_eval import evaluate_terminal
from SearchEngine.models import GameState, Node, ROOT_C
from SearchEngine.my_mcts import _backprop, _rollout, _select_expand
from Utils.helper import to_battle_array
from benchmarks.fights import FIGHTS, TRAINERS, _mon, _pokemon, fight, seed_all
from benchmarks.play import _only_action, _search, battle_task
from benchmarks.quality import _pool, _wilson

BASELINE = (Node.best_action.__defaults__[0], ROOT_C)  # (c, c at the root)
_SETS = tuple(
    (c, root_c) for c in (0.2, 0.25, 0.3, 0.35, 0.42) for root_c in (0.6, 0.8, 1.2, 1.6)
)
_SEEDS = 20
_POSITION_ITERS = 100_000  # Less than the app's cap: nearly every position stops before this
_CHECK_EVERY = 2500  # The backend's stop rule, as in benchmarks/search.py
_CONVERGED_VISITS = 5000
_PLAYOUT_BATTLES = 300
_PLAYOUT_ITERS = 2000
_FIGHTS = ("Roark good", "Roark weak", "Barry 2-P")
_STAGE_2 = (1000, 300, 10)  # Iterations per decision, battles, sets that reach it
_STAGE_3 = (5000, 300, 3)
_Z_95 = 1.96
_STOP_SEEDS = 8
# Past every battle count so far, so these seeds played no part in choosing the values. quality
# uses the same seeds as the tuning stages, so its numbers aren't a fresh check
_FRESH_FIRST_SEED = 50_000

_MOVE, _SWITCH = ActionType.MOVE, ActionType.SWITCH
_IVS_15 = {
    k: 15 for k in ("HP", "Attack", "Defense", "Special Attack", "Special Defense", "Speed")
}


def _trainer(name):
    """A TrainerDB team as it stands"""
    return [
        _mon(p["name"], p["level"], p["ability"], p["moves"], p["nature"], p.get("ivs"),
             p.get("item"), p.get("gender", "Male"))
        for p in TRAINERS[name]["team"]
    ]


def _dawn(lead, my_hp, foe_hp):
    """Eevee 9 and Chimchar 9 against Dawn 1-P. The moves are the level-up ones, the IVs a guess"""
    eevee = _mon("Eevee", 9, "Run Away", ["Tail Whip", "Bite", "Covet", "Sand Attack"], ivs=_IVS_15)
    chimchar = _mon("Chimchar", 9, "Blaze", ["Scratch", "Leer", "Ember", "Taunt"], ivs=_IVS_15)
    team = [eevee, chimchar] if lead == "Eevee" else [chimchar, eevee]
    return team, _trainer("Dawn 1-P"), my_hp, foe_hp


def _crit(moves, behind=False):
    """Only a crit from the faster foe's Tackle kills my active at 11 HP. The foe is at 1 HP"""
    team = [_mon("Machop", 14, "Guts", moves), _mon("Gastly", 14, "Levitate", ["Lick", "Leer"])]
    foes = [_mon("Shinx", 14, "Rivalry", ["Tackle"])]
    if behind:
        team.append(_mon("Prinplup", 18, "Torrent", ["Water Pulse", "Peck", "Pound"]))
        foes += _trainer("Gym Leader Roark 1")[:2]
    return team, foes, 11, 1


# Name: (how to build it, actions that are right, the action the search is tempted by)
POSITIONS = {
    "Dawn, Eevee 9/30, foe 9/31": (
        lambda: _dawn("Eevee", 9, 9), ((_SWITCH, 1),), (_MOVE, 2)),
    "Dawn, Eevee 15/30, foe 9/31": (
        lambda: _dawn("Eevee", 15, 9), ((_SWITCH, 1),), (_MOVE, 2)),
    "Dawn, Eevee 15/30, foe 31/31": (
        lambda: _dawn("Eevee", 15, 31), ((_SWITCH, 1),), (_MOVE, 3)),
    "Dawn, Chimchar 11/28, foe 18/31 (stay)": (
        lambda: _dawn("Chimchar", 11, 18), ((_MOVE, 2),), (_SWITCH, 1)),
    "Crit, Quick Attack first": (
        lambda: _crit(["Pound", "Quick Attack", "Leer"]), ((_MOVE, 1),), (_MOVE, 0)),
    "Crit, immune switch": (
        lambda: _crit(["Pound", "Leer", "Focus Energy"]), ((_SWITCH, 1),), (_MOVE, 0)),
    "Crit, Roark behind": (
        lambda: _crit(["Pound", "Leer", "Focus Energy"], behind=True),
        ((_SWITCH, 1), (_SWITCH, 2)), (_MOVE, 0)),
}


def position(name):
    """A fresh battle array for a named position"""
    team, foes, my_hp, foe_hp = POSITIONS[name][0]()
    battle = to_battle_array([_pokemon(p) for p in team], [_pokemon(p) for p in foes])
    if battle[Field.TURN] == 0:
        start_of_battle(battle)
    battle[Pok.CURRENT_HP] = my_hp
    battle[6 * POK_LEN + Pok.CURRENT_HP] = foe_hp
    return battle


def _set_values(values):
    """Selection reads these for the whole tree. Each worker sets them before every task"""
    c, root_c = values
    Node.best_action.__defaults__ = (c,)
    my_mcts.ROOT_C = root_c


def _backend_loop(root, root_state, iters):
    """The backend's loop and stop rule. Returns the iterations run and if the stop rule ended it"""
    for i in range(iters):
        state, path, actions = _select_expand(root_state.clone(), root)
        value, win, dead = _rollout(state)
        _backprop(path, actions, value, win, dead)
        if i % _CHECK_EVERY == 0 and i > 0:
            node, _, _ = find_best_terminal_node(root)
            prune_dominated(root)
            if node.snapshot.terminal and node.visits >= _CONVERGED_VISITS:
                return i + 1, True
    return iters, False


def _position_task(task):
    """The most visited root action under the backend's loop and stop rule"""
    values, name, iters, seed = task
    _set_values(values)
    root_state = GameState(position(name))
    seed_all(seed)
    root = Node(root_state)
    _backend_loop(root, root_state, iters)
    best = max(root.children, key=lambda a: sum(n.visits for n in root.children[a]))
    return int(best[0]), int(best[1])


def _stop_task(task):
    """How long the stop rule takes to end a search, and the top action's share of visits by then"""
    values, name, iters, seed = task
    _set_values(values)
    root_state = GameState(position(name) if name in POSITIONS else fight(name))
    seed_all(seed)
    root = Node(root_state)
    start = time.perf_counter()
    ran, stopped = _backend_loop(root, root_state, iters)
    seconds = time.perf_counter() - start
    visits = [sum(n.visits for n in nodes) for nodes in root.children.values()]
    return ran, stopped, seconds, max(visits) / sum(visits)


def _playout_task(task):
    """Plays the action, then search plays the rest with today's values"""
    name, action, iters, seed = task
    _set_values(BASELINE)
    seed_all(seed)
    state = GameState(position(name))
    state.step(action)
    made = 0
    while made < 60 and not state.is_terminal():
        chosen = _only_action(state)
        state.step(_search(state, iters) if chosen is None else chosen)
        made += 1
    value, win, dead = evaluate_terminal(state.battle_array)
    return float(value), int(win), int(dead)


def _battle_task(task):
    values, name, iters, seed = task
    _set_values(values)
    return battle_task((name, iters, seed))


def _label(values):
    return f"c {values[0]}, root c {values[1]}"


def _playouts(report, pool, budget):
    """Checks the right answers themselves: both first moves, played to the end of the battle"""
    n = max(2, int(_PLAYOUT_BATTLES * budget.battle_fraction)) if budget.smoke else _PLAYOUT_BATTLES
    iters = min(_PLAYOUT_ITERS, budget.max_iters)
    rows = []
    for name, (_, right, tempting) in POSITIONS.items():
        for label, action in (("right", right[-1]), ("tempting", tempting)):
            tasks = [(name, action, iters, 400_000 + i) for i in range(n)]
            done = pool.map(_playout_task, tasks, chunksize=1)
            deaths = sum(d[2] for d in done) / n
            value = sum(d[0] for d in done) / n
            spread = _Z_95 * math.sqrt(max(deaths * (1 - min(deaths, 1)), 1e-9) / n)
            rows.append((name, label, f"{sum(d[1] for d in done) / n * 100:.1f}%",
                         f"{deaths:.3f} ± {spread:.3f}", f"{value:.3f}"))
            report.progress(rows[-1])
    report.text(f"Both first moves played out, {n} battles each, search at {iters:,} iterations per "
                "decision with today's values. The right move should show fewer deaths or more value.")
    report.table(("Position", "First move", "Win", "Deaths per battle", "Value"), rows)


def _score_positions(report, pool, budget, sets=_SETS):
    """Share of searches that pick a right action, per set. Returns {set: share over positions}"""
    sets = sets[:3] if budget.smoke else sets
    seeds = 2 if budget.smoke else _SEEDS
    iters = budget.max_iters if budget.smoke else _POSITION_ITERS
    scores, rows = {}, []
    for values in sets:
        hits = []
        cells = []
        for name, (_, right, _) in POSITIONS.items():
            tasks = [(values, name, iters, 500_000 + i) for i in range(seeds)]
            good = sum(pick in right for pick in pool.map(_position_task, tasks, chunksize=1))
            hits.append(good)
            cells.append(f"{good}/{seeds}")
        scores[values] = sum(hits) / (seeds * len(POSITIONS))
        rows.append((_label(values), *cells, f"{scores[values] * 100:.0f}%"))
        report.metric(f"tuning/positions/{_label(values)}", scores[values])
        report.progress(rows[-1])
    report.text(f"Searches that picked a right action, {seeds} per position, backend's stop rule, "
                f"at most {iters:,} iterations.")
    report.table(("Values", *POSITIONS, "All"), rows)
    return scores


def _stop_rule(report, pool, budget, sets):
    """A larger c at the root spreads the visits, which could delay the stop rule the app waits on"""
    iters = budget.max_iters if budget.smoke else _POSITION_ITERS
    seeds = 2 if budget.smoke else _STOP_SEEDS
    rows = []
    for name in (*FIGHTS, *POSITIONS):
        for values in sets:
            tasks = [(values, name, iters, 600_000 + i) for i in range(seeds)]
            done = pool.map(_stop_task, tasks, chunksize=1)
            ran = sum(d[0] for d in done) / seeds
            report.metric(f"tuning/stop/{_label(values)}/{name}/iterations", ran)
            rows.append((
                name, _label(values), f"{ran:,.0f}", f"{sum(d[1] for d in done)}/{seeds}",
                f"{sum(d[2] for d in done) / seeds:.1f} s",
                f"{sum(d[3] for d in done) / seeds * 100:.0f}%",
            ))
            report.progress(rows[-1])
    report.text(f"How long a search runs under the backend's stop rule, {seeds} searches each, at most "
                f"{iters:,} iterations, on busy workers.")
    report.table(("Where", "Values", "Iterations", "Stopped", "Time", "Top action's visits"), rows)


def _battles(pool, values, name, iters, n, first_seed=0):
    tasks = [(values, name, iters, 100_000 * iters + first_seed + i) for i in range(n)]
    done = list(pool.imap_unordered(_battle_task, tasks, chunksize=1))
    wins = sum(r[1] for r in done)
    return {
        "wins": wins, "n": n, "value": sum(r[0] for r in done) / n,
        "deaths": sum(r[2] for r in done if r[1]) / wins if wins else 0.0,
    }


def _significantly_worse(wins, n, base_wins, base_n):
    """Two-proportion test of a set's win rate against today's"""
    pooled = (wins + base_wins) / (n + base_n)
    spread = math.sqrt(max(pooled * (1 - pooled), 1e-9) * (1 / n + 1 / base_n))
    return (base_wins / base_n - wins / n) / spread > _Z_95


def _rank_key(result, base):
    """Fewest deaths per win among sets that don't lose significantly more, then best value"""
    worse = any(
        _significantly_worse(result[f]["wins"], result[f]["n"], base[f]["wins"], base[f]["n"])
        for f in result
    )
    deaths = sum(r["deaths"] for r in result.values()) / len(result)
    value = sum(r["value"] for r in result.values()) / len(result)
    return (worse, deaths, -value)


def _stage(report, pool, budget, sets, iters, n, first_seed=0):
    """Full battles per set. Returns the sets from best to worst"""
    iters = min(iters, budget.max_iters)
    n = max(2, int(n * budget.battle_fraction)) if budget.smoke else n
    results, rows = {}, []
    for values in sets:
        results[values] = {f: _battles(pool, values, f, iters, n, first_seed) for f in _FIGHTS}
        for fight_name, r in results[values].items():
            key = f"tuning/{iters}/{first_seed}/{_label(values)}/{fight_name}"
            low, high = _wilson(r["wins"], r["n"])
            report.metric(f"{key}/win", r["wins"] / r["n"])
            report.metric(f"{key}/deaths_per_win", r["deaths"])
            rows.append((
                _label(values), fight_name, f"{r['wins'] / r['n'] * 100:.1f}%",
                f"{low * 100:.1f}-{high * 100:.1f}%", f"{r['deaths']:.2f}", f"{r['value']:.3f}",
            ))
            report.progress(rows[-1])
    base = results[BASELINE]
    ranked = sorted(sets, key=lambda v: _rank_key(results[v], base))
    report.text(f"Full battles at {iters:,} iterations per decision, {n} each, same seeds for every set.")
    report.table(("Values", "Fight", "Win", "95% CI", "Deaths per win", "Value"), rows)
    report.text("Best first, by fewest deaths per win among sets with no significant loss of wins: "
                + "; ".join(_label(v) for v in ranked[:5]) + ".")
    return ranked


def run(report, budget):
    """Playouts to check the answers, every set on the positions, the best in full battles, then
    the best other set against today's on unused seeds and under the stop rule"""
    report.heading("Tuning best_action")
    _, pool = _pool()
    with pool:
        _playouts(report, pool, budget)
        report.save()
        scores = _score_positions(report, pool, budget)
        report.save()

        by_score = sorted(scores, key=lambda v: -scores[v])
        iters, n, keep = _STAGE_2
        chosen = [v for v in by_score if v != BASELINE][:1 if budget.smoke else keep - 1]
        ranked = _stage(report, pool, budget, [BASELINE] + chosen, iters, n)
        report.save()

        iters, n, keep = _STAGE_3
        finalists = [v for v in ranked if v != BASELINE][:1 if budget.smoke else keep]
        ranked = _stage(report, pool, budget, [BASELINE] + finalists, iters, n)
        report.save()

        best = next(v for v in ranked if v != BASELINE)
        _stage(report, pool, budget, [BASELINE, best], iters, n, _FRESH_FIRST_SEED)
        report.save()
        _stop_rule(report, pool, budget, (BASELINE, best))
    report.text(f"Best at the end: {_label(ranked[0])}. Today's: {_label(BASELINE)}.")
