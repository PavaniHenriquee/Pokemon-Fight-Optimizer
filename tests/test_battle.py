"""Turn flow (start_of_turn / action / end_of_turn / switches) and a seeded fuzz over
whole battles that checks state invariants after every decision"""
import random
import pytest
from Engine import battle
from Engine.battle import start_of_turn, end_of_turn, turn_sim, switch_in_action
from Engine.status_calc import vol_status
from Models.idx_const import (
    Pok, Move, Sec, Field, Flags, POK_LEN, SIDE_REFLECT_TURNS, SIDE_LIGHT_SCREEN_TURNS, SIDE_MIST_TURNS,
    SIDE_SAFEGUARD_TURNS, SIDE_LUCKY_CHANT_TURNS, SIDE_TOXIC_SPIKES, FIELD_LEN, SIDE_SPIKES,
    SIDE_FUTURE_TURNS, SIDE_FUTURE_DAMAGE, SIDE_FUTURE_MOVE,
)
from Models.helper import (
    ActionType, BattlePhase, Status, Potions, MoveOutcome, VolStatus, VolStatus2, Types, SideCondition,
    Weather,
    Enemy_AI_Knows, HoldEffect,
)
from Models.idx_const import Item
from DataBase.ItemDB import ItemNames
from DataBase.AbilitiesDB import AbilityNames
from DataBase.MoveDB import MoveName
from DataBase.PkDB import PokemonName
from Engine import engine_helper
from Engine.speed import check_speed
from Models.helper import Terrain
from Models.move import STRUGGLE
from Models.constants import _ENEMY_AI_KNOWS_MOVE2
from Models.trainer_ai import return_idx
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
            # My Healing Wish user (or its replacement the hazards KOed) waits for my pick fainted
            healing_wish = (
                arr[Field.PHASE] == BattlePhase.BATON_PASS
                and arr[Field.MY_SIDE_COND] & SideCondition.HEALING_WISH
            )
            if not healing_wish:
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


@pytest.mark.parametrize("level", [5, 100])
def test_sonic_boom_deals_20(poke, level):
    """Always 20, whatever the stats"""
    a = poke("Magnemite", level, "Sturdy", ["Sonic Boom"])
    d = poke("Snorlax", 50, "Thick Fat", ["Tackle"])
    hp = d[Pok.CURRENT_HP]
    battle.ps_moves(a, d, move_slice(a, 0), 0, False, False)
    assert hp - d[Pok.CURRENT_HP] == 20


@pytest.mark.parametrize("move", ["Double-Edge", "Flare Blitz", "Head Smash", "Wild Charge"])
def test_recoil_moves_recoil_from_hp_lost(monkeypatch, poke, move):
    """A third, a half or a quarter of what the target lost"""
    monkeypatch.setattr(battle, "calculate_hit_miss", lambda *a: MoveOutcome.HIT)
    a = poke("Rattata", 50, "Run Away", [move])
    d = poke("Snorlax", 50, "Thick Fat", ["Tackle"])
    a_hp, d_hp = a[Pok.CURRENT_HP], d[Pok.CURRENT_HP]
    battle.ps_moves(a, d, move_slice(a, 0), 0, False, False)
    dealt = d_hp - d[Pok.CURRENT_HP]
    assert dealt > 0
    assert a_hp - a[Pok.CURRENT_HP] == max(1, dealt // move_slice(a, 0)[Move.RECOIL])


@pytest.mark.parametrize("move", ["Double Hit", "Bonemerang"])
def test_two_hit_moves_hit_twice(monkeypatch, poke, move):
    """Double Hit and Bonemerang are 2 hits, like Double Kick"""
    core = battle._ps_moves_core
    calls = []

    def counting_core(*args):
        calls.append(1)
        return core(*args)

    monkeypatch.setattr(battle, "_ps_moves_core", counting_core)
    a = poke("Machop", 50, "Guts", [move])
    d = poke("Snorlax", 100, "Thick Fat", ["Tackle"])
    battle.ps_moves_multihit(a, d, move_slice(a, 0), 0, False, False)
    assert len(calls) == 2


def test_rp_cut_is_a_high_crit_move(poke):
    """RP's Cut: Grass, 60 power, high critical ratio"""
    cut = move_slice(poke("Rattata", 50, "Run Away", ["Cut"]), 0)
    assert (cut[Move.CRIT_RATIO], cut[Move.POWER], cut[Move.TYPE]) == (2, 60, Types.GRASS)


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


def _charge_battle(make_pokemon, make_battle, monkeypatch, move, item=None, foe_ability="Immunity"):
    """A faster charge move user that always hits a bulky foe that only uses Defense Curl"""
    monkeypatch.setattr(battle, "calculate_hit_miss", lambda *a: MoveOutcome.HIT)
    arr = make_battle([make_pokemon("Rattata", 50, "Run Away", [move], item=item)],
                      [make_pokemon("Snorlax", 50, foe_ability, ["Defense Curl"])])
    return arr, my_active(arr), opp_active(arr)


@pytest.mark.parametrize("move", ["Solar Beam", "Skull Bash", "Sky Attack", "Razor Wind"])
def test_charge_move_charges_then_hits(make_pokemon, make_battle, monkeypatch, move):
    """Turn 1 locks the slot and deals nothing, turn 2 hits and frees it, PP is paid once"""
    arr, me, foe = _charge_battle(make_pokemon, make_battle, monkeypatch, move)
    pp = move_slice(me, 0)[Move.PP]
    turn_sim(0, (MOVE, 0), arr)
    assert (me[Pok.LOCKED_MOVE], me[Pok.CHARGE_RECHARGE]) == (0, 1)
    assert foe[Pok.CURRENT_HP] == foe[Pok.MAX_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] < foe[Pok.MAX_HP]
    assert (me[Pok.LOCKED_MOVE], me[Pok.CHARGE_RECHARGE]) == (-1, 0)
    assert move_slice(me, 0)[Move.PP] == pp - 1


def test_solar_beam_skips_the_charge_in_sun(make_pokemon, make_battle, monkeypatch):
    """Sun: the hit lands on the first turn and the Power Herb stays (pokeplatinum effect 0151)"""
    arr, me, foe = _charge_battle(make_pokemon, make_battle, monkeypatch, "Solar Beam", item="Power Herb")
    arr[Field.WEATHER] = Weather.SUN
    arr[Field.WEATHER_DURATION] = 5
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] < foe[Pok.MAX_HP]
    assert (me[Pok.LOCKED_MOVE], me[Pok.CHARGE_RECHARGE]) == (-1, 0)
    assert me[Item.ID] == ItemNames.POWER_HERB


@pytest.mark.parametrize("ability", ["Cloud Nine", "Air Lock"])
def test_solar_beam_charges_in_suppressed_sun(make_pokemon, make_battle, monkeypatch, ability):
    """Cloud Nine and Air Lock take the sun away, so Solar Beam charges (CheckIgnoreWeather)"""
    arr, me, foe = _charge_battle(make_pokemon, make_battle, monkeypatch, "Solar Beam", foe_ability=ability)
    arr[Field.WEATHER] = Weather.SUN
    arr[Field.WEATHER_DURATION] = 5
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] == foe[Pok.MAX_HP]
    assert (me[Pok.LOCKED_MOVE], me[Pok.CHARGE_RECHARGE]) == (0, 1)


@pytest.mark.parametrize("stage, expected", [(0, 1), (-2, -1), (6, 6)])
def test_skull_bash_raises_defense_on_the_charge_turn(make_pokemon, make_battle, monkeypatch, stage, expected):
    """Defense +1 on the charge turn only, capped at +6 (pokeplatinum effect 0145)"""
    arr, me, _ = _charge_battle(make_pokemon, make_battle, monkeypatch, "Skull Bash")
    me[Pok.DEFENSE_STAT_STAGE] = stage
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.DEFENSE_STAT_STAGE] == expected
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.DEFENSE_STAT_STAGE] == expected


def test_skull_bash_power_herb_raises_defense_and_hits(make_pokemon, make_battle, monkeypatch):
    """Power Herb: Defense +1, then the hit in the same turn (subscript_power_herb_skull_bash)"""
    arr, me, foe = _charge_battle(make_pokemon, make_battle, monkeypatch, "Skull Bash", item="Power Herb")
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.DEFENSE_STAT_STAGE] == 1
    assert foe[Pok.CURRENT_HP] < foe[Pok.MAX_HP]
    assert me[Pok.LOCKED_MOVE] == -1 and me[Item.ID] == 0


def _beam_battle(make_pokemon, make_battle, monkeypatch, ability="Run Away", move="Hyper Beam"):
    """A faster Hyper Beam user that always hits a bulky foe that only uses Defense Curl"""
    monkeypatch.setattr(battle, "calculate_hit_miss", lambda *a: MoveOutcome.HIT)
    arr = make_battle([make_pokemon("Rattata", 50, ability, [move, "Tackle"])],
                      [make_pokemon("Snorlax", 50, "Immunity", ["Defense Curl"])])
    return arr, my_active(arr), opp_active(arr)


@pytest.mark.parametrize("move", [
    "Hyper Beam", "Giga Impact", "Blast Burn", "Hydro Cannon", "Frenzy Plant", "Roar of Time", "Rock Wrecker",
])
def test_recharge_blocks_the_next_turn_only(make_pokemon, make_battle, monkeypatch, move):
    """The hit locks the slot into a recharge, the next turn does nothing and spends no PP, then it's free"""
    arr, me, foe = _beam_battle(make_pokemon, make_battle, monkeypatch, move=move)
    turn_sim(0, (MOVE, 0), arr)
    assert (me[Pok.CHARGE_RECHARGE], me[Pok.LOCKED_MOVE]) == (-1, 0)
    hp, pp = foe[Pok.CURRENT_HP], move_slice(me, 0)[Move.PP]
    turn_sim(0, (MOVE, 0), arr)
    assert (me[Pok.CHARGE_RECHARGE], me[Pok.LOCKED_MOVE]) == (0, -1)
    assert foe[Pok.CURRENT_HP] == hp and move_slice(me, 0)[Move.PP] == pp
    turn_sim(0, (MOVE, 1), arr)
    assert foe[Pok.CURRENT_HP] < hp


@pytest.mark.parametrize("outcome", [MoveOutcome.MISS, MoveOutcome.PROTECTED, MoveOutcome.INVULNERABLE])
def test_no_recharge_without_a_hit(make_pokemon, make_battle, monkeypatch, outcome):
    """A miss, Protect or an immune target: no recharge"""
    arr, me, _ = _beam_battle(make_pokemon, make_battle, monkeypatch)
    monkeypatch.setattr(battle, "calculate_hit_miss", lambda *a: outcome)
    turn_sim(0, (MOVE, 0), arr)
    assert (me[Pok.CHARGE_RECHARGE], me[Pok.LOCKED_MOVE]) == (0, -1)


def test_recharge_after_a_ko(make_pokemon, make_battle, monkeypatch):
    """Gen II on, a KO still costs the recharge"""
    arr, me, foe = _beam_battle(make_pokemon, make_battle, monkeypatch)
    foe[Pok.CURRENT_HP] = 1
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] == 0
    assert me[Pok.CHARGE_RECHARGE] == -1


def test_recharge_after_a_substitute_hit(make_pokemon, make_battle, monkeypatch):
    """Only Gen I skips the recharge when the hit lands on a Substitute"""
    arr, me, foe = _beam_battle(make_pokemon, make_battle, monkeypatch)
    foe[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
    foe[Pok.SUB_HP] = 200
    hp = foe[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] == hp
    assert me[Pok.CHARGE_RECHARGE] == -1


def test_truant_loaf_is_the_recharge_turn(make_pokemon, make_battle, monkeypatch):
    """pokeplatinum checks Truant first and clears the recharge at the next turn's setup either way, so the
    loaf turn and the recharge turn are the same one"""
    arr, me, foe = _beam_battle(make_pokemon, make_battle, monkeypatch, ability="Truant")
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.CHARGE_RECHARGE] == -1
    hp = foe[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert (me[Pok.CHARGE_RECHARGE], me[Pok.LOCKED_MOVE]) == (0, -1) and foe[Pok.CURRENT_HP] == hp
    turn_sim(0, (MOVE, 1), arr)
    assert foe[Pok.CURRENT_HP] < hp


@pytest.mark.parametrize("status, counter", [(Status.SLEEP, 3), (Status.SLEEP, 1), (Status.FREEZE, 0)])
def test_blocked_turn_uses_up_the_recharge(make_pokemon, make_battle, monkeypatch, status, counter):
    """Sleep or freeze on the recharge turn uses it up, and waking up that turn still recharges"""
    arr, me, foe = _beam_battle(make_pokemon, make_battle, monkeypatch)
    monkeypatch.setattr(engine_helper, "freeze", lambda: True)
    turn_sim(0, (MOVE, 0), arr)
    me[Pok.STATUS] = status
    me[Pok.SLEEP_COUNTER] = counter
    hp = foe[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert (me[Pok.CHARGE_RECHARGE], me[Pok.LOCKED_MOVE]) == (0, -1) and foe[Pok.CURRENT_HP] == hp


def test_ai_recharge_turn_is_forced(make_pokemon, make_battle, monkeypatch):
    """The AI's recharge turn plays its locked slot"""
    monkeypatch.setattr(battle, "calculate_hit_miss", lambda *a: MoveOutcome.HIT)
    arr = make_battle([make_pokemon("Onix", 50, "Sturdy", ["Harden"])],
                      [make_pokemon("Rattata", 50, "Run Away", ["Tackle", "Hyper Beam"])])
    turn_sim(1, (MOVE, 0), arr)
    foe = opp_active(arr)
    assert (foe[Pok.CHARGE_RECHARGE], foe[Pok.LOCKED_MOVE]) == (-1, 1)
    assert return_idx(arr) == 1


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


def _rampaging(arr, turns):
    """My active is locked into slot 0's rampage with `turns` left"""
    me = my_active(arr)
    me[Pok.RAMPAGE_TURNS] = turns
    me[Pok.LOCKED_MOVE] = 0
    return me


@pytest.mark.parametrize("move", ["Thrash", "Outrage", "Petal Dance"])
def test_rampage_locks_2_to_3_turns_then_confuses(monkeypatch, make_pokemon, make_battle, move):
    """PP only on the first turn, the lock ends with the counter and the user gets confused
    (pokeplatinum subscript_thrash, MON_COND_CHECK_STATE_THRASH)"""
    _always_hit(monkeypatch)
    arr = _phase3_battle(make_pokemon, make_battle, [move, "Growl"], ["Growl"])
    me = my_active(arr)
    pp = move_slice(me, 0)[Move.PP]
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.LOCKED_MOVE] == 0 and me[Pok.RAMPAGE_TURNS] in (1, 2)
    turns = 1
    while me[Pok.RAMPAGE_TURNS]:
        assert not me[Pok.VOL_STATUS] & VolStatus.CONFUSION
        turn_sim(0, (MOVE, 0), arr)
        turns += 1
    assert turns in (2, 3) and me[Pok.LOCKED_MOVE] == -1
    assert me[Pok.VOL_STATUS] & VolStatus.CONFUSION and 2 <= me[Pok.CONFUSION_COUNTER] <= 5
    assert move_slice(me, 0)[Move.PP] == pp - 1


def test_rampage_needs_a_first_hit(monkeypatch, make_pokemon, make_battle):
    """A miss on the first turn doesn't lock in (an on-hit side effect)"""
    _always_hit(monkeypatch)
    monkeypatch.setattr(battle, "calculate_hit_miss", lambda *a: MoveOutcome.MISS)
    arr = _phase3_battle(make_pokemon, make_battle, ["Thrash"], ["Growl"])
    me = my_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert (me[Pok.RAMPAGE_TURNS], me[Pok.LOCKED_MOVE]) == (0, -1)


@pytest.mark.parametrize("outcome, keeps", [
    (MoveOutcome.MISS, True), (MoveOutcome.PROTECTED, True),
    (MoveOutcome.SEMI_INVULNERABLE, True), (MoveOutcome.INVULNERABLE, False),
])
def test_rampage_goes_on_through_a_miss(monkeypatch, make_pokemon, make_battle, outcome, keeps):
    """A miss, Protect or a hidden target keep it counting, an immune target ends it without
    confusion (pokeplatinum BattleContext_MoveFailed's noEffect)"""
    _always_hit(monkeypatch)
    monkeypatch.setattr(battle, "calculate_hit_miss", lambda *a: outcome)
    arr = _phase3_battle(make_pokemon, make_battle, ["Thrash"], ["Growl"])
    me = _rampaging(arr, 2)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.RAMPAGE_TURNS] == (1 if keeps else 0)
    assert me[Pok.LOCKED_MOVE] == (0 if keeps else -1)
    assert not me[Pok.VOL_STATUS] & VolStatus.CONFUSION


def test_full_paralysis_ends_the_rampage_without_confusion(monkeypatch, make_pokemon, make_battle):
    """A blocked turn on the last turn ends it with no confusion"""
    monkeypatch.setattr(engine_helper, "paralysis", lambda: True)
    arr = _phase3_battle(make_pokemon, make_battle, ["Thrash"], ["Growl"])
    me = _rampaging(arr, 1)
    me[Pok.STATUS] = Status.PARALYSIS
    turn_sim(0, (MOVE, 0), arr)
    assert (me[Pok.RAMPAGE_TURNS], me[Pok.LOCKED_MOVE]) == (0, -1)
    assert not me[Pok.VOL_STATUS] & VolStatus.CONFUSION


def test_truant_loafing_keeps_the_rampage(monkeypatch, make_pokemon, make_battle):
    """Loafing around doesn't end it, the counter still drops"""
    monkeypatch.setattr(engine_helper, "truant_loafs", lambda pok: True)
    arr = _phase3_battle(make_pokemon, make_battle, ["Thrash"], ["Growl"])
    me = _rampaging(arr, 2)
    turn_sim(0, (MOVE, 0), arr)
    assert (me[Pok.RAMPAGE_TURNS], me[Pok.LOCKED_MOVE]) == (1, 0)


@pytest.mark.parametrize("turns, confused", [(2, False), (1, True)])
def test_sleep_ends_the_rampage(make_pokemon, make_battle, turns, confused):
    """Asleep at the turn's end it loses the rampage without confusion, unless that was its last
    turn: the counter drops first (pokeplatinum SetupNextTurn after MON_COND_CHECK_STATE_THRASH)"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Thrash"], ["Growl"])
    me = _rampaging(arr, turns)
    me[Pok.STATUS] = Status.SLEEP
    me[Pok.SLEEP_COUNTER] = 4
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.STATUS] == Status.SLEEP
    assert (me[Pok.RAMPAGE_TURNS], me[Pok.LOCKED_MOVE]) == (0, -1)
    assert bool(me[Pok.VOL_STATUS] & VolStatus.CONFUSION) == confused


@pytest.mark.parametrize("ability, vol, side, confused", [
    ("Own Tempo", 0, 0, False),
    ("Run Away", 0, SideCondition.SAFEGUARD, True),
])
def test_rampage_end_confusion_blocks(make_pokemon, make_battle, ability, vol, side, confused):
    """Own Tempo stops the fatigue confusion, Safeguard doesn't (pokeplatinum subscript_confuse,
    SIDE_EFFECT_TYPE_MOVE_EFFECT)"""
    arr = make_battle([make_pokemon("Slowpoke", 30, ability, ["Thrash"])],
                      [make_pokemon("Rattata", 5, "Run Away", ["Growl"])])
    me = _rampaging(arr, 1)
    me[Pok.VOL_STATUS] = vol
    arr[MY_SIDE] = side
    battle._apply_residual(me, opp_active(arr), Field.MY_ENTER_FIELD, arr)
    assert (me[Pok.RAMPAGE_TURNS], me[Pok.LOCKED_MOVE]) == (0, -1)
    assert bool(me[Pok.VOL_STATUS] & VolStatus.CONFUSION) == confused


def test_rampage_end_keeps_an_existing_confusion(make_pokemon, make_battle):
    """Already confused: the counter isn't rerolled"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Thrash"], ["Growl"])
    me = _rampaging(arr, 1)
    me[Pok.VOL_STATUS] = VolStatus.CONFUSION
    me[Pok.CONFUSION_COUNTER] = 4
    battle._apply_residual(me, opp_active(arr), Field.MY_ENTER_FIELD, arr)
    assert me[Pok.CONFUSION_COUNTER] == 4 and me[Pok.LOCKED_MOVE] == -1


def test_switch_out_clears_the_rampage(poke):
    """A dragged-out thrasher comes back free"""
    p = poke("Rattata", 20, "Run Away", ["Thrash"])
    p[Pok.RAMPAGE_TURNS] = 2
    p[Pok.LOCKED_MOVE] = 0
    engine_helper.reset_switch_out(p)
    assert (p[Pok.RAMPAGE_TURNS], p[Pok.LOCKED_MOVE]) == (0, -1)


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


def test_metronome_into_thrash_keeps_thrashing(monkeypatch, make_pokemon, make_battle):
    """Thrash locks Metronome's slot, the next turn is Thrash again, then the confusion"""
    _force_metronome(monkeypatch, MoveName.THRASH)
    arr = make_battle([make_pokemon("Munchlax", 30, "Thick Fat", ["Metronome"])],
                      [make_pokemon("Geodude", 30, "Sturdy", ["Defense Curl"])])
    me = my_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.LOCKED_MOVE] == 0 and me[Pok.RAMPAGE_TURNS] == 1  # randint gives the low end
    _force_metronome(monkeypatch, MoveName.EMBER)
    hp = opp_active(arr)[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert opp_active(arr)[Pok.CURRENT_HP] < hp and arr[Field.LAST_MOVE] == MoveName.METRONOME
    assert me[Pok.CALLED_MOVE] == MoveName.THRASH
    assert me[Pok.LOCKED_MOVE] == -1 and me[Pok.VOL_STATUS] & VolStatus.CONFUSION


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


@pytest.mark.parametrize("move, foe_move, reached", [
    ("Fly", "Thunder", True), ("Fly", "Surf", False), ("Dive", "Surf", True),
    ("Dive", "Thunder", False), ("Shadow Force", "Surf", False),
])
def test_hidden_turn_and_what_reaches_it(monkeypatch, make_pokemon, make_battle, move, foe_move, reached):
    """Fly, Dive and Shadow Force hide on the charge turn, then attack and come back"""
    monkeypatch.setattr(engine_helper.random, "randint", lambda a, b: a)
    arr = make_battle([make_pokemon("Machop", 50, "Guts", [move])],
                      [make_pokemon("Geodude", 5, "Sturdy", [foe_move])])
    me, foe = my_active(arr), opp_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.VOL_STATUS] & VolStatus.SEMI_INVULNERABLE
    assert me[Pok.SEMI_INV_MOVE] == getattr(MoveName, move.upper().replace(" ", "_"))
    assert (me[Pok.CURRENT_HP] < me[Pok.MAX_HP]) == reached
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.SEMI_INV_MOVE] == 0 and not me[Pok.VOL_STATUS] & VolStatus.SEMI_INVULNERABLE
    assert foe[Pok.CURRENT_HP] < foe[Pok.MAX_HP]


@pytest.mark.parametrize("move, hits", [("Shadow Force", True), ("Bounce", False)])
def test_shadow_force_goes_through_protect(make_pokemon, make_battle, move, hits):
    """
    The faster foe protects on the attack turn: Shadow Force (no protect flag) still hits,
    Bounce is blocked
    """
    arr = make_battle([make_pokemon("Slowpoke", 50, "Oblivious", [move])],
                      [make_pokemon("Machop", 50, "Guts", ["Protect"])])
    foe = opp_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] == foe[Pok.MAX_HP]
    foe[Pok.PROTECT_COUNT] = 0
    turn_sim(0, (MOVE, 0), arr)
    assert (foe[Pok.CURRENT_HP] < foe[Pok.MAX_HP]) == hits


@pytest.mark.parametrize("weather", [Weather.SANDSTORM, Weather.HAIL])
def test_no_weather_damage_underwater(make_pokemon, make_battle, weather):
    """pokeplatinum MOVE_EFFECT_NO_WEATHER_DAMAGE covers Dive like Dig"""
    arr = make_battle([make_pokemon("Rattata", 50, "Run Away", ["Dive"])],
                      [make_pokemon("Geodude", 5, "Sturdy", ["Harden"])])
    arr[Field.WEATHER] = weather
    me = my_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.SEMI_INV_MOVE] == MoveName.DIVE
    assert me[Pok.CURRENT_HP] == me[Pok.MAX_HP]


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


# ── Trick Room, Tailwind ─────────────────────────────────────────────────────

def test_tailwind_lasts_three_turns_and_fails_while_up(make_pokemon, make_battle):
    """Tailwind counts the turn it was set in, a second one doesn't reset it (pokeplatinum
    subscript_tailwind_start, SIDE_CONDITION_TAILWIND)"""
    arr = make_battle([make_pokemon("Pidgey", 20, "Keen Eye", ["Tailwind"])],
                      [make_pokemon("Geodude", 20, "Sturdy", ["Harden"])])
    turn_sim(0, (MOVE, 0), arr)
    assert arr[Field.MY_SIDE_COND] & SideCondition.TAILWIND
    assert arr[Field.MY_TAILWIND_TURNS] == 2
    assert not arr[Field.OPP_SIDE_COND] & SideCondition.TAILWIND
    turn_sim(0, (MOVE, 0), arr)
    assert arr[Field.MY_TAILWIND_TURNS] == 1
    end_of_turn(arr)
    assert not arr[Field.MY_SIDE_COND] & SideCondition.TAILWIND
    assert arr[Field.MY_TAILWIND_TURNS] == 0


def test_trick_room_lasts_five_turns_and_a_second_one_ends_it(make_pokemon, make_battle):
    """pokeplatinum effect_script_0259: Trick Room used while up ends it"""
    arr = make_battle([make_pokemon("Abra", 20, "Synchronize", ["Trick Room"])],
                      [make_pokemon("Geodude", 20, "Sturdy", ["Harden"])])
    turn_sim(0, (MOVE, 0), arr)
    assert arr[Field.TRICKROOM] == 4
    turn_sim(0, (MOVE, 0), arr)
    assert arr[Field.TRICKROOM] == 0
    turn_sim(0, (MOVE, 0), arr)
    assert arr[Field.TRICKROOM] == 4
    for _ in range(4):
        end_of_turn(arr)
    assert arr[Field.TRICKROOM] == 0


@pytest.mark.parametrize("tailwind, trick_room, me_first", [
    (False, False, False),
    (True, False, True),     # 30 * 2 > 50
    (False, True, True),     # the slower first
    (True, True, False),     # 60 is faster now, so second
])
def test_tailwind_and_trick_room_set_the_turn_order(make_pokemon, make_battle, tailwind, trick_room,
                                                    me_first):
    """My Tackle KOs a 1 HP foe only if I move first, else its Tackle hits me"""
    arr = make_battle([make_pokemon("Geodude", 20, "Sturdy", ["Tackle"])],
                      [make_pokemon("Rattata", 20, "Run Away", ["Tackle"])])
    me, foe = my_active(arr), opp_active(arr)
    me[Pok.SPEED], foe[Pok.SPEED] = 30, 50
    foe[Pok.CURRENT_HP] = 1
    if tailwind:
        arr[Field.MY_SIDE_COND] |= SideCondition.TAILWIND
        arr[Field.MY_TAILWIND_TURNS] = 3
    arr[Field.TRICKROOM] = 5 if trick_room else 0
    turn_sim(0, (MOVE, 0), arr)
    assert (me[Pok.CURRENT_HP] == me[Pok.MAX_HP]) == me_first


def test_trick_room_flips_the_end_of_turn_order(monkeypatch, make_pokemon, make_battle):
    """The end of turn sorts by speed through the same compare, so Trick Room flips it"""
    arr = make_battle([make_pokemon("Geodude", 20, "Sturdy", ["Harden"])],
                      [make_pokemon("Rattata", 20, "Run Away", ["Harden"])])
    me, foe = my_active(arr), opp_active(arr)
    me[Pok.SPEED], foe[Pok.SPEED] = 30, 50
    order = []
    real = battle._residual_weather

    def spy(pok, weather, flag, battle_array):
        order.append(flag)
        return real(pok, weather, flag, battle_array)

    monkeypatch.setattr(battle, "_residual_weather", spy)
    end_of_turn(arr)
    arr[Field.TRICKROOM] = 5
    end_of_turn(arr)
    assert order == [
        Field.OPP_ENTER_FIELD, Field.MY_ENTER_FIELD, Field.MY_ENTER_FIELD, Field.OPP_ENTER_FIELD
    ]


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


def test_magma_storm_traps_like_wrap(monkeypatch, make_pokemon, make_battle):
    """pokeplatinum BATTLE_EFFECT_BIND_HIT: the hit, then 1/16 at the end of the turn"""
    _always_hit(monkeypatch)
    my = [make_pokemon("Rattata", 5, "Run Away", ["Magma Storm"])]
    arr = make_battle(my, [make_pokemon("Geodude", 50, "Sturdy", ["Growl"])])
    foe = opp_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.VOL_STATUS] & VolStatus.PARTIALLY_TRAPPED
    assert 2 <= foe[Pok.TRAP_TURNS] <= 5
    assert foe[Pok.CURRENT_HP] < foe[Pok.MAX_HP] - foe[Pok.MAX_HP] // 16


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


@pytest.mark.parametrize("move, stage", [
    ("Swagger", Pok.ATTACK_STAT_STAGE), ("Flatter", Pok.SPECIAL_ATTACK_STAT_STAGE),
])
@pytest.mark.parametrize("confused", [True, False])
def test_swagger_fails_at_plus_6_on_a_confused_target(monkeypatch, make_pokemon, make_battle, move,
                                                       stage, confused):
    """At +6 on a target already confused the move fails and gives back its Metronome count; at +6
    alone it still confuses (pokeplatinum subscript_swagger, subscript_flatter)"""
    monkeypatch.setattr(battle, "calculate_hit_miss", lambda *a: MoveOutcome.HIT)
    arr = make_battle(
        [make_pokemon("Rattata", 50, "Run Away", [move], item="Metronome")],
        [make_pokemon("Munchlax", 50, "Thick Fat", ["Harden"])],
    )
    me, foe = my_active(arr), opp_active(arr)
    foe[stage] = 6
    if confused:
        foe[Pok.VOL_STATUS] |= VolStatus.CONFUSION
        foe[Pok.CONFUSION_COUNTER] = 5
    move_id = getattr(MoveName, move.upper())
    me[Pok.METRONOME_COUNT] = (move_id << 4) + 2
    turn_sim(0, (MOVE, 0), arr)
    assert foe[stage] == 6
    assert foe[Pok.VOL_STATUS] & VolStatus.CONFUSION
    assert me[Pok.METRONOME_COUNT] == (move_id << 4) + (2 if confused else 3)


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
    battle.random.seed(5)
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


# ── 4.5: Thief, Pluck, Trick, Switcheroo, Embargo, Fling ─────────────────────

