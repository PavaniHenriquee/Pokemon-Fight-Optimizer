"""Turn flow (start_of_turn / action / end_of_turn / switches) and a seeded fuzz over
whole battles that checks state invariants after every decision"""
import pytest
from Engine import battle
from Engine.battle import start_of_turn, end_of_turn, turn_sim, switch_in_action
from Models.idx_const import Pok, Move, Field, POK_LEN
from Models.helper import ActionType, BattlePhase, Status, Potions, MoveOutcome, VolStatus, Types
from Models.move import STRUGGLE
from Models.constants import _ENEMY_AI_KNOWS_MOVE2
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


# ── Phase 3 volatiles ────────────────────────────────────────────────────────

def _phase3_battle(make_pokemon, make_battle, my_moves, opp_moves, my_level=50, opp_level=5,
                   my_name="Rattata"):
    """My Pokemon vs a Rattata, both sides with a Geodude to switch to"""
    my = [make_pokemon(my_name, my_level, "Run Away", my_moves),
          make_pokemon("Geodude", 10, "Sturdy", ["Tackle"])]
    opp = [make_pokemon("Rattata", opp_level, "Run Away", opp_moves),
           make_pokemon("Geodude", 10, "Sturdy", ["Tackle"])]
    return make_battle(my, opp)


def test_protect_blocks_then_wears_off(make_pokemon, make_battle):
    """Protect blocks the foe's Tackle this turn and is gone at the end of it"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Protect"], ["Tackle"], my_level=5,
                         opp_level=50)
    me = my_active(arr)
    hp = me[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.CURRENT_HP] == hp
    assert not me[Pok.VOL_STATUS] & VolStatus.PROTECT and me[Pok.PROTECT_COUNT] == 1


def test_protect_fails_when_nothing_acts_after(make_pokemon, make_battle):
    """The foe switching leaves no one after the user, Protect fails and the count resets"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Protect"], ["Tackle"])
    me = my_active(arr)
    me[Pok.PROTECT_COUNT] = 1
    turn_sim(-5, (MOVE, 0), arr)
    assert me[Pok.PROTECT_COUNT] == 0


def test_other_move_resets_protect_count(make_pokemon, make_battle):
    """Only Protect/Endure keep the consecutive count"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Protect", "Tackle"], ["Tackle"])
    me = my_active(arr)
    me[Pok.PROTECT_COUNT] = 2
    turn_sim(0, (MOVE, 1), arr)
    assert me[Pok.PROTECT_COUNT] == 0


def test_endure_survives_with_one_hp(make_pokemon, make_battle):
    """A KO hit on an enduring Pokemon leaves it at 1 HP"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Endure"], ["Tackle"], my_level=5,
                         opp_level=50)
    me = my_active(arr)
    me[Pok.CURRENT_HP] = 2
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.CURRENT_HP] == 1


@pytest.mark.parametrize("my_move, hits", [("Protect", True), ("Growl", False)])
def test_feint_needs_and_breaks_protect(make_pokemon, make_battle, my_move, hits):
    """Gen IV Feint only works on a protecting target, and goes through the protection"""
    arr = _phase3_battle(make_pokemon, make_battle, [my_move], ["Feint"], my_level=5,
                         opp_level=50)
    me = my_active(arr)
    hp = me[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert (me[Pok.CURRENT_HP] < hp) == hits


def test_destiny_bond_takes_the_attacker_down(make_pokemon, make_battle):
    """KOed while Destiny Bond is up: the foe that landed the hit faints too"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Destiny Bond"], ["Tackle"])
    me, foe = my_active(arr), opp_active(arr)
    me[Pok.CURRENT_HP] = 1
    phase, _ = turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.CURRENT_HP] == 0 == foe[Pok.CURRENT_HP]
    assert phase == BattlePhase.DEATH_END_OF_TURN


def test_destiny_bond_gone_after_next_move(make_pokemon, make_battle):
    """The bond lasts until the user's next move"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Destiny Bond", "Tail Whip"], ["Growl"])
    me = my_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.VOL_STATUS] & VolStatus.DESTINY_BOND
    turn_sim(0, (MOVE, 1), arr)
    assert not me[Pok.VOL_STATUS] & VolStatus.DESTINY_BOND


