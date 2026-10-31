"""Turn flow (start_of_turn / action / end_of_turn / switches) and a seeded fuzz over
whole battles that checks state invariants after every decision"""
import pytest
from Engine import battle
from Engine.battle import start_of_turn, end_of_turn, turn_sim, switch_in_action
from Models.idx_const import (
    Pok, Move, Field, POK_LEN, SIDE_REFLECT_TURNS, SIDE_LIGHT_SCREEN_TURNS, SIDE_MIST_TURNS,
    SIDE_SAFEGUARD_TURNS, SIDE_LUCKY_CHANT_TURNS, SIDE_TOXIC_SPIKES, FIELD_LEN,
)
from Models.helper import (
    ActionType, BattlePhase, Status, Potions, MoveOutcome, VolStatus, VolStatus2, Types, SideCondition,
    Weather,
    Enemy_AI_Knows,
)
from Models.idx_const import Item
from DataBase.ItemDB import ItemNames
from DataBase.AbilitiesDB import AbilityNames
from DataBase.MoveDB import MoveName
from Engine import engine_helper
from Models.helper import Terrain
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
    assert arr[Field.PHASE] in (
        BattlePhase.TURN_START, BattlePhase.DEATH_END_OF_TURN, BattlePhase.BATON_PASS
    )
    if not is_over(arr):
        if arr[Field.PHASE] != BattlePhase.DEATH_END_OF_TURN:
            assert my_active(arr)[Pok.CURRENT_HP] > 0, "my active fainted outside death phase"
            assert opp_active(arr)[Pok.CURRENT_HP] > 0, "opponent active fainted mid-battle"
        else:
            # Double KO: the opponent's replacement waits for switch_in_action
            assert my_active(arr)[Pok.CURRENT_HP] == 0, "death phase with my active alive"
    assert len(arr) == 12 * POK_LEN + FIELD_LEN


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


@pytest.mark.parametrize("ability, hits", [("Skill Link", {5}), ("Run Away", {2, 3, 4, 5})])
def test_skill_link_always_hits_five_times(monkeypatch, poke, ability, hits):
    """Skill Link makes a 2-5 hit move hit 5 times (pokeplatinum BtlCmd_SetMultiHit)"""
    core = battle._ps_moves_core
    calls = []

    def counting_core(*args):
        calls.append(1)
        return core(*args)

    monkeypatch.setattr(battle, "_ps_moves_core", counting_core)
    seen = set()
    for _ in range(60):
        a = poke("Shellder", 50, ability, ["Fury Attack"])
        d = poke("Snorlax", 100, "Run Away", ["Tackle"])
        calls.clear()
        battle.ps_moves_multihit(a, d, move_slice(a, 0), 0, False, False)
        seen.add(len(calls))
    assert seen == hits


@pytest.mark.parametrize("crit, damage, stage", [(True, 10, 6), (False, 10, 0), (True, 60, 0)])
def test_anger_point_maxes_attack_after_a_crit(poke, crit, damage, stage):
    """Surviving a critical hit sets Anger Point's Attack to +6 (Showdown gen4 angerpoint); a
    normal hit or a KO does nothing"""
    a = poke("Rattata", 50, "Run Away", ["Tackle"])
    d = poke("Mankey", 50, "Anger Point", ["Scratch"])
    d[Pok.CURRENT_HP] = 60
    battle._apply_move_damage(a, d, move_slice(a, 0), damage, crit)
    assert d[Pok.ATTACK_STAT_STAGE] == stage


def test_anger_point_through_a_real_crit(poke):
    """The crit from the damage roll reaches Anger Point"""
    a = poke("Rattata", 50, "Run Away", ["Tackle"])
    d = poke("Mankey", 50, "Anger Point", ["Scratch"])
    mv = move_slice(a, 0).copy()
    mv[Move.WILL_CRIT] = 1
    battle._ps_moves_core(a, d, mv, 0)
    assert d[Pok.CURRENT_HP] > 0
    assert d[Pok.ATTACK_STAT_STAGE] == 6


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
    assert battle._resolve_move_damage(a, d, move_slice(a, 0), 0)[0] == expected


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


# ── Phase 5 side conditions, weather, hazards ────────────────────────────────

MY_SIDE = Field.MY_SIDE_COND
OPP_SIDE = Field.OPP_SIDE_COND
SR = SideCondition.STEALTH_ROCK


@pytest.mark.parametrize("cond, turns", [
    (SideCondition.REFLECT, SIDE_REFLECT_TURNS),
    (SideCondition.LIGHT_SCREEN, SIDE_LIGHT_SCREEN_TURNS),
    (SideCondition.MIST, SIDE_MIST_TURNS),
    (SideCondition.SAFEGUARD, SIDE_SAFEGUARD_TURNS),
    (SideCondition.LUCKY_CHANT, SIDE_LUCKY_CHANT_TURNS),
])
def test_timed_side_condition_lasts_five_turns(one_v_one, cond, turns):
    """Set to 5, counted down at the end of the turn it was set, gone after the 5th"""
    arr = one_v_one()
    battle._set_side_condition(cond, arr, OPP_SIDE)
    assert arr[OPP_SIDE] == cond and arr[OPP_SIDE + turns] == 5
    for left in (4, 3, 2, 1):
        battle._count_down_field(arr)
        assert arr[OPP_SIDE] == cond and arr[OPP_SIDE + turns] == left
    battle._count_down_field(arr)
    assert arr[OPP_SIDE] == 0 and arr[OPP_SIDE + turns] == 0


def test_side_condition_fails_while_up(one_v_one):
    """Using Reflect again doesn't refresh it"""
    arr = one_v_one()
    battle._set_side_condition(SideCondition.REFLECT, arr, MY_SIDE)
    battle._count_down_field(arr)
    battle._set_side_condition(SideCondition.REFLECT, arr, MY_SIDE)
    assert arr[MY_SIDE + SIDE_REFLECT_TURNS] == 4


def test_toxic_spikes_stack_to_two_and_rocks_once(one_v_one):
    """A third Toxic Spikes and a second Stealth Rock fail"""
    arr = one_v_one()
    for _ in range(3):
        battle._set_side_condition(SideCondition.TOXIC_SPIKES, arr, OPP_SIDE)
        battle._set_side_condition(SR, arr, OPP_SIDE)
    assert arr[OPP_SIDE + SIDE_TOXIC_SPIKES] == 2
    assert arr[OPP_SIDE] == SideCondition.TOXIC_SPIKES | SR


def _phase5_battle(make_pokemon, make_battle, my_moves, opp=("Rattata", "Run Away")):
    me = make_pokemon("Machop", 20, "Guts", my_moves)
    foe = make_pokemon(opp[0], 20, opp[1], ["Growl"])
    return make_battle([me], [foe])


def test_reflect_and_hazards_go_on_the_right_side(make_pokemon, make_battle):
    """Reflect on the user's side, Stealth Rock on the foe's"""
    arr = _phase5_battle(make_pokemon, make_battle, ["Reflect", "Stealth Rock"])
    turn_sim(0, (MOVE, 0), arr)
    turn_sim(0, (MOVE, 1), arr)
    assert arr[MY_SIDE] == SideCondition.REFLECT
    assert arr[OPP_SIDE] == SR


@pytest.mark.parametrize("opp, breaks", [
    (("Rattata", "Run Away"), True), (("Gastly", "Levitate"), False),
])
def test_brick_break_shatters_screens(make_pokemon, make_battle, opp, breaks):
    """Brick Break clears the target side's screens on a hit, a Ghost type isn't hit"""
    arr = _phase5_battle(make_pokemon, make_battle, ["Brick Break"], opp)
    arr[OPP_SIDE] = SideCondition.REFLECT | SideCondition.LIGHT_SCREEN | SR
    arr[OPP_SIDE + SIDE_REFLECT_TURNS] = arr[OPP_SIDE + SIDE_LIGHT_SCREEN_TURNS] = 3
    turn_sim(0, (MOVE, 0), arr)
    if breaks:
        assert arr[OPP_SIDE] == SR
        assert arr[OPP_SIDE + SIDE_REFLECT_TURNS] == arr[OPP_SIDE + SIDE_LIGHT_SCREEN_TURNS] == 0
    else:
        assert arr[OPP_SIDE] & SideCondition.REFLECT