def test_thief_steals_like_covet(make_pokemon, make_battle):
    """Thief is Covet's move ([pp] BATTLE_EFFECT_STEAL_HELD_ITEM)"""
    arr = make_battle([make_pokemon("Murkrow", 20, "Insomnia", ["Thief"])],
                      [make_pokemon("Rattata", 20, "Run Away", ["Leer"], item="Leftovers")])
    me, foe = my_active(arr), opp_active(arr)
    battle.ps_moves(me, foe, move_slice(me, 0), 0, False, False)
    assert me[Item.ID] == ItemNames.LEFTOVERS and foe[Item.ID] == 0


def test_the_ais_thief_steals_too(make_pokemon, make_battle):
    """The AI's steal works in RP, like its Covet"""
    arr = make_battle([make_pokemon("Rattata", 20, "Run Away", ["Leer"], item="Leftovers")],
                      [make_pokemon("Murkrow", 20, "Insomnia", ["Thief"])])
    turn_sim(0, (MOVE, 0), arr)
    assert opp_active(arr)[Item.ID] == ItemNames.LEFTOVERS and my_active(arr)[Item.ID] == 0


def test_thief_keeps_the_users_own_item(make_pokemon, make_battle):
    """A user holding an item steals nothing"""
    arr = make_battle([make_pokemon("Murkrow", 20, "Insomnia", ["Thief"], item="Everstone")],
                      [make_pokemon("Rattata", 20, "Run Away", ["Leer"], item="Leftovers")])
    me, foe = my_active(arr), opp_active(arr)
    battle.ps_moves(me, foe, move_slice(me, 0), 0, False, False)
    assert me[Item.ID] == ItemNames.EVERSTONE and foe[Item.ID] == ItemNames.LEFTOVERS


def _pluck_battle(make_pokemon, make_battle, ability="Rock Head"):
    """A weak Pluck into a sturdy Sitrus holder, so the holder never eats it first"""
    arr = make_battle([make_pokemon("Starly", 10, "Keen Eye", ["Pluck"])],
                      [make_pokemon("Geodude", 50, ability, ["Defense Curl"], item="Sitrus Berry")])
    me = my_active(arr)
    me[Pok.CURRENT_HP] = 1
    return me, opp_active(arr)


def test_pluck_eats_the_targets_berry(make_pokemon, make_battle):
    """Pluck is Bug Bite's move ([pp] BATTLE_EFFECT_EAT_BERRY)"""
    me, foe = _pluck_battle(make_pokemon, make_battle)
    battle.ps_moves(me, foe, move_slice(me, 0), 0, False, False)
    assert me[Pok.CURRENT_HP] == 1 + me[Pok.MAX_HP] // 4 and foe[Item.ID] == 0


@pytest.mark.parametrize("ability, kept", [("Sticky Hold", True), ("Rock Head", False)])
def test_sticky_hold_keeps_the_berry_from_pluck(make_pokemon, make_battle, ability, kept):
    """pokeplatinum BtlCmd_TryPluck"""
    me, foe = _pluck_battle(make_pokemon, make_battle, ability)
    battle.ps_moves(me, foe, move_slice(me, 0), 0, False, False)
    assert (foe[Item.ID] != 0) == kept


def test_pluck_eats_an_embargoed_targets_berry(make_pokemon, make_battle):
    """Embargo stops the holder's item, not the plucker eating it (pokeplatinum PluckBerry reads the
    raw item)"""
    me, foe = _pluck_battle(make_pokemon, make_battle)
    assert engine_helper.embargo(foe)
    battle.ps_moves(me, foe, move_slice(me, 0), 0, False, False)
    assert me[Pok.CURRENT_HP] == 1 + me[Pok.MAX_HP] // 4 and foe[Item.ID] == 0


def test_an_embargoed_plucker_only_takes_the_berry(make_pokemon, make_battle):
    """pokeplatinum PluckBerry: no script for an Embargoed attacker, the berry still goes"""
    me, foe = _pluck_battle(make_pokemon, make_battle)
    assert engine_helper.embargo(me)
    battle.ps_moves(me, foe, move_slice(me, 0), 0, False, False)
    assert me[Pok.CURRENT_HP] == 1 and foe[Item.ID] == 0


def _trick_battle(make_pokemon, make_battle, my_item, opp_item, move="Trick",
                  my_ability="Synchronize", opp_ability="Run Away", my_moves=None):
    return make_battle(
        [make_pokemon("Abra", 20, my_ability, my_moves or [move], item=my_item)],
        [make_pokemon("Rattata", 20, opp_ability, ["Growl"], item=opp_item)])


def _item_id(name):
    return getattr(ItemNames, name.upper().replace(" ", "_")) if name else 0


@pytest.mark.parametrize("move", ["Trick", "Switcheroo"])
@pytest.mark.parametrize("my_item, opp_item", [
    ("Leftovers", "Everstone"), ("Everstone", ""), ("", "Everstone"),
])
def test_trick_swaps_the_items(make_pokemon, make_battle, move, my_item, opp_item):
    """Either side may hold nothing"""
    arr = _trick_battle(make_pokemon, make_battle, my_item, opp_item, move)
    turn_sim(0, (MOVE, 0), arr)
    assert my_active(arr)[Item.ID] == _item_id(opp_item)
    assert opp_active(arr)[Item.ID] == _item_id(my_item)


@pytest.mark.parametrize("my_item, opp_item, opp_ability, knocked", [
    ("", "", "Run Away", None),
    ("Everstone", "Leftovers", "Sticky Hold", None),
    ("Everstone", "", "Sticky Hold", None),
    ("Griseous Orb", "Leftovers", "Run Away", None),
    ("Everstone", "Griseous Orb", "Run Away", None),
    ("Everstone", "Leftovers", "Run Away", "mine"),
    ("Everstone", "Leftovers", "Run Away", "foe"),
])
def test_trick_fails(make_pokemon, make_battle, my_item, opp_item, opp_ability, knocked):
    """Nothing to swap, Sticky Hold (even holding nothing), a Griseous Orb or a knocked-off item on
    either side (pokeplatinum subscript_exchange_items, BtlCmd_TrySwapItems)"""
    arr = _trick_battle(make_pokemon, make_battle, my_item, opp_item, opp_ability=opp_ability)
    me, foe = my_active(arr), opp_active(arr)
    if knocked == "mine":
        me[Pok.ITEM_KNOCKED_OFF] = 1
    elif knocked == "foe":
        foe[Pok.ITEM_KNOCKED_OFF] = 1
    assert not engine_helper.swap_items(me, foe)
    assert (me[Item.ID], foe[Item.ID]) == (_item_id(my_item), _item_id(opp_item))


def test_sticky_hold_stopping_trick_reveals_it(make_pokemon, make_battle):
    """The fail message names the ability; Mold Breaker gets through"""
    arr = _trick_battle(make_pokemon, make_battle, "Everstone", "Leftovers", opp_ability="Sticky Hold")
    me, foe = my_active(arr), opp_active(arr)
    assert not engine_helper.swap_items(me, foe)
    assert foe[Pok.AB_KNOWN] == 1
    arr = _trick_battle(make_pokemon, make_battle, "Everstone", "Leftovers",
                        my_ability="Mold Breaker", opp_ability="Sticky Hold")
    assert engine_helper.swap_items(my_active(arr), opp_active(arr))


def test_trick_fails_into_a_substitute(make_pokemon, make_battle):
    """pokeplatinum CheckSubstitute in subscript_exchange_items"""
    arr = _trick_battle(make_pokemon, make_battle, "Everstone", "Leftovers")
    foe = opp_active(arr)
    foe[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
    foe[Pok.SUB_HP] = 10
    turn_sim(0, (MOVE, 0), arr)
    assert my_active(arr)[Item.ID] == ItemNames.EVERSTONE and foe[Item.ID] == ItemNames.LEFTOVERS


def test_the_ais_trick_swaps_too(make_pokemon, make_battle):
    """RP's AI swaps like its Covet steals"""
    arr = make_battle([make_pokemon("Rattata", 20, "Run Away", ["Growl"], item="Leftovers")],
                      [make_pokemon("Abra", 20, "Synchronize", ["Trick"])])
    turn_sim(0, (MOVE, 0), arr)
    assert opp_active(arr)[Item.ID] == ItemNames.LEFTOVERS and my_active(arr)[Item.ID] == 0


def test_tricking_a_choice_item_onto_yourself_locks_into_trick(make_pokemon, make_battle):
    """The item is read after the move (pokeplatinum UpdateMoveBuffers)"""
    arr = _trick_battle(make_pokemon, make_battle, "", "Choice Band", my_moves=["Trick", "Tackle"])
    turn_sim(0, (MOVE, 0), arr)
    me = my_active(arr)
    assert me[Item.ID] == ItemNames.CHOICE_BAND and me[Pok.CHOICE_LOCK] == 1


def test_losing_the_choice_item_to_a_move_ends_the_targets_lock(make_pokemon, make_battle):
    """pokeplatinum UpdateMoveBuffers clears the defender's lock when it holds no choice item, so a
    Choice Band Tricked back later doesn't bring the old lock back"""
    arr = make_battle([make_pokemon("Murkrow", 30, "Insomnia", ["Knock Off"])],
                      [make_pokemon("Rattata", 20, "Run Away", ["Tackle", "Growl"],
                                    item="Choice Band")])
    foe = opp_active(arr)
    foe[Pok.CHOICE_LOCK] = 2
    turn_sim(1, (MOVE, 0), arr)
    assert foe[Item.ID] == 0 and foe[Pok.CHOICE_LOCK] == 0


def test_the_targets_lock_stays_while_it_keeps_its_choice_item(make_pokemon, make_battle):
    """Only a target without a choice item loses its lock"""
    arr = make_battle([make_pokemon("Murkrow", 30, "Insomnia", ["Peck"])],
                      [make_pokemon("Rattata", 20, "Run Away", ["Tackle", "Growl"],
                                    item="Choice Band")])
    foe = opp_active(arr)
    foe[Pok.CHOICE_LOCK] = 2
    turn_sim(1, (MOVE, 0), arr)
    assert foe[Pok.CHOICE_LOCK] == 2


def _embargo_battle(make_pokemon, make_battle, my_item="Leftovers", my_ability="Run Away"):
    """My Rattata against the foe's Embargo"""
    arr = make_battle([make_pokemon("Rattata", 20, my_ability, ["Growl"], item=my_item),
                       make_pokemon("Geodude", 20, "Sturdy", ["Tackle"], item="Leftovers")],
                      [make_pokemon("Murkrow", 20, "Insomnia", ["Embargo"])])
    return arr, my_active(arr)


def test_embargo_stops_the_held_item(make_pokemon, make_battle):
    """The item stays but does nothing: no Leftovers heal at the end of the turn"""
    arr, me = _embargo_battle(make_pokemon, make_battle)
    me[Pok.CURRENT_HP] -= 20
    hp = me[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.VOL_STATUS2] & VolStatus2.EMBARGO
    assert me[Item.ID] == ItemNames.LEFTOVERS and me[Item.HOLD_EFFECT] == 0
    assert me[Pok.CURRENT_HP] == hp and me[Pok.EMBARGO_TURNS] == 4


def test_embargo_lasts_five_turns(make_pokemon, make_battle):
    """Set to 5, counted down at every end of turn, the turn it lands included (pokeplatinum
    subscript_embargo_start, MON_COND_CHECK_STATE_EMBARGO); the item works again after"""
    _, me = _embargo_battle(make_pokemon, make_battle)
    assert engine_helper.embargo(me)
    for _ in range(4):
        engine_helper.embargo_count(me)
    assert me[Pok.VOL_STATUS2] & VolStatus2.EMBARGO and me[Pok.EMBARGO_TURNS] == 1
    engine_helper.embargo_count(me)
    assert not me[Pok.VOL_STATUS2] & VolStatus2.EMBARGO and me[Pok.EMBARGO_TURNS] == 0
    assert me[Item.HOLD_EFFECT] != 0


@pytest.mark.parametrize("item, ability", [("Griseous Orb", "Run Away"), ("Leftovers", "Multitype")])
def test_embargo_fails(make_pokemon, make_battle, item, ability):
    """A Griseous Orb holder or Multitype (pokeplatinum subscript_embargo_start)"""
    _, me = _embargo_battle(make_pokemon, make_battle, item, ability)
    assert not engine_helper.embargo(me)
    assert not me[Pok.VOL_STATUS2] & VolStatus2.EMBARGO


def test_embargo_fails_while_up(make_pokemon, make_battle):
    """A second Embargo doesn't restart the count"""
    _, me = _embargo_battle(make_pokemon, make_battle)
    assert engine_helper.embargo(me)
    engine_helper.embargo_count(me)
    assert not engine_helper.embargo(me)
    assert me[Pok.EMBARGO_TURNS] == 4


def test_embargo_on_a_pokemon_holding_nothing(make_pokemon, make_battle):
    """No item doesn't make it fail"""
    _, me = _embargo_battle(make_pokemon, make_battle, my_item="")
    assert engine_helper.embargo(me)


def test_embargo_fails_into_a_substitute(make_pokemon, make_battle):
    """pokeplatinum CheckSubstitute"""
    arr, me = _embargo_battle(make_pokemon, make_battle)
    me[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
    me[Pok.SUB_HP] = 10
    turn_sim(0, (MOVE, 0), arr)
    assert not me[Pok.VOL_STATUS2] & VolStatus2.EMBARGO


def test_embargo_ends_on_switch_out(make_pokemon, make_battle):
    """The item works again on the bench"""
    _, me = _embargo_battle(make_pokemon, make_battle)
    engine_helper.embargo(me)
    engine_helper.reset_switch_out(me)
    assert not me[Pok.VOL_STATUS2] & VolStatus2.EMBARGO and me[Pok.EMBARGO_TURNS] == 0
    assert me[Item.HOLD_EFFECT] != 0


def test_baton_pass_passes_embargo(make_pokemon, make_battle):
    """With its turns, over the new Pokemon's item (pokeplatinum embargoTurns)"""
    arr, me = _embargo_battle(make_pokemon, make_battle)
    engine_helper.embargo(me)
    engine_helper.embargo_count(me)
    new = pok_slice(arr, 1)
    battle._pass_baton(me, new)
    assert new[Pok.VOL_STATUS2] & VolStatus2.EMBARGO and new[Pok.EMBARGO_TURNS] == 4
    assert new[Item.ID] == ItemNames.LEFTOVERS and new[Item.HOLD_EFFECT] == 0


def test_an_embargoed_pokemon_gets_a_suppressed_item_from_trick(make_pokemon, make_battle):
    """The swap rebuilds both blocks: the Embargoed side's new item does nothing, the other's works"""
    arr = _trick_battle(make_pokemon, make_battle, "Choice Scarf", "Leftovers")
    me, foe = my_active(arr), opp_active(arr)
    engine_helper.embargo(me)
    assert engine_helper.swap_items(me, foe)
    assert me[Item.ID] == ItemNames.LEFTOVERS and me[Item.HOLD_EFFECT] == 0
    assert foe[Item.ID] == ItemNames.CHOICE_SCARF and foe[Item.HOLD_EFFECT] != 0


@pytest.mark.parametrize("item, halved", [("Iron Ball", True), ("Choice Scarf", False)])
def test_embargo_and_speed_items(make_pokemon, make_battle, item, halved):
    """The speed-halving items still work, the rest doesn't (pokeplatinum reads the raw item for
    sSpeedHalvingItemEffects)"""
    _, me = _embargo_battle(make_pokemon, make_battle, my_item=item)
    engine_helper.embargo(me)
    speed = me[Pok.SPEED]
    assert check_speed(me, me, 0)[0] == (speed // 2 if halved else speed)


def test_natural_gift_fails_under_embargo(make_pokemon, make_battle):
    """pokeplatinum Battler_NaturalGiftPower reads Battler_HeldItem: the berry stays"""
    arr = make_battle([make_pokemon("Rattata", 20, "Run Away", ["Natural Gift"], item="Oran Berry")],
                      [make_pokemon("Geodude", 20, "Sturdy", ["Defense Curl"])])
    me, foe = my_active(arr), opp_active(arr)
    engine_helper.embargo(me)
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] == foe[Pok.MAX_HP] and me[Item.ID] == ItemNames.ORAN_BERRY


def test_no_trainer_items_on_an_embargoed_pokemon(make_pokemon, make_battle):
    """pokeplatinum TrainerAI_ShouldUseItem returns early under Embargo"""
    arr = make_battle([make_pokemon("Rattata", 20, "Run Away", ["Growl"])],
                      [make_pokemon("Geodude", 20, "Sturdy", ["Tackle"])],
                      trainer_items=(Potions.FULL_RESTORE,))
    foe = opp_active(arr)
    foe[Pok.CURRENT_HP] = 1
    assert return_idx(arr) < 0
    engine_helper.embargo(foe)
    assert return_idx(arr) >= 0


def _fling_battle(make_pokemon, make_battle, item, opp="Rattata", opp_level=20):
    arr = make_battle([make_pokemon("Machop", 20, "Guts", ["Fling"], item=item)],
                      [make_pokemon(opp, opp_level, "Run Away", ["Growl"])])
    return arr, my_active(arr), opp_active(arr)


def _fling(me, foe):
    """One Fling hit, as _execute_move_slot sets it up"""
    return battle.ps_moves(
        me, foe, engine_helper.fling_move(me, foe, move_slice(me, 0)), 0, False, False
    )


@pytest.mark.parametrize("item, power", [("Iron Ball", 130), ("Everstone", 30), ("Oran Berry", 10)])
def test_fling_power_comes_from_the_item(make_pokemon, make_battle, item, power):
    """The item's Fling power (ItemDB, [pp] ITEM_PARAM_FLING_POWER)"""
    _, me, foe = _fling_battle(make_pokemon, make_battle, item)
    assert engine_helper.fling_move(me, foe, move_slice(me, 0))[Move.POWER] == power


def test_fling_throws_the_item(make_pokemon, make_battle):
    """Gone after the hit, Recycle can bring it back"""
    arr, me, foe = _fling_battle(make_pokemon, make_battle, "Iron Ball")
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] < foe[Pok.MAX_HP]
    assert me[Item.ID] == 0 and me[Pok.CONSUMED_ITEM] == ItemNames.IRON_BALL


def test_fling_throws_the_item_on_a_miss(monkeypatch, make_pokemon, make_battle):
    """[pp] removes it before the hit check, Showdown's fling volatile too"""
    arr, me, foe = _fling_battle(make_pokemon, make_battle, "Iron Ball")
    monkeypatch.setattr(battle, "calculate_hit_miss", lambda *a: MoveOutcome.MISS)
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] == foe[Pok.MAX_HP] and me[Item.ID] == 0


@pytest.mark.parametrize("item, ability", [
    ("", "Guts"), ("Griseous Orb", "Guts"), ("Iron Ball", "Multitype"),
])
def test_fling_fails(make_pokemon, make_battle, item, ability):
    """Nothing to throw, a Griseous Orb or Multitype: no hit, the item stays, the PP is spent"""
    arr = make_battle([make_pokemon("Machop", 20, ability, ["Fling"], item=item)],
                      [make_pokemon("Rattata", 20, "Run Away", ["Growl"])])
    me, foe = my_active(arr), opp_active(arr)
    pp = move_slice(me, 0)[Move.PP]
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] == foe[Pok.MAX_HP]
    assert move_slice(me, 0)[Move.PP] == pp - 1 and me[Item.ID] == _item_id(item)


def test_fling_fails_under_embargo(make_pokemon, make_battle):
    """pokeplatinum Battler_ItemFlingPower is 0 under Embargo"""
    arr, me, foe = _fling_battle(make_pokemon, make_battle, "Iron Ball")
    engine_helper.embargo(me)
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] == foe[Pok.MAX_HP] and me[Item.ID] == ItemNames.IRON_BALL


@pytest.mark.parametrize("item, status", [
    ("Flame Orb", Status.BURN), ("Toxic Orb", Status.TOXIC), ("Poison Barb", Status.POISON),
    ("Light Ball", Status.PARALYSIS),
])
def test_fling_gives_the_items_status(make_pokemon, make_battle, item, status):
    """A sure secondary effect (Showdown fling, the item's fling.status)"""
    _, me, foe = _fling_battle(make_pokemon, make_battle, item, opp_level=40)
    _fling(me, foe)
    assert foe[Pok.STATUS] == status


def test_fling_status_respects_immunities(make_pokemon, make_battle):
    """It goes through the normal status checks: a Fire type isn't burned"""
    _, me, foe = _fling_battle(make_pokemon, make_battle, "Flame Orb", opp="Ponyta", opp_level=40)
    _fling(me, foe)
    assert foe[Pok.STATUS] == 0


def test_fling_has_no_effect_on_an_embargoed_target(make_pokemon, make_battle):
    """pokeplatinum BattleSystem_FlingItem drops the fling script, the status ones included"""
    _, me, foe = _fling_battle(make_pokemon, make_battle, "Flame Orb", opp_level=40)
    engine_helper.embargo(foe)
    _fling(me, foe)
    assert foe[Pok.STATUS] == 0 and foe[Pok.CURRENT_HP] < foe[Pok.MAX_HP]


@pytest.mark.parametrize("item", ["King's Rock", "Razor Fang"])
def test_fling_flinches(make_pokemon, make_battle, item):
    """A sure flinch (Showdown fling.volatileStatus)"""
    _, me, foe = _fling_battle(make_pokemon, make_battle, item, opp_level=40)
    flinch, _, _ = _fling(me, foe)
    assert flinch


