"""Turn flow (start_of_turn / action / end_of_turn / switches) and a seeded fuzz over
whole battles that checks state invariants after every decision"""
import pytest
from Engine.battle import start_of_turn, end_of_turn, turn_sim, switch_in_action
from Models.idx_const import Pok, Move, Field, POK_LEN
from Models.helper import ActionType, BattlePhase, Status, Potions
from battle_driver import (
    SCENARIOS, build_scenario, play_battle, pok_slice, my_active, opp_active, move_slice,
    is_over, MAX_TURNS,
)

MOVE = ActionType.MOVE
SWITCH = ActionType.SWITCH


@pytest.fixture(name="two_v_two")
def fixture_two_v_two(make_pokemon, make_battle):
    """Rattata + Geodude vs Rattata + Geodude, no items"""
    def _team():
        return [
            make_pokemon("Rattata", 10, "Run Away", ["Tackle", "Tail Whip"]),
            make_pokemon("Geodude", 10, "Sturdy", ["Tackle", "Defense Curl"]),
        ]
    return lambda: make_battle(_team(), _team())


def test_start_of_battle(one_v_one):
    """Turn 1, both actives at slot 0 and marked as on their first turn"""
    arr = one_v_one()
    assert arr[Field.TURN] == 1
    assert arr[Field.MY_POK] == 0 and arr[Field.OPP_POK] == 0
    assert my_active(arr)[Pok.TURNS_ACTIVE] == 1 == opp_active(arr)[Pok.TURNS_ACTIVE]


def test_move_turn_bookkeeping(one_v_one):
    """A normal turn spends PP, records my last move, advances turn counters"""
    arr = one_v_one()
    me = my_active(arr)
    pp = me[Pok.MOVE1_ID + Move.PP]
    phase, _ = turn_sim(0, (MOVE, 0), arr)
    assert phase == BattlePhase.TURN_START
    assert me[Pok.MOVE1_ID + Move.PP] == pp - 1
    assert arr[Field.MY_LAST_MOVE] == me[Pok.MOVE1_ID + Move.ID]
    assert arr[Field.TURN] == 2
    assert me[Pok.TURNS_ACTIVE] == 2
    assert opp_active(arr)[Pok.CURRENT_HP] < opp_active(arr)[Pok.MAX_HP]


def test_my_switch(two_v_two):
    """Switching moves MY_POK, resets the outgoing Pokemon, and the AI forgets my mon"""
    arr = two_v_two()
    rattata = pok_slice(arr, 0)
    rattata[Pok.ATTACK_STAT_STAGE] = 2
    arr[Field.AI_KNOWS] = 3
    turn_sim(1, (SWITCH, 1), arr)
    assert arr[Field.MY_POK] == 1
    assert rattata[Pok.ATTACK_STAT_STAGE] == 0
    assert arr[Field.AI_KNOWS] == 0


def test_opponent_switch(two_v_two):
    """Opponent switch encoded as slot - 6 (so -5 is slot 1)"""
    arr = two_v_two()
    start_of_turn(-5, -1, arr)
    assert arr[Field.OPP_POK] == 1
    assert arr[Field.OPP_ENTER_FIELD] == 1


def test_opponent_potion(two_v_two):
    """Trainer item -10 uses AI_ITEM1 on the active Pokemon and clears the slot"""
    arr = two_v_two()
    arr[Field.AI_ITEM1] = Potions.POTION
    opp = opp_active(arr)
    opp[Pok.CURRENT_HP] = 3
    start_of_turn(-10, -1, arr)
    assert opp[Pok.CURRENT_HP] == min(opp[Pok.MAX_HP], 23)
    assert arr[Field.AI_ITEM1] == 0


@pytest.mark.parametrize("status, fraction", [(Status.POISON, 8), (Status.BURN, 8)])
def test_residual_status_damage(one_v_one, status, fraction):
    """Poison and burn chip 1/8 at end of turn"""
    arr = one_v_one()
    me = my_active(arr)
    me[Pok.STATUS] = status
    end_of_turn(arr)
    assert me[Pok.CURRENT_HP] == me[Pok.MAX_HP] - me[Pok.MAX_HP] // fraction


def test_toxic_escalates(make_pokemon, make_battle):
    """Toxic does 1/16, 2/16, 3/16..."""
    arr = make_battle([make_pokemon("Geodude", 100, "Sturdy", ["Tackle"])],
                      [make_pokemon("Geodude", 100, "Sturdy", ["Tackle"])])
    me = my_active(arr)
    me[Pok.STATUS] = Status.TOXIC
    me[Pok.BADLY_POISON] = 1
    mx = me[Pok.MAX_HP]
    hp = me[Pok.CURRENT_HP]
    for n in (1, 2, 3):
        end_of_turn(arr)
        hp -= mx * n // 16
        assert me[Pok.CURRENT_HP] == hp