def test_rapid_spin_clears_hazards_seed_and_bind(make_pokemon, make_battle):
    """Rapid Spin frees the user and clears every hazard on its side, the screens stay"""
    arr = _phase5_battle(make_pokemon, make_battle, ["Rapid Spin"])
    me = my_active(arr)
    arr[MY_SIDE] = SR | SideCondition.SPIKES | SideCondition.TOXIC_SPIKES | SideCondition.REFLECT
    arr[MY_SIDE + SIDE_TOXIC_SPIKES] = 2
    arr[MY_SIDE + SIDE_REFLECT_TURNS] = 3
    me[Pok.VOL_STATUS] = VolStatus.LEECH_SEED | VolStatus.PARTIALLY_TRAPPED
    me[Pok.TRAP_TURNS] = 3
    turn_sim(0, (MOVE, 0), arr)
    assert arr[MY_SIDE] == SideCondition.REFLECT
    assert arr[MY_SIDE + SIDE_TOXIC_SPIKES] == 0
    assert not me[Pok.VOL_STATUS] & (VolStatus.LEECH_SEED | VolStatus.PARTIALLY_TRAPPED)
    assert me[Pok.CURRENT_HP] == me[Pok.MAX_HP]


def test_rain_dance_lasts_five_turns(make_pokemon, make_battle):
    """Rain for the turn it's set plus 4, Rain Dance again during it fails"""
    arr = _phase5_battle(make_pokemon, make_battle, ["Rain Dance"])
    turn_sim(0, (MOVE, 0), arr)
    assert arr[Field.WEATHER] == Weather.RAIN and arr[Field.WEATHER_DURATION] == 4
    turn_sim(0, (MOVE, 0), arr)
    assert arr[Field.WEATHER_DURATION] == 3
    for _ in range(3):
        end_of_turn(arr)
    assert arr[Field.WEATHER] == 0 and arr[Field.WEATHER_DURATION] == 0


def test_sandstorm_doesnt_hit_on_its_last_turn(one_v_one):
    """The turn the sandstorm ends nobody takes damage"""
    arr = one_v_one()
    me = my_active(arr)
    arr[Field.WEATHER] = Weather.SANDSTORM
    arr[Field.WEATHER_DURATION] = 2
    end_of_turn(arr)
    hp = me[Pok.CURRENT_HP]
    assert hp < me[Pok.MAX_HP]
    end_of_turn(arr)
    assert me[Pok.CURRENT_HP] == hp and arr[Field.WEATHER] == 0


def test_weather_without_duration_is_permanent(one_v_one):
    """Weather set with no turns left (abilities, scenarios) never ends"""
    arr = one_v_one()
    arr[Field.WEATHER] = Weather.SANDSTORM
    for _ in range(8):
        end_of_turn(arr)
    assert arr[Field.WEATHER] == Weather.SANDSTORM


def test_second_mover_sees_the_new_weather(monkeypatch, make_pokemon, make_battle):
    """Rain Dance from the faster side boosts the slower side's Water move the same turn"""
    fast = make_pokemon("Rattata", 30, "Run Away", ["Rain Dance"])
    slow = make_pokemon("Squirtle", 10, "Torrent", ["Water Gun"])
    arr = make_battle([fast], [slow])
    seen = []
    real = battle._execute_move_slot

    def spy(*args, **kwargs):
        seen.append(int(args[10]))
        return real(*args, **kwargs)
    monkeypatch.setattr(battle, "_execute_move_slot", spy)
    turn_sim(0, (MOVE, 0), arr)
    assert seen == [0, Weather.RAIN]


def test_my_switch_in_faints_to_the_rocks(two_v_two):
    """My switch-in dies on entry: the foe's move has no target and I pick again"""
    arr = two_v_two()
    arr[MY_SIDE] = SR
    geodude = pok_slice(arr, 1)
    geodude[Pok.CURRENT_HP] = 1
    rattata = pok_slice(arr, 0)
    phase, _ = turn_sim(0, (SWITCH, 1), arr)    # foe Tackles
    assert phase == BattlePhase.DEATH_END_OF_TURN
    assert geodude[Pok.CURRENT_HP] == 0
    arr[Field.PHASE] = phase
    switch_in_action(arr, 0)
    assert arr[Field.PHASE] == BattlePhase.TURN_START
    assert rattata[Pok.CURRENT_HP] == rattata[Pok.MAX_HP] - rattata[Pok.MAX_HP] // 8


def test_death_phase_replacement_faints_to_the_rocks(make_pokemon, make_battle):
    """The replacement dies on entry: still the death phase, the turn doesn't advance"""
    team = [make_pokemon("Rattata", 10, "Run Away", ["Tackle"]) for _ in range(3)]
    arr = make_battle(team, [make_pokemon("Rattata", 10, "Run Away", ["Tackle"])])
    arr[MY_SIDE] = SR
    pok_slice(arr, 0)[Pok.CURRENT_HP] = 0
    pok_slice(arr, 1)[Pok.CURRENT_HP] = 1
    arr[Field.PHASE] = BattlePhase.DEATH_END_OF_TURN
    turn = arr[Field.TURN]
    switch_in_action(arr, 1)
    assert arr[Field.PHASE] == BattlePhase.DEATH_END_OF_TURN and arr[Field.TURN] == turn
    assert pok_slice(arr, 1)[Pok.CURRENT_HP] == 0
    switch_in_action(arr, 2)
    assert arr[Field.PHASE] == BattlePhase.TURN_START and arr[Field.TURN] == turn + 1
    assert arr[Field.MY_POK] == 2


def test_ai_keeps_replacing_while_its_switch_ins_faint(make_pokemon, make_battle):
    """The AI's replacements die to the rocks until one survives (Magic Guard)"""
    me = make_pokemon("Machop", 20, "Guts", ["Karate Chop"])
    opp = [make_pokemon("Rattata", 20, "Run Away", ["Tackle"]) for _ in range(3)]
    opp.append(make_pokemon("Clefairy", 20, "Magic Guard", ["Growl"]))
    arr = make_battle([me], opp)
    arr[OPP_SIDE] = SR
    pok_slice(arr, 0, opp=True)[Pok.CURRENT_HP] = 0
    for slot in (1, 2):
        pok_slice(arr, slot, opp=True)[Pok.CURRENT_HP] = 1
    assert end_of_turn(arr) == 3 == arr[Field.OPP_POK]
    assert all(pok_slice(arr, slot, opp=True)[Pok.CURRENT_HP] == 0 for slot in (1, 2))
    assert opp_active(arr)[Pok.CURRENT_HP] == opp_active(arr)[Pok.MAX_HP]


def test_double_ko_my_replacement_faints_after_seeing_the_ai_pick(make_pokemon, make_battle):
    """Both send in, mine dies to the rocks: I pick again with the AI's new Pokemon already in"""
    team = [make_pokemon("Rattata", 10, "Run Away", ["Tackle"]) for _ in range(3)]
    foes = [make_pokemon("Rattata", 10, "Run Away", ["Tackle"]) for _ in range(2)]
    arr = make_battle(team, foes)
    arr[MY_SIDE] = SR
    pok_slice(arr, 0)[Pok.CURRENT_HP] = 0
    pok_slice(arr, 1)[Pok.CURRENT_HP] = 1
    pok_slice(arr, 0, opp=True)[Pok.CURRENT_HP] = 0
    arr[Field.PHASE] = BattlePhase.DEATH_END_OF_TURN
    switch_in_action(arr, 1)
    assert arr[Field.PHASE] == BattlePhase.DEATH_END_OF_TURN
    assert arr[Field.OPP_POK] == 1 and opp_active(arr)[Pok.CURRENT_HP] > 0
    switch_in_action(arr, 2)
    assert arr[Field.PHASE] == BattlePhase.TURN_START and arr[Field.OPP_POK] == 1


