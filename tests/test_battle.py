"""Turn flow (start_of_turn / action / end_of_turn / switches) and a seeded fuzz over
whole battles that checks state invariants after every decision"""
import pytest
from Engine import battle
from Engine.battle import start_of_turn, end_of_turn, turn_sim, switch_in_action
from Engine.status_calc import vol_status
from Models.idx_const import (
    Pok, Move, Sec, Field, POK_LEN, SIDE_REFLECT_TURNS, SIDE_LIGHT_SCREEN_TURNS, SIDE_MIST_TURNS,
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
    """Toxic does 1/16, 2/16, 3/16..., the 1/16 floored first (pokeplatinum Divide(max, 16) * n)"""
    arr = make_battle([make_pokemon("Geodude", 100, "Sturdy", ["Tackle"])],
                      [make_pokemon("Geodude", 100, "Sturdy", ["Tackle"])])
    me = my_active(arr)
    me[Pok.STATUS] = Status.TOXIC
    me[Pok.BADLY_POISON] = 1
    mx = me[Pok.MAX_HP]
    hp = me[Pok.CURRENT_HP]
    for n in (1, 2, 3):
        end_of_turn(arr)
        hp -= max(1, mx // 16) * n
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
            has_sub = bool(p[Pok.VOL_STATUS2] & VolStatus2.SUBSTITUTE)
            assert has_sub == (p[Pok.SUB_HP] > 0), f"Substitute bit and HP disagree, {where}"
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
            # A foe that fainted before my Baton Pass is replaced at the end of the paused turn
            if arr[Field.PHASE] != BattlePhase.BATON_PASS:
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


def test_drain_doesnt_revive_after_aftermath(poke):
    """Draining Kiss KOs an Aftermath holder: drain heals first, then Aftermath knocks the user out,
    so it stays fainted (it used to be revived by the drain)"""
    a = poke("Clefairy", 50, "Cute Charm", ["Draining Kiss"])
    a[Pok.CURRENT_HP] = 5
    d = poke("Stunky", 5, "Aftermath", ["Scratch"])
    d[Pok.CURRENT_HP] = 1
    battle.ps_moves(a, d, move_slice(a, 0), 0, False, False)
    assert d[Pok.CURRENT_HP] == 0
    assert a[Pok.CURRENT_HP] == 0


def test_rough_skin_stops_a_multihit_move(monkeypatch, poke):
    """Rough Skin KOs the user on the first hit, the remaining hits don't happen"""
    core = battle._ps_moves_core
    calls = []

    def counting_core(*args):
        calls.append(1)
        return core(*args)

    monkeypatch.setattr(battle, "_ps_moves_core", counting_core)
    a = poke("Shellder", 50, "Skill Link", ["Fury Attack"])
    a[Pok.CURRENT_HP] = 1
    d = poke("Carvanha", 100, "Rough Skin", ["Bite"])
    battle.ps_moves_multihit(a, d, move_slice(a, 0), 0, False, False)
    assert a[Pok.CURRENT_HP] == 0
    assert len(calls) == 1


def test_static_paralyzes_on_the_ko_hit(monkeypatch, poke):
    """Through the whole hit: Tackle KOs the Static holder and still gets paralyzed"""
    monkeypatch.setattr(engine_helper.random, "randint", lambda lo, hi: lo)
    a = poke("Rattata", 50, "Run Away", ["Tackle"])
    d = poke("Pikachu", 50, "Static", ["Tackle"])
    d[Pok.CURRENT_HP] = 1
    battle.ps_moves(a, d, move_slice(a, 0), 0, False, False)
    assert d[Pok.CURRENT_HP] == 0
    assert a[Pok.STATUS] == Status.PARALYSIS


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


@pytest.mark.parametrize("mine", [True, False])
@pytest.mark.parametrize("ability", ["Cloud Nine", "Air Lock"])
def test_cloud_nine_stops_weather_but_not_its_countdown(make_pokemon, make_battle, mine, ability):
    """No sandstorm damage while either active has it, the sandstorm still runs out
    (pokeplatinum NO_CLOUD_NINE gates the weather step, not CheckFieldConditions)"""
    holder = make_pokemon("Psyduck", 20, ability, ["Tackle"])
    other = make_pokemon("Rattata", 20, "Run Away", ["Tackle"])
    arr = make_battle([holder], [other]) if mine else make_battle([other], [holder])
    arr[Field.WEATHER] = Weather.SANDSTORM
    arr[Field.WEATHER_DURATION] = 3
    assert battle.effective_weather(arr) == 0
    end_of_turn(arr)
    assert my_active(arr)[Pok.CURRENT_HP] == my_active(arr)[Pok.MAX_HP]
    assert opp_active(arr)[Pok.CURRENT_HP] == opp_active(arr)[Pok.MAX_HP]
    assert arr[Field.WEATHER] == Weather.SANDSTORM and arr[Field.WEATHER_DURATION] == 2


def test_fainted_cloud_nine_lets_the_weather_back(make_pokemon, make_battle):
    """Only a living holder suppresses the weather"""
    arr = make_battle([make_pokemon("Rattata", 20, "Run Away", ["Tackle"])],
                      [make_pokemon("Psyduck", 20, "Cloud Nine", ["Tackle"])])
    arr[Field.WEATHER] = Weather.RAIN
    assert battle.effective_weather(arr) == 0
    opp_active(arr)[Pok.CURRENT_HP] = 0
    assert battle.effective_weather(arr) == Weather.RAIN


@pytest.mark.parametrize("ability, weather", [
    ("Drizzle", Weather.RAIN), ("Drought", Weather.SUN), ("Sand Stream", Weather.SANDSTORM),
    ("Snow Warning", Weather.HAIL),
])
def test_weather_abilities_set_permanent_weather(make_pokemon, make_battle, ability, weather):
    """The weather comes in with no turn count and names the ability (pokeplatinum
    subscript_drizzle and co. set the _PERM flag)"""
    arr = make_battle([make_pokemon("Rattata", 20, "Run Away", ["Tackle"])],
                      [make_pokemon("Snover", 20, ability, ["Tackle"])])
    assert arr[Field.WEATHER] == weather and arr[Field.WEATHER_DURATION] == 0
    assert opp_active(arr)[Pok.AB_KNOWN]
    for _ in range(8):
        end_of_turn(arr)
    assert arr[Field.WEATHER] == weather


@pytest.mark.parametrize("weather, duration, replaced", [
    (Weather.RAIN, 0, False),
    (Weather.RAIN, 3, True),
    (Weather.SANDSTORM, 0, True),
])
def test_weather_ability_fails_only_on_its_own_permanent_weather(make_pokemon, make_battle,
                                                                 weather, duration, replaced):
    """Rain from Rain Dance turns permanent, another ability's weather is replaced, the same
    permanent rain makes Drizzle fail silently"""
    my = [make_pokemon("Rattata", 20, "Run Away", ["Tackle"]),
          make_pokemon("Psyduck", 20, "Drizzle", ["Tackle"])]
    arr = make_battle(my, [make_pokemon("Rattata", 20, "Run Away", ["Growl"])])
    arr[Field.WEATHER] = weather
    arr[Field.WEATHER_DURATION] = duration
    engine_helper.switch_in(pok_slice(arr, 1), opp_active(arr), arr, True)
    assert arr[Field.WEATHER] == Weather.RAIN
    assert arr[Field.WEATHER_DURATION] == 0
    assert bool(pok_slice(arr, 1)[Pok.AB_KNOWN]) == replaced


def test_slower_lead_weather_wins(make_pokemon, make_battle):
    """Both leads come in by speed, so the slower one's weather is the one left"""
    arr = make_battle([make_pokemon("Psyduck", 50, "Drizzle", ["Tackle"])],
                      [make_pokemon("Hippopotas", 5, "Sand Stream", ["Tackle"])])
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
    arr = make_battle(mine, [make_pokemon("Murkrow", 20, "Super Luck", ["Pursuit"])])
    opp_active(arr)[Pok.STATUS] = Status.SLEEP
    opp_active(arr)[Pok.SLEEP_COUNTER] = 3
    hits = _spy_power(monkeypatch)
    turn_sim(0, (SWITCH, 1), arr)
    assert hits == []


def test_loafing_truant_doesnt_pursue(monkeypatch, make_pokemon, make_battle):
    """pokeplatinum BtlCmd_TryPursuit skips a Truant holder on its loafing turn"""
    mine = [make_pokemon("Rattata", 20, "Run Away", ["Tackle"]),
            make_pokemon("Geodude", 20, "Sturdy", ["Tackle"])]
    arr = make_battle(mine, [make_pokemon("Slakoth", 20, "Truant", ["Pursuit"])])
    opp_active(arr)[Pok.TURNS_ACTIVE] = 2
    hits = _spy_power(monkeypatch)
    turn_sim(0, (SWITCH, 1), arr)
    assert hits == []


def test_pursuit_on_a_switching_pressure_holder_costs_two(monkeypatch, make_pokemon, make_battle):
    """pokeplatinum: Pursuit before the switch takes one more PP from a Pressure holder"""
    mine = [make_pokemon("Absol", 20, "Pressure", ["Tackle"]),
            make_pokemon("Geodude", 20, "Sturdy", ["Tackle"])]
    arr = make_battle(mine, [make_pokemon("Murkrow", 20, "Super Luck", ["Pursuit"])])
    _spy_power(monkeypatch)
    pp = _pp(opp_active(arr), 0)
    turn_sim(0, (SWITCH, 1), arr)
    assert _pp(opp_active(arr), 0) == pp - 2


# ── Batch 9: Pressure and Trace through the turn flow ────────────────────────

@pytest.mark.parametrize("slot, extra", [(0, 1), (1, 0), (2, 1), (3, 1)])
def test_pressure_through_a_move(make_pokemon, make_battle, slot, extra):
    """Tackle, Stealth Rock and Rain Dance into Pressure cost 2 PP, Harden 1"""
    arr = make_battle(
        [make_pokemon("Geodude", 20, "Sturdy", ["Tackle", "Harden", "Stealth Rock", "Rain Dance"])],
        [make_pokemon("Absol", 20, "Pressure", ["Tackle"])])
    me, foe = my_active(arr), opp_active(arr)
    mv = move_slice(me, slot)
    pp = int(mv[Move.PP])
    battle._execute_move_slot(me, foe, mv, True, slot, 0, False, 1, True, arr, 0)
    assert mv[Move.PP] == pp - 1 - extra


def test_trace_at_start_of_battle_copies_intimidate_once(make_pokemon, make_battle):
    """Both leads come in together: Trace copies Intimidate and each side loses one stage"""
    arr = make_battle([make_pokemon("Ralts", 20, "Trace", ["Growl"])],
                      [make_pokemon("Shinx", 20, "Intimidate", ["Tackle"])])
    assert my_active(arr)[Pok.AB_ID] == AbilityNames.INTIMIDATE
    assert my_active(arr)[Pok.ATTACK_STAT_STAGE] == -1
    assert opp_active(arr)[Pok.ATTACK_STAT_STAGE] == -1
    assert my_active(arr)[Pok.AB_KNOWN]


def test_trace_on_a_double_switch_copies_intimidate_once(make_pokemon, make_battle):
    """Both replacing a fainted Pokemon: one copy, one Intimidate each way"""
    arr = make_battle(
        [make_pokemon("Rattata", 20, "Run Away", ["Tackle"]),
         make_pokemon("Ralts", 20, "Trace", ["Growl"])],
        [make_pokemon("Rattata", 20, "Run Away", ["Tackle"]),
         make_pokemon("Shinx", 20, "Intimidate", ["Tackle"])])
    pok_slice(arr, 0)[Pok.CURRENT_HP] = 0
    pok_slice(arr, 0, opp=True)[Pok.CURRENT_HP] = 0
    arr[Field.PHASE] = BattlePhase.DEATH_END_OF_TURN
    switch_in_action(arr, 1)
    assert my_active(arr)[Pok.AB_ID] == AbilityNames.INTIMIDATE
    assert my_active(arr)[Pok.ATTACK_STAT_STAGE] == -1
    assert opp_active(arr)[Pok.ATTACK_STAT_STAGE] == -1


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


def test_covet_cant_take_a_griseous_orb(make_pokemon, make_battle):
    """pokeplatinum BtlCmd_TryStealItem fails on a defender holding a Griseous Orb"""
    arr = make_battle([make_pokemon("Machop", 20, "Guts", ["Covet"])],
                      [make_pokemon("Rattata", 20, "Run Away", ["Leer"], item="Griseous Orb")])
    me, foe = my_active(arr), opp_active(arr)
    battle.ps_moves(me, foe, move_slice(me, 0), 0, False, False)
    assert me[Item.ID] == 0
    assert foe[Item.ID] == ItemNames.GRISEOUS_ORB


@pytest.mark.parametrize("item", ["Everstone", "Rare Candy"])
def test_covet_takes_an_item_with_no_battle_effect(make_pokemon, make_battle, item):
    """A no-effect item is still an item: Covet takes it"""
    arr = make_battle([make_pokemon("Machop", 20, "Guts", ["Covet"])],
                      [make_pokemon("Rattata", 20, "Run Away", ["Leer"], item=item)])
    me, foe = my_active(arr), opp_active(arr)
    battle.ps_moves(me, foe, move_slice(me, 0), 0, False, False)
    assert me[Item.ID] == getattr(ItemNames, item.upper().replace(" ", "_"))
    assert foe[Item.ID] == 0


# ── King's Rock / Razor Fang ─────────────────────────────────────────────────

def _flinch_roll(monkeypatch, roll):
    """Every randint(1, 100) (the flinch roll) gives roll; returns the list of those calls"""
    calls = []
    def fake(lo, hi):
        if (lo, hi) == (1, 100):
            calls.append(roll)
            return roll
        return lo
    monkeypatch.setattr(engine_helper.random, "randint", fake)
    return calls


@pytest.mark.parametrize("item, move, ability, roll, flinches", [
    ("King's Rock", "Tackle", "Run Away", 10, True),
    ("King's Rock", "Tackle", "Run Away", 11, False),
    ("Razor Fang", "Tackle", "Run Away", 10, True),
    ("King's Rock", "Tackle", "Serene Grace", 20, True),      # Showdown: a secondary, doubled
    ("King's Rock", "Bite", "Run Away", 31, False),           # Bite keeps its own 30%
    ("King's Rock", "Bite", "Run Away", 30, True),
    ("King's Rock", "Disarming Voice", "Run Away", 10, True),  # RP's moves from after Gen IV
    ("King's Rock", "Bulldoze", "Run Away", 10, True),
])
def test_kings_rock_flinch(monkeypatch, poke, item, move, ability, roll, flinches):
    """Showdown gen4 kingsrock / razorfang: a 10% flinch on the moves of its list that have none, and
    on RP's damaging moves from later generations"""
    _flinch_roll(monkeypatch, roll)
    a = poke("Rattata", 20, ability, [move], item=item)
    d = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert battle._apply_move_damage(a, d, move_slice(a, 0), 1) == flinches


@pytest.mark.parametrize("move, item, def_ab", [
    ("Ember", "King's Rock", "Sturdy"),             # a Gen IV move not on Showdown gen4's list
    ("Tackle", "King's Rock", "Shield Dust"),
    ("Tackle", "King's Rock", "Inner Focus"),
    ("Tackle", None, "Sturdy"),
])
def test_kings_rock_doesnt_flinch(monkeypatch, poke, move, item, def_ab):
    """Off the list, Shield Dust, Inner Focus or no item: no flinch, even on a roll of 1"""
    _flinch_roll(monkeypatch, 1)
    a = poke("Rattata", 20, "Run Away", [move], item=item)
    d = poke("Geodude", 20, def_ab, ["Tackle"])
    assert not battle._apply_move_damage(a, d, move_slice(a, 0), 1)


def test_kings_rock_rolls_per_hit_and_not_through_a_substitute(monkeypatch, poke):
    """Double Kick rolls once per hit (Showdown secondaries); a hit on the Substitute doesn't flinch"""
    calls = _flinch_roll(monkeypatch, 100)
    a = poke("Machop", 50, "Guts", ["Double Kick"], item="King's Rock")
    d = poke("Snorlax", 50, "Thick Fat", ["Tackle"])
    battle.ps_moves_multihit(a, d, move_slice(a, 0), 0, False, False)
    assert len(calls) == 2
    calls.clear()
    d[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
    d[Pok.SUB_HP] = 200
    flinch, _, _, sub_hit, _ = battle._ps_moves_core(a, d, move_slice(a, 0), 0)
    assert sub_hit and not flinch and not calls


def test_kings_rock_needs_no_rng_without_the_item(poke):
    """No King's Rock: Tackle's hit makes no flinch roll"""
    a = poke("Rattata", 20, "Run Away", ["Tackle"])
    d = poke("Geodude", 20, "Sturdy", ["Tackle"])
    state = engine_helper.random.getstate()
    battle._apply_move_damage(a, d, move_slice(a, 0), 1)
    assert engine_helper.random.getstate() == state


# ── Zoom Lens: who acted first ───────────────────────────────────────────────

def _spy_target_moved(monkeypatch):
    """Records (attacker species, target_moved) for every accuracy check"""
    seen = []
    real = engine_helper.move_accuracy
    def spy(move, attacker, defender, move_acc, weather, gravity=False, target_moved=False):
        seen.append((int(attacker[Pok.ID]), target_moved))
        return real(move, attacker, defender, move_acc, weather, gravity, target_moved)
    monkeypatch.setattr(engine_helper, "move_accuracy", spy)
    return seen


def test_target_moved_follows_the_turn_order(monkeypatch, make_pokemon, make_battle):
    """The faster mover's target hasn't acted yet, the slower one's has"""
    seen = _spy_target_moved(monkeypatch)
    arr = make_battle([make_pokemon("Rattata", 20, "Run Away", ["Tackle"])],
                      [make_pokemon("Geodude", 20, "Sturdy", ["Tackle"])])
    turn_sim(0, (MOVE, 0), arr)
    rattata, geodude = my_active(arr)[Pok.ID], opp_active(arr)[Pok.ID]
    assert seen == [(rattata, False), (geodude, True)]


def test_a_switch_counts_as_acting(monkeypatch, two_v_two):
    """My switch comes first, so the foe's move into the Pokemon coming in has target_moved"""
    seen = _spy_target_moved(monkeypatch)
    arr = two_v_two()
    turn_sim(0, (SWITCH, 1), arr)
    assert seen == [(opp_active(arr)[Pok.ID], True)]


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
    got = engine_helper.resist_berry(atk, dfn, move_slice(atk, 0), 41)
    if halved:
        assert got == 20 and dfn[Item.ID] == 0 and dfn[Pok.CONSUMED_ITEM] == item_id
    else:
        assert got == 41 and dfn[Item.ID] == item_id


def test_resist_berry_leaves_at_least_one_and_skips_immune(make_pokemon):
    """Halving 1 still does 1; a hit that does nothing (Normal into Ghost) keeps the berry"""
    atk = make_pokemon("Rattata", 20, "Run Away", ["Tackle"]).to_np()
    dfn = make_pokemon("Rattata", 20, "Run Away", ["Tackle"], item="Chilan Berry").to_np()
    assert engine_helper.resist_berry(atk, dfn, move_slice(atk, 0), 1) == 1
    ghost = make_pokemon("Gastly", 20, "Levitate", ["Tackle"], item="Chilan Berry").to_np()
    assert engine_helper.resist_berry(atk, ghost, move_slice(atk, 0), 0) == 0
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


@pytest.mark.parametrize("move, item, left", [
    ("Rain Dance", "Damp Rock", 7),
    ("Rain Dance", None, 4),
    ("Sandstorm", "Damp Rock", 4),
])
def test_damp_rock_extends_rain_only(make_pokemon, make_battle, move, item, left):
    """Damp Rock makes the user's Rain Dance last 8 turns, Sandstorm keeps 5 (pokeplatinum
    HOLD_EFFECT_EXTEND_RAIN, effectParam 3)"""
    me = make_pokemon("Geodude", 30, "Sturdy", [move], item=item)
    arr = make_battle([me], [make_pokemon("Onix", 30, "Rock Head", ["Harden"])])
    turn_sim(0, (MOVE, 0), arr)
    assert arr[Field.WEATHER_DURATION] == left


@pytest.mark.parametrize("item, low, high", [("Grip Claw", 5, 5), (None, 2, 5)])
def test_grip_claw_binds_for_six_turns(monkeypatch, make_pokemon, make_battle, item, low, high):
    """The binder's Grip Claw sets the 3-6 counter to 6 (pokeplatinum subscript_bind_start); it
    ticks once at this turn's end"""
    _always_hit(monkeypatch)
    my = [make_pokemon("Rattata", 50, "Run Away", ["Wrap"], item=item)]
    arr = make_battle(my, [make_pokemon("Rattata", 5, "Run Away", ["Growl"])])
    foe = opp_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.VOL_STATUS] & VolStatus.PARTIALLY_TRAPPED
    assert low <= foe[Pok.TRAP_TURNS] <= high


@pytest.mark.parametrize("vol", [VolStatus.INGRAIN, VolStatus.AQUA_RING])
def test_big_root_boosts_ingrain_and_aqua_ring(make_pokemon, make_battle, vol):
    """1/16 of max HP x130/100 (pokeplatinum subscript_ingrain_heal / subscript_aqua_ring_heal)"""
    arr = make_battle([make_pokemon("Rattata", 50, "Run Away", ["Tackle"], item="Big Root")],
                      [make_pokemon("Rattata", 5, "Run Away", ["Tackle"])])
    me = my_active(arr)
    me[Pok.VOL_STATUS] = vol
    me[Pok.CURRENT_HP] = 10
    end_of_turn(arr)
    assert me[Pok.CURRENT_HP] == 10 + max(1, me[Pok.MAX_HP] // 16) * 130 // 100


def test_big_root_boosts_leech_seed(make_pokemon, make_battle):
    """The seeder's Big Root raises what Leech Seed gives it, not what the seeded loses"""
    arr = make_battle([make_pokemon("Rattata", 50, "Run Away", ["Tackle"], item="Big Root")],
                      [make_pokemon("Rattata", 50, "Run Away", ["Tackle"])])
    me, foe = my_active(arr), opp_active(arr)
    foe[Pok.VOL_STATUS] = VolStatus.LEECH_SEED
    me[Pok.CURRENT_HP] = 10
    foe_hp = foe[Pok.CURRENT_HP]
    end_of_turn(arr)
    drained = max(1, foe[Pok.MAX_HP] // 8)
    assert foe[Pok.CURRENT_HP] == foe_hp - drained
    assert me[Pok.CURRENT_HP] == 10 + drained * 130 // 100



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


# ── Batch 7: cures and status items ──────────────────────────────────────────

def test_chesto_wakes_before_the_slower_holder_moves(monkeypatch, make_pokemon, make_battle):
    """The berry is checked after every move, so the slower holder put to sleep still acts
    (pokeplatinum AFTER_MOVE_EFFECT_HELD_ITEM_STATUS)"""
    monkeypatch.setattr(battle, "calculate_hit_miss", lambda *a: MoveOutcome.HIT)
    me = make_pokemon("Geodude", 20, "Sturdy", ["Tackle"], item="Chesto Berry")
    foe = make_pokemon("Rattata", 20, "Run Away", ["Hypnosis"])
    arr = make_battle([me], [foe])
    turn_sim(0, (MOVE, 0), arr)
    assert my_active(arr)[Pok.STATUS] == 0 and my_active(arr)[Item.ID] == 0
    assert my_active(arr)[Pok.CONSUMED_ITEM] == ItemNames.CHESTO_BERRY
    assert opp_active(arr)[Pok.CURRENT_HP] < opp_active(arr)[Pok.MAX_HP]


def test_chesto_after_yawn_sleep(make_pokemon, make_battle):
    """Yawn's sleep at the end of the turn is cured in the ITEM_CONDITION step right after it"""
    me = make_pokemon("Geodude", 20, "Sturdy", ["Tackle"], item="Chesto Berry")
    arr = make_battle([me], [make_pokemon("Rattata", 20, "Run Away", ["Growl"])])
    p = my_active(arr)
    p[Pok.VOL_STATUS] |= VolStatus.YAWN
    p[Pok.YAWN_TURNS] = 1
    battle._apply_residual(p, opp_active(arr), Field.MY_ENTER_FIELD, arr)
    assert p[Pok.STATUS] == 0 and p[Item.ID] == 0


@pytest.mark.parametrize("weather, cured", [(Weather.RAIN, True), (Weather.SUN, False)])
def test_hydration_cures_in_rain(make_pokemon, make_battle, weather, cured):
    """Rain cures it at the weather step, before the poison damage"""
    me = make_pokemon("Wingull", 20, "Hydration", ["Tackle"])
    arr = make_battle([me], [make_pokemon("Rattata", 20, "Run Away", ["Growl"])])
    p = my_active(arr)
    p[Pok.STATUS] = Status.POISON
    battle._residual_weather(p, weather, Field.MY_ENTER_FIELD, arr)
    assert (p[Pok.STATUS] == 0) == cured


def _residual_battle(make_pokemon, make_battle, species, ability, item=None):
    """My active with ability/item against a Rattata, ready for _apply_residual"""
    arr = make_battle([make_pokemon(species, 30, ability, ["Tackle"], item=item)],
                      [make_pokemon("Rattata", 30, "Run Away", ["Growl"])])
    return arr, my_active(arr)


def _residual(arr):
    battle._apply_residual(my_active(arr), opp_active(arr), Field.MY_ENTER_FIELD, arr)


@pytest.mark.parametrize("species, item, change", [
    ("Rattata", "Leftovers", 16),
    ("Grimer", "Black Sludge", 16),
    ("Rattata", "Black Sludge", -8),
])
def test_gradual_items(make_pokemon, make_battle, species, item, change):
    """Leftovers heals 1/16, Black Sludge 1/16 for a Poison type and -1/8 for anyone else
    (pokeplatinum BattleSystem_TriggerLeftovers)"""
    arr, p = _residual_battle(make_pokemon, make_battle, species, "Run Away", item)
    p[Pok.CURRENT_HP] = 40
    _residual(arr)
    assert p[Pok.CURRENT_HP] == 40 + (p[Pok.MAX_HP] // abs(change)) * (1 if change > 0 else -1)


@pytest.mark.parametrize("species, ability, item", [
    ("Rattata", "Run Away", "Leftovers"), ("Grimer", "Stench", "Black Sludge"),
    ("Clefairy", "Magic Guard", "Black Sludge"),
])
def test_gradual_items_do_nothing(make_pokemon, make_battle, species, ability, item):
    """No heal at full HP, Magic Guard takes no Black Sludge damage"""
    arr, p = _residual_battle(make_pokemon, make_battle, species, ability, item)
    _residual(arr)
    assert p[Pok.CURRENT_HP] == p[Pok.MAX_HP]


def test_leftovers_before_poison(make_pokemon, make_battle):
    """The LEFTOVERS step comes first, so at full HP it heals nothing and poison takes 1/8"""
    arr, p = _residual_battle(make_pokemon, make_battle, "Rattata", "Run Away", "Leftovers")
    p[Pok.STATUS] = Status.POISON
    _residual(arr)
    assert p[Pok.CURRENT_HP] == p[Pok.MAX_HP] - p[Pok.MAX_HP] // 8


def test_black_sludge_can_faint(make_pokemon, make_battle):
    """Fainting to it skips the rest of the residuals"""
    arr, p = _residual_battle(make_pokemon, make_battle, "Rattata", "Run Away", "Black Sludge")
    p[Pok.CURRENT_HP] = 1
    p[Pok.STATUS] = Status.POISON
    _residual(arr)
    assert p[Pok.CURRENT_HP] == 0


@pytest.mark.parametrize("status", [Status.POISON, Status.TOXIC])
def test_poison_heal(make_pokemon, make_battle, status):
    """Heals 1/8 instead of the poison damage and names itself; toxic's counter still goes up
    (pokeplatinum subscript_poison_damage)"""
    arr, p = _residual_battle(make_pokemon, make_battle, "Shroomish", "Poison Heal")
    p[Pok.STATUS] = status
    p[Pok.BADLY_POISON] = 1 if status == Status.TOXIC else 0
    p[Pok.CURRENT_HP] = 40
    _residual(arr)
    assert p[Pok.CURRENT_HP] == 40 + p[Pok.MAX_HP] // 8 and p[Pok.AB_KNOWN]
    assert p[Pok.BADLY_POISON] == (2 if status == Status.TOXIC else 0)


def test_poison_heal_at_full_hp(make_pokemon, make_battle):
    """Nothing to heal, no message"""
    arr, p = _residual_battle(make_pokemon, make_battle, "Shroomish", "Poison Heal")
    p[Pok.STATUS] = Status.POISON
    _residual(arr)
    assert p[Pok.CURRENT_HP] == p[Pok.MAX_HP] and not p[Pok.AB_KNOWN]


def test_heatproof_halves_burn(make_pokemon, make_battle):
    """1/8 then halved (pokeplatinum subscript_burn_damage)"""
    arr, p = _residual_battle(make_pokemon, make_battle, "Bronzor", "Heatproof")
    p[Pok.STATUS] = Status.BURN
    _residual(arr)
    assert p[Pok.CURRENT_HP] == p[Pok.MAX_HP] - p[Pok.MAX_HP] // 8 // 2


@pytest.mark.parametrize("status", [Status.POISON, Status.BURN])
def test_status_damage_is_at_least_one(make_pokemon, make_battle, status):
    """pokeplatinum BattleSystem_Divide never gives 0"""
    arr, p = _residual_battle(make_pokemon, make_battle, "Rattata", "Run Away")
    p[Pok.MAX_HP] = 7
    p[Pok.CURRENT_HP] = 7
    p[Pok.STATUS] = status
    _residual(arr)
    assert p[Pok.CURRENT_HP] == 6


def _bad_dreams_battle(make_pokemon, make_battle, ability="Run Away"):
    """My sleeping Rattata against a Bad Dreams Darkrai"""
    arr = make_battle([make_pokemon("Rattata", 30, ability, ["Tackle"])],
                      [make_pokemon("Darkrai", 30, "Bad Dreams", ["Growl"])])
    p = my_active(arr)
    p[Pok.STATUS] = Status.SLEEP
    p[Pok.SLEEP_COUNTER] = 3
    return arr, p


def test_bad_dreams(make_pokemon, make_battle):
    """A sleeper loses 1/8 to the foe's Bad Dreams, whose message names it"""
    arr, p = _bad_dreams_battle(make_pokemon, make_battle)
    _residual(arr)
    assert p[Pok.CURRENT_HP] == p[Pok.MAX_HP] - p[Pok.MAX_HP] // 8
    assert opp_active(arr)[Pok.AB_KNOWN]


@pytest.mark.parametrize("case", ["awake", "magic_guard", "fainted_holder"])
def test_bad_dreams_does_nothing(make_pokemon, make_battle, case):
    """Only a sleeper without Magic Guard, only while the holder is alive (pokeplatinum
    MON_COND_CHECK_STATE_BAD_DREAMS)"""
    arr, p = _bad_dreams_battle(
        make_pokemon, make_battle, "Magic Guard" if case == "magic_guard" else "Run Away"
    )
    if case == "awake":
        p[Pok.STATUS] = 0
    if case == "fainted_holder":
        opp_active(arr)[Pok.CURRENT_HP] = 0
    _residual(arr)
    assert p[Pok.CURRENT_HP] == p[Pok.MAX_HP]


@pytest.mark.parametrize("species, ability, weather, change", [
    ("Snorunt", "Ice Body", Weather.HAIL, 16),
    ("Paras", "Dry Skin", Weather.RAIN, 8),
    ("Paras", "Dry Skin", Weather.SUN, -8),
    ("Rattata", "Snow Cloak", Weather.HAIL, 0),
])
def test_weather_step_abilities(make_pokemon, make_battle, species, ability, weather, change):
    """Ice Body and Dry Skin heal or hurt at the weather step, Snow Cloak takes no hail damage"""
    arr = make_battle([make_pokemon(species, 30, ability, ["Tackle"])],
                      [make_pokemon("Rattata", 30, "Run Away", ["Growl"])])
    p = my_active(arr)
    p[Pok.CURRENT_HP] = 40
    battle._residual_weather(p, weather, Field.MY_ENTER_FIELD, arr)
    sign = 1 if change > 0 else -1
    assert p[Pok.CURRENT_HP] == 40 + (sign * (p[Pok.MAX_HP] // abs(change)) if change else 0)


def test_shed_skin_cures_before_poison_damage(monkeypatch, make_pokemon, make_battle):
    """The ABILITY step comes before the poison step"""
    monkeypatch.setattr(engine_helper.random, "randint", lambda lo, hi: lo)
    me = make_pokemon("Metapod", 20, "Shed Skin", ["Tackle"])
    arr = make_battle([me], [make_pokemon("Rattata", 20, "Run Away", ["Growl"])])
    p = my_active(arr)
    p[Pok.STATUS] = Status.POISON
    battle._apply_residual(p, opp_active(arr), Field.MY_ENTER_FIELD, arr)
    assert p[Pok.STATUS] == 0 and p[Pok.CURRENT_HP] == p[Pok.MAX_HP]


def test_natural_cure_on_switch(make_pokemon, make_battle):
    """Switching out cures the Natural Cure holder"""
    my = [
        make_pokemon("Staryu", 20, "Natural Cure", ["Tackle"]),
        make_pokemon("Rattata", 20, "Run Away", ["Tackle"]),
    ]
    arr = make_battle(my, [make_pokemon("Rattata", 20, "Run Away", ["Growl"])])
    pok_slice(arr, 0)[Pok.STATUS] = Status.BURN
    turn_sim(0, (SWITCH, 1), arr)
    assert pok_slice(arr, 0)[Pok.STATUS] == 0


# ── The AI learns an ability from its message (pokeplatinum BattleMessage_AbilityTag) ──

def test_suction_cups_reveals_itself(make_pokemon, make_battle):
    """"X anchors itself with Suction Cups!" """
    arr = make_battle(
        [make_pokemon("Rattata", 20, "Run Away", ["Roar"])],
        [make_pokemon("Octillery", 20, "Suction Cups", ["Tackle"]),
         make_pokemon("Rattata", 20, "Run Away", ["Tackle"])])
    assert not battle._force_switch(my_active(arr), opp_active(arr), arr, False)
    assert opp_active(arr)[Pok.AB_KNOWN]


@pytest.mark.parametrize("stage, known", [(0, True), (6, False)])
def test_anger_point_reveals_when_attack_goes_up(poke, stage, known):
    """pokeplatinum subscript_critical_hit skips the message at +6"""
    a = poke("Rattata", 50, "Run Away", ["Tackle"])
    d = poke("Mankey", 50, "Anger Point", ["Scratch"])
    d[Pok.CURRENT_HP] = 60
    d[Pok.ATTACK_STAT_STAGE] = stage
    battle._apply_move_damage(a, d, move_slice(a, 0), 10, True)
    assert bool(d[Pok.AB_KNOWN]) == known


def test_yawn_sleep_blocked_by_ability_reveals_it(poke):
    """"X stayed awake because of its Insomnia!" at the end of the turn"""
    p = poke("Machop", 20, "Insomnia", ["Tackle"])
    p[Pok.VOL_STATUS] = VolStatus.YAWN
    p[Pok.YAWN_TURNS] = 1
    battle._yawn(p, poke("Rattata", 20, "Run Away", ["Tackle"]))
    assert p[Pok.AB_KNOWN]


@pytest.mark.parametrize("species, ability, weather, status", [
    ("Wingull", "Hydration", Weather.RAIN, Status.POISON),
    ("Sunkern", "Solar Power", Weather.SUN, 0),
])
def test_weather_step_abilities_reveal_themselves(make_pokemon, make_battle, species, ability,
                                                  weather, status):
    """Hydration's cure and Solar Power's damage name the ability"""
    arr = make_battle([make_pokemon(species, 20, ability, ["Tackle"])],
                      [make_pokemon("Rattata", 20, "Run Away", ["Growl"])])
    p = my_active(arr)
    p[Pok.STATUS] = status
    battle._residual_weather(p, weather, Field.MY_ENTER_FIELD, arr)
    assert p[Pok.AB_KNOWN]


def test_flame_orb_blocked_by_water_veil_reveals_it(poke):
    """pokeplatinum subscript_burn prints the ability for a held item"""
    p = poke("Goldeen", 20, "Water Veil", ["Tackle"])
    battle._flame_orb(p, 0, 0)
    assert p[Pok.STATUS] == 0 and p[Pok.AB_KNOWN]


# ── Power Herb, Metronome item, Liquid Ooze, Sticky Hold ─────────────────────

def test_power_herb_digs_and_hits_in_one_turn(make_pokemon, make_battle):
    """No underground turn: the hit lands now, the slower foe's Tackle reaches me, the herb is gone"""
    arr = make_battle([make_pokemon("Diglett", 50, "Sand Veil", ["Dig"], item="Power Herb")],
                      [make_pokemon("Munchlax", 30, "Thick Fat", ["Tackle"])])
    me, foe = my_active(arr), opp_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] < foe[Pok.MAX_HP] and me[Pok.CURRENT_HP] < me[Pok.MAX_HP]
    assert not me[Pok.VOL_STATUS] & VolStatus.SEMI_INVULNERABLE
    assert me[Pok.SEMI_INV_MOVE] == 0 and me[Pok.LOCKED_MOVE] == -1
    assert me[Item.ID] == 0 and me[Pok.CONSUMED_ITEM] == ItemNames.POWER_HERB


def _metronome_battle(make_pokemon, make_battle):
    """My Rattata holding the Metronome item vs a Munchlax that only Hardens"""
    return make_battle(
        [make_pokemon("Rattata", 50, "Run Away", ["Tackle", "Growl"], item="Metronome")],
        [make_pokemon("Munchlax", 50, "Thick Fat", ["Harden"])],
    )


def test_metronome_item_count_over_turns(monkeypatch, make_pokemon, make_battle):
    """Counts each Tackle in a row; a miss gives it back, a turn the move isn't reached keeps it,
    another move starts over"""
    arr = _metronome_battle(make_pokemon, make_battle)
    me = my_active(arr)
    tackle = MoveName.TACKLE << 4
    turn_sim(0, (MOVE, 0), arr)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.METRONOME_COUNT] == tackle + 1
    with monkeypatch.context() as m:
        m.setattr(battle, "calculate_hit_miss", lambda *args: MoveOutcome.MISS)
        turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.METRONOME_COUNT] == tackle + 1
    with monkeypatch.context() as m:
        m.setattr(battle, "early_returns", lambda *args: True)
        turn_sim(0, (MOVE, 1), arr)
    assert me[Pok.METRONOME_COUNT] == tackle + 1
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.METRONOME_COUNT] == tackle + 2
    turn_sim(0, (MOVE, 1), arr)
    assert me[Pok.METRONOME_COUNT] == MoveName.GROWL << 4


def test_metronome_item_skips_the_attack_turn_of_dig(make_pokemon, make_battle):
    """The locked attack turn doesn't count, so Dig twice in a row is one count"""
    arr = make_battle([make_pokemon("Diglett", 50, "Sand Veil", ["Dig"], item="Metronome")],
                      [make_pokemon("Munchlax", 50, "Thick Fat", ["Harden"])])
    me = my_active(arr)
    for _ in range(4):
        turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.METRONOME_COUNT] == (MoveName.DIG << 4) + 1


@pytest.mark.parametrize("seeder_ab", ["Run Away", "Magic Guard"])
def test_liquid_ooze_hurts_the_leech_seeder(make_pokemon, make_battle, seeder_ab):
    """The seeder loses what the seeded foe lost; Magic Guard takes nothing and both abilities are
    named (pokeplatinum subscript_leech_seed_effect)"""
    arr = make_battle([make_pokemon("Oddish", 30, seeder_ab, ["Tackle"])],
                      [make_pokemon("Tentacool", 30, "Liquid Ooze", ["Tackle"])])
    me, foe = my_active(arr), opp_active(arr)
    foe[Pok.VOL_STATUS] = VolStatus.LEECH_SEED
    me[Pok.CURRENT_HP] = 20
    end_of_turn(arr)
    drained = max(1, foe[Pok.MAX_HP] // 8)
    assert foe[Pok.CURRENT_HP] == foe[Pok.MAX_HP] - drained
    magic_guard = seeder_ab == "Magic Guard"
    assert me[Pok.CURRENT_HP] == (20 if magic_guard else 20 - drained)
    assert me[Pok.AB_KNOWN] == foe[Pok.AB_KNOWN] == magic_guard


def test_liquid_ooze_can_knock_out_the_leech_seeder(make_pokemon, make_battle):
    """The seeder faints from it like any end-of-turn damage"""
    arr = make_battle([make_pokemon("Oddish", 30, "Run Away", ["Tackle"]),
                       make_pokemon("Geodude", 10, "Sturdy", ["Tackle"])],
                      [make_pokemon("Tentacool", 30, "Liquid Ooze", ["Tackle"])])
    me, foe = my_active(arr), opp_active(arr)
    foe[Pok.VOL_STATUS] = VolStatus.LEECH_SEED
    me[Pok.CURRENT_HP] = 1
    end_of_turn(arr)
    assert me[Pok.CURRENT_HP] == 0


@pytest.mark.parametrize("move, item, attacker_ab, kept", [
    ("Covet", "Oran Berry", "Guts", True), ("Covet", "Oran Berry", "Mold Breaker", False),
    ("Bug Bite", "Sitrus Berry", "Guts", True), ("Bug Bite", "Sitrus Berry", "Mold Breaker", False),
])
def test_sticky_hold_keeps_the_item_from_covet_and_bug_bite(
        make_pokemon, make_battle, move, item, attacker_ab, kept):
    """The hit lands, only the steal / pluck fails (pokeplatinum BtlCmd_TryStealItem, TryPluck)"""
    arr = make_battle([make_pokemon("Machop", 20, attacker_ab, [move])],
                      [make_pokemon("Grimer", 20, "Sticky Hold", ["Leer"], item=item)])
    me, foe = my_active(arr), opp_active(arr)
    battle.ps_moves(me, foe, move_slice(me, 0), 0, False, False)
    assert foe[Pok.CURRENT_HP] < foe[Pok.MAX_HP]
    assert (foe[Item.ID] != 0) == kept


# ── Batch 15: Normalize ──────────────────────────────────────────────────────

@pytest.mark.parametrize("item, halved", [("Chilan Berry", True), ("Occa Berry", False)])
def test_normalize_resist_berries(make_pokemon, item, halved):
    """A normalized Ember is a Normal hit: Chilan halves it, Occa doesn't"""
    atk = make_pokemon("Skitty", 20, "Normalize", ["Ember"]).to_np()
    dfn = make_pokemon("Bulbasaur", 20, "Overgrow", ["Tackle"], item=item).to_np()
    got = engine_helper.resist_berry(atk, dfn, move_slice(atk, 0), 41)
    assert got == (20 if halved else 41)


def test_normalize_tells_the_ai_a_normal_hit(monkeypatch, make_pokemon, make_battle):
    """The type the AI's withdraw checks read is the one the move hit with (pokeplatinum
    moveHitType from CalcCurrentMoveType)"""
    monkeypatch.setattr(engine_helper.random, "randint", lambda a, b: a)
    arr = make_battle([make_pokemon("Skitty", 20, "Normalize", ["Ember"])],
                      [make_pokemon("Machop", 20, "Guts", ["Leer"])])
    turn_sim(0, (MOVE, 0), arr)
    assert opp_active(arr)[Pok.CURRENT_HP] < opp_active(arr)[Pok.MAX_HP]
    assert arr[Field.AI_TOOK_DMG_LAST_TURN] == Types.NORMAL


def test_struggle_crit_reaches_anger_point(monkeypatch, poke):
    """Struggle's crit comes out of the damage roll like any move's, so Anger Point sees it"""
    monkeypatch.setattr(battle, "calculate_crit", lambda *a: True)
    a = poke("Rattata", 5, "Run Away", ["Tackle"])
    d = poke("Mankey", 50, "Anger Point", ["Scratch"])
    battle._ps_moves_core(a, d, STRUGGLE.copy(), 0)  # pylint: disable=protected-access
    assert d[Pok.CURRENT_HP] > 0 and d[Pok.ATTACK_STAT_STAGE] == 6


def test_curse_takes_at_least_one(make_pokemon, make_battle):
    """Curse's quarter is at least 1 HP (pokeplatinum subscript_curse_damage, DivideVarByValue)"""
    arr = make_battle([make_pokemon("Rattata", 5, "Run Away", ["Tackle"])],
                      [make_pokemon("Rattata", 5, "Run Away", ["Tackle"])])
    me = my_active(arr)
    me[Pok.MAX_HP] = me[Pok.CURRENT_HP] = 3
    me[Pok.VOL_STATUS] |= VolStatus.CURSE
    end_of_turn(arr)
    assert me[Pok.CURRENT_HP] == 2


@pytest.mark.parametrize("ability, drowsy", [("Run Away", False), ("Soundproof", True)])
def test_yawn_fails_during_an_uproar(poke, ability, drowsy):
    """pokeplatinum subscript_yawn: an uproar makes Yawn fail, unless the target is Soundproof"""
    user = poke("Rattata", 20, "Run Away", ["Yawn"])
    target = poke("Rattata", 20, ability, ["Uproar"])
    target[Pok.VOL_STATUS] |= VolStatus.UPROAR
    vol_status(move_slice(user, 0), target, user)
    assert bool(target[Pok.VOL_STATUS] & VolStatus.YAWN) == drowsy


def test_ability_cures_a_forbidden_status_after_a_move(make_pokemon, make_battle):
    """pokeplatinum BattleControllerPlayer_MoveEnd runs RecoverStatusByAbility for the attacker and
    the defender after every move: a paralyzed Limber holder is cured"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Tackle"], ["Growl"])
    me = my_active(arr)
    me[Pok.AB_ID] = AbilityNames.LIMBER
    me[Pok.STATUS] = Status.PARALYSIS
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.STATUS] == 0


def test_failed_counter_spends_pp_and_counts_as_used(make_pokemon, make_battle):
    """Counter moving first fails after its PP is spent, and it's still the last move used"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Counter"], ["Growl"])
    me = my_active(arr)
    pp = move_slice(me, 0)[Move.PP]
    turn_sim(0, (MOVE, 0), arr)
    assert move_slice(me, 0)[Move.PP] == pp - 1
    assert me[Pok.LAST_MOVE_ID] == MoveName.COUNTER


def test_metronome_item_keeps_the_count_with_no_foe(monkeypatch, make_pokemon, make_battle):
    """The foe fainted to its own Selfdestruct before my Growl: the stored move and count stay
    (pokeplatinum HasNoTarget runs before UpdateMetronomeCount)"""
    monkeypatch.setattr(battle, "calculate_hit_miss", lambda *a: MoveOutcome.MISS)
    arr = make_battle(
        [make_pokemon("Rattata", 5, "Run Away", ["Tackle", "Growl"], item="Metronome")],
        [make_pokemon("Koffing", 50, "Levitate", ["Selfdestruct"])],
    )
    me = my_active(arr)
    me[Pok.METRONOME_COUNT] = (MoveName.TACKLE << 4) + 2
    turn_sim(0, (MOVE, 1), arr)
    assert opp_active(arr)[Pok.CURRENT_HP] == 0
    assert me[Pok.METRONOME_COUNT] == (MoveName.TACKLE << 4) + 2


# ── Phase 3: Substitute ──────────────────────────────────────────────────────

def _sub(pok, hp):
    """pok behind a Substitute of hp HP"""
    pok[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
    pok[Pok.SUB_HP] = hp


def _has_sub(pok):
    return bool(pok[Pok.VOL_STATUS2] & VolStatus2.SUBSTITUTE)


def _sure_hit(pok, slot, sec_chance=None):
    """The slot's move can't miss, and its secondary always rolls when sec_chance is 100"""
    mv = move_slice(pok, slot)
    mv[Move.ACCURACY] = -1
    if sec_chance is not None:
        mv[Sec.CHANCE] = sec_chance
    return mv


def _use(arr, slot, mine=True, rec=False):
    """One move slot, no foe action around it"""
    atk, defn = (my_active(arr), opp_active(arr)) if mine else (opp_active(arr), my_active(arr))
    mv = move_slice(atk, slot)
    battle._execute_move_slot(
        atk, defn, mv, mine, slot if mine else 0, 0 if mine else slot, False, 1, True, arr, 0,
        rec, rec
    )


def test_substitute_turn(make_pokemon, make_battle):
    """The user pays a quarter of its max HP, the foe's Tackle then hits the Substitute"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Substitute"], ["Tackle"])
    me = my_active(arr)
    cost = me[Pok.MAX_HP] // 4
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.CURRENT_HP] == me[Pok.MAX_HP] - cost
    assert _has_sub(me) and 0 < me[Pok.SUB_HP] < cost


def test_hit_on_the_substitute_leaves_the_pokemon_alone(make_pokemon, make_battle):
    """No HP lost, no hurt flag, nothing recorded for Bide / Counter, and the overflow is lost"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Tackle"], ["Tackle"], my_level=5,
                         opp_level=50)
    me = my_active(arr)
    _sub(me, 2)
    hp = me[Pok.CURRENT_HP]
    _use(arr, 0, mine=False, rec=True)
    assert me[Pok.CURRENT_HP] == hp and not _has_sub(me) and me[Pok.SUB_HP] == 0
    assert not me[Pok.VOL_STATUS] & VolStatus.HURT_THIS_TURN and me[Pok.DMG_TAKEN] == 0


def test_multihit_goes_on_after_the_substitute_breaks(make_pokemon, make_battle):
    """Double Kick: the first hit breaks it, the second hits the Pokemon"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Double Kick"], ["Tackle"], opp_level=50)
    foe = opp_active(arr)
    _sub(foe, 1)
    _use(arr, 0)
    assert not _has_sub(foe) and foe[Pok.CURRENT_HP] < foe[Pok.MAX_HP]


@pytest.mark.parametrize("sub_hp, poisoned", [(1, True), (999, False)])
def test_multihit_secondary_after_the_break(make_pokemon, make_battle, sub_hp, poisoned):
    """Twineedle's later hits poison once the Substitute is gone (Showdown), not through it"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Twineedle"], ["Tackle"], opp_level=50)
    _sure_hit(my_active(arr), 0, 100)
    foe = opp_active(arr)
    _sub(foe, sub_hp)
    _use(arr, 0)
    assert (foe[Pok.STATUS] == Status.POISON) == poisoned


def test_substitute_blocks_the_target_secondary_not_the_users(make_pokemon, make_battle):
    """Thunder Shock doesn't paralyze through it, Metal Claw still raises the user's Attack"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Thunder Shock", "Metal Claw"], ["Tackle"],
                         opp_level=50)
    me, foe = my_active(arr), opp_active(arr)
    _sure_hit(me, 0, 100)
    _sure_hit(me, 1, 100)
    _sub(foe, 999)
    _use(arr, 0)
    _use(arr, 1)
    assert foe[Pok.STATUS] == 0 and me[Pok.ATTACK_STAT_STAGE] == 1


def test_drain_and_recoil_read_what_the_substitute_lost(make_pokemon, make_battle):
    """Absorb heals half of the Substitute's lost HP, Take Down recoils a quarter of it"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Absorb", "Take Down"], ["Tackle"])
    me, foe = my_active(arr), opp_active(arr)
    _sure_hit(me, 1)
    me[Pok.CURRENT_HP] = 20
    _sub(foe, 8)
    _use(arr, 0)
    assert me[Pok.CURRENT_HP] == 24 and not _has_sub(foe)
    _sub(foe, 8)
    _use(arr, 1)
    assert me[Pok.CURRENT_HP] == 22


@pytest.mark.parametrize("move", ["Wrap", "Knock Off", "Covet"])
def test_substitute_keeps_off_trap_and_item_moves(make_pokemon, make_battle, move):
    """No bind, no knocked off or stolen item through a Substitute"""
    my = [make_pokemon("Rattata", 50, "Run Away", [move])]
    opp = [make_pokemon("Rattata", 50, "Run Away", ["Tackle"], item="Oran Berry")]
    arr = make_battle(my, opp)
    _sure_hit(my_active(arr), 0)
    foe = opp_active(arr)
    _sub(foe, 999)
    item = foe[Pok.ITEM_ID]
    _use(arr, 0)
    assert not foe[Pok.VOL_STATUS] & VolStatus.PARTIALLY_TRAPPED
    assert foe[Pok.ITEM_ID] == item and not foe[Pok.ITEM_KNOCKED_OFF]
    assert my_active(arr)[Pok.ITEM_ID] == 0


def test_contact_abilities_and_resist_berries_stay_out(make_pokemon, make_battle):
    """Rough Skin doesn't hurt the attacker and a Chilan Berry isn't eaten on a Substitute hit"""
    my = [make_pokemon("Rattata", 50, "Run Away", ["Tackle"])]
    opp = [make_pokemon("Carvanha", 50, "Rough Skin", ["Tackle"], item="Chilan Berry")]
    arr = make_battle(my, opp)
    me, foe = my_active(arr), opp_active(arr)
    _sub(foe, 999)
    item = foe[Pok.ITEM_ID]
    _use(arr, 0)
    assert me[Pok.CURRENT_HP] == me[Pok.MAX_HP] and foe[Pok.ITEM_ID] == item


def test_fire_move_doesnt_thaw_through_a_substitute(make_pokemon, make_battle):
    """Showdown thaws on a damaging hit, the Substitute's isn't one. The AI's took-damage
    record stays empty too"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Ember"], ["Tackle"], opp_level=50)
    foe = opp_active(arr)
    foe[Pok.STATUS] = Status.FREEZE
    _sub(foe, 999)
    _use(arr, 0)
    assert foe[Pok.STATUS] == Status.FREEZE
    assert arr[Field.AI_TOOK_DMG_LAST_TURN] == 0


def test_ohko_move_breaks_the_substitute(make_pokemon, make_battle):
    """It takes max HP on a Substitute, so it breaks even above the Pokemon's own HP"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Fissure"], ["Tackle"])
    move_slice(my_active(arr), 0)[Move.ACCURACY] = 100
    foe = opp_active(arr)
    foe[Pok.CURRENT_HP] = 3
    _sub(foe, 10)
    _use(arr, 0)
    assert not _has_sub(foe) and foe[Pok.CURRENT_HP] == 3


@pytest.mark.parametrize("move, works", [
    ("Thunder Wave", False), ("Growl", False), ("Sing", False), ("Taunt", True),
])
def test_status_moves_into_a_substitute(make_pokemon, make_battle, move, works):
    """Only the moves that bypass it get through, sound moves don't in Gen IV"""
    arr = _phase3_battle(make_pokemon, make_battle, [move], ["Tackle"], opp_level=50)
    _sure_hit(my_active(arr), 0)
    foe = opp_active(arr)
    _sub(foe, 999)
    _use(arr, 0)
    changed = (
        foe[Pok.STATUS] != 0, foe[Pok.ATTACK_STAT_STAGE] != 0,
        bool(foe[Pok.VOL_STATUS] & VolStatus.TAUNT),
    )
    assert any(changed) == works


def test_ghost_curse_fails_into_a_substitute_without_its_cost(make_pokemon, make_battle):
    """pokeplatinum subscript_curse_ghost checks the Substitute before cutting the user's HP"""
    my = [make_pokemon("Gastly", 30, "Levitate", ["Curse"])]
    arr = make_battle(my, [make_pokemon("Rattata", 30, "Run Away", ["Tackle"])])
    me, foe = my_active(arr), opp_active(arr)
    _sub(foe, 999)
    _use(arr, 0)
    assert me[Pok.CURRENT_HP] == me[Pok.MAX_HP] and not foe[Pok.VOL_STATUS] & VolStatus.CURSE


def test_baton_pass_passes_the_substitute(make_pokemon, make_battle):
    """The receiver gets it with its HP, the user loses it"""
    arr = _baton_battle(make_pokemon, make_battle, 30, 10)
    rattata = my_active(arr)
    _sub(rattata, 7)
    turn_sim(0, (MOVE, 0), arr)
    battle.baton_pass_action(arr, 1)
    geodude = my_active(arr)
    assert _has_sub(geodude) and 0 < geodude[Pok.SUB_HP] <= 7
    assert not _has_sub(rattata) and rattata[Pok.SUB_HP] == 0


def test_rage_glitch_drops_the_substitute(make_pokemon, make_battle):
    """Substitute is a statusVolatile bit in pokeplatinum, the glitch wipes it"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Rage", "Tail Whip"], ["Growl"])
    me = my_active(arr)
    me[Pok.VOL_STATUS] = VolStatus.RAGE
    _sub(me, 5)
    turn_sim(0, (MOVE, 1), arr)
    assert not _has_sub(me) and me[Pok.SUB_HP] == 0


# ── 4.2: Life Orb, Shell Bell, Focus Sash, Toxic Orb, Sticky Barb ────────────

def _item_battle(make_pokemon, make_battle, my_item, my_move="Tackle", opp_item=None,
                 opp="Munchlax", opp_ability="Thick Fat"):
    """My Rattata with my_item vs a foe that only Growls"""
    return make_battle([make_pokemon("Rattata", 50, "Run Away", [my_move], item=my_item)],
                       [make_pokemon(opp, 50, opp_ability, ["Growl"], item=opp_item)])


@pytest.mark.parametrize("move, sub, recoil", [
    ("Tackle", False, True), ("Tackle", True, False), ("Seismic Toss", False, False),
])
def test_life_orb_recoil_after_my_move(make_pokemon, make_battle, move, sub, recoil):
    """1/10 of max HP once the hit reaches the foe; a Substitute or fixed damage costs nothing"""
    arr = _item_battle(make_pokemon, make_battle, "Life Orb", move)
    me, foe = my_active(arr), opp_active(arr)
    _sure_hit(me, 0)
    if sub:
        _sub(foe, 200)
    full = int(me[Pok.MAX_HP])
    _use(arr, 0)
    assert me[Pok.CURRENT_HP] == (full - full // 10 if recoil else full)


def test_shell_bell_heals_after_my_hit(make_pokemon, make_battle):
    """1/8 of what the foe lost, at least 1"""
    arr = _item_battle(make_pokemon, make_battle, "Shell Bell")
    me, foe = my_active(arr), opp_active(arr)
    _sure_hit(me, 0)
    me[Pok.CURRENT_HP] = 1
    _use(arr, 0)
    dealt = int(foe[Pok.MAX_HP] - foe[Pok.CURRENT_HP])
    assert dealt > 0 and me[Pok.CURRENT_HP] == 1 + max(1, dealt // 8)


def _big_hits(monkeypatch, damage):
    monkeypatch.setattr(battle, "_resolve_move_damage", lambda *args: (damage, False))


@pytest.mark.parametrize("full_hp, survives", [(True, True), (False, False)])
def test_focus_sash_holds_every_hit_of_a_multihit_move(monkeypatch, poke, full_hp, survives):
    """Gen IV: found at full HP on the first hit, the Sash holds every lethal hit after it
    (pokeplatinum focusItemActivated lasts the move, Showdown gen4 focussash)"""
    a = poke("Shellder", 50, "Skill Link", ["Fury Attack"])
    d = poke("Rattata", 20, "Run Away", ["Tackle"], item="Focus Sash")
    _big_hits(monkeypatch, int(d[Pok.MAX_HP]) * 6 // 10)
    if not full_hp:
        d[Pok.CURRENT_HP] -= 1
    battle.ps_moves_multihit(a, d, move_slice(a, 0), 0, False, False)
    assert (d[Pok.CURRENT_HP] == 1) == survives
    assert d[Item.ID] == (0 if survives else ItemNames.FOCUS_SASH)


def test_focus_sash_after_the_substitute_breaks(monkeypatch, poke):
    """The hit on the Substitute doesn't count, the next one finds the holder at full HP"""
    a = poke("Shellder", 50, "Skill Link", ["Fury Attack"])
    d = poke("Rattata", 20, "Run Away", ["Tackle"], item="Focus Sash")
    _sub(d, 5)
    _big_hits(monkeypatch, 10_000)
    battle.ps_moves_multihit(a, d, move_slice(a, 0), 0, False, False)
    assert not _has_sub(d) and d[Pok.CURRENT_HP] == 1 and d[Item.ID] == 0


def test_focus_sash_holds_an_ohko_move(poke):
    """An OHKO takes the current HP, so a Sash at full HP holds it"""
    a = poke("Krabby", 50, "Hyper Cutter", ["Guillotine"])
    d = poke("Rattata", 20, "Run Away", ["Tackle"], item="Focus Sash")
    battle.ps_moves(a, d, move_slice(a, 0), 0, False, False)
    assert d[Pok.CURRENT_HP] == 1 and d[Pok.CONSUMED_ITEM] == ItemNames.FOCUS_SASH


@pytest.mark.parametrize("species, ability, side, toxic", [
    ("Rattata", "Run Away", 0, True),
    ("Magnemite", "Sturdy", 0, False),
    ("Grimer", "Stench", 0, False),
    ("Snorlax", "Immunity", 0, False),
    ("Rattata", "Run Away", SideCondition.SAFEGUARD, False),
])
def test_toxic_orb(poke, species, ability, side, toxic):
    """Badly poisons its holder unless it's Poison or Steel, has Immunity or Safeguard
    (pokeplatinum subscript_badly_poison, held item branch)"""
    p = poke(species, 20, ability, ["Tackle"], item="Toxic Orb")
    battle._flame_orb(p, side, 0)
    assert (p[Pok.STATUS] == Status.TOXIC) == toxic
    assert bool(p[Pok.AB_KNOWN]) == (ability == "Immunity")


def test_toxic_orb_at_the_end_of_the_turn_after_the_poison_step(make_pokemon, make_battle):
    """It comes after the poison damage, so the first 1/16 is next turn"""
    arr = _item_battle(make_pokemon, make_battle, "Toxic Orb", "Growl")
    me = my_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.STATUS] == Status.TOXIC and me[Pok.CURRENT_HP] == me[Pok.MAX_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.CURRENT_HP] == me[Pok.MAX_HP] - max(1, me[Pok.MAX_HP] // 16)


@pytest.mark.parametrize("species, ability, loses", [
    ("Rattata", "Run Away", True), ("Clefairy", "Magic Guard", False),
])
def test_sticky_barb_hurts_its_holder(make_pokemon, make_battle, species, ability, loses):
    """1/8 of max HP at the end of the turn, Magic Guard is immune"""
    arr = make_battle([make_pokemon(species, 50, ability, ["Growl"], item="Sticky Barb")],
                      [make_pokemon("Munchlax", 50, "Thick Fat", ["Growl"])])
    me = my_active(arr)
    full = int(me[Pok.MAX_HP])
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.CURRENT_HP] == (full - full // 8 if loses else full)


def test_sticky_barb_sticks_to_my_tackle(make_pokemon, make_battle):
    """My contact hit takes the foe's barb, and it hurts me at the end of the turn"""
    arr = _item_battle(make_pokemon, make_battle, None, opp_item="Sticky Barb")
    me, foe = my_active(arr), opp_active(arr)
    _sure_hit(me, 0)
    full = int(me[Pok.MAX_HP])
    turn_sim(0, (MOVE, 0), arr)
    assert me[Item.ID] == ItemNames.STICKY_BARB and foe[Item.ID] == 0
    assert me[Pok.CURRENT_HP] == full - full // 8


# ── 4.3 Berries ──────────────────────────────────────────────────────────────

def test_jaboca_stops_a_multihit_move(monkeypatch, poke):
    """Jaboca's damage KOs the user on the first hit, the remaining hits don't happen (Showdown
    onDamagingHit, per hit)"""
    core = battle._ps_moves_core
    calls = []

    def counting_core(*args):
        calls.append(1)
        return core(*args)

    monkeypatch.setattr(battle, "_ps_moves_core", counting_core)
    a = poke("Shellder", 50, "Skill Link", ["Fury Attack"])
    a[Pok.CURRENT_HP] = 1
    d = poke("Snorlax", 100, "Thick Fat", ["Tackle"], item="Jaboca Berry")
    battle.ps_moves_multihit(a, d, move_slice(a, 0), 0, False, False)
    assert a[Pok.CURRENT_HP] == 0 and d[Item.ID] == 0
    assert len(calls) == 1


def test_jaboca_not_through_a_substitute(make_pokemon, make_battle):
    """A hit on the Substitute leaves the berry alone"""
    arr = _item_battle(make_pokemon, make_battle, None, opp_item="Jaboca Berry")
    me, foe = my_active(arr), opp_active(arr)
    _sure_hit(me, 0)
    foe[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
    foe[Pok.SUB_HP] = 200
    _use(arr, 0)
    assert foe[Item.ID] == ItemNames.JABOCA_BERRY and me[Pok.CURRENT_HP] == me[Pok.MAX_HP]


def test_custap_turn(make_pokemon, make_battle):
    """My slow Custap holder in a pinch hits first and the berry is gone after the turn"""
    arr = make_battle(
        [make_pokemon("Geodude", 50, "Sturdy", ["Tackle"], item="Custap Berry")],
        [make_pokemon("Rattata", 50, "Run Away", ["Tackle"])],
    )
    me = my_active(arr)
    me[Pok.CURRENT_HP] = 1
    first = battle.move_order(me, 0, opp_active(arr), 0, False, False, 0)
    assert first[3] is True and me[Item.ID] == 0


# ── Choice items ─────────────────────────────────────────────────────────────

def _choice_battle(make_pokemon, make_battle, my_moves, my_item="Choice Band", opp=None):
    me = make_pokemon("Rattata", 30, "Run Away", my_moves, item=my_item)
    return make_battle([me], opp or [make_pokemon("Geodude", 30, "Sturdy", ["Defense Curl"])])


def test_choice_item_locks_into_the_move_that_ran(make_pokemon, make_battle):
    """The first move locks the holder, the other slots can't be picked"""
    arr = _choice_battle(make_pokemon, make_battle, ["Tackle", "Growl"])
    me = my_active(arr)
    turn_sim(0, (MOVE, 1), arr)
    assert me[Pok.CHOICE_LOCK] == 2
    assert engine_helper.move_blocked(me, 0) and not engine_helper.move_blocked(me, 1)


def test_choice_item_doesnt_lock_on_a_turn_without_the_move(monkeypatch, make_pokemon, make_battle):
    """Full paralysis, a flinch or sleep: "X used Y!" never shows, no lock (pokeplatinum
    SYSCTL_ATTACK_MESSAGE_SHOWN)"""
    arr = _choice_battle(make_pokemon, make_battle, ["Tackle", "Growl"])
    monkeypatch.setattr(battle, "early_returns", lambda *args: True)
    turn_sim(0, (MOVE, 1), arr)
    assert my_active(arr)[Pok.CHOICE_LOCK] == 0


def test_choice_item_locks_metronome_into_itself(make_pokemon, make_battle):
    """The selected move locks, not the one Metronome called"""
    battle.random.seed(4)
    arr = _choice_battle(make_pokemon, make_battle, ["Tackle", "Metronome"])
    turn_sim(0, (MOVE, 1), arr)
    assert my_active(arr)[Pok.CHOICE_LOCK] == 2


def test_choice_lock_follows_the_foe(make_pokemon, make_battle):
    """The foe's move locks it the same way"""
    opp = [make_pokemon("Geodude", 30, "Sturdy", ["Tackle", "Defense Curl"], item="Choice Scarf")]
    arr = _choice_battle(make_pokemon, make_battle, ["Growl"], my_item="", opp=opp)
    turn_sim(1, (MOVE, 0), arr)
    assert opp_active(arr)[Pok.CHOICE_LOCK] == 2


def test_covet_stealing_a_choice_item_locks_into_covet(make_pokemon, make_battle):
    """The item is read after the move (pokeplatinum UpdateMoveBuffers)"""
    battle.random.seed(1)
    opp = [make_pokemon("Geodude", 30, "Sturdy", ["Defense Curl"], item="Choice Band")]
    arr = _choice_battle(make_pokemon, make_battle, ["Tackle", "Covet"], my_item="", opp=opp)
    me = my_active(arr)
    turn_sim(0, (MOVE, 1), arr)
    assert me[Item.ID] == ItemNames.CHOICE_BAND and me[Pok.CHOICE_LOCK] == 2


def test_pursuit_on_a_switch_locks(make_pokemon, make_battle):
    """Pursuit before the switch locks its user (pokeplatinum BtlCmd_TryPursuit)"""
    mine = [make_pokemon("Rattata", 20, "Run Away", ["Tackle"]),
            make_pokemon("Geodude", 20, "Sturdy", ["Tackle"])]
    opp = [make_pokemon("Murkrow", 20, "Insomnia", ["Growl", "Pursuit"], item="Choice Band")]
    arr = make_battle(mine, opp)
    turn_sim(1, (SWITCH, 1), arr)
    assert opp_active(arr)[Pok.CHOICE_LOCK] == 2


def test_baton_pass_doesnt_pass_the_choice_lock(make_pokemon, make_battle):
    """The passer's lock ends on switch-out, the one coming in isn't locked"""
    mine = [make_pokemon("Rattata", 30, "Run Away", ["Baton Pass"], item="Choice Band"),
            make_pokemon("Geodude", 20, "Sturdy", ["Tackle"], item="Choice Band")]
    arr = make_battle(mine, [make_pokemon("Machop", 10, "Guts", ["Leer"])])
    rattata = my_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    battle.baton_pass_action(arr, 1)
    assert rattata[Pok.CHOICE_LOCK] == 0 and my_active(arr)[Pok.CHOICE_LOCK] == 0


def test_choice_lock_with_no_pp_left_struggles(make_pokemon, make_battle):
    """The locked move out of PP leaves only Struggle, which keeps the lock"""
    arr = _choice_battle(make_pokemon, make_battle, ["Tackle", "Growl"])
    me = my_active(arr)
    me[Pok.CHOICE_LOCK] = 1
    move_slice(me, 0)[Move.PP] = 0
    hp = opp_active(arr)[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 10), arr)
    assert opp_active(arr)[Pok.CURRENT_HP] < hp and me[Pok.CHOICE_LOCK] == 1
