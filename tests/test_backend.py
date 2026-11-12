"""FastAPI endpoints and the tree serializer the frontend depends on.
The real UserData/box.json and nuzlocke.json are never written: their paths point to temp files."""
import json
import os
import pytest
from fastapi.testclient import TestClient
from backend import main
from backend.serializer import serialize_node, opp_move_label, battle_sprite
from SearchEngine.models import (
    GameState, Node, reconstruct_battle_array, OPP_DIDNT_MOVE, OPP_STRUGGLED, OPP_SWITCHED,
    OPP_USED_ITEM, OPP_TURN_BITS,
)
from SearchEngine.my_mcts import mcts_loop
from DataBase.AbilitiesDB import AbilityNames
from DataBase.PkDB import PokemonName
from Models.helper import Gender, Types, ActionType
from Models.idx_const import Pok, POK_LEN, Move
from battle_driver import build_scenario, pok_slice, move_slice

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
    """TestClient with the box and the run redirected to temp files and no leftover session"""
    monkeypatch.setattr(main, "_BOX_PATH", str(tmp_path / "box.json"))
    monkeypatch.setattr(main, "_NUZLOCKE_PATH", str(tmp_path / "nuzlocke.json"))
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
    assert set(data["moveInfo"]) == set(data["moves"])
    assert "Struggle" not in data["moves"]
    assert data["moveInfo"]["Ember"] == {"type": "Fire", "category": "Special", "power": 40,
                                         "accuracy": 100, "pp": 25}
    assert set(data["pokemonTypes"]) == set(data["pokemon"])
    assert data["pokemonTypes"]["Charmander"] == ["Fire"]
    assert data["pokemonTypes"]["Bulbasaur"] == ["Grass", "Poison"]
    assert set(data["pokemonAbilities"]) == set(data["pokemon"])
    assert data["pokemonAbilities"]["Bulbasaur"] == ["Chlorophyll", "Overgrow"]
    assert set(a for abs_ in data["pokemonAbilities"].values() for a in abs_) <= set(data["abilities"])
    assert data["pokemonAbilities"]["Zubat"] == ["Inner Focus"]  # PkDB lists it twice
    assert all(len(set(abs_)) == len(abs_) for abs_ in data["pokemonAbilities"].values())
    assert set(data["learnsets"]) == set(data["pokemon"])
    assert data["learnsets"]["Bulbasaur"][:3] == [[1, "Tackle"], [1, "Growl"], [5, "Vine Whip"]]
    assert "Magnemite" in data["genderless"] and "Bulbasaur" not in data["genderless"]


def test_trainers(client):
    """Trainer list is TrainerDB.json as-is, plus what a trainer lacks"""
    data = client.get("/trainers").json()
    assert "Gym Leader Roark 1" in data
    assert all("team" in t for t in data.values())
    assert "lacks" not in data["Gym Leader Roark 1"]
    assert "Detect" in data["Commander Mars 1"]["lacks"]
    assert all(t["lacks"] for t in data.values() if "lacks" in t)


def test_box_round_trip(client, tmp_path):
    """POST /box then GET /box returns the same entries (temp file only)"""
    assert client.get("/box").json() == []
    entry = {**TEAM_MEMBER, "id": "abc"}
    entry.pop("item")
    assert client.post("/box", json=[entry]).json() == {"status": "saved"}
    got = client.get("/box").json()
    assert len(got) == 1 and got[0]["name"] == "Charmander" and got[0]["id"] == "abc"
    assert json.loads((tmp_path / "box.json").read_text(encoding="utf-8")) == got


def test_box_keeps_the_held_item(client):
    """A party's item edit reaches the box, an entry without one has none"""
    entry = {**TEAM_MEMBER, "id": "a"}
    plain = {**TEAM_MEMBER, "id": "b"}
    plain.pop("item")
    assert client.post("/box", json=[entry, plain]).json() == {"status": "saved"}
    got = {e["id"]: e["item"] for e in client.get("/box").json()}
    assert got == {"a": "Oran Berry", "b": None}