# ── Moves into a fainted foe ─────────────────────────────────────────────────

@pytest.mark.parametrize("slot, works", [(0, False), (1, True), (2, True), (3, True)])
def test_move_into_a_fainted_foe(make_pokemon, make_battle, slot, works):
    """PP is spent either way, a move aimed at the fainted foe fails, self/side/field moves go"""
    arr = _phase5_battle(
        make_pokemon, make_battle, ["Tackle", "Harden", "Stealth Rock", "Rain Dance"]
    )
    me = my_active(arr)
    foe = opp_active(arr)
    foe[Pok.CURRENT_HP] = 0
    mv = move_slice(me, slot)
    pp = mv[Move.PP]
    battle._execute_move_slot(me, foe, mv, True, slot, 0, False, 1, True, arr, 0)
    assert mv[Move.PP] == pp - 1
    assert me[Pok.LAST_MOVE_ID] == mv[Move.ID] == arr[Field.MY_LAST_MOVE]
    changed = (
        me[Pok.DEFENSE_STAT_STAGE] == 1, arr[OPP_SIDE] == SR, arr[Field.WEATHER] == Weather.RAIN
    )
    assert any(changed) == works


# ── Phase 6 switching moves ──────────────────────────────────────────────────

def _pp(pok, slot):
    return int(move_slice(pok, slot)[Move.PP])


def test_roar_drags_out_a_random_bench_pokemon(make_pokemon, make_battle):
    """The replacement comes from the bench and takes the hazards on entry"""
    me = make_pokemon("Geodude", 20, "Sturdy", ["Roar"])
    opp = [make_pokemon(n, 20, a, ["Growl"]) for n, a in
           (("Rattata", "Run Away"), ("Machop", "Guts"), ("Zubat", "Inner Focus"))]
    arr = make_battle([me], opp)
    arr[OPP_SIDE] = SR
    turn_sim(0, (MOVE, 0), arr)
    assert arr[Field.OPP_POK] in (1, 2)
    assert opp_active(arr)[Pok.CURRENT_HP] < opp_active(arr)[Pok.MAX_HP]
    assert pok_slice(arr, 0, opp=True)[Pok.ATTACK_STAT_STAGE] == 0


def test_dragged_out_pokemon_doesnt_move(make_pokemon, make_battle):
    """Both use Roar, the faster drags the other out and the one sent in doesn't act"""
    mine = [make_pokemon("Rattata", 30, "Run Away", ["Roar"]),
            make_pokemon("Geodude", 30, "Sturdy", ["Tackle"])]
    opp = [make_pokemon("Geodude", 10, "Sturdy", ["Roar"]),
           make_pokemon("Machop", 10, "Guts", ["Roar"])]
    arr = make_battle(mine, opp)
    machop_pp = _pp(pok_slice(arr, 1, opp=True), 0)
    turn_sim(0, (MOVE, 0), arr)
    assert arr[Field.OPP_POK] == 1 and arr[Field.MY_POK] == 0
    assert _pp(opp_active(arr), 0) == machop_pp


@pytest.mark.parametrize("atk_ab, def_ab, vol, bench, works", [
    ("Sturdy", "Run Away", 0, True, True),
    ("Sturdy", "Suction Cups", 0, True, False),
    ("Mold Breaker", "Suction Cups", 0, True, True),
    ("Sturdy", "Run Away", VolStatus.INGRAIN, True, False),
    ("Sturdy", "Run Away", 0, False, False),
])
def test_force_switch_failures(make_pokemon, make_battle, atk_ab, def_ab, vol, bench, works):
    """Suction Cups (unless Mold Breaker), Ingrain and an empty bench make it fail"""
    me = make_pokemon("Geodude", 20, atk_ab, ["Roar"])
    opp = [make_pokemon("Rattata", 20, def_ab, ["Growl"])]
    if bench:
        opp.append(make_pokemon("Machop", 20, "Guts", ["Growl"]))
    arr = make_battle([me], opp)
    opp_active(arr)[Pok.VOL_STATUS] = vol
    assert battle._force_switch(my_active(arr), opp_active(arr), arr, False) == works
    assert (arr[Field.OPP_POK] == 1) == works


@pytest.mark.parametrize("roll, works", [(0, False), (None, True)])
def test_force_switch_level_roll(monkeypatch, make_pokemon, make_battle, roll, works):
    """A lower level user fails unless (rand * (lv sum) >> 8) + 1 > target lv / 4"""
    me = make_pokemon("Geodude", 10, "Sturdy", ["Roar"])
    opp = [make_pokemon("Rattata", 40, "Run Away", ["Growl"]),
           make_pokemon("Machop", 40, "Guts", ["Growl"])]
    arr = make_battle([me], opp)
    monkeypatch.setattr(battle.random, "randrange", lambda n: n - 1 if roll is None else roll)
    assert battle._force_switch(my_active(arr), opp_active(arr), arr, False) == works


def _baton_battle(make_pokemon, make_battle, my_lv, opp_lv, bench=True):
    mine = [make_pokemon("Rattata", my_lv, "Run Away", ["Baton Pass"])]
    if bench:
        mine.append(make_pokemon("Geodude", 20, "Sturdy", ["Tackle"]))
    opp = [make_pokemon("Machop", opp_lv, "Guts", ["Tackle"])]
    return make_battle(mine, opp)


def test_my_baton_pass_pauses_the_turn(make_pokemon, make_battle):
    """Faster: the turn waits for my pick, then the foe's move hits who came in"""
    arr = _baton_battle(make_pokemon, make_battle, 30, 10)
    rattata = my_active(arr)
    rattata[Pok.ATTACK_STAT_STAGE] = 2
    rattata[Pok.VOL_STATUS] = VolStatus.FOCUS_ENERGY | VolStatus.AQUA_RING | VolStatus.DEFENSE_CURL
    turn = arr[Field.TURN]
    phase, _ = turn_sim(0, (MOVE, 0), arr)
    assert phase == arr[Field.PHASE] == BattlePhase.BATON_PASS
    assert arr[Field.PENDING_OPP_MOVE] == 1 and arr[Field.TURN] == turn
    pp = _pp(opp_active(arr), 0)
    assert battle.baton_pass_action(arr, 1) == BattlePhase.TURN_START
    geodude = my_active(arr)
    assert arr[Field.MY_POK] == 1 and arr[Field.TURN] == turn + 1
    assert arr[Field.PENDING_OPP_MOVE] == 0 and arr[Field.PHASE] == BattlePhase.TURN_START
    assert geodude[Pok.ATTACK_STAT_STAGE] == 2 and rattata[Pok.ATTACK_STAT_STAGE] == 0
    assert geodude[Pok.VOL_STATUS] & VolStatus.FOCUS_ENERGY
    assert not geodude[Pok.VOL_STATUS] & VolStatus.DEFENSE_CURL
    assert _pp(opp_active(arr), 0) == pp - 1


def test_slower_baton_pass_has_nothing_pending(make_pokemon, make_battle):
    """The foe already moved, the pick just finishes the turn"""
    arr = _baton_battle(make_pokemon, make_battle, 30, 10)
    my_active(arr)[Pok.SPEED] = 1
    turn_sim(0, (MOVE, 0), arr)
    assert arr[Field.PHASE] == BattlePhase.BATON_PASS and arr[Field.PENDING_OPP_MOVE] == 0
    pp = _pp(opp_active(arr), 0)
    battle.baton_pass_action(arr, 1)
    assert _pp(opp_active(arr), 0) == pp and arr[Field.MY_POK] == 1