def test_rage_builds_attack_when_hit(make_pokemon, make_battle):
    """Rage hits first, then the foe's Tackle raises the user's Attack"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Rage"], ["Tackle"], opp_level=30)
    me = my_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.VOL_STATUS] & VolStatus.RAGE
    assert me[Pok.ATTACK_STAT_STAGE] == 1


def test_rage_glitch_wipes_other_volatiles(make_pokemon, make_battle):
    """Picking another move keeps Rage and clears the statusVolatile bits, not Leech Seed"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Rage", "Tail Whip"], ["Growl"])
    me = my_active(arr)
    me[Pok.VOL_STATUS] = (VolStatus.RAGE | VolStatus.CONFUSION | VolStatus.FOCUS_ENERGY
                          | VolStatus.LEECH_SEED)
    me[Pok.CONFUSION_COUNTER] = 3
    turn_sim(0, (MOVE, 1), arr)
    assert me[Pok.VOL_STATUS] == VolStatus.RAGE | VolStatus.LEECH_SEED


def test_rage_kept_when_rage_picked_again(make_pokemon, make_battle):
    """Choosing Rage again doesn't trigger the glitch"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Rage"], ["Growl"])
    me = my_active(arr)
    me[Pok.VOL_STATUS] = VolStatus.RAGE | VolStatus.FOCUS_ENERGY
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.VOL_STATUS] & VolStatus.FOCUS_ENERGY


def test_charge_lasts_until_next_move(make_pokemon, make_battle):
    """Charge stays through the turn it's used and ends after the next move"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Charge", "Thunder Shock"], ["Growl"],
                         my_name="Pikachu")
    me = my_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.VOL_STATUS] & VolStatus.CHARGE
    turn_sim(0, (MOVE, 1), arr)
    assert not me[Pok.VOL_STATUS] & VolStatus.CHARGE