def test_build_battle_ignores_a_gender_on_a_genderless_species():
    """A box saved before PkDB knew it can still say Male: Rivalry and Attract must not see that"""
    def config(name):
        return main.PokemonConfig(name=name, gender="Male", ability="Sturdy", moves=["Tackle"])
    battle = main._build_battle(main.BattleConfig(  # pylint: disable=protected-access
        my_team=[config("Magnemite"), config("Geodude")], opp_team=[config("Geodude")],
    ))
    assert battle[Pok.GENDER] == Gender.GENDERLESS
    assert battle[POK_LEN + Pok.GENDER] == Gender.MALE


@pytest.mark.parametrize("name, item, ability, form, form_ability", [
    ("Giratina", "Griseous Orb", "Pressure", "Giratina_origin", "Levitate"),
    ("Giratina_origin", None, "Levitate", "Giratina", "Pressure"),
    ("Giratina", None, "Pressure", "Giratina", "Pressure"),
    ("Giratina_origin", "Griseous Orb", "Levitate", "Giratina_origin", "Levitate"),
])
def test_build_battle_sets_giratina_form_by_its_item(name, item, ability, form, form_ability):
    """[pp] BoxPokemon_SetGiratinaForm: Origin (Levitate) with a Griseous Orb, Altered (Pressure)
    without, whatever the box says"""
    mon = main.PokemonConfig(name=name, ability=ability, moves=["Tackle"], item=item)
    foe = main.PokemonConfig(name="Geodude", ability="Sturdy", moves=["Tackle"])
    battle = main._build_battle(main.BattleConfig(  # pylint: disable=protected-access
        my_team=[mon], opp_team=[foe],
    ))
    assert battle[Pok.ID] == getattr(PokemonName, form.upper())
    assert battle[Pok.AB_ID] == getattr(AbilityNames, form_ability.upper())


def test_box_keeps_the_death_box(client):
    """The death box is the same file: dead round-trips, and an entry without it isn't dead"""
    alive = {**TEAM_MEMBER, "id": "a"}
    alive.pop("item")
    dead = {**alive, "id": "b", "dead": True}
    assert client.post("/box", json=[alive, dead]).json() == {"status": "saved"}
    got = {entry["id"]: entry["dead"] for entry in client.get("/box").json()}
    assert got == {"a": False, "b": True}


def test_box_empty_file_is_an_empty_box(client, tmp_path):
    """The committed box.json is 0 bytes: the app starts with an empty box"""
    (tmp_path / "box.json").write_text("", encoding="utf-8")
    assert client.get("/box").json() == []


def test_box_unreadable_file_is_an_error_not_an_empty_box(client, tmp_path):
    """An empty answer would let the next save wipe the file"""
    (tmp_path / "box.json").write_text('[{"name": "Starly"', encoding="utf-8")
    response = client.get("/box")
    assert response.status_code == 500 and "box.json" in response.json()["detail"]
    assert (tmp_path / "box.json").read_text(encoding="utf-8") == '[{"name": "Starly"'


def test_encounters(client):
    """Encounter data is EncounterDB.json as-is, in the sheet's order"""
    data = client.get("/encounters").json()
    assert data["starters"] == ["Turtwig", "Chimchar", "Piplup"]
    assert list(data["locations"])[0] == "Route 201"


def test_nuzlocke_without_a_file_is_an_empty_run(client):
    """A new run: no starter, no gender, every location open"""
    assert client.get("/nuzlocke").json() == {
        "player": "",
        "starter": {"species": "", "status": "caught"},
        "encounters": {},
        "last_trainer": "",
        "items": [],
    }


def test_item_locations(client):
    """Item data is ItemLocationDB.json as-is, in story order"""
    data = client.get("/item-locations").json()
    assert list(data["locations"])[0] == "Lake Verity"
    assert data["locations"]["Oreburgh City"][-1]["item"] == "TM76"