def test_baton_pass_fails_without_a_bench(make_pokemon, make_battle):
    """Last Pokemon: no phase change, the turn ends normally"""
    arr = _baton_battle(make_pokemon, make_battle, 30, 10, bench=False)
    phase, _ = turn_sim(0, (MOVE, 0), arr)
    assert phase == BattlePhase.TURN_START


def test_pass_baton_keeps_confusion_and_its_counter(make_pokemon, make_battle):
    """Confusion and its turns left go over, Attract doesn't"""
    arr = _baton_battle(make_pokemon, make_battle, 30, 10)
    old, new = pok_slice(arr, 0), pok_slice(arr, 1)
    old[Pok.VOL_STATUS] = VolStatus.CONFUSION | VolStatus.ATTRACT
    old[Pok.CONFUSION_COUNTER] = 3
    battle._pass_baton(old, new)
    assert new[Pok.VOL_STATUS] == VolStatus.CONFUSION and new[Pok.CONFUSION_COUNTER] == 3


def test_baton_pass_into_the_rocks_ends_in_the_death_phase(make_pokemon, make_battle):
    """The replacement faints on entry, the foe's move has no target, I pick at the end"""
    mine = [make_pokemon("Rattata", 30, "Run Away", ["Baton Pass"]),
            make_pokemon("Geodude", 20, "Sturdy", ["Tackle"])]
    arr = make_battle(mine, [make_pokemon("Machop", 10, "Guts", ["Tackle"])])
    arr[MY_SIDE] = SR
    pok_slice(arr, 1)[Pok.CURRENT_HP] = 1
    turn_sim(0, (MOVE, 0), arr)
    assert battle.baton_pass_action(arr, 1) == BattlePhase.DEATH_END_OF_TURN
    assert pok_slice(arr, 1)[Pok.CURRENT_HP] == 0


def test_ai_baton_pass_picks_with_post_ko_logic(make_pokemon, make_battle):
    """The AI passes right away, never to itself, my slower move hits who it sent"""
    me = make_pokemon("Geodude", 10, "Sturdy", ["Tackle"])
    opp = [make_pokemon("Ninjask", 30, "Run Away", ["Baton Pass"]),
           make_pokemon("Rattata", 10, "Run Away", ["Growl"])]
    arr = make_battle([me], opp)
    pok_slice(arr, 0, opp=True)[Pok.DEFENSE_STAT_STAGE] = 2
    turn_sim(0, (MOVE, 0), arr)
    assert arr[Field.OPP_POK] == 1 and arr[Field.PHASE] != BattlePhase.BATON_PASS
    rattata = opp_active(arr)
    assert rattata[Pok.DEFENSE_STAT_STAGE] == 2
    assert rattata[Pok.CURRENT_HP] < rattata[Pok.MAX_HP]


def _spy_power(monkeypatch):
    hits = []
    real = battle.ps_moves

    def spy(atk, defn, mv, *args):
        hits.append((int(defn[Pok.ID]), int(mv[Move.POWER])))
        return real(atk, defn, mv, *args)
    monkeypatch.setattr(battle, "ps_moves", spy)
    return hits


def test_ai_pursuit_hits_my_switch_at_double_power(monkeypatch, make_pokemon, make_battle):
    """Before the switch, double power, and the AI's turn is used up"""
    mine = [make_pokemon("Rattata", 20, "Run Away", ["Tackle"]),
            make_pokemon("Geodude", 20, "Sturdy", ["Tackle"])]
    arr = make_battle(mine, [make_pokemon("Murkrow", 20, "Insomnia", ["Pursuit"])])
    hits = _spy_power(monkeypatch)
    rattata_id = int(pok_slice(arr, 0)[Pok.ID])
    pp = _pp(opp_active(arr), 0)
    turn_sim(0, (SWITCH, 1), arr)
    assert hits == [(rattata_id, 80)]
    assert pok_slice(arr, 0)[Pok.CURRENT_HP] < pok_slice(arr, 0)[Pok.MAX_HP]
    assert my_active(arr)[Pok.CURRENT_HP] == my_active(arr)[Pok.MAX_HP]
    assert _pp(opp_active(arr), 0) == pp - 1


def test_my_pursuit_hits_the_ai_switch(monkeypatch, make_pokemon, make_battle):
    """The AI switching out to slot 1 takes my Pursuit first"""
    me = make_pokemon("Murkrow", 20, "Insomnia", ["Pursuit"])
    opp = [make_pokemon("Rattata", 20, "Run Away", ["Tackle"]),
           make_pokemon("Geodude", 20, "Sturdy", ["Tackle"])]
    arr = make_battle([me], opp)
    hits = _spy_power(monkeypatch)
    pp = _pp(my_active(arr), 0)
    turn_sim(-5, (MOVE, 0), arr)
    assert arr[Field.OPP_POK] == 1
    assert hits == [(int(pok_slice(arr, 0, opp=True)[Pok.ID]), 80)]
    assert opp_active(arr)[Pok.CURRENT_HP] == opp_active(arr)[Pok.MAX_HP]
    assert _pp(my_active(arr), 0) == pp - 1
    assert arr[Field.MY_LAST_MOVE] == move_slice(my_active(arr), 0)[Move.ID]


def test_pursuit_without_a_switch_is_normal(monkeypatch, make_pokemon, make_battle):
    """No switch, no double power"""
    me = make_pokemon("Murkrow", 20, "Insomnia", ["Pursuit"])
    arr = make_battle([me], [make_pokemon("Rattata", 20, "Run Away", ["Growl"])])
    hits = _spy_power(monkeypatch)
    turn_sim(0, (MOVE, 0), arr)
    assert [power for _, power in hits] == [40]


def test_sleeping_pursuer_doesnt_pursue(monkeypatch, make_pokemon, make_battle):
    """Asleep: no Pursuit before the switch, and no move after it either"""
    mine = [make_pokemon("Rattata", 20, "Run Away", ["Tackle"]),
            make_pokemon("Geodude", 20, "Sturdy", ["Tackle"])]
    arr = make_battle(mine, [make_pokemon("Murkrow", 20, "Insomnia", ["Pursuit"])])
    opp_active(arr)[Pok.STATUS] = Status.SLEEP
    opp_active(arr)[Pok.SLEEP_COUNTER] = 3
    hits = _spy_power(monkeypatch)
    turn_sim(0, (SWITCH, 1), arr)
    assert hits == []


# ── Phase 7: healing, items, misc ────────────────────────────────────────────

def test_recover_heals_half_in_a_turn(make_pokemon, make_battle):
    """Recover through a whole turn"""
    arr = make_battle([make_pokemon("Machop", 20, "Guts", ["Recover"])],
                      [make_pokemon("Rattata", 5, "Run Away", ["Growl"])])
    me = my_active(arr)
    me[Pok.CURRENT_HP] = 1
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.CURRENT_HP] == 1 + me[Pok.MAX_HP] // 2


def test_perish_song_faints_both_after_four_ends_of_turn(make_pokemon, make_battle):
    """Used on turn 1, both faint at the end of turn 4, the counts tick down in between"""
    arr = make_battle([make_pokemon("Rattata", 20, "Run Away", ["Perish Song", "Growl"])],
                      [make_pokemon("Machop", 20, "Guts", ["Leer"])])
    me, foe = my_active(arr), opp_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.PERISH_TURNS] == foe[Pok.PERISH_TURNS] == 2
    for _ in range(2):
        turn_sim(0, (MOVE, 1), arr)
    assert me[Pok.PERISH_TURNS] == foe[Pok.PERISH_TURNS] == 0
    assert me[Pok.CURRENT_HP] > 0 and foe[Pok.CURRENT_HP] > 0
    phase, _ = turn_sim(0, (MOVE, 1), arr)
    assert me[Pok.CURRENT_HP] == 0 and foe[Pok.CURRENT_HP] == 0
    assert phase == BattlePhase.DEATH_END_OF_TURN


