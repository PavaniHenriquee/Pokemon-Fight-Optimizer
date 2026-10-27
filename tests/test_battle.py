"""Turn flow (start_of_turn / action / end_of_turn / switches) and a seeded fuzz over
whole battles that checks state invariants after every decision"""
import pytest
from Engine import battle
from Engine.battle import start_of_turn, end_of_turn, turn_sim, switch_in_action
from Models.idx_const import Pok, Move, Field, POK_LEN
from Models.helper import ActionType, BattlePhase, Status, Potions, MoveOutcome, VolStatus, Types
from Models.move import STRUGGLE
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



@pytest.mark.parametrize("ko_first_hit, rolls", [(False, 2), (True, 1)])
def test_multihit_secondary_rolls_every_hit(monkeypatch, poke, ko_first_hit, rolls):
    """Showdown rolls secondaries inside the hit loop: Twineedle gets a poison roll per hit"""
    calls = []
    monkeypatch.setattr(battle, "sec_effects", lambda *a: calls.append(1))
    a = poke("Beedrill", 50, "Swarm", ["Twineedle"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    if ko_first_hit:
        d[Pok.CURRENT_HP] = 1
    battle.ps_moves_multihit(a, d, move_slice(a, 0), 0, False, False)
    assert len(calls) == rolls


# ── Phase 2: damage mechanics ────────────────────────────────────────────────

@pytest.mark.parametrize("move", ["Seismic Toss", "Night Shade"])
def test_level_damage_moves_deal_user_level(poke, move):
    """Bulbapedia: Seismic Toss / Night Shade deal damage equal to the user's level"""
    a = poke("Machop", 14, "Guts", [move])
    d = poke("Rattata", 30, "Run Away", ["Tackle"])
    d[Pok.CURRENT_HP] -= 20
    hp = d[Pok.CURRENT_HP]
    battle.ps_moves(a, d, move_slice(a, 0), 0, False, False)
    assert d[Pok.CURRENT_HP] == hp - 14


@pytest.mark.parametrize("level, roll, expected", [(30, 0, 15), (30, 10, 45), (30, 5, 30), (1, 0, 1)])
def test_psywave_gen4_formula(monkeypatch, poke, level, roll, expected):
    """Effect script 0088: level * (rand(0..10) + 5) / 10, at least 1"""
    monkeypatch.setattr(battle.random, "randint", lambda lo, hi: roll)
    a = poke("Abra", level, "Synchronize", ["Psywave"])
    d = poke("Rattata", 30, "Run Away", ["Tackle"])
    assert battle._resolve_move_damage(a, d, move_slice(a, 0), 0) == expected


@pytest.mark.parametrize("target_hp", [None, 5])
def test_take_down_recoil_from_hp_lost(poke, target_hp):
    """Recoil is a quarter of what the target actually lost, so a KO caps it"""
    a = poke("Rattata", 50, "Run Away", ["Take Down"])
    d = poke("Geodude", 50, "Sturdy", ["Tackle"])
    if target_hp:
        d[Pok.CURRENT_HP] = target_hp
    a_hp, d_hp = a[Pok.CURRENT_HP], d[Pok.CURRENT_HP]
    battle.ps_moves(a, d, move_slice(a, 0), 0, False, False)
    dealt = d_hp - d[Pok.CURRENT_HP]
    assert dealt > 0
    assert a_hp - a[Pok.CURRENT_HP] == max(1, dealt // 4)


def test_struggle_recoil_after_the_hit(poke):
    """The target takes the hit even when the recoil makes the user faint"""
    a = poke("Rattata", 50, "Run Away", ["Tackle"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    a[Pok.CURRENT_HP] = 1
    hp = d[Pok.CURRENT_HP]
    battle.ps_moves(a, d, STRUGGLE.copy(), 0, False, False)
    assert d[Pok.CURRENT_HP] < hp and a[Pok.CURRENT_HP] == 0


def _always_hit(monkeypatch, damage=1):
    """Every move hits and does `damage`, so long locks can't KO anything"""
    monkeypatch.setattr(battle, "calculate_hit_miss", lambda *a: MoveOutcome.HIT)
    monkeypatch.setattr(battle, "calculate_damage", lambda *a, **k: damage)


def test_rollout_locks_for_five_uses(monkeypatch, make_pokemon, make_battle):
    """Locked for 5 uses, PP only once, the count drives the power, then it unlocks"""
    _always_hit(monkeypatch)
    arr = make_battle([make_pokemon("Geodude", 50, "Sturdy", ["Rollout", "Tackle"])],
                      [make_pokemon("Onix", 50, "Sturdy", ["Harden"])])
    me = my_active(arr)
    pp = move_slice(me, 0)[Move.PP]
    for use in range(1, 6):
        turn_sim(0, (MOVE, 0), arr)
        if use < 5:
            assert (me[Pok.LOCKED_MOVE], me[Pok.CONSEC_COUNT]) == (0, use)
    assert (me[Pok.LOCKED_MOVE], me[Pok.CONSEC_COUNT]) == (-1, 0)
    assert move_slice(me, 0)[Move.PP] == pp - 1


def test_rollout_miss_unlocks(monkeypatch, make_pokemon, make_battle):
    """A miss ends the lock and the count (subscript_missed's UnlockMoveChoice)"""
    _always_hit(monkeypatch)
    arr = make_battle([make_pokemon("Geodude", 50, "Sturdy", ["Rollout"])],
                      [make_pokemon("Onix", 50, "Sturdy", ["Harden"])])
    me = my_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.CONSEC_COUNT] == 2
    monkeypatch.setattr(battle, "calculate_hit_miss", lambda *a: MoveOutcome.MISS)
    turn_sim(0, (MOVE, 0), arr)
    assert (me[Pok.LOCKED_MOVE], me[Pok.CONSEC_COUNT]) == (-1, 0)


def test_fury_cutter_count_resets_on_other_move_and_miss(monkeypatch, make_pokemon, make_battle):
    """Consecutive hits count up, another move or a miss starts over"""
    _always_hit(monkeypatch)
    arr = make_battle([make_pokemon("Anorith", 50, "Battle Armor", ["Fury Cutter", "Harden"])],
                      [make_pokemon("Onix", 50, "Sturdy", ["Harden"])])
    me = my_active(arr)
    for count in (1, 2, 3):
        turn_sim(0, (MOVE, 0), arr)
        assert me[Pok.CONSEC_COUNT] == count
    turn_sim(0, (MOVE, 1), arr)
    assert me[Pok.CONSEC_COUNT] == 0
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.CONSEC_COUNT] == 1
    monkeypatch.setattr(battle, "calculate_hit_miss", lambda *a: MoveOutcome.MISS)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.CONSEC_COUNT] == 0


def test_bounce_charges_airborne_then_lands(make_pokemon, make_battle):
    """Turn 1: airborne and the foe's Tackle misses. Turn 2: attacks and lands"""
    arr = make_battle([make_pokemon("Pidgey", 50, "Keen Eye", ["Bounce"])],
                      [make_pokemon("Rattata", 5, "Run Away", ["Tackle"])])
    me = my_active(arr)
    hp = me[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.VOL_STATUS] & VolStatus.SEMI_INVULNERABLE
    assert (me[Pok.LOCKED_MOVE], me[Pok.CHARGE_RECHARGE]) == (0, 1)
    assert me[Pok.CURRENT_HP] == hp
    turn_sim(0, (MOVE, 0), arr)
    assert not me[Pok.VOL_STATUS] & VolStatus.SEMI_INVULNERABLE
    assert me[Pok.LOCKED_MOVE] == -1


@pytest.mark.parametrize("outcome", [MoveOutcome.HIT, MoveOutcome.MISS])
def test_natural_gift_berry_used_even_on_miss(monkeypatch, make_pokemon, make_battle, outcome):
    """The effect script removes the berry before the accuracy check"""
    monkeypatch.setattr(battle, "calculate_hit_miss", lambda *a: outcome)
    arr = make_battle(
        [make_pokemon("Rattata", 50, "Run Away", ["Natural Gift"], item="Sitrus Berry")],
        [make_pokemon("Onix", 50, "Sturdy", ["Harden"])])
    me, foe = my_active(arr), opp_active(arr)
    hp = foe[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.ITEM_ID] == 0
    assert (move_slice(me, 0)[Move.TYPE], move_slice(me, 0)[Move.POWER]) == (Types.PSYCHIC, 60)
    assert (foe[Pok.CURRENT_HP] < hp) == (outcome == MoveOutcome.HIT)


def test_natural_gift_fails_without_berry(make_pokemon, make_battle):
    """No berry, no Natural Gift"""
    arr = make_battle([make_pokemon("Rattata", 50, "Run Away", ["Natural Gift"])],
                      [make_pokemon("Onix", 50, "Sturdy", ["Harden"])])
    hp = opp_active(arr)[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert opp_active(arr)[Pok.CURRENT_HP] == hp


@pytest.mark.parametrize("foe_move, reflects", [("Water Gun", True), ("Tackle", False)])
def test_mirror_coat_doubles_special_damage(make_pokemon, make_battle, foe_move, reflects):
    """Mirror Coat returns twice the special damage taken this turn, nothing after a physical hit"""
    arr = make_battle([make_pokemon("Wobbuffet", 50, "Shadow Tag", ["Mirror Coat"])],
                      [make_pokemon("Squirtle", 50, "Torrent", [foe_move])])
    me, foe = my_active(arr), opp_active(arr)
    my_hp, foe_hp = me[Pok.CURRENT_HP], foe[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    taken = my_hp - me[Pok.CURRENT_HP]
    assert taken > 0
    assert foe_hp - foe[Pok.CURRENT_HP] == (2 * taken if reflects else 0)


def test_hurt_this_turn_set_on_damage_and_cleared_at_turn_end(poke, make_pokemon, make_battle):
    """Losing HP sets the Assurance bit, the turn ends with it cleared (no extra search nodes)"""
    a = poke("Rattata", 50, "Run Away", ["Tackle"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    battle.ps_moves(a, d, move_slice(a, 0), 0, False, False)
    assert d[Pok.VOL_STATUS] & VolStatus.HURT_THIS_TURN
    arr = make_battle([make_pokemon("Rattata", 50, "Run Away", ["Harden"])],
                      [make_pokemon("Rattata", 50, "Run Away", ["Tackle"])])
    me = my_active(arr)
    hp = me[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.CURRENT_HP] < hp
    assert not me[Pok.VOL_STATUS] & VolStatus.HURT_THIS_TURN


def test_drain_heals_from_hp_lost(poke):
    """subscript_drain_half_damage_dealt uses the capped hit damage, so a KO heals less"""
    a = poke("Oddish", 50, "Chlorophyll", ["Mega Drain"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    a[Pok.CURRENT_HP] = 1
    d[Pok.CURRENT_HP] = 6
    battle.ps_moves(a, d, move_slice(a, 0), 0, False, False)
    assert d[Pok.CURRENT_HP] == 0 and a[Pok.CURRENT_HP] == 1 + 3