def test_nuzlocke_round_trip(client, tmp_path):
    """POST /nuzlocke then GET /nuzlocke returns the same run (temp file only)"""
    run = {
        "player": "Female",
        "starter": {"species": "Piplup", "status": "caught"},
        "encounters": {
            "Route 201": {"species": "Starly", "status": "dead"},
            "Route 202": {"species": "", "status": "missed"},
        },
        "last_trainer": "Lass Natalie 1",
        "items": ["Route 203||Silk Scarf|"],
    }
    assert client.post("/nuzlocke", json=run).json() == {"status": "saved"}
    assert client.get("/nuzlocke").json() == run
    assert json.loads((tmp_path / "nuzlocke.json").read_text(encoding="utf-8")) == run
    assert not (tmp_path / "nuzlocke.json.tmp").exists()


def test_nuzlocke_loads_a_run_saved_with_nicknames(client, tmp_path):
    """Runs saved before nicknames were removed still load, the nickname is just dropped"""
    old = {"player": "", "starter": {"species": "Piplup", "nickname": "Pip", "status": "caught"}, "encounters": {}}
    (tmp_path / "nuzlocke.json").write_text(json.dumps(old), encoding="utf-8")
    assert client.get("/nuzlocke").json()["starter"] == {"species": "Piplup", "status": "caught"}


def test_nuzlocke_loads_a_run_saved_before_last_trainer(client, tmp_path):
    """Runs saved before the last trainer was kept still load, with none picked"""
    old = {"player": "Male", "starter": {"species": "Piplup", "status": "caught"}, "encounters": {}}
    (tmp_path / "nuzlocke.json").write_text(json.dumps(old), encoding="utf-8")
    assert client.get("/nuzlocke").json() == {**old, "last_trainer": "", "items": []}


@pytest.mark.parametrize("text", ["", "{ not json", '{"player": "Nobody"}'])
def test_nuzlocke_unreadable_file_is_an_error_not_an_empty_run(client, tmp_path, text):
    """The tracker saves every change, so an empty answer would end up replacing the real run"""
    (tmp_path / "nuzlocke.json").write_text(text, encoding="utf-8")
    assert client.get("/nuzlocke").status_code == 500
    assert (tmp_path / "nuzlocke.json").read_text(encoding="utf-8") == text


def test_nuzlocke_rejects_an_unknown_status(client, tmp_path):
    """A bad save is refused and leaves the file alone"""
    bad = {"encounters": {"Route 201": {"species": "Starly", "status": "lost"}}}
    assert client.post("/nuzlocke", json=bad).status_code == 422
    assert not (tmp_path / "nuzlocke.json").exists()


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


def test_start_refuses_what_the_engine_lacks(client):
    """An opponent with a move the engine can't run is refused before the running search is touched"""
    foe = {**OPP_MEMBER, "moves": ["Tackle", "Detect"]}
    res = client.post("/start", json={"my_team": [TEAM_MEMBER], "opp_team": [foe], "iterations": 10}).json()
    assert res == {"status": "error", "error": "Not supported yet: Detect"}


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


def _pack(*turns):
    """step_arr's answer for these (foe's party slot, what it did, PP paid), oldest first"""
    did = 0
    for foe, what, paid in turns:
        did = did << OPP_TURN_BITS | ((foe << 5 | what << 2 | paid) + 1)
    return did


TACKLE = _pack((0, 1, 1))
TAIL_WHIP = _pack((0, 2, 1))


def _merged_node(client):
    """A finished tiny search and one of its outcome nodes, made to look like Tackle and Tail Whip
    merged into it, its snapshot coming from a visit that used Tackle"""
    client.post("/start", json={
        "my_team": [TEAM_MEMBER], "opp_team": [OPP_MEMBER], "iterations": 60,
    })
    sess = main._session  # pylint: disable=protected-access
    _wait(sess)
    node = next(iter(sess.root.children.values()))[0]
    node.opp_moves = {TACKLE: 3, TAIL_WHIP: 1}
    node.snapshot.opp_move_idx = TACKLE
    return sess, node