def test_perish_song_into_a_soundproof_foe_still_counts_the_user(make_pokemon, make_battle):
    """No hit check: the Soundproof foe is skipped, the user still gets its count"""
    arr = make_battle([make_pokemon("Rattata", 20, "Run Away", ["Perish Song"])],
                      [make_pokemon("Machop", 20, "Soundproof", ["Leer"])])
    turn_sim(0, (MOVE, 0), arr)
    assert my_active(arr)[Pok.VOL_STATUS] & VolStatus.PERISH_SONG
    assert not opp_active(arr)[Pok.VOL_STATUS] & VolStatus.PERISH_SONG


def test_baton_pass_passes_perish_song_and_its_count(make_pokemon, make_battle):
    """The receiver keeps the count it was passed"""
    arr = _baton_battle(make_pokemon, make_battle, 30, 10)
    old, new = pok_slice(arr, 0), pok_slice(arr, 1)
    old[Pok.VOL_STATUS] = VolStatus.PERISH_SONG
    old[Pok.PERISH_TURNS] = 1
    battle._pass_baton(old, new)
    assert new[Pok.VOL_STATUS] & VolStatus.PERISH_SONG and new[Pok.PERISH_TURNS] == 1


def test_knock_off_in_a_turn(make_pokemon, make_battle):
    """The hit knocks the item off and marks the target"""
    arr = make_battle([make_pokemon("Murkrow", 20, "Insomnia", ["Knock Off"])],
                      [make_pokemon("Machop", 20, "Guts", ["Leer"], item="Oran Berry")])
    turn_sim(0, (MOVE, 0), arr)
    foe = opp_active(arr)
    assert foe[Item.ID] == 0 and foe[Pok.ITEM_KNOCKED_OFF] == 1


@pytest.mark.parametrize("knocked", ["attacker", "defender", None])
def test_covet_fails_with_a_knocked_off_pokemon(make_pokemon, make_battle, knocked):
    """Gen IV: no item changes hands if either side had its item knocked off"""
    arr = make_battle([make_pokemon("Machop", 20, "Guts", ["Covet"])],
                      [make_pokemon("Rattata", 20, "Run Away", ["Leer"], item="Oran Berry")])
    me, foe = my_active(arr), opp_active(arr)
    if knocked == "attacker":
        me[Pok.ITEM_KNOCKED_OFF] = 1
    elif knocked == "defender":
        foe[Pok.ITEM_KNOCKED_OFF] = 1
    battle.ps_moves(me, foe, move_slice(me, 0), 0, False, False)
    assert (me[Item.ID] == ItemNames.ORAN_BERRY) == (knocked is None)


def test_recyclable_item_stays_with_the_slot(two_v_two):
    """Gen IV: after a switch the Pokemon coming in can Recycle what the other one ate"""
    arr = two_v_two()
    pok_slice(arr, 0)[Pok.CONSUMED_ITEM] = ItemNames.ORAN_BERRY
    turn_sim(1, (SWITCH, 1), arr)
    assert pok_slice(arr, 0)[Pok.CONSUMED_ITEM] == 0
    assert pok_slice(arr, 1)[Pok.CONSUMED_ITEM] == ItemNames.ORAN_BERRY


def test_recycle_in_a_turn(make_pokemon, make_battle):
    """Recycle gives the eaten berry back"""
    arr = make_battle([make_pokemon("Machop", 20, "Guts", ["Recycle"])],
                      [make_pokemon("Rattata", 5, "Run Away", ["Growl"])])
    my_active(arr)[Pok.CONSUMED_ITEM] = ItemNames.SITRUS_BERRY
    turn_sim(0, (MOVE, 0), arr)
    assert my_active(arr)[Item.ID] == ItemNames.SITRUS_BERRY


def test_ai_worry_seed_wakes_me_and_learns_my_ability(make_pokemon, make_battle):
    """My sleeping Pokemon gets Insomnia and wakes, the AI now knows my ability"""
    arr = make_battle([make_pokemon("Machop", 10, "Guts", ["Leer"])],
                      [make_pokemon("Rattata", 30, "Run Away", ["Worry Seed"])])
    me = my_active(arr)
    me[Pok.STATUS] = Status.SLEEP
    me[Pok.SLEEP_COUNTER] = 3
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.AB_ID] == AbilityNames.INSOMNIA and me[Pok.STATUS] == 0
    assert arr[Field.AI_KNOWS] & Enemy_AI_Knows.ABILITY


def test_yawn_doesnt_put_an_insomnia_pokemon_to_sleep(poke):
    """A drowsy Pokemon that got Insomnia meanwhile stays awake"""
    p = poke("Machop", 20, "Insomnia", ["Tackle"])
    p[Pok.VOL_STATUS] = VolStatus.YAWN
    p[Pok.YAWN_TURNS] = 1
    battle._yawn(p, poke("Rattata", 20, "Run Away", ["Tackle"]))
    assert p[Pok.STATUS] == 0 and not p[Pok.VOL_STATUS] & VolStatus.YAWN


# ── Phase 8: move-calling ────────────────────────────────────────────────────

def _force_metronome(monkeypatch, move_id, always_hit=True):
    """Metronome draws move_id, and every 1-100 roll is 1 so accuracy rolls hit"""
    monkeypatch.setattr(engine_helper, "metronome_move", lambda pok: move_id)
    if always_hit:
        monkeypatch.setattr(engine_helper.random, "randint", lambda a, b: a)


def test_metronome_calls_a_move_in_its_turn(monkeypatch, make_pokemon, make_battle):
    """The called move hits, Metronome spends its PP and is the last move for everything else"""
    _force_metronome(monkeypatch, MoveName.EMBER)
    arr = make_battle([make_pokemon("Munchlax", 20, "Thick Fat", ["Metronome"])],
                      [make_pokemon("Machop", 20, "Guts", ["Leer"])])
    me, foe = my_active(arr), opp_active(arr)
    pp = _pp(me, 0)
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] < foe[Pok.MAX_HP]
    assert _pp(me, 0) == pp - 1
    assert me[Pok.LAST_MOVE_ID] == MoveName.METRONOME
    assert arr[Field.MY_LAST_MOVE] == MoveName.METRONOME
    assert arr[Field.LAST_MOVE] == MoveName.METRONOME          # the slower Munchlax moved last
    assert arr[Field.AI_TOOK_DMG_LAST_TURN] == Types.FIRE      # the AI saw an Ember


def test_metronome_into_bounce_lands_next_turn(monkeypatch, make_pokemon, make_battle):
    """A called charge move keeps Metronome's slot locked and lands as the called move"""
    _force_metronome(monkeypatch, MoveName.BOUNCE)
    arr = make_battle([make_pokemon("Munchlax", 20, "Thick Fat", ["Metronome", "Tackle"])],
                      [make_pokemon("Machop", 20, "Guts", ["Leer"])])
    me, foe = my_active(arr), opp_active(arr)
    pp = _pp(me, 0)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.LOCKED_MOVE] == 0 and me[Pok.CALLED_MOVE] == MoveName.BOUNCE
    assert me[Pok.VOL_STATUS] & VolStatus.SEMI_INVULNERABLE
    assert foe[Pok.CURRENT_HP] == foe[Pok.MAX_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] < foe[Pok.MAX_HP]
    assert me[Pok.LOCKED_MOVE] == -1 and _pp(me, 0) == pp - 1


def test_metronome_into_rollout_keeps_rolling(monkeypatch, make_pokemon, make_battle):
    """Rollout locks Metronome's slot, the next turn is Rollout again with a higher count"""
    _force_metronome(monkeypatch, MoveName.ROLLOUT)
    arr = make_battle([make_pokemon("Munchlax", 30, "Thick Fat", ["Metronome"])],
                      [make_pokemon("Geodude", 30, "Sturdy", ["Defense Curl"])])
    me = my_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.LOCKED_MOVE] == 0 and me[Pok.CONSEC_COUNT] == 1
    _force_metronome(monkeypatch, MoveName.EMBER)    # a fresh draw would be Ember
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.CALLED_MOVE] == MoveName.ROLLOUT and me[Pok.CONSEC_COUNT] == 2


