"""The coverage report (DataBase/coverage.py): the plan reader, what trainers use, what my Pokemon can get"""
from DataBase import coverage

PLAN = """# Engine plan

## Phase 2: state and search capacity

- [ ] A note about the layout

## Phase 4: items

### 4.1 Simple held items

- [x] Life Orb
- [ ] Lagging Tail *
- [ ] No-effect items, only the ones a trainer holds
- [ ] Fling(B/E) !! (last: it needs every item's Fling data)

### 4.3 Berries

- [ ] Cheri Berry

## Phase 5: plain damage moves

- [ ] Crunch
- [ ] Hyper Beam (in MoveDB)

## To check in 1.3

- [ ] Twister (→ 6.3)
- [x] Brine: dropped, nothing has it
- [ ] Any other tutor move that a trainer team has

## Phase 13: trainer AI

- [ ] 13.1 Only if the tool shows it
"""


def _data(**changes):
    """A small world: two trainers, one route, one TM"""
    team = [{"name": "Geodude", "level": 10, "ability": "Sturdy", "item": "Life Orb",
             "moves": ["Tackle", "Crunch", "", ""]}]
    data = {
        "trainers": {
            "Youngster A 1": {"split": "Roark", "team": [{**team[0], "item": None, "moves": ["Tackle"]}]},
            "Hiker B 1": {"split": "Gardenia", "team": team, "trainer_items": ["Potion", "X Attack"]},
        },
        "encounters": {
            "starters": ["Turtwig"],
            "locations": {
                "Route 201": [{"method": "Grass", "mons": [{"name": "Geodude"}]}],
                "Pokémon League": [{"method": "Static Encounter (After Credits)", "mons": [{"name": "Mew"}]}],
                "Route 224": [{"method": "Grass", "mons": [{"name": "Sketcher"}]}],
            },
            "evolution_lines": [["Geodude", "Graveler", "Golem"], ["Turtwig", "Grotle", "Torterra"]],
        },
        "item_locations": {
            "Route 201": [{"kind": "tm", "item": "TM01", "move": "Cut"},
                          {"kind": "item", "item": "Lagging Tail"}],
            "Route 223": [],
            "Route 226": [{"kind": "item", "item": "Razor Fang"}],
        },
        "plan": PLAN,
        "pk": {
            "Geodude": {"abilities": ["Sturdy"], "learnset": [[1, "Tackle"]], "tutor": []},
            "Graveler": {"abilities": ["Sturdy"], "learnset": [[1, "Tackle"]], "tutor": ["Twister"]},
            "Golem": {"abilities": ["Sturdy"], "learnset": [], "tutor": []},
            "Turtwig": {"abilities": ["Overgrow"], "learnset": [[1, "Tackle"]], "tutor": []},
            "Grotle": {"abilities": ["Overgrow"], "learnset": [], "tutor": []},
            "Torterra": {"abilities": ["Overgrow"], "learnset": [], "tutor": []},
            "Mew": {"abilities": ["Synchronize"], "learnset": [[1, "Transform"]], "tutor": []},
            "Sketcher": {"abilities": ["Own Tempo"], "learnset": [[1, "Sketch"]], "tutor": []},
        },
        "moves": {"Tackle", "Cut"},
        "items": {"Life Orb"},
        "abilities": {"Sturdy", "Overgrow", "Synchronize", "Own Tempo", "Color Change"},
    }
    data.update(changes)
    return data


def test_parse_plan():
    """Phases 3-12 and the open "To check" lines only, the step from ### or the phase, the name before ( ! *,
    a * after it"""
    plan = coverage.parse_plan(PLAN)
    assert set(plan) == {
        "Life Orb", "Lagging Tail", "No-effect items, only the ones a trainer holds", "Fling", "Cheri Berry",
        "Crunch", "Hyper Beam", "Twister", "Any other tutor move that a trainer team has",
    }
    assert plan["Life Orb"] == {"step": "4.1", "phase": 4, "star": False, "ticked": True, "to_check": False}
    assert plan["Lagging Tail"]["star"] and not plan["Lagging Tail"]["ticked"]
    assert (plan["Cheri Berry"]["step"], plan["Crunch"]["step"]) == ("4.3", "5")
    assert plan["Twister"] == {"step": "6.3", "phase": 6, "star": False, "ticked": False, "to_check": True}
    assert plan["Any other tutor move that a trainer team has"]["step"] is None