def _foe_pp(battle):
    foe = pok_slice(battle, 0, True)
    return [int(move_slice(foe, m)[Move.PP]) for m in (0, 1)]


def _continue_foe_pp(client, sess, node, **extra):
    """Foe's PP in the search that starts from the node"""
    res = client.post("/continue_from_node", json={
        "node_id": str(id(node)), "iterations": 5, "my_active_hp": 5, "opp_active_hp": 7,
        "bench_hps": {}, **extra,
    }).json()
    assert res == {"status": "started"}
    new_sess = main._session  # pylint: disable=protected-access
    assert new_sess is not sess
    _wait(new_sess)
    return _foe_pp(new_sess.battle_array)


def test_continue_charges_the_move_picked_on_the_path(client):
    """The root's PP minus the move the path says, not the visit that made the node"""
    sess, node = _merged_node(client)
    tackle, tail_whip = _foe_pp(sess.battle_array)
    path = [{"node_id": str(id(node)), "opp_move": "Tail Whip"}]
    assert _continue_foe_pp(client, sess, node, path=path) == [tackle, tail_whip - 1]


def test_continue_with_a_label_it_doesnt_know_takes_the_most_seen_move(client):
    """A step always has a move when the node saw one"""
    sess, node = _merged_node(client)
    tackle, tail_whip = _foe_pp(sess.battle_array)
    path = [{"node_id": str(id(node)), "opp_move": "Nope"}]
    assert _continue_foe_pp(client, sess, node, path=path) == [tackle - 1, tail_whip]


@pytest.mark.parametrize("stale_path", [False, True])
def test_continue_without_the_path_is_the_snapshot(client, stale_path):
    """No clicks to go by, or a node that isn't where they say"""
    sess, node = _merged_node(client)
    expected = _foe_pp(reconstruct_battle_array(node.snapshot, sess.battle_array))
    extra = {"path": [{"node_id": "gone", "opp_move": "Tackle"}]} if stale_path else {}
    assert _continue_foe_pp(client, sess, node, **extra) == expected


@pytest.mark.parametrize("did, label", [
    (_pack((0, OPP_DIDNT_MOVE, 0)), "Didn't move"),
    (_pack((0, 2, 1)), "Tail Whip"),
    (_pack((0, OPP_STRUGGLED, 0)), "Struggle"),
    (_pack((0, OPP_SWITCHED, 0)), "Switched"),
    (_pack((0, OPP_USED_ITEM, 0)), "Used item"),
    (_pack((0, 1, 1), (0, 2, 0)), "Tackle, then Tail Whip"),
    (_pack((0, 1, 1), (0, OPP_DIDNT_MOVE, 0)), "Tackle, then didn't move"),
    (_pack((0, OPP_DIDNT_MOVE, 0), (1, 1, 1)), "Didn't move, then Bulbasaur: Tackle"),
])
def test_opp_move_label(did, label):
    """Named from the foe that moved in that turn, also when another one is in by the end"""
    battle = main._build_battle(main.BattleConfig(  # pylint: disable=protected-access
        my_team=[TEAM_MEMBER],
        opp_team=[OPP_MEMBER, {**OPP_MEMBER, "name": "Bulbasaur", "ability": "Overgrow"}],
    ))
    assert opp_move_label(did, battle) == label


def _tree_with(counts_per_child):
    """The serialized root of a tree whose only action has these outcomes, (opp_moves, win_chance)"""
    battle = main._build_battle(main.BattleConfig(  # pylint: disable=protected-access
        my_team=[TEAM_MEMBER], opp_team=[OPP_MEMBER]
    ))
    state = GameState(battle)
    root = Node(state)
    children = []
    for counts, win in counts_per_child:
        child = Node(state.clone().step((1, 0)))
        child.opp_moves = counts
        child.win_chance = win
        child.visits = sum(counts.values())
        children.append(child)
    root.children[(1, 0)] = children
    tree = serialize_node(root, battle)
    json.dumps(tree)
    return tree