def test_leech_seed_drains_into_foe(make_pokemon, make_battle):
    """1/8 of the seeded Pokemon's max HP goes to the opposing active"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Tackle"], ["Tackle"])
    me, foe = my_active(arr), opp_active(arr)
    foe[Pok.VOL_STATUS] = VolStatus.LEECH_SEED
    me[Pok.CURRENT_HP] = 10
    foe_hp = foe[Pok.CURRENT_HP]
    end_of_turn(arr)
    drained = max(1, foe[Pok.MAX_HP] // 8)
    assert foe[Pok.CURRENT_HP] == foe_hp - drained
    assert me[Pok.CURRENT_HP] == 10 + drained


@pytest.mark.parametrize("vol", [VolStatus.INGRAIN, VolStatus.AQUA_RING])
def test_ingrain_and_aqua_ring_heal(make_pokemon, make_battle, vol):
    """1/16 of max HP at the end of the turn"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Tackle"], ["Tackle"])
    me = my_active(arr)
    me[Pok.VOL_STATUS] = vol
    me[Pok.CURRENT_HP] = 10
    end_of_turn(arr)
    assert me[Pok.CURRENT_HP] == 10 + max(1, me[Pok.MAX_HP] // 16)


@pytest.mark.parametrize("status, sleeps", [(0, True), (Status.BURN, False)])
def test_yawn_sleep_after_two_turn_ends(make_pokemon, make_battle, status, sleeps):
    """Drowsy this turn, asleep at the end of the next one unless already statused"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Tackle"], ["Tackle"], opp_level=50)
    foe = opp_active(arr)
    foe[Pok.VOL_STATUS] = VolStatus.YAWN
    foe[Pok.YAWN_TURNS] = 2
    foe[Pok.STATUS] = status
    end_of_turn(arr)
    assert foe[Pok.VOL_STATUS] & VolStatus.YAWN and foe[Pok.STATUS] == status
    end_of_turn(arr)
    assert not foe[Pok.VOL_STATUS] & VolStatus.YAWN
    assert (foe[Pok.STATUS] == Status.SLEEP) == sleeps
    if sleeps:
        assert 2 <= foe[Pok.SLEEP_COUNTER] <= 5


def test_attract_ends_when_source_switches(make_pokemon, make_battle):
    """My infatuation was with the foe's active, it ends when that Pokemon leaves"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Tackle"], ["Tackle"])
    me = my_active(arr)
    me[Pok.VOL_STATUS] = VolStatus.ATTRACT
    start_of_turn(-5, -1, arr)
    assert not me[Pok.VOL_STATUS] & VolStatus.ATTRACT


def test_ai_learns_my_moves_when_used(make_pokemon, make_battle):
    """Using a move sets its AI_KNOWS bit, switching out forgets them"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Tackle", "Tail Whip"], ["Growl"])
    turn_sim(0, (MOVE, 1), arr)
    assert arr[Field.AI_KNOWS] == _ENEMY_AI_KNOWS_MOVE2
    turn_sim(0, (SWITCH, 1), arr)
    assert arr[Field.AI_KNOWS] == 0


def test_ai_replacement_switch_in_ability_hits_me(make_pokemon, make_battle):
    """The AI's replacement after a faint gets its own switch-in (Intimidate on me)"""
    arr = make_battle(
        [make_pokemon("Rattata", 20, "Run Away", ["Tackle"])],
        [make_pokemon("Rattata", 20, "Run Away", ["Tackle"]),
         make_pokemon("Shinx", 20, "Intimidate", ["Tackle"])])
    me = my_active(arr)
    opp_active(arr)[Pok.CURRENT_HP] = 0
    assert end_of_turn(arr) == 1
    assert me[Pok.ATTACK_STAT_STAGE] == -1
    assert opp_active(arr)[Pok.ATTACK_STAT_STAGE] == 0


def test_my_replacement_after_faint_gets_switch_in(make_pokemon, make_battle):
    """My replacement while the foe is still standing triggers its switch-in ability"""
    arr = make_battle(
        [make_pokemon("Rattata", 20, "Run Away", ["Tackle"]),
         make_pokemon("Shinx", 20, "Intimidate", ["Tackle"])],
        [make_pokemon("Rattata", 20, "Run Away", ["Tackle"])])
    foe = opp_active(arr)
    foe[Pok.VOL_STATUS] = VolStatus.ATTRACT
    my_active(arr)[Pok.CURRENT_HP] = 0
    arr[Field.PHASE] = BattlePhase.DEATH_END_OF_TURN
    switch_in_action(arr, 1)
    assert foe[Pok.ATTACK_STAT_STAGE] == -1
    assert not foe[Pok.VOL_STATUS] & VolStatus.ATTRACT


@pytest.mark.parametrize("opp_faster", [True, False])
def test_residuals_weather_first_then_speed_order(monkeypatch, make_pokemon, make_battle,
                                                  opp_faster):
    """Weather for both actives in speed order, then each one's own residuals in speed order"""
    arr = make_battle([make_pokemon("Rattata", 5 if opp_faster else 50, "Run Away", ["Tackle"])],
                      [make_pokemon("Rattata", 50 if opp_faster else 5, "Run Away", ["Tackle"])])
    me, foe = my_active(arr), opp_active(arr)
    calls = []
    monkeypatch.setattr(battle, "_residual_weather",
                        lambda pok, *a: calls.append(("weather", pok.ctypes.data == foe.ctypes.data)))
    monkeypatch.setattr(battle, "_apply_residual",
                        lambda pok, *a: calls.append(("own", pok.ctypes.data == foe.ctypes.data)))
    end_of_turn(arr)
    fast, slow = (True, False) if opp_faster else (False, True)
    assert calls == [("weather", fast), ("weather", slow), ("own", fast), ("own", slow)]
    assert me.ctypes.data != foe.ctypes.data


def test_faster_receiver_fainting_skips_my_leech_seed(make_pokemon, make_battle):
    """The faster foe faints to its burn first, so my Leech Seed has no one to drain into"""
    arr = make_battle([make_pokemon("Rattata", 5, "Run Away", ["Tackle"])],
                      [make_pokemon("Rattata", 50, "Run Away", ["Tackle"])])
    me, foe = my_active(arr), opp_active(arr)
    me[Pok.VOL_STATUS] = VolStatus.LEECH_SEED
    foe[Pok.STATUS] = Status.BURN
    foe[Pok.CURRENT_HP] = foe[Pok.MAX_HP] // 8
    end_of_turn(arr)
    assert foe[Pok.CURRENT_HP] == 0
    assert me[Pok.CURRENT_HP] == me[Pok.MAX_HP]


# ── Phase 4 volatiles ────────────────────────────────────────────────────────

def test_wrap_traps_and_hurts_until_freed(monkeypatch, make_pokemon, make_battle):
    """3-6 counter, ticking from this turn: 2-5 hits of 1/16, then the target is freed"""
    _always_hit(monkeypatch)
    arr = _phase3_battle(make_pokemon, make_battle, ["Wrap", "Growl"], ["Growl"])
    foe = opp_active(arr)
    tick = max(1, foe[Pok.MAX_HP] // 16)
    hp = foe[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.VOL_STATUS] & VolStatus.PARTIALLY_TRAPPED
    assert 2 <= foe[Pok.TRAP_TURNS] <= 5
    assert foe[Pok.CURRENT_HP] == hp - 1 - tick
    hits = 1
    while foe[Pok.VOL_STATUS] & VolStatus.PARTIALLY_TRAPPED:
        hp = foe[Pok.CURRENT_HP]
        turn_sim(0, (MOVE, 1), arr)
        if foe[Pok.VOL_STATUS] & VolStatus.PARTIALLY_TRAPPED:
            assert foe[Pok.CURRENT_HP] == hp - tick
            hits += 1
        else:
            assert foe[Pok.CURRENT_HP] == hp
    assert 2 <= hits <= 5


def test_wrap_doesnt_refresh_the_bind(monkeypatch, make_pokemon, make_battle):
    """Hitting a bound target again leaves its counter alone"""
    _always_hit(monkeypatch)
    arr = _phase3_battle(make_pokemon, make_battle, ["Wrap"], ["Growl"])
    foe = opp_active(arr)
    foe[Pok.VOL_STATUS] = VolStatus.PARTIALLY_TRAPPED
    foe[Pok.TRAP_TURNS] = 3
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.TRAP_TURNS] == 2


def test_bind_ends_when_the_binder_faints(make_pokemon, make_battle):
    """Freed right away, no damage that turn"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Wrap"], ["Growl"])
    me, foe = my_active(arr), opp_active(arr)
    foe[Pok.VOL_STATUS] = VolStatus.PARTIALLY_TRAPPED
    foe[Pok.TRAP_TURNS] = 4
    me[Pok.CURRENT_HP] = 0
    hp = foe[Pok.CURRENT_HP]
    end_of_turn(arr)
    assert not foe[Pok.VOL_STATUS] & VolStatus.PARTIALLY_TRAPPED
    assert foe[Pok.CURRENT_HP] == hp


def test_magic_guard_takes_no_bind_damage(make_pokemon, make_battle):
    """Magic Guard skips the damage, the counter still runs"""
    arr = make_battle([make_pokemon("Rattata", 20, "Run Away", ["Wrap"])],
                      [make_pokemon("Abra", 20, "Magic Guard", ["Growl"])])
    foe = opp_active(arr)
    foe[Pok.VOL_STATUS] = VolStatus.PARTIALLY_TRAPPED
    foe[Pok.TRAP_TURNS] = 4
    hp = foe[Pok.CURRENT_HP]
    end_of_turn(arr)
    assert foe[Pok.CURRENT_HP] == hp and foe[Pok.TRAP_TURNS] == 3


def test_uproar_locks_3_to_6_turns_and_wakes_the_foe(monkeypatch, make_pokemon, make_battle):
    """PP only on the first turn, the sleeping foe wakes, the lock ends with the counter"""
    _always_hit(monkeypatch)
    arr = _phase3_battle(make_pokemon, make_battle, ["Uproar", "Growl"], ["Growl"])
    me, foe = my_active(arr), opp_active(arr)
    foe[Pok.STATUS] = Status.SLEEP
    foe[Pok.SLEEP_COUNTER] = 5
    pp = move_slice(me, 0)[Move.PP]
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.VOL_STATUS] & VolStatus.UPROAR and me[Pok.LOCKED_MOVE] == 0
    assert foe[Pok.STATUS] == 0
    turns = 1
    while me[Pok.VOL_STATUS] & VolStatus.UPROAR:
        turn_sim(0, (MOVE, 0), arr)
        turns += 1
    assert 3 <= turns <= 6 and me[Pok.LOCKED_MOVE] == -1
    assert move_slice(me, 0)[Move.PP] == pp - 1


@pytest.mark.parametrize("outcome, keeps", [
    (MoveOutcome.MISS, True), (MoveOutcome.PROTECTED, True), (MoveOutcome.INVULNERABLE, False),
])
def test_uproar_goes_on_through_a_miss(monkeypatch, make_pokemon, make_battle, outcome, keeps):
    """A miss or Protect doesn't end the uproar, an immune target does"""
    _always_hit(monkeypatch)
    arr = _phase3_battle(make_pokemon, make_battle, ["Uproar"], ["Growl"])
    me = my_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    me[Pok.UPROAR_TURNS] = 3
    monkeypatch.setattr(battle, "calculate_hit_miss", lambda *a: outcome)
    turn_sim(0, (MOVE, 0), arr)
    assert bool(me[Pok.VOL_STATUS] & VolStatus.UPROAR) == keeps
    assert me[Pok.LOCKED_MOVE] == (0 if keeps else -1)


def test_yawn_sleep_blocked_by_uproar(poke):
    """The drowsy Pokemon doesn't fall asleep while someone makes an uproar"""
    p = poke("Rattata", 20, "Run Away", ["Tackle"])
    foe = poke("Rattata", 20, "Run Away", ["Uproar"])
    p[Pok.VOL_STATUS] = VolStatus.YAWN
    p[Pok.YAWN_TURNS] = 1
    foe[Pok.VOL_STATUS] = VolStatus.UPROAR
    battle._yawn(p, foe)  # pylint: disable=protected-access
    assert p[Pok.STATUS] == 0 and not p[Pok.VOL_STATUS] & VolStatus.YAWN


def test_last_move_id_set_and_cleared(make_pokemon, make_battle):
    """The move that got past the status checks, 0 after a blocked turn"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Growl"], ["Growl"])
    me = my_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.LAST_MOVE_ID] == move_slice(me, 0)[Move.ID]
    me[Pok.STATUS] = Status.SLEEP
    me[Pok.SLEEP_COUNTER] = 3
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.LAST_MOVE_ID] == 0


def test_encore_forces_the_slower_target_this_turn(make_pokemon, make_battle):
    """The foe picked Tackle, Encore lands first and it uses its last move (Growl) instead"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Encore"], ["Growl", "Tackle"])
    me, foe = my_active(arr), opp_active(arr)
    foe[Pok.LAST_MOVE_ID] = move_slice(foe, 0)[Move.ID]
    hp = me[Pok.CURRENT_HP]
    turn_sim(1, (MOVE, 0), arr)
    assert foe[Pok.VOL_STATUS] & VolStatus.ENCORE and foe[Pok.ENCORE_TURNS] % 4 == 0
    assert me[Pok.CURRENT_HP] == hp and me[Pok.ATTACK_STAT_STAGE] == -1