def test_slower_copycat_copies_the_foes_move(make_pokemon, make_battle):
    """The foe's Growl this turn is the last move, Copycat uses Growl on it"""
    arr = make_battle([make_pokemon("Togepi", 10, "Hustle", ["Copycat"])],
                      [make_pokemon("Machop", 30, "Guts", ["Growl"])])
    turn_sim(0, (MOVE, 0), arr)
    assert my_active(arr)[Pok.ATTACK_STAT_STAGE] == -1
    assert opp_active(arr)[Pok.ATTACK_STAT_STAGE] == -1
    assert arr[Field.LAST_MOVE] == MoveName.COPYCAT


def test_faster_copycat_fails_on_the_first_turn(make_pokemon, make_battle):
    """Nobody moved yet: no last move, Copycat fails but still spends PP"""
    arr = make_battle([make_pokemon("Togepi", 30, "Hustle", ["Copycat"])],
                      [make_pokemon("Machop", 5, "Guts", ["Growl"])])
    me = my_active(arr)
    pp = _pp(me, 0)
    turn_sim(0, (MOVE, 0), arr)
    assert opp_active(arr)[Pok.ATTACK_STAT_STAGE] == 0 and _pp(me, 0) == pp - 1


def test_mirror_move_copies_the_foes_last_hit(make_pokemon, make_battle):
    """Hit by Leer on turn 1, the faster Mirror Move uses Leer on turn 2"""
    arr = make_battle([make_pokemon("Pidgey", 30, "Keen Eye", ["Mirror Move"])],
                      [make_pokemon("Machop", 5, "Guts", ["Leer"])])
    turn_sim(0, (MOVE, 0), arr)
    assert my_active(arr)[Pok.MIRROR_MOVE] == MoveName.LEER
    assert opp_active(arr)[Pok.DEFENSE_STAT_STAGE] == 0
    turn_sim(0, (MOVE, 0), arr)
    assert opp_active(arr)[Pok.DEFENSE_STAT_STAGE] == -1


def test_mirror_move_cant_copy_a_called_move(monkeypatch, make_pokemon, make_battle):
    """The foe's Metronome-called Ember leaves nothing to mirror"""
    _force_metronome(monkeypatch, MoveName.EMBER)
    arr = make_battle([make_pokemon("Pidgey", 30, "Keen Eye", ["Mirror Move", "Tackle"])],
                      [make_pokemon("Munchlax", 20, "Thick Fat", ["Metronome"])])
    my_active(arr)[Pok.MIRROR_MOVE] = MoveName.TACKLE
    turn_sim(0, (MOVE, 1), arr)
    assert my_active(arr)[Pok.MIRROR_MOVE] == 0


@pytest.mark.parametrize("terrain, move", [
    (Terrain.PLAIN, MoveName.EARTHQUAKE), (Terrain.CAVE, MoveName.ROCK_SLIDE),
    (Terrain.GRASS, MoveName.SEED_BOMB),
])
def test_nature_power_uses_the_terrain_move(monkeypatch, make_pokemon, make_battle, terrain, move):
    """Curtis's cave makes it Rock Slide, the default plain Earthquake"""
    used = []
    real = battle.ps_moves

    def spy(atk, defn, mv, *args):
        used.append(int(mv[Move.ID]))
        return real(atk, defn, mv, *args)
    monkeypatch.setattr(battle, "ps_moves", spy)
    arr = make_battle([make_pokemon("Seedot", 20, "Chlorophyll", ["Nature Power"])],
                      [make_pokemon("Machop", 5, "Guts", ["Leer"])])
    arr[Field.TERRAIN] = terrain
    turn_sim(0, (MOVE, 0), arr)
    assert used in ([move], [])     # [] only if it missed
    assert my_active(arr)[Pok.LAST_MOVE_ID] == MoveName.NATURE_POWER


def test_called_hidden_power_uses_the_users_ivs():
    """A Metronome-called Hidden Power has the type and power the user's IVs give"""
    odd = {s: 31 for s in ("HP", "Attack", "Defense", "Speed", "Special Attack", "Special Defense")}
    from Models.pokemon import Pokemon
    p = Pokemon("Munchlax", "Male", 20, "Thick Fat", "Hardy", ["Metronome"], ivs=odd)
    arr = p.to_np()
    hp_type, hp_power = p.hidden_power()
    assert arr[Pok.HIDDEN_POWER_TYPE] == hp_type == Types.DARK and arr[Pok.HIDDEN_POWER_POWER] == hp_power
    mv = battle._called_move_array(arr, MoveName.HIDDEN_POWER)
    assert mv[Move.TYPE] == hp_type and mv[Move.POWER] == hp_power
    assert battle._called_move_array(arr, MoveName.TACKLE)[Move.TYPE] == Types.NORMAL


# ── Dig, Gravity, Minimize ───────────────────────────────────────────────────

def test_dig_goes_underground_then_lands(make_pokemon, make_battle):
    """Turn 1: underground, the foe's Tackle misses. Turn 2: attacks and comes back up"""
    arr = make_battle([make_pokemon("Diglett", 50, "Sand Veil", ["Dig"])],
                      [make_pokemon("Rattata", 5, "Run Away", ["Tackle"])])
    me, foe = my_active(arr), opp_active(arr)
    hp = me[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.VOL_STATUS] & VolStatus.SEMI_INVULNERABLE
    assert me[Pok.SEMI_INV_MOVE] == MoveName.DIG
    assert me[Pok.CURRENT_HP] == hp and foe[Pok.CURRENT_HP] == foe[Pok.MAX_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.SEMI_INV_MOVE] == 0 and not me[Pok.VOL_STATUS] & VolStatus.SEMI_INVULNERABLE
    assert foe[Pok.CURRENT_HP] < foe[Pok.MAX_HP]


def test_earthquake_hits_digging_pokemon(make_pokemon, make_battle):
    """The slower foe's Earthquake reaches my Diglett underground"""
    arr = make_battle([make_pokemon("Diglett", 50, "Sand Veil", ["Dig"])],
                      [make_pokemon("Geodude", 5, "Sturdy", ["Earthquake"])])
    me = my_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.SEMI_INV_MOVE] == MoveName.DIG
    assert me[Pok.CURRENT_HP] < me[Pok.MAX_HP]


def test_no_sandstorm_damage_underground(make_pokemon, make_battle):
    """A Pokemon underground skips the sandstorm damage at the end of the turn"""
    arr = make_battle([make_pokemon("Rattata", 50, "Run Away", ["Dig"])],
                      [make_pokemon("Geodude", 5, "Sturdy", ["Harden"])])
    arr[Field.WEATHER] = Weather.SANDSTORM
    me = my_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.SEMI_INV_MOVE] == MoveName.DIG
    assert me[Pok.CURRENT_HP] == me[Pok.MAX_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.CURRENT_HP] < me[Pok.MAX_HP]


def test_metronome_into_dig_is_underground(monkeypatch, make_pokemon, make_battle):
    """A called Dig records Dig as the semi-invulnerable move, not Metronome"""
    _force_metronome(monkeypatch, MoveName.DIG)
    arr = make_battle([make_pokemon("Munchlax", 20, "Thick Fat", ["Metronome"])],
                      [make_pokemon("Machop", 20, "Guts", ["Leer"])])
    me, foe = my_active(arr), opp_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.SEMI_INV_MOVE] == MoveName.DIG
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.SEMI_INV_MOVE] == 0 and foe[Pok.CURRENT_HP] < foe[Pok.MAX_HP]


def test_gravity_lasts_five_turns_and_fails_while_up(make_pokemon, make_battle):
    """Gravity counts the turn it was set in, a second Gravity doesn't reset the count"""
    arr = make_battle([make_pokemon("Abra", 20, "Synchronize", ["Gravity"])],
                      [make_pokemon("Geodude", 20, "Sturdy", ["Harden"])])
    turn_sim(0, (MOVE, 0), arr)
    assert arr[Field.GRAVITY_TURNS] == 4
    turn_sim(0, (MOVE, 0), arr)
    assert arr[Field.GRAVITY_TURNS] == 3
    for _ in range(3):
        end_of_turn(arr)
    assert arr[Field.GRAVITY_TURNS] == 0