def test_outcome_rows_add_up_what_the_foe_did_over_the_outcomes():
    """A move on two outcomes is one row, with its visits and the win chance weighted by them, most
    often first. Every node also says how often each row got to it"""
    tree = _tree_with([({TACKLE: 6, TAIL_WHIP: 2}, 0.5), ({TACKLE: 2}, 1.0)])
    assert tree["opp_moves"] == {}
    action = tree["actions"]["1_0"]
    assert action["opp_moves"] == [
        {"label": "Tackle", "visits": 8, "win_chance": 0.625},
        {"label": "Tail Whip", "visits": 2, "win_chance": 0.5},
    ]
    assert [n["opp_moves"] for n in action["nodes"]] == [{"Tackle": 6, "Tail Whip": 2}, {"Tackle": 2}]


def test_outcome_rows_keep_two_equal_moves_in_place():
    """First seen first, so they don't swap on every update"""
    rows = _tree_with([({TAIL_WHIP: 2, TACKLE: 2}, 0.5)])["actions"]["1_0"]["opp_moves"]
    assert [r["label"] for r in rows] == ["Tail Whip", "Tackle"]


def test_outcome_rows_join_the_same_move_paying_different_pp():
    """Locked in some visits and not in others: it's still one thing the foe did"""
    rows = _tree_with([({TACKLE: 2, _pack((0, 1, 0)): 3}, 0.5)])["actions"]["1_0"]["opp_moves"]
    assert rows == [{"label": "Tackle", "visits": 5, "win_chance": 0.5}]


def test_no_outcome_rows_without_a_foe_turn():
    """I only picked a replacement"""
    assert _tree_with([({}, 0.5)])["actions"]["1_0"]["opp_moves"] == []


def test_max_pp_covers_every_move():
    """Every MoveDB move has its base PP, hyphenated names (Mud-Slap, Will-O-Wisp) included"""
    from backend.serializer import _MOVE_ID_TO_MAX_PP  # pylint: disable=import-outside-toplevel
    from DataBase.MoveDB import MoveName  # pylint: disable=import-outside-toplevel
    from DataBase.loader import moveDB  # pylint: disable=import-outside-toplevel
    missing = [k for k, e in moveDB.items()
               if _MOVE_ID_TO_MAX_PP.get(getattr(MoveName, e["name"].upper())) != e["pp"]]
    assert not missing, missing
    assert _MOVE_ID_TO_MAX_PP[MoveName.MUD_SLAP] == 10
    assert _MOVE_ID_TO_MAX_PP[MoveName.WILL_O_WISP] == 15


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
    assert snap["my"]["types"] == ["Fire"] and snap["my"]["level"] > 0
    for bench in snap["my_bench"] + snap["opp_bench"]:
        assert bench["types"], bench["name"]
    for mv in snap["my"]["moves"]:
        for key in ("name", "pp", "max_pp", "type", "category", "power"):
            assert key in mv
        assert mv["type"] and mv["category"] in ("Physical", "Special", "Status")
    assert tree["actions"], "root should list its explored actions"
    for act in tree["actions"].values():
        for key in ("action_type", "action_idx", "label", "total_visits", "win_chance",
                    "nodes", "move_type", "category", "power"):
            assert key in act
        assert 0.0 <= act["win_chance"] <= 1.0
        if act["action_type"] == 1 and act["label"] != "Struggle":
            assert act["move_type"] and act["category"], act["label"]
        else:
            assert act["move_type"] is None, act["label"]
    ember = [a for a in tree["actions"].values() if a["label"] == "Ember"]
    if ember:
        assert (ember[0]["move_type"], ember[0]["category"], ember[0]["power"]) == (
            "Fire", "Special", 40)