def test_a_flung_sitrus_heals_the_target(make_pokemon, make_battle):
    """The target eats it after the hit (Showdown fling onHit)"""
    _, me, foe = _fling_battle(make_pokemon, make_battle, "Sitrus Berry", opp="Geodude", opp_level=50)
    foe[Pok.CURRENT_HP] = foe[Pok.MAX_HP] // 2
    hp = foe[Pok.CURRENT_HP]
    _, _, dealt = _fling(me, foe)
    assert foe[Pok.CURRENT_HP] == min(foe[Pok.MAX_HP], hp - dealt + foe[Pok.MAX_HP] // 4)
    assert me[Item.ID] == 0


def test_a_flung_persim_cures_confusion(make_pokemon, make_battle):
    """No Bug Bite quirk: Fling's Persim cures ([pp] FLING_EFFECT_CNF_RESTORE)"""
    _, me, foe = _fling_battle(make_pokemon, make_battle, "Persim Berry", opp="Geodude", opp_level=50)
    foe[Pok.VOL_STATUS] |= VolStatus.CONFUSION
    _fling(me, foe)
    assert not foe[Pok.VOL_STATUS] & VolStatus.CONFUSION and foe[Pok.ATTACK_STAT_STAGE] == 0


def test_flung_herbs(make_pokemon, make_battle):
    """White Herb restores the target's lowered stats, Mental Herb cures its infatuation"""
    _, me, foe = _fling_battle(make_pokemon, make_battle, "White Herb", opp="Geodude", opp_level=50)
    foe[Pok.DEFENSE_STAT_STAGE] = -2
    _fling(me, foe)
    assert foe[Pok.DEFENSE_STAT_STAGE] == 0
    _, me, foe = _fling_battle(make_pokemon, make_battle, "Mental Herb", opp="Geodude", opp_level=50)
    foe[Pok.VOL_STATUS] |= VolStatus.ATTRACT
    _fling(me, foe)
    assert not foe[Pok.VOL_STATUS] & VolStatus.ATTRACT


def test_fling_into_a_substitute(make_pokemon, make_battle):
    """The item is lost, its effect doesn't reach the target"""
    _, me, foe = _fling_battle(make_pokemon, make_battle, "Flame Orb", opp_level=40)
    foe[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
    foe[Pok.SUB_HP] = 200
    _fling(me, foe)
    assert foe[Pok.STATUS] == 0 and me[Item.ID] == 0


def test_a_flung_life_orb_gives_no_recoil(make_pokemon, make_battle):
    """Still held for the damage, gone before the recoil (pokeplatinum CalcDamage before RemoveItem)"""
    arr, me, foe = _fling_battle(make_pokemon, make_battle, "Life Orb", opp="Geodude", opp_level=50)
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] < foe[Pok.MAX_HP]
    assert me[Pok.CURRENT_HP] == me[Pok.MAX_HP] and me[Pok.CONSUMED_ITEM] == ItemNames.LIFE_ORB


SELF_DROPS = [
    ("Close Combat", {Pok.DEFENSE_STAT_STAGE: -1, Pok.SPECIAL_DEFENSE_STAT_STAGE: -1}),
    ("Superpower", {Pok.ATTACK_STAT_STAGE: -1, Pok.DEFENSE_STAT_STAGE: -1}),
    ("Hammer Arm", {Pok.SPEED_STAT_STAGE: -1}),
    ("Overheat", {Pok.SPECIAL_ATTACK_STAT_STAGE: -2}),
    ("Draco Meteor", {Pok.SPECIAL_ATTACK_STAT_STAGE: -2}),
    ("Leaf Storm", {Pok.SPECIAL_ATTACK_STAT_STAGE: -2}),
    ("Psycho Boost", {Pok.SPECIAL_ATTACK_STAT_STAGE: -2}),
]
STAGES = (
    Pok.ATTACK_STAT_STAGE, Pok.DEFENSE_STAT_STAGE, Pok.SPECIAL_ATTACK_STAT_STAGE,
    Pok.SPECIAL_DEFENSE_STAT_STAGE, Pok.SPEED_STAT_STAGE,
)


@pytest.mark.parametrize("move, drops", SELF_DROPS)
@pytest.mark.parametrize("case", ["hit", "ko", "substitute"])
def test_self_drop_moves_lower_the_user_on_any_hit(poke, move, drops, case):
    """pokeplatinum MOVE_SIDE_EFFECT_TO_ATTACKER: no roll, on a KO and into a Substitute too. The
    target having Clear Body changes nothing"""
    a = poke("Machop", 50, "Guts", [move])
    d = poke("Metang", 100, "Clear Body", ["Tackle"])
    if case == "ko":
        d[Pok.CURRENT_HP] = 1
    if case == "substitute":
        d[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
        d[Pok.SUB_HP] = 1
    battle.ps_moves(a, d, move_slice(a, 0), 0, False, False)
    assert (d[Pok.CURRENT_HP] <= 0) == (case == "ko")
    assert {s: a[s] for s in STAGES} == {s: drops.get(s, 0) for s in STAGES}
    assert all(d[s] == 0 for s in STAGES)


def test_self_drop_move_keeps_the_stats_on_a_miss(monkeypatch, make_pokemon, make_battle):
    """The drop is part of the hit"""
    monkeypatch.setattr(battle, "calculate_hit_miss", lambda *a: MoveOutcome.MISS)
    arr = make_battle([make_pokemon("Machop", 50, "Guts", ["Close Combat"])],
                      [make_pokemon("Onix", 50, "Sturdy", ["Harden"])])
    me = my_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert (me[Pok.DEFENSE_STAT_STAGE], me[Pok.SPECIAL_DEFENSE_STAT_STAGE]) == (0, 0)


# ── Phase 6.5: crash damage ─────────────────────────────────────────────────────

def _crash_battle(make_pokemon, make_battle, move="Jump Kick", ability="Limber",
                  foe="Rattata", foe_ability="Run Away"):
    """Hitmonlee with a crash move vs a foe that only uses Growl"""
    return make_battle([make_pokemon("Hitmonlee", 50, ability, [move])],
                       [make_pokemon(foe, 50, foe_ability, ["Growl"])])


def _crash_lost(monkeypatch, make_pokemon, make_battle, outcome, damage, **kwargs):
    """HP my Hitmonlee lost to its own move, with the hit check and damage fixed"""
    monkeypatch.setattr(battle, "calculate_hit_miss", lambda *a: outcome)
    monkeypatch.setattr(battle, "calculate_crit", lambda *a: False)
    monkeypatch.setattr(battle, "calculate_damage", lambda *a: damage)
    arr = _crash_battle(make_pokemon, make_battle, **kwargs)
    me = my_active(arr)
    hp = me[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    return hp - me[Pok.CURRENT_HP], arr


@pytest.mark.parametrize("move", ["Jump Kick", "High Jump Kick"])
@pytest.mark.parametrize("outcome", [
    MoveOutcome.MISS, MoveOutcome.PROTECTED, MoveOutcome.SEMI_INVULNERABLE,
    MoveOutcome.INVULNERABLE,
])
def test_crash_costs_half_the_damage(monkeypatch, make_pokemon, make_battle, move, outcome):
    """Any outcome that didn't hit costs half the damage the move would have dealt (pokeplatinum
    subscript_missed calls subscript_crash_on_miss)"""
    lost, _ = _crash_lost(monkeypatch, make_pokemon, make_battle, outcome, 41, move=move)
    assert lost == 20


def test_crash_is_capped_at_half_the_targets_max_hp(monkeypatch, make_pokemon, make_battle):
    """subscript_crash_on_miss caps it at the defender's max HP / 2"""
    lost, arr = _crash_lost(monkeypatch, make_pokemon, make_battle, MoveOutcome.MISS, 10_000)
    assert lost == opp_active(arr)[Pok.MAX_HP] // 2


def test_magic_guard_skips_the_crash(monkeypatch, make_pokemon, make_battle):
    lost, _ = _crash_lost(monkeypatch, make_pokemon, make_battle, MoveOutcome.MISS, 40,
                          ability="Magic Guard")
    assert lost == 0


def test_no_crash_on_a_hit(monkeypatch, make_pokemon, make_battle):
    lost, arr = _crash_lost(monkeypatch, make_pokemon, make_battle, MoveOutcome.HIT, 40)
    foe = opp_active(arr)
    assert lost == 0 and foe[Pok.MAX_HP] - foe[Pok.CURRENT_HP] == 40


def test_no_crash_into_a_ghost(make_pokemon, make_battle):
    """The type chart already made the stored damage 0, so the crash is 0 (pokeplatinum
    ApplyTypeChart runs on it in TryMove)"""
    arr = _crash_battle(make_pokemon, make_battle, foe="Gastly", foe_ability="Levitate")
    me = my_active(arr)
    hp = me[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.CURRENT_HP] == hp


def test_wonder_guard_still_costs_the_crash(make_pokemon, make_battle):
    """Wonder Guard leaves the stored damage as it is, so the crash goes through"""
    random.seed(3)
    arr = _crash_battle(make_pokemon, make_battle, foe="Zubat", foe_ability="Wonder Guard")
    me, foe = my_active(arr), opp_active(arr)
    hp = me[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] == foe[Pok.MAX_HP]
    assert 0 < hp - me[Pok.CURRENT_HP] <= foe[Pok.MAX_HP] // 2


def test_crash_can_knock_the_user_out(monkeypatch, make_pokemon, make_battle):
    monkeypatch.setattr(battle, "calculate_hit_miss", lambda *a: MoveOutcome.MISS)
    monkeypatch.setattr(battle, "calculate_damage", lambda *a: 10_000)
    arr = _crash_battle(make_pokemon, make_battle)
    me = my_active(arr)
    me[Pok.CURRENT_HP] = 1
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.CURRENT_HP] == 0


# ── Phase 7.1: variable power ────────────────────────────────────────────────

@pytest.mark.parametrize("move, status", [
    ("Smelling Salts", Status.PARALYSIS), ("Wake-Up Slap", Status.SLEEP),
])
def test_status_cure_on_hit(monkeypatch, poke, move, status):
    """The target that survives is cured (pokeplatinum subscript_heal_target_*)"""
    monkeypatch.setattr(battle, "calculate_damage", lambda *a: 10)
    a = poke("Hariyama", 50, "Thick Fat", [move])
    d = poke("Snorlax", 50, "Thick Fat", ["Tackle"])
    d[Pok.STATUS] = status
    d[Pok.SLEEP_COUNTER] = 3 if status == Status.SLEEP else 0
    battle.ps_moves(a, d, move_slice(a, 0), 0, False, False)
    assert d[Pok.STATUS] == 0 and d[Pok.SLEEP_COUNTER] == 0


@pytest.mark.parametrize("move, status", [
    ("Smelling Salts", Status.SLEEP), ("Wake-Up Slap", Status.PARALYSIS),
])
def test_status_cure_only_its_own_status(monkeypatch, poke, move, status):
    monkeypatch.setattr(battle, "calculate_damage", lambda *a: 10)
    a = poke("Hariyama", 50, "Thick Fat", [move])
    d = poke("Snorlax", 50, "Thick Fat", ["Tackle"])
    d[Pok.STATUS] = status
    battle.ps_moves(a, d, move_slice(a, 0), 0, False, False)
    assert d[Pok.STATUS] == status


def test_status_cure_not_on_a_ko_or_a_substitute(monkeypatch, poke):
    """A fainted target isn't cured, nor one whose Substitute took the hit"""
    monkeypatch.setattr(battle, "calculate_damage", lambda *a: 10_000)
    a = poke("Hariyama", 50, "Thick Fat", ["Wake-Up Slap"])
    d = poke("Snorlax", 50, "Thick Fat", ["Tackle"])
    d[Pok.STATUS] = Status.SLEEP
    battle.ps_moves(a, d, move_slice(a, 0), 0, False, False)
    assert d[Pok.CURRENT_HP] == 0 and d[Pok.STATUS] == Status.SLEEP
    monkeypatch.setattr(battle, "calculate_damage", lambda *a: 10)
    d = poke("Snorlax", 50, "Thick Fat", ["Tackle"])
    d[Pok.STATUS] = Status.SLEEP
    d[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
    d[Pok.SUB_HP] = 200
    battle.ps_moves(a, d, move_slice(a, 0), 0, False, False)
    assert d[Pok.STATUS] == Status.SLEEP


def test_called_trump_card_reads_the_callers_pp(monkeypatch, make_pokemon, make_battle):
    """A called Trump Card's power comes from Metronome's PP (pokeplatinum ATTACKER_MOVE_SLOT)"""
    _force_metronome(monkeypatch, MoveName.TRUMP_CARD)
    seen = []
    monkeypatch.setattr(battle, "calculate_damage", lambda a, d, mv, *r: seen.append(int(mv[Move.PP])) or 1)
    arr = make_battle([make_pokemon("Munchlax", 20, "Thick Fat", ["Metronome"])],
                      [make_pokemon("Machop", 20, "Guts", ["Leer"])])
    me = my_active(arr)
    move_slice(me, 0)[Move.PP] = 2
    turn_sim(0, (MOVE, 0), arr)
    assert seen == [1]


@pytest.mark.parametrize("roll, power", [(0, 0), (1, 0), (2, 40), (5, 40), (6, 80), (8, 80), (9, 120)])
def test_present_rolls(monkeypatch, poke, roll, power):
    """Showdown Present: 20% heal (power 0), 40% 40, 30% 80, 10% 120"""
    monkeypatch.setattr(battle.random, "randint", lambda a, b: roll)
    a = poke("Delibird", 30, "Hustle", ["Present"])
    present = battle._present_move(move_slice(a, 0))
    assert present[Move.POWER] == power
    assert move_slice(a, 0)[Move.POWER] == 0           # the slot keeps its data


def test_present_heal(poke):
    """1/4 of the target's max HP, capped at the max, Heal Block stops it"""
    d = poke("Snorlax", 50, "Thick Fat", ["Tackle"])
    d[Pok.CURRENT_HP] = 10
    battle._present_heal(d)
    assert d[Pok.CURRENT_HP] == 10 + d[Pok.MAX_HP] // 4
    d[Pok.CURRENT_HP] = d[Pok.MAX_HP] - 1
    battle._present_heal(d)
    assert d[Pok.CURRENT_HP] == d[Pok.MAX_HP]
    d[Pok.CURRENT_HP] = 10
    d[Pok.VOL_STATUS] |= VolStatus.HEAL_BLOCK
    battle._present_heal(d)
    assert d[Pok.CURRENT_HP] == 10


def test_present_heal_turn_reaches_behind_a_substitute(monkeypatch, make_pokemon, make_battle):
    """A heal roll heals the target instead of hitting it, through its Substitute"""
    monkeypatch.setattr(battle.random, "randint", lambda a, b: a)    # heal roll, accuracy hits
    arr = make_battle([make_pokemon("Delibird", 30, "Hustle", ["Present"])],
                      [make_pokemon("Snorlax", 30, "Thick Fat", ["Harden"])])
    foe = opp_active(arr)
    foe[Pok.CURRENT_HP] = 20
    foe[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
    foe[Pok.SUB_HP] = 30
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] == 20 + foe[Pok.MAX_HP] // 4 and foe[Pok.SUB_HP] == 30


def _kick_powers(monkeypatch, kicks):
    """Records each hit's power, kick_hits answers from kicks in order"""
    powers = []
    monkeypatch.setattr(battle, "calculate_damage", lambda a, d, mv, *r: powers.append(int(mv[Move.POWER])) or 1)
    answers = iter(kicks)
    monkeypatch.setattr(battle, "kick_hits", lambda *a: next(answers))
    return powers


@pytest.mark.parametrize("kicks, expected", [
    ((True, True), [10, 20, 30]), ((False,), [10]), ((True, False), [10, 20]),
])
def test_triple_kick_ramps_and_stops_at_a_miss(monkeypatch, poke, kicks, expected):
    """10, 20 and 30 power, a missed kick ends the move"""
    powers = _kick_powers(monkeypatch, kicks)
    a = poke("Hitmontop", 30, "Intimidate", ["Triple Kick"])
    d = poke("Snorlax", 50, "Thick Fat", ["Tackle"])
    battle.ps_moves_multihit(a, d, move_slice(a, 0), 0, False, False)
    assert powers == expected
    assert move_slice(a, 0)[Move.POWER] == 10


def test_triple_kick_ignores_skill_link(monkeypatch, poke):
    powers = _kick_powers(monkeypatch, (True, True, True, True))
    a = poke("Hitmontop", 30, "Skill Link", ["Triple Kick"])
    d = poke("Snorlax", 50, "Thick Fat", ["Tackle"])
    battle.ps_moves_multihit(a, d, move_slice(a, 0), 0, False, False)
    assert powers == [10, 20, 30]


def test_kick_hits_rolls_accuracy(monkeypatch, poke):
    """Each later kick rolls the move's accuracy, No Guard skips it"""
    a = poke("Hitmontop", 30, "Intimidate", ["Triple Kick"])
    d = poke("Snorlax", 50, "Thick Fat", ["Tackle"])
    mv = move_slice(a, 0)
    monkeypatch.setattr(engine_helper.random, "randint", lambda lo, hi: 90)
    assert engine_helper.kick_hits(mv, a, d, 0)
    monkeypatch.setattr(engine_helper.random, "randint", lambda lo, hi: 91)
    assert not engine_helper.kick_hits(mv, a, d, 0)
    a[Pok.AB_ID] = AbilityNames.NO_GUARD
    assert engine_helper.kick_hits(mv, a, d, 0)


def _beat_up_battle(make_pokemon, make_battle, monkeypatch):
    """Houndour leads, the hits are recorded by member species and do 1 each"""
    seen = []
    monkeypatch.setattr(battle, "beat_up_damage", lambda a, m, d, c: seen.append(int(m[Pok.ID])) or 1)
    monkeypatch.setattr(battle, "calculate_hit_miss", lambda *a: MoveOutcome.HIT)
    arr = make_battle(
        [make_pokemon("Houndour", 20, "Early Bird", ["Beat Up"]),
         make_pokemon("Poochyena", 20, "Run Away", ["Tackle"]),
         make_pokemon("Rattata", 20, "Run Away", ["Tackle"]),
         make_pokemon("Zubat", 20, "Inner Focus", ["Tackle"])],
        [make_pokemon("Snorlax", 50, "Thick Fat", ["Harden"])])
    return arr, seen


def test_beat_up_hits_once_per_healthy_member(monkeypatch, make_pokemon, make_battle):
    """In party order, a fainted or statused member doesn't hit"""
    arr, seen = _beat_up_battle(make_pokemon, make_battle, monkeypatch)
    pok_slice(arr, 1)[Pok.STATUS] = Status.PARALYSIS
    pok_slice(arr, 2)[Pok.CURRENT_HP] = 0
    foe = opp_active(arr)
    hp = foe[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert seen == [PokemonName.HOUNDOUR, PokemonName.ZUBAT]
    assert foe[Pok.CURRENT_HP] == hp - 2


def test_beat_up_skips_a_statused_user(monkeypatch, make_pokemon, make_battle):
    """The user only hits when it has no status either (Showdown gen4 allies)"""
    arr, seen = _beat_up_battle(make_pokemon, make_battle, monkeypatch)
    my_active(arr)[Pok.STATUS] = Status.BURN
    turn_sim(0, (MOVE, 0), arr)
    assert seen == [PokemonName.POOCHYENA, PokemonName.RATTATA, PokemonName.ZUBAT]


def test_beat_up_fails_with_nobody_to_hit(monkeypatch, make_pokemon, make_battle):
    arr, seen = _beat_up_battle(make_pokemon, make_battle, monkeypatch)
    my_active(arr)[Pok.STATUS] = Status.BURN
    for slot in (1, 2, 3):
        pok_slice(arr, slot)[Pok.CURRENT_HP] = 0
    me, foe = my_active(arr), opp_active(arr)
    pp = move_slice(me, 0)[Move.PP]
    turn_sim(0, (MOVE, 0), arr)
    assert seen == [] and foe[Pok.CURRENT_HP] == foe[Pok.MAX_HP]
    assert move_slice(me, 0)[Move.PP] == pp - 1


def test_beat_up_stops_at_a_ko(monkeypatch, make_pokemon, make_battle):
    arr, seen = _beat_up_battle(make_pokemon, make_battle, monkeypatch)
    opp_active(arr)[Pok.CURRENT_HP] = 1
    turn_sim(0, (MOVE, 0), arr)
    assert seen == [PokemonName.HOUNDOUR]


def test_beat_up_hits_a_substitute(monkeypatch, make_pokemon, make_battle):
    """The hits go to the Substitute, the ones after it breaks reach the Pokemon"""
    arr, seen = _beat_up_battle(make_pokemon, make_battle, monkeypatch)
    foe = opp_active(arr)
    foe[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
    foe[Pok.SUB_HP] = 2
    hp = foe[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert len(seen) == 4 and foe[Pok.CURRENT_HP] == hp - 2


def test_last_resort_fails_until_the_other_moves_were_used(monkeypatch, make_pokemon, make_battle):
    """It fails before its hit check while a move is still unused, PP spent, then it works"""
    monkeypatch.setattr(battle, "calculate_hit_miss", lambda *a: MoveOutcome.HIT)
    arr = make_battle([make_pokemon("Eevee", 30, "Run Away", ["Last Resort", "Tackle", "Growl"])],
                      [make_pokemon("Snorlax", 50, "Thick Fat", ["Harden"])])
    me, foe = my_active(arr), opp_active(arr)
    pp = move_slice(me, 0)[Move.PP]
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] == foe[Pok.MAX_HP] and move_slice(me, 0)[Move.PP] == pp - 1
    turn_sim(0, (MOVE, 1), arr)
    turn_sim(0, (MOVE, 2), arr)
    assert me[Pok.LAST_RESORT] == 0b110
    hp = foe[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] < hp


def test_secret_power_in_a_grass_battle_puts_to_sleep(monkeypatch, make_pokemon, make_battle):
    """The terrain picks the 30% effect: sleep on grass"""
    monkeypatch.setattr(battle, "calculate_damage", lambda *a: 1)
    monkeypatch.setattr(battle, "calculate_hit_miss", lambda *a: MoveOutcome.HIT)
    from Engine import status_calc
    monkeypatch.setattr(status_calc.random, "randint", lambda a, b: a)
    arr = make_battle([make_pokemon("Linoone", 30, "Pickup", ["Secret Power"])],
                      [make_pokemon("Snorlax", 50, "Thick Fat", ["Harden"])])
    arr[Field.TERRAIN] = Terrain.GRASS
    turn_sim(0, (MOVE, 0), arr)
    assert opp_active(arr)[Pok.STATUS] == Status.SLEEP


def test_called_return_uses_the_callers_friendship(monkeypatch, make_pokemon, make_battle):
    """A Return Metronome calls has the caller's friendship power"""
    _force_metronome(monkeypatch, MoveName.RETURN)
    powers = []
    real = battle.calculate_damage

    def spy(a, d, mv, *rest):
        from Engine.damage_calc import variable_power
        powers.append(int(variable_power(a, d, mv)))
        return real(a, d, mv, *rest)
    monkeypatch.setattr(battle, "calculate_damage", spy)
    arr = make_battle([make_pokemon("Togepi", 20, "Hustle", ["Metronome"])],
                      [make_pokemon("Machop", 20, "Guts", ["Leer"])])
    my_active(arr)[Pok.FRIENDSHIP] = 100
    turn_sim(0, (MOVE, 0), arr)
    assert powers == [40]


def test_pursuit_before_a_switch_counts_for_last_resort(monkeypatch, make_pokemon, make_battle):
    """A Pursuit used on a switch is a used move like any other (pokeplatinum UpdateLastResort)"""
    _spy_power(monkeypatch)
    mine = [make_pokemon("Rattata", 20, "Run Away", ["Tackle"]),
            make_pokemon("Geodude", 20, "Sturdy", ["Tackle"])]
    arr = make_battle(mine, [make_pokemon("Murkrow", 20, "Insomnia", ["Last Resort", "Pursuit"])])
    foe = opp_active(arr)
    assert battle._pursuit(foe, my_active(arr), 1, False, arr)
    assert foe[Pok.LAST_RESORT] == 0b10


# ── 7.2 fixed and HP-based damage ─────────────────────────────────────────────

@pytest.fixture(name="always_hit")
def fixture_always_hit(monkeypatch):
    """Every move hits"""
    monkeypatch.setattr(battle, "calculate_hit_miss", lambda *a: MoveOutcome.HIT)


@pytest.mark.parametrize("foe_hp, left", [(51, 26), (2, 1), (1, 0)])
def test_super_fang_halves_current_hp(make_pokemon, make_battle, always_hit, foe_hp, left):
    """Half the target's HP rounded down, at least 1 (pokeplatinum effect 0040, BattleSystem_Divide)"""
    arr = make_battle([make_pokemon("Raticate", 50, "Run Away", ["Super Fang"])],
                      [make_pokemon("Steelix", 50, "Sturdy", ["Harden"])])
    foe = opp_active(arr)
    foe[Pok.CURRENT_HP] = foe_hp
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] == left


def test_super_fang_misses_a_ghost(make_pokemon, make_battle):
    """No type multiplier, but the Ghost immunity stays (pokeplatinum ApplyTypeChart)"""
    arr = make_battle([make_pokemon("Raticate", 50, "Run Away", ["Super Fang"])],
                      [make_pokemon("Gastly", 50, "Levitate", ["Lick"])])
    hp = opp_active(arr)[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert opp_active(arr)[Pok.CURRENT_HP] == hp


def test_super_fang_on_a_substitute_reads_the_targets_hp(make_pokemon, make_battle, always_hit):
    """The damage comes from the Pokemon's HP, the Substitute takes it"""
    arr = make_battle([make_pokemon("Raticate", 50, "Run Away", ["Super Fang"])],
                      [make_pokemon("Steelix", 50, "Sturdy", ["Harden"])])
    foe = opp_active(arr)
    foe[Pok.CURRENT_HP] = 100
    foe[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
    foe[Pok.SUB_HP] = 80
    turn_sim(0, (MOVE, 0), arr)
    assert (foe[Pok.CURRENT_HP], foe[Pok.SUB_HP]) == (100, 30)


@pytest.mark.parametrize("my_hp, foe_hp, left", [(10, 80, 10), (80, 80, 80), (90, 80, 80)])
def test_endeavor(make_pokemon, make_battle, my_hp, foe_hp, left):
    """The target drops to the user's HP, it fails unless the target has more (pokeplatinum
    effect 0189)"""
    arr = make_battle([make_pokemon("Raticate", 50, "Run Away", ["Endeavor"])],
                      [make_pokemon("Steelix", 50, "Sturdy", ["Harden"])])
    me, foe = my_active(arr), opp_active(arr)
    me[Pok.CURRENT_HP], foe[Pok.CURRENT_HP] = my_hp, foe_hp
    pp = move_slice(me, 0)[Move.PP]
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] == left
    assert move_slice(me, 0)[Move.PP] == pp - 1


@pytest.mark.parametrize("foe_move", ["Water Gun", "Tackle"])
def test_metal_burst_returns_one_and_a_half(make_pokemon, make_battle, foe_move):
    """1.5x the last hit taken this turn, physical or special (pokeplatinum BtlCmd_TryMetalBurst)"""
    arr = make_battle([make_pokemon("Steelix", 50, "Sturdy", ["Metal Burst"])],
                      [make_pokemon("Squirtle", 50, "Torrent", [foe_move])])
    me, foe = my_active(arr), opp_active(arr)
    my_hp, foe_hp = me[Pok.CURRENT_HP], foe[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    taken = my_hp - me[Pok.CURRENT_HP]
    assert taken > 0
    assert foe_hp - foe[Pok.CURRENT_HP] == taken * 15 // 10


def test_metal_burst_fails_moving_first(make_pokemon, make_battle):
    """Nothing taken yet this turn"""
    arr = make_battle([make_pokemon("Raticate", 50, "Run Away", ["Metal Burst"])],
                      [make_pokemon("Steelix", 50, "Sturdy", ["Tackle"])])
    hp = opp_active(arr)[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert opp_active(arr)[Pok.CURRENT_HP] == hp


@pytest.mark.parametrize("move", ["Counter", "Metal Burst"])
def test_damage_record_is_cleared_at_turn_end(make_pokemon, make_battle, move):
    """A record left from a turn the move didn't run in (full paralysis, a flinch) doesn't reach
    the next turn (pokeplatinum turnFlags)"""
    arr = make_battle([make_pokemon("Steelix", 50, "Sturdy", [move])],
                      [make_pokemon("Raticate", 50, "Run Away", ["Growl"])])
    me, foe = my_active(arr), opp_active(arr)
    me[Pok.DMG_TAKEN] = 30
    battle._finish_turn(arr)
    assert me[Pok.DMG_TAKEN] == 0
    hp = foe[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] == hp


def test_charging_bide_keeps_its_damage_record(make_pokemon, make_battle):
    """Bide adds up its damage across turns"""
    arr = make_battle([make_pokemon("Steelix", 50, "Sturdy", ["Bide"])],
                      [make_pokemon("Raticate", 50, "Run Away", ["Tackle"])])
    me = my_active(arr)
    hp = me[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.VOL_STATUS] & VolStatus.BIDE
    assert me[Pok.DMG_TAKEN] == hp - me[Pok.CURRENT_HP] > 0


@pytest.mark.parametrize("my_hp, foe_hp, mine, theirs", [
    (20, 101, 60, 60),    # odd sum rounds down
    (150, 10, 80, 50),    # the foe's max HP (50) caps its share
])
def test_pain_split(make_pokemon, make_battle, my_hp, foe_hp, mine, theirs):
    """Both go to the average, capped at max HP (pokeplatinum subscript_pain_split,
    BtlCmd_UpdateHealthBarValue). It isn't damage: nothing recorded"""
    arr = make_battle([make_pokemon("Wobbuffet", 50, "Shadow Tag", ["Pain Split"])],
                      [make_pokemon("Raticate", 50, "Run Away", ["Harden"])])
    me, foe = my_active(arr), opp_active(arr)
    me[Pok.MAX_HP], foe[Pok.MAX_HP] = 160, max(foe_hp, 50)
    me[Pok.CURRENT_HP], foe[Pok.CURRENT_HP] = my_hp, foe_hp
    turn_sim(0, (MOVE, 0), arr)
    assert (me[Pok.CURRENT_HP], foe[Pok.CURRENT_HP]) == (mine, theirs)
    assert me[Pok.DMG_TAKEN] == 0 == foe[Pok.DMG_TAKEN]


def test_pain_split_hurts_the_one_losing_hp(poke):
    """The side losing HP counts as hurt for Assurance (pokeplatinum subscript_update_hp)"""
    a = poke("Wobbuffet", 50, "Shadow Tag", ["Pain Split"])
    d = poke("Raticate", 50, "Run Away", ["Harden"])
    a[Pok.CURRENT_HP] = 10
    battle._pain_split(a, d)
    assert d[Pok.VOL_STATUS] & VolStatus.HURT_THIS_TURN
    assert not a[Pok.VOL_STATUS] & VolStatus.HURT_THIS_TURN


def test_pain_split_fails_into_a_substitute(make_pokemon, make_battle):
    """pokeplatinum subscript_pain_split checks the Substitute first"""
    arr = make_battle([make_pokemon("Wobbuffet", 50, "Shadow Tag", ["Pain Split"])],
                      [make_pokemon("Raticate", 50, "Run Away", ["Harden"])])
    me, foe = my_active(arr), opp_active(arr)
    me[Pok.CURRENT_HP] = 10
    foe[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
    foe[Pok.SUB_HP] = 20
    hp = foe[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert (me[Pok.CURRENT_HP], foe[Pok.CURRENT_HP]) == (10, hp)


@pytest.mark.parametrize("foe_hp, left", [(5, 1), (1, 1)])
def test_false_swipe_leaves_one_hp(make_pokemon, make_battle, always_hit, foe_hp, left):
    """A lethal hit leaves 1 HP, at 1 HP it deals nothing (pokeplatinum
    BattleControllerPlayer_UpdateHP)"""
    arr = make_battle([make_pokemon("Raticate", 50, "Run Away", ["False Swipe"])],
                      [make_pokemon("Rattata", 5, "Run Away", ["Growl"], item="Focus Sash")])
    foe = opp_active(arr)
    foe[Pok.CURRENT_HP] = foe_hp
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] == left
    assert foe[Pok.ITEM_ID] == ItemNames.FOCUS_SASH or foe_hp == foe[Pok.MAX_HP]


# ── 7.3 turn order ───────────────────────────────────────────────────────────

def _record_power(monkeypatch, move_id):
    """calculate_damage returns 10 and keeps the base power each use of move_id saw"""
    powers = []

    def fake(attacker, defender, move, *rest):
        if move[Move.ID] == move_id:
            powers.append(int(move[Move.POWER]))
        return 10
    monkeypatch.setattr(battle, "calculate_damage", fake)
    return powers


@pytest.mark.parametrize("move", ["Revenge", "Avalanche"])
@pytest.mark.parametrize("foe_move, power", [("Tackle", 120), ("Growl", 60)])
def test_revenge_doubles_after_a_hit(monkeypatch, make_pokemon, make_battle, always_hit, move,
                                     foe_move, power):
    """Doubled when the target's damaging move hit the user this turn (pokeplatinum
    BtlCmd_CalcRevengePowerMul)"""
    powers = _record_power(monkeypatch, getattr(MoveName, move.upper()))
    arr = make_battle([make_pokemon("Hariyama", 50, "Thick Fat", [move])],
                      [make_pokemon("Raticate", 50, "Run Away", [foe_move])])
    turn_sim(0, (MOVE, 0), arr)
    assert powers == [power]


def test_revenge_after_a_hit_on_the_substitute(monkeypatch, make_pokemon, make_battle, always_hit):
    """A hit on the Substitute isn't recorded (pokeplatinum BattleControllerPlayer_UpdateHP)"""
    powers = _record_power(monkeypatch, MoveName.REVENGE)
    arr = make_battle([make_pokemon("Hariyama", 50, "Thick Fat", ["Revenge"])],
                      [make_pokemon("Raticate", 50, "Run Away", ["Tackle"])])
    me = my_active(arr)
    me[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
    me[Pok.SUB_HP] = 50
    turn_sim(0, (MOVE, 0), arr)
    assert powers == [60]


def test_damaged_by_move_is_cleared_at_turn_end(make_pokemon, make_battle, always_hit):
    """It only lasts the turn (pokeplatinum turnFlags)"""
    arr = make_battle([make_pokemon("Hariyama", 50, "Thick Fat", ["Harden"])],
                      [make_pokemon("Raticate", 50, "Run Away", ["Tackle"])])
    me = my_active(arr)
    battle._apply_move_damage(opp_active(arr), me, move_slice(opp_active(arr), 0), 5)
    assert me[Pok.VOL_STATUS2] & VolStatus2.DAMAGED_BY_MOVE
    battle._finish_turn(arr)
    assert not me[Pok.VOL_STATUS2] & VolStatus2.DAMAGED_BY_MOVE


@pytest.mark.parametrize("mine, theirs, power", [
    ("Steelix", "Raticate", 100),   # moves second
    ("Raticate", "Steelix", 50),    # moves first
])
def test_payback_doubles_moving_second(monkeypatch, make_pokemon, make_battle, always_hit, mine,
                                       theirs, power):
    """pokeplatinum BtlCmd_CalcPaybackPower, Showdown gen4 queue.willMove"""
    powers = _record_power(monkeypatch, MoveName.PAYBACK)
    arr = make_battle([make_pokemon(mine, 50, "Sturdy", ["Payback"])],
                      [make_pokemon(theirs, 50, "Sturdy", ["Harden"])])
    turn_sim(0, (MOVE, 0), arr)
    assert powers == [power]


def test_payback_doubles_into_a_switch_or_an_item(poke):
    """The target's action was a switch or an item, it already used its turn"""
    a = poke("Raticate", 50, "Run Away", ["Payback"])
    assert engine_helper.turn_order_doubles(a, move_slice(a, 0), 1, -1)
    assert engine_helper.turn_order_doubles(a, move_slice(a, 0), 1, -10)
    assert not engine_helper.turn_order_doubles(a, move_slice(a, 0), 1, 0)


@pytest.mark.parametrize("foe_move, hits", [("Tackle", True), ("Harden", False)])
def test_sucker_punch_needs_an_attack(make_pokemon, make_battle, always_hit, foe_move, hits):
    """Fails into a status move, after the PP is spent (pokeplatinum BtlCmd_TrySuckerPunch)"""
    arr = make_battle([make_pokemon("Raticate", 50, "Run Away", ["Sucker Punch"])],
                      [make_pokemon("Steelix", 50, "Sturdy", [foe_move])])
    me, foe = my_active(arr), opp_active(arr)
    hp, pp = foe[Pok.CURRENT_HP], move_slice(me, 0)[Move.PP]
    turn_sim(0, (MOVE, 0), arr)
    assert (foe[Pok.CURRENT_HP] < hp) == hits
    assert move_slice(me, 0)[Move.PP] == pp - 1


def test_sucker_punch_fail_cases(poke):
    """The target already acted (moved first, switched, used an item) or is recharging (Showdown
    gen4 mustrecharge). Struggle counts as an attack"""
    a = poke("Raticate", 50, "Run Away", ["Sucker Punch"])
    d = poke("Steelix", 50, "Sturdy", ["Tackle", "Harden"])
    sucker = move_slice(a, 0)
    assert not engine_helper.sucker_punch_fails(d, sucker, 1, 0)
    assert engine_helper.sucker_punch_fails(d, sucker, 1, 1)
    assert engine_helper.sucker_punch_fails(d, sucker, 2, 0)
    assert engine_helper.sucker_punch_fails(d, sucker, 1, -1)
    assert not engine_helper.sucker_punch_fails(d, sucker, 1, 10)
    d[Pok.CHARGE_RECHARGE] = -1
    assert engine_helper.sucker_punch_fails(d, sucker, 1, 0)


@pytest.mark.parametrize("foe_move, sub, hits", [
    ("Tackle", False, False), ("Growl", False, True), ("Tackle", True, True),
])
def test_focus_punch_loses_focus_when_hit(make_pokemon, make_battle, always_hit, foe_move, sub, hits):
    """A damaging hit before it moves makes it fail after the PP is spent, a hit on its Substitute
    doesn't (pokeplatinum effect 0170)"""
    arr = make_battle([make_pokemon("Machop", 50, "Guts", ["Focus Punch"])],
                      [make_pokemon("Raticate", 50, "Run Away", [foe_move])])
    me, foe = my_active(arr), opp_active(arr)
    if sub:
        me[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
        me[Pok.SUB_HP] = 50
    hp, pp = foe[Pok.CURRENT_HP], move_slice(me, 0)[Move.PP]
    turn_sim(0, (MOVE, 0), arr)
    assert (foe[Pok.CURRENT_HP] < hp) == hits
    assert move_slice(me, 0)[Move.PP] == pp - 1


def test_focus_punch_user_does_not_flinch(poke):
    """It loses its focus instead, Steadfast doesn't trigger (Showdown gen4 focuspunch
    onTryAddVolatile)"""
    a = poke("Riolu", 50, "Steadfast", ["Focus Punch"])
    d = poke("Raticate", 50, "Run Away", ["Fake Out"])
    assert not engine_helper.early_returns(a, d, 2, True, move_slice(a, 0))
    assert a[Pok.SPEED_STAT_STAGE] == 0


# ── 8.1 stat stages ──────────────────────────────────────────────────────────

def _stage_battle(make_pokemon, make_battle, move, my_ab="Run Away", foe_ab="Thick Fat",
                  my_gender="Male", foe_gender="Female"):
    """My Rattata using move against a Munchlax that only Splashes"""
    return make_battle(
        [make_pokemon("Rattata", 50, my_ab, [move], gender=my_gender)],
        [make_pokemon("Munchlax", 50, foe_ab, ["Splash"], gender=foe_gender)],
    )


@pytest.mark.parametrize("hp_cut, stage, works", [(0, 0, True), (0, 6, False), (1, 0, False), (2, 0, True)])
def test_belly_drum(make_pokemon, make_battle, hp_cut, stage, works):
    """+6 Attack for half the max HP; fails at +6 or at half HP or less (hp_cut 1: exactly half,
    2: one above), PP still spent (pokeplatinum subscript_belly_drum)"""
    arr = _stage_battle(make_pokemon, make_battle, "Belly Drum")
    me = my_active(arr)
    half = me[Pok.MAX_HP] // 2
    if hp_cut:
        me[Pok.CURRENT_HP] = half + (hp_cut - 1)
    me[Pok.ATTACK_STAT_STAGE] = stage
    hp, pp = me[Pok.CURRENT_HP], move_slice(me, 0)[Move.PP]
    turn_sim(0, (MOVE, 0), arr)
    assert move_slice(me, 0)[Move.PP] == pp - 1
    assert me[Pok.CURRENT_HP] == (hp - half if works else hp)
    assert me[Pok.ATTACK_STAT_STAGE] == (6 if works else stage)
    assert not me[Pok.VOL_STATUS2] & VolStatus2.DAMAGED_BY_MOVE


def test_acupressure_raises_a_stat_below_plus_6(make_pokemon, make_battle):
    """+2 to a random stat among those below +6, capped at +6 (BtlCmd_BoostRandomStatBy2)"""
    arr = _stage_battle(make_pokemon, make_battle, "Acupressure")
    me = my_active(arr)
    stages = range(Pok.ATTACK_STAT_STAGE, Pok.EVASION_STAT_STAGE + 1)
    for idx in stages:
        me[idx] = 6
    me[Pok.SPEED_STAT_STAGE] = 5
    turn_sim(0, (MOVE, 0), arr)
    assert [me[i] for i in stages] == [6] * 7
    random.seed(3)
    for idx in stages:
        me[idx] = 0
    for _ in range(3):
        turn_sim(0, (MOVE, 0), arr)
    assert sum(me[i] for i in stages) == 6 and all(me[i] % 2 == 0 for i in stages)


@pytest.mark.parametrize("setup", ["all_six", "sub"])
def test_acupressure_fails(make_pokemon, make_battle, setup):
    """Fails with every stat at +6, or behind the user's own Substitute (effect 226)"""
    arr = _stage_battle(make_pokemon, make_battle, "Acupressure")
    me = my_active(arr)
    if setup == "all_six":
        for idx in range(Pok.ATTACK_STAT_STAGE, Pok.EVASION_STAT_STAGE + 1):
            me[idx] = 6
    else:
        me[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
        me[Pok.SUB_HP] = 30
    before = me.copy()
    turn_sim(0, (MOVE, 0), arr)
    assert all(me[i] == before[i] for i in range(Pok.ATTACK_STAT_STAGE, Pok.EVASION_STAT_STAGE + 1))


@pytest.mark.parametrize("my_ab, foe_ab, my_gender, foe_gender, drop, revealed", [
    ("Run Away", "Thick Fat", "Male", "Female", -2, False),
    ("Run Away", "Thick Fat", "Female", "Male", -2, False),
    ("Run Away", "Thick Fat", "Male", "Male", 0, False),
    ("Run Away", "Thick Fat", "Genderless", "Female", 0, False),
    ("Run Away", "Thick Fat", "Male", "Genderless", 0, False),
    ("Run Away", "Oblivious", "Male", "Female", 0, True),
    ("Mold Breaker", "Oblivious", "Male", "Female", -2, False),
    ("Run Away", "Clear Body", "Male", "Female", 0, False),
])
def test_captivate(make_pokemon, make_battle, always_hit, my_ab, foe_ab, my_gender, foe_gender,
                   drop, revealed):
    """SpAtk -2 on a foe of the other gender; Oblivious stops it with its message unless Mold
    Breaker, Clear Body like any drop (pokeplatinum effect 265)"""
    arr = _stage_battle(make_pokemon, make_battle, "Captivate", my_ab, foe_ab, my_gender, foe_gender)
    foe = opp_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.SPECIAL_ATTACK_STAT_STAGE] == drop
    assert bool(foe[Pok.AB_KNOWN]) == revealed


def test_captivate_reveals_oblivious_behind_a_substitute(make_pokemon, make_battle, always_hit):
    """The Oblivious check comes before the stat drop's Substitute check (effect 265)"""
    arr = _stage_battle(make_pokemon, make_battle, "Captivate", foe_ab="Oblivious")
    foe = opp_active(arr)
    foe[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
    foe[Pok.SUB_HP] = 30
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.AB_KNOWN]


STAGES = range(Pok.ATTACK_STAT_STAGE, Pok.EVASION_STAT_STAGE + 1)


def _set_stages(pok, values):
    for idx, val in zip(STAGES, values):
        pok[idx] = val


def test_haze_clears_both_sides_and_focus_energy(make_pokemon, make_battle):
    """Every stage of both actives back to 0, Focus Energy gone on both (pokeplatinum
    BtlCmd_ResetAllStatChanges, Showdown gen4 haze)"""
    arr = _stage_battle(make_pokemon, make_battle, "Haze")
    me, foe = my_active(arr), opp_active(arr)
    _set_stages(me, [2, -1, 3, 0, 1, -6, 6])
    _set_stages(foe, [-2, 4, 0, 1, -3, 2, 1])
    me[Pok.VOL_STATUS] |= VolStatus.FOCUS_ENERGY
    foe[Pok.VOL_STATUS] |= VolStatus.FOCUS_ENERGY
    turn_sim(0, (MOVE, 0), arr)
    assert [me[i] for i in STAGES] == [foe[i] for i in STAGES] == [0] * 7
    assert not (me[Pok.VOL_STATUS] | foe[Pok.VOL_STATUS]) & VolStatus.FOCUS_ENERGY


@pytest.mark.parametrize("foe_sub", [False, True])
def test_psych_up_copies_the_stages_only(make_pokemon, make_battle, foe_sub):
    """The user takes all seven stages, through a Substitute; Focus Energy isn't copied in Gen IV,
    and the user keeps its own (Showdown gen5 psychup)"""
    arr = _stage_battle(make_pokemon, make_battle, "Psych Up")
    me, foe = my_active(arr), opp_active(arr)
    _set_stages(me, [-1, -1, 2, 0, 0, 0, 3])
    _set_stages(foe, [2, -1, 0, 1, -3, 2, 1])
    foe[Pok.VOL_STATUS] |= VolStatus.FOCUS_ENERGY
    if foe_sub:
        foe[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
        foe[Pok.SUB_HP] = 30
    turn_sim(0, (MOVE, 0), arr)
    assert [me[i] for i in STAGES] == [2, -1, 0, 1, -3, 2, 1]
    assert [foe[i] for i in STAGES] == [2, -1, 0, 1, -3, 2, 1]
    assert not me[Pok.VOL_STATUS] & VolStatus.FOCUS_ENERGY


@pytest.mark.parametrize("move, swapped", [
    ("Power Swap", (Pok.ATTACK_STAT_STAGE, Pok.SPECIAL_ATTACK_STAT_STAGE)),
    ("Guard Swap", (Pok.DEFENSE_STAT_STAGE, Pok.SPECIAL_DEFENSE_STAT_STAGE)),
    ("Heart Swap", tuple(STAGES)),
])
def test_stage_swaps(make_pokemon, make_battle, always_hit, move, swapped):
    """Power Swap trades Atk and SpAtk stages, Guard Swap Def and SpDef, Heart Swap all seven,
    through a Substitute; Focus Energy stays where it is (Showdown powerswap, guardswap, heartswap)"""
    arr = _stage_battle(make_pokemon, make_battle, move)
    me, foe = my_active(arr), opp_active(arr)
    mine, theirs = [1, -1, 2, -2, 3, -3, 4], [-4, 5, -5, 6, -6, 0, 2]
    _set_stages(me, mine)
    _set_stages(foe, theirs)
    foe[Pok.VOL_STATUS] |= VolStatus.FOCUS_ENERGY
    foe[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
    foe[Pok.SUB_HP] = 30
    turn_sim(0, (MOVE, 0), arr)
    for k, idx in enumerate(STAGES):
        assert me[idx] == (theirs[k] if idx in swapped else mine[k])
        assert foe[idx] == (mine[k] if idx in swapped else theirs[k])
    assert foe[Pok.VOL_STATUS] & VolStatus.FOCUS_ENERGY and not me[Pok.VOL_STATUS] & VolStatus.FOCUS_ENERGY


def test_power_trick_swaps_and_swaps_back(make_pokemon, make_battle):
    """Attack and Defense trade, a second use trades them back (pokeplatinum
    subscript_user_swap_atk_and_def)"""
    arr = _stage_battle(make_pokemon, make_battle, "Power Trick")
    me = my_active(arr)
    atk, dfn = me[Pok.ATTACK], me[Pok.DEFENSE]
    turn_sim(0, (MOVE, 0), arr)
    assert (me[Pok.ATTACK], me[Pok.DEFENSE]) == (dfn, atk)
    assert me[Pok.VOL_STATUS2] & VolStatus2.POWER_TRICK
    turn_sim(0, (MOVE, 0), arr)
    assert (me[Pok.ATTACK], me[Pok.DEFENSE]) == (atk, dfn)
    assert not me[Pok.VOL_STATUS2] & VolStatus2.POWER_TRICK


def test_power_trick_ends_on_switch_out(make_pokemon, make_battle):
    """Switching out gives the Pokemon its own Attack and Defense back"""
    arr = _stage_battle(make_pokemon, make_battle, "Power Trick")
    me = my_active(arr)
    atk, dfn = me[Pok.ATTACK], me[Pok.DEFENSE]
    battle.power_trick(me)
    engine_helper.reset_switch_out(me)
    assert (me[Pok.ATTACK], me[Pok.DEFENSE]) == (atk, dfn)
    assert not me[Pok.VOL_STATUS2] & VolStatus2.POWER_TRICK


def test_baton_pass_hands_over_power_trick(make_pokemon, make_battle):
    """The receiver gets the effect and its own Attack and Defense trade; the passer gets its own
    back (pokeplatinum MOVE_EFFECT_BATON_PASSED, BattleSystem_UpdateAfterSwitch)"""
    arr = _baton_battle(make_pokemon, make_battle, 30, 10)
    old, new = pok_slice(arr, 0), pok_slice(arr, 1)
    old_stats, new_stats = (old[Pok.ATTACK], old[Pok.DEFENSE]), (new[Pok.ATTACK], new[Pok.DEFENSE])
    battle.power_trick(old)
    battle._pass_baton(old, new)
    engine_helper.reset_switch_out(old)
    assert new[Pok.VOL_STATUS2] & VolStatus2.POWER_TRICK
    assert (new[Pok.ATTACK], new[Pok.DEFENSE]) == new_stats[::-1]
    assert (old[Pok.ATTACK], old[Pok.DEFENSE]) == old_stats
    engine_helper.reset_switch_out(new)
    assert (new[Pok.ATTACK], new[Pok.DEFENSE]) == new_stats


# ── 8.2 status and sleep ─────────────────────────────────────────────────────

def _sleep_battle(make_pokemon, make_battle, moves, my_ab="Run Away", foe_ab="Thick Fat",
                  item=None, bench=(), foe="Munchlax"):
    """My Rattata with moves (and a bench) against a foe that only Splashes"""
    return make_battle(
        [make_pokemon("Rattata", 50, my_ab, moves, item=item)] + list(bench),
        [make_pokemon(foe, 50, foe_ab, ["Splash"])],
    )


def _asleep(pok, counter=5):
    pok[Pok.STATUS] = Status.SLEEP
    pok[Pok.SLEEP_COUNTER] = counter


@pytest.mark.parametrize("move, status, vol", [
    ("Toxic", Status.TOXIC, 0), ("Glare", Status.PARALYSIS, 0), ("Spore", Status.SLEEP, 0),
    ("Lovely Kiss", Status.SLEEP, 0), ("Dark Void", Status.SLEEP, 0),
    ("Poison Gas", Status.POISON, 0), ("Teeter Dance", 0, VolStatus.CONFUSION),
])
def test_status_moves_from_data(make_pokemon, make_battle, always_hit, move, status, vol):
    """These run on their MoveDB data alone"""
    arr = _sleep_battle(make_pokemon, make_battle, [move])
    foe = opp_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.STATUS] == status
    assert foe[Pok.VOL_STATUS] & VolStatus.CONFUSION == vol
    if status == Status.TOXIC:
        assert foe[Pok.BADLY_POISON] == 2


def test_rest_heals_and_sleeps_two_turns(make_pokemon, make_battle):
    """Full HP, the toxic and its counter gone, a counter of 3: two turns asleep, it moves on the
    third ([SD] rest, statusState.time = 3)"""
    arr = _sleep_battle(make_pokemon, make_battle, ["Rest", "Tackle"])
    me, foe = my_active(arr), opp_active(arr)
    me[Pok.CURRENT_HP] = me[Pok.MAX_HP] // 2
    me[Pok.STATUS] = Status.TOXIC
    me[Pok.BADLY_POISON] = 3
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.CURRENT_HP] == me[Pok.MAX_HP]
    assert (me[Pok.STATUS], me[Pok.SLEEP_COUNTER], me[Pok.BADLY_POISON]) == (Status.SLEEP, 3, 0)
    for _ in range(2):
        turn_sim(0, (MOVE, 1), arr)
        assert me[Pok.STATUS] == Status.SLEEP and foe[Pok.CURRENT_HP] == foe[Pok.MAX_HP]
    turn_sim(0, (MOVE, 1), arr)
    assert me[Pok.STATUS] == 0 and foe[Pok.CURRENT_HP] < foe[Pok.MAX_HP]


@pytest.mark.parametrize("setup, works, revealed", [
    ("full_hp", False, False), ("insomnia", False, True), ("vital_spirit", False, True),
    ("uproar", False, False), ("uproar_soundproof", True, False), ("leaf_guard_sun", True, False),
])
def test_rest_fails(make_pokemon, make_battle, setup, works, revealed):
    """Fails at full HP, with Insomnia or Vital Spirit (named) and in an uproar unless Soundproof.
    Leaf Guard in sun doesn't stop it ([SD] gen4 rest onTry, gen4 Leaf Guard skips Rest)"""
    abilities = {"insomnia": "Insomnia", "vital_spirit": "Vital Spirit",
                 "uproar_soundproof": "Soundproof", "leaf_guard_sun": "Leaf Guard"}
    arr = _sleep_battle(make_pokemon, make_battle, ["Rest"], my_ab=abilities.get(setup, "Run Away"))
    me, foe = my_active(arr), opp_active(arr)
    if setup != "full_hp":
        me[Pok.CURRENT_HP] = me[Pok.MAX_HP] // 2
    if setup.startswith("uproar"):
        foe[Pok.VOL_STATUS] |= VolStatus.UPROAR
        foe[Pok.UPROAR_TURNS] = 5
    if setup == "leaf_guard_sun":
        arr[Field.WEATHER] = Weather.SUN
        arr[Field.WEATHER_DURATION] = 5
    hp = me[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert (me[Pok.STATUS] == Status.SLEEP) == works
    assert me[Pok.CURRENT_HP] == (me[Pok.MAX_HP] if works else hp)
    assert bool(me[Pok.AB_KNOWN]) == revealed


def test_rest_fails_when_already_asleep(make_pokemon, make_battle):
    """Sleep Talk calling Rest: already asleep, so no heal and the counter goes on"""
    arr = _sleep_battle(make_pokemon, make_battle, ["Sleep Talk", "Rest"])
    me = my_active(arr)
    me[Pok.CURRENT_HP] = me[Pok.MAX_HP] // 2
    _asleep(me)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.CURRENT_HP] == me[Pok.MAX_HP] // 2
    assert me[Pok.SLEEP_COUNTER] == 4


@pytest.mark.parametrize("asleep", [True, False])
def test_snore_only_while_asleep(make_pokemon, make_battle, asleep):
    """Snore works through sleep and fails awake, PP spent either way ([SD] snore onTry)"""
    arr = _sleep_battle(make_pokemon, make_battle, ["Snore"])
    me, foe = my_active(arr), opp_active(arr)
    if asleep:
        _asleep(me, 3)
    pp = move_slice(me, 0)[Move.PP]
    turn_sim(0, (MOVE, 0), arr)
    assert move_slice(me, 0)[Move.PP] == pp - 1
    assert (foe[Pok.CURRENT_HP] < foe[Pok.MAX_HP]) == asleep
    if asleep:
        assert me[Pok.SLEEP_COUNTER] == 2


def test_snore_fails_on_the_turn_it_wakes(make_pokemon, make_battle):
    """Waking up this turn, the user isn't asleep when Snore runs"""
    arr = _sleep_battle(make_pokemon, make_battle, ["Snore"])
    me, foe = my_active(arr), opp_active(arr)
    _asleep(me, 1)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.STATUS] == 0 and foe[Pok.CURRENT_HP] == foe[Pok.MAX_HP]


def test_sleep_talk_calls_another_move(make_pokemon, make_battle):
    """It calls Tackle without spending Tackle's PP, even at 0 PP ([pp] TrySleepTalk skips PP)"""
    arr = _sleep_battle(make_pokemon, make_battle, ["Sleep Talk", "Tackle"])
    me, foe = my_active(arr), opp_active(arr)
    _asleep(me)
    move_slice(me, 1)[Move.PP] = 0
    pp = move_slice(me, 0)[Move.PP]
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] < foe[Pok.MAX_HP]
    assert move_slice(me, 0)[Move.PP] == pp - 1 and move_slice(me, 1)[Move.PP] == 0


def test_sleep_talk_can_call_snore(make_pokemon, make_battle):
    """Snore called while asleep works"""
    arr = _sleep_battle(make_pokemon, make_battle, ["Sleep Talk", "Snore"])
    me, foe = my_active(arr), opp_active(arr)
    _asleep(me)
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] < foe[Pok.MAX_HP]


@pytest.mark.parametrize("moves, setup", [
    (["Sleep Talk", "Tackle"], "awake"),
    (["Sleep Talk", "Fly", "Focus Punch", "Uproar"], "asleep"),
    (["Sleep Talk", "Tackle"], "choice_lock"),
    (["Sleep Talk", "Tackle"], "disabled"),
])
def test_sleep_talk_fails(make_pokemon, make_battle, moves, setup):
    """Fails awake, with only uncallable moves (Fly is a charge move with no nosleeptalk flag),
    under a choice lock and with the only other move disabled (move_blocked)"""
    item = "Choice Band" if setup == "choice_lock" else None
    arr = _sleep_battle(make_pokemon, make_battle, moves, item=item)
    me, foe = my_active(arr), opp_active(arr)
    if setup != "awake":
        _asleep(me)
    if setup == "choice_lock":
        me[Pok.CHOICE_LOCK] = 1
    if setup == "disabled":
        me[Pok.VOL_STATUS] |= VolStatus.DISABLE
        me[Pok.DISABLE_TURNS] = 4 * 4 + 1
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] == foe[Pok.MAX_HP]
    assert not me[Pok.VOL_STATUS] & VolStatus.SEMI_INVULNERABLE
    assert me[Pok.LOCKED_MOVE] == -1


@pytest.mark.parametrize("foe_ab, damage", [("Thick Fat", True), ("Magic Guard", False)])
def test_nightmare_hurts_a_sleeper(make_pokemon, make_battle, foe_ab, damage):
    """1/4 of max HP at the end of each turn asleep, none with Magic Guard"""
    arr = _sleep_battle(make_pokemon, make_battle, ["Nightmare"], foe_ab=foe_ab)
    foe = opp_active(arr)
    _asleep(foe)
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.VOL_STATUS] & VolStatus.NIGHTMARE
    assert foe[Pok.CURRENT_HP] == foe[Pok.MAX_HP] - (max(1, foe[Pok.MAX_HP] // 4) if damage else 0)


@pytest.mark.parametrize("setup", ["awake", "already", "substitute"])
def test_nightmare_fails(make_pokemon, make_battle, setup):
    """Fails on a foe awake, already in a nightmare or behind a Substitute"""
    arr = _sleep_battle(make_pokemon, make_battle, ["Nightmare"])
    foe = opp_active(arr)
    if setup != "awake":
        _asleep(foe)
    if setup == "already":
        foe[Pok.VOL_STATUS] |= VolStatus.NIGHTMARE
    if setup == "substitute":
        foe[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
        foe[Pok.SUB_HP] = 30
    hp = foe[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert bool(foe[Pok.VOL_STATUS] & VolStatus.NIGHTMARE) == (setup == "already")
    assert foe[Pok.CURRENT_HP] == hp - (max(1, foe[Pok.MAX_HP] // 4) if setup == "already" else 0)


def test_nightmare_ends_once_awake(make_pokemon, make_battle):
    """A Nightmare left on an awake Pokemon does nothing and is gone at the end of the turn"""
    arr = _sleep_battle(make_pokemon, make_battle, ["Splash"])
    foe = opp_active(arr)
    foe[Pok.VOL_STATUS] |= VolStatus.NIGHTMARE
    turn_sim(0, (MOVE, 0), arr)
    assert not foe[Pok.VOL_STATUS] & VolStatus.NIGHTMARE
    assert foe[Pok.CURRENT_HP] == foe[Pok.MAX_HP]


@pytest.mark.parametrize("move", ["Spore", "Rest"])
def test_a_new_sleep_ends_an_old_nightmare(make_pokemon, make_battle, always_hit, move):
    """Woken and asleep again in the same turn: the old Nightmare doesn't hurt ([SD] slp onStart)"""
    arr = _sleep_battle(make_pokemon, make_battle, [move])
    me, foe = my_active(arr), opp_active(arr)
    target = foe if move == "Spore" else me
    target[Pok.VOL_STATUS] |= VolStatus.NIGHTMARE
    if move == "Rest":
        me[Pok.CURRENT_HP] = me[Pok.MAX_HP] // 2
    turn_sim(0, (MOVE, 0), arr)
    assert target[Pok.STATUS] == Status.SLEEP
    assert not target[Pok.VOL_STATUS] & VolStatus.NIGHTMARE
    assert target[Pok.CURRENT_HP] == target[Pok.MAX_HP]


@pytest.mark.parametrize("setup, hits", [("asleep", True), ("awake", False), ("substitute", False)])
def test_dream_eater_needs_a_sleeping_target(make_pokemon, make_battle, setup, hits):
    """Hits and drains a sleeper; an awake one or one behind a Substitute isn't affected ([SD] gen4
    onTryImmunity)"""
    arr = _sleep_battle(make_pokemon, make_battle, ["Dream Eater"])
    me, foe = my_active(arr), opp_active(arr)
    me[Pok.CURRENT_HP] = 1
    if setup != "awake":
        _asleep(foe)
    if setup == "substitute":
        foe[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
        foe[Pok.SUB_HP] = 30
    turn_sim(0, (MOVE, 0), arr)
    assert (foe[Pok.CURRENT_HP] < foe[Pok.MAX_HP]) == hits
    assert (me[Pok.CURRENT_HP] > 1) == hits
    if setup == "substitute":
        assert foe[Pok.SUB_HP] == 30


def test_dream_eater_into_liquid_ooze(make_pokemon, make_battle):
    """Liquid Ooze turns the drain into damage, as for any drain ([SD])"""
    arr = _sleep_battle(make_pokemon, make_battle, ["Dream Eater"], foe_ab="Liquid Ooze")
    me, foe = my_active(arr), opp_active(arr)
    _asleep(foe)
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] < foe[Pok.MAX_HP] and me[Pok.CURRENT_HP] < me[Pok.MAX_HP]


@pytest.mark.parametrize("status, badly", [(Status.BURN, 0), (Status.PARALYSIS, 0), (Status.TOXIC, 5)])
def test_psycho_shift_moves_the_status(make_pokemon, make_battle, always_hit, status, badly):
    """The foe gets the status (toxic starting over) and the user is cured"""
    arr = _sleep_battle(make_pokemon, make_battle, ["Psycho Shift"])
    me, foe = my_active(arr), opp_active(arr)
    me[Pok.STATUS] = status
    me[Pok.BADLY_POISON] = badly
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.STATUS] == 0 and me[Pok.BADLY_POISON] == 0
    assert foe[Pok.STATUS] == status
    if status == Status.TOXIC:
        assert foe[Pok.BADLY_POISON] == 2


def test_psycho_shift_gives_sleep_a_new_count(make_pokemon, make_battle, always_hit):
    """Called by Sleep Talk, the sleep moves with a fresh 2-5 count (the slower foe's own turn
    asleep then takes one off)"""
    arr = _sleep_battle(make_pokemon, make_battle, ["Sleep Talk", "Psycho Shift"])
    me, foe = my_active(arr), opp_active(arr)
    _asleep(me)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.STATUS] == 0 and me[Pok.SLEEP_COUNTER] == 0
    assert foe[Pok.STATUS] == Status.SLEEP and 1 <= foe[Pok.SLEEP_COUNTER] <= 4


@pytest.mark.parametrize("setup, foe, foe_ab, revealed", [
    ("no_status", "Munchlax", "Thick Fat", False),
    ("foe_statused", "Munchlax", "Thick Fat", False),
    ("fire_type", "Ponyta", "Run Away", False),
    ("limber", "Munchlax", "Limber", True),
    ("safeguard", "Munchlax", "Thick Fat", False),
    ("substitute", "Munchlax", "Thick Fat", False),
])
def test_psycho_shift_fails(make_pokemon, make_battle, always_hit, setup, foe, foe_ab, revealed):
    """No status on the user, one on the foe, a foe that can't take it (its ability named), Safeguard
    or a Substitute: the user keeps its status"""
    arr = _sleep_battle(make_pokemon, make_battle, ["Psycho Shift"], foe=foe, foe_ab=foe_ab)
    me, target = my_active(arr), opp_active(arr)
    status = 0 if setup == "no_status" else (Status.PARALYSIS if setup == "limber" else Status.BURN)
    me[Pok.STATUS] = status
    if setup == "foe_statused":
        target[Pok.STATUS] = Status.POISON
    if setup == "safeguard":
        arr[Field.OPP_SIDE_COND] |= SideCondition.SAFEGUARD
        arr[Field.OPP_SIDE_COND + SIDE_SAFEGUARD_TURNS] = 5
    if setup == "substitute":
        target[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
        target[Pok.SUB_HP] = 30
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.STATUS] == status
    assert target[Pok.STATUS] == (Status.POISON if setup == "foe_statused" else 0)
    assert bool(target[Pok.AB_KNOWN]) == revealed


@pytest.mark.parametrize("move, my_ab, cured", [
    ("Heal Bell", "Run Away", (True, True, False)),
    ("Heal Bell", "Mold Breaker", (True, True, True)),
    ("Heal Bell", "Soundproof", (False, True, False)),
    ("Aromatherapy", "Soundproof", (True, True, True)),
])
def test_heal_bell_cures_the_party(make_pokemon, make_battle, move, my_ab, cured):
    """The whole party is cured; Heal Bell skips every Soundproof one, the user's named, unless the
    user has Mold Breaker ([SD] gen4 healbell, suppressingAbility). Aromatherapy cures them all"""
    bench = [make_pokemon("Pikachu", 50, "Static", ["Tackle"]),
             make_pokemon("Whismur", 50, "Soundproof", ["Pound"])]
    arr = _sleep_battle(make_pokemon, make_battle, [move], my_ab=my_ab, bench=bench)
    party = [pok_slice(arr, i) for i in range(3)]
    for pok, status in zip(party, (Status.BURN, Status.PARALYSIS, Status.TOXIC)):
        pok[Pok.STATUS] = status
    party[2][Pok.BADLY_POISON] = 3
    turn_sim(0, (MOVE, 0), arr)
    assert tuple(pok[Pok.STATUS] == 0 for pok in party) == cured
    if my_ab == "Soundproof":
        assert bool(party[0][Pok.AB_KNOWN]) == (move == "Heal Bell")
    if cured[2]:
        assert party[2][Pok.BADLY_POISON] == 0


# ── 8.3 healing ──────────────────────────────────────────────────────────────

def test_roost_drops_the_flying_type_for_the_turn(make_pokemon, make_battle):
    """A faster Pidgey Roosts, the slower foe's Ground move hits it, and it's Flying again at the end
    of the turn (pokeplatinum BasicTypeMulApplies, TURN_FLAG_ROOSTING)"""
    arr = make_battle([make_pokemon("Pidgey", 50, "Keen Eye", ["Roost", "Splash"])],
                      [make_pokemon("Geodude", 5, "Sturdy", ["Mud-Slap"])])
    me = my_active(arr)
    me[Pok.CURRENT_HP] -= 30
    hp = me[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert hp < me[Pok.CURRENT_HP] < hp + me[Pok.MAX_HP] // 2
    assert not me[Pok.VOL_STATUS2] & VolStatus2.ROOST
    hp = me[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 1), arr)
    assert me[Pok.CURRENT_HP] == hp


def test_roost_at_full_hp_keeps_the_flying_type(make_pokemon, make_battle):
    """No heal, no roosting flag (pokeplatinum subscript_roost skips it on MOVE_STATUS_NO_MORE_WORK)"""
    arr = make_battle([make_pokemon("Pidgey", 50, "Keen Eye", ["Roost"])],
                      [make_pokemon("Geodude", 5, "Sturdy", ["Mud-Slap"])])
    me, foe = my_active(arr), opp_active(arr)
    battle._status_move(me, foe, move_slice(me, 0), True, arr, 0)
    assert not me[Pok.VOL_STATUS2] & VolStatus2.ROOST
    me[Pok.CURRENT_HP] -= 1
    battle._status_move(me, foe, move_slice(me, 0), True, arr, 0)
    assert me[Pok.VOL_STATUS2] & VolStatus2.ROOST


def test_roost_ends_on_switch_out(poke):
    """A turn flag, a switch clears it"""
    p = poke("Pidgey", 20, "Keen Eye", ["Roost"])
    p[Pok.VOL_STATUS2] |= VolStatus2.ROOST
    engine_helper.reset_switch_out(p)
    assert not p[Pok.VOL_STATUS2] & VolStatus2.ROOST


def _heal_block_battle(make_pokemon, make_battle, foe_moves, my_moves=("Heal Block",)):
    """My faster Abra against a Munchlax with foe_moves, both with a bench"""
    return make_battle(
        [make_pokemon("Abra", 50, "Synchronize", list(my_moves)),
         make_pokemon("Geodude", 10, "Sturdy", ["Tackle"])],
        [make_pokemon("Munchlax", 20, "Thick Fat", list(foe_moves)),
         make_pokemon("Geodude", 10, "Sturdy", ["Tackle"])],
    )


def _heal_blocked(pok, turns=5):
    pok[Pok.VOL_STATUS] |= VolStatus.HEAL_BLOCK
    pok[Pok.HEAL_BLOCK_TURNS] = turns


def test_heal_block_stops_a_move_picked_before_it(make_pokemon, make_battle):
    """The foe's Recover fails after my faster Heal Block, 5 turns counted down from this turn's end
    (pokeplatinum subscript_heal_block_start, CHECK_STATUS_STATE_HEAL_BLOCK)"""
    arr = _heal_block_battle(make_pokemon, make_battle, ["Recover"])
    foe = opp_active(arr)
    foe[Pok.CURRENT_HP] = 10
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.VOL_STATUS] & VolStatus.HEAL_BLOCK and foe[Pok.HEAL_BLOCK_TURNS] == 4
    assert foe[Pok.CURRENT_HP] == 10
    assert engine_helper.move_blocked(foe, 0)


def test_heal_block_lasts_five_turns_and_fails_while_up(make_pokemon, make_battle):
    """A second one doesn't restart the count, it ends after five ends of turn"""
    arr = _heal_block_battle(make_pokemon, make_battle, ["Splash"])
    foe = opp_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.HEAL_BLOCK_TURNS] == 3
    for _ in range(3):
        engine_helper.heal_block_count(foe)
    assert not foe[Pok.VOL_STATUS] & VolStatus.HEAL_BLOCK and foe[Pok.HEAL_BLOCK_TURNS] == 0


def test_heal_block_fails_into_a_substitute(make_pokemon, make_battle):
    """pokeplatinum CheckSubstitute"""
    arr = _heal_block_battle(make_pokemon, make_battle, ["Splash"])
    foe = opp_active(arr)
    foe[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
    foe[Pok.SUB_HP] = 10
    turn_sim(0, (MOVE, 0), arr)
    assert not foe[Pok.VOL_STATUS] & VolStatus.HEAL_BLOCK


@pytest.mark.parametrize("move", [
    "Recover", "Soft-Boiled", "Milk Drink", "Slack Off", "Heal Order", "Roost", "Moonlight",
    "Morning Sun", "Synthesis", "Rest",
])
def test_heal_block_stops_selecting_its_moves(poke, move):
    """pokeplatinum sMovesAffectedByHealBlock, CHECK_INVALID_HEAL_BLOCK"""
    p = poke("Abra", 20, "Synchronize", [move, "Tackle"])
    assert not engine_helper.move_blocked(p, 0)
    _heal_blocked(p)
    assert engine_helper.move_blocked(p, 0) and not engine_helper.move_blocked(p, 1)


@pytest.mark.parametrize("vol", [VolStatus.INGRAIN, VolStatus.AQUA_RING])
def test_heal_block_stops_ingrain_and_aqua_ring(make_pokemon, make_battle, vol):
    """pokeplatinum MON_COND_CHECK_STATE_INGRAIN / AQUA_RING load subscript_cannot_heal"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Tackle"], ["Tackle"])
    me = my_active(arr)
    me[Pok.VOL_STATUS] = vol
    _heal_blocked(me)
    me[Pok.CURRENT_HP] = 10
    end_of_turn(arr)
    assert me[Pok.CURRENT_HP] == 10 and me[Pok.VOL_STATUS] & vol
    assert me[Pok.HEAL_BLOCK_TURNS] == 4


def test_heal_block_stops_the_leech_seed_heal(make_pokemon, make_battle):
    """The seeded Pokemon still loses its HP (pokeplatinum subscript_leech_seed_effect)"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Tackle"], ["Tackle"])
    me, foe = my_active(arr), opp_active(arr)
    foe[Pok.VOL_STATUS] = VolStatus.LEECH_SEED
    _heal_blocked(me)
    me[Pok.CURRENT_HP] = 10
    foe_hp = foe[Pok.CURRENT_HP]
    end_of_turn(arr)
    assert foe[Pok.CURRENT_HP] == foe_hp - max(1, foe[Pok.MAX_HP] // 8)
    assert me[Pok.CURRENT_HP] == 10


def test_heal_block_stops_the_drain_heal(poke):
    """The heal is gone, Liquid Ooze still hurts (pokeplatinum subscript_drain_half_damage_dealt)"""
    a = poke("Oddish", 20, "Chlorophyll", ["Giga Drain"])
    d = poke("Rattata", 20, "Run Away", ["Tackle"])
    _heal_blocked(a)
    a[Pok.CURRENT_HP] = 10
    engine_helper.drain(a, d, move_slice(a, 0), 20)
    assert a[Pok.CURRENT_HP] == 10
    d[Pok.AB_ID] = AbilityNames.LIQUID_OOZE
    engine_helper.drain(a, d, move_slice(a, 0), 20)
    assert a[Pok.CURRENT_HP] < 10


def test_heal_block_makes_a_called_heal_move_fail(monkeypatch, make_pokemon, make_battle):
    """A called move Heal Block stops fails, like Gravity's (Showdown healblock onModifyMove)"""
    _force_metronome(monkeypatch, MoveName.RECOVER)
    arr = make_battle([make_pokemon("Munchlax", 20, "Thick Fat", ["Metronome"])],
                      [make_pokemon("Machop", 20, "Guts", ["Leer"])])
    me = my_active(arr)
    _heal_blocked(me)
    me[Pok.CURRENT_HP] = 10
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.CURRENT_HP] == 10


def test_sleep_talk_skips_a_heal_blocked_move(make_pokemon, make_battle):
    """Through move_blocked: with Recover its only other move, Sleep Talk fails"""
    arr = _sleep_battle(make_pokemon, make_battle, ["Sleep Talk", "Recover"])
    me = my_active(arr)
    _asleep(me)
    _heal_blocked(me)
    me[Pok.CURRENT_HP] = 10
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.CURRENT_HP] == 10


def test_heal_block_ends_on_switch_out_and_baton_pass_keeps_it(make_pokemon, make_battle):
    """Baton Pass hands it over with its turns (pokeplatinum healBlockTurns), a switch ends it"""
    arr = _heal_block_battle(make_pokemon, make_battle, ["Splash"])
    me, new = my_active(arr), pok_slice(arr, 1)
    _heal_blocked(me, 3)
    battle._pass_baton(me, new)
    assert new[Pok.VOL_STATUS] & VolStatus.HEAL_BLOCK and new[Pok.HEAL_BLOCK_TURNS] == 3
    engine_helper.reset_switch_out(me)
    assert not me[Pok.VOL_STATUS] & VolStatus.HEAL_BLOCK and me[Pok.HEAL_BLOCK_TURNS] == 0


# ── 9.1 Weather: Sunny Day, Hail, Heat Rock, Icy Rock, Weather Ball, Forecast ─

@pytest.mark.parametrize("move, item, weather, left", [
    ("Sunny Day", None, Weather.SUN, 4),
    ("Sunny Day", "Heat Rock", Weather.SUN, 7),
    ("Sunny Day", "Icy Rock", Weather.SUN, 4),
    ("Hail", None, Weather.HAIL, 4),
    ("Hail", "Icy Rock", Weather.HAIL, 7),
    ("Hail", "Heat Rock", Weather.HAIL, 4),
    ("Rain Dance", "Heat Rock", Weather.RAIN, 4),
])
def test_sunny_day_and_hail_with_their_rocks(make_pokemon, make_battle, move, item, weather, left):
    """5 turns plus the user's matching rock: Heat Rock for sun, Icy Rock for hail (pokeplatinum
    effect scripts 0137 and 0164, HOLD_EFFECT_EXTEND_SUN / _HAIL, effectParam 3)"""
    me = make_pokemon("Geodude", 30, "Sturdy", [move], item=item)
    arr = make_battle([me], [make_pokemon("Onix", 30, "Rock Head", ["Harden"])])
    turn_sim(0, (MOVE, 0), arr)
    assert arr[Field.WEATHER] == weather and arr[Field.WEATHER_DURATION] == left


@pytest.mark.parametrize("move, weather, duration", [
    ("Sunny Day", Weather.SUN, 0), ("Sunny Day", Weather.SUN, 3),
    ("Hail", Weather.HAIL, 0), ("Hail", Weather.HAIL, 3),
])
def test_weather_move_fails_under_the_same_weather(make_pokemon, make_battle, move, weather, duration):
    """Under its own weather the move fails, whether a move or an ability set it (Showdown: Hail
    fails under Snow Warning's hail too)"""
    me = make_pokemon("Geodude", 30, "Sturdy", [move], item="Icy Rock")
    arr = make_battle([me], [make_pokemon("Onix", 30, "Rock Head", ["Harden"])])
    arr[Field.WEATHER] = weather
    arr[Field.WEATHER_DURATION] = duration
    turn_sim(0, (MOVE, 0), arr)
    assert arr[Field.WEATHER] == weather
    assert arr[Field.WEATHER_DURATION] == max(0, duration - 1)


def _seen_moves(monkeypatch):
    """(type, power) of every Weather Ball that reaches the hit check"""
    seen = []
    real = battle.calculate_hit_miss

    def spy(mv, *args):
        if mv[Move.ID] == MoveName.WEATHER_BALL:
            seen.append((int(mv[Move.TYPE]), int(mv[Move.POWER])))
        return real(mv, *args)
    monkeypatch.setattr(battle, "calculate_hit_miss", spy)
    return seen


@pytest.mark.parametrize("ability, weather, expected", [
    ("Run Away", 0, (Types.NORMAL, 50)),
    ("Run Away", Weather.SUN, (Types.FIRE, 100)),
    ("Run Away", Weather.RAIN, (Types.WATER, 100)),
    ("Run Away", Weather.SANDSTORM, (Types.ROCK, 100)),
    ("Run Away", Weather.HAIL, (Types.ICE, 100)),
    ("Cloud Nine", Weather.SUN, (Types.NORMAL, 50)),
])
def test_weather_ball_type_and_power(monkeypatch, make_pokemon, make_battle, ability, weather, expected):
    """Double power and the weather's type, Normal 50 with no weather or under Cloud Nine
    (pokeplatinum BtlCmd_CalcWeatherBallParams, Showdown effectiveWeather). The slot keeps its data"""
    seen = _seen_moves(monkeypatch)
    arr = make_battle([make_pokemon("Psyduck", 30, ability, ["Weather Ball"])],
                      [make_pokemon("Onix", 30, "Rock Head", ["Harden"])])
    arr[Field.WEATHER] = weather
    turn_sim(0, (MOVE, 0), arr)
    assert seen[0] == expected
    slot = move_slice(my_active(arr), 0)
    assert (slot[Move.TYPE], slot[Move.POWER]) == (Types.NORMAL, 50)


@pytest.mark.parametrize("ability, weather, hits", [
    ("Run Away", 0, False), ("Run Away", Weather.SUN, True), ("Normalize", Weather.SUN, False),
])
def test_weather_ball_type_reaches_the_type_chart(make_pokemon, make_battle, ability, weather, hits):
    """In sun Weather Ball is Fire and hits a Ghost, Normalize keeps it Normal"""
    arr = make_battle([make_pokemon("Rattata", 30, ability, ["Weather Ball"])],
                      [make_pokemon("Gastly", 30, "Levitate", ["Growl"])])
    arr[Field.WEATHER] = weather
    turn_sim(0, (MOVE, 0), arr)
    foe = opp_active(arr)
    assert (foe[Pok.CURRENT_HP] < foe[Pok.MAX_HP]) == hits


def test_weather_ball_into_water_absorb_in_rain(make_pokemon, make_battle):
    """Its Water type in rain is what Water Absorb takes in"""
    arr = make_battle([make_pokemon("Rattata", 30, "Run Away", ["Weather Ball"])],
                      [make_pokemon("Lapras", 30, "Water Absorb", ["Growl"])])
    arr[Field.WEATHER] = Weather.RAIN
    foe = opp_active(arr)
    foe[Pok.CURRENT_HP] -= 10
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] > foe[Pok.MAX_HP] - 10


@pytest.mark.parametrize("weather, shudders", [(0, False), (Weather.RAIN, True), (Weather.SUN, False)])
def test_anticipation_sees_weather_ball(make_pokemon, weather, shudders):
    """pokeplatinum CalcMoveType gives Anticipation Weather Ball's weather type"""
    me = make_pokemon("Geodude", 30, "Anticipation", ["Tackle"]).to_np()
    foe = make_pokemon("Rattata", 30, "Run Away", ["Weather Ball"]).to_np()
    assert engine_helper.anticipation_shudders(me, foe, False, weather) == shudders


@pytest.mark.parametrize("move, m_type", [
    ("Sunny Day", Types.FIRE), ("Rain Dance", Types.WATER), ("Hail", Types.ICE),
    ("Sandstorm", Types.NORMAL),
])
def test_forecast_follows_the_move_weather(make_pokemon, make_battle, move, m_type):
    """Castform turns into the weather's type once the move set it, sand leaves it Normal
    (pokeplatinum BattleSystem_TriggerFormChange)"""
    arr = make_battle([make_pokemon("Castform", 30, "Forecast", [move])],
                      [make_pokemon("Onix", 30, "Rock Head", ["Harden"])])
    turn_sim(0, (MOVE, 0), arr)
    me = my_active(arr)
    assert (me[Pok.TYPE1], me[Pok.TYPE2]) == (m_type, 0)


def test_forecast_back_to_normal_when_the_weather_ends(make_pokemon, make_battle):
    """The last turn of sun turns it back at the end of the turn"""
    arr = make_battle([make_pokemon("Castform", 30, "Forecast", ["Splash"])],
                      [make_pokemon("Onix", 30, "Rock Head", ["Harden"])])
    arr[Field.WEATHER] = Weather.SUN
    arr[Field.WEATHER_DURATION] = 2
    battle.forecast_actives(arr)
    assert my_active(arr)[Pok.TYPE1] == Types.FIRE
    end_of_turn(arr)
    assert my_active(arr)[Pok.TYPE1] == Types.FIRE
    end_of_turn(arr)
    assert my_active(arr)[Pok.TYPE1] == Types.NORMAL


def test_forecast_on_switch_in_after_drought(make_pokemon, make_battle):
    """A foe's Drought on entry turns Castform Fire (SWITCH_IN_CHECK_STATE_FORM_CHANGE after the
    weather abilities)"""
    arr = make_battle([make_pokemon("Castform", 30, "Forecast", ["Splash"])],
                      [make_pokemon("Vulpix", 5, "Drought", ["Ember"])])
    assert my_active(arr)[Pok.TYPE1] == Types.FIRE


def test_forecast_under_cloud_nine(make_pokemon, make_battle):
    """Cloud Nine turns it back to Normal (Showdown effectiveWeather), and it changes again once
    the holder faints"""
    arr = make_battle([make_pokemon("Castform", 30, "Forecast", ["Splash"])],
                      [make_pokemon("Psyduck", 30, "Cloud Nine", ["Tackle"])])
    arr[Field.WEATHER] = Weather.RAIN
    battle.forecast_actives(arr)
    assert my_active(arr)[Pok.TYPE1] == Types.NORMAL
    opp_active(arr)[Pok.CURRENT_HP] = 0
    battle.forecast_actives(arr)
    assert my_active(arr)[Pok.TYPE1] == Types.WATER


def test_forecast_reset_on_switch_out_and_not_when_fainted(make_pokemon, make_battle):
    """It leaves as Normal, and a fainted Castform doesn't change"""
    arr = make_battle([make_pokemon("Castform", 30, "Forecast", ["Splash"])],
                      [make_pokemon("Onix", 30, "Rock Head", ["Harden"])])
    me = my_active(arr)
    arr[Field.WEATHER] = Weather.HAIL
    battle.forecast_actives(arr)
    assert me[Pok.TYPE1] == Types.ICE
    engine_helper.reset_switch_out(me)
    assert (me[Pok.TYPE1], me[Pok.TYPE2]) == (Types.NORMAL, 0)
    me[Pok.CURRENT_HP] = 0
    battle.forecast_actives(arr)
    assert me[Pok.TYPE1] == Types.NORMAL


def test_forecast_needs_the_ability(make_pokemon, make_battle):
    """Only a Forecast holder changes (pokeplatinum checks the ability)"""
    arr = make_battle([make_pokemon("Rattata", 30, "Run Away", ["Sunny Day"])],
                      [make_pokemon("Onix", 30, "Rock Head", ["Harden"])])
    turn_sim(0, (MOVE, 0), arr)
    assert my_active(arr)[Pok.TYPE1] == Types.NORMAL


# ── 9.3 Spikes, Defog, Rapid Spin, Magnet Rise ───────────────────────────────

SPIKES = SideCondition.SPIKES


def test_spikes_stack_to_three(one_v_one):
    """A fourth Spikes fails (pokeplatinum BtlCmd_TrySpikes)"""
    arr = one_v_one()
    for _ in range(4):
        battle._set_side_condition(SPIKES, arr, OPP_SIDE)
    assert arr[OPP_SIDE] == SPIKES and arr[OPP_SIDE + SIDE_SPIKES] == 3


def test_spikes_go_on_the_foes_side(make_pokemon, make_battle):
    arr = _phase5_battle(make_pokemon, make_battle, ["Spikes"])
    turn_sim(0, (MOVE, 0), arr)
    assert arr[OPP_SIDE] == SPIKES and arr[OPP_SIDE + SIDE_SPIKES] == 1
    assert arr[MY_SIDE] == 0


def test_rapid_spin_clears_spikes_layers(make_pokemon, make_battle):
    arr = _phase5_battle(make_pokemon, make_battle, ["Rapid Spin"])
    arr[MY_SIDE] = SPIKES
    arr[MY_SIDE + SIDE_SPIKES] = 3
    turn_sim(0, (MOVE, 0), arr)
    assert arr[MY_SIDE] == 0 and arr[MY_SIDE + SIDE_SPIKES] == 0


def _defog_battle(make_pokemon, make_battle):
    arr = make_battle([make_pokemon("Pidgey", 20, "Keen Eye", ["Defog"])],
                      [make_pokemon("Rattata", 20, "Run Away", ["Tail Whip"])])
    arr[OPP_SIDE] = (
        SideCondition.REFLECT | SideCondition.LIGHT_SCREEN | SideCondition.SAFEGUARD | SPIKES
        | SideCondition.TOXIC_SPIKES | SR | SideCondition.TAILWIND
    )
    arr[OPP_SIDE + SIDE_REFLECT_TURNS] = arr[OPP_SIDE + SIDE_LIGHT_SCREEN_TURNS] = 4
    arr[OPP_SIDE + SIDE_SAFEGUARD_TURNS] = 4
    arr[OPP_SIDE + SIDE_SPIKES] = 2
    arr[OPP_SIDE + SIDE_TOXIC_SPIKES] = 1
    arr[MY_SIDE] = SR | SPIKES
    arr[MY_SIDE + SIDE_SPIKES] = 1
    return arr


def test_defog_clears_the_targets_side_and_drops_evasion(make_pokemon, make_battle):
    """Screens, Safeguard and hazards go from the target's side, Tailwind and the user's side stay
    (pokeplatinum subscript_defog)"""
    arr = _defog_battle(make_pokemon, make_battle)
    turn_sim(0, (MOVE, 0), arr)
    assert arr[OPP_SIDE] & ~SideCondition.TAILWIND == 0
    assert arr[OPP_SIDE + SIDE_SPIKES] == arr[OPP_SIDE + SIDE_TOXIC_SPIKES] == 0
    assert arr[OPP_SIDE + SIDE_REFLECT_TURNS] == arr[OPP_SIDE + SIDE_SAFEGUARD_TURNS] == 0
    assert arr[MY_SIDE] == SR | SPIKES and arr[MY_SIDE + SIDE_SPIKES] == 1
    assert opp_active(arr)[Pok.EVASION_STAT_STAGE] == -1


def test_defog_into_mist_clears_it_without_the_drop(make_pokemon, make_battle):
    """The drop comes first, so Mist still blocks it"""
    arr = _defog_battle(make_pokemon, make_battle)
    arr[OPP_SIDE] |= SideCondition.MIST
    arr[OPP_SIDE + SIDE_MIST_TURNS] = 4
    turn_sim(0, (MOVE, 0), arr)
    assert not arr[OPP_SIDE] & SideCondition.MIST
    assert opp_active(arr)[Pok.EVASION_STAT_STAGE] == 0


def test_defog_into_a_substitute_clears_without_the_drop(make_pokemon, make_battle):
    """Showdown gen5 defog onHit (bypasssub)"""
    arr = _defog_battle(make_pokemon, make_battle)
    foe = opp_active(arr)
    foe[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
    foe[Pok.SUB_HP] = 10
    turn_sim(0, (MOVE, 0), arr)
    assert not arr[OPP_SIDE] & (SPIKES | SR)
    assert foe[Pok.EVASION_STAT_STAGE] == 0


def test_magnet_rise_dodges_earthquake(make_pokemon, make_battle):
    """Up for the turn it's used in plus 4"""
    arr = make_battle([make_pokemon("Rattata", 20, "Run Away", ["Magnet Rise"])],
                      [make_pokemon("Geodude", 20, "Sturdy", ["Earthquake"])])
    me = my_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.CURRENT_HP] == me[Pok.MAX_HP]
    assert me[Pok.VOL_STATUS2] & VolStatus2.MAGNET_RISE and me[Pok.MAGNET_RISE_TURNS] == 4


def test_gravity_ends_magnet_rise_and_blocks_it(make_pokemon, make_battle):
    """subscript_gravity_start clears it, Magnet Rise can't be picked under Gravity"""
    arr = make_battle([make_pokemon("Rattata", 20, "Run Away", ["Harden", "Magnet Rise"])],
                      [make_pokemon("Abra", 20, "Synchronize", ["Gravity"])])
    me = my_active(arr)
    engine_helper.start_magnet_rise(me)
    turn_sim(0, (MOVE, 0), arr)
    assert arr[Field.GRAVITY_TURNS] > 0
    assert me[Pok.MAGNET_RISE_TURNS] == 0 and not me[Pok.VOL_STATUS2] & VolStatus2.MAGNET_RISE
    assert engine_helper.move_blocked(me, 1, True)


def test_baton_pass_passes_magnet_rise(make_pokemon):
    """With its turns (pokeplatinum magnetRiseTurns)"""
    old = make_pokemon("Rattata", 20, "Run Away", ["Magnet Rise"]).to_np()
    new = make_pokemon("Geodude", 20, "Sturdy", ["Tackle"]).to_np()
    engine_helper.start_magnet_rise(old)
    engine_helper.magnet_rise_count(old)
    battle._pass_baton(old, new)
    assert new[Pok.VOL_STATUS2] & VolStatus2.MAGNET_RISE and new[Pok.MAGNET_RISE_TURNS] == 4


# ── 10.1 delayed effects: Future Sight, Doom Desire, Wish, Stockpile, Spit Up, Swallow ────────────

def _delayed_battle(make_pokemon, make_battle, my_moves, foe_moves=("Splash",), foe="Umbreon", foe_item=None):
    """My Abra with my_moves against a level 50 foe with foe_moves, both with a Geodude on the bench"""
    return make_battle(
        [make_pokemon("Abra", 30, "Synchronize", list(my_moves)),
         make_pokemon("Geodude", 30, "Sturdy", ["Tackle"])],
        [make_pokemon(foe, 50, "Synchronize", list(foe_moves), item=foe_item),
         make_pokemon("Geodude", 10, "Sturdy", ["Tackle"])],
    )


def _future_pending(arr, side, damage, turns=1, move=MoveName.FUTURE_SIGHT):
    arr[side] |= SideCondition.FUTURE_SIGHT
    arr[side + SIDE_FUTURE_TURNS] = turns
    arr[side + SIDE_FUTURE_DAMAGE] = damage
    arr[side + SIDE_FUTURE_MOVE] = move


def _future_cleared(arr, side):
    return not arr[side] & SideCondition.FUTURE_SIGHT and arr[side + SIDE_FUTURE_TURNS] == 0 and (
        arr[side + SIDE_FUTURE_DAMAGE] == 0 and arr[side + SIDE_FUTURE_MOVE] == 0
    )


def test_future_sight_hits_at_the_end_of_the_turn_after_next(make_pokemon, make_battle):
    """The damage is fixed when it's used and the hit is typeless, so a Dark type takes it. A second one fails
    while it waits (pokeplatinum BtlCmd_TryFutureSight, SIDE_COND_CHECK_STATE_FUTURE_SIGHT)"""
    arr = _delayed_battle(make_pokemon, make_battle, ["Future Sight"])
    foe = opp_active(arr)
    hp = foe[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    damage = arr[Field.OPP_FUTURE_DAMAGE]
    assert arr[Field.OPP_SIDE_COND] & SideCondition.FUTURE_SIGHT and arr[Field.OPP_FUTURE_TURNS] == 2
    assert arr[Field.OPP_FUTURE_MOVE] == MoveName.FUTURE_SIGHT and 0 < damage < hp
    assert foe[Pok.CURRENT_HP] == hp
    turn_sim(0, (MOVE, 0), arr)
    assert arr[Field.OPP_FUTURE_TURNS] == 1 and arr[Field.OPP_FUTURE_DAMAGE] == damage
    assert foe[Pok.CURRENT_HP] == hp
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] == hp - damage
    assert _future_cleared(arr, Field.OPP_SIDE_COND)


def test_future_sight_goes_through_protect(make_pokemon, make_battle):
    """It has no hit check when used and no protect flag"""
    arr = _delayed_battle(make_pokemon, make_battle, ["Doom Desire"], foe_moves=("Protect",))
    turn_sim(0, (MOVE, 0), arr)
    assert arr[Field.OPP_SIDE_COND] & SideCondition.FUTURE_SIGHT
    assert arr[Field.OPP_FUTURE_MOVE] == MoveName.DOOM_DESIRE


def test_future_sight_hits_the_switch_in(make_pokemon, make_battle):
    """It's stored for the side, so whoever is there when it's due takes it"""
    arr = _delayed_battle(make_pokemon, make_battle, ["Splash"])
    _future_pending(arr, Field.MY_SIDE_COND, 20)
    turn_sim(0, (SWITCH, 1), arr)
    geodude = my_active(arr)
    assert geodude[Pok.ID] == PokemonName.GEODUDE
    assert geodude[Pok.MAX_HP] - geodude[Pok.CURRENT_HP] == 20
    assert _future_cleared(arr, Field.MY_SIDE_COND)


@pytest.mark.parametrize("case", ["fainted", "semi_invulnerable"])
def test_future_sight_is_lost(make_pokemon, make_battle, case):
    """A fainted target takes nothing and a semi-invulnerable one dodges it, both use it up"""
    arr = _delayed_battle(make_pokemon, make_battle, ["Splash"])
    foe, me = opp_active(arr), my_active(arr)
    _future_pending(arr, Field.OPP_SIDE_COND, 20)
    if case == "fainted":
        foe[Pok.CURRENT_HP] = 0
    else:
        foe[Pok.VOL_STATUS] |= VolStatus.SEMI_INVULNERABLE
        foe[Pok.SEMI_INV_MOVE] = MoveName.FLY
    hp = foe[Pok.CURRENT_HP]
    battle._future_attack_hit(arr, Field.OPP_SIDE_COND, foe, me, 0, False)
    assert foe[Pok.CURRENT_HP] == hp
    assert _future_cleared(arr, Field.OPP_SIDE_COND)


def test_future_sight_no_guard_reaches_semi_invulnerable(make_pokemon, make_battle):
    """No Guard on the attacking side skips the roll and the semi-invulnerable check"""
    arr = _delayed_battle(make_pokemon, make_battle, ["Splash"])
    foe, me = opp_active(arr), my_active(arr)
    me[Pok.AB_ID] = AbilityNames.NO_GUARD
    foe[Pok.VOL_STATUS] |= VolStatus.SEMI_INVULNERABLE
    foe[Pok.SEMI_INV_MOVE] = MoveName.FLY
    _future_pending(arr, Field.OPP_SIDE_COND, 20)
    hp = foe[Pok.CURRENT_HP]
    battle._future_attack_hit(arr, Field.OPP_SIDE_COND, foe, me, 0, False)
    assert foe[Pok.CURRENT_HP] == hp - 20


def test_future_sight_hit_substitute_sash_rage(make_pokemon, make_battle):
    """A Substitute takes it, a Focus Sash at full HP holds on at 1, Rage builds"""
    arr = _delayed_battle(make_pokemon, make_battle, ["Splash"], foe_item="Focus Sash")
    foe, me = opp_active(arr), my_active(arr)
    foe[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
    foe[Pok.SUB_HP] = 30
    _future_pending(arr, Field.OPP_SIDE_COND, 20)
    hp = foe[Pok.CURRENT_HP]
    battle._future_attack_hit(arr, Field.OPP_SIDE_COND, foe, me, 0, False)
    assert foe[Pok.SUB_HP] == 10 and foe[Pok.CURRENT_HP] == hp
    foe[Pok.VOL_STATUS2] &= ~VolStatus2.SUBSTITUTE
    foe[Pok.SUB_HP] = 0
    _future_pending(arr, Field.OPP_SIDE_COND, 999)
    battle._future_attack_hit(arr, Field.OPP_SIDE_COND, foe, me, 0, False)
    assert foe[Pok.CURRENT_HP] == 1 and foe[Item.ID] == 0
    foe[Pok.CURRENT_HP] = 100
    foe[Pok.VOL_STATUS] |= VolStatus.RAGE
    _future_pending(arr, Field.OPP_SIDE_COND, 20)
    battle._future_attack_hit(arr, Field.OPP_SIDE_COND, foe, me, 0, False)
    assert foe[Pok.CURRENT_HP] == 80 and foe[Pok.ATTACK_STAT_STAGE] == 1


def test_future_sight_hit_triggers_sitrus(make_pokemon, make_battle):
    """The HP berries check right after the hit, like a move hit ([SD] futuremove)"""
    arr = _delayed_battle(make_pokemon, make_battle, ["Splash"], foe_item="Sitrus Berry")
    foe, me = opp_active(arr), my_active(arr)
    max_hp = foe[Pok.MAX_HP]
    _future_pending(arr, Field.OPP_SIDE_COND, max_hp // 2 + 5)
    battle._future_attack_hit(arr, Field.OPP_SIDE_COND, foe, me, 0, False)
    assert foe[Item.ID] == 0
    assert foe[Pok.CURRENT_HP] == max_hp - (max_hp // 2 + 5) + max_hp // 4


def test_wish_heals_at_the_end_of_the_next_turn(make_pokemon, make_battle):
    """Half of max HP at the end of the next turn, and a second Wish fails while one waits (pokeplatinum
    BtlCmd_TryWish, FIELD_COND_CHECK_STATE_WISH)"""
    arr = _delayed_battle(make_pokemon, make_battle, ["Wish"])
    me = my_active(arr)
    me[Pok.CURRENT_HP] = 1
    turn_sim(0, (MOVE, 0), arr)
    assert arr[Field.MY_SIDE_COND] & SideCondition.WISH and arr[Field.MY_WISH_TURNS] == 1
    assert me[Pok.CURRENT_HP] == 1
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.CURRENT_HP] == 1 + me[Pok.MAX_HP] // 2
    assert not arr[Field.MY_SIDE_COND] & SideCondition.WISH and arr[Field.MY_WISH_TURNS] == 0


def test_wish_heals_the_switch_in_by_its_own_max_hp(make_pokemon, make_battle):
    """It heals whoever is there when it comes true, half of that one's max HP"""
    arr = _delayed_battle(make_pokemon, make_battle, ["Splash"])
    arr[Field.MY_SIDE_COND] |= SideCondition.WISH
    arr[Field.MY_WISH_TURNS] = 1
    arr[1 * POK_LEN + Pok.CURRENT_HP] = 1
    turn_sim(0, (SWITCH, 1), arr)
    geodude = my_active(arr)
    assert geodude[Pok.CURRENT_HP] == 1 + geodude[Pok.MAX_HP] // 2


def test_heal_block_stops_wish(make_pokemon, make_battle):
    """The Wish still comes true and is gone, it just doesn't heal (pokeplatinum subscript_wish_heal)"""
    arr = _delayed_battle(make_pokemon, make_battle, ["Splash"])
    me = my_active(arr)
    me[Pok.CURRENT_HP] = 1
    _heal_blocked(me)
    arr[Field.MY_SIDE_COND] |= SideCondition.WISH
    arr[Field.MY_WISH_TURNS] = 1
    battle._wish_heal(arr, Field.MY_SIDE_COND, me)
    assert me[Pok.CURRENT_HP] == 1 and not arr[Field.MY_SIDE_COND] & SideCondition.WISH
    assert engine_helper.heal_block_stops(me, MoveName.WISH)
    assert engine_helper.heal_block_stops(me, MoveName.SWALLOW)


def test_stockpile_counts_and_remembers_the_stages_it_gave(poke):
    """Up to 3, Defense and Sp. Def +1 each, a stage already at +6 isn't remembered (pokeplatinum
    subscript_stockpile)"""
    p = poke("Swalot", 30, "Sticky Hold", ["Stockpile"])
    p[Pok.DEFENSE_STAT_STAGE] = 5
    for _ in range(4):
        engine_helper.stockpile(p)
    assert engine_helper.stockpile_count(p) == 3
    assert p[Pok.DEFENSE_STAT_STAGE] == 6 and p[Pok.SPECIAL_DEFENSE_STAT_STAGE] == 3
    p[Pok.DEFENSE_STAT_STAGE] = 0
    p[Pok.SPECIAL_DEFENSE_STAT_STAGE] = -5
    assert engine_helper.release_stockpile(p) == 3
    assert p[Pok.DEFENSE_STAT_STAGE] == -1 and p[Pok.SPECIAL_DEFENSE_STAT_STAGE] == -6
    assert p[Pok.STOCKPILE] == 0


def test_switch_out_clears_stockpile(poke):
    """The count is per stay on the field, Baton Pass doesn't pass it"""
    p = poke("Swalot", 30, "Sticky Hold", ["Stockpile"])
    engine_helper.stockpile(p)
    engine_helper.reset_switch_out(p)
    assert p[Pok.STOCKPILE] == 0


def _stockpiled(pok, count):
    for _ in range(count):
        engine_helper.stockpile(pok)


@pytest.mark.parametrize("seed", [1, 2])
def test_spit_up_power_and_no_roll(make_pokemon, make_battle, seed):
    """100 power per stockpile and no damage roll, the stockpile and its stages are gone after (pokeplatinum
    effect 0161, CalcMaxDamage)"""
    random.seed(seed)
    arr = _delayed_battle(make_pokemon, make_battle, ["Spit Up"])
    me, foe = my_active(arr), opp_active(arr)
    _stockpiled(me, 2)
    mv = move_slice(me, 0).copy()
    mv[Move.POWER] = 200
    expected = battle.calculate_damage(me, foe, mv, 0, False, 100)
    hp = foe[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert hp - foe[Pok.CURRENT_HP] == expected
    assert me[Pok.STOCKPILE] == 0 and me[Pok.DEFENSE_STAT_STAGE] == 0 and me[Pok.SPECIAL_DEFENSE_STAT_STAGE] == 0


def test_spit_up_protected_still_loses_the_stockpile(make_pokemon, make_battle):
    """The stockpile goes before the hit check"""
    arr = _delayed_battle(make_pokemon, make_battle, ["Spit Up"], foe_moves=("Protect",))
    me, foe = my_active(arr), opp_active(arr)
    _stockpiled(me, 1)
    hp = foe[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] == hp and me[Pok.STOCKPILE] == 0 and me[Pok.DEFENSE_STAT_STAGE] == 0


def test_spit_up_fails_with_nothing_stockpiled(make_pokemon, make_battle):
    """Nothing stockpiled, nothing to spit up"""
    arr = _delayed_battle(make_pokemon, make_battle, ["Spit Up"])
    foe = opp_active(arr)
    hp = foe[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.CURRENT_HP] == hp


@pytest.mark.parametrize("count, divisor", [(1, 4), (2, 2), (3, 1)])
def test_swallow_heals_by_the_stockpile(poke, count, divisor):
    """Max HP / 4, / 2 or all of it (pokeplatinum effect 0162)"""
    p = poke("Swalot", 30, "Sticky Hold", ["Swallow"])
    _stockpiled(p, count)
    p[Pok.CURRENT_HP] = 1
    engine_helper.swallow(p)
    assert p[Pok.CURRENT_HP] == min(p[Pok.MAX_HP], 1 + p[Pok.MAX_HP] // divisor)
    assert p[Pok.STOCKPILE] == 0 and p[Pok.DEFENSE_STAT_STAGE] == 0


def test_swallow_at_full_hp_still_empties_the_stockpile(poke):
    """The stockpile goes before the full HP check (pokeplatinum effect 0162, subscript_recover_hp)"""
    p = poke("Swalot", 30, "Sticky Hold", ["Swallow"])
    _stockpiled(p, 2)
    engine_helper.swallow(p)
    assert p[Pok.CURRENT_HP] == p[Pok.MAX_HP] and p[Pok.STOCKPILE] == 0 and p[Pok.DEFENSE_STAT_STAGE] == 0


def _memento_battle(make_pokemon, make_battle, foe_moves=("Splash",), foe="Machop", foe_ab="Guts"):
    """My faster Murkrow with Memento and a Geodude on the bench, against a level 30 foe"""
    arr = make_battle(
        [make_pokemon("Murkrow", 30, "Insomnia", ["Memento"]),
         make_pokemon("Geodude", 30, "Sturdy", ["Tackle"])],
        [make_pokemon(foe, 30, foe_ab, list(foe_moves))],
    )
    my_active(arr)[Pok.SPEED] = 200
    return arr


def test_memento_faints_the_user_and_drops_both(make_pokemon, make_battle):
    """Attack and Sp. Atk -2 on the target, the user faints"""
    arr = _memento_battle(make_pokemon, make_battle)
    phase, _ = turn_sim(0, (MOVE, 0), arr)
    foe = opp_active(arr)
    assert phase == BattlePhase.DEATH_END_OF_TURN and pok_slice(arr, 0)[Pok.CURRENT_HP] == 0
    assert foe[Pok.ATTACK_STAT_STAGE] == -2 and foe[Pok.SPECIAL_ATTACK_STAT_STAGE] == -2


@pytest.mark.parametrize("case", ["protect", "substitute"])
def test_memento_that_doesnt_reach_spares_the_user(make_pokemon, make_battle, case):
    """Protect or a Substitute: no drop and the user stays (Showdown selfdestruct ifHit, the gen4
    substitute's onTryPrimaryHit fails a status move)"""
    arr = _memento_battle(make_pokemon, make_battle, ("Protect",) if case == "protect" else ("Splash",))
    foe = opp_active(arr)
    if case == "protect":
        foe[Pok.SPEED] = 300
    else:
        foe[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
        foe[Pok.SUB_HP] = 10
    turn_sim(0, (MOVE, 0), arr)
    assert my_active(arr)[Pok.CURRENT_HP] > 0
    assert foe[Pok.ATTACK_STAT_STAGE] == 0 and foe[Pok.SPECIAL_ATTACK_STAT_STAGE] == 0


def test_memento_miss_spares_the_user(monkeypatch, make_pokemon, make_battle):
    """A miss doesn't reach the target either"""
    arr = _memento_battle(make_pokemon, make_battle)
    monkeypatch.setattr(battle, "calculate_hit_miss", lambda *a: MoveOutcome.MISS)
    turn_sim(0, (MOVE, 0), arr)
    assert my_active(arr)[Pok.CURRENT_HP] > 0


@pytest.mark.parametrize("case", ["both at -6", "clear body", "mist"])
def test_memento_faints_the_user_with_nothing_to_drop(make_pokemon, make_battle, case):
    """It reached the target, so the user faints even when no drop lands"""
    foe, ab = ("Tentacool", "Clear Body") if case == "clear body" else ("Machop", "Guts")
    arr = _memento_battle(make_pokemon, make_battle, foe=foe, foe_ab=ab)
    target = opp_active(arr)
    start = -6 if case == "both at -6" else 0
    target[Pok.ATTACK_STAT_STAGE] = start
    target[Pok.SPECIAL_ATTACK_STAT_STAGE] = start
    if case == "mist":
        arr[OPP_SIDE] |= SideCondition.MIST
    turn_sim(0, (MOVE, 0), arr)
    assert pok_slice(arr, 0)[Pok.CURRENT_HP] == 0
    assert target[Pok.ATTACK_STAT_STAGE] == start and target[Pok.SPECIAL_ATTACK_STAT_STAGE] == start


@pytest.mark.parametrize("hidden", [MoveName.FLY, MoveName.DIG, MoveName.DIVE, MoveName.SHADOW_FORCE])
def test_memento_reaches_every_semi_invulnerable_target(make_pokemon, make_battle, hidden):
    """pokeplatinum effect 0168 sets every SYSCTL_HIT_DURING_* flag, Shadow Force included"""
    arr = _memento_battle(make_pokemon, make_battle)
    foe = opp_active(arr)
    foe[Pok.VOL_STATUS] |= VolStatus.SEMI_INVULNERABLE
    foe[Pok.SEMI_INV_MOVE] = hidden
    assert engine_helper.semi_inv_reaches(MoveName.MEMENTO, foe)
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.ATTACK_STAT_STAGE] == -2 and pok_slice(arr, 0)[Pok.CURRENT_HP] == 0


def _healing_wish_battle(make_pokemon, make_battle, bench=2, foe_moves=("Growl",)):
    """My faster Clefairy with Healing Wish, Geodude and Machop on the bench, against a Rattata"""
    mine = [make_pokemon("Clefairy", 40, "Cute Charm", ["Healing Wish"]),
            make_pokemon("Geodude", 30, "Sturdy", ["Tackle"]),
            make_pokemon("Machop", 30, "Guts", ["Tackle"])][:bench + 1]
    return make_battle(mine, [make_pokemon("Rattata", 10, "Run Away", list(foe_moves))])


def test_my_healing_wish_heals_my_pick(make_pokemon, make_battle):
    """The user faints, the turn waits for my pick, which comes in at full HP with no status and no
    passed stages; then the slower foe's move hits it"""
    arr = _healing_wish_battle(make_pokemon, make_battle)
    clefairy, geodude = pok_slice(arr, 0), pok_slice(arr, 1)
    clefairy[Pok.ATTACK_STAT_STAGE] = 2
    geodude[Pok.CURRENT_HP] = 1
    geodude[Pok.STATUS] = Status.BURN
    phase, _ = turn_sim(0, (MOVE, 0), arr)
    assert phase == BattlePhase.BATON_PASS and arr[Field.PENDING_OPP_MOVE] == 1
    assert clefairy[Pok.CURRENT_HP] == 0 and arr[MY_SIDE] & SideCondition.HEALING_WISH
    assert battle.baton_pass_action(arr, 1) == BattlePhase.TURN_START
    assert arr[Field.MY_POK] == 1 and not arr[MY_SIDE] & SideCondition.HEALING_WISH
    assert geodude[Pok.CURRENT_HP] == geodude[Pok.MAX_HP] and geodude[Pok.STATUS] == 0
    assert geodude[Pok.ATTACK_STAT_STAGE] == -1


def test_healing_wish_fails_without_a_bench(make_pokemon, make_battle):
    """Nobody to switch in: the user stays and nothing waits (pokeplatinum TryReplaceFaintedMon)"""
    arr = _healing_wish_battle(make_pokemon, make_battle, bench=0)
    phase, _ = turn_sim(0, (MOVE, 0), arr)
    assert phase == BattlePhase.TURN_START and my_active(arr)[Pok.CURRENT_HP] > 0
    assert not arr[MY_SIDE] & SideCondition.HEALING_WISH


def test_healing_wish_heals_after_the_hazards(make_pokemon, make_battle):
    """The rocks hit first, then the heal brings it to full"""
    arr = _healing_wish_battle(make_pokemon, make_battle)
    arr[MY_SIDE] = SR
    turn_sim(0, (MOVE, 0), arr)
    battle.baton_pass_action(arr, 2)
    machop = my_active(arr)
    assert machop[Pok.CURRENT_HP] == machop[Pok.MAX_HP]


def test_healing_wish_pick_into_the_rocks_picks_again(make_pokemon, make_battle):
    """One the hazards KO is replaced before the foe moves, the next one gets the heal"""
    arr = _healing_wish_battle(make_pokemon, make_battle)
    arr[MY_SIDE] = SR
    pok_slice(arr, 1)[Pok.CURRENT_HP] = 1
    turn_sim(0, (MOVE, 0), arr)
    pp = _pp(opp_active(arr), 0)
    assert battle.baton_pass_action(arr, 1) == BattlePhase.BATON_PASS
    assert arr[Field.PENDING_OPP_MOVE] == 1 and arr[MY_SIDE] & SideCondition.HEALING_WISH
    assert _pp(opp_active(arr), 0) == pp
    assert battle.baton_pass_action(arr, 2) == BattlePhase.TURN_START
    machop = my_active(arr)
    assert machop[Pok.CURRENT_HP] == machop[Pok.MAX_HP] and machop[Pok.ATTACK_STAT_STAGE] == -1
    assert _pp(opp_active(arr), 0) == pp - 1


def test_ai_healing_wish_sends_its_pick_healed(make_pokemon, make_battle):
    """The AI picks right away with its post-KO logic, my slower move hits who it sent"""
    me = make_pokemon("Geodude", 10, "Sturdy", ["Tackle"])
    opp = [make_pokemon("Clefairy", 40, "Cute Charm", ["Healing Wish"]),
           make_pokemon("Rattata", 30, "Run Away", ["Growl"])]
    arr = make_battle([me], opp)
    rattata = pok_slice(arr, 1, opp=True)
    rattata[Pok.CURRENT_HP] = 1
    rattata[Pok.STATUS] = Status.POISON
    phase, _ = turn_sim(0, (MOVE, 0), arr)
    assert phase == BattlePhase.TURN_START and arr[Field.OPP_POK] == 1
    assert pok_slice(arr, 0, opp=True)[Pok.CURRENT_HP] == 0 and rattata[Pok.STATUS] == 0
    assert 1 < rattata[Pok.CURRENT_HP] < rattata[Pok.MAX_HP]
    assert not arr[OPP_SIDE] & SideCondition.HEALING_WISH


def test_heal_block_stops_healing_wish(make_pokemon, make_battle):
    """pokeplatinum sMovesAffectedByHealBlock lists it"""
    arr = _healing_wish_battle(make_pokemon, make_battle)
    _heal_blocked(my_active(arr))
    assert engine_helper.heal_block_stops(my_active(arr), MoveName.HEALING_WISH)


def _grudge_battle(make_pokemon, make_battle):
    """My faster Misdreavus with Grudge and Splash, a Geodude on the bench, against a Poochyena"""
    arr = make_battle(
        [make_pokemon("Misdreavus", 30, "Levitate", ["Grudge", "Splash"]),
         make_pokemon("Geodude", 30, "Sturdy", ["Tackle"])],
        [make_pokemon("Poochyena", 30, "Run Away", ["Bite", "Leer"])],
    )
    my_active(arr)[Pok.SPEED] = 200
    return arr


def test_grudge_empties_the_move_that_kos_the_user(make_pokemon, make_battle):
    """The foe's Bite loses all its PP, its other move keeps them (pokeplatinum BtlCmd_TryGrudge)"""
    arr = _grudge_battle(make_pokemon, make_battle)
    my_active(arr)[Pok.CURRENT_HP] = 1
    leer = _pp(opp_active(arr), 1)
    turn_sim(0, (MOVE, 0), arr)
    assert pok_slice(arr, 0)[Pok.CURRENT_HP] == 0
    assert _pp(opp_active(arr), 0) == 0 and _pp(opp_active(arr), 1) == leer


def test_grudge_ends_when_the_user_moves_again(make_pokemon, make_battle):
    """Gone at the start of the user's next move, like Destiny Bond (CHECK_STATUS_START)"""
    arr = _grudge_battle(make_pokemon, make_battle)
    turn_sim(1, (MOVE, 0), arr)
    assert my_active(arr)[Pok.VOL_STATUS2] & VolStatus2.GRUDGE
    my_active(arr)[Pok.CURRENT_HP] = 1
    pp = _pp(opp_active(arr), 0)
    turn_sim(0, (MOVE, 1), arr)
    assert pok_slice(arr, 0)[Pok.CURRENT_HP] == 0 and _pp(opp_active(arr), 0) == pp - 1


@pytest.mark.parametrize("case", ["attacker fainted", "struggle", "user alive"])
def test_grudge_needs_a_ko_and_a_standing_attacker(poke, case):
    """No PP lost when the attacker went down too, for Struggle, or without a KO"""
    atk = poke("Machop", 30, "Guts", ["Tackle"])
    defn = poke("Misdreavus", 30, "Levitate", ["Grudge"])
    defn[Pok.VOL_STATUS2] |= VolStatus2.GRUDGE
    defn[Pok.CURRENT_HP] = 0 if case != "user alive" else 1
    if case == "attacker fainted":
        atk[Pok.CURRENT_HP] = 0
    pp = _pp(atk, 0)
    battle._grudge(atk, defn, 10 if case == "struggle" else 0)
    assert _pp(atk, 0) == pp



def _u_turn_battle(make_pokemon, make_battle, bench=True, foe_moves=("Tackle",), foe="Rattata",
                   foe_ability="Run Away", foe_bench=False):
    """My faster Scyther with U-turn, a Geodude on the bench, against a bulky foe"""
    mine = [make_pokemon("Scyther", 30, "Swarm", ["U-turn", "Tackle"])]
    if bench:
        mine.append(make_pokemon("Geodude", 30, "Sturdy", ["Tackle"]))
    opp = [make_pokemon(foe, 30, foe_ability, list(foe_moves))]
    if foe_bench:
        opp.append(make_pokemon("Machop", 30, "Guts", ["Tackle"]))
    arr = make_battle(mine, opp)
    my_active(arr)[Pok.SPEED] = 200
    opp_active(arr)[Pok.SPEED] = 10
    opp_active(arr)[Pok.MAX_HP] = opp_active(arr)[Pok.CURRENT_HP] = 500
    return arr


def test_my_u_turn_pauses_for_a_plain_switch(make_pokemon, make_battle):
    """The hit lands, the turn waits for my pick, nothing is passed; the slower foe hits who came in"""
    arr = _u_turn_battle(make_pokemon, make_battle)
    scyther = my_active(arr)
    scyther[Pok.ATTACK_STAT_STAGE] = 2
    scyther[Pok.VOL_STATUS] = VolStatus.FOCUS_ENERGY
    phase, _ = turn_sim(0, (MOVE, 0), arr)
    assert phase == BattlePhase.BATON_PASS and arr[Field.PENDING_OPP_MOVE] == 1
    assert opp_active(arr)[Pok.CURRENT_HP] < 500 and scyther[Pok.VOL_STATUS2] & VolStatus2.U_TURN
    pp = _pp(opp_active(arr), 0)
    assert battle.baton_pass_action(arr, 1) == BattlePhase.TURN_START
    geodude = my_active(arr)
    assert arr[Field.MY_POK] == 1 and not scyther[Pok.VOL_STATUS2] & VolStatus2.U_TURN
    assert geodude[Pok.ATTACK_STAT_STAGE] == 0 and not geodude[Pok.VOL_STATUS] & VolStatus.FOCUS_ENERGY
    assert not geodude[Pok.VOL_STATUS2] & VolStatus2.U_TURN
    assert _pp(opp_active(arr), 0) == pp - 1 and geodude[Pok.CURRENT_HP] < geodude[Pok.MAX_HP]


def test_slower_u_turn_has_nothing_pending(make_pokemon, make_battle):
    """The foe already moved, the pick just finishes the turn"""
    arr = _u_turn_battle(make_pokemon, make_battle)
    my_active(arr)[Pok.SPEED] = 1
    turn_sim(0, (MOVE, 0), arr)
    assert arr[Field.PHASE] == BattlePhase.BATON_PASS and arr[Field.PENDING_OPP_MOVE] == 0
    assert battle.baton_pass_action(arr, 1) == BattlePhase.TURN_START and arr[Field.MY_POK] == 1


@pytest.mark.parametrize("case", ["no bench", "protect", "rough skin"])
def test_u_turn_stays_in(make_pokemon, make_battle, case):
    """No switch with an empty bench, after Protect, or when Rough Skin KOs the user (pokeplatinum
    subscript_attack_then_switch_out)"""
    arr = _u_turn_battle(
        make_pokemon, make_battle, bench=case != "no bench",
        foe_moves=("Protect",) if case == "protect" else ("Tackle",),
        foe="Carvanha" if case == "rough skin" else "Rattata",
        foe_ability="Rough Skin" if case == "rough skin" else "Run Away",
    )
    if case == "rough skin":
        my_active(arr)[Pok.CURRENT_HP] = 1
    phase, _ = turn_sim(0, (MOVE, 0), arr)
    assert phase != BattlePhase.BATON_PASS and arr[Field.MY_POK] == 0
    assert not pok_slice(arr, 0)[Pok.VOL_STATUS2] & VolStatus2.U_TURN
    if case == "rough skin":
        assert phase == BattlePhase.DEATH_END_OF_TURN


def test_u_turn_into_a_substitute_still_switches(make_pokemon, make_battle):
    """An on-hit side effect, not a CHECK_SUBSTITUTE one (pokeplatinum effect 0228)"""
    arr = _u_turn_battle(make_pokemon, make_battle)
    foe = opp_active(arr)
    foe[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
    foe[Pok.SUB_HP] = 400
    turn_sim(0, (MOVE, 0), arr)
    assert arr[Field.PHASE] == BattlePhase.BATON_PASS and foe[Pok.CURRENT_HP] == 500
    assert foe[Pok.SUB_HP] < 400


@pytest.mark.parametrize("foe_bench", [True, False])
def test_u_turn_ko(make_pokemon, make_battle, foe_bench):
    """A KO still switches while the foe has a bench, not on its last Pokemon (CheckBlackOut)"""
    arr = _u_turn_battle(make_pokemon, make_battle, foe_bench=foe_bench)
    opp_active(arr)[Pok.CURRENT_HP] = 1
    phase, _ = turn_sim(0, (MOVE, 0), arr)
    assert (phase == BattlePhase.BATON_PASS) == foe_bench
    if foe_bench:
        battle.baton_pass_action(arr, 1)
        assert arr[Field.MY_POK] == 1 and arr[Field.OPP_POK] == 1


def test_pursuit_hits_my_u_turn_on_its_way_out(make_pokemon, make_battle):
    """The slower Pursuit hits at double power before the switch and uses up the foe's turn"""
    arr = _u_turn_battle(make_pokemon, make_battle, foe="Poochyena", foe_moves=("Pursuit",))
    scyther = my_active(arr)
    pp = _pp(opp_active(arr), 0)
    phase, _ = turn_sim(0, (MOVE, 0), arr)
    assert phase == BattlePhase.BATON_PASS and arr[Field.PENDING_OPP_MOVE] == 0
    assert scyther[Pok.CURRENT_HP] < scyther[Pok.MAX_HP] and _pp(opp_active(arr), 0) == pp - 1
    battle.baton_pass_action(arr, 1)
    geodude = my_active(arr)
    assert geodude[Pok.CURRENT_HP] == geodude[Pok.MAX_HP] and _pp(opp_active(arr), 0) == pp - 1


def test_pursuit_ko_stops_my_u_turn(make_pokemon, make_battle):
    """KOed on the way out: no pick mid-turn, the usual replacement at the end of the turn"""
    arr = _u_turn_battle(make_pokemon, make_battle, foe="Poochyena", foe_moves=("Pursuit",))
    my_active(arr)[Pok.CURRENT_HP] = 1
    phase, _ = turn_sim(0, (MOVE, 0), arr)
    assert phase == BattlePhase.DEATH_END_OF_TURN
    assert not pok_slice(arr, 0)[Pok.VOL_STATUS2] & VolStatus2.U_TURN


def test_flinch_from_my_u_turn_reaches_the_pending_move(make_pokemon, make_battle):
    """A King's Rock flinch carries over the pick in Field.PENDING_OPP_MOVE"""
    arr = _u_turn_battle(make_pokemon, make_battle)
    turn_sim(0, (MOVE, 0), arr)
    arr[Field.PENDING_OPP_MOVE] += battle.PENDING_FLINCH
    pp = _pp(opp_active(arr), 0)
    battle.baton_pass_action(arr, 1)
    geodude = my_active(arr)
    assert _pp(opp_active(arr), 0) == pp and geodude[Pok.CURRENT_HP] == geodude[Pok.MAX_HP]


def _ai_u_turn_battle(make_pokemon, make_battle, my_moves=("Tackle",)):
    """The AI's faster Scyther with U-turn and a Machop on its bench, against my bulky Rattata"""
    arr = make_battle(
        [make_pokemon("Rattata", 30, "Run Away", list(my_moves))],
        [make_pokemon("Scyther", 30, "Swarm", ["U-turn"]),
         make_pokemon("Machop", 30, "Guts", ["Tackle"])],
    )
    opp_active(arr)[Pok.SPEED] = 200
    my_active(arr)[Pok.SPEED] = 10
    my_active(arr)[Pok.MAX_HP] = my_active(arr)[Pok.CURRENT_HP] = 500
    return arr


def test_ai_u_turn_switches_right_away(make_pokemon, make_battle):
    """The AI picks with its post-KO logic, my slower move hits who it sent"""
    arr = _ai_u_turn_battle(make_pokemon, make_battle)
    scyther = opp_active(arr)
    scyther[Pok.ATTACK_STAT_STAGE] = 2
    phase, _ = turn_sim(0, (MOVE, 0), arr)
    machop = opp_active(arr)
    assert phase == BattlePhase.TURN_START and arr[Field.OPP_POK] == 1
    assert my_active(arr)[Pok.CURRENT_HP] < 500 and machop[Pok.CURRENT_HP] < machop[Pok.MAX_HP]
    assert machop[Pok.ATTACK_STAT_STAGE] == 0 and scyther[Pok.ATTACK_STAT_STAGE] == 0
    assert not scyther[Pok.VOL_STATUS2] & VolStatus2.U_TURN


def test_my_pursuit_hits_the_ai_u_turn(make_pokemon, make_battle):
    """My slower Pursuit hits the Scyther before it leaves and is my turn"""
    arr = _ai_u_turn_battle(make_pokemon, make_battle, my_moves=("Pursuit",))
    scyther = opp_active(arr)
    pp = _pp(my_active(arr), 0)
    turn_sim(0, (MOVE, 0), arr)
    machop = opp_active(arr)
    assert arr[Field.OPP_POK] == 1 and scyther[Pok.CURRENT_HP] < scyther[Pok.MAX_HP]
    assert machop[Pok.CURRENT_HP] == machop[Pok.MAX_HP] and _pp(my_active(arr), 0) == pp - 1


def test_ai_u_turn_after_my_baton_pass(make_pokemon, make_battle):
    """The AI's slower U-turn waits for my Baton Pass pick, then it switches too"""
    arr = make_battle(
        [make_pokemon("Rattata", 30, "Run Away", ["Baton Pass"]),
         make_pokemon("Geodude", 30, "Sturdy", ["Tackle"])],
        [make_pokemon("Scyther", 30, "Swarm", ["U-turn"]),
         make_pokemon("Machop", 30, "Guts", ["Tackle"])],
    )
    my_active(arr)[Pok.SPEED] = 200
    opp_active(arr)[Pok.SPEED] = 10
    turn_sim(0, (MOVE, 0), arr)
    assert battle.baton_pass_action(arr, 1) == BattlePhase.TURN_START
    assert arr[Field.MY_POK] == 1 and arr[Field.OPP_POK] == 1


# ── Restriction and trapping ─────────────────────────────────────────────────

def _restrict_battle(make_pokemon, make_battle, my_moves, foe_moves, foe_ability="Run Away",
                     my_bench=False, foe_bench=False, fast=True):
    """My Murkrow against a Rattata, both bulky, mine faster unless fast is False"""
    mine = [make_pokemon("Murkrow", 30, "Insomnia", list(my_moves))]
    if my_bench:
        mine.append(make_pokemon("Geodude", 30, "Sturdy", ["Tackle"]))
    opp = [make_pokemon("Rattata", 30, foe_ability, list(foe_moves))]
    if foe_bench:
        opp.append(make_pokemon("Machop", 30, "Guts", ["Tackle"]))
    arr = make_battle(mine, opp)
    my_active(arr)[Pok.SPEED] = 200 if fast else 10
    opp_active(arr)[Pok.SPEED] = 10 if fast else 200
    for p in (my_active(arr), opp_active(arr)):
        p[Pok.MAX_HP] = p[Pok.CURRENT_HP] = 500
    return arr


def test_torment_blocks_the_last_move(make_pokemon, make_battle):
    """Only the slot of the move used last can't be picked, and it follows the last move
    (pokeplatinum BattleSystem_CheckInvalidMoves, CHECK_INVALID_TORMENTED)"""
    arr = _restrict_battle(make_pokemon, make_battle, ["Torment", "Splash"], ["Tackle", "Growl"])
    foe = opp_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.VOL_STATUS2] & VolStatus2.TORMENT
    assert engine_helper.move_blocked(foe, 0) and not engine_helper.move_blocked(foe, 1)
    turn_sim(1, (MOVE, 1), arr)
    assert not engine_helper.move_blocked(foe, 0) and engine_helper.move_blocked(foe, 1)


def test_torment_blocks_nothing_after_a_disrupted_turn(poke):
    """A turn the move didn't run leaves no last move (pokeplatinum movePrevByBattler)"""
    p = poke("Rattata", 30, "Run Away", ["Tackle", "Growl"])
    p[Pok.VOL_STATUS2] = VolStatus2.TORMENT
    assert not any(engine_helper.move_blocked(p, i) for i in range(2))


def test_torment_fails_while_up_and_goes_through_a_substitute(make_pokemon, make_battle):
    """subscript_torment_start has no Substitute check, only the target already under it"""
    arr = _restrict_battle(make_pokemon, make_battle, ["Torment"], ["Splash"])
    me, foe = my_active(arr), opp_active(arr)
    foe[Pok.VOL_STATUS2] = VolStatus2.SUBSTITUTE
    foe[Pok.SUB_HP] = 50
    assert not engine_helper.status_move_fails(move_slice(me, 0), me, foe)
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.VOL_STATUS2] & VolStatus2.TORMENT and foe[Pok.SUB_HP] == 50
    assert engine_helper.status_move_fails(move_slice(me, 0), me, foe)


def test_baton_pass_drops_torment_and_imprison(make_pokemon, make_battle):
    """Neither is in VOLATILE_CONDITION_BATON_PASSED or MOVE_EFFECT_BATON_PASSED"""
    arr = _restrict_battle(make_pokemon, make_battle, ["Splash"], ["Splash"], my_bench=True)
    me = my_active(arr)
    me[Pok.VOL_STATUS2] = VolStatus2.TORMENT | VolStatus2.IMPRISON
    new = pok_slice(arr, 1)
    battle._pass_baton(me, new)
    assert not new[Pok.VOL_STATUS2] & (VolStatus2.TORMENT | VolStatus2.IMPRISON)


def test_imprison_seals_a_move_picked_before_it(make_pokemon, make_battle):
    """My faster Imprison stops the foe's Tackle that turn, which costs no PP (pokeplatinum
    CHECK_STATUS_STATE_IMPRISON runs before DECREMENT_PP), and from then on only the move I don't
    know can be picked"""
    arr = _restrict_battle(make_pokemon, make_battle, ["Imprison", "Tackle"], ["Tackle", "Growl"])
    me, foe = my_active(arr), opp_active(arr)
    pp = _pp(foe, 0)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.VOL_STATUS2] & VolStatus2.IMPRISON
    assert me[Pok.CURRENT_HP] == 500 and _pp(foe, 0) == pp and foe[Pok.LAST_MOVE_ID] == 0
    assert engine_helper.imprisoned(me, MoveName.TACKLE)
    assert not engine_helper.imprisoned(me, MoveName.GROWL)


@pytest.mark.parametrize("foe_moves, up", [(["Growl"], False), (["Tackle"], True)])
def test_imprison_fails(make_pokemon, make_battle, foe_moves, up):
    """With no move in common, or while already up (pokeplatinum BtlCmd_TryImprison)"""
    arr = _restrict_battle(make_pokemon, make_battle, ["Imprison", "Tackle"], foe_moves)
    me, foe = my_active(arr), opp_active(arr)
    if up:
        me[Pok.VOL_STATUS2] = VolStatus2.IMPRISON
    assert engine_helper.status_move_fails(move_slice(me, 0), me, foe)


def test_imprison_pays_pressure(make_pokemon, make_battle):
    """One PP more against a Pressure foe, though it aims at the user (DecrementPP)"""
    arr = _restrict_battle(make_pokemon, make_battle, ["Imprison", "Tackle"], ["Tackle"],
                           foe_ability="Pressure")
    pp = _pp(my_active(arr), 0)
    turn_sim(0, (MOVE, 0), arr)
    assert _pp(my_active(arr), 0) == pp - 2


def test_imprison_ends_when_the_user_leaves(make_pokemon, make_battle):
    """The seal is the user's own flag, a switch-out clears it"""
    arr = _restrict_battle(make_pokemon, make_battle, ["Imprison", "Tackle"], ["Tackle"],
                           my_bench=True)
    me = my_active(arr)
    me[Pok.VOL_STATUS2] = VolStatus2.IMPRISON
    turn_sim(0, (SWITCH, 1), arr)
    assert not me[Pok.VOL_STATUS2] & VolStatus2.IMPRISON


def test_sleep_talk_skips_sealed_and_tormented_moves(poke):
    """TrySleepTalk runs CheckInvalidMoves without the PP check, so Imprison and Torment count"""
    p = poke("Rattata", 30, "Run Away", ["Sleep Talk", "Tackle", "Growl", "Bite"])
    foe = poke("Murkrow", 30, "Insomnia", ["Imprison", "Tackle"])
    p[Pok.STATUS] = Status.SLEEP
    p[Pok.SLEEP_COUNTER] = 3
    foe[Pok.VOL_STATUS2] = VolStatus2.IMPRISON
    p[Pok.VOL_STATUS2] = VolStatus2.TORMENT
    p[Pok.LAST_MOVE_ID] = MoveName.GROWL
    random.seed(0)
    assert {engine_helper.sleep_talk_move(p, foe, False) for _ in range(30)} == {MoveName.BITE}


@pytest.mark.parametrize("pp, left", [(20, 16), (3, 0)])
def test_spite_takes_four_pp_from_the_last_move(make_pokemon, make_battle, pp, left):
    """4 PP, or what's left, from the move the foe used before my slower Spite (BtlCmd_TrySpite).
    Tackle pays its own 1 first"""
    arr = _restrict_battle(make_pokemon, make_battle, ["Spite"], ["Tackle", "Growl"], fast=False)
    foe = opp_active(arr)
    move_slice(foe, 0)[Move.PP] = pp + 1
    growl = _pp(foe, 1)
    turn_sim(0, (MOVE, 0), arr)
    assert _pp(foe, 0) == left and _pp(foe, 1) == growl


def test_spite_fails(poke):
    """No last move, a last move it doesn't know or one with no PP left"""
    me = poke("Murkrow", 30, "Insomnia", ["Spite"])
    foe = poke("Rattata", 30, "Run Away", ["Tackle"])
    spite = move_slice(me, 0)
    assert engine_helper.status_move_fails(spite, me, foe)
    foe[Pok.LAST_MOVE_ID] = MoveName.GROWL
    assert engine_helper.status_move_fails(spite, me, foe)
    foe[Pok.LAST_MOVE_ID] = MoveName.TACKLE
    assert not engine_helper.status_move_fails(spite, me, foe)
    move_slice(foe, 0)[Move.PP] = 0
    assert engine_helper.status_move_fails(spite, me, foe)


@pytest.mark.parametrize("move", ["Mean Look", "Block", "Spider Web"])
def test_mean_look_traps(make_pokemon, make_battle, move):
    """The target can't switch, a Shed Shell holder still can (Battler_IsTrapped)"""
    arr = _restrict_battle(make_pokemon, make_battle, [move], ["Splash"])
    me, foe = my_active(arr), opp_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.VOL_STATUS2] & VolStatus2.MEAN_LOOK and engine_helper.is_trapped(foe, me)
    foe[Item.HOLD_EFFECT] = HoldEffect.SWITCH
    assert not engine_helper.is_trapped(foe, me)


@pytest.mark.parametrize("case", ["trapped", "substitute"])
def test_mean_look_fails(make_pokemon, make_battle, case):
    """On a target already trapped by it, or behind a Substitute (subscript_mean_look)"""
    arr = _restrict_battle(make_pokemon, make_battle, ["Mean Look"], ["Splash"])
    me, foe = my_active(arr), opp_active(arr)
    if case == "trapped":
        foe[Pok.VOL_STATUS2] = VolStatus2.MEAN_LOOK
        assert engine_helper.status_move_fails(move_slice(me, 0), me, foe)
    else:
        foe[Pok.VOL_STATUS2] = VolStatus2.SUBSTITUTE
        foe[Pok.SUB_HP] = 50
        turn_sim(0, (MOVE, 0), arr)
        assert not foe[Pok.VOL_STATUS2] & VolStatus2.MEAN_LOOK


@pytest.mark.parametrize("baton, freed", [(False, True), (True, False)])
def test_the_trapper_leaving_frees_the_target(make_pokemon, make_battle, baton, freed):
    """A switch-out frees the one it trapped, a Baton Pass doesn't (UpdateAfterSwitch)"""
    arr = _restrict_battle(make_pokemon, make_battle, ["Mean Look"], ["Splash"], my_bench=True)
    me, foe = my_active(arr), opp_active(arr)
    foe[Pok.VOL_STATUS2] = VolStatus2.MEAN_LOOK
    battle._switch_my_side(arr, me, foe, 1, baton)
    assert (not foe[Pok.VOL_STATUS2] & VolStatus2.MEAN_LOOK) == freed


def test_the_ai_trapper_leaving_frees_me(make_pokemon, make_battle):
    """The same on the AI's side"""
    arr = _restrict_battle(make_pokemon, make_battle, ["Splash"], ["Mean Look"], foe_bench=True)
    me, foe = my_active(arr), opp_active(arr)
    me[Pok.VOL_STATUS2] = VolStatus2.MEAN_LOOK
    battle._switch_opp_side(arr, foe, me, 1)
    assert not me[Pok.VOL_STATUS2] & VolStatus2.MEAN_LOOK


def test_baton_pass_keeps_the_trapped_one_trapped(make_pokemon, make_battle):
    """VOLATILE_CONDITION_BATON_PASSED has Mean Look"""
    arr = _restrict_battle(make_pokemon, make_battle, ["Splash"], ["Splash"], my_bench=True)
    me = my_active(arr)
    me[Pok.VOL_STATUS2] = VolStatus2.MEAN_LOOK
    new = pok_slice(arr, 1)
    battle._pass_baton(me, new)
    assert new[Pok.VOL_STATUS2] & VolStatus2.MEAN_LOOK


def test_a_move_spite_emptied_fails(make_pokemon, make_battle):
    """The foe picked Tackle with 1 PP, my faster Spite took it: no PP left for the move, nothing
    is paid and no last move stays (pokeplatinum DecrementPP, MOVE_STATUS_NO_PP)"""
    arr = _restrict_battle(make_pokemon, make_battle, ["Spite"], ["Tackle", "Growl"])
    me, foe = my_active(arr), opp_active(arr)
    foe[Pok.LAST_MOVE_ID] = MoveName.TACKLE
    move_slice(foe, 0)[Move.PP] = 1
    turn_sim(0, (MOVE, 0), arr)
    assert _pp(foe, 0) == 0 and foe[Pok.LAST_MOVE_ID] == 0 and me[Pok.CURRENT_HP] == 500


# ── 11.2 Accuracy locks and protection: Lock-On, Mind Reader, Miracle Eye, Detect ─────────────

def _miss_rolls(monkeypatch):
    """Every accuracy roll misses unless something skips it"""
    monkeypatch.setattr(random, "randint", lambda a, b: b)


@pytest.mark.parametrize("move", ["Lock-On", "Mind Reader"])
def test_lock_on_lasts_through_the_next_turn(make_pokemon, make_battle, move):
    """Set to 2, counted down at the end of each turn (pokeplatinum LOCK_ON_INITIAL_DURATION,
    MON_COND_CHECK_STATE_LOCK_ON; Showdown duration 2)"""
    arr = _restrict_battle(make_pokemon, make_battle, [move, "Splash"], ["Splash"])
    me = my_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.VOL_STATUS2] & VolStatus2.LOCK_ON and me[Pok.LOCK_ON_TURNS] == 1
    turn_sim(0, (MOVE, 1), arr)
    assert not me[Pok.VOL_STATUS2] & VolStatus2.LOCK_ON and me[Pok.LOCK_ON_TURNS] == 0


def test_lock_on_skips_the_accuracy_roll_and_reaches_fly(monkeypatch, make_pokemon, make_battle):
    """Like No Guard: past the evasion and a semi-invulnerable target, not past Protect
    (pokeplatinum CheckMoveHitOverrides, MON_IS_LOCKED_ONTO)"""
    arr = _restrict_battle(make_pokemon, make_battle, ["Tackle"], ["Splash"])
    me, foe = my_active(arr), opp_active(arr)
    tackle = move_slice(me, 0)
    _miss_rolls(monkeypatch)
    foe[Pok.EVASION_STAT_STAGE] = 6
    assert engine_helper.calculate_hit_miss(tackle, me, foe, 0) == MoveOutcome.MISS
    me[Pok.VOL_STATUS2] |= VolStatus2.LOCK_ON
    assert engine_helper.calculate_hit_miss(tackle, me, foe, 0) == MoveOutcome.HIT
    foe[Pok.VOL_STATUS] |= VolStatus.SEMI_INVULNERABLE
    foe[Pok.SEMI_INV_MOVE] = MoveName.FLY
    assert engine_helper.calculate_hit_miss(tackle, me, foe, 0) == MoveOutcome.HIT
    foe[Pok.VOL_STATUS] = VolStatus.PROTECT
    assert engine_helper.calculate_hit_miss(tackle, me, foe, 0) == MoveOutcome.PROTECTED


@pytest.mark.parametrize("foe_level, ability, outcome", [
    (30, "Run Away", MoveOutcome.HIT),
    (31, "Run Away", MoveOutcome.INVULNERABLE),
    (30, "Sturdy", MoveOutcome.INVULNERABLE),
])
def test_lock_on_ohko_keeps_the_level_rule(monkeypatch, make_pokemon, make_battle, foe_level, ability,
                                           outcome):
    """A locked OHKO move hits from the same level up, Sturdy still stops it (BtlCmd_TryOHKOMove)"""
    arr = make_battle([make_pokemon("Krabby", 30, "Hyper Cutter", ["Guillotine"])],
                      [make_pokemon("Rattata", foe_level, ability, ["Splash"])])
    me, foe = my_active(arr), opp_active(arr)
    _miss_rolls(monkeypatch)
    me[Pok.VOL_STATUS2] |= VolStatus2.LOCK_ON
    assert engine_helper.calculate_hit_miss(move_slice(me, 0), me, foe, 0) == outcome


@pytest.mark.parametrize("move", ["Lock-On", "Mind Reader"])
def test_lock_on_fails_while_the_lock_is_up(make_pokemon, make_battle, move):
    """Showdown lockon onTryHit: the user already has one, the turns don't restart"""
    arr = _restrict_battle(make_pokemon, make_battle, [move], ["Splash"])
    me, foe = my_active(arr), opp_active(arr)
    assert not engine_helper.status_move_fails(move_slice(me, 0), me, foe)
    me[Pok.VOL_STATUS2] |= VolStatus2.LOCK_ON
    me[Pok.LOCK_ON_TURNS] = 1
    assert engine_helper.status_move_fails(move_slice(me, 0), me, foe)
    turn_sim(0, (MOVE, 0), arr)
    assert not me[Pok.VOL_STATUS2] & VolStatus2.LOCK_ON and me[Pok.LOCK_ON_TURNS] == 0


def test_lock_on_fails_into_a_substitute(make_pokemon, make_battle):
    """No bypass_sub (pokeplatinum subscript_lock_on CheckSubstitute)"""
    arr = _restrict_battle(make_pokemon, make_battle, ["Lock-On"], ["Splash"])
    me, foe = my_active(arr), opp_active(arr)
    foe[Pok.VOL_STATUS2] = VolStatus2.SUBSTITUTE
    foe[Pok.SUB_HP] = 50
    turn_sim(0, (MOVE, 0), arr)
    assert not me[Pok.VOL_STATUS2] & VolStatus2.LOCK_ON


@pytest.mark.parametrize("baton, kept", [(False, False), (True, True)])
def test_the_target_leaving_ends_the_lock(make_pokemon, make_battle, baton, kept):
    """The target's switch-out ends it, its Baton Pass keeps it with its turns
    (pokeplatinum BattleSystem_UpdateAfterSwitch, MOVE_EFFECT_BATON_PASSED)"""
    arr = _restrict_battle(make_pokemon, make_battle, ["Splash"], ["Splash"], foe_bench=True)
    me, foe = my_active(arr), opp_active(arr)
    me[Pok.VOL_STATUS2] |= VolStatus2.LOCK_ON
    me[Pok.LOCK_ON_TURNS] = 1
    battle._switch_opp_side(arr, foe, me, 1, baton)
    assert bool(me[Pok.VOL_STATUS2] & VolStatus2.LOCK_ON) == kept
    assert me[Pok.LOCK_ON_TURNS] == 1


def test_my_target_leaving_ends_the_ai_lock(make_pokemon, make_battle):
    """The same on my side"""
    arr = _restrict_battle(make_pokemon, make_battle, ["Splash"], ["Splash"], my_bench=True)
    me, foe = my_active(arr), opp_active(arr)
    foe[Pok.VOL_STATUS2] |= VolStatus2.LOCK_ON
    battle._switch_my_side(arr, me, foe, 1)
    assert not foe[Pok.VOL_STATUS2] & VolStatus2.LOCK_ON


def test_baton_pass_restarts_the_lock(make_pokemon, make_battle):
    """The user's Baton Pass hands the lock over with its turns back at 2
    (pokeplatinum LOCK_ON_INITIAL_DURATION); a switch-out drops it"""
    arr = _restrict_battle(make_pokemon, make_battle, ["Splash"], ["Splash"], my_bench=True)
    me = my_active(arr)
    me[Pok.VOL_STATUS2] |= VolStatus2.LOCK_ON
    me[Pok.LOCK_ON_TURNS] = 1
    new = pok_slice(arr, 1)
    battle._pass_baton(me, new)
    assert new[Pok.VOL_STATUS2] & VolStatus2.LOCK_ON and new[Pok.LOCK_ON_TURNS] == 2
    engine_helper.reset_switch_out(me)
    assert not me[Pok.VOL_STATUS2] & VolStatus2.LOCK_ON and me[Pok.LOCK_ON_TURNS] == 0


def test_lock_on_makes_future_sight_land(make_pokemon, make_battle):
    """The attacking side's active's lock reaches a semi-invulnerable target (CheckMoveHitOverrides)"""
    arr = _delayed_battle(make_pokemon, make_battle, ["Splash"])
    me, foe = my_active(arr), opp_active(arr)
    foe[Pok.VOL_STATUS] |= VolStatus.SEMI_INVULNERABLE
    foe[Pok.SEMI_INV_MOVE] = MoveName.FLY
    future = battle.MOVE_TABLE[MoveName.FUTURE_SIGHT]
    assert not engine_helper.future_hit_lands(future, me, foe, 0)
    me[Pok.VOL_STATUS2] |= VolStatus2.LOCK_ON
    assert engine_helper.future_hit_lands(future, me, foe, 0)


def test_a_same_turn_lock_on_reaches_future_sight(monkeypatch, make_pokemon, make_battle):
    """Future Sight lands after the countdown (CheckSideConditions after CheckMonConditions), so a
    Lock-On used that turn still counts"""
    arr = _delayed_battle(make_pokemon, make_battle, ["Lock-On"])
    me, foe = my_active(arr), opp_active(arr)
    me[Pok.SPEED] = 200
    foe[Pok.SPEED] = 10
    _future_pending(arr, Field.OPP_SIDE_COND, 20)
    foe[Pok.EVASION_STAT_STAGE] = 6
    hp = foe[Pok.CURRENT_HP]
    _miss_rolls(monkeypatch)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.VOL_STATUS2] & VolStatus2.LOCK_ON
    assert foe[Pok.CURRENT_HP] == hp - 20


def test_miracle_eye_lets_psychic_hit_dark(monkeypatch, make_pokemon, make_battle):
    """pokeplatinum battle_lib MOVE_EFFECT_MIRACLE_EYE drops the Dark immunity to Psychic"""
    arr = _delayed_battle(make_pokemon, make_battle, ["Miracle Eye", "Confusion"])
    me, foe = my_active(arr), opp_active(arr)
    me[Pok.SPEED] = 200
    confusion = move_slice(me, 1)
    assert engine_helper.calculate_hit_miss(confusion, me, foe, 0) == MoveOutcome.INVULNERABLE
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.VOL_STATUS2] & VolStatus2.MIRACLE_EYE
    monkeypatch.setattr(random, "randint", lambda a, b: a)
    assert engine_helper.calculate_hit_miss(confusion, me, foe, 0) == MoveOutcome.HIT


def test_miracle_eye_ignores_raised_evasion(make_pokemon, make_battle):
    """MON_IS_IDENTIFIED covers Foresight and Miracle Eye: raised evasion counts as 0"""
    arr = _restrict_battle(make_pokemon, make_battle, ["Tackle"], ["Splash"])
    me, foe = my_active(arr), opp_active(arr)
    tackle = move_slice(me, 0)
    foe[Pok.EVASION_STAT_STAGE] = 6
    assert engine_helper.move_accuracy(tackle, me, foe, 100, 0) < 100
    foe[Pok.VOL_STATUS2] |= VolStatus2.MIRACLE_EYE
    assert engine_helper.move_accuracy(tackle, me, foe, 100, 0) == 100


@pytest.mark.parametrize("vol, vol2", [(VolStatus.FORESIGHT, 0), (0, VolStatus2.MIRACLE_EYE)])
def test_miracle_eye_fails_on_an_identified_target(make_pokemon, make_battle, vol, vol2):
    """Showdown miracleeye onTryHit (Foresight) and its volatile already there"""
    arr = _restrict_battle(make_pokemon, make_battle, ["Miracle Eye"], ["Splash"])
    me, foe = my_active(arr), opp_active(arr)
    assert not engine_helper.status_move_fails(move_slice(me, 0), me, foe)
    foe[Pok.VOL_STATUS] |= vol
    foe[Pok.VOL_STATUS2] |= vol2
    assert engine_helper.status_move_fails(move_slice(me, 0), me, foe)


def test_miracle_eye_goes_through_a_substitute_and_ends_on_switch_out(make_pokemon, make_battle):
    """bypass_sub (pokeplatinum subscript_miracle_eye has no Substitute check); not Baton Passed"""
    arr = _restrict_battle(make_pokemon, make_battle, ["Miracle Eye"], ["Splash"], foe_bench=True)
    foe = opp_active(arr)
    foe[Pok.VOL_STATUS2] = VolStatus2.SUBSTITUTE
    foe[Pok.SUB_HP] = 50
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.VOL_STATUS2] & VolStatus2.MIRACLE_EYE
    new = pok_slice(arr, 7)
    battle._pass_baton(foe, new)
    assert not new[Pok.VOL_STATUS2] & VolStatus2.MIRACLE_EYE
    engine_helper.reset_switch_out(foe)
    assert not foe[Pok.VOL_STATUS2] & VolStatus2.MIRACLE_EYE


def test_detect_blocks_like_protect(make_pokemon, make_battle):
    """Detect is Protect's effect (pokeplatinum effect 111)"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Detect"], ["Tackle"], my_level=5, opp_level=50)
    me = my_active(arr)
    hp = me[Pok.CURRENT_HP]
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.CURRENT_HP] == hp
    assert not me[Pok.VOL_STATUS] & VolStatus.PROTECT and me[Pok.PROTECT_COUNT] == 1


def test_detect_shares_protects_count(monkeypatch, make_pokemon, make_battle):
    """A Detect after a Protect rolls the 1/2 chance, a failure resets the count (TryProtection)"""
    arr = _phase3_battle(make_pokemon, make_battle, ["Protect", "Detect"], ["Splash"])
    me = my_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.PROTECT_COUNT] == 1
    monkeypatch.setattr(random, "getrandbits", lambda n: 1)
    turn_sim(0, (MOVE, 1), arr)
    assert me[Pok.PROTECT_COUNT] == 0


# ── 11.3 Reflection: Magic Coat, Snatch ───────────────────────────────────────────────────────

def _run_slot(arr, mine, slot=0, slot_num=1, is_last=False):
    """One side's move through _execute_move_slot, so the turn flags can be read mid-turn"""
    me, foe = my_active(arr), opp_active(arr)
    atk, defn = (me, foe) if mine else (foe, me)
    battle._execute_move_slot(
        atk, defn, move_slice(atk, slot), mine, slot if mine else 0, 0 if mine else slot,
        False, slot_num, is_last, arr, 0
    )


def _taker_then_user(arr, taker_mine=True):
    """The taker's first move, then the other side's first move as the last slot of the turn"""
    _run_slot(arr, taker_mine)
    _run_slot(arr, not taker_mine, slot_num=2, is_last=True)


@pytest.mark.parametrize("move, bit", [
    ("Magic Coat", VolStatus2.MAGIC_COAT), ("Snatch", VolStatus2.SNATCH),
])
def test_magic_coat_and_snatch_fail_when_moving_last(make_pokemon, make_battle, move, bit):
    """pokeplatinum BtlCmd_TrySetMagicCoat / BtlCmd_TrySnatch: nothing acts after the user"""
    arr = _restrict_battle(make_pokemon, make_battle, [move], ["Splash"])
    me = my_active(arr)
    _run_slot(arr, True, is_last=True)
    assert not me[Pok.VOL_STATUS2] & bit
    _run_slot(arr, True)
    assert me[Pok.VOL_STATUS2] & bit
    battle._finish_turn(arr)
    assert not me[Pok.VOL_STATUS2] & bit


def test_magic_coat_sends_the_move_back_once(monkeypatch, make_pokemon, make_battle):
    """pokeplatinum BattleControllerPlayer_MoveStolen: the user pays its PP and the move counts as
    its last one, the coat is used up and nothing is left for Mirror Move"""
    monkeypatch.setattr(random, "randint", lambda a, b: a)
    arr = _restrict_battle(make_pokemon, make_battle, ["Magic Coat"], ["Thunder Wave"])
    me, foe = my_active(arr), opp_active(arr)
    pp = move_slice(foe, 0)[Move.PP]
    _taker_then_user(arr)
    assert foe[Pok.STATUS] == Status.PARALYSIS and me[Pok.STATUS] == 0
    assert move_slice(foe, 0)[Move.PP] == pp - 1
    assert foe[Pok.LAST_MOVE_ID] == MoveName.THUNDER_WAVE
    assert me[Pok.LAST_MOVE_ID] == MoveName.MAGIC_COAT
    assert not me[Pok.VOL_STATUS2] & VolStatus2.MAGIC_COAT
    assert foe[Pok.MIRROR_MOVE] == 0 and me[Pok.MIRROR_MOVE] == 0
    # The coat is gone: a second one this turn lands
    foe[Pok.STATUS] = 0
    _run_slot(arr, False, slot_num=2, is_last=True)
    assert me[Pok.STATUS] == Status.PARALYSIS


@pytest.mark.parametrize("move", ["Taunt", "Roar", "Foresight", "Stealth Rock", "Tackle"])
def test_magic_coat_leaves_other_moves_alone(make_pokemon, make_battle, move):
    """Gen IV's list (Showdown gen4 flags): these aren't reflected yet, the coat stays up"""
    arr = _restrict_battle(make_pokemon, make_battle, ["Magic Coat"], [move])
    assert not move_slice(opp_active(arr), 0)[Flags.REFLECTABLE]
    _taker_then_user(arr)
    assert my_active(arr)[Pok.VOL_STATUS2] & VolStatus2.MAGIC_COAT


def test_a_bounced_move_stops_at_the_users_substitute(monkeypatch, make_pokemon, make_battle):
    """The bounced move goes through the checks again with the coat user as the attacker"""
    monkeypatch.setattr(random, "randint", lambda a, b: a)
    arr = _restrict_battle(make_pokemon, make_battle, ["Magic Coat"], ["Thunder Wave"])
    me, foe = my_active(arr), opp_active(arr)
    foe[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
    foe[Pok.SUB_HP] = 50
    _taker_then_user(arr)
    assert foe[Pok.STATUS] == 0 and me[Pok.STATUS] == 0
    assert not me[Pok.VOL_STATUS2] & VolStatus2.MAGIC_COAT


def test_magic_coat_in_a_full_turn(monkeypatch, make_pokemon, make_battle):
    """Priority +4: the slower side's coat is up before the move comes"""
    monkeypatch.setattr(random, "randint", lambda a, b: a)
    arr = _restrict_battle(make_pokemon, make_battle, ["Magic Coat"], ["Thunder Wave"], fast=False)
    me, foe = my_active(arr), opp_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.STATUS] == Status.PARALYSIS and me[Pok.STATUS] == 0
    assert not me[Pok.VOL_STATUS2] & VolStatus2.MAGIC_COAT


def test_snatch_takes_the_boost(make_pokemon, make_battle):
    """The move runs with the Snatch user as its user, the original user only pays the PP"""
    arr = _restrict_battle(make_pokemon, make_battle, ["Snatch"], ["Swords Dance"])
    me, foe = my_active(arr), opp_active(arr)
    pp = move_slice(foe, 0)[Move.PP]
    _taker_then_user(arr)
    assert me[Pok.ATTACK_STAT_STAGE] == 2 and foe[Pok.ATTACK_STAT_STAGE] == 0
    assert move_slice(foe, 0)[Move.PP] == pp - 1
    assert foe[Pok.LAST_MOVE_ID] == MoveName.SWORDS_DANCE
    assert not me[Pok.VOL_STATUS2] & VolStatus2.SNATCH
    # Used up: the next one stays with its user
    _run_slot(arr, False, slot_num=2, is_last=True)
    assert foe[Pok.ATTACK_STAT_STAGE] == 2


def test_snatch_takes_recover_and_substitute(make_pokemon, make_battle):
    """The healing and the Substitute's cost land on the Snatch user"""
    arr = _restrict_battle(make_pokemon, make_battle, ["Snatch"], ["Recover", "Substitute"])
    me, foe = my_active(arr), opp_active(arr)
    me[Pok.CURRENT_HP] = foe[Pok.CURRENT_HP] = 100
    _taker_then_user(arr)
    assert me[Pok.CURRENT_HP] == 350 and foe[Pok.CURRENT_HP] == 100
    _run_slot(arr, True)
    _run_slot(arr, False, slot=1, slot_num=2, is_last=True)
    assert me[Pok.VOL_STATUS2] & VolStatus2.SUBSTITUTE and me[Pok.CURRENT_HP] == 225
    assert not foe[Pok.VOL_STATUS2] & VolStatus2.SUBSTITUTE


def test_snatch_leaves_other_moves_alone(make_pokemon, make_battle):
    """Only the moves flagged for it, the flag stays up for a later one"""
    arr = _restrict_battle(make_pokemon, make_battle, ["Snatch"], ["Splash"])
    _taker_then_user(arr)
    assert my_active(arr)[Pok.VOL_STATUS2] & VolStatus2.SNATCH


def test_a_snatched_heal_fails_under_heal_block(make_pokemon, make_battle):
    """The move is taken, then Heal Block stops it for its new user"""
    arr = _restrict_battle(make_pokemon, make_battle, ["Snatch"], ["Recover"])
    me, foe = my_active(arr), opp_active(arr)
    me[Pok.CURRENT_HP] = foe[Pok.CURRENT_HP] = 100
    me[Pok.VOL_STATUS] |= VolStatus.HEAL_BLOCK
    me[Pok.HEAL_BLOCK_TURNS] = 3
    _taker_then_user(arr)
    assert me[Pok.CURRENT_HP] == 100 and foe[Pok.CURRENT_HP] == 100
    assert not me[Pok.VOL_STATUS2] & VolStatus2.SNATCH


@pytest.mark.parametrize("taker_mine", [True, False])
def test_the_users_pressure_costs_the_taker_a_pp(make_pokemon, make_battle, taker_mine):
    """pokeplatinum BattleSystem_DecPPForPressure in MoveStolen. The foe's extra PP is counted in
    Field.OPP_MOVE_RAN"""
    mine, theirs = (["Snatch"], ["Swords Dance"]) if taker_mine else (["Swords Dance"], ["Snatch"])
    arr = _restrict_battle(make_pokemon, make_battle, mine, theirs)
    me, foe = my_active(arr), opp_active(arr)
    taker, user = (me, foe) if taker_mine else (foe, me)
    user[Pok.AB_ID] = AbilityNames.PRESSURE
    pp = move_slice(taker, 0)[Move.PP]
    arr[Field.OPP_MOVE_RAN] = 0
    _taker_then_user(arr, taker_mine)
    assert move_slice(taker, 0)[Move.PP] == pp - 2
    assert taker[Pok.ATTACK_STAT_STAGE] == 2
    if not taker_mine:
        assert arr[Field.OPP_MOVE_RAN] == 1 + 16 * 2


# ── 12.1 type and ability changes: Conversion, Conversion 2, Camouflage, Color Change, Role Play,
#    Skill Swap, Gastro Acid ──────────────────────────────────────────────────────────────────────

def _change_battle(make_pokemon, make_battle, my_moves, foe_moves=("Splash",), my_ab="Download",
                   foe=("Geodude", "Sturdy"), mine="Porygon"):
    """My level 30 Pokemon with my_moves against a level 30 foe, both with a Rattata on the bench"""
    return make_battle(
        [make_pokemon(mine, 30, my_ab, list(my_moves)),
         make_pokemon("Rattata", 30, "Run Away", ["Tackle"])],
        [make_pokemon(foe[0], 30, foe[1], list(foe_moves)),
         make_pokemon("Rattata", 30, "Run Away", ["Tackle"])],
    )


def test_conversion_takes_a_move_type_until_switch_out(make_pokemon, make_battle):
    """Tackle is its own type, so only Thunderbolt's is left. Switch-out gives Normal back"""
    arr = _change_battle(make_pokemon, make_battle, ["Conversion", "Thunderbolt", "Tackle"])
    me = my_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert (me[Pok.TYPE1], me[Pok.TYPE2]) == (Types.ELECTRIC, 0)
    engine_helper.reset_switch_out(me)
    assert (me[Pok.TYPE1], me[Pok.TYPE2]) == (Types.NORMAL, 0)


@pytest.mark.parametrize("moves, ability, fails", [
    (["Conversion", "Tackle"], "Download", True),
    (["Conversion", "Curse"], "Download", True),          # [SD] gen4 skips Curse
    (["Conversion", "Hidden Power"], "Download", True),   # Normal in the move data
    (["Conversion", "Ember"], "Download", False),
    (["Conversion", "Ember"], "Multitype", True),
])
def test_conversion_fails(poke, moves, ability, fails):
    """No move of another type, or Multitype (pokeplatinum BtlCmd_TryConversion)"""
    p = poke("Porygon", 30, ability, moves)
    assert engine_helper.conversion_fails(p) == fails


def test_conversion_picks_each_slot_evenly(poke):
    """Two Fire moves and one Water move: Fire two times in three"""
    random.seed(3)
    seen = []
    for _ in range(300):
        p = poke("Porygon", 30, "Download", ["Conversion", "Ember", "Flamethrower", "Surf"])
        engine_helper.conversion(p)
        seen.append(int(p[Pok.TYPE1]))
    assert set(seen) == {Types.FIRE, Types.WATER}
    assert 170 < seen.count(Types.FIRE) < 230


@pytest.mark.parametrize("last_move, attack_type", [
    (MoveName.EMBER, Types.FIRE), (MoveName.STRUGGLE, Types.NORMAL), (MoveName.EARTHQUAKE, Types.GROUND),
])
def test_conversion_2_resists_the_foes_last_move(poke, last_move, attack_type):
    """A type that resists or is immune to it, never one the user has ([SD] gen4 conversion2)"""
    foe = poke("Geodude", 30, "Sturdy", ["Ember", "Tackle"])
    foe[Pok.LAST_MOVE_ID] = last_move
    random.seed(5)
    seen = set()
    for _ in range(200):
        p = poke("Porygon", 30, "Download", ["Conversion 2"])
        assert not engine_helper.conversion2_fails(p, foe, 0)
        engine_helper.conversion2(p, foe, 0)
        assert p[Pok.TYPE2] == 0
        seen.add(int(p[Pok.TYPE1]))
    assert Types.NORMAL not in seen and len(seen) > 1
    for p_type in seen:
        eff, den = engine_helper.get_type_effectiveness(attack_type, p_type, 0)
        assert eff < den


def test_conversion_2_fails_without_a_last_move(poke):
    """And with Multitype"""
    foe = poke("Geodude", 30, "Sturdy", ["Ember"])
    p = poke("Porygon", 30, "Download", ["Conversion 2"])
    assert engine_helper.conversion2_fails(p, foe, 0)
    foe[Pok.LAST_MOVE_ID] = MoveName.EMBER
    assert not engine_helper.conversion2_fails(p, foe, 0)
    assert engine_helper.conversion2_fails(poke("Porygon", 30, "Multitype", ["Conversion 2"]), foe, 0)


def test_conversion_2_reads_hidden_power_from_the_slot(poke):
    """The type it hits with, not the move data's Normal"""
    foe = poke("Geodude", 30, "Sturdy", ["Hidden Power"])
    move_slice(foe, 0)[Move.TYPE] = Types.DRAGON
    foe[Pok.LAST_MOVE_ID] = MoveName.HIDDEN_POWER
    assert engine_helper._conversion2_attack_type(foe, 0) == Types.DRAGON


@pytest.mark.parametrize("terrain, p_type", [
    (Terrain.PLAIN, Types.GROUND), (Terrain.GRASS, Types.GRASS), (Terrain.CAVE, Types.ROCK),
    (Terrain.SNOW, Types.ICE), (Terrain.WATER, Types.WATER), (Terrain.BRIDGE, Types.FLYING),
])
def test_camouflage_takes_the_terrain_type(make_pokemon, make_battle, terrain, p_type):
    """pokeplatinum sTerrainCamouflageType, and the flag the AI's Basic check reads"""
    arr = _change_battle(make_pokemon, make_battle, ["Camouflage"])
    arr[Field.TERRAIN] = terrain
    me = my_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert (me[Pok.TYPE1], me[Pok.TYPE2]) == (p_type, 0)
    assert me[Pok.VOL_STATUS2] & VolStatus2.CAMOUFLAGE
    assert engine_helper.camouflage_fails(me, terrain)
    engine_helper.reset_switch_out(me)
    assert me[Pok.TYPE1] == Types.NORMAL and not me[Pok.VOL_STATUS2] & VolStatus2.CAMOUFLAGE


def test_camouflage_fails_on_its_own_type(make_pokemon, make_battle):
    """A Normal type in a building: no change, no flag. Multitype fails too"""
    arr = _change_battle(make_pokemon, make_battle, ["Camouflage"])
    arr[Field.TERRAIN] = Terrain.BUILDING
    me = my_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.TYPE1] == Types.NORMAL and not me[Pok.VOL_STATUS2] & VolStatus2.CAMOUFLAGE
    me[Pok.AB_ID] = AbilityNames.MULTITYPE
    assert engine_helper.camouflage_fails(me, Terrain.CAVE)