@pytest.mark.parametrize("vol, field", [
    (VolStatus.ENCORE, Pok.ENCORE_TURNS), (VolStatus.DISABLE, Pok.DISABLE_TURNS),
])
def test_encore_disable_count_down(make_pokemon, make_battle, vol, field):
    """One turn less per residual, the slot stays, it ends a turn after reaching 0"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Growl"], ["Tackle", "Growl"])
    foe = opp_active(arr)
    foe[Pok.VOL_STATUS] = vol
    foe[field] = 1 * 4 + 1
    end_of_turn(arr)
    assert foe[Pok.VOL_STATUS] & vol and foe[field] == 1
    end_of_turn(arr)
    assert not foe[Pok.VOL_STATUS] & vol and foe[field] == 0


def test_encore_ends_when_the_move_runs_out_of_pp(make_pokemon, make_battle):
    """At the residual, whatever turns were left"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Growl"], ["Tackle", "Growl"])
    foe = opp_active(arr)
    foe[Pok.VOL_STATUS] = VolStatus.ENCORE
    foe[Pok.ENCORE_TURNS] = 5 * 4 + 0
    move_slice(foe, 0)[Move.PP] = 0
    end_of_turn(arr)
    assert not foe[Pok.VOL_STATUS] & VolStatus.ENCORE