def test_magic_guard_ignores_residuals(make_pokemon, make_battle):
    """Magic Guard takes no poison/burn damage"""
    arr = make_battle([make_pokemon("Clefairy", 30, "Magic Guard", ["Pound"])],
                      [make_pokemon("Rattata", 30, "Run Away", ["Tackle"])])
    me = my_active(arr)
    me[Pok.STATUS] = Status.BURN
    end_of_turn(arr)
    assert me[Pok.CURRENT_HP] == me[Pok.MAX_HP]


def test_opponent_replaces_fainted(two_v_two):
    """When the opponent faints at end of turn the AI sends in its next Pokemon"""
    arr = two_v_two()
    opp_active(arr)[Pok.CURRENT_HP] = 0
    new_idx = end_of_turn(arr)
    assert new_idx == 1 == arr[Field.OPP_POK]
    assert opp_active(arr)[Pok.CURRENT_HP] > 0


def test_my_faint_enters_death_phase_then_switch(two_v_two):
    """My active fainting returns DEATH_END_OF_TURN; switch_in_action resolves it"""
    arr = two_v_two()
    me = my_active(arr)
    me[Pok.CURRENT_HP] = 1
    me[Pok.STATUS] = Status.POISON
    phase, _ = turn_sim(1, (MOVE, 1), arr)    # Tail Whip, poison finishes me off
    assert phase == BattlePhase.DEATH_END_OF_TURN
    assert me[Pok.CURRENT_HP] == 0
    arr[Field.PHASE] = phase
    turn = arr[Field.TURN]
    switch_in_action(arr, 1)
    assert arr[Field.MY_POK] == 1
    assert arr[Field.PHASE] == BattlePhase.TURN_START
    assert arr[Field.TURN] == turn + 1


def test_struggle_when_out_of_pp(one_v_one):
    """Struggle (slot 10) works and records -1 as my last move"""
    arr = one_v_one()
    me = my_active(arr)
    for i in range(3):
        me[Pok.MOVE1_ID + i * (Pok.MOVE2_ID - Pok.MOVE1_ID) + Move.PP] = 0
    hp = me[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 10), arr)
    assert arr[Field.MY_LAST_MOVE] == -1
    assert me[Pok.CURRENT_HP] < hp


# ── Fuzz: whole battles, invariants after every decision ─────────────────────

def check_invariants(arr, action):
    """Things that must hold after any turn, whatever the RNG did"""
    for side in (False, True):
        for slot in range(6):
            p = pok_slice(arr, slot, side)
            if p[Pok.ID] == 0:
                assert not p.any(), f"empty slot {slot} (opp={side}) got written to"
                continue
            where = f"slot {slot} opp={side} after {action}"
            assert 0 <= p[Pok.CURRENT_HP] <= p[Pok.MAX_HP], f"HP out of range, {where}"
            stages = p[Pok.ATTACK_STAT_STAGE:Pok.EVASION_STAT_STAGE + 1]
            assert ((stages >= -6) & (stages <= 6)).all(), f"stage out of range, {where}"
            assert 0 <= p[Pok.STATUS] <= Status.TOXIC, where
            for m in range(4):
                assert move_slice(p, m)[Move.PP] >= 0, f"negative PP, {where}"
    for field in (Field.MY_POK, Field.OPP_POK):
        assert 0 <= arr[field] < 6
    assert pok_slice(arr, int(arr[Field.MY_POK]))[Pok.ID] != 0
    assert pok_slice(arr, int(arr[Field.OPP_POK]), True)[Pok.ID] != 0
    assert arr[Field.PHASE] in (BattlePhase.TURN_START, BattlePhase.DEATH_END_OF_TURN)
    if not is_over(arr):
        if arr[Field.PHASE] == BattlePhase.TURN_START:
            assert my_active(arr)[Pok.CURRENT_HP] > 0, "my active fainted outside death phase"
            assert opp_active(arr)[Pok.CURRENT_HP] > 0, "opponent active fainted mid-battle"
        else:
            # Double KO: the opponent's replacement waits for switch_in_action
            assert my_active(arr)[Pok.CURRENT_HP] == 0, "death phase with my active alive"
    assert len(arr) == 12 * POK_LEN + (Field.AI_KNOWS - Field.MY_POK + 1)


def _fuzz(name, seeds):
    for seed in seeds:
        arr = build_scenario(name)
        turns = play_battle(arr, seed, on_turn=check_invariants)
        assert is_over(arr), f"{name} seed {seed} didn't finish in {MAX_TURNS} decisions"
        assert turns > 0


@pytest.mark.parametrize("name", SCENARIOS)
def test_fuzz_battles(name):
    """60 seeded random battles per scenario finish without breaking any invariant"""
    _fuzz(name, range(60))


@pytest.mark.slow
@pytest.mark.parametrize("name", SCENARIOS)
def test_fuzz_battles_long(name):
    """Same as above with 1000 seeds, run with `pytest -m slow`"""
    _fuzz(name, range(1000, 2000))