def test_snapshot_has_ability_and_gender():
    """The battle view's hover cards read these: a changed ability shows, genderless is None"""
    battle = build_scenario("starters")
    battle[Pok.GENDER] = Gender.FEMALE
    battle[Pok.AB_ID] = AbilityNames.ROCK_HEAD
    opp_first = 6 * POK_LEN
    battle[opp_first + Pok.GENDER] = Gender.GENDERLESS
    root_state = GameState(battle)
    root = Node(root_state)
    mcts_loop(root, root_state, max_iterations=20, terminal_iterations=10**9)
    snap = serialize_node(root, root_state.battle_array, min_visits=1, max_depth=1)["snapshot"]
    json.dumps(snap)
    assert snap["my"]["gender"] == "Female"
    assert snap["my"]["ability"] == "Rock Head"
    assert snap["opp"]["gender"] is None
    assert snap["opp"]["ability"]
    for bench in snap["my_bench"] + snap["opp_bench"]:
        assert bench["ability"], bench["name"]
        assert "gender" in bench


def test_warm_up_runs_a_throwaway_search(monkeypatch, capsys):
    """The startup warm-up builds its battle and searches without touching the real session"""
    monkeypatch.setattr(main, "_session", None)
    monkeypatch.setattr(main, "_WARMUP_CONFIG",
                        main._WARMUP_CONFIG.model_copy(update={"iterations": 20}))  # pylint: disable=protected-access
    main._warm_up()  # pylint: disable=protected-access
    assert "engine ready" in capsys.readouterr().out
    assert main._session is None and not main._warmup_running  # pylint: disable=protected-access


def test_no_warm_up_with_jit_off(client):
    """pytest runs with NUMBA_DISABLE_JIT=1, so the lifespan never starts the warm-up thread"""
    assert client.get("/box").status_code == 200
    assert not main._warmup_running  # pylint: disable=protected-access


def test_cache_dir_is_keyed_by_sources(tmp_path):
    """A source edit gets a new cache folder and the old one is deleted"""
    from Utils.jit_cache import cache_dir  # pylint: disable=import-outside-toplevel
    (tmp_path / "Engine").mkdir()
    src = tmp_path / "Engine" / "a.py"
    src.write_text("x = 1")
    first = cache_dir("backend", ("Engine",), str(tmp_path))
    os.makedirs(first)
    assert cache_dir("backend", ("Engine",), str(tmp_path)) == first
    src.write_text("x = 2")
    second = cache_dir("backend", ("Engine",), str(tmp_path))
    assert second != first and not os.path.exists(first)


def test_cache_root_moves_the_cache(tmp_path):
    """PBO_CACHE_ROOT's folder replaces the repo's .numba_cache (the Electron app)"""
    from Utils.jit_cache import cache_dir  # pylint: disable=import-outside-toplevel
    (tmp_path / "src" / "Engine").mkdir(parents=True)
    (tmp_path / "src" / "Engine" / "a.py").write_text("x = 1")
    path = cache_dir("backend", ("Engine",), str(tmp_path / "src"), cache_root=str(tmp_path / "cache"))
    assert os.path.dirname(path) == str(tmp_path / "cache" / "backend")


def test_box_path_env(monkeypatch, tmp_path):
    """PBO_BOX_PATH overrides UserData/box.json"""
    monkeypatch.setenv("PBO_BOX_PATH", str(tmp_path / "box.json"))
    assert main._box_path() == str(tmp_path / "box.json")  # pylint: disable=protected-access
    monkeypatch.delenv("PBO_BOX_PATH")
    assert main._box_path().endswith(os.path.join("UserData", "box.json"))  # pylint: disable=protected-access


def test_nuzlocke_path_env(monkeypatch, tmp_path):
    """PBO_NUZLOCKE_PATH overrides UserData/nuzlocke.json"""
    monkeypatch.setenv("PBO_NUZLOCKE_PATH", str(tmp_path / "nuzlocke.json"))
    assert main._nuzlocke_path() == str(tmp_path / "nuzlocke.json")  # pylint: disable=protected-access
    monkeypatch.delenv("PBO_NUZLOCKE_PATH")
    assert main._nuzlocke_path().endswith(os.path.join("UserData", "nuzlocke.json"))  # pylint: disable=protected-access