def test_color_change_takes_the_hits_type(make_pokemon, make_battle):
    """Both types become the move's and the ability is named"""
    arr = _change_battle(make_pokemon, make_battle, ["Splash"], ["Ember"], my_ab="Color Change",
                         mine="Kecleon")
    me = my_active(arr)
    random.seed(0)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.CURRENT_HP] < me[Pok.MAX_HP]
    assert (me[Pok.TYPE1], me[Pok.TYPE2]) == (Types.FIRE, 0) and me[Pok.AB_KNOWN]
    engine_helper.reset_switch_out(me)
    assert me[Pok.TYPE1] == Types.NORMAL


@pytest.mark.parametrize("case", ["same type", "struggle", "fainted", "no damage", "other ability"])
def test_color_change_does_nothing(poke, case):
    """A type it already has, Struggle, a KO, a hit that dealt nothing, or another ability"""
    foe = poke("Geodude", 30, "Sturdy", ["Tackle", "Ember"])
    me = poke("Kecleon", 30, "Run Away" if case == "other ability" else "Color Change", ["Splash"])
    move = STRUGGLE.copy() if case == "struggle" else move_slice(foe, 0 if case == "same type" else 1)
    if case == "fainted":
        me[Pok.CURRENT_HP] = 0
    engine_helper.on_hit_abilities(foe, me, move, 0 if case == "no damage" else 5, 0)
    assert (me[Pok.TYPE1], me[Pok.TYPE2]) == (Types.NORMAL, 0) and not me[Pok.AB_KNOWN]