def test_gravity_brings_down_a_bouncing_pokemon(make_pokemon, make_battle):
    """Gravity cancels Bounce in the air, and Bounce can't start again under it"""
    arr = make_battle([make_pokemon("Pidgey", 50, "Keen Eye", ["Bounce"])],
                      [make_pokemon("Abra", 5, "Synchronize", ["Gravity"])])
    me, foe = my_active(arr), opp_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert arr[Field.GRAVITY_TURNS] > 0
    assert not me[Pok.VOL_STATUS] & VolStatus.SEMI_INVULNERABLE
    assert me[Pok.SEMI_INV_MOVE] == 0 and me[Pok.LOCKED_MOVE] == -1
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] == foe[Pok.MAX_HP]
    assert me[Pok.SEMI_INV_MOVE] == 0


def test_minimize_sets_flag_and_one_evasion_stage(make_pokemon, make_battle):
    """Gen IV Minimize raises evasion by 1 and marks the user as minimized"""
    arr = make_battle([make_pokemon("Rattata", 20, "Run Away", ["Minimize"])],
                      [make_pokemon("Geodude", 5, "Sturdy", ["Harden"])])
    me = my_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.EVASION_STAT_STAGE] == 1
    assert me[Pok.VOL_STATUS2] & VolStatus2.MINIMIZE


def test_baton_pass_keeps_evasion_not_minimize(make_pokemon):
    """Baton Pass hands over the evasion boost, the minimized flag stays behind"""
    old = make_pokemon("Rattata", 20, "Run Away", ["Tackle"]).to_np()
    new = make_pokemon("Geodude", 20, "Sturdy", ["Tackle"]).to_np()
    old[Pok.EVASION_STAT_STAGE] = 1
    old[Pok.VOL_STATUS2] = VolStatus2.MINIMIZE
    battle._pass_baton(old, new)
    assert new[Pok.EVASION_STAT_STAGE] == 1 and new[Pok.VOL_STATUS2] == 0



# ── Batch 2: resist berries, Flame Orb, Light Clay, Smooth Rock ──────────────

@pytest.mark.parametrize("item, move, defender, halved", [
    ("Rindo Berry", "Vine Whip", "Geodude", True),
    ("Rindo Berry", "Vine Whip", "Rattata", False),
    ("Rindo Berry", "Tackle", "Geodude", False),
    ("Chilan Berry", "Tackle", "Rattata", True),
    ("Chilan Berry", "Vine Whip", "Rattata", False),
])
def test_resist_berry(make_pokemon, item, move, defender, halved):
    """A resist berry halves a super effective hit of its type, Chilan any Normal hit, and it's
    eaten (recyclable); otherwise it stays"""
    atk = make_pokemon("Bulbasaur", 20, "Overgrow", [move]).to_np()
    dfn = make_pokemon(defender, 20, "Sturdy", ["Tackle"], item=item).to_np()
    item_id = dfn[Item.ID]
    got = engine_helper.resist_berry(dfn, move_slice(atk, 0), 41)
    if halved:
        assert got == 20 and dfn[Item.ID] == 0 and dfn[Pok.CONSUMED_ITEM] == item_id
    else:
        assert got == 41 and dfn[Item.ID] == item_id


def test_resist_berry_leaves_at_least_one_and_skips_immune(make_pokemon):
    """Halving 1 still does 1; a hit that does nothing (Normal into Ghost) keeps the berry"""
    atk = make_pokemon("Rattata", 20, "Run Away", ["Tackle"]).to_np()
    dfn = make_pokemon("Rattata", 20, "Run Away", ["Tackle"], item="Chilan Berry").to_np()
    assert engine_helper.resist_berry(dfn, move_slice(atk, 0), 1) == 1
    ghost = make_pokemon("Gastly", 20, "Levitate", ["Tackle"], item="Chilan Berry").to_np()
    assert engine_helper.resist_berry(ghost, move_slice(atk, 0), 0) == 0
    assert ghost[Item.ID] == ItemNames.CHILAN_BERRY


def test_resist_berry_only_halves_the_first_hit(monkeypatch, make_pokemon):
    """Double Kick into a Chople Berry: the first hit eats it, the second does full damage"""
    monkeypatch.setattr(battle, "calculate_damage", lambda *a: 40)
    atk = make_pokemon("Machop", 20, "Guts", ["Double Kick"]).to_np()
    dfn = make_pokemon("Snorlax", 50, "Thick Fat", ["Tackle"], item="Chople Berry").to_np()
    hp = dfn[Pok.CURRENT_HP]
    battle.ps_moves_multihit(atk, dfn, move_slice(atk, 0), 0, False, False)
    assert dfn[Pok.CURRENT_HP] == hp - 20 - 40
    assert dfn[Item.ID] == 0 and dfn[Pok.CONSUMED_ITEM] == ItemNames.CHOPLE_BERRY


def _flame_orb_battle(make_pokemon, make_battle, species="Machop", ability="Guts"):
    me = make_pokemon(species, 20, ability, ["Tackle"], item="Flame Orb")
    foe = make_pokemon("Rattata", 20, "Run Away", ["Growl"])
    return make_battle([me], [foe])


def test_flame_orb_burns_at_the_end_of_the_turn(make_pokemon, make_battle):
    """The burn comes after the burn damage step, so it only hurts from the next turn on"""
    arr = _flame_orb_battle(make_pokemon, make_battle)
    me = my_active(arr)
    end_of_turn(arr)
    assert me[Pok.STATUS] == Status.BURN and me[Pok.CURRENT_HP] == me[Pok.MAX_HP]
    end_of_turn(arr)
    assert me[Pok.CURRENT_HP] == me[Pok.MAX_HP] - me[Pok.MAX_HP] // 8
    assert me[Item.ID] == ItemNames.FLAME_ORB


@pytest.mark.parametrize("species, ability, status, side, weather", [
    ("Ponyta", "Flash Fire", 0, 0, 0),
    ("Machop", "Guts", Status.PARALYSIS, 0, 0),
    ("Machop", "Guts", 0, SideCondition.SAFEGUARD, 0),
    ("Goldeen", "Water Veil", 0, 0, 0),
    ("Chikorita", "Leaf Guard", 0, 0, Weather.SUN),
])
def test_flame_orb_blocked(make_pokemon, make_battle, species, ability, status, side, weather):
    """Fire type, another status, Safeguard, Water Veil and Leaf Guard in sun stop Flame Orb
    (pokeplatinum subscript_burn, held item branch)"""
    arr = _flame_orb_battle(make_pokemon, make_battle, species, ability)
    me = my_active(arr)
    me[Pok.STATUS] = status
    arr[MY_SIDE] = side
    arr[Field.WEATHER] = weather
    battle._apply_residual(me, opp_active(arr), Field.MY_ENTER_FIELD, arr)
    assert me[Pok.STATUS] == status


def test_leaf_guard_without_sun_gets_burned(make_pokemon, make_battle):
    """Leaf Guard only blocks it in sun"""
    arr = _flame_orb_battle(make_pokemon, make_battle, "Chikorita", "Leaf Guard")
    me = my_active(arr)
    battle._apply_residual(me, opp_active(arr), Field.MY_ENTER_FIELD, arr)
    assert me[Pok.STATUS] == Status.BURN


