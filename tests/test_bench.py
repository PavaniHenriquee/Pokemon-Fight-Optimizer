"""The benchmarks keep working: the fights still build and a battle still finishes. The compiled
run is `python -m benchmarks.run all --smoke`."""
import json
import pytest
from Engine.damage_calc import calculate_damage
from Engine.speed import check_speed
from Models.idx_const import FIELD_LEN, MOVE_STRIDE, OFFSET_MOVE, POK_LEN, Pok
from SearchEngine import my_mcts
from SearchEngine.models import ACTION_SLOT, Node, valid_action_mask
from benchmarks.fights import FIGHTS, fight, seed_all
from benchmarks.play import MAX_DECISIONS, play
from benchmarks.report import Report
from benchmarks.tuning import _SETS, BASELINE, POSITIONS, _rank_key, _set_values, position


def test_every_fight_builds():
    """TrainerDB edits can remove what a fight is made of"""
    for name in FIGHTS:
        assert fight(name).size == 12 * POK_LEN + FIELD_LEN, name


def test_tuning_positions_build():
    """Each one has its named HP and its actions can be picked, so its answer still means something"""
    expected = {
        "Dawn, Eevee 9/30, foe 9/31": (9, 30, 9, 31),
        "Dawn, Eevee 15/30, foe 9/31": (15, 30, 9, 31),
        "Dawn, Eevee 15/30, foe 31/31": (15, 30, 31, 31),
        "Dawn, Chimchar 11/28, foe 18/31 (stay)": (11, 28, 18, 31),
    }
    for name, (_, right, tempting) in POSITIONS.items():
        battle = position(name)
        mask = valid_action_mask(battle)
        assert battle.size == 12 * POK_LEN + FIELD_LEN, name
        for action in (*right, tempting):
            assert mask >> ACTION_SLOT[action] & 1, (name, action)
        if name in expected:
            foe = battle[6 * POK_LEN:7 * POK_LEN]
            got = (battle[Pok.CURRENT_HP], battle[Pok.MAX_HP], foe[Pok.CURRENT_HP], foe[Pok.MAX_HP])
            assert got == expected[name], name


@pytest.mark.parametrize("name", [n for n in POSITIONS if n.startswith("Crit")])
def test_tuning_crit_positions_only_die_to_a_crit(name):
    """The point of these three: a normal Tackle can't kill, a crit always does, the foe goes first"""
    battle = position(name)
    me = battle[0:POK_LEN]
    foe = battle[6 * POK_LEN:7 * POK_LEN]
    move = foe[OFFSET_MOVE:OFFSET_MOVE + MOVE_STRIDE]
    normal = [calculate_damage(foe, me, move, 0, False, None, 0, False) for _ in range(200)]
    crit = [calculate_damage(foe, me, move, 0, True, None, 0, False) for _ in range(200)]
    assert max(normal) < me[Pok.CURRENT_HP] <= min(crit)
    my_speed, foe_speed = check_speed(me, foe, 0)
    assert foe_speed > my_speed


def test_tuning_sets_are_valid():
    """Today's values are compared against, and no set is tried twice"""
    assert BASELINE in _SETS
    assert len(set(_SETS)) == len(_SETS)


def test_tuning_rank_prefers_fewer_deaths_unless_wins_drop():
    """Deaths decide, but a significant loss of wins comes last whatever its deaths"""
    def result(wins, deaths):
        return {"fight": {"wins": wins, "n": 300, "deaths": deaths, "value": 0.5}}
    base = result(280, 1.0)
    fewer_deaths = _rank_key(result(280, 0.5), base)
    same = _rank_key(base, base)
    loses_wins = _rank_key(result(200, 0.1), base)
    assert sorted([loses_wins, same, fewer_deaths]) == [fewer_deaths, same, loses_wins]


def test_tuning_values_reach_the_search(monkeypatch):
    """_set_values writes where selection reads, in both places"""
    monkeypatch.setattr(Node.best_action, "__defaults__", Node.best_action.__defaults__)
    monkeypatch.setattr(my_mcts, "ROOT_C", my_mcts.ROOT_C)
    _set_values((0.5, 2.0))
    assert Node.best_action.__defaults__ == (0.5,)
    assert my_mcts.ROOT_C == 2.0


def test_battle_finishes_and_repeats():
    """Same seed, same battle: the win rate table relies on it"""
    results = []
    for _ in range(2):
        seed_all(5)
        results.append(play(fight("Dallas"), 4))
    value, win, _, decisions, searched, _ = results[0]
    assert 0.0 <= value <= 1.0
    assert win in (0, 1)
    assert 0 < searched <= decisions < MAX_DECISIONS
    assert results[0][:5] == results[1][:5]


def _report(results_dir, cpu="same"):
    return Report(["search"], results_dir=results_dir, machine={"cpu": cpu})


def _save_earlier(folder, stamp, cpu, metrics, budget="default"):
    data = {
        "stamp": stamp, "budget": budget, "sections": [], "machine": {"cpu": cpu},
        "metrics": metrics,
    }
    (folder / f"{stamp}.json").write_text(json.dumps(data), encoding="utf-8")


def test_report_compares_with_the_latest_run_on_this_cpu(tmp_path):
    """The newest value of a metric wins. Other machines and other budgets don't count"""
    _save_earlier(tmp_path, "2000-01-01_0000", "same", {"a": 1.0, "b": 10.0})
    _save_earlier(tmp_path, "2000-01-02_0000", "same", {"a": 2.0})
    _save_earlier(tmp_path, "2000-01-03_0000", "other", {"a": 100.0})
    _save_earlier(tmp_path, "2000-01-04_0000", "same", {"a": 200.0}, budget="long")
    report = _report(str(tmp_path))
    report.metric("a", 3.0)
    report.metric("b", 5.0)
    report.metric("new", 1.0)
    assert report.changes() == [("a", 2.0, 3.0, pytest.approx(50.0)),
                                ("b", 10.0, 5.0, pytest.approx(-50.0))]


def test_report_saves_both_files(tmp_path):
    """A report reads on its own and the next run can load it"""
    report = _report(str(tmp_path))
    report.heading("Section")
    report.table(("A", "B"), [(1, "two")])
    report.metric("a", 1.5)
    report.save()
    saved = json.loads((tmp_path / f"{report.stamp}.json").read_text(encoding="utf-8"))
    assert saved["metrics"] == {"a": 1.5}
    text = (tmp_path / f"{report.stamp}.md").read_text(encoding="utf-8")
    assert "## Section" in text and "| two |" in text


def test_smoke_report_saves_nothing(tmp_path):
    """--smoke numbers mean nothing, so they never become the baseline"""
    report = _report(None)
    report.metric("a", 1.0)
    report.save()
    assert not report.changes()
    assert not list(tmp_path.iterdir())