def test_color_change_not_through_a_substitute(make_pokemon, make_battle):
    """The hit never reached the holder (pokeplatinum physicalDamageTaken)"""
    arr = _change_battle(make_pokemon, make_battle, ["Splash"], ["Ember"], my_ab="Color Change",
                         mine="Kecleon")
    me = my_active(arr)
    me[Pok.VOL_STATUS2] = VolStatus2.SUBSTITUTE
    me[Pok.SUB_HP] = 500
    random.seed(0)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.TYPE1] == Types.NORMAL


def test_role_play_copies_the_ability_until_switch_out(make_pokemon, make_battle):
    """The whole ability block, and its own comes back"""
    arr = _change_battle(make_pokemon, make_battle, ["Role Play"])
    me, foe = my_active(arr), opp_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert (me[Pok.AB_ID:Pok.AB_BREAKABLE + 1] == foe[Pok.AB_ID:Pok.AB_BREAKABLE + 1]).all()
    assert me[Pok.BASE_AB_ID] == AbilityNames.DOWNLOAD and foe[Pok.BASE_AB_ID] == 0
    engine_helper.reset_switch_out(me)
    assert me[Pok.AB_ID] == AbilityNames.DOWNLOAD and me[Pok.BASE_AB_ID] == 0


@pytest.mark.parametrize("user_ab, target_ab, fails", [
    ("Download", "Sturdy", False), ("Download", "Wonder Guard", True), ("Download", "Multitype", True),
    ("Multitype", "Sturdy", True), ("Sturdy", "Sturdy", True), ("Wonder Guard", "Sturdy", False),
])
def test_role_play_fails(poke, user_ab, target_ab, fails):
    """pokeplatinum subscript_copy_ability, plus Showdown's same ability"""
    me = poke("Porygon", 30, user_ab, ["Role Play"])
    foe = poke("Geodude", 30, target_ab, ["Tackle"])
    assert engine_helper.status_move_fails(move_slice(me, 0), me, foe) == fails