@pytest.mark.parametrize("move, item, slot, left", [
    ("Reflect", "Light Clay", SIDE_REFLECT_TURNS, 7),
    ("Light Screen", "Light Clay", SIDE_LIGHT_SCREEN_TURNS, 7),
    ("Reflect", None, SIDE_REFLECT_TURNS, 4),
    ("Mist", "Light Clay", SIDE_MIST_TURNS, 4),
    ("Safeguard", "Light Clay", SIDE_SAFEGUARD_TURNS, 4),
])
def test_light_clay_extends_screens_only(make_pokemon, make_battle, move, item, slot, left):
    """Light Clay makes Reflect and Light Screen last 8 turns, the other side conditions keep 5"""
    me = make_pokemon("Machop", 20, "Guts", [move], item=item)
    arr = make_battle([me], [make_pokemon("Rattata", 20, "Run Away", ["Growl"])])
    turn_sim(0, (MOVE, 0), arr)
    assert arr[MY_SIDE + slot] == left


@pytest.mark.parametrize("move, item, left", [
    ("Sandstorm", "Smooth Rock", 7),
    ("Sandstorm", None, 4),
    ("Rain Dance", "Smooth Rock", 4),
])
def test_smooth_rock_extends_sandstorm_only(make_pokemon, make_battle, move, item, left):
    """Smooth Rock makes the user's Sandstorm last 8 turns, Rain Dance keeps 5"""
    me = make_pokemon("Geodude", 30, "Sturdy", [move], item=item)
    arr = make_battle([me], [make_pokemon("Onix", 30, "Rock Head", ["Harden"])])
    turn_sim(0, (MOVE, 0), arr)
    assert arr[Field.WEATHER_DURATION] == left



# ── Batch 3: Rock Head ───────────────────────────────────────────────────────

@pytest.mark.parametrize("ability, recoil", [
    ("Run Away", True), ("Rock Head", False), ("Magic Guard", False),
])
def test_take_down_recoil_and_rock_head(make_pokemon, ability, recoil):
    """Take Down's quarter recoil is skipped by Rock Head and Magic Guard"""
    atk = make_pokemon("Rattata", 30, ability, ["Take Down"]).to_np()
    hp = atk[Pok.CURRENT_HP]
    battle._recoil(atk, move_slice(atk, 0), 40)
    assert atk[Pok.CURRENT_HP] == (hp - 10 if recoil else hp)


@pytest.mark.parametrize("ability", ["Rock Head", "Magic Guard"])
def test_struggle_recoil_ignores_rock_head(make_pokemon, ability):
    """Struggle's recoil (a quarter of max HP) still hits both (pokeplatinum subscript_struggle)"""
    atk = make_pokemon("Rattata", 30, ability, ["Tackle"]).to_np()
    hp = atk[Pok.CURRENT_HP]
    battle._recoil(atk, STRUGGLE, 40)
    assert atk[Pok.CURRENT_HP] == hp - atk[Pok.MAX_HP] // 4



# ── Explosion / Selfdestruct ─────────────────────────────────────────────────

def _explode_battle(make_pokemon, make_battle, user_ab="Sturdy", foe=("Rattata", 20, "Run Away"),
                    foe_move="Growl", move="Explosion"):
    me = make_pokemon("Geodude", 30, user_ab, [move])
    them = make_pokemon(foe[0], foe[1], foe[2], [foe_move])
    return make_battle([me], [them])


@pytest.mark.parametrize("move", ["Explosion", "Selfdestruct"])
def test_explosion_faints_the_user_and_hits(make_pokemon, make_battle, move):
    """The user faints, the foe takes the hit"""
    arr = _explode_battle(make_pokemon, make_battle, foe=("Machop", 40, "Guts"), move=move)
    turn_sim(0, (MOVE, 0), arr)
    foe = opp_active(arr)
    assert my_active(arr)[Pok.CURRENT_HP] == 0
    assert 0 < foe[Pok.CURRENT_HP] < foe[Pok.MAX_HP]


@pytest.mark.parametrize("foe, foe_move", [
    (("Gastly", 20, "Levitate"), "Lick"),       # immune
    (("Rattata", 20, "Run Away"), "Protect"),   # protected
])
def test_explosion_faints_the_user_without_hitting(make_pokemon, make_battle, foe, foe_move):
    """A Ghost or Protect takes no damage, the user still faints (Showdown gen4 useMoveInner)"""
    arr = _explode_battle(make_pokemon, make_battle, foe=foe, foe_move=foe_move)
    turn_sim(0, (MOVE, 0), arr)
    them = opp_active(arr)
    assert my_active(arr)[Pok.CURRENT_HP] == 0
    assert them[Pok.CURRENT_HP] == them[Pok.MAX_HP]


def test_explosion_faints_the_user_on_a_miss(monkeypatch, make_pokemon, make_battle):
    """The faint comes before the hit check"""
    monkeypatch.setattr(battle, "calculate_hit_miss", lambda *a: MoveOutcome.MISS)
    arr = _explode_battle(make_pokemon, make_battle)
    turn_sim(0, (MOVE, 0), arr)
    them = opp_active(arr)
    assert my_active(arr)[Pok.CURRENT_HP] == 0
    assert them[Pok.CURRENT_HP] == them[Pok.MAX_HP]


@pytest.mark.parametrize("user_ab, foe_ab, blocked", [
    ("Damp", "Run Away", True),
    ("Sturdy", "Damp", True),
    ("Mold Breaker", "Damp", False),
])
def test_damp_stops_explosion(make_pokemon, make_battle, user_ab, foe_ab, blocked):
    """Damp on either side stops the move and the faint, Mold Breaker ignores the target's"""
    arr = _explode_battle(make_pokemon, make_battle, user_ab, ("Rattata", 30, foe_ab))
    turn_sim(0, (MOVE, 0), arr)
    me, them = my_active(arr), opp_active(arr)
    if blocked:
        assert me[Pok.CURRENT_HP] == me[Pok.MAX_HP] and them[Pok.CURRENT_HP] == them[Pok.MAX_HP]
    else:
        assert me[Pok.CURRENT_HP] == 0 and them[Pok.CURRENT_HP] < them[Pok.MAX_HP]


def test_gen4_sturdy_doesnt_survive_explosion(make_pokemon, make_battle):
    """Gen IV Sturdy only stops OHKO moves: a full HP Sturdy Pokemon is KO'd like any other"""
    arr = _explode_battle(make_pokemon, make_battle, foe=("Geodude", 5, "Sturdy"))
    turn_sim(0, (MOVE, 0), arr)
    assert opp_active(arr)[Pok.CURRENT_HP] == 0



# ── OHKO moves ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("move", ["Fissure", "Guillotine", "Sheer Cold"])
def test_ohko_takes_the_current_hp(make_pokemon, move):
    """The damage is the target's current HP: no crit, no damage calc"""
    atk = make_pokemon("Rattata", 50, "Run Away", [move]).to_np()
    dfn = make_pokemon("Geodude", 50, "Rock Head", ["Tackle"]).to_np()
    dfn[Pok.CURRENT_HP] = 10
    assert battle._resolve_move_damage(atk, dfn, move_slice(atk, 0), 0)[0] == 10


def test_ohko_knocks_out(monkeypatch, make_pokemon, make_battle):
    """A hit leaves the target at 0 from full HP"""
    monkeypatch.setattr(battle, "calculate_hit_miss", lambda *a: MoveOutcome.HIT)
    me = make_pokemon("Rattata", 50, "Run Away", ["Guillotine"])
    arr = make_battle([me], [make_pokemon("Geodude", 50, "Rock Head", ["Harden"])])
    turn_sim(0, (MOVE, 0), arr)
    assert opp_active(arr)[Pok.CURRENT_HP] == 0


def test_endure_survives_ohko(make_pokemon):
    """Endure leaves the target at 1 HP"""
    atk = make_pokemon("Rattata", 50, "Run Away", ["Guillotine"]).to_np()
    dfn = make_pokemon("Geodude", 50, "Rock Head", ["Tackle"]).to_np()
    dfn[Pok.VOL_STATUS] |= VolStatus.ENDURE
    battle._ps_moves_core(atk, dfn, move_slice(atk, 0), 0)
    assert dfn[Pok.CURRENT_HP] == 1