def test_taunt_counts_down(make_pokemon, make_battle):
    """Gone at the residual where the counter reaches 0"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Growl"], ["Growl"])
    foe = opp_active(arr)
    foe[Pok.VOL_STATUS] = VolStatus.TAUNT
    foe[Pok.TAUNT_TURNS] = 2
    end_of_turn(arr)
    assert foe[Pok.VOL_STATUS] & VolStatus.TAUNT and foe[Pok.TAUNT_TURNS] == 1
    end_of_turn(arr)
    assert not foe[Pok.VOL_STATUS] & VolStatus.TAUNT


def test_taunt_stops_a_status_move_picked_before(make_pokemon, make_battle):
    """The faster foe taunts me, my Growl this turn fails"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Growl"], ["Taunt"], my_level=5,
                         opp_level=50)
    me, foe = my_active(arr), opp_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.VOL_STATUS] & VolStatus.TAUNT
    assert foe[Pok.ATTACK_STAT_STAGE] == 0


def test_disable_stops_the_move_this_turn(make_pokemon, make_battle):
    """The faster foe disables the Tackle I used last turn, my Tackle this turn fails"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Tackle"], ["Disable"], my_level=5,
                         opp_level=50)
    me, foe = my_active(arr), opp_active(arr)
    me[Pok.LAST_MOVE_ID] = move_slice(me, 0)[Move.ID]
    hp = foe[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.VOL_STATUS] & VolStatus.DISABLE and me[Pok.DISABLE_TURNS] % 4 == 0
    assert foe[Pok.CURRENT_HP] == hp