def test_role_play_goes_through_protect_and_a_substitute(make_pokemon, make_battle):
    """No protect flag and it bypasses the Substitute"""
    arr = _change_battle(make_pokemon, make_battle, ["Role Play"], ["Protect"])
    me, foe = my_active(arr), opp_active(arr)
    foe[Pok.VOL_STATUS2] = VolStatus2.SUBSTITUTE
    foe[Pok.SUB_HP] = 50
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.AB_ID] == AbilityNames.STURDY


def test_a_copied_intimidate_fires(make_pokemon, make_battle):
    """The gained ability starts like on a switch-in ([SD] setAbility)"""
    arr = _change_battle(make_pokemon, make_battle, ["Role Play"], foe=("Gyarados", "Intimidate"))
    me, foe = my_active(arr), opp_active(arr)
    foe[Pok.ATTACK_STAT_STAGE] = 0
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.AB_ID] == AbilityNames.INTIMIDATE and foe[Pok.ATTACK_STAT_STAGE] == -1


def test_skill_swap_trades_the_abilities(make_pokemon, make_battle):
    """Each side keeps its own as the base and gets it back on switch-out. The AI knows mine"""
    arr = _change_battle(make_pokemon, make_battle, ["Skill Swap"])
    me, foe = my_active(arr), opp_active(arr)
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.AB_ID] == AbilityNames.STURDY and foe[Pok.AB_ID] == AbilityNames.DOWNLOAD
    assert me[Pok.BASE_AB_ID] == AbilityNames.DOWNLOAD and foe[Pok.BASE_AB_ID] == AbilityNames.STURDY
    assert arr[Field.AI_KNOWS] & Enemy_AI_Knows.ABILITY
    engine_helper.reset_switch_out(foe)
    assert foe[Pok.AB_ID] == AbilityNames.STURDY and me[Pok.AB_ID] == AbilityNames.STURDY