def test_trainer_uses():
    """Each move, held item, ability and trainer item, with the split that first has it and who uses it"""
    uses = coverage.trainer_uses(_data()["trainers"])
    assert uses[("move", "Tackle")] == {"first": "Roark", "trainers": ["Youngster A 1", "Hiker B 1"]}
    assert uses[("move", "Crunch")] == {"first": "Gardenia", "trainers": ["Hiker B 1"]}
    assert set(uses) == {
        ("move", "Tackle"), ("move", "Crunch"), ("item", "Life Orb"), ("ability", "Sturdy"),
        ("trainer item", "Potion"), ("trainer item", "X Attack"),
    }


def test_supported():
    """In its database and not NOT_IMPLEMENTED, or a trainer item the AI uses"""
    data = _data()
    assert coverage.supported("move", "Tackle", data)
    assert not coverage.supported("move", "Crunch", data)
    assert not coverage.supported("ability", "Color Change", data)  # NOT_IMPLEMENTED
    assert coverage.supported("trainer item", "Potion", data)
    assert not coverage.supported("trainer item", "X Attack", data)


def test_runnable_after():
    """A trainer runs once every phase it needs is done. One that needs something the plan doesn't have never
    does"""
    data = _data()
    plan, uses = coverage.parse_plan(PLAN), coverage.trainer_uses(data["trainers"])
    table, never = coverage.runnable_after(data["trainers"], uses, plan, data)
    assert (table[0]["Roark"], table[0]["Gardenia"]) == (1, 0)
    assert never == ["Hiker B 1"]  # X Attack isn't in the plan
    data["trainers"]["Hiker B 1"]["trainer_items"] = ["Potion"]
    uses = coverage.trainer_uses(data["trainers"])
    table, never = coverage.runnable_after(data["trainers"], uses, plan, data)
    assert not never and (table[4]["Gardenia"], table[5]["Gardenia"]) == (0, 1)


def test_my_pokemon_sources():
    """Every encounter, post-game too, with whole evolution lines; the first place each thing comes from, and
    the [pp] berry trees for what the sheet doesn't list"""
    data = _data()
    assert coverage.my_species(data["encounters"]) == [
        "Turtwig", "Grotle", "Torterra", "Geodude", "Graveler", "Golem", "Mew", "Sketcher",
    ]
    sources = coverage.my_sources(data)
    assert sources[("move", "Cut")] == "TM01 (Route 201)"
    assert sources[("move", "Twister")] == "Graveler's tutor"
    assert sources[("move", "Sketch")] == "Sketcher's learnset"
    assert sources[("item", "Lagging Tail")] == "Route 201"
    assert sources[("item", "Razor Fang")] == "Route 226"  # a file's location comes before PP_ITEM_SOURCES
    assert sources[("item", "Cheri Berry")] == "berry trees ([pp] berry_init.h)"
    assert sources[("item", "Ganlon Berry")] == "Route 208 seller (NPCTRADES)"  # every rare berry
    assert sources[("ability", "Own Tempo")] == "Sketcher"


def test_report():
    """Every section, and the verdicts: a * for what only I can get, drop for what nothing has"""
    text = "\n".join(coverage.report(_data()))
    for title in ("Trainers the engine runs", "What trainers use: moves", "Plan check", "To check"):
        assert title in text
    assert "X Attack (trainer item)" in text  # used, not supported, not in the plan
    lines = text.splitlines()
    assert any(l.split()[:1] == ["Twister"] and l.endswith("-> 6.3 * (Graveler's tutor)") for l in lines)
    drop = lines.index(next(l for l in lines if "my Pokemon can't get it (" in l))
    assert any(l.split()[:1] == ["Cheri"] for l in lines[drop - 40:drop])  # a berry tree has it: it gets *
    notes = lines.index(next(l for l in lines if "aren't a move, item or ability" in l))
    assert "No-effect items" in lines[notes + 1]