def test_search_seed_env(monkeypatch):
    """PBO_SEED (dev.bat) makes searches repeat; without it (the installed app) they don't"""
    def draws():
        main._seed_search()  # pylint: disable=protected-access
        return [main.random.random() for _ in range(3)]

    monkeypatch.setenv("PBO_SEED", "37")
    assert draws() == draws()
    monkeypatch.delenv("PBO_SEED")
    main.random.seed(1)
    assert draws() != draws()


def test_exit_when_parent_closes(monkeypatch):
    """The backend exits once Electron's stdin pipe closes"""
    exits = []
    monkeypatch.setattr(main.os, "_exit", exits.append)
    read_fd, write_fd = os.pipe()
    os.write(write_fd, b"still open")
    os.close(write_fd)
    main._exit_when_parent_closes(read_fd)  # pylint: disable=protected-access
    os.close(read_fd)
    assert exits == [0]


def test_build_battle_friendship():
    """Mine default to 255, a trainer's to its species' base friendship, a given value wins"""
    def config(name, friendship=None):
        return main.PokemonConfig(name=name, ability="Cute Charm", moves=["Return"], friendship=friendship)
    battle = main._build_battle(main.BattleConfig(  # pylint: disable=protected-access
        my_team=[config("Lopunny"), config("Lopunny", 10)], opp_team=[config("Lopunny")],
    ))
    assert battle[Pok.FRIENDSHIP] == 255
    assert battle[POK_LEN + Pok.FRIENDSHIP] == 10
    assert battle[6 * POK_LEN + Pok.FRIENDSHIP] == 140


def test_box_entry_friendship_defaults_to_255():
    entry = main.BoxEntry(id="a", name="Lopunny")
    assert entry.friendship == 255


@pytest.mark.parametrize("m_type, sprite", [
    (Types.NORMAL, PokemonName.CASTFORM), (Types.FIRE, 10013), (Types.WATER, 10014), (Types.ICE, 10015),
])
def test_castform_sprite_follows_its_form(make_pokemon, m_type, sprite):
    """The battle view shows Castform's sunny, rainy or snowy form for the type Forecast gave it"""
    arr = make_pokemon("Castform", 30, "Forecast", ["Weather Ball"]).to_np()
    arr[Pok.TYPE1] = m_type
    assert battle_sprite(arr) == sprite
    assert battle_sprite(make_pokemon("Charmander", 30, "Blaze", ["Ember"]).to_np()) == PokemonName.CHARMANDER


def test_field_shows_trick_room_and_tailwind():
    """The battle view gets Trick Room's turns left and Tailwind among a side's timed conditions"""
    from backend.serializer import _field  # pylint: disable=import-outside-toplevel
    from Models.helper import SideCondition  # pylint: disable=import-outside-toplevel
    from Models.idx_const import Field  # pylint: disable=import-outside-toplevel
    arr = build_scenario("starters")
    arr[Field.TRICKROOM] = 4
    arr[Field.OPP_SIDE_COND] |= SideCondition.TAILWIND
    arr[Field.OPP_TAILWIND_TURNS] = 2
    field = _field(arr[Field.MY_POK:])
    assert field["trick_room_turns"] == 4
    assert {"name": "Tailwind", "turns": 2} in field["opp_side"]
    assert not field["my_side"]


def test_field_shows_spikes_layers():
    """Spikes carry their layers, like Toxic Spikes"""
    from backend.serializer import _field  # pylint: disable=import-outside-toplevel
    from Models.helper import SideCondition  # pylint: disable=import-outside-toplevel
    from Models.idx_const import Field  # pylint: disable=import-outside-toplevel
    arr = build_scenario("starters")
    arr[Field.MY_SIDE_COND] |= SideCondition.SPIKES
    arr[Field.MY_SPIKES] = 3
    field = _field(arr[Field.MY_POK:])
    assert {"name": "Spikes", "layers": 3} in field["my_side"]