@pytest.mark.parametrize("user_ab, target_ab, user_item, target_item, fails", [
    ("Download", "Sturdy", None, None, False),
    ("Wonder Guard", "Sturdy", None, None, True), ("Download", "Wonder Guard", None, None, True),
    ("Multitype", "Sturdy", None, None, True), ("Download", "Multitype", None, None, True),
    ("Download", "Sturdy", "Griseous Orb", None, True), ("Download", "Sturdy", None, "Griseous Orb", True),
    ("Sturdy", "Sturdy", None, None, True),
])
def test_skill_swap_fails(make_pokemon, user_ab, target_ab, user_item, target_item, fails):
    """pokeplatinum subscript_exchange_abilities, plus Showdown's same ability"""
    me = make_pokemon("Porygon", 30, user_ab, ["Skill Swap"], item=user_item).to_np()
    foe = make_pokemon("Geodude", 30, target_ab, ["Tackle"], item=target_item).to_np()
    assert engine_helper.status_move_fails(move_slice(me, 0), me, foe) == fails


def test_skill_swap_is_stopped_by_protect(make_pokemon, make_battle):
    """It has the protect flag, unlike Role Play"""
    arr = _change_battle(make_pokemon, make_battle, ["Skill Swap"], ["Protect"])
    turn_sim(0, (MOVE, 0), arr)
    assert my_active(arr)[Pok.AB_ID] == AbilityNames.DOWNLOAD


