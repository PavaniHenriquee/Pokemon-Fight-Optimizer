"""FastAPI endpoints and the tree serializer the frontend depends on.
The real UserData/box.json is never written: _BOX_PATH points to a temp file."""
import json
import pytest
from fastapi.testclient import TestClient
from backend import main
from backend.serializer import serialize_node
from SearchEngine.models import GameState, Node
from SearchEngine.my_mcts import mcts_loop
from Models.idx_const import Pok
from battle_driver import build_scenario

TEAM_MEMBER = {
    "name": "Charmander", "gender": "Male", "level": 5, "ability": "Blaze",
    "nature": "Hardy", "moves": ["Scratch", "Growl", "Ember", ""], "item": "Oran Berry",
}
OPP_MEMBER = {
    "name": "Squirtle", "gender": "Male", "level": 5, "ability": "Torrent",
    "nature": "Hardy", "moves": ["Tackle", "Tail Whip", "", ""],
}


@pytest.fixture
def client(monkeypatch, tmp_path):
    """TestClient with the box redirected to a temp file and no leftover session"""
    monkeypatch.setattr(main, "_BOX_PATH", str(tmp_path / "box.json"))
    monkeypatch.setattr(main, "_session", None)
    with TestClient(main.app) as c:
        yield c
    sess = main._session  # pylint: disable=protected-access
    if sess is not None:
        sess.stop_event.set()
        if sess.thread is not None:
            sess.thread.join(10)


def _wait(sess):
    sess.thread.join(60)
    assert not sess.thread.is_alive(), "MCTS thread didn't finish"
    assert sess.error is None, sess.error


def test_pokemon_data(client):
    """Team builder dropdown data is complete and consistent"""
    data = client.get("/pokemon-data").json()
    for key in ("pokemon", "moves", "natures", "abilities", "items", "nameToId",
                "baseStats", "natureMultipliers"):
        assert data[key], key
    assert "Charmander" in data["pokemon"] and "Ember" in data["moves"]
    assert set(data["nameToId"]) <= set(data["pokemon"])
    assert data["baseStats"]["Charmander"]["HP"] == 39


def test_trainers(client):
    """Trainer list is TrainerDB.json as-is"""
    data = client.get("/trainers").json()
    assert "Gym Leader Roark 1" in data
    assert all("team" in t for t in data.values())


def test_box_round_trip(client, tmp_path):
    """POST /box then GET /box returns the same entries (temp file only)"""
    assert client.get("/box").json() == []
    entry = {**TEAM_MEMBER, "id": "abc"}
    entry.pop("item")
    assert client.post("/box", json=[entry]).json() == {"status": "saved"}
    got = client.get("/box").json()
    assert len(got) == 1 and got[0]["name"] == "Charmander" and got[0]["id"] == "abc"
    assert json.loads((tmp_path / "box.json").read_text(encoding="utf-8")) == got


def test_no_session_endpoints(client):
    """Endpoints that need a run answer cleanly without one"""
    assert client.get("/node_info/123").json() == {"error": "no active battle"}
    assert client.post("/stop").json() == {"status": "stopped"}


def test_start_rejects_bad_config(client):
    """Unknown species reports an error instead of crashing"""
    bad = {**TEAM_MEMBER, "name": "NotAPokemon"}
    res = client.post("/start", json={"my_team": [bad], "opp_team": [OPP_MEMBER],
                                      "iterations": 10}).json()
    assert res["status"] == "error"


def test_start_node_info_and_continue(client):
    """Full happy path: start a tiny search, inspect the root, continue from it"""
    res = client.post("/start", json={
        "my_team": [TEAM_MEMBER], "opp_team": [OPP_MEMBER, OPP_MEMBER],
        "iterations": 60, "trainer_items": ["Potion"],
    }).json()
    assert res == {"status": "started"}
    sess = main._session  # pylint: disable=protected-access
    _wait(sess)
    assert sess.iterations == 60 and sess.root.visits == 60

    root_id = str(id(sess.root))
    info = client.get(f"/node_info/{root_id}").json()
    assert info["my_active"]["name"] == "Charmander"
    assert info["opp_active"]["name"] == "Squirtle"
    assert client.get("/node_info/does-not-exist").json() == {"error": "node not found"}

    res = client.post("/continue_from_node", json={
        "node_id": root_id, "iterations": 30, "my_active_hp": 5, "opp_active_hp": 7,
        "bench_hps": {},
    }).json()
    assert res == {"status": "started"}
    new_sess = main._session  # pylint: disable=protected-access
    assert new_sess is not sess
    _wait(new_sess)
    assert new_sess.root.snapshot.my_slice[Pok.CURRENT_HP] == 5


def test_serialize_node_is_json_ready():
    """The tree payload sent over the websocket survives json.dumps and has the fields
    frontend/src/types.ts expects"""
    root_state = GameState(build_scenario("starters"))
    root = Node(root_state)
    mcts_loop(root, root_state, max_iterations=200, terminal_iterations=10**9)
    tree = serialize_node(root, root_state.battle_array, min_visits=1, max_depth=3)
    json.dumps(tree)
    for key in ("id", "visits", "wins", "win_chance", "dead_avg", "snapshot", "actions"):
        assert key in tree
    snap = tree["snapshot"]
    for key in ("phase", "my", "opp", "my_bench", "opp_bench", "trainer_items", "turn"):
        assert key in snap
    assert snap["my"]["name"] == "Charmander"
    assert tree["actions"], "root should list its explored actions"
    for act in tree["actions"].values():
        for key in ("action_type", "action_idx", "label", "total_visits", "win_chance",
                    "nodes"):
            assert key in act
        assert 0.0 <= act["win_chance"] <= 1.0