def test_field_shows_wish_future_sight_and_stockpile():
    """Wish and Future Sight / Doom Desire show with their turns left, named by the move, and the
    stockpile count as a chip"""
    from backend.serializer import _field, _pok  # pylint: disable=import-outside-toplevel
    from Models.helper import SideCondition  # pylint: disable=import-outside-toplevel
    from Models.idx_const import Field, Pok, POK_LEN  # pylint: disable=import-outside-toplevel
    from DataBase.MoveDB import MoveName  # pylint: disable=import-outside-toplevel
    arr = build_scenario("starters")
    arr[Field.MY_SIDE_COND] |= SideCondition.WISH
    arr[Field.MY_WISH_TURNS] = 1
    arr[Field.OPP_SIDE_COND] |= SideCondition.FUTURE_SIGHT
    arr[Field.OPP_FUTURE_TURNS] = 2
    arr[Field.OPP_FUTURE_MOVE] = MoveName.DOOM_DESIRE
    field = _field(arr[Field.MY_POK:])
    assert {"name": "Wish", "turns": 1} in field["my_side"]
    assert {"name": "Doom Desire", "turns": 2} in field["opp_side"]
    mine = arr[0:POK_LEN]
    mine[Pok.STOCKPILE] = 2 + 4 * 2
    assert "Stockpile 2" in _pok(mine)["vol_status"]


def _spite_node(client, my_moves=("Spite", "Scratch", "", "")):
    """A finished tiny search and the outcome node of my first move, made to look like the foe used
    Tackle there"""
    client.post("/start", json={
        "my_team": [{**TEAM_MEMBER, "moves": list(my_moves)}], "opp_team": [OPP_MEMBER],
        "iterations": 60,
    })
    sess = main._session  # pylint: disable=protected-access
    _wait(sess)
    action, children = next((a, c) for a, c in sess.root.children.items() if tuple(a) == (ActionType.MOVE, 0))
    node = children[0]
    node.opp_moves = {TACKLE: 1}
    node.snapshot.opp_move_idx = TACKLE
    return sess, node, action


def test_spite_pp_suggests_four_less_on_the_move_used_that_turn(client):
    """After my Spite the foe's Tackle shows what it paid plus Spite's 4, Tail Whip the root's"""
    sess, node, _ = _spite_node(client)
    tackle, tail_whip = _foe_pp(sess.battle_array)
    path = [{"node_id": str(id(node)), "opp_move": "Tackle"}]
    rows = client.post("/spite_pp", json={"node_id": str(id(node)), "path": path}).json()["rows"]
    assert [r["slot"] for r in rows] == [0] and rows[0]["name"] == "Squirtle"
    assert [(m["move_slot"], m["name"], m["pp"]) for m in rows[0]["moves"]] == [
        (0, "Tackle", tackle - 5), (1, "Tail Whip", tail_whip)
    ]


def test_spite_pp_is_empty_without_my_spite(client):
    """Continue asks nothing when no step of the path is a Spite"""
    _, node, _ = _spite_node(client, ("Scratch", "Growl", "", ""))
    path = [{"node_id": str(id(node)), "opp_move": "Tackle"}]
    assert client.post("/spite_pp", json={"node_id": str(id(node)), "path": path}).json() == {
        "rows": []
    }


def test_continue_takes_the_pp_i_set(client):
    """opp_pp overrides the arithmetic for that move only"""
    sess, node, _ = _spite_node(client)
    tackle, _tail_whip = _foe_pp(sess.battle_array)
    path = [{"node_id": str(id(node)), "opp_move": "Tackle"}]
    assert _continue_foe_pp(client, sess, node, path=path, opp_pp={"0:1": 0}) == [tackle - 1, 0]