def test_gastro_acid_suppresses_until_switch_out(make_pokemon, make_battle):
    """No ability block, the real one kept aside, and it fails a second time"""
    arr = _change_battle(make_pokemon, make_battle, ["Gastro Acid"])
    me, foe = my_active(arr), opp_active(arr)
    random.seed(0)
    turn_sim(0, (MOVE, 0), arr)
    assert not foe[Pok.AB_ID:Pok.AB_BREAKABLE + 1].any()
    assert foe[Pok.VOL_STATUS2] & VolStatus2.GASTRO_ACID
    assert foe[Pok.SUPPRESSED_AB_ID] == AbilityNames.STURDY and foe[Pok.BASE_AB_ID] == AbilityNames.STURDY
    assert engine_helper.status_move_fails(move_slice(me, 0), me, foe)
    engine_helper.reset_switch_out(foe)
    assert foe[Pok.AB_ID] == AbilityNames.STURDY and foe[Pok.SUPPRESSED_AB_ID] == 0
    assert not foe[Pok.VOL_STATUS2] & VolStatus2.GASTRO_ACID


def test_gastro_acid_lets_earthquake_reach_a_levitator(make_pokemon, make_battle):
    """A suppressed Levitate is no ability at all"""
    arr = _change_battle(make_pokemon, make_battle, ["Gastro Acid", "Earthquake"],
                         foe=("Gastly", "Levitate"))
    foe = opp_active(arr)
    random.seed(0)
    turn_sim(0, (MOVE, 1), arr)
    assert foe[Pok.CURRENT_HP] == foe[Pok.MAX_HP]
    turn_sim(0, (MOVE, 0), arr)
    turn_sim(0, (MOVE, 1), arr)
    assert foe[Pok.CURRENT_HP] < foe[Pok.MAX_HP]


def test_gastro_acid_fails_on_multitype_and_a_substitute(make_pokemon, make_battle):
    """pokeplatinum subscript_suppress_target_ability"""
    arr = _change_battle(make_pokemon, make_battle, ["Gastro Acid"])
    me, foe = my_active(arr), opp_active(arr)
    foe[Pok.VOL_STATUS2] = VolStatus2.SUBSTITUTE
    foe[Pok.SUB_HP] = 50
    random.seed(0)
    turn_sim(0, (MOVE, 0), arr)
    assert foe[Pok.AB_ID] == AbilityNames.STURDY
    foe[Pok.AB_ID] = AbilityNames.MULTITYPE
    assert engine_helper.status_move_fails(move_slice(me, 0), me, foe)


def test_baton_pass_passes_gastro_acid(make_pokemon):
    """The receiver's ability is suppressed, a Multitype one isn't (pokeplatinum Battler_Ability)"""
    old = make_pokemon("Rattata", 20, "Run Away", ["Baton Pass"]).to_np()
    engine_helper.suppress_ability(old)
    new = make_pokemon("Geodude", 20, "Sturdy", ["Tackle"]).to_np()
    battle._pass_baton(old, new)
    assert new[Pok.AB_ID] == 0 and new[Pok.SUPPRESSED_AB_ID] == AbilityNames.STURDY
    assert new[Pok.VOL_STATUS2] & VolStatus2.GASTRO_ACID
    arceus = make_pokemon("Geodude", 20, "Multitype", ["Tackle"]).to_np()
    battle._pass_baton(old, arceus)
    assert arceus[Pok.AB_ID] == AbilityNames.MULTITYPE
    assert not arceus[Pok.VOL_STATUS2] & VolStatus2.GASTRO_ACID


def test_a_suppressed_ability_can_still_be_copied_and_traded(poke):
    """Role Play and Skill Swap read the ability under the Gastro Acid, which stays on its Pokemon
    and suppresses what it got (pokeplatinum battleMons.ability against Battler_Ability)"""
    me = poke("Porygon", 30, "Download", ["Role Play"])
    foe = poke("Geodude", 30, "Sturdy", ["Tackle"])
    engine_helper.suppress_ability(foe)
    assert not engine_helper.role_play_fails(me, foe)
    engine_helper.set_ability(me, engine_helper.raw_ability(foe))
    assert me[Pok.AB_ID] == AbilityNames.STURDY
    other = poke("Rattata", 30, "Run Away", ["Skill Swap"])
    assert not engine_helper.skill_swap_fails(other, foe)
    engine_helper.set_ability(foe, AbilityNames.RUN_AWAY)
    assert foe[Pok.AB_ID] == 0 and foe[Pok.SUPPRESSED_AB_ID] == AbilityNames.RUN_AWAY
    engine_helper.reset_switch_out(foe)
    assert foe[Pok.AB_ID] == AbilityNames.STURDY


def test_worry_seed_under_gastro_acid(poke):
    """Insomnia goes under the suppression, so a sleeper stays asleep"""
    foe = poke("Machop", 30, "Guts", ["Tackle"])
    engine_helper.suppress_ability(foe)
    foe[Pok.STATUS] = Status.SLEEP
    foe[Pok.SLEEP_COUNTER] = 3
    assert engine_helper.worry_seed(foe)
    assert foe[Pok.AB_ID] == 0 and foe[Pok.SUPPRESSED_AB_ID] == AbilityNames.INSOMNIA
    assert foe[Pok.STATUS] == Status.SLEEP


def test_trace_copies_a_suppressed_ability(poke):
    """pokeplatinum ChooseTraceTarget reads battleMons.ability"""
    me = poke("Porygon", 30, "Trace", ["Tackle"])
    foe = poke("Geodude", 30, "Sturdy", ["Tackle"])
    engine_helper.suppress_ability(foe)
    assert engine_helper.trace(me, foe) and me[Pok.AB_ID] == AbilityNames.STURDY


def test_forecast_only_changes_castform(make_pokemon, make_battle):
    """A Pokemon that got Forecast from Skill Swap keeps its types (pokeplatinum SPECIES_CASTFORM)"""
    arr = make_battle([make_pokemon("Rattata", 30, "Forecast", ["Splash"])],
                      [make_pokemon("Onix", 30, "Rock Head", ["Harden"])])
    arr[Field.WEATHER] = Weather.HAIL
    battle.forecast_actives(arr)
    assert my_active(arr)[Pok.TYPE1] == Types.NORMAL


# ── 12.2 copying: Mimic, Sketch, Transform ──────────────────────────────────────────────────────

def test_mimic_copies_the_last_move_until_switch_out(make_pokemon, make_battle):
    """Up to 5 PP, the AI no longer knows the slot, and switch-out brings Mimic back with its PP"""
    arr = _change_battle(make_pokemon, make_battle, ["Tackle", "Mimic"])
    me, foe = my_active(arr), opp_active(arr)
    foe[Pok.LAST_MOVE_ID] = MoveName.EMBER
    turn_sim(0, (MOVE, 1), arr)
    slot = move_slice(me, 1)
    assert slot[Move.ID] == MoveName.EMBER and slot[Move.PP] == 5
    assert slot[Move.TYPE] == Types.FIRE and slot[Move.POWER] > 0
    assert not arr[Field.AI_KNOWS] & _ENEMY_AI_KNOWS_MOVE2
    assert me[Pok.ORIG_MOVE1 + 1] == MoveName.MIMIC * engine_helper.ORIG_MOVE_STEP + 9
    engine_helper.reset_switch_out(me)
    assert slot[Move.ID] == MoveName.MIMIC and slot[Move.PP] == 9
    assert me[Pok.ORIG_MOVE1 + 1] == 0


@pytest.mark.parametrize("move, last, fails", [
    ("Mimic", MoveName.EMBER, False), ("Mimic", 0, True), ("Mimic", MoveName.TACKLE, True),
    ("Mimic", MoveName.METRONOME, True), ("Mimic", MoveName.STRUGGLE, True),
    ("Mimic", MoveName.SKETCH, True), ("Mimic", MoveName.MIMIC, True), ("Mimic", MoveName.CHATTER, True),
    ("Mimic", MoveName.TRANSFORM, False),
    ("Sketch", MoveName.EMBER, False), ("Sketch", 0, True), ("Sketch", MoveName.TACKLE, True),
    ("Sketch", MoveName.STRUGGLE, True), ("Sketch", MoveName.CHATTER, True),
    ("Sketch", MoveName.METRONOME, False),
])
def test_mimic_and_sketch_fail(poke, move, last, fails):
    """No last move, one the user knows, or one of pokeplatinum's forbidden moves"""
    me = poke("Porygon", 30, "Download", [move, "Tackle"])
    foe = poke("Geodude", 30, "Sturdy", ["Tackle"])
    foe[Pok.LAST_MOVE_ID] = last
    assert engine_helper.status_move_fails(move_slice(me, 0), me, foe) == fails


@pytest.mark.parametrize("move", ["Mimic", "Sketch"])
def test_mimic_and_sketch_fail_transformed_or_into_a_substitute(poke, move):
    """pokeplatinum BtlCmd_TryMimic, BtlCmd_TrySketch and subscript_sketch"""
    foe = poke("Geodude", 30, "Sturdy", ["Tackle"])
    foe[Pok.LAST_MOVE_ID] = MoveName.EMBER
    me = poke("Porygon", 30, "Download", [move])
    move_id = move_slice(me, 0)[Move.ID]
    assert engine_helper.copy_slot(me, foe, move_id) == 0
    me[Pok.VOL_STATUS2] |= VolStatus2.TRANSFORM
    assert engine_helper.copy_slot(me, foe, move_id) == -1
    me[Pok.VOL_STATUS2] = 0
    foe[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
    assert engine_helper.copy_slot(me, foe, move_id) == -1


def test_a_mimicked_hidden_power_is_the_users(poke):
    """Its type and power come from the user, not from the move data"""
    me = poke("Porygon", 30, "Download", ["Mimic"])
    foe = poke("Geodude", 30, "Sturdy", ["Hidden Power"])
    foe[Pok.LAST_MOVE_ID] = MoveName.HIDDEN_POWER
    me[Pok.HIDDEN_POWER_TYPE], me[Pok.HIDDEN_POWER_POWER] = Types.ICE, 61
    engine_helper.mimic(me, foe)
    slot = move_slice(me, 0)
    assert (slot[Move.TYPE], slot[Move.POWER]) == (Types.ICE, 61)


def test_mimic_ends_a_disable_on_its_slot_and_resets_last_resort(poke):
    """The disabled move is gone, and a copied Last Resort starts its count over"""
    me = poke("Porygon", 30, "Download", ["Tackle", "Mimic"])
    foe = poke("Geodude", 30, "Sturdy", ["Tackle"])
    foe[Pok.LAST_MOVE_ID] = MoveName.LAST_RESORT
    me[Pok.VOL_STATUS] |= VolStatus.DISABLE
    me[Pok.DISABLE_TURNS] = 3 * 4 + 1
    me[Pok.LAST_RESORT] = 3
    assert engine_helper.mimic(me, foe) == 1
    assert not me[Pok.VOL_STATUS] & VolStatus.DISABLE and me[Pok.DISABLE_TURNS] == 0
    assert me[Pok.LAST_RESORT] == 0


def test_mimic_frees_a_choice_lock(make_pokemon, make_battle):
    """The locked move left the moveset (pokeplatinum BattleSystem_CheckInvalidMoves)"""
    arr = make_battle(
        [make_pokemon("Porygon", 30, "Download", ["Tackle", "Mimic"], item="Choice Scarf")],
        [make_pokemon("Geodude", 30, "Sturdy", ["Splash"])],
    )
    me, foe = my_active(arr), opp_active(arr)
    foe[Pok.LAST_MOVE_ID] = MoveName.EMBER
    turn_sim(0, (MOVE, 1), arr)
    assert move_slice(me, 1)[Move.ID] == MoveName.EMBER and me[Pok.CHOICE_LOCK] == 0
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.CHOICE_LOCK] == 1


def test_sketch_keeps_the_move_for_good(make_pokemon, make_battle):
    """Full PP, no backup, and it survives the switch-out"""
    arr = _change_battle(make_pokemon, make_battle, ["Sketch"], mine="Smeargle", my_ab="Own Tempo")
    me, foe = my_active(arr), opp_active(arr)
    foe[Pok.LAST_MOVE_ID] = MoveName.EMBER
    turn_sim(0, (MOVE, 0), arr)
    slot = move_slice(me, 0)
    full = engine_helper.MOVE_TABLE[MoveName.EMBER, Move.PP]
    assert slot[Move.ID] == MoveName.EMBER and slot[Move.PP] == full
    assert me[Pok.ORIG_MOVE1] == 0
    engine_helper.reset_switch_out(me)
    assert slot[Move.ID] == MoveName.EMBER and slot[Move.PP] == full


def test_transform_copies_the_target_until_switch_out(make_pokemon, make_battle):
    """Species, stats but HP, stages, weight, types, ability and moves at up to 5 PP. Level, HP and
    item stay, and switch-out gives everything back"""
    arr = make_battle(
        [make_pokemon("Ditto", 30, "Limber", ["Transform"], item="Oran Berry"),
         make_pokemon("Rattata", 30, "Run Away", ["Tackle"])],
        [make_pokemon("Geodude", 40, "Sturdy", ["Splash", "Rock Throw", "Fire Blast"]),
         make_pokemon("Rattata", 30, "Run Away", ["Tackle"])],
    )
    me, foe = my_active(arr), opp_active(arr)
    before = me.copy()
    foe[Pok.DEFENSE_STAT_STAGE] = 2
    arr[Field.AI_KNOWS] |= _ENEMY_AI_KNOWS_MOVE2
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.VOL_STATUS2] & VolStatus2.TRANSFORM
    assert me[Pok.ID] == PokemonName.GEODUDE and me[Pok.ORIG_ID] == PokemonName.DITTO
    assert (me[Pok.ATTACK:Pok.SPEED + 1] == foe[Pok.ATTACK:Pok.SPEED + 1]).all()
    assert me[Pok.DEFENSE_STAT_STAGE] == 2
    assert me[Pok.WEIGHT] == foe[Pok.WEIGHT]
    assert (me[Pok.TYPE1], me[Pok.TYPE2]) == (foe[Pok.TYPE1], foe[Pok.TYPE2])
    assert me[Pok.AB_ID] == AbilityNames.STURDY and me[Pok.BASE_AB_ID] == AbilityNames.LIMBER
    assert [move_slice(me, i)[Move.ID] for i in range(4)] == [move_slice(foe, i)[Move.ID] for i in range(4)]
    assert [move_slice(me, i)[Move.PP] for i in range(4)] == [5, 5, 5, 0]
    for keeps in (Pok.LEVEL, Pok.MAX_HP, Pok.CURRENT_HP, Pok.GENDER, Item.ID):
        assert me[keeps] == before[keeps]
    assert not arr[Field.AI_KNOWS] & _ENEMY_AI_KNOWS_MOVE2
    engine_helper.reset_switch_out(me)
    before[Pok.MOVE1_ID + Move.PP] -= 1
    for same in (Pok.ID, Pok.WEIGHT, Pok.TYPE1, Pok.TYPE2, Pok.AB_ID, Pok.HIDDEN_POWER_TYPE):
        assert me[same] == before[same]
    assert (me[Pok.ATTACK:Pok.SPEED + 1] == before[Pok.ATTACK:Pok.SPEED + 1]).all()
    assert (me[Pok.MOVE1_ID:Pok.ITEM_ID] == before[Pok.MOVE1_ID:Pok.ITEM_ID]).all()
    assert not me[Pok.ORIG_MOVE1:Pok.ORIG_MOVE4 + 1].any()


def test_transform_fails(poke):
    """Into a semi-invulnerable or transformed target (pokeplatinum subscript_transform_into_target)"""
    me = poke("Ditto", 30, "Limber", ["Transform"])
    foe = poke("Geodude", 30, "Sturdy", ["Tackle"])
    mv = move_slice(me, 0)
    assert not engine_helper.status_move_fails(mv, me, foe)
    foe[Pok.VOL_STATUS] |= VolStatus.SEMI_INVULNERABLE
    assert engine_helper.status_move_fails(mv, me, foe)
    foe[Pok.VOL_STATUS] = 0
    foe[Pok.VOL_STATUS2] |= VolStatus2.TRANSFORM
    assert engine_helper.status_move_fails(mv, me, foe)


def test_transform_goes_through_a_substitute(make_pokemon, make_battle):
    """Gen IV: the Substitute doesn't stop it ([SD] gen4 bypasssub)"""
    arr = _change_battle(make_pokemon, make_battle, ["Transform"], mine="Ditto", my_ab="Limber")
    me, foe = my_active(arr), opp_active(arr)
    foe[Pok.VOL_STATUS2] = VolStatus2.SUBSTITUTE
    foe[Pok.SUB_HP] = 50
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.ID] == PokemonName.GEODUDE


def test_transform_takes_the_ability_under_a_gastro_acid(make_pokemon, make_battle):
    """The target's real ability, and a copied Intimidate fires (pokeplatinum clears the announced
    flags)"""
    arr = _change_battle(make_pokemon, make_battle, ["Transform"], mine="Ditto", my_ab="Limber",
                         foe=("Gyarados", "Intimidate"))
    me, foe = my_active(arr), opp_active(arr)
    engine_helper.suppress_ability(foe)
    foe[Pok.ATTACK_STAT_STAGE] = 0
    turn_sim(0, (MOVE, 0), arr)
    assert me[Pok.AB_ID] == AbilityNames.INTIMIDATE and foe[Pok.ATTACK_STAT_STAGE] == -1


def test_transform_over_a_mimic_keeps_mimic_for_switch_out(make_pokemon, make_battle):
    """The first backup of a slot is the one switch-out restores"""
    arr = _change_battle(make_pokemon, make_battle, ["Mimic", "Transform"], ["Splash", "Ember"],
                         mine="Mew", my_ab="Synchronize")
    me, foe = my_active(arr), opp_active(arr)
    foe[Pok.LAST_MOVE_ID] = MoveName.EMBER
    turn_sim(0, (MOVE, 0), arr)
    backup = me[Pok.ORIG_MOVE1]
    turn_sim(0, (MOVE, 1), arr)
    assert me[Pok.VOL_STATUS2] & VolStatus2.TRANSFORM and me[Pok.ORIG_MOVE1] == backup
    assert move_slice(me, 0)[Move.ID] == MoveName.SPLASH
    engine_helper.reset_switch_out(me)
    assert [move_slice(me, i)[Move.ID] for i in range(2)] == [MoveName.MIMIC, MoveName.TRANSFORM]


def test_a_transformed_chatot_does_not_confuse(make_pokemon, make_battle):
    """pokeplatinum BtlCmd_CheckChatterActivation"""
    random.seed(1)
    for _ in range(40):
        arr = make_battle([make_pokemon("Chatot", 30, "Keen Eye", ["Chatter"])],
                          [make_pokemon("Geodude", 30, "Sturdy", ["Splash"])])
        my_active(arr)[Pok.VOL_STATUS2] |= VolStatus2.TRANSFORM
        turn_sim(0, (MOVE, 0), arr)
        assert not opp_active(arr)[Pok.VOL_STATUS] & VolStatus.CONFUSION
