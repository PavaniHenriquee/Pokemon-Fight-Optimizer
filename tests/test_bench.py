"""The benchmarks keep working: the fights still build and a battle still finishes. The compiled
run is `python -m benchmarks.run all --smoke`."""
import json
import pytest
from Models.idx_const import FIELD_LEN, POK_LEN
from benchmarks.fights import FIGHTS, fight, seed_all
from benchmarks.play import MAX_DECISIONS, play
from benchmarks.report import Report


def test_every_fight_builds():
    """TrainerDB edits can remove what a fight is made of"""
    for name in FIGHTS:
        assert fight(name).size == 12 * POK_LEN + FIELD_LEN, name


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
