"""Engine helpers: speed, turn order, accuracy, crits, switching, items, residuals"""
import random
import numpy as np
import pytest
from Engine import engine_helper
from Engine.speed import check_speed
from Engine.engine_helper import (
    move_order, calculate_hit_miss, calculate_crit, reset_switch_out,
    switch_in, trainer_ai_items, eat_berry, eat_berry_bug_bite, item_on_rdmg, drain, weather_dmg,
    early_returns, struggle,
    thaw, heal_weather, on_residual, flinch_checker, unlock_move, move_recoil, apply_recoil,
    natural_gift, try_protect, endure_damage, move_blocked, apply_hazards, stealth_rock_damage,
    heal_move, refresh, recycle, carry_recycle, knock_off, worry_seed, perish_song, perish_count,
    is_grounded, ohko_fails, move_accuracy, on_hit_abilities, trace, download,
    recover_status_by_ability, pressure_pp, confusion, metronome_count, metronome_fail,
    power_herb, sticky_hold, counter_fails,
    make_substitute, hit_substitute, substitute_fails, sub_blocks_move, sub_blocks_status_move,
)
from Engine.damage_calc import METRONOME_MOVE_SHIFT
from Engine.ability_helper import ignorable_ability
from Models.ability import ABILITY_TABLE
from Models.item import ITEM_TABLE
from DataBase.AbilitiesDB import AbilityNames
from Engine.engine_helper import (
    metronome_move, copycat_move, nature_power_move, mirror_record,
)
from Models.move import METRONOME_POOL, METRONOME_FORBIDDEN
from Models.helper import Terrain
from DataBase.MoveDB import MoveName
from Models.idx_const import Pok, Move, Item, Sec, Field, SIDE_TOXIC_SPIKES, FIELD_LEN
from Models.helper import (
    Status, Weather, VolStatus, VolStatus2, Potions, MoveOutcome, Types, SideCondition, Gender,
)
from DataBase.ItemDB import ItemNames
from battle_driver import move_slice, my_active


def empty_field():
    """A battle array with every field slot at 0, enough for switch_in's side lookups"""
    return np.zeros(Field.MY_POK + FIELD_LEN, dtype=np.int32)


# ── Speed & order ────────────────────────────────────────────────────────────

def test_check_speed_stages_then_paralysis(poke):
    """Stage multiplier first, paralysis quarters the result"""
    a = poke("Rattata", 50, "Run Away", ["Tackle"])
    b = poke("Rattata", 50, "Run Away", ["Tackle"])
    base, _ = check_speed(a, b, 0)
    a[Pok.SPEED_STAT_STAGE] = 2
    assert check_speed(a, b, 0)[0] == base * 2
    a[Pok.STATUS] = Status.PARALYSIS
    assert check_speed(a, b, 0)[0] == (base * 2) // 4


@pytest.mark.parametrize("species, doubled", [("Ditto", True), ("Rattata", False)])
def test_quick_powder_doubles_ditto_speed_before_paralysis(poke, species, doubled):
    """Quick Powder doubles Ditto's Speed, then paralysis quarters it (pokeplatinum
    BattleSystem_CompareBattlerSpeed)"""
    a = poke(species, 50, "Run Away", ["Tackle"], item="Quick Powder")
    b = poke("Rattata", 50, "Run Away", ["Tackle"])
    a[Pok.SPEED] = 101
    speed = 202 if doubled else 101
    assert check_speed(a, b, 0)[0] == speed
    a[Pok.STATUS] = Status.PARALYSIS
    assert check_speed(a, b, 0)[0] == speed // 4


@pytest.mark.parametrize("item", [
    "Macho Brace", "Power Anklet", "Power Band", "Power Belt", "Power Bracer", "Power Lens",
    "Power Weight", "Iron Ball",
])
def test_speed_halving_items(poke, item):
    """Macho Brace, the Power items and Iron Ball halve Speed after Swift Swim and before paralysis
    (pokeplatinum sSpeedHalvingItemEffects): 101 -> 202 -> 101 (halving first would give 100)"""
    a = poke("Magikarp", 50, "Swift Swim", ["Tackle"], item=item)
    b = poke("Rattata", 50, "Run Away", ["Tackle"])
    a[Pok.SPEED] = 101
    assert check_speed(a, b, Weather.RAIN)[0] == 101
    a[Pok.STATUS] = Status.PARALYSIS
    assert check_speed(a, b, Weather.RAIN)[0] == 25


@pytest.mark.parametrize("ability, weather", [
    ("Chlorophyll", Weather.SUN), ("Swift Swim", Weather.RAIN),
])
def test_weather_speed_abilities(poke, ability, weather):
    """Chlorophyll/Swift Swim double speed only in their weather"""
    a = poke("Oddish", 50, ability, ["Absorb"])
    b = poke("Rattata", 50, "Run Away", ["Tackle"])
    base, _ = check_speed(a, b, 0)
    assert check_speed(a, b, weather)[0] == base * 2
    other = Weather.RAIN if weather == Weather.SUN else Weather.SUN
    assert check_speed(a, b, other)[0] == base


def test_faster_moves_first(poke):
    """No priority: higher speed acts first"""
    fast = poke("Rattata", 50, "Run Away", ["Tackle"])
    slow = poke("Geodude", 50, "Sturdy", ["Tackle"])
    assert move_order(fast, 0, slow, 0, False, False, 0) == (0, 0, 2, True)
    assert move_order(slow, 0, fast, 0, False, False, 0)[3] is False


def test_priority_beats_speed(poke):
    """Quick Attack from the slower side still goes first"""
    slow = poke("Geodude", 50, "Sturdy", ["Tackle", "Quick Attack"])
    fast = poke("Rattata", 50, "Run Away", ["Tackle"])
    mv1, mv2, count, first_is_mine = move_order(slow, 1, fast, 0, False, False, 0)
    assert (mv1, mv2, count, first_is_mine) == (1, 0, 2, True)


def test_negative_priority_goes_last(poke):
    """Counter (-5) moves after a slower Tackle"""
    me = poke("Rattata", 50, "Run Away", ["Counter"])
    opp = poke("Geodude", 50, "Sturdy", ["Tackle"])
    assert move_order(me, 0, opp, 0, False, False, 0)[3] is False


def test_switch_order(poke):
    """A switching side doesn't get a move slot"""
    a = poke("Rattata", 50, "Run Away", ["Tackle"])
    b = poke("Geodude", 50, "Sturdy", ["Tackle"])
    assert move_order(a, -1, b, 2, True, False, 0) == (2, -1, 1, False)
    assert move_order(a, 3, b, -1, False, True, 0) == (3, -1, 1, True)
    assert move_order(a, -1, b, -1, True, True, 0)[2] == 0


def test_speed_tie_is_a_coin_flip(poke):
    """Identical speed: both sides win the tie sometimes"""
    a = poke("Rattata", 50, "Run Away", ["Tackle"])
    b = poke("Rattata", 50, "Run Away", ["Tackle"])
    firsts = {move_order(a, 0, b, 0, False, False, 0)[3] for _ in range(100)}
    assert firsts == {True, False}


@pytest.mark.parametrize("stage, expected_stage", [(1, 2), (2, 4), (4, 6), (-2, -4), (-4, -6)])
def test_simple_doubles_speed_stages(poke, stage, expected_stage):
    """pokeplatinum CompareSpeed_ApplySimple: the stage doubles, capped at +-6"""
    a = poke("Bidoof", 50, "Simple", ["Tackle"])
    ref = poke("Bidoof", 50, "Run Away", ["Tackle"])
    a[Pok.SPEED_STAT_STAGE] = stage
    ref[Pok.SPEED_STAT_STAGE] = expected_stage
    assert check_speed(a, ref, 0)[0] == check_speed(ref, a, 0)[0]


@pytest.mark.parametrize("status", [Status.PARALYSIS, Status.BURN, Status.POISON, Status.SLEEP])
def test_quick_feet_boosts_any_status_and_skips_paralysis(poke, status):
    """x15/10 with any status, replacing paralysis's quarter"""
    a = poke("Rattata", 50, "Quick Feet", ["Tackle"])
    base = check_speed(a, a, 0)[0]
    a[Pok.STATUS] = status
    assert check_speed(a, a, 0)[0] == base * 15 // 10


@pytest.mark.parametrize("turns_active, halved", [(0, True), (1, True), (5, True), (6, False)])
def test_slow_start_halves_speed_for_five_turns(poke, turns_active, halved):
    """The rest of the turn it enters plus 5 full turns (TURNS_ACTIVE 0..5)"""
    a = poke("Rattata", 50, "Slow Start", ["Tackle"])
    plain = poke("Rattata", 50, "Run Away", ["Tackle"])
    a[Pok.TURNS_ACTIVE] = turns_active
    base = check_speed(plain, plain, 0)[0]
    assert check_speed(a, a, 0)[0] == (base // 2 if halved else base)


@pytest.mark.parametrize("marked, has_item, doubled", [
    (True, False, True), (True, True, False), (False, False, False),
])
def test_unburden_doubles_speed_once_the_item_is_gone(poke, marked, has_item, doubled):
    """x2 only with the CAN_UNBURDEN mark and no item"""
    a = poke("Treecko", 50, "Unburden", ["Pound"], item="Oran Berry" if has_item else None)
    plain = poke("Treecko", 50, "Run Away", ["Pound"])
    if marked:
        a[Pok.VOL_STATUS2] |= VolStatus2.CAN_UNBURDEN
    base = check_speed(plain, plain, 0)[0]
    assert check_speed(a, a, 0)[0] == (base * 2 if doubled else base)


def test_unburden_comes_after_paralysis(poke):
    """pokeplatinum order: paralysis floors first, then Unburden doubles"""
    a = poke("Treecko", 37, "Unburden", ["Pound"])
    a[Pok.VOL_STATUS2] |= VolStatus2.CAN_UNBURDEN
    a[Pok.STATUS] = Status.PARALYSIS
    assert check_speed(a, a, 0)[0] == a[Pok.SPEED] // 4 * 2


def test_unburden_marked_on_switch_in_while_holding(poke):
    """recover_status_by_ability marks a holder; an empty hand or a knocked off item doesn't"""
    foe = poke("Rattata", 20, "Run Away", ["Tackle"])
    holder = poke("Treecko", 20, "Unburden", ["Pound"], item="Oran Berry")
    switch_in(holder, foe, empty_field(), True)
    assert holder[Pok.VOL_STATUS2] & VolStatus2.CAN_UNBURDEN
    reset_switch_out(holder)
    assert not holder[Pok.VOL_STATUS2] & VolStatus2.CAN_UNBURDEN
    empty = poke("Treecko", 20, "Unburden", ["Pound"])
    switch_in(empty, foe, empty_field(), True)
    assert not empty[Pok.VOL_STATUS2] & VolStatus2.CAN_UNBURDEN
    knocked = poke("Treecko", 20, "Unburden", ["Pound"], item="Oran Berry")
    knocked[Pok.ITEM_KNOCKED_OFF] = 1
    switch_in(knocked, foe, empty_field(), True)
    assert not knocked[Pok.VOL_STATUS2] & VolStatus2.CAN_UNBURDEN


def test_traced_unburden_marks_the_holder(poke):
    """A Trace holder that copies Unburden while holding an item is marked too"""
    tracer = poke("Ralts", 20, "Trace", ["Pound"], item="Oran Berry")
    foe = poke("Treecko", 20, "Unburden", ["Pound"])
    switch_in(tracer, foe, empty_field(), True)
    assert tracer[Pok.AB_ID] == AbilityNames.UNBURDEN
    assert tracer[Pok.VOL_STATUS2] & VolStatus2.CAN_UNBURDEN


def _claw(monkeypatch, activates):
    monkeypatch.setattr(random, "randint", lambda lo, hi: 0 if activates else 99)


def test_quick_claw_moves_first_in_its_bracket(monkeypatch, poke):
    """An activated Quick Claw beats speed, not a higher priority"""
    slow = poke("Geodude", 50, "Sturdy", ["Tackle"], item="Quick Claw")
    fast = poke("Rattata", 50, "Run Away", ["Tackle", "Quick Attack"])
    _claw(monkeypatch, True)
    assert move_order(slow, 0, fast, 0, False, False, 0)[3] is True
    assert move_order(fast, 0, slow, 0, False, False, 0)[3] is False
    assert move_order(slow, 0, fast, 1, False, False, 0)[3] is False
    _claw(monkeypatch, False)
    assert move_order(slow, 0, fast, 0, False, False, 0)[3] is False


def test_two_quick_claws_fall_back_to_speed(monkeypatch, poke):
    """Both activate: the faster one goes first"""
    slow = poke("Geodude", 50, "Sturdy", ["Tackle"], item="Quick Claw")
    fast = poke("Rattata", 50, "Run Away", ["Tackle"], item="Quick Claw")
    _claw(monkeypatch, True)
    assert move_order(slow, 0, fast, 0, False, False, 0)[3] is False


def test_quick_claw_chance_and_no_roll_without_one(poke):
    """About 1 in 5, and no RNG call when nobody holds it"""
    slow = poke("Geodude", 50, "Sturdy", ["Tackle"], item="Quick Claw")
    fast = poke("Rattata", 50, "Run Away", ["Tackle"])
    firsts = sum(move_order(slow, 0, fast, 0, False, False, 0)[3] for _ in range(5000))
    assert 900 < firsts < 1100
    plain = poke("Geodude", 50, "Sturdy", ["Tackle"])
    state = random.getstate()
    move_order(plain, 0, fast, 0, False, False, 0)
    assert random.getstate() == state


@pytest.mark.parametrize("moves, stall_first", [
    (["Tackle"], False),   # priority 0: the Stall holder goes last
    (["Counter"], True),   # Showdown gen4 only applies Stall at priority >= 0
])
def test_stall_moves_last_in_its_bracket(poke, moves, stall_first):
    """A faster Stall holder moves after a slower foe of the same priority"""
    stall = poke("Rattata", 50, "Stall", moves)
    slow = poke("Geodude", 50, "Sturdy", moves)
    assert move_order(stall, 0, slow, 0, False, False, 0)[3] is stall_first


def test_two_stalls_and_quick_claw_over_stall(monkeypatch, poke):
    """Both Stall: speed (Showdown). An activated Quick Claw on a Stall holder still goes first"""
    fast = poke("Rattata", 50, "Stall", ["Tackle"])
    slow = poke("Geodude", 50, "Stall", ["Tackle"])
    assert move_order(fast, 0, slow, 0, False, False, 0)[3] is True
    claw = poke("Geodude", 50, "Stall", ["Tackle"], item="Quick Claw")
    plain = poke("Rattata", 50, "Run Away", ["Tackle"])
    _claw(monkeypatch, True)
    assert move_order(claw, 0, plain, 0, False, False, 0)[3] is True


@pytest.mark.parametrize("item", ["Lagging Tail", "Full Incense"])
def test_lagging_tail_moves_last_in_its_bracket(poke, item):
    """The holder moves after a slower foe at any priority, after a Stall holder too, but a
    higher-priority move still goes first (pokeplatinum CompareBattlerSpeed)"""
    lag = poke("Rattata", 50, "Run Away", ["Tackle", "Quick Attack", "Counter"], item=item)
    slow = poke("Geodude", 50, "Sturdy", ["Tackle", "Counter"])
    assert move_order(lag, 0, slow, 0, False, False, 0)[3] is False
    assert move_order(slow, 0, lag, 0, False, False, 0)[3] is True
    assert move_order(lag, 2, slow, 1, False, False, 0)[3] is False
    assert move_order(lag, 1, slow, 0, False, False, 0)[3] is True
    stall = poke("Geodude", 50, "Stall", ["Tackle"])
    assert move_order(lag, 0, stall, 0, False, False, 0)[3] is False


def test_two_lagging_tails_and_quick_claw(monkeypatch, poke):
    """Both hold one: speed (Showdown). An activated Quick Claw goes before a Lagging Tail holder"""
    fast = poke("Rattata", 50, "Run Away", ["Tackle"], item="Lagging Tail")
    slow = poke("Geodude", 50, "Sturdy", ["Tackle"], item="Full Incense")
    assert move_order(fast, 0, slow, 0, False, False, 0)[3] is True
    claw = poke("Geodude", 50, "Sturdy", ["Tackle"], item="Quick Claw")
    _claw(monkeypatch, True)
    assert move_order(fast, 0, claw, 0, False, False, 0)[3] is False


@pytest.mark.parametrize("turns_active, loafs", [(1, False), (2, True), (3, False), (4, True)])
def test_truant_loafs_every_other_turn(poke, turns_active, loafs):
    """Acts on its first full turn, then loafs by turn parity; loafing unlocks the move"""
    a = poke("Slakoth", 20, "Truant", ["Scratch"])
    d = poke("Rattata", 20, "Run Away", ["Tackle"])
    a[Pok.TURNS_ACTIVE] = turns_active
    a[Pok.LOCKED_MOVE] = 0
    assert early_returns(a, d, 1, False, move_slice(a, 0)) is loafs
    assert a[Pok.LOCKED_MOVE] == (-1 if loafs else 0)


# ── Accuracy & crits ─────────────────────────────────────────────────────────

def test_type_immunity_is_invulnerable(poke):
    """Normal move into Ghost reports INVULNERABLE"""
    a = poke("Rattata", 50, "Run Away", ["Tackle"])
    d = poke("Gastly", 50, "Levitate", ["Lick"])
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == MoveOutcome.INVULNERABLE


def test_never_miss_move(poke):
    """accuracy -1 always hits, even at -6 accuracy / +6 evasion"""
    a = poke("Pikachu", 50, "Static", ["Swift"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    a[Pok.ACCURACY_STAT_STAGE] = -6
    d[Pok.EVASION_STAT_STAGE] = 6
    assert all(calculate_hit_miss(move_slice(a, 0), a, d, 0) == MoveOutcome.HIT
               for _ in range(50))


def test_hundred_accuracy_neutral_stages_hits(poke):
    """100% move with no stage changes never misses"""
    a = poke("Rattata", 50, "Run Away", ["Tackle"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    assert all(calculate_hit_miss(move_slice(a, 0), a, d, 0) == MoveOutcome.HIT
               for _ in range(200))


def _hit_rate(a, d, n=6000):
    return sum(calculate_hit_miss(move_slice(a, 0), a, d, 0) == MoveOutcome.HIT
               for _ in range(n)) / n


@pytest.mark.parametrize("acc, eva, expected", [
    (-1, 0, 3 / 4), (-3, 0, 3 / 6), (-6, 0, 3 / 9),
    (0, 1, 3 / 4), (0, 6, 3 / 9),
    (1, 0, 1.0), (2, 1, 1.0),
])
def test_accuracy_stages(poke, acc, eva, expected):
    """Regression: negative stages used 3/(3+n) (more accurate at -1, divide by zero at -3).
    Gen IV: (accuracy - evasion) stage n multiplies by 3/(3-n) below 0, (3+n)/3 above"""
    a = poke("Rattata", 50, "Run Away", ["Tackle"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    a[Pok.ACCURACY_STAT_STAGE] = acc
    d[Pok.EVASION_STAT_STAGE] = eva
    assert _hit_rate(a, d) == pytest.approx(expected, abs=0.03)


def test_combined_accuracy_stage_clamps_at_six(poke):
    """-6 accuracy vs +6 evasion is a -12 difference, clamped to -6 (3/9)"""
    a = poke("Rattata", 50, "Run Away", ["Tackle"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    a[Pok.ACCURACY_STAT_STAGE] = -6
    d[Pok.EVASION_STAT_STAGE] = 6
    assert _hit_rate(a, d) == pytest.approx(3 / 9, abs=0.03)


def test_fake_out_only_first_turn(poke):
    """Fake Out fails after the user's first active turn"""
    a = poke("Rattata", 50, "Run Away", ["Fake Out"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    a[Pok.TURNS_ACTIVE] = 1
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == MoveOutcome.HIT
    a[Pok.TURNS_ACTIVE] = 2
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == MoveOutcome.MISS


def test_water_absorb_heals_and_blocks(poke):
    """Water move into Water Absorb heals 1/4 and doesn't land (it hit, the ability took it)"""
    a = poke("Squirtle", 50, "Torrent", ["Water Gun"])
    d = poke("Mudkip", 50, "Water Absorb", ["Tackle"])
    d[Pok.CURRENT_HP] = 10
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == MoveOutcome.INVULNERABLE
    assert d[Pok.CURRENT_HP] == 10 + d[Pok.MAX_HP] // 4


def test_will_crit_and_battle_armor(poke):
    """WILL_CRIT forces a crit, Battle Armor blocks every crit"""
    a = poke("Rattata", 50, "Run Away", ["Tackle"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    mv = move_slice(a, 0).copy()
    mv[Move.WILL_CRIT] = 1
    assert calculate_crit(a, d, mv)
    armored = poke("Kabuto", 50, "Battle Armor", ["Scratch"])
    assert not any(calculate_crit(a, armored, mv) for _ in range(50))


@pytest.mark.parametrize("focus, crit_ratio, expected", [
    (False, 1, 1 / 16), (False, 2, 1 / 8), (True, 1, 1 / 4), (True, 2, 1 / 3),
])
def test_crit_rates(poke, focus, crit_ratio, expected):
    """Gen IV crit stages: 1/16, 1/8, 1/4, 1/3 (statistical, seeded)"""
    a = poke("Rattata", 50, "Run Away", ["Tackle"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    if focus:
        a[Pok.VOL_STATUS] |= VolStatus.FOCUS_ENERGY
    mv = move_slice(a, 0).copy()
    mv[Move.CRIT_RATIO] = crit_ratio
    n = 20_000
    rate = sum(bool(calculate_crit(a, d, mv)) for _ in range(n)) / n
    assert rate == pytest.approx(expected, abs=0.015)


@pytest.mark.parametrize("species, item, expected", [
    ("Chansey", "Lucky Punch", 1 / 4), ("Farfetchd", "Stick", 1 / 4),
    ("Rattata", "Lucky Punch", 1 / 16), ("Chansey", "Stick", 1 / 16),
])
def test_species_crit_items(poke, species, item, expected):
    """Lucky Punch (Chansey) and Stick (Farfetch'd) add 2 crit stages (statistical, seeded)"""
    a = poke(species, 50, "Run Away", ["Tackle"], item=item)
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    mv = move_slice(a, 0)
    random.seed(11)
    n = 20_000
    rate = sum(bool(calculate_crit(a, d, mv)) for _ in range(n)) / n
    assert rate == pytest.approx(expected, abs=0.015)


@pytest.mark.parametrize("item", ["Scope Lens", "Razor Claw"])
def test_razor_claw_adds_a_crit_stage(poke, item):
    """Razor Claw is Scope Lens's effect: +1 stage, 1/8 (statistical, seeded)"""
    a = poke("Rattata", 50, "Run Away", ["Tackle"], item=item)
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    mv = move_slice(a, 0)
    random.seed(11)
    n = 20_000
    rate = sum(bool(calculate_crit(a, d, mv)) for _ in range(n)) / n
    assert rate == pytest.approx(1 / 8, abs=0.015)


# ── Accuracy, crit and flinch abilities ──────────────────────────────────────

def _acc(a, d, weather=0, slot=0):
    """Hit rate move_accuracy gives for a's move `slot`"""
    mv = move_slice(a, slot)
    return move_accuracy(mv, a, d, mv[Move.ACCURACY], weather)


@pytest.mark.parametrize("atk_ab, def_ab, weather, expected", [
    ("Compound Eyes", "Run Away", 0, 130),
    ("Run Away", "Sand Veil", Weather.SANDSTORM, 80),
    ("Run Away", "Sand Veil", 0, 100),
    ("Run Away", "Snow Cloak", Weather.HAIL, 80),
    ("Run Away", "Snow Cloak", Weather.SANDSTORM, 100),
    ("Hustle", "Run Away", 0, 80),
    ("Hustle", "Sand Veil", Weather.SANDSTORM, 64),
    ("Compound Eyes", "Snow Cloak", Weather.HAIL, 104),
    ("Mold Breaker", "Sand Veil", Weather.SANDSTORM, 100),
    ("Mold Breaker", "Snow Cloak", Weather.HAIL, 100),
])
def test_accuracy_abilities(poke, atk_ab, def_ab, weather, expected):
    """pokeplatinum order and integer steps: Compound Eyes x130/100, Sand Veil / Snow Cloak x80/100
    (Mold Breaker ignores them), Hustle x80/100. Issue 3: Hustle no longer skips Sand Veil"""
    a = poke("Rattata", 50, atk_ab, ["Tackle"])
    d = poke("Rattata", 50, def_ab, ["Tackle"])
    assert _acc(a, d, weather) == expected


def test_hustle_only_cuts_physical_accuracy(poke):
    """Hustle doesn't touch special moves"""
    a = poke("Togepi", 50, "Hustle", ["Ember"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    assert _acc(a, d) == 100


def test_accuracy_modifiers_come_after_the_stages(poke):
    """Issue 14: Rock Throw 90 at -1 is 67, Hustle 53 (Hustle first gave 72, then 54)"""
    a = poke("Geodude", 50, "Hustle", ["Rock Throw"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    a[Pok.ACCURACY_STAT_STAGE] = -1
    assert _acc(a, d) == 53


@pytest.mark.parametrize("atk_ab, confused, expected", [
    ("Run Away", True, 50), ("Run Away", False, 100), ("Mold Breaker", True, 100),
])
def test_tangled_feet_halves_accuracy_while_confused(poke, atk_ab, confused, expected):
    """Tangled Feet x50/100 against a confused holder, Mold Breaker ignores it"""
    a = poke("Rattata", 50, atk_ab, ["Tackle"])
    d = poke("Pidgey", 50, "Tangled Feet", ["Tackle"])
    if confused:
        d[Pok.VOL_STATUS] |= VolStatus.CONFUSION
    assert _acc(a, d) == expected


@pytest.mark.parametrize("item", ["Bright Powder", "Lax Incense"])
def test_accuracy_reducing_items(poke, item):
    """The defender's Bright Powder / Lax Incense: x(100 - 10)/100"""
    a = poke("Rattata", 50, "Run Away", ["Tackle"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"], item=item)
    assert _acc(a, d) == 90


@pytest.mark.parametrize("item, target_moved, expected", [
    ("Wide Lens", False, 99), ("Wide Lens", True, 99),
    ("Zoom Lens", False, 90), ("Zoom Lens", True, 108),
])
def test_accuracy_lenses(poke, item, target_moved, expected):
    """pokeplatinum CheckMoveHitAccuracy: Rock Throw's 90 x110/100 with Wide Lens, x120/100 with Zoom
    Lens only once the target has acted this turn"""
    a = poke("Geodude", 50, "Rock Head", ["Rock Throw"], item=item)
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    mv = move_slice(a, 0)
    assert move_accuracy(mv, a, d, mv[Move.ACCURACY], 0, False, target_moved) == expected


def test_lenses_come_after_bright_powder_and_before_gravity(poke):
    """90 -> Bright Powder 81 -> Zoom Lens 97 -> Gravity x6840/4096"""
    a = poke("Geodude", 50, "Rock Head", ["Rock Throw"], item="Zoom Lens")
    d = poke("Rattata", 50, "Run Away", ["Tackle"], item="Bright Powder")
    mv = move_slice(a, 0)
    assert move_accuracy(mv, a, d, mv[Move.ACCURACY], 0, False, True) == 97
    gravity = move_accuracy(mv, a, d, mv[Move.ACCURACY], 0, True, True)
    assert gravity == pytest.approx(97 * 6840 / 4096)


@pytest.mark.parametrize("atk_ab, def_ab, acc, eva, expected", [
    ("Run Away", "Unaware", 2, 0, 100),        # defending Unaware ignores the accuracy boost
    ("Unaware", "Run Away", 0, 2, 100),        # attacking Unaware ignores the evasion boost
    ("Unaware", "Run Away", -1, 0, 75),        # its own stage still counts
    ("Mold Breaker", "Unaware", 2, 0, 166),
    ("Simple", "Run Away", -1, 0, 60),         # -1 doubled to -2
    ("Run Away", "Simple", 0, 1, 60),          # +1 evasion doubled to +2
    ("Mold Breaker", "Simple", 0, 1, 75),
])
def test_unaware_and_simple_on_accuracy_stages(poke, atk_ab, def_ab, acc, eva, expected):
    """pokeplatinum CheckMoveHitAccuracy: Simple doubles the stages, Unaware zeroes the foe's;
    Mold Breaker ignores the defender's"""
    a = poke("Bidoof", 50, atk_ab, ["Tackle"])
    d = poke("Bidoof", 50, def_ab, ["Tackle"])
    a[Pok.ACCURACY_STAT_STAGE] = acc
    d[Pok.EVASION_STAT_STAGE] = eva
    assert _acc(a, d) == expected


@pytest.mark.parametrize("side", ["attacker", "defender"])
def test_no_guard_always_hits_and_reaches_dig(poke, side):
    """No Guard on either side skips the roll and the semi-invulnerable check
    (pokeplatinum BattleControllerPlayer_CheckMoveHitOverrides)"""
    a = poke("Machop", 50, "No Guard" if side == "attacker" else "Guts", ["Rock Throw"])
    d = poke("Rattata", 50, "No Guard" if side == "defender" else "Run Away", ["Tackle"])
    a[Pok.ACCURACY_STAT_STAGE] = -6
    assert all(calculate_hit_miss(move_slice(a, 0), a, d, 0) == MoveOutcome.HIT
               for _ in range(100))
    d[Pok.VOL_STATUS] = VolStatus.SEMI_INVULNERABLE
    d[Pok.SEMI_INV_MOVE] = MoveName.DIG
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == MoveOutcome.HIT


def test_no_guard_keeps_protect_and_type_immunity(poke):
    """No Guard doesn't get through Protect or a type immunity"""
    a = poke("Machop", 50, "No Guard", ["Karate Chop"])
    ghost = poke("Gastly", 50, "Levitate", ["Lick"])
    assert calculate_hit_miss(move_slice(a, 0), a, ghost, 0) == MoveOutcome.INVULNERABLE
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    d[Pok.VOL_STATUS] |= VolStatus.PROTECT
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == MoveOutcome.PROTECTED


@pytest.mark.parametrize("atk_lv, semi_inv, outcome", [
    (50, 0, MoveOutcome.HIT),
    (50, MoveName.DIG, MoveOutcome.HIT),
    (49, 0, MoveOutcome.INVULNERABLE),
])
def test_no_guard_ohko(monkeypatch, poke, atk_lv, semi_inv, outcome):
    """No Guard: an OHKO move always hits, Dig included, but still fails from a lower level
    (pokeplatinum BtlCmd_TryOHKOMove)"""
    monkeypatch.setattr(engine_helper.random, "randint", lambda x, y: 99)
    a = poke("Machop", atk_lv, "No Guard", ["Guillotine"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    if semi_inv:
        d[Pok.VOL_STATUS] = VolStatus.SEMI_INVULNERABLE
        d[Pok.SEMI_INV_MOVE] = semi_inv
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == outcome


@pytest.mark.parametrize("ability, item, expected", [
    ("Super Luck", None, 1 / 8), ("Run Away", "Scope Lens", 1 / 8), ("Super Luck", "Scope Lens", 1 / 4),
])
def test_super_luck_and_scope_lens_raise_the_crit_stage(poke, ability, item, expected):
    """Each is +1 crit stage (pokeplatinum BattleSystem_CalcCriticalMulti)"""
    a = poke("Murkrow", 50, ability, ["Peck"], item=item)
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    mv = move_slice(a, 0)
    n = 20_000
    rate = sum(bool(calculate_crit(a, d, mv)) for _ in range(n)) / n
    assert rate == pytest.approx(expected, abs=0.015)


@pytest.mark.parametrize("ability", ["Battle Armor", "Shell Armor"])
def test_mold_breaker_crits_through_armor(poke, ability):
    """Battle Armor and Shell Armor are ignored by Mold Breaker"""
    a = poke("Cranidos", 50, "Mold Breaker", ["Headbutt"])
    d = poke("Shellder", 50, ability, ["Tackle"])
    mv = move_slice(a, 0).copy()
    mv[Move.WILL_CRIT] = 1
    assert calculate_crit(a, d, mv)


@pytest.mark.parametrize("atk_ab, def_ab, flinches", [
    ("Run Away", "Inner Focus", False),
    ("Mold Breaker", "Inner Focus", True),
    ("Run Away", "Shield Dust", False),
    ("Mold Breaker", "Shield Dust", True),
    ("Run Away", "Run Away", True),
])
def test_inner_focus_and_shield_dust_stop_flinch(poke, atk_ab, def_ab, flinches):
    """pokeplatinum subscript_flinch_mon: both are ignorable, so Mold Breaker makes them flinch"""
    a = poke("Zubat", 50, atk_ab, ["Bite"])
    d = poke("Rattata", 50, def_ab, ["Tackle"])
    mv = move_slice(a, 0).copy()
    mv[Sec.CHANCE] = 100
    assert flinch_checker(mv, a, d) == flinches


@pytest.mark.parametrize("ability, flinches", [("Serene Grace", True), ("Run Away", False)])
def test_serene_grace_doubles_flinch_chance(monkeypatch, poke, ability, flinches):
    """A 50% flinch becomes 100%: a roll of 100 flinches only with Serene Grace"""
    monkeypatch.setattr(engine_helper.random, "randint", lambda x, y: 100)
    a = poke("Togepi", 50, ability, ["Bite"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    mv = move_slice(a, 0).copy()
    mv[Sec.CHANCE] = 50
    assert flinch_checker(mv, a, d) == flinches


# ── Contact abilities ────────────────────────────────────────────────────────

def _fix_rolls(monkeypatch, chance_roll, pick=0):
    """randint(0, 9) is the 30% roll, randint(0, 2) Effect Spore's pick"""
    monkeypatch.setattr(engine_helper.random, "randint",
                        lambda lo, hi: chance_roll if hi == 9 else pick)


@pytest.mark.parametrize("ability, status", [
    ("Static", Status.PARALYSIS), ("Flame Body", Status.BURN), ("Poison Point", Status.POISON),
])
@pytest.mark.parametrize("roll, applies", [(2, True), (3, False)])
def test_contact_status_abilities(monkeypatch, poke, ability, status, roll, applies):
    """30% on a contact hit, pokeplatinum RandNext % 10 < 3"""
    _fix_rolls(monkeypatch, roll)
    a = poke("Rattata", 50, "Run Away", ["Tackle"])
    d = poke("Pikachu", 50, ability, ["Tackle"])
    on_hit_abilities(a, d, move_slice(a, 0), 10, 0)
    assert (a[Pok.STATUS] == status) == applies


@pytest.mark.parametrize("move, dealt, attacker_hp, attacker_status", [
    ("Ember", 10, 50, 0),                   # no contact
    ("Tackle", 0, 50, 0),                   # no damage
    ("Tackle", 10, 0, 0),                   # attacker already fainted
    ("Tackle", 10, 50, Status.BURN),        # already has a status
])
def test_contact_status_needs_contact_damage_and_a_healthy_attacker(
        monkeypatch, poke, move, dealt, attacker_hp, attacker_status):
    """Nothing happens without contact, damage, a living attacker or with a status already"""
    _fix_rolls(monkeypatch, 0)
    a = poke("Rattata", 50, "Run Away", [move])
    a[Pok.CURRENT_HP] = attacker_hp
    a[Pok.STATUS] = attacker_status
    d = poke("Pikachu", 50, "Static", ["Tackle"])
    on_hit_abilities(a, d, move_slice(a, 0), dealt, 0)
    assert a[Pok.STATUS] == attacker_status


@pytest.mark.parametrize("ability, attacker", [("Flame Body", "Charmander"), ("Poison Point", "Grimer")])
def test_contact_status_respects_type_immunity(monkeypatch, poke, ability, attacker):
    """Fire types don't burn, Poison types don't get poisoned"""
    _fix_rolls(monkeypatch, 0)
    a = poke(attacker, 50, "Run Away", ["Scratch"] if attacker == "Charmander" else ["Pound"])
    d = poke("Ponyta", 50, ability, ["Tackle"])
    on_hit_abilities(a, d, move_slice(a, 0), 10, 0)
    assert a[Pok.STATUS] == 0


def test_static_on_the_ko_hit(monkeypatch, poke):
    """The hit that knocks the Static holder out can still paralyze (pokeplatinum, Showdown gen4)"""
    _fix_rolls(monkeypatch, 0)
    a = poke("Rattata", 50, "Run Away", ["Tackle"])
    d = poke("Pikachu", 50, "Static", ["Tackle"])
    d[Pok.CURRENT_HP] = 0
    on_hit_abilities(a, d, move_slice(a, 0), 10, 0)
    assert a[Pok.STATUS] == Status.PARALYSIS


def test_synchronize_bounces_a_contact_status(monkeypatch, poke):
    """Static paralyzes a Synchronize attacker, which paralyzes the Static holder back"""
    _fix_rolls(monkeypatch, 0)
    a = poke("Abra", 50, "Synchronize", ["Fire Punch"])
    d = poke("Pikachu", 50, "Static", ["Tackle"])
    on_hit_abilities(a, d, move_slice(a, 0), 10, 0)
    assert a[Pok.STATUS] == d[Pok.STATUS] == Status.PARALYSIS


@pytest.mark.parametrize("pick, status", [
    (0, Status.POISON), (1, Status.PARALYSIS), (2, Status.SLEEP),
])
def test_effect_spore_picks_one_of_three(monkeypatch, poke, pick, status):
    """30%, then RandNext % 3: poison, paralysis, sleep"""
    _fix_rolls(monkeypatch, 2, pick)
    a = poke("Rattata", 50, "Run Away", ["Tackle"])
    d = poke("Paras", 50, "Effect Spore", ["Tackle"])
    on_hit_abilities(a, d, move_slice(a, 0), 10, 0)
    assert a[Pok.STATUS] == status
    if status == Status.SLEEP:
        assert a[Pok.SLEEP_COUNTER] > 0


@pytest.mark.parametrize("atk_gender, def_hp, attracted", [
    (Gender.MALE, 50, True), (Gender.FEMALE, 50, False), (Gender.MALE, 0, False),
])
def test_cute_charm(monkeypatch, poke, atk_gender, def_hp, attracted):
    """30% Attract, opposite genders only, and the Cute Charm holder has to be alive"""
    _fix_rolls(monkeypatch, 0)
    a = poke("Rattata", 50, "Run Away", ["Tackle"])
    a[Pok.GENDER] = atk_gender
    d = poke("Clefairy", 50, "Cute Charm", ["Pound"])
    d[Pok.GENDER] = Gender.FEMALE
    d[Pok.CURRENT_HP] = def_hp
    on_hit_abilities(a, d, move_slice(a, 0), 10, 0)
    assert bool(a[Pok.VOL_STATUS] & VolStatus.ATTRACT) == attracted


@pytest.mark.parametrize("atk_ab, def_hp, loses", [
    ("Run Away", 50, True), ("Run Away", 0, True), ("Magic Guard", 50, False),
])
def test_rough_skin(poke, atk_ab, def_hp, loses):
    """The attacker loses 1/8 of its max HP, the KO hit too; Magic Guard is immune"""
    a = poke("Rattata", 50, atk_ab, ["Tackle"])
    d = poke("Carvanha", 50, "Rough Skin", ["Bite"])
    d[Pok.CURRENT_HP] = def_hp
    hp = a[Pok.CURRENT_HP]
    on_hit_abilities(a, d, move_slice(a, 0), 10, 0)
    assert a[Pok.CURRENT_HP] == (hp - a[Pok.MAX_HP] // 8 if loses else hp)


@pytest.mark.parametrize("atk_ab, move, def_hp, loses", [
    ("Run Away", "Tackle", 0, True),
    ("Run Away", "Tackle", 30, False),          # the holder has to faint
    ("Run Away", "Ember", 0, False),            # no contact
    ("Damp", "Tackle", 0, False),
    ("Magic Guard", "Tackle", 0, False),
])
def test_aftermath(poke, atk_ab, move, def_hp, loses):
    """Issue 5: a contact KO costs the attacker 1/4 of its max HP, whatever the move's damage
    source; Damp and Magic Guard stop it"""
    a = poke("Rattata", 50, atk_ab, [move])
    d = poke("Stunky", 50, "Aftermath", ["Scratch"])
    d[Pok.CURRENT_HP] = def_hp
    hp = a[Pok.CURRENT_HP]
    on_hit_abilities(a, d, move_slice(a, 0), 10, 0)
    assert a[Pok.CURRENT_HP] == (hp - a[Pok.MAX_HP] // 4 if loses else hp)


# ── Switching ────────────────────────────────────────────────────────────────

def test_reset_switch_out(poke):
    """Switching out clears stages, volatiles, charge/lock; toxic counter restarts"""
    p = poke("Rattata", 50, "Run Away", ["Tackle"])
    p[Pok.ATTACK_STAT_STAGE:Pok.EVASION_STAT_STAGE + 1] = 3
    p[Pok.VOL_STATUS] = VolStatus.CONFUSION | VolStatus.CURSE
    p[Pok.STATUS] = Status.TOXIC
    p[Pok.BADLY_POISON] = 5
    p[Pok.CHARGE_RECHARGE] = 1
    p[Pok.LOCKED_MOVE] = 2
    p[Pok.TURNS_ACTIVE] = 4
    p[Pok.DMG_TAKEN] = 30
    hp = p[Pok.CURRENT_HP]
    reset_switch_out(p)
    assert not p[Pok.ATTACK_STAT_STAGE:Pok.EVASION_STAT_STAGE + 1].any()
    assert p[Pok.VOL_STATUS] == 0
    assert p[Pok.STATUS] == Status.TOXIC and p[Pok.BADLY_POISON] == 1
    assert p[Pok.LOCKED_MOVE] == -1
    assert p[Pok.CHARGE_RECHARGE] == p[Pok.TURNS_ACTIVE] == p[Pok.DMG_TAKEN] == 0
    assert p[Pok.CURRENT_HP] == hp


def test_intimidate_on_switch_in(poke):
    """Intimidate drops the foe's Attack by one, floored at -6"""
    me = poke("Shinx", 50, "Intimidate", ["Tackle"])
    foe = poke("Rattata", 50, "Run Away", ["Tackle"])
    switch_in(me, foe, empty_field(), True)
    assert foe[Pok.ATTACK_STAT_STAGE] == -1
    foe[Pok.ATTACK_STAT_STAGE] = -6
    switch_in(me, foe, empty_field(), True)
    assert foe[Pok.ATTACK_STAT_STAGE] == -6
    switch_in(foe, me, empty_field(), False)
    assert me[Pok.ATTACK_STAT_STAGE] == 0


@pytest.mark.parametrize("ability, blocked", [
    ("Clear Body", True), ("White Smoke", True), ("Hyper Cutter", True), ("Keen Eye", False),
])
def test_intimidate_respects_stat_drop_guards(poke, ability, blocked):
    """Intimidate goes through the stat stage change, so the guard abilities stop it"""
    me = poke("Shinx", 50, "Intimidate", ["Tackle"])
    foe = poke("Geodude", 50, ability, ["Tackle"])
    switch_in(me, foe, empty_field(), True)
    assert foe[Pok.ATTACK_STAT_STAGE] == (0 if blocked else -1)


def test_intimidate_skips_a_fainted_foe(poke):
    """pokeplatinum subscript_intimidate skips a foe at 0 HP"""
    me = poke("Shinx", 50, "Intimidate", ["Tackle"])
    foe = poke("Rattata", 50, "Run Away", ["Tackle"])
    foe[Pok.CURRENT_HP] = 0
    switch_in(me, foe, empty_field(), True)
    assert foe[Pok.ATTACK_STAT_STAGE] == 0


def test_trace_copies_and_reverts(poke):
    """Trace copies the foe's whole ability block on entry and gets Trace back on switch-out"""
    me = poke("Ralts", 20, "Trace", ["Growl"])
    foe = poke("Geodude", 20, "Sturdy", ["Tackle"])
    arr = empty_field()
    switch_in(me, foe, arr, True)
    assert me[Pok.AB_ID] == AbilityNames.STURDY and me[Pok.BASE_AB_ID] == AbilityNames.TRACE
    assert (me[Pok.AB_ID:Pok.AB_ID + 3] == ABILITY_TABLE[AbilityNames.STURDY][:3]).all()
    assert me[Pok.AB_KNOWN] and foe[Pok.AB_KNOWN]
    reset_switch_out(me)
    assert me[Pok.AB_ID] == AbilityNames.TRACE and me[Pok.BASE_AB_ID] == 0
    assert me[Pok.AB_KNOWN] == 0


@pytest.mark.parametrize("foe_ability", ["Trace", "Multitype", "Forecast"])
def test_trace_fails_on_untraceable(poke, foe_ability):
    """pokeplatinum ChooseTraceTarget skips Trace, Multitype and Forecast"""
    me = poke("Ralts", 20, "Trace", ["Growl"])
    foe = poke("Geodude", 20, foe_ability, ["Tackle"])
    assert not trace(me, foe)
    assert me[Pok.AB_ID] == AbilityNames.TRACE and me[Pok.BASE_AB_ID] == 0


def test_trace_fails_on_fainted_foe_and_retries_on_the_next(poke):
    """traceAnnounced stays FALSE after a failed Trace, so the next foe's entry gets copied"""
    me = poke("Ralts", 20, "Trace", ["Growl"])
    fainted = poke("Rattata", 20, "Run Away", ["Tackle"])
    fainted[Pok.CURRENT_HP] = 0
    arr = empty_field()
    switch_in(me, fainted, arr, True)
    assert me[Pok.AB_ID] == AbilityNames.TRACE
    newcomer = poke("Geodude", 20, "Rock Head", ["Tackle"])
    switch_in(newcomer, me, arr, False)
    assert me[Pok.AB_ID] == AbilityNames.ROCK_HEAD


def test_traced_intimidate_fires_once(poke):
    """A copied Intimidate fires right after Trace, the retry on the next foe fires it there"""
    me = poke("Ralts", 20, "Trace", ["Growl"])
    foe = poke("Shinx", 20, "Intimidate", ["Tackle"])
    switch_in(me, foe, empty_field(), True)
    assert foe[Pok.ATTACK_STAT_STAGE] == -1
    assert me[Pok.ATTACK_STAT_STAGE] == 0
    # Trace held off by a Trace foe, then a Shinx comes in: each Intimidates the other once
    me = poke("Ralts", 20, "Trace", ["Growl"])
    switch_in(me, poke("Ralts", 20, "Trace", ["Growl"]), empty_field(), True)
    shinx = poke("Shinx", 20, "Intimidate", ["Tackle"])
    switch_in(shinx, me, empty_field(), False)
    assert me[Pok.AB_ID] == AbilityNames.INTIMIDATE
    assert me[Pok.ATTACK_STAT_STAGE] == -1 and shinx[Pok.ATTACK_STAT_STAGE] == -1


def test_foe_entering_skips_the_trace_retry(poke):
    """Both entering together: the second switch_in does the copy, so nothing fires twice"""
    ralts = poke("Ralts", 20, "Trace", ["Growl"])
    shinx = poke("Shinx", 20, "Intimidate", ["Tackle"])
    arr = empty_field()
    switch_in(shinx, ralts, arr, False, True)
    assert ralts[Pok.AB_ID] == AbilityNames.TRACE
    switch_in(ralts, shinx, arr, True)
    assert ralts[Pok.ATTACK_STAT_STAGE] == -1 and shinx[Pok.ATTACK_STAT_STAGE] == -1


def test_trace_cures_a_status_the_copy_forbids(poke):
    """pokeplatinum SWITCH_IN_CHECK_STATE_FORBIDDEN_STATUS after Trace copies Limber"""
    me = poke("Ralts", 20, "Trace", ["Growl"])
    me[Pok.STATUS] = Status.PARALYSIS
    foe = poke("Buneary", 20, "Limber", ["Tackle"])
    switch_in(me, foe, empty_field(), True)
    assert me[Pok.STATUS] == 0


@pytest.mark.parametrize("ability, status, vol, cured", [
    ("Insomnia", Status.SLEEP, 0, True),
    ("Immunity", Status.TOXIC, 0, True),
    ("Water Veil", Status.BURN, 0, True),
    ("Magma Armor", Status.FREEZE, 0, True),
    ("Limber", Status.BURN, 0, False),
    ("Own Tempo", 0, VolStatus.CONFUSION, True),
    ("Oblivious", 0, VolStatus.ATTRACT, True),
])
def test_recover_status_by_ability(poke, ability, status, vol, cured):
    """pokeplatinum BattleSystem_RecoverStatusByAbility"""
    p = poke("Rattata", 20, ability, ["Tackle"])
    p[Pok.STATUS] = status
    p[Pok.VOL_STATUS] = vol
    recover_status_by_ability(p)
    assert (p[Pok.STATUS] == 0 and p[Pok.VOL_STATUS] == 0) == cured


@pytest.mark.parametrize("def_stage, spd_stage, boosted", [
    (0, 0, Pok.SPECIAL_ATTACK_STAT_STAGE),
    (-6, 0, Pok.ATTACK_STAT_STAGE),
    (0, -6, Pok.SPECIAL_ATTACK_STAT_STAGE),
])
def test_download(poke, def_stage, spd_stage, boosted):
    """pokeplatinum: Defense >= Sp. Def (with stages) raises Sp. Atk, otherwise Attack"""
    me = poke("Porygon", 20, "Download", ["Tackle"])
    foe = poke("Rattata", 20, "Run Away", ["Tackle"])
    foe[Pok.DEFENSE] = foe[Pok.SPECIAL_DEFENSE] = 40
    foe[Pok.DEFENSE_STAT_STAGE], foe[Pok.SPECIAL_DEFENSE_STAT_STAGE] = def_stage, spd_stage
    switch_in(me, foe, empty_field(), True)
    other = (Pok.ATTACK_STAT_STAGE if boosted == Pok.SPECIAL_ATTACK_STAT_STAGE
             else Pok.SPECIAL_ATTACK_STAT_STAGE)
    assert me[boosted] == 1 and me[other] == 0


def test_download_does_nothing_against_a_fainted_foe(poke):
    """No alive foe, no boost"""
    me = poke("Porygon", 20, "Download", ["Tackle"])
    foe = poke("Rattata", 20, "Run Away", ["Tackle"])
    foe[Pok.CURRENT_HP] = 0
    download(me, foe)
    assert me[Pok.ATTACK_STAT_STAGE] == me[Pok.SPECIAL_ATTACK_STAT_STAGE] == 0


@pytest.mark.parametrize("ability, knows", [
    ("Pressure", True), ("Mold Breaker", True), ("Intimidate", False), ("Download", False),
])
def test_switch_in_announcements_tell_the_ai(poke, ability, knows):
    """Pressure's and Mold Breaker's switch-in messages name the ability, Intimidate's and
    Download's are built in C and don't (pokeplatinum BattleMessage_AbilityTag)"""
    p = poke("Pinsir", 20, ability, ["Tackle"])
    foe = poke("Rattata", 20, "Run Away", ["Tackle"])
    switch_in(p, foe, empty_field(), True)
    assert bool(p[Pok.AB_KNOWN]) == knows


@pytest.mark.parametrize("species, foe_moves, foe_level, knows", [
    ("Croagunk", ["Tackle", "Confusion"], 20, True),
    ("Croagunk", ["Tackle", "Water Gun"], 20, False),
    ("Croagunk", ["Psywave"], 20, False),
    ("Croagunk", ["Hypnosis"], 20, False),
    ("Barboach", ["Guillotine"], 20, True),
    ("Barboach", ["Guillotine"], 19, False),
])
def test_anticipation_shudder_tells_the_ai(poke, species, foe_moves, foe_level, knows):
    """The shudder names the ability and shows only for a super-effective damaging move (not
    fixed damage) or an OHKO move from a foe at the holder's level or higher (pokeplatinum
    SWITCH_IN_CHECK_STATE_ANTICIPATION)"""
    p = poke(species, 20, "Anticipation", ["Tackle"])
    foe = poke("Abra", foe_level, "Synchronize", foe_moves)
    switch_in(p, foe, empty_field(), True)
    assert bool(p[Pok.AB_KNOWN]) == knows


@pytest.mark.parametrize("foe_hp, knows", [(1, True), (0, False)])
def test_forewarn_alert_tells_the_ai(poke, foe_hp, knows):
    """Forewarn names a move of any foe that's out (pokeplatinum SWITCH_IN_CHECK_STATE_FOREWARN)"""
    p = poke("Drowzee", 20, "Forewarn", ["Pound"])
    foe = poke("Rattata", 20, "Run Away", ["Tackle"])
    foe[Pok.CURRENT_HP] = foe_hp
    switch_in(p, foe, empty_field(), True)
    assert bool(p[Pok.AB_KNOWN]) == knows


def test_frisk_doesnt_tell_the_ai(poke):
    """Frisk's message names the item, not the ability"""
    p = poke("Stantler", 20, "Frisk", ["Tackle"])
    foe = poke("Rattata", 20, "Run Away", ["Tackle"])
    switch_in(p, foe, empty_field(), True)
    assert not p[Pok.AB_KNOWN]


@pytest.mark.parametrize("move, ability, extra", [
    ("Tackle", "Pressure", 1), ("Stealth Rock", "Pressure", 1), ("Rain Dance", "Pressure", 1),
    ("Harden", "Pressure", 0), ("Metronome", "Pressure", 0), ("Tackle", "Run Away", 0),
])
def test_pressure_pp(poke, move, ability, extra):
    """pokeplatinum BattleControllerPlayer_DecrementPP: +1 unless the move aims at the user's side"""
    a = poke("Togepi", 20, "Hustle", [move])
    d = poke("Murkrow", 20, ability, ["Tackle"])
    mv = move_slice(a, 0)
    pp = int(mv[Move.PP])
    pressure_pp(mv, d)
    assert mv[Move.PP] == pp - extra


def test_pressure_pp_stops_at_zero_and_needs_alive_holder(poke):
    """No PP below 0, a fainted Pressure holder costs nothing"""
    a = poke("Rattata", 20, "Run Away", ["Tackle"])
    d = poke("Murkrow", 20, "Pressure", ["Tackle"])
    mv = move_slice(a, 0)
    mv[Move.PP] = 0
    pressure_pp(mv, d)
    assert mv[Move.PP] == 0
    mv[Move.PP] = 5
    d[Pok.CURRENT_HP] = 0
    pressure_pp(mv, d)
    assert mv[Move.PP] == 5


# ── Items ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("item, missing, healed", [
    (Potions.POTION, 30, 20), (Potions.POTION, 5, 5),
    (Potions.SUPER_POTION, 80, 50), (Potions.HYPER_POTION, 120, 120),
])
def test_trainer_potions(poke, item, missing, healed):
    """Potions heal a fixed amount, never past max"""
    p = poke("Geodude", 100, "Sturdy", ["Tackle"])
    p[Pok.CURRENT_HP] = p[Pok.MAX_HP] - missing
    trainer_ai_items(p, item)
    assert p[Pok.CURRENT_HP] == p[Pok.MAX_HP] - missing + healed


def test_full_restore_and_full_heal(poke):
    """Full Restore heals and cures; Full Heal only cures"""
    p = poke("Geodude", 50, "Sturdy", ["Tackle"])
    p[Pok.CURRENT_HP] = 1
    p[Pok.STATUS] = Status.TOXIC
    p[Pok.BADLY_POISON] = 3
    trainer_ai_items(p, Potions.FULL_HEAL)
    assert p[Pok.STATUS] == 0 and p[Pok.BADLY_POISON] == 0 and p[Pok.CURRENT_HP] == 1
    p[Pok.STATUS] = Status.BURN
    trainer_ai_items(p, Potions.FULL_RESTORE)
    assert p[Pok.STATUS] == 0 and p[Pok.CURRENT_HP] == p[Pok.MAX_HP]


@pytest.mark.parametrize("item, stage", [
    (Potions.X_DEFEND, Pok.DEFENSE_STAT_STAGE),
    (Potions.X_SPECIAL, Pok.SPECIAL_ATTACK_STAT_STAGE),
    (Potions.X_SPEED, Pok.SPEED_STAT_STAGE),
])
def test_x_items_raise_one_stage_capped(poke, item, stage):
    """X items +1 stage, max +6"""
    p = poke("Geodude", 50, "Sturdy", ["Tackle"])
    trainer_ai_items(p, item)
    assert p[stage] == 1
    p[stage] = 6
    trainer_ai_items(p, item)
    assert p[stage] == 6


def test_oran_berry_at_half_hp(poke):
    """Oran Berry: +10 HP at <= 50% and is consumed; nothing above 50%"""
    p = poke("Geodude", 50, "Sturdy", ["Tackle"], item="Oran Berry")
    p[Pok.CURRENT_HP] = p[Pok.MAX_HP] // 2 + 1
    eat_berry(p)
    assert p[Item.ID] == ItemNames.ORAN_BERRY
    p[Pok.CURRENT_HP] = p[Pok.MAX_HP] // 2
    eat_berry(p)
    assert p[Pok.CURRENT_HP] == p[Pok.MAX_HP] // 2 + 10
    assert not p[Item.ID:].any()


def test_sitrus_berry_quarter_heal(poke):
    """Sitrus Berry heals 1/4 max HP"""
    p = poke("Geodude", 50, "Sturdy", ["Tackle"], item="Sitrus Berry")
    p[Pok.CURRENT_HP] = 5
    eat_berry(p)
    assert p[Pok.CURRENT_HP] == 5 + p[Pok.MAX_HP] // 4


def test_fainted_pokemon_doesnt_eat_its_berry(poke):
    """pokeplatinum BattleSystem_TriggerHeldItem needs HP left: no revive from 0"""
    p = poke("Geodude", 50, "Sturdy", ["Tackle"], item="Sitrus Berry")
    p[Pok.CURRENT_HP] = 0
    item_on_rdmg(p)
    assert p[Pok.CURRENT_HP] == 0 and p[Item.ID] == ItemNames.SITRUS_BERRY


def test_sitrus_berry_heals_at_least_one(poke):
    """Sitrus heals maxHP * 25 / 100 through BattleSystem_Divide, which never rounds to 0"""
    p = poke("Geodude", 50, "Sturdy", ["Tackle"], item="Sitrus Berry")
    p[Pok.MAX_HP], p[Pok.CURRENT_HP] = 3, 1
    eat_berry(p)
    assert p[Pok.CURRENT_HP] == 2


def test_berry_juice_heals_20(poke):
    """Berry Juice isn't a berry but shares HP_RESTORE with Oran: +20 at <= 50%, used up"""
    p = poke("Geodude", 50, "Sturdy", ["Tackle"], item="Berry Juice")
    p[Pok.CURRENT_HP] = p[Pok.MAX_HP] // 2
    item_on_rdmg(p)
    assert p[Pok.CURRENT_HP] == p[Pok.MAX_HP] // 2 + 20
    assert p[Item.ID] == 0 and p[Pok.CONSUMED_ITEM] == ItemNames.BERRY_JUICE


def test_bug_bite_gives_berry_to_attacker(poke):
    """Bug Bite: the biter heals by the target's berry (its own max HP for Sitrus), the target
    loses it and can't recycle it"""
    atk = poke("Kricketune", 50, "Swarm", ["Bug Bite"])
    dfn = poke("Geodude", 50, "Sturdy", ["Tackle"], item="Sitrus Berry")
    atk[Pok.CURRENT_HP] = 10
    eat_berry_bug_bite(atk, dfn)
    assert atk[Pok.CURRENT_HP] == 10 + atk[Pok.MAX_HP] // 4
    assert dfn[Item.ID] == 0 and dfn[Pok.CONSUMED_ITEM] == 0


@pytest.mark.parametrize("defender_ab, attacker_ab, applies", [
    ("Levitate", "Mold Breaker", False),
    ("Levitate", "Blaze", True),
    ("Intimidate", "Mold Breaker", True),
])
def test_ignorable_ability(poke, defender_ab, attacker_ab, applies):
    """Mold Breaker ignores breakable abilities only"""
    dfn = poke("Geodude", 50, defender_ab, ["Tackle"])
    atk = poke("Geodude", 50, attacker_ab, ["Tackle"])
    assert bool(ignorable_ability(dfn, atk)) == applies


def test_drain_half_with_minimum_one(poke):
    """Absorb heals half the damage dealt, at least 1, capped at max"""
    p = poke("Oddish", 50, "Chlorophyll", ["Absorb"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    absorb = move_slice(p, 0)
    p[Pok.CURRENT_HP] = 10
    drain(p, d, absorb, 20)
    assert p[Pok.CURRENT_HP] == 20
    drain(p, d, absorb, 1)
    assert p[Pok.CURRENT_HP] == 21
    drain(p, d, absorb, 10_000)
    assert p[Pok.CURRENT_HP] == p[Pok.MAX_HP]


def test_drain_never_heals_a_fainted_user(poke):
    """A drainer at 0 HP stays fainted, whatever path reaches drain()"""
    p = poke("Oddish", 50, "Chlorophyll", ["Absorb"])
    p[Pok.CURRENT_HP] = 0
    drain(p, poke("Rattata", 50, "Run Away", ["Tackle"]), move_slice(p, 0), 20)
    assert p[Pok.CURRENT_HP] == 0


def test_struggle_recoil(poke):
    """Struggle recoil is 1/4 max HP, rec=False leaves the user alone"""
    a = poke("Rattata", 50, "Run Away", ["Tackle"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    hp = a[Pok.CURRENT_HP]
    assert struggle(a, d, rec=False) > 0
    assert a[Pok.CURRENT_HP] == hp
    struggle(a, d)
    assert a[Pok.CURRENT_HP] == hp - a[Pok.MAX_HP] // 4


# ── Residual / weather ───────────────────────────────────────────────────────

@pytest.mark.parametrize("name, ability, weather, fraction", [
    ("Rattata", "Run Away", Weather.SANDSTORM, 16),
    ("Geodude", "Sturdy", Weather.SANDSTORM, 0),
    ("Rattata", "Sand Veil", Weather.SANDSTORM, 0),
    ("Rattata", "Run Away", Weather.HAIL, 16),
    ("Snover", "Snow Warning", Weather.HAIL, 0),
    ("Charmander", "Solar Power", Weather.SUN, 8),
    ("Charmander", "Blaze", Weather.SUN, 0),
    ("Rattata", "Run Away", Weather.RAIN, 0),
    ("Rattata", "Snow Cloak", Weather.HAIL, 0),
    ("Rattata", "Ice Body", Weather.HAIL, 0),
    ("Paras", "Dry Skin", Weather.SUN, 8),
    ("Paras", "Dry Skin", Weather.RAIN, 0),
])
def test_weather_damage(poke, name, ability, weather, fraction):
    """Sandstorm/Hail chip 1/16 unless immune (Snow Cloak, Ice Body); Solar Power and Dry Skin
    cost 1/8 in sun"""
    p = poke(name, 100, ability, ["Tackle"])
    expected = p[Pok.MAX_HP] // fraction if fraction else 0
    assert weather_dmg(p, weather, p[Pok.MAX_HP]) == expected


@pytest.mark.parametrize("weather", [Weather.SANDSTORM, Weather.HAIL, Weather.SUN])
def test_weather_damage_is_at_least_one(poke, weather):
    """pokeplatinum BattleSystem_Divide never gives 0"""
    p = poke("Rattata", 100, "Solar Power", ["Tackle"])
    assert weather_dmg(p, weather, 7) == 1


@pytest.mark.parametrize("ability, weather, fraction, underground", [
    ("Rain Dish", Weather.RAIN, 16, False),
    ("Dry Skin", Weather.RAIN, 8, False),
    ("Dry Skin", Weather.RAIN, 8, True),
    ("Ice Body", Weather.HAIL, 16, False),
    ("Ice Body", Weather.HAIL, 0, True),
    ("Ice Body", Weather.RAIN, 0, False),
    ("Dry Skin", Weather.SUN, 0, False),
])
def test_weather_heals(poke, ability, weather, fraction, underground):
    """Rain Dish 1/16 and Dry Skin 1/8 in rain, Ice Body 1/16 in hail but not underground
    (pokeplatinum BtlCmd_EndOfTurnWeatherEffect)"""
    p = poke("Paras", 100, ability, ["Tackle"])
    p[Pok.CURRENT_HP] = 50
    heal_weather(p, weather, underground)
    assert p[Pok.CURRENT_HP] == 50 + (p[Pok.MAX_HP] // fraction if fraction else 0)
    assert bool(p[Pok.AB_KNOWN]) == bool(fraction)


def test_weather_heal_is_at_least_one(poke):
    """A heal below 1 HP rounds up to 1"""
    p = poke("Lotad", 100, "Rain Dish", ["Absorb"])
    p[Pok.MAX_HP] = 10
    p[Pok.CURRENT_HP] = 5
    heal_weather(p, Weather.RAIN)
    assert p[Pok.CURRENT_HP] == 6


def test_rain_dish(poke):
    """Rain Dish heals 1/16 in rain, never past max"""
    p = poke("Lotad", 100, "Rain Dish", ["Absorb"])
    p[Pok.CURRENT_HP] = 50
    heal_weather(p, Weather.RAIN)
    assert p[Pok.CURRENT_HP] == 50 + p[Pok.MAX_HP] // 16
    heal_weather(p, Weather.SUN)
    assert p[Pok.CURRENT_HP] == 50 + p[Pok.MAX_HP] // 16
    p[Pok.CURRENT_HP] = p[Pok.MAX_HP]
    heal_weather(p, Weather.RAIN)
    assert p[Pok.CURRENT_HP] == p[Pok.MAX_HP]


def test_speed_boost_not_on_entry_turn(poke):
    """Speed Boost +1 at end of turn, skipped on the turn it switched in"""
    p = poke("Ninjask", 50, "Speed Boost", ["Scratch"])
    on_residual(p, 1)
    assert p[Pok.SPEED_STAT_STAGE] == 0
    on_residual(p, 0)
    assert p[Pok.SPEED_STAT_STAGE] == 1


def test_fire_move_thaws(poke):
    """Being hit by a Fire move thaws"""
    a = poke("Charmander", 50, "Blaze", ["Ember", "Scratch"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    d[Pok.STATUS] = Status.FREEZE
    assert not thaw(a, move_slice(a, 1), d) and d[Pok.STATUS] == Status.FREEZE
    assert thaw(a, move_slice(a, 0), d) and d[Pok.STATUS] == 0


# ── early_returns (the "can I act this turn" gate) ───────────────────────────

def test_sleep_blocks_until_counter_runs_out(poke):
    """The counter drops first: still above 0 it's blocked, at 0 it wakes and acts (pokeplatinum
    CHECK_STATUS_STATE_SLEEP), so a counter of 2 sleeps one turn"""
    a = poke("Rattata", 50, "Run Away", ["Tackle"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    mv = move_slice(a, 0)
    a[Pok.STATUS] = Status.SLEEP
    a[Pok.SLEEP_COUNTER] = 2
    assert early_returns(a, d, 1, False, mv)
    assert a[Pok.SLEEP_COUNTER] == 1
    assert not early_returns(a, d, 1, False, mv)
    assert a[Pok.STATUS] == 0 and a[Pok.SLEEP_COUNTER] == 0


def test_flinch_only_for_second_mover(poke):
    """Flinch only stops the Pokemon moving second"""
    a = poke("Rattata", 50, "Run Away", ["Tackle"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    mv = move_slice(a, 0)
    assert not early_returns(a, d, 1, True, mv)
    assert early_returns(a, d, 2, True, mv)


def test_steadfast_boosts_the_flinched_pokemon(poke):
    """Regression: Steadfast raises Speed of the Pokemon that flinched, not the other one"""
    flinched = poke("Riolu", 50, "Steadfast", ["Tackle"])
    other = poke("Rattata", 50, "Run Away", ["Tackle"])
    assert early_returns(flinched, other, 2, True, move_slice(flinched, 0))
    assert flinched[Pok.SPEED_STAT_STAGE] == 1
    assert other[Pok.SPEED_STAT_STAGE] == 0
    other_flinched = poke("Rattata", 50, "Run Away", ["Tackle"])
    steadfast_foe = poke("Riolu", 50, "Steadfast", ["Tackle"])
    early_returns(other_flinched, steadfast_foe, 2, True, move_slice(other_flinched, 0))
    assert steadfast_foe[Pok.SPEED_STAT_STAGE] == 0 == other_flinched[Pok.SPEED_STAT_STAGE]


def test_confusion_wears_off(poke):
    """Confusion counter ticks down and the volatile is removed at 0"""
    a = poke("Rattata", 50, "Run Away", ["Tackle"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    a[Pok.VOL_STATUS] = VolStatus.CONFUSION
    a[Pok.CONFUSION_COUNTER] = 1
    assert not early_returns(a, d, 1, False, move_slice(a, 0))
    assert not a[Pok.VOL_STATUS] & VolStatus.CONFUSION


def test_full_paralysis_rate_and_magic_guard(poke):
    """~25% full paralysis; Magic Guard (Gen IV) never fully paralyzed"""
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    a = poke("Rattata", 50, "Run Away", ["Tackle"])
    a[Pok.STATUS] = Status.PARALYSIS
    n = 8000
    rate = sum(bool(early_returns(a, d, 1, False, move_slice(a, 0))) for _ in range(n)) / n
    assert rate == pytest.approx(0.25, abs=0.02)
    guard = poke("Clefairy", 50, "Magic Guard", ["Pound"])
    guard[Pok.STATUS] = Status.PARALYSIS
    assert not any(early_returns(guard, d, 1, False, move_slice(guard, 0)) for _ in range(200))


def test_counter_needs_damage_and_to_move_second(poke):
    """Counter fails moving first or without damage taken"""
    a = poke("Machop", 50, "Guts", ["Counter"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    mv = move_slice(a, 0)
    assert not early_returns(a, d, 2, False, mv)
    assert counter_fails(a, mv, 2)
    a[Pok.DMG_TAKEN] = 20
    assert counter_fails(a, mv, 1)
    assert not counter_fails(a, mv, 2)


def test_random_is_seeded_per_test():
    """Sanity check for the autouse seed fixture in conftest"""
    first = random.random()
    random.seed(1234)
    assert random.random() == first



@pytest.mark.parametrize("move, target", [
    ("Growl", "Gastly"),        # Normal status move into Ghost
    ("Leer", "Gastly"),
    ("Sand Attack", "Pidgey"),  # Ground status move into Flying
])
def test_status_moves_ignore_type_immunity(poke, move, target):
    """Showdown: ignoreImmunity defaults to true for Status moves"""
    a = poke("Rattata", 50, "Run Away", [move])
    d = poke(target, 50, "Run Away", ["Tackle"])
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == MoveOutcome.HIT


def test_thunder_wave_respects_ground_immunity(poke):
    """Thunder Wave sets ignoreImmunity: false, so Ground types are immune"""
    a = poke("Pikachu", 50, "Static", ["Thunder Wave"])
    d = poke("Geodude", 50, "Sturdy", ["Tackle"])
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == MoveOutcome.INVULNERABLE


def test_flinch_checker_second_slot(poke):
    """Fire Fang's flinch lives in the second secondary slot"""
    a = poke("Growlithe", 50, "Intimidate", ["Fire Fang"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    mv = move_slice(a, 0).copy()
    mv[Sec.CHANCE] = 0
    mv[Sec.CHANCE2] = 100
    assert flinch_checker(mv, a, d, True)
    assert not flinch_checker(mv, a, d)
    d2 = poke("Rattata", 50, "Inner Focus", ["Tackle"])
    assert not flinch_checker(mv, a, d2, True)


# ── Phase 2: semi-invulnerability, locks, recoil, Struggle ──────────────────

def test_airborne_target_dodges_all_but_gust(poke):
    """Bounce's airborne turn: aimed moves miss, Gust still hits, self moves still work"""
    a = poke("Pidgey", 50, "Keen Eye", ["Tackle", "Gust", "Growl", "Harden"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    d[Pok.VOL_STATUS] = VolStatus.SEMI_INVULNERABLE
    d[Pok.SEMI_INV_MOVE] = MoveName.BOUNCE
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == MoveOutcome.SEMI_INVULNERABLE
    assert calculate_hit_miss(move_slice(a, 1), a, d, 0) == MoveOutcome.HIT
    assert calculate_hit_miss(move_slice(a, 2), a, d, 0) == MoveOutcome.SEMI_INVULNERABLE
    assert calculate_hit_miss(move_slice(a, 3), a, d, 0) == MoveOutcome.HIT


@pytest.mark.parametrize("block", ["paralysis", "flinch", "confusion", "sleep"])
def test_blocked_turn_ends_charge_and_lock(monkeypatch, poke, block):
    """pokeplatinum UnlockMoveChoice on full paralysis, flinch, confusion self-hit and sleep"""
    a = poke("Pidgey", 50, "Keen Eye", ["Bounce"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    a[Pok.CHARGE_RECHARGE] = 1
    a[Pok.LOCKED_MOVE] = 0
    a[Pok.CONSEC_COUNT] = 3
    a[Pok.VOL_STATUS] = VolStatus.SEMI_INVULNERABLE
    flinch = block == "flinch"
    if block == "paralysis":
        a[Pok.STATUS] = Status.PARALYSIS
        monkeypatch.setattr(engine_helper, "paralysis", lambda: True)
    elif block == "confusion":
        a[Pok.VOL_STATUS] |= VolStatus.CONFUSION
        a[Pok.CONFUSION_COUNTER] = 3
        monkeypatch.setattr(random, "getrandbits", lambda n: 1)
    elif block == "sleep":
        a[Pok.STATUS] = Status.SLEEP
        a[Pok.SLEEP_COUNTER] = 2
    assert early_returns(a, d, 2, flinch, move_slice(a, 0))
    assert a[Pok.LOCKED_MOVE] == -1
    assert a[Pok.CHARGE_RECHARGE] == a[Pok.CONSEC_COUNT] == 0
    assert not a[Pok.VOL_STATUS] & VolStatus.SEMI_INVULNERABLE


def test_freeze_keeps_the_lock(monkeypatch, poke):
    """subscript_frozen has no UnlockMoveChoice, so a frozen Rollout user stays locked"""
    a = poke("Geodude", 50, "Sturdy", ["Rollout"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    a[Pok.LOCKED_MOVE] = 0
    a[Pok.CONSEC_COUNT] = 2
    a[Pok.STATUS] = Status.FREEZE
    monkeypatch.setattr(engine_helper, "freeze", lambda: True)
    assert early_returns(a, d, 1, False, move_slice(a, 0))
    assert a[Pok.LOCKED_MOVE] == 0 and a[Pok.CONSEC_COUNT] == 2


def test_unlock_leaves_bide_alone(poke):
    """Bide keeps its own pause rule"""
    a = poke("Geodude", 50, "Sturdy", ["Bide"])
    a[Pok.VOL_STATUS] = VolStatus.BIDE
    a[Pok.CHARGE_RECHARGE] = 2
    a[Pok.LOCKED_MOVE] = 0
    unlock_move(a)
    assert a[Pok.CHARGE_RECHARGE] == 2 and a[Pok.LOCKED_MOVE] == 0


def test_reset_switch_out_clears_phase2_state(poke):
    """Switching out drops the Rollout/Fury Cutter count and the airborne/hurt bits"""
    p = poke("Geodude", 50, "Sturdy", ["Rollout"])
    p[Pok.CONSEC_COUNT] = 4
    p[Pok.VOL_STATUS] = VolStatus.SEMI_INVULNERABLE | VolStatus.HURT_THIS_TURN
    reset_switch_out(p)
    assert p[Pok.CONSEC_COUNT] == 0 and p[Pok.VOL_STATUS] == 0


def _struggle(a, d):
    random.seed(7)
    return struggle(a, d, rec=False)


def test_struggle_uses_attack_abilities(poke):
    """Struggle goes through the normal formula: Huge Power, Guts (no burn halving), Hustle"""
    d = poke("Geodude", 50, "Sturdy", ["Tackle"])
    base = _struggle(poke("Rattata", 50, "Run Away", ["Tackle"]), d)
    assert _struggle(poke("Rattata", 50, "Huge Power", ["Tackle"]), d) > base * 1.8
    assert _struggle(poke("Rattata", 50, "Hustle", ["Tackle"]), d) > base * 1.3
    guts = poke("Rattata", 50, "Guts", ["Tackle"])
    guts[Pok.STATUS] = Status.BURN
    burned = poke("Rattata", 50, "Run Away", ["Tackle"])
    burned[Pok.STATUS] = Status.BURN
    assert _struggle(guts, d) > base * 1.3
    assert _struggle(burned, d) < base * 0.6


@pytest.mark.parametrize("dealt, recoil", [(0, 0), (1, 1), (3, 1), (4, 1), (8, 2), (99, 24)])
def test_take_down_recoil(poke, dealt, recoil):
    """A quarter of the HP the target lost, at least 1"""
    a = poke("Rattata", 50, "Run Away", ["Take Down"])
    assert move_recoil(move_slice(a, 0), dealt) == recoil


def test_recoil_marks_hurt_and_faints(poke):
    """Recoil counts as HP lost this turn and can make the user faint"""
    a = poke("Rattata", 50, "Run Away", ["Take Down"])
    hp = a[Pok.CURRENT_HP]
    apply_recoil(a, 5)
    assert a[Pok.CURRENT_HP] == hp - 5 and a[Pok.VOL_STATUS] & VolStatus.HURT_THIS_TURN
    apply_recoil(a, 10_000)
    assert a[Pok.CURRENT_HP] == 0


def test_natural_gift_uses_berry(poke, make_pokemon):
    """Type and power from the berry (Gen IV 60), the berry is used up and remembered"""
    a = make_pokemon("Rattata", 50, "Run Away", ["Natural Gift"], item="Sitrus Berry").to_np()
    mv = move_slice(a, 0)
    assert natural_gift(a, mv)
    assert (mv[Move.TYPE], mv[Move.POWER]) == (Types.PSYCHIC, 60)
    assert a[Pok.ITEM_ID] == 0 and a[Pok.CONSUMED_ITEM] == ItemNames.SITRUS_BERRY
    assert not natural_gift(a, mv)
    assert not natural_gift(poke("Rattata", 50, "Run Away", ["Natural Gift"]), mv)


# ── Phase 3: Protect, Endure, Foresight, Ingrain, Destiny Bond, Attract ─────────

def test_protect_success_chance_halves_and_caps(poke):
    """1, 1/2, 1/4, then 1/8 for every further consecutive use"""
    p = poke("Rattata", 20, "Run Away", ["Protect"])
    n = 20_000
    for count, expected in [(1, 0.5), (2, 0.25), (3, 0.125)]:
        hits = 0
        for _ in range(n):
            p[Pok.PROTECT_COUNT] = count
            p[Pok.VOL_STATUS] = 0
            try_protect(p, MoveName.PROTECT, False)
            hits += bool(p[Pok.VOL_STATUS] & VolStatus.PROTECT)
        assert hits / n == pytest.approx(expected, abs=0.015)


def test_protect_count_and_failure(poke):
    """A success counts up to 3, failing (also by moving last) resets the count"""
    p = poke("Rattata", 20, "Run Away", ["Protect"])
    try_protect(p, MoveName.PROTECT, False)
    assert p[Pok.VOL_STATUS] & VolStatus.PROTECT and p[Pok.PROTECT_COUNT] == 1
    p[Pok.PROTECT_COUNT] = 3
    p[Pok.VOL_STATUS] = 0
    random.seed(0)
    while not p[Pok.VOL_STATUS] & VolStatus.PROTECT:
        p[Pok.PROTECT_COUNT] = 3
        try_protect(p, MoveName.PROTECT, False)
    assert p[Pok.PROTECT_COUNT] == 3
    p[Pok.VOL_STATUS] = 0
    try_protect(p, MoveName.PROTECT, True)
    assert not p[Pok.VOL_STATUS] & VolStatus.PROTECT and p[Pok.PROTECT_COUNT] == 0


def test_endure_sets_its_own_bit(poke):
    """Endure shares the count with Protect but marks ENDURE"""
    p = poke("Rattata", 20, "Run Away", ["Endure"])
    try_protect(p, MoveName.ENDURE, False)
    assert p[Pok.VOL_STATUS] == VolStatus.ENDURE and p[Pok.PROTECT_COUNT] == 1


@pytest.mark.parametrize("move, outcome", [("Tackle", MoveOutcome.PROTECTED), ("Feint", MoveOutcome.HIT)])
def test_protect_blocks_flagged_moves(poke, move, outcome):
    """Only moves with the protect flag are blocked"""
    a = poke("Rattata", 20, "Run Away", [move])
    d = poke("Rattata", 20, "Run Away", ["Protect"])
    d[Pok.VOL_STATUS] = VolStatus.PROTECT
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == outcome


def test_foresight_lets_normal_hit_ghost_and_ignores_evasion(poke):
    """Ghost loses its Normal immunity, positive evasion counts as 0"""
    a = poke("Rattata", 20, "Run Away", ["Tackle"])
    d = poke("Gastly", 20, "Levitate", ["Lick"])
    mv = move_slice(a, 0)
    assert calculate_hit_miss(mv, a, d, 0) == MoveOutcome.INVULNERABLE
    d[Pok.VOL_STATUS] = VolStatus.FORESIGHT
    d[Pok.EVASION_STAT_STAGE] = 6
    assert all(calculate_hit_miss(mv, a, d, 0) == MoveOutcome.HIT for _ in range(50))


def test_ingrain_grounds_flying_types(poke):
    """An Ingrained Flying type can be hit by Ground moves"""
    a = poke("Geodude", 20, "Sturdy", ["Mud-Slap"])
    d = poke("Pidgey", 20, "Keen Eye", ["Tackle"])
    mv = move_slice(a, 0)
    assert calculate_hit_miss(mv, a, d, 0) == MoveOutcome.INVULNERABLE
    d[Pok.VOL_STATUS] = VolStatus.INGRAIN
    assert calculate_hit_miss(mv, a, d, 0) == MoveOutcome.HIT


@pytest.mark.parametrize("vol, hp, damage, expected", [
    (VolStatus.ENDURE, 10, 30, 9), (VolStatus.ENDURE, 10, 5, 5), (0, 10, 30, 30),
])
def test_endure_damage(poke, vol, hp, damage, expected):
    """Endure caps a would-be KO at current HP - 1"""
    d = poke("Rattata", 20, "Run Away", ["Endure"])
    d[Pok.VOL_STATUS] = vol
    d[Pok.CURRENT_HP] = hp
    assert endure_damage(d, damage) == expected


def test_destiny_bond_ends_when_user_tries_to_move(poke):
    """Cleared at the start of the user's next move attempt, even a blocked one"""
    a = poke("Gastly", 20, "Levitate", ["Lick"])
    d = poke("Rattata", 20, "Run Away", ["Tackle"])
    a[Pok.VOL_STATUS] = VolStatus.DESTINY_BOND
    a[Pok.STATUS] = Status.SLEEP
    a[Pok.SLEEP_COUNTER] = 2
    assert early_returns(a, d, 1, False, move_slice(a, 0))
    assert not a[Pok.VOL_STATUS] & VolStatus.DESTINY_BOND


@pytest.mark.parametrize("roll, blocked", [(1, True), (0, False)])
def test_attract_immobilizes_half_the_time(monkeypatch, poke, roll, blocked):
    """Infatuation blocks the move on a 50% roll"""
    a = poke("Rattata", 20, "Run Away", ["Tackle"])
    d = poke("Pikachu", 20, "Static", ["Tackle"])
    a[Pok.VOL_STATUS] = VolStatus.ATTRACT
    monkeypatch.setattr(engine_helper.random, "getrandbits", lambda k: roll)
    assert early_returns(a, d, 1, False, move_slice(a, 0)) == blocked


def test_switch_in_ends_foe_attract(poke):
    """The foe's infatuation was with the Pokemon that left"""
    new = poke("Rattata", 20, "Run Away", ["Tackle"])
    foe = poke("Pikachu", 20, "Static", ["Tackle"])
    foe[Pok.VOL_STATUS] = VolStatus.ATTRACT | VolStatus.CONFUSION
    switch_in(new, foe, empty_field(), True)
    assert foe[Pok.VOL_STATUS] == VolStatus.CONFUSION


def test_reset_switch_out_clears_phase3_counters(poke):
    """Protect's consecutive count and the Yawn countdown don't survive a switch"""
    p = poke("Rattata", 50, "Run Away", ["Protect"])
    p[Pok.PROTECT_COUNT] = 2
    p[Pok.YAWN_TURNS] = 1
    p[Pok.VOL_STATUS] = VolStatus.INGRAIN | VolStatus.YAWN
    reset_switch_out(p)
    assert p[Pok.PROTECT_COUNT] == p[Pok.YAWN_TURNS] == p[Pok.VOL_STATUS] == 0


# ── Phase 4 volatiles ────────────────────────────────────────────────────────

@pytest.mark.parametrize("vol, field, packed, blocked", [
    (VolStatus.DISABLE, Pok.DISABLE_TURNS, 3 * 4 + 1, [False, True, False]),
    (VolStatus.ENCORE, Pok.ENCORE_TURNS, 3 * 4 + 1, [True, False, True]),
    (VolStatus.TAUNT, Pok.TAUNT_TURNS, 3, [False, True, False]),
])
def test_move_blocked(poke, vol, field, packed, blocked):
    """Disable blocks its slot, Encore every other slot, Taunt the status moves (Growl)"""
    p = poke("Rattata", 20, "Run Away", ["Tackle", "Growl", "Quick Attack"])
    assert [move_blocked(p, i) for i in range(3)] == [False] * 3
    p[Pok.VOL_STATUS] = vol
    p[field] = packed
    assert [move_blocked(p, i) for i in range(3)] == blocked


@pytest.mark.parametrize("vol, field, packed, slot, blocked", [
    (VolStatus.DISABLE, Pok.DISABLE_TURNS, 3 * 4 + 0, 0, True),
    (VolStatus.DISABLE, Pok.DISABLE_TURNS, 3 * 4 + 0, 1, False),
    (VolStatus.TAUNT, Pok.TAUNT_TURNS, 3, 1, True),
    (VolStatus.TAUNT, Pok.TAUNT_TURNS, 3, 0, False),
])
def test_disable_and_taunt_stop_a_move_picked_before(poke, vol, field, packed, slot, blocked):
    """A move chosen before Disable/Taunt landed fails when the Pokemon tries it"""
    a = poke("Rattata", 20, "Run Away", ["Tackle", "Growl"])
    d = poke("Rattata", 20, "Run Away", ["Tackle"])
    a[Pok.VOL_STATUS] = vol
    a[field] = packed
    assert early_returns(a, d, 1, False, move_slice(a, slot)) == blocked


@pytest.mark.parametrize("ability, wakes", [("Run Away", True), ("Soundproof", False)])
def test_sleeper_wakes_when_moving_during_uproar(poke, ability, wakes):
    """During an uproar a sleeping Pokemon wakes up as it tries to move, unless Soundproof"""
    a = poke("Rattata", 20, ability, ["Tackle"])
    d = poke("Rattata", 20, "Run Away", ["Uproar"])
    a[Pok.STATUS] = Status.SLEEP
    a[Pok.SLEEP_COUNTER] = 3
    d[Pok.VOL_STATUS] = VolStatus.UPROAR
    assert early_returns(a, d, 1, False, move_slice(a, 0)) != wakes
    assert (a[Pok.STATUS] == 0) == wakes


def test_blocked_turn_ends_uproar_at_the_residual(poke):
    """unlock_move frees the lock and leaves the uproar one last tick"""
    p = poke("Rattata", 20, "Run Away", ["Uproar"])
    p[Pok.VOL_STATUS] = VolStatus.UPROAR
    p[Pok.UPROAR_TURNS] = 4
    p[Pok.LOCKED_MOVE] = 0
    unlock_move(p)
    assert (p[Pok.UPROAR_TURNS], p[Pok.LOCKED_MOVE]) == (1, -1)


def test_switch_in_frees_the_foe_from_the_bind(poke):
    """The bind ends when the binder leaves, other volatiles stay"""
    new = poke("Rattata", 20, "Run Away", ["Tackle"])
    foe = poke("Rattata", 20, "Run Away", ["Tackle"])
    foe[Pok.VOL_STATUS] = VolStatus.PARTIALLY_TRAPPED | VolStatus.CONFUSION
    switch_in(new, foe, empty_field(), True)
    assert foe[Pok.VOL_STATUS] == VolStatus.CONFUSION


def test_switch_out_clears_phase4_counters(poke):
    """Every Phase 4 counter and the last move reset on switch out"""
    p = poke("Rattata", 20, "Run Away", ["Tackle"])
    fields = (Pok.TRAP_TURNS, Pok.TAUNT_TURNS, Pok.ENCORE_TURNS, Pok.DISABLE_TURNS,
              Pok.UPROAR_TURNS, Pok.LAST_MOVE_ID)
    for f in fields:
        p[f] = 5
    reset_switch_out(p)
    assert all(p[f] == 0 for f in fields)


# ── Phase 5 Lucky Chant, hazards ─────────────────────────────────────────────

SR = SideCondition.STEALTH_ROCK
TSPIKES = SideCondition.TOXIC_SPIKES
MY_SIDE = Field.MY_SIDE_COND


def test_lucky_chant_blocks_crits(monkeypatch, poke):
    """A roll that would crit doesn't under Lucky Chant"""
    a = poke("Rattata", 20, "Run Away", ["Tackle"])
    d = poke("Rattata", 20, "Run Away", ["Tackle"])
    monkeypatch.setattr(engine_helper.random, "getrandbits", lambda k: 0)
    assert calculate_crit(a, d, move_slice(a, 0))
    assert not calculate_crit(a, d, move_slice(a, 0), SideCondition.LUCKY_CHANT)


@pytest.mark.parametrize("species, ability, divisor", [
    ("Butterfree", "Compound Eyes", 2),  # Bug/Flying, 4x
    ("Charmander", "Blaze", 4),
    ("Rattata", "Run Away", 8),
    ("Geodude", "Sturdy", 16),           # Rock/Ground, Ground resists
    ("Steelix", "Sturdy", 32),           # Steel/Ground, 1/4x
])
def test_stealth_rock_damage(poke, species, ability, divisor):
    """Max HP / 8 scaled by Rock effectiveness"""
    p = poke(species, 50, ability, ["Tackle"])
    assert stealth_rock_damage(p) == max(1, p[Pok.MAX_HP] // divisor)


def _field(cond, layers=0):
    arr = empty_field()
    arr[MY_SIDE] = cond
    arr[MY_SIDE + SIDE_TOXIC_SPIKES] = layers
    return arr


@pytest.mark.parametrize("layers, status", [(1, Status.POISON), (2, Status.TOXIC)])
def test_toxic_spikes_poison(poke, layers, status):
    """1 layer poisons, 2 badly poison"""
    p = poke("Rattata", 20, "Run Away", ["Tackle"])
    apply_hazards(p, _field(TSPIKES, layers), MY_SIDE)
    assert p[Pok.STATUS] == status


def test_grounded_poison_type_absorbs_toxic_spikes(poke):
    """A Poison type clears the spikes and isn't poisoned"""
    p = poke("Grimer", 20, "Stench", ["Pound"])
    arr = _field(TSPIKES, 2)
    apply_hazards(p, arr, MY_SIDE)
    assert p[Pok.STATUS] == 0
    assert arr[MY_SIDE] == 0 and arr[MY_SIDE + SIDE_TOXIC_SPIKES] == 0


@pytest.mark.parametrize("species, ability, cond", [
    ("Pidgey", "Keen Eye", TSPIKES),                         # not grounded
    ("Gastly", "Levitate", TSPIKES),
    ("Magnemite", "Sturdy", TSPIKES),                        # Steel
    ("Rattata", "Run Away", TSPIKES | SideCondition.SAFEGUARD),
])
def test_toxic_spikes_immunities(poke, species, ability, cond):
    """Flying, Levitate, Steel and Safeguard keep the Pokemon healthy, the spikes stay"""
    p = poke(species, 20, ability, ["Tackle"])
    arr = _field(cond, 1)
    apply_hazards(p, arr, MY_SIDE)
    assert p[Pok.STATUS] == 0 and arr[MY_SIDE] & TSPIKES


def test_toxic_spikes_poison_a_flying_iron_ball_holder(poke):
    """Iron Ball grounds the holder, so the spikes reach a Flying type"""
    p = poke("Pidgey", 20, "Keen Eye", ["Tackle"], item="Iron Ball")
    apply_hazards(p, _field(TSPIKES, 1), MY_SIDE)
    assert p[Pok.STATUS] == Status.POISON


def test_stealth_rock_hits_flying_types(poke):
    """Stealth Rock doesn't need the Pokemon grounded"""
    p = poke("Pidgey", 20, "Keen Eye", ["Tackle"])
    apply_hazards(p, _field(SR), MY_SIDE)
    assert p[Pok.CURRENT_HP] == p[Pok.MAX_HP] - stealth_rock_damage(p)


def test_magic_guard_skips_hazards(poke):
    """No rock damage and no poison for Magic Guard"""
    p = poke("Clefairy", 20, "Magic Guard", ["Pound"])
    apply_hazards(p, _field(SR | TSPIKES, 2), MY_SIDE)
    assert p[Pok.CURRENT_HP] == p[Pok.MAX_HP] and p[Pok.STATUS] == 0


def test_rock_faint_skips_switch_in_ability(poke):
    """A Pokemon that faints to the rocks doesn't Intimidate"""
    me = poke("Shinx", 20, "Intimidate", ["Tackle"])
    foe = poke("Rattata", 20, "Run Away", ["Tackle"])
    me[Pok.CURRENT_HP] = 1
    switch_in(me, foe, _field(SR), True)
    assert me[Pok.CURRENT_HP] == 0 and foe[Pok.ATTACK_STAT_STAGE] == 0


def test_mist_blocks_intimidate(poke):
    """Intimidate is a stat drop from the other side, Mist stops it"""
    me = poke("Shinx", 20, "Intimidate", ["Tackle"])
    foe = poke("Rattata", 20, "Run Away", ["Tackle"])
    arr = empty_field()
    arr[Field.OPP_SIDE_COND] = SideCondition.MIST
    switch_in(me, foe, arr, True)
    assert foe[Pok.ATTACK_STAT_STAGE] == 0


# ── Phase 7: healing, items, Worry Seed, Perish Song ─────────────────────────

@pytest.mark.parametrize("move, weather, num, den", [
    (MoveName.RECOVER, 0, 1, 2), (MoveName.RECOVER, Weather.RAIN, 1, 2),
    (MoveName.SYNTHESIS, 0, 1, 2), (MoveName.SYNTHESIS, Weather.SUN, 20, 30),
    (MoveName.SYNTHESIS, Weather.RAIN, 1, 4), (MoveName.SYNTHESIS, Weather.SANDSTORM, 1, 4),
    (MoveName.SYNTHESIS, Weather.HAIL, 1, 4),
])
def test_heal_move_amounts(poke, move, weather, num, den):
    """Recover 1/2, Synthesis 1/2, 2/3 in sun and 1/4 in rain, sand or hail, rounded down"""
    p = poke("Machop", 40, "Guts", ["Tackle"])
    p[Pok.CURRENT_HP] = 1
    heal_move(p, move, weather)
    assert p[Pok.CURRENT_HP] == 1 + p[Pok.MAX_HP] * num // den


def test_heal_move_caps_and_full_hp(poke):
    """Capped at max HP, nothing at full HP, at least 1"""
    p = poke("Machop", 40, "Guts", ["Tackle"])
    p[Pok.CURRENT_HP] = p[Pok.MAX_HP] - 1
    heal_move(p, MoveName.RECOVER, 0)
    assert p[Pok.CURRENT_HP] == p[Pok.MAX_HP]
    heal_move(p, MoveName.RECOVER, 0)
    assert p[Pok.CURRENT_HP] == p[Pok.MAX_HP]
    p[Pok.MAX_HP], p[Pok.CURRENT_HP] = 3, 1
    heal_move(p, MoveName.SYNTHESIS, Weather.RAIN)
    assert p[Pok.CURRENT_HP] == 2


@pytest.mark.parametrize("status, cured", [
    (Status.BURN, True), (Status.POISON, True), (Status.TOXIC, True), (Status.PARALYSIS, True),
    (Status.SLEEP, False), (Status.FREEZE, False),
])
def test_refresh(poke, status, cured):
    """Refresh cures burn, poison and paralysis, not sleep or freeze"""
    p = poke("Machop", 20, "Guts", ["Tackle"])
    p[Pok.STATUS] = status
    p[Pok.BADLY_POISON] = 3 if status == Status.TOXIC else 0
    refresh(p)
    assert (p[Pok.STATUS] == 0) == cured
    assert p[Pok.BADLY_POISON] == 0


def test_eaten_berry_can_be_recycled(poke):
    """The holder eating its berry makes it recyclable, Recycle restores the whole item block"""
    p = poke("Machop", 20, "Guts", ["Tackle"], item="Sitrus Berry")
    block = p[Item.ID:Item.EFFECT_TYPE + 1].copy()
    p[Pok.CURRENT_HP] = p[Pok.MAX_HP] // 2
    eat_berry(p)
    assert p[Item.ID] == 0 and p[Pok.CONSUMED_ITEM] == ItemNames.SITRUS_BERRY
    p[Pok.CURRENT_HP] = p[Pok.MAX_HP]
    recycle(p)
    assert (p[Item.ID:Item.EFFECT_TYPE + 1] == block).all() and p[Pok.CONSUMED_ITEM] == 0
    assert (ITEM_TABLE[ItemNames.SITRUS_BERRY] == block).all()


def test_recycle_fails_holding_an_item_or_with_nothing(poke):
    """Holding an item or nothing used up: no change"""
    p = poke("Machop", 20, "Guts", ["Tackle"], item="Oran Berry")
    p[Pok.CONSUMED_ITEM] = ItemNames.SITRUS_BERRY
    recycle(p)
    assert p[Item.ID] == ItemNames.ORAN_BERRY and p[Pok.CONSUMED_ITEM] == ItemNames.SITRUS_BERRY
    q = poke("Machop", 20, "Guts", ["Tackle"])
    recycle(q)
    assert q[Item.ID] == 0


def test_recycled_berry_is_eaten_at_low_hp(poke):
    """A berry restored at half HP or less is eaten right away"""
    p = poke("Machop", 20, "Guts", ["Tackle"])
    p[Pok.CONSUMED_ITEM] = ItemNames.ORAN_BERRY
    p[Pok.CURRENT_HP] = 5
    recycle(p)
    assert p[Pok.CURRENT_HP] == 15 and p[Item.ID] == 0
    assert p[Pok.CONSUMED_ITEM] == ItemNames.ORAN_BERRY


def test_carry_recycle_moves_the_item_to_the_slot(poke):
    """Gen IV: the Pokemon coming in gets the recyclable item, the one leaving loses it"""
    old = poke("Machop", 20, "Guts", ["Tackle"])
    new = poke("Rattata", 20, "Run Away", ["Tackle"])
    old[Pok.CONSUMED_ITEM] = ItemNames.ORAN_BERRY
    carry_recycle(old, new)
    assert old[Pok.CONSUMED_ITEM] == 0 and new[Pok.CONSUMED_ITEM] == ItemNames.ORAN_BERRY


@pytest.mark.parametrize("def_ab, atk_ab, removed", [
    ("Guts", "Run Away", True), ("Sticky Hold", "Run Away", False),
    ("Sticky Hold", "Mold Breaker", True),
])
def test_knock_off(poke, def_ab, atk_ab, removed):
    """Knock Off removes the item and marks the target, Sticky Hold stops it unless Mold Breaker.
    A knocked off item isn't recyclable"""
    a = poke("Murkrow", 20, atk_ab, ["Knock Off"])
    d = poke("Machop", 20, def_ab, ["Tackle"], item="Oran Berry")
    knock_off(a, d)
    assert (d[Item.ID] == 0) == removed
    assert d[Pok.ITEM_KNOCKED_OFF] == int(removed)
    assert d[Pok.CONSUMED_ITEM] == 0


def test_knock_off_leaves_a_griseous_orb(poke):
    """pokeplatinum subscript_knock_off fails on a Griseous Orb: no item lost, no mark"""
    a = poke("Murkrow", 20, "Insomnia", ["Knock Off"])
    d = poke("Rattata", 20, "Run Away", ["Tackle"], item="Griseous Orb")
    knock_off(a, d)
    assert d[Item.ID] == ItemNames.GRISEOUS_ORB
    assert d[Pok.ITEM_KNOCKED_OFF] == 0


def test_knock_off_without_an_item_does_nothing(poke):
    """No item: nothing to knock off, no mark"""
    a = poke("Murkrow", 20, "Insomnia", ["Knock Off"])
    d = poke("Machop", 20, "Guts", ["Tackle"])
    knock_off(a, d)
    assert d[Pok.ITEM_KNOCKED_OFF] == 0


def test_knocked_off_pokemon_loses_a_regained_item_on_switch_in(poke):
    """Gen IV: an item the knocked off Pokemon got back (Recycle) is gone when it comes in"""
    me = poke("Machop", 20, "Guts", ["Tackle"], item="Oran Berry")
    foe = poke("Rattata", 20, "Run Away", ["Tackle"])
    me[Pok.ITEM_KNOCKED_OFF] = 1
    switch_in(me, foe, empty_field(), True)
    assert me[Item.ID] == 0


@pytest.mark.parametrize("status", [0, Status.SLEEP])
def test_worry_seed_gives_insomnia_until_switch_out(poke, status):
    """Insomnia's whole ability block, a sleeper wakes, the base ability comes back on switch"""
    d = poke("Machop", 20, "Guts", ["Tackle"])
    d[Pok.STATUS] = status
    d[Pok.SLEEP_COUNTER] = 3 if status else 0
    guts = d[Pok.AB_ID:Pok.AB_BREAKABLE + 1].copy()
    assert worry_seed(d)
    assert (d[Pok.AB_ID:Pok.AB_BREAKABLE + 1] == ABILITY_TABLE[AbilityNames.INSOMNIA]).all()
    assert d[Pok.BASE_AB_ID] == AbilityNames.GUTS
    assert d[Pok.STATUS] == 0 and d[Pok.SLEEP_COUNTER] == 0
    assert worry_seed(d) and d[Pok.BASE_AB_ID] == AbilityNames.GUTS
    reset_switch_out(d)
    assert (d[Pok.AB_ID:Pok.AB_BREAKABLE + 1] == guts).all() and d[Pok.BASE_AB_ID] == 0


@pytest.mark.parametrize("ability", ["Truant", "Multitype"])
def test_worry_seed_fails(poke, ability):
    """Truant and Multitype stay"""
    d = poke("Machop", 20, ability, ["Tackle"])
    assert not worry_seed(d)
    assert d[Pok.AB_ID] == getattr(AbilityNames, ability.upper()) and d[Pok.BASE_AB_ID] == 0


@pytest.mark.parametrize("foe_ab, user_ab, foe_vol, foe_hp, foe_gets", [
    ("Guts", "Run Away", 0, 1, True),
    ("Soundproof", "Run Away", 0, 1, False),
    ("Soundproof", "Mold Breaker", 0, 1, True),
    ("Guts", "Run Away", VolStatus.SEMI_INVULNERABLE, 1, False),
    ("Guts", "Run Away", 0, 0, False),
])
def test_perish_song_targets(poke, foe_ab, user_ab, foe_vol, foe_hp, foe_gets):
    """Both actives get a count of 3, except a Soundproof (unless Mold Breaker), semi-invulnerable
    or fainted foe. The user always does"""
    user = poke("Rattata", 20, user_ab, ["Perish Song"])
    foe = poke("Machop", 20, foe_ab, ["Tackle"])
    foe[Pok.VOL_STATUS] = foe_vol
    foe[Pok.CURRENT_HP] = foe_hp
    perish_song(user, foe)
    assert user[Pok.VOL_STATUS] & VolStatus.PERISH_SONG and user[Pok.PERISH_TURNS] == 3
    assert bool(foe[Pok.VOL_STATUS] & VolStatus.PERISH_SONG) == foe_gets


def test_perish_song_doesnt_reset_a_count(poke):
    """A Pokemon that already has it keeps its count"""
    user = poke("Rattata", 20, "Run Away", ["Perish Song"])
    foe = poke("Machop", 20, "Guts", ["Tackle"])
    perish_song(user, foe)
    perish_count(user)
    perish_song(user, foe)
    assert user[Pok.PERISH_TURNS] == 2


def test_perish_count_faints_at_the_fourth_end_of_turn(poke):
    """3, 2, 1, 0 then faint, the bit goes with it"""
    p = poke("Machop", 20, "Guts", ["Tackle"])
    perish_song(p, poke("Rattata", 20, "Run Away", ["Tackle"]))
    for left in (2, 1, 0):
        perish_count(p)
        assert p[Pok.PERISH_TURNS] == left and p[Pok.CURRENT_HP] > 0
    perish_count(p)
    assert p[Pok.CURRENT_HP] == 0 and not p[Pok.VOL_STATUS] & VolStatus.PERISH_SONG


def test_switch_out_clears_perish_song(poke):
    """The bit and the count go when the Pokemon leaves"""
    p = poke("Machop", 20, "Guts", ["Tackle"])
    perish_song(p, poke("Rattata", 20, "Run Away", ["Tackle"]))
    reset_switch_out(p)
    assert not p[Pok.VOL_STATUS] & VolStatus.PERISH_SONG and p[Pok.PERISH_TURNS] == 0


# ── Phase 8: move-calling ────────────────────────────────────────────────────

def test_metronome_skips_forbidden_and_known_moves(poke):
    """Every draw is in the pool, never a forbidden move or one of the user's own"""
    p = poke("Munchlax", 20, "Thick Fat", ["Metronome", "Tackle", "Amnesia", "Rock Tomb"])
    known = {int(move_slice(p, i)[Move.ID]) for i in range(4)}
    for _ in range(300):
        move_id = metronome_move(p)
        assert move_id not in known and move_id not in METRONOME_FORBIDDEN
        assert move_id in METRONOME_POOL


def test_metronome_pool_is_movedb_minus_the_forbidden_list():
    """The pool follows MoveDB, Protect and Counter are out, a plain attack is in"""
    assert MoveName.PROTECT not in METRONOME_POOL and MoveName.COUNTER not in METRONOME_POOL
    assert MoveName.EARTHQUAKE in METRONOME_POOL and MoveName.METRONOME not in METRONOME_POOL


@pytest.mark.parametrize("last, expected", [
    (0, 0), (MoveName.METRONOME, 0), (MoveName.MIRROR_MOVE, 0), (MoveName.PROTECT, 0),
    (MoveName.STRUGGLE, 0), (MoveName.TACKLE, MoveName.TACKLE), (MoveName.GROWL, MoveName.GROWL),
])
def test_copycat_move(last, expected):
    """Fails with nothing, on a move-calling move or on one Metronome can't call"""
    arr = empty_field()
    arr[Field.LAST_MOVE] = last
    assert copycat_move(arr) == expected


@pytest.mark.parametrize("terrain, move", [
    (Terrain.PLAIN, MoveName.EARTHQUAKE), (Terrain.SAND, MoveName.EARTHQUAKE),
    (Terrain.GRASS, MoveName.SEED_BOMB), (Terrain.PUDDLE, MoveName.SEED_BOMB),
    (Terrain.MOUNTAIN, MoveName.ROCK_SLIDE), (Terrain.CAVE, MoveName.ROCK_SLIDE),
    (Terrain.SNOW, MoveName.BLIZZARD), (Terrain.WATER, MoveName.HYDRO_PUMP),
    (Terrain.ICE, MoveName.ICE_BEAM), (Terrain.BUILDING, MoveName.TRI_ATTACK),
    (Terrain.GREAT_MARSH, MoveName.MUD_BOMB), (Terrain.BRIDGE, MoveName.AIR_SLASH),
    (Terrain.SPECIAL, MoveName.TRI_ATTACK), (Terrain.SPECIAL + 5, MoveName.TRI_ATTACK),
])
def test_nature_power_move(terrain, move):
    """pokeplatinum sTerrainMove, anything past SPECIAL counts as SPECIAL"""
    arr = empty_field()
    arr[Field.TERRAIN] = terrain
    assert nature_power_move(arr) == move


@pytest.mark.parametrize("move, called, recorded", [
    ("Tackle", False, True), ("Tackle", True, False), ("Encore", False, False),
    ("Psych Up", False, False),
])
def test_mirror_record(poke, move, called, recorded):
    """A mirrorable move that hit is recorded, a called or unmirrorable one clears the record"""
    a = poke("Pidgey", 20, "Keen Eye", [move])
    d = poke("Machop", 20, "Guts", ["Tackle"])
    d[Pok.MIRROR_MOVE] = MoveName.GROWL
    mirror_record(move_slice(a, 0), d, called)
    assert d[Pok.MIRROR_MOVE] == (move_slice(a, 0)[Move.ID] if recorded else 0)


def test_switches_clear_mirror_move_and_called_move(poke):
    """Leaving clears both, the foe coming in clears the Pokemon's mirror record too"""
    p = poke("Pidgey", 20, "Keen Eye", ["Mirror Move"])
    foe = poke("Machop", 20, "Guts", ["Tackle"])
    p[Pok.MIRROR_MOVE] = MoveName.TACKLE
    p[Pok.CALLED_MOVE] = MoveName.TACKLE
    reset_switch_out(p)
    assert p[Pok.MIRROR_MOVE] == 0 and p[Pok.CALLED_MOVE] == 0
    p[Pok.MIRROR_MOVE] = MoveName.TACKLE
    switch_in(foe, p, empty_field(), False)
    assert p[Pok.MIRROR_MOVE] == 0


@pytest.mark.parametrize("weather, outcome", [
    (Weather.HAIL, MoveOutcome.HIT), (0, MoveOutcome.MISS), (Weather.RAIN, MoveOutcome.MISS),
])
def test_blizzard_cant_miss_in_hail(monkeypatch, poke, weather, outcome):
    """Gen IV Blizzard skips the accuracy roll in hail"""
    monkeypatch.setattr(engine_helper.random, "randint", lambda a, b: 100)
    a = poke("Rattata", 20, "Run Away", ["Blizzard"])
    d = poke("Machop", 20, "Guts", ["Tackle"])
    assert calculate_hit_miss(move_slice(a, 0), a, d, weather) == outcome


# ── Dig, Gravity, Minimize ───────────────────────────────────────────────────

def test_underground_target_only_hit_by_earthquake_and_magnitude(poke):
    """Dig's underground turn: Earthquake and Magnitude hit, Gust and aimed moves miss"""
    a = poke("Geodude", 50, "Sturdy", ["Tackle", "Gust", "Earthquake", "Magnitude"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    d[Pok.VOL_STATUS] = VolStatus.SEMI_INVULNERABLE
    d[Pok.SEMI_INV_MOVE] = MoveName.DIG
    outcomes = [calculate_hit_miss(move_slice(a, i), a, d, 0) for i in range(4)]
    assert outcomes == [MoveOutcome.SEMI_INVULNERABLE, MoveOutcome.SEMI_INVULNERABLE,
                        MoveOutcome.HIT, MoveOutcome.HIT]


def test_airborne_target_dodges_earthquake(poke):
    """Bounce's airborne turn isn't reached by Earthquake"""
    a = poke("Geodude", 50, "Sturdy", ["Earthquake"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    d[Pok.VOL_STATUS] = VolStatus.SEMI_INVULNERABLE
    d[Pok.SEMI_INV_MOVE] = MoveName.BOUNCE
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == MoveOutcome.SEMI_INVULNERABLE


def test_gravity_boosts_accuracy(monkeypatch, poke):
    """Gravity multiplies accuracy by 5/3, so a 60% move rolled at 99 hits only under Gravity"""
    monkeypatch.setattr(engine_helper.random, "randint", lambda a, b: 99)
    a = poke("Abra", 20, "Synchronize", ["Hypnosis"])
    d = poke("Rattata", 20, "Run Away", ["Tackle"])
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == MoveOutcome.MISS
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0, True) == MoveOutcome.HIT


def test_gravity_lets_ground_moves_hit_flying(poke):
    """Under Gravity a Flying type isn't immune to Ground moves"""
    a = poke("Geodude", 20, "Sturdy", ["Earthquake"])
    d = poke("Pidgey", 20, "Keen Eye", ["Tackle"])
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == MoveOutcome.INVULNERABLE
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0, True) == MoveOutcome.HIT


def test_gravity_blocks_its_moves(poke):
    """Splash and Bounce can't be selected under Gravity and fail if picked before it"""
    p = poke("Pidgey", 20, "Keen Eye", ["Splash", "Bounce", "Tackle"])
    d = poke("Rattata", 20, "Run Away", ["Tackle"])
    assert [move_blocked(p, i) for i in range(3)] == [False] * 3
    assert [move_blocked(p, i, True) for i in range(3)] == [True, True, False]
    assert early_returns(p, d, 1, False, move_slice(p, 1), True)
    assert not early_returns(p, d, 1, False, move_slice(p, 2), True)


def test_gravity_grounds_everyone(poke):
    """Flying types and Levitate are grounded under Gravity (Toxic Spikes reach them)"""
    pidgey = poke("Pidgey", 20, "Keen Eye", ["Tackle"])
    assert not is_grounded(pidgey)
    assert is_grounded(pidgey, True)


def test_reset_switch_out_clears_semi_inv_and_minimize(poke):
    """Switching out ends Dig's state and the minimized flag"""
    p = poke("Rattata", 20, "Run Away", ["Tackle"])
    p[Pok.SEMI_INV_MOVE] = MoveName.DIG
    p[Pok.VOL_STATUS2] = VolStatus2.MINIMIZE
    reset_switch_out(p)
    assert p[Pok.SEMI_INV_MOVE] == 0 and p[Pok.VOL_STATUS2] == 0


def test_unlock_move_clears_semi_inv_move(poke):
    """A blocked turn ends the charge and the semi-invulnerable move with it"""
    p = poke("Diglett", 20, "Sand Veil", ["Dig"])
    p[Pok.VOL_STATUS] = VolStatus.SEMI_INVULNERABLE
    p[Pok.SEMI_INV_MOVE] = MoveName.DIG
    unlock_move(p)
    assert p[Pok.SEMI_INV_MOVE] == 0 and not p[Pok.VOL_STATUS] & VolStatus.SEMI_INVULNERABLE



# ── Batch 3: Sturdy ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("attacker_ab, outcome", [
    ("Run Away", MoveOutcome.INVULNERABLE), ("Mold Breaker", MoveOutcome.HIT),
])
def test_sturdy_blocks_ohko_moves(poke, attacker_ab, outcome):
    """An OHKO move fails into Sturdy unless the user has Mold Breaker (70 levels up, so the
    roll always hits)"""
    a = poke("Rattata", 100, attacker_ab, ["Guillotine"])
    d = poke("Geodude", 30, "Sturdy", ["Tackle"])
    mv = move_slice(a, 0)
    assert calculate_hit_miss(mv, a, d, 0) == outcome
    d2 = poke("Geodude", 30, "Rock Head", ["Tackle"])
    assert calculate_hit_miss(mv, a, d2, 0) == MoveOutcome.HIT



# ── OHKO moves ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("atk_lv, def_lv, roll, outcome", [
    (50, 50, 29, MoveOutcome.HIT),
    (50, 50, 30, MoveOutcome.MISS),
    (60, 50, 39, MoveOutcome.HIT),
    (60, 50, 40, MoveOutcome.MISS),
    (49, 50, 0, MoveOutcome.INVULNERABLE),
])
def test_ohko_accuracy_adds_the_level_difference(monkeypatch, poke, atk_lv, def_lv, roll, outcome):
    """Hits when the 0-99 roll is under accuracy + the level difference, always fails from a lower
    level (pokeplatinum BtlCmd_TryOHKOMove)"""
    monkeypatch.setattr(engine_helper.random, "randint", lambda a, b: roll)
    a = poke("Rattata", atk_lv, "Run Away", ["Guillotine"])
    d = poke("Rattata", def_lv, "Run Away", ["Tackle"])
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == outcome


def test_ohko_ignores_stages_gravity_and_accuracy_abilities(monkeypatch, poke):
    """Accuracy and evasion stages, Gravity, Hustle and Sand Veil don't change the 30%"""
    a = poke("Rattata", 50, "Hustle", ["Guillotine"])
    d = poke("Rattata", 50, "Sand Veil", ["Tackle"])
    a[Pok.ACCURACY_STAT_STAGE] = 6
    d[Pok.EVASION_STAT_STAGE] = 6
    mv = move_slice(a, 0)
    for roll, outcome in ((29, MoveOutcome.HIT), (30, MoveOutcome.MISS)):
        monkeypatch.setattr(engine_helper.random, "randint", lambda x, y, r=roll: r)
        assert calculate_hit_miss(mv, a, d, Weather.SANDSTORM, True) == outcome


@pytest.mark.parametrize("move, defender, outcome", [
    ("Fissure", "Pidgey", MoveOutcome.INVULNERABLE),
    ("Guillotine", "Gastly", MoveOutcome.INVULNERABLE),
    ("Sheer Cold", "Swinub", MoveOutcome.HIT),   # Gen IV: Ice types aren't immune
])
def test_ohko_type_immunity(poke, move, defender, outcome):
    """The type chart still applies (70 levels up, so the roll always hits)"""
    a = poke("Rattata", 100, "Run Away", [move])
    d = poke(defender, 30, "Run Away", ["Tackle"])
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == outcome


@pytest.mark.parametrize("semi_inv", [MoveName.BOUNCE, MoveName.DIG])
@pytest.mark.parametrize("move", ["Fissure", "Guillotine", "Sheer Cold"])
def test_ohko_misses_semi_invulnerable_targets(poke, move, semi_inv):
    """Showdown gen4: OHKO moves don't reach Bounce or Dig, not even Fissure"""
    a = poke("Rattata", 100, "Run Away", [move])
    d = poke("Rattata", 30, "Run Away", ["Tackle"])
    d[Pok.VOL_STATUS] = VolStatus.SEMI_INVULNERABLE
    d[Pok.SEMI_INV_MOVE] = semi_inv
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == MoveOutcome.SEMI_INVULNERABLE


@pytest.mark.parametrize("atk_lv, atk_ab, def_ab, fails", [
    (50, "Run Away", "Run Away", False),
    (49, "Run Away", "Run Away", True),
    (50, "Run Away", "Sturdy", True),
    (50, "Mold Breaker", "Sturdy", False),
])
def test_ohko_fails(poke, atk_lv, atk_ab, def_ab, fails):
    """A lower level or Sturdy (unless Mold Breaker) makes it never work"""
    a = poke("Rattata", atk_lv, atk_ab, ["Guillotine"])
    d = poke("Geodude", 50, def_ab, ["Tackle"])
    assert ohko_fails(a, d) == fails


# ── Batch 7: status immunity, cures, status items ────────────────────────────

def _turns_asleep(a, d, counter):
    """How many move attempts sleep blocks, starting from this counter"""
    a[Pok.STATUS] = Status.SLEEP
    a[Pok.SLEEP_COUNTER] = counter
    n = 0
    while early_returns(a, d, 1, False, move_slice(a, 0)):
        n += 1
    return n


@pytest.mark.parametrize("ability, turns", [
    ("Run Away", (1, 2, 3, 4)), ("Early Bird", (0, 1, 1, 2)),
])
def test_sleep_turns_and_early_bird(poke, ability, turns):
    """A counter of 2-5 sleeps 1-4 turns, Early Bird drops it by 2 (pokeplatinum
    CHECK_STATUS_STATE_SLEEP, Showdown gen4 slp)"""
    a = poke("Doduo", 50, ability, ["Tackle"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    assert tuple(_turns_asleep(a, d, c) for c in (2, 3, 4, 5)) == turns
    assert a[Pok.STATUS] == 0 and a[Pok.SLEEP_COUNTER] == 0


@pytest.mark.parametrize("ability, base, hp, cured", [
    ("Natural Cure", 0, 50, True),
    ("Natural Cure", 0, 0, False),
    ("Run Away", 0, 50, False),
    # Worry Seed: its own Limber forbids paralysis, a Worry Seeded Natural Cure doesn't cure
    ("Insomnia", AbilityNames.LIMBER, 50, True),
    ("Insomnia", AbilityNames.NATURAL_CURE, 50, False),
])
def test_natural_cure_on_switch_out(poke, ability, base, hp, cured):
    """pokeplatinum BtlCmd_TryRestoreStatusOnSwitch: Natural Cure, or the party ability forbids
    the status, and the Pokemon is alive"""
    p = poke("Staryu", 50, ability, ["Tackle"])
    p[Pok.BASE_AB_ID] = base
    p[Pok.CURRENT_HP] = hp
    p[Pok.STATUS] = Status.PARALYSIS
    reset_switch_out(p)
    assert (p[Pok.STATUS] == 0) == cured


def test_natural_cure_clears_toxic_counter(poke):
    """A cured Toxic doesn't keep its counter"""
    p = poke("Staryu", 50, "Natural Cure", ["Tackle"])
    p[Pok.STATUS] = Status.TOXIC
    p[Pok.BADLY_POISON] = 4
    reset_switch_out(p)
    assert p[Pok.STATUS] == 0 and p[Pok.BADLY_POISON] == 0


@pytest.mark.parametrize("roll, cured", [(2, True), (3, False)])
def test_shed_skin(monkeypatch, poke, roll, cured):
    """Gen IV 30% at the end of the turn, pokeplatinum RandNext % 10 < 3"""
    _fix_rolls(monkeypatch, roll)
    p = poke("Metapod", 50, "Shed Skin", ["Tackle"])
    p[Pok.STATUS] = Status.SLEEP
    p[Pok.SLEEP_COUNTER] = 3
    on_residual(p, 0)
    assert (p[Pok.STATUS] == 0) == cured


def test_shed_skin_no_roll_without_status(monkeypatch, poke):
    """No status, no roll (keeps the RNG order)"""
    monkeypatch.setattr(engine_helper.random, "randint", lambda lo, hi: pytest.fail("rolled"))
    on_residual(poke("Metapod", 50, "Shed Skin", ["Tackle"]), 0)


@pytest.mark.parametrize("attacker_ab, attracted", [("Oblivious", False), ("Run Away", True)])
def test_cute_charm_into_oblivious(monkeypatch, poke, attacker_ab, attracted):
    """Oblivious keeps Cute Charm's infatuation off the attacker"""
    _fix_rolls(monkeypatch, 0)
    a = poke("Slowpoke", 50, attacker_ab, ["Tackle"], gender="Male")
    d = poke("Clefairy", 50, "Cute Charm", ["Tackle"], gender="Female")
    on_hit_abilities(a, d, move_slice(a, 0), 10, 0)
    assert bool(a[Pok.VOL_STATUS] & VolStatus.ATTRACT) == attracted


@pytest.mark.parametrize("ability, weather, poisoned", [
    ("Immunity", 0, False), ("Leaf Guard", Weather.SUN, False), ("Leaf Guard", 0, True),
])
def test_toxic_spikes_abilities(poke, ability, weather, poisoned):
    """Immunity and Leaf Guard in sun keep Toxic Spikes' poison off"""
    p = poke("Rattata", 50, ability, ["Tackle"])
    arr = empty_field()
    arr[Field.MY_SIDE_COND] = SideCondition.TOXIC_SPIKES
    arr[Field.MY_SIDE_COND + SIDE_TOXIC_SPIKES] = 1
    engine_helper._toxic_spikes(p, arr, Field.MY_SIDE_COND, weather)
    assert (p[Pok.STATUS] == Status.POISON) == poisoned


@pytest.mark.parametrize("item, status, vol, cured", [
    ("Pecha Berry", Status.POISON, 0, True),
    ("Pecha Berry", Status.TOXIC, 0, True),
    ("Pecha Berry", Status.BURN, 0, False),
    ("Chesto Berry", Status.SLEEP, 0, True),
    ("Chesto Berry", Status.PARALYSIS, 0, False),
    ("Lum Berry", Status.FREEZE, 0, True),
    ("Lum Berry", 0, VolStatus.CONFUSION, True),
    ("Lum Berry", 0, VolStatus.ATTRACT, False),
    ("Mental Herb", 0, VolStatus.ATTRACT, True),
    ("Mental Herb", 0, VolStatus.CONFUSION, False),
])
def test_status_item(poke, item, status, vol, cured):
    """Each cures its own condition and is used up, recyclable; anything else leaves it held
    (pokeplatinum BattleSystem_TriggerHeldItemOnStatus, Mental Herb is Attract only in Gen IV)"""
    p = poke("Rattata", 50, "Run Away", ["Tackle"], item=item)
    held = p[Item.ID]
    p[Pok.STATUS] = status
    p[Pok.VOL_STATUS] = vol
    engine_helper.status_item(p)
    if cured:
        assert p[Pok.STATUS] == 0 and p[Pok.VOL_STATUS] == 0
        assert p[Item.ID] == 0 and p[Pok.CONSUMED_ITEM] == held
    else:
        assert p[Pok.STATUS] == status and p[Pok.VOL_STATUS] == vol and p[Item.ID] == held


def test_lum_cures_status_and_confusion_at_once(poke):
    """Lum clears both and the toxic counter"""
    p = poke("Rattata", 50, "Run Away", ["Tackle"], item="Lum Berry")
    p[Pok.STATUS] = Status.TOXIC
    p[Pok.BADLY_POISON] = 3
    p[Pok.VOL_STATUS] = VolStatus.CONFUSION
    engine_helper.status_item(p)
    assert p[Pok.STATUS] == 0 and p[Pok.BADLY_POISON] == 0 and p[Pok.VOL_STATUS] == 0


def test_status_item_not_used_when_fainted(poke):
    """A fainted holder keeps its berry"""
    p = poke("Rattata", 50, "Run Away", ["Tackle"], item="Pecha Berry")
    p[Pok.STATUS] = Status.POISON
    p[Pok.CURRENT_HP] = 0
    engine_helper.status_item(p)
    assert p[Item.ID] == ItemNames.PECHA_BERRY


def test_bug_bite_status_berry_cures_the_biter(poke):
    """The biter gets the cure, the target loses its berry (pokeplatinum BattleSystem_PluckBerry)"""
    atk = poke("Kricketune", 50, "Swarm", ["Bug Bite"])
    dfn = poke("Rattata", 50, "Run Away", ["Tackle"], item="Pecha Berry")
    atk[Pok.STATUS] = Status.POISON
    dfn[Pok.STATUS] = Status.POISON
    eat_berry_bug_bite(atk, dfn)
    assert atk[Pok.STATUS] == 0
    assert dfn[Pok.STATUS] == Status.POISON and dfn[Item.ID] == 0


def test_switch_in_pecha_cures_toxic_spikes(poke):
    """The berry is checked right after the hazards (SWITCH_IN_CHECK_STATE_HELD_ITEM_STATUS)"""
    p = poke("Rattata", 50, "Run Away", ["Tackle"], item="Pecha Berry")
    arr = empty_field()
    arr[Field.MY_SIDE_COND] = SideCondition.TOXIC_SPIKES
    arr[Field.MY_SIDE_COND + SIDE_TOXIC_SPIKES] = 2
    switch_in(p, poke("Rattata", 50, "Run Away", ["Tackle"]), arr, True)
    assert p[Pok.STATUS] == 0 and p[Item.ID] == 0


# ── Batch 8: type immunity and absorbing abilities ───────────────────────────

def _always_hit(monkeypatch):
    """The accuracy roll always hits"""
    monkeypatch.setattr(engine_helper.random, "randint", lambda lo, hi: lo)


@pytest.mark.parametrize("ability, move", [
    ("Volt Absorb", "Thunder Shock"), ("Volt Absorb", "Thunder Wave"),
    ("Water Absorb", "Water Gun"), ("Dry Skin", "Water Gun"),
])
def test_absorbs_heal_a_quarter(monkeypatch, poke, ability, move):
    """The move hit and the ability takes it: 1/4 of max HP, the move does nothing else.
    Volt Absorb takes status moves too (pokeplatinum TriggerImmunityAbility has no power check)"""
    _always_hit(monkeypatch)
    a = poke("Rattata", 50, "Run Away", [move])
    d = poke("Rattata", 50, ability, ["Tackle"])
    d[Pok.CURRENT_HP] = 10
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == MoveOutcome.INVULNERABLE
    assert d[Pok.CURRENT_HP] == 10 + d[Pok.MAX_HP] // 4 and d[Pok.STATUS] == 0


@pytest.mark.parametrize("stage, after", [(0, 1), (6, 6)])
def test_motor_drive(monkeypatch, poke, stage, after):
    """Speed +1, still immune at +6"""
    _always_hit(monkeypatch)
    a = poke("Pikachu", 50, "Static", ["Thunder Shock"])
    d = poke("Rattata", 50, "Motor Drive", ["Tackle"])
    d[Pok.SPEED_STAT_STAGE] = stage
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == MoveOutcome.INVULNERABLE
    assert d[Pok.SPEED_STAT_STAGE] == after


@pytest.mark.parametrize("move", ["Ember", "Will-O-Wisp"])
def test_flash_fire_absorbs_and_sets_the_boost(monkeypatch, poke, move):
    """Damaging Fire moves and Will-O-Wisp, the holder gets the Flash Fire volatile"""
    _always_hit(monkeypatch)
    a = poke("Charmander", 50, "Blaze", [move])
    d = poke("Ponyta", 50, "Flash Fire", ["Ember"])
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == MoveOutcome.INVULNERABLE
    assert d[Pok.VOL_STATUS2] & VolStatus2.FLASH_FIRE and d[Pok.STATUS] == 0


def test_frozen_flash_fire_gets_hit(monkeypatch, poke):
    """Frozen, Flash Fire doesn't work (pokeplatinum and Showdown gen4)"""
    _always_hit(monkeypatch)
    a = poke("Charmander", 50, "Blaze", ["Ember"])
    d = poke("Ponyta", 50, "Flash Fire", ["Ember"])
    d[Pok.STATUS] = Status.FREEZE
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == MoveOutcome.HIT
    assert not d[Pok.VOL_STATUS2] & VolStatus2.FLASH_FIRE


@pytest.mark.parametrize("ability, move", [
    ("Volt Absorb", "Thunder Shock"), ("Water Absorb", "Water Gun"), ("Flash Fire", "Ember"),
    ("Motor Drive", "Thunder Shock"), ("Wonder Guard", "Tackle"),
])
def test_mold_breaker_ignores_absorbs(monkeypatch, poke, ability, move):
    """All of them are breakable"""
    _always_hit(monkeypatch)
    a = poke("Rattata", 50, "Mold Breaker", [move])
    d = poke("Rattata", 50, ability, ["Tackle"])
    d[Pok.CURRENT_HP] = 10
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == MoveOutcome.HIT
    assert d[Pok.CURRENT_HP] == 10


def test_absorb_needs_the_move_to_hit(monkeypatch, poke):
    """A Water move that misses doesn't heal Water Absorb (the absorbs come after the accuracy
    roll in pokeplatinum and Showdown gen4)"""
    monkeypatch.setattr(engine_helper.random, "randint", lambda lo, hi: hi)
    a = poke("Squirtle", 50, "Torrent", ["Hydro Pump"])
    d = poke("Mudkip", 50, "Water Absorb", ["Tackle"])
    d[Pok.CURRENT_HP] = 10
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == MoveOutcome.MISS
    assert d[Pok.CURRENT_HP] == 10


@pytest.mark.parametrize("move", ["Rain Dance", "Water Sport"])
def test_water_absorb_ignores_water_status_moves(poke, move):
    """Issue 4: only damaging Water moves aimed at it are absorbed"""
    a = poke("Squirtle", 50, "Torrent", [move])
    d = poke("Mudkip", 50, "Water Absorb", ["Tackle"])
    d[Pok.CURRENT_HP] = 10
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == MoveOutcome.HIT
    assert d[Pok.CURRENT_HP] == 10


@pytest.mark.parametrize("move, outcome", [
    ("Tackle", MoveOutcome.INVULNERABLE),       # neutral
    ("Dragon Rage", MoveOutcome.INVULNERABLE),  # fixed damage counts as damaging
    ("Karate Chop", MoveOutcome.HIT),           # super effective
    ("Fire Fang", MoveOutcome.HIT),             # Gen IV bug, always gets through
    ("Thunder Wave", MoveOutcome.HIT),          # status moves aren't blocked
])
def test_wonder_guard(monkeypatch, poke, move, outcome):
    """Only super effective damaging moves land (pokeplatinum ApplyTypeChart, Showdown gen4)"""
    _always_hit(monkeypatch)
    a = poke("Rattata", 50, "Run Away", [move])
    d = poke("Rattata", 50, "Wonder Guard", ["Tackle"])
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == outcome


@pytest.mark.parametrize("atk_ab, gravity, ingrain, outcome", [
    ("Run Away", False, False, MoveOutcome.INVULNERABLE),
    ("Mold Breaker", False, False, MoveOutcome.HIT),
    ("Run Away", True, False, MoveOutcome.HIT),
    ("Run Away", False, True, MoveOutcome.HIT),
])
def test_levitate(monkeypatch, poke, atk_ab, gravity, ingrain, outcome):
    """Ground moves miss a Levitate Pokemon, Mold Breaker, Gravity and Ingrain ground it
    (pokeplatinum Battler_Ability)"""
    _always_hit(monkeypatch)
    a = poke("Rattata", 50, atk_ab, ["Mud-Slap"])
    d = poke("Misdreavus", 50, "Levitate", ["Astonish"])
    if ingrain:
        d[Pok.VOL_STATUS] |= VolStatus.INGRAIN
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0, gravity) == outcome


def test_levitate_doesnt_stop_ground_status_moves(monkeypatch, poke):
    """Sand Attack skips the type chart, so it reaches a Levitate Pokemon"""
    _always_hit(monkeypatch)
    a = poke("Rattata", 50, "Run Away", ["Sand Attack"])
    d = poke("Misdreavus", 50, "Levitate", ["Astonish"])
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == MoveOutcome.HIT


@pytest.mark.parametrize("species, ability, grounded", [
    ("Misdreavus", "Levitate", True), ("Pidgey", "Keen Eye", False),
])
def test_ingrain_grounds_levitate_not_flying(poke, species, ability, grounded):
    """pokeplatinum BattlerIsGrounded: Ingrain switches Levitate off, a Flying type stays up"""
    p = poke(species, 50, ability, ["Tackle"])
    p[Pok.VOL_STATUS] |= VolStatus.INGRAIN
    assert is_grounded(p) == grounded


@pytest.mark.parametrize("species, ability", [("Misdreavus", "Levitate"), ("Pidgey", "Keen Eye")])
def test_iron_ball_grounds_levitate_and_flying(monkeypatch, poke, species, ability):
    """pokeplatinum ApplyTypeChart and BattlerIsGrounded: Ground moves reach an Iron Ball holder
    through Levitate and the Flying type, and so do the spikes"""
    _always_hit(monkeypatch)
    a = poke("Rattata", 50, "Run Away", ["Mud-Slap"])
    d = poke(species, 50, ability, ["Tackle"])
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == MoveOutcome.INVULNERABLE
    assert not is_grounded(d)
    d = poke(species, 50, ability, ["Tackle"], item="Iron Ball")
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == MoveOutcome.HIT
    assert is_grounded(d)


@pytest.mark.parametrize("atk_ab, outcome", [
    ("Run Away", MoveOutcome.INVULNERABLE), ("Scrappy", MoveOutcome.HIT),
])
def test_scrappy_hits_ghosts(monkeypatch, poke, atk_ab, outcome):
    """Normal and Fighting moves reach a Ghost type"""
    _always_hit(monkeypatch)
    a = poke("Kangaskhan", 50, atk_ab, ["Tackle"])
    d = poke("Gastly", 50, "Levitate", ["Lick"])
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == outcome


@pytest.mark.parametrize("atk_ab, outcome", [
    ("Run Away", MoveOutcome.MISS), ("Mold Breaker", MoveOutcome.HIT),
])
def test_soundproof_and_mold_breaker(monkeypatch, poke, atk_ab, outcome):
    """Soundproof is breakable (pokeplatinum TriggerImmunityAbility)"""
    _always_hit(monkeypatch)
    a = poke("Rattata", 50, atk_ab, ["Growl"])
    d = poke("Whismur", 50, "Soundproof", ["Pound"])
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == outcome


# ── The AI learns an ability from its message (pokeplatinum BattleMessage_AbilityTag) ──

@pytest.mark.parametrize("move, ability, known", [
    ("Thunder Shock", "Volt Absorb", True),
    ("Water Gun", "Water Absorb", True),
    ("Ember", "Flash Fire", True),
    ("Thunder Shock", "Motor Drive", True),
    ("Mud-Slap", "Levitate", True),
    ("Fissure", "Sturdy", True),
    ("Growl", "Soundproof", True),
    ("Selfdestruct", "Damp", True),
    ("Water Gun", "Wonder Guard", True),
    ("Tackle", "Run Away", False),
])
def test_hit_check_abilities_reveal_themselves(poke, move, ability, known):
    """The absorbs, Wonder Guard, Levitate, Sturdy, Soundproof and Damp name themselves"""
    a = poke("Geodude", 50, "Rock Head", [move])
    d = poke("Shedinja" if ability == "Wonder Guard" else "Rattata", 30, ability, ["Tackle"])
    calculate_hit_miss(move_slice(a, 0), a, d, 0)
    assert bool(d[Pok.AB_KNOWN]) == known


def test_attackers_damp_reveals_itself(poke):
    """Damp on the user's side stops its own Selfdestruct, the message names it"""
    a = poke("Psyduck", 50, "Damp", ["Selfdestruct"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    calculate_hit_miss(move_slice(a, 0), a, d, 0)
    assert a[Pok.AB_KNOWN] and d[Pok.AB_KNOWN] == 0


def test_mold_breaker_hit_doesnt_reveal(poke):
    """Mold Breaker's Mud-Slap goes through Levitate, nothing is shown"""
    a = poke("Pinsir", 50, "Mold Breaker", ["Mud-Slap"])
    d = poke("Gastly", 50, "Levitate", ["Tackle"])
    calculate_hit_miss(move_slice(a, 0), a, d, 0)
    assert d[Pok.AB_KNOWN] == 0


@pytest.mark.parametrize("ability, roll, known", [
    ("Static", 2, True), ("Static", 3, False), ("Cute Charm", 2, True), ("Rough Skin", 9, True),
])
def test_contact_abilities_reveal_when_they_trigger(monkeypatch, poke, ability, roll, known):
    """"X's Static paralyzed Y!" only when the status lands, Rough Skin whenever it hurts"""
    _fix_rolls(monkeypatch, roll)
    a = poke("Rattata", 50, "Run Away", ["Tackle"], gender="Male")
    d = poke("Clefairy", 50, ability, ["Tackle"], gender="Female")
    on_hit_abilities(a, d, move_slice(a, 0), 10, 0)
    assert bool(d[Pok.AB_KNOWN]) == known


def test_aftermath_reveals_when_it_hurts(poke):
    """Aftermath names itself when the KO hit damages the attacker"""
    a = poke("Rattata", 50, "Run Away", ["Tackle"])
    d = poke("Stunky", 50, "Aftermath", ["Tackle"])
    d[Pok.CURRENT_HP] = 0
    on_hit_abilities(a, d, move_slice(a, 0), 10, 0)
    assert d[Pok.AB_KNOWN]


@pytest.mark.parametrize("move, known", [("Fake Out", True), ("Bite", False)])
def test_inner_focus_reveals_on_fake_out_only(poke, move, known):
    """pokeplatinum subscript_flinch_mon prints only for Fake Out"""
    a = poke("Rattata", 50, "Run Away", [move])
    d = poke("Zubat", 50, "Inner Focus", ["Tackle"])
    assert not flinch_checker(move_slice(a, 0), a, d)
    assert bool(d[Pok.AB_KNOWN]) == known


@pytest.mark.parametrize("hp_missing, known", [(10, True), (0, False)])
def test_rain_dish_reveals_when_it_heals(poke, hp_missing, known):
    """No heal at full HP, no message"""
    p = poke("Lotad", 20, "Rain Dish", ["Tackle"])
    p[Pok.CURRENT_HP] -= hp_missing
    heal_weather(p, Weather.RAIN)
    assert bool(p[Pok.AB_KNOWN]) == known


def test_shed_skin_reveals_when_it_cures(monkeypatch, poke):
    """"X's Shed Skin cured its poison!" """
    monkeypatch.setattr(engine_helper.random, "randint", lambda lo, hi: lo)
    p = poke("Metapod", 20, "Shed Skin", ["Tackle"])
    p[Pok.STATUS] = Status.POISON
    on_residual(p, False)
    assert p[Pok.STATUS] == 0 and p[Pok.AB_KNOWN]


def test_toxic_spikes_blocked_by_immunity_reveals_it(poke):
    """pokeplatinum subscript_poison prints the ability for Toxic Spikes"""
    p = poke("Munchlax", 20, "Immunity", ["Tackle"])
    apply_hazards(p, _field(TSPIKES, 1), MY_SIDE)
    assert p[Pok.STATUS] == 0 and p[Pok.AB_KNOWN]


def test_switch_out_forgets_the_ability(poke):
    """pokeplatinum clears the AI's known ability when the battler is replaced"""
    p = poke("Rattata", 20, "Run Away", ["Tackle"])
    p[Pok.AB_KNOWN] = 1
    reset_switch_out(p)
    assert p[Pok.AB_KNOWN] == 0


# ── Focus Band, Metronome item, Power Herb, Liquid Ooze, Sticky Hold ─────────

@pytest.mark.parametrize("roll, hp, damage, expected", [
    (9, 10, 30, 9), (10, 10, 30, 30), (9, 10, 5, 5), (9, 10, 10, 9),
])
def test_focus_band_holds_on_one_time_in_ten(monkeypatch, poke, roll, hp, damage, expected):
    """A 0-99 roll under 10 (effect_param) leaves the holder at 1 HP from a KO hit"""
    d = poke("Rattata", 20, "Run Away", ["Tackle"], item="Focus Band")
    d[Pok.CURRENT_HP] = hp
    monkeypatch.setattr(engine_helper.random, "randint", lambda lo, hi: roll)
    assert endure_damage(d, damage) == expected


def test_focus_band_rolls_every_hit_but_not_under_endure(monkeypatch, poke):
    """pokeplatinum rolls on a hit that wouldn't KO too, Endure goes first and skips the roll"""
    rolls = []
    monkeypatch.setattr(engine_helper.random, "randint", lambda lo, hi: rolls.append((lo, hi)) or 99)
    d = poke("Rattata", 20, "Run Away", ["Tackle"], item="Focus Band")
    assert endure_damage(d, 1) == 1 and rolls == [(0, 99)]
    assert endure_damage(d, 0) == 0 and len(rolls) == 1
    d[Pok.VOL_STATUS] = VolStatus.ENDURE
    assert endure_damage(d, 10_000) == d[Pok.CURRENT_HP] - 1 and len(rolls) == 1


def test_confusion_self_hit_ignores_magic_guard(poke):
    """Issue 7: Magic Guard doesn't stop the self-hit (pokeplatinum subscript_hurt_self_in_confusion)"""
    p = poke("Abra", 50, "Magic Guard", ["Tackle"])
    confusion(p)
    assert p[Pok.CURRENT_HP] < p[Pok.MAX_HP]


@pytest.mark.parametrize("roll, survives", [(0, True), (99, False)])
def test_focus_band_holds_on_through_a_confusion_self_hit(monkeypatch, poke, roll, survives):
    """CheckHoldOnWith1HP runs in the self-hit too"""
    p = poke("Rattata", 50, "Run Away", ["Tackle"], item="Focus Band")
    p[Pok.CURRENT_HP] = 1
    monkeypatch.setattr(engine_helper.random, "randint", lambda lo, hi: roll)
    confusion(p)
    assert p[Pok.CURRENT_HP] == (1 if survives else 0)


def test_metronome_item_counts_the_same_move_up_to_ten(poke):
    """Another move starts over at 0, a failed counted move gives back one"""
    p = poke("Rattata", 20, "Run Away", ["Tackle", "Growl"], item="Metronome")
    tackle = MoveName.TACKLE << METRONOME_MOVE_SHIFT
    metronome_count(p, MoveName.TACKLE)
    assert p[Pok.METRONOME_COUNT] == tackle
    for _ in range(12):
        metronome_count(p, MoveName.TACKLE)
    assert p[Pok.METRONOME_COUNT] == tackle + 10
    metronome_fail(p, MoveName.TACKLE)
    assert p[Pok.METRONOME_COUNT] == tackle + 9
    metronome_fail(p, MoveName.GROWL)
    assert p[Pok.METRONOME_COUNT] == tackle + 9
    metronome_count(p, MoveName.GROWL)
    metronome_fail(p, MoveName.GROWL)
    assert p[Pok.METRONOME_COUNT] == MoveName.GROWL << METRONOME_MOVE_SHIFT


def test_metronome_count_needs_the_item_and_ends_on_switch_out(poke):
    """Without the item the count is 0 (the move stays, as in pokeplatinum), a switch clears both"""
    p = poke("Rattata", 20, "Run Away", ["Tackle"])
    tackle = MoveName.TACKLE << METRONOME_MOVE_SHIFT
    p[Pok.METRONOME_COUNT] = tackle + 3
    metronome_count(p, MoveName.TACKLE)
    assert p[Pok.METRONOME_COUNT] == tackle
    p[Pok.METRONOME_COUNT] = tackle + 3
    reset_switch_out(p)
    assert p[Pok.METRONOME_COUNT] == 0


def test_power_herb_is_used_up_on_a_charge_move_not_bide(poke):
    """Dig skips its charge turn and the herb can be recycled, Bide keeps the herb"""
    p = poke("Diglett", 20, "Sand Veil", ["Dig", "Bide"], item="Power Herb")
    assert not power_herb(p, move_slice(p, 1)) and p[Item.ID] == ItemNames.POWER_HERB
    assert power_herb(p, move_slice(p, 0))
    assert p[Item.ID] == 0 and p[Pok.CONSUMED_ITEM] == ItemNames.POWER_HERB
    assert not power_herb(p, move_slice(p, 0))


@pytest.mark.parametrize("drainer_ab, start_hp, expected_hp", [
    ("Chlorophyll", 30, 20), ("Chlorophyll", 5, 0), ("Magic Guard", 30, 30),
])
def test_liquid_ooze_hurts_the_drainer(poke, drainer_ab, start_hp, expected_hp):
    """The drainer loses what it would have healed, a Magic Guard drainer gets nothing (pokeplatinum
    subscript_drain_half_damage_dealt)"""
    p = poke("Oddish", 50, drainer_ab, ["Absorb"])
    ooze = poke("Tentacool", 50, "Liquid Ooze", ["Tackle"])
    p[Pok.CURRENT_HP] = start_hp
    drain(p, ooze, move_slice(p, 0), 20)
    assert p[Pok.CURRENT_HP] == expected_hp


@pytest.mark.parametrize("foe_ab, expected_hp", [("Run Away", 43), ("Liquid Ooze", 17)])
def test_big_root_boosts_drain_and_liquid_ooze(poke, foe_ab, expected_hp):
    """Half of 20 is 10, x130/100 is 13, applied before Liquid Ooze turns it into damage
    (pokeplatinum subscript_drain_half_damage_dealt)"""
    p = poke("Oddish", 50, "Chlorophyll", ["Absorb"], item="Big Root")
    d = poke("Tentacool", 50, foe_ab, ["Tackle"])
    p[Pok.CURRENT_HP] = 30
    drain(p, d, move_slice(p, 0), 20)
    assert p[Pok.CURRENT_HP] == expected_hp


@pytest.mark.parametrize("defender_ab, attacker_ab, holds", [
    ("Sticky Hold", "Run Away", True), ("Sticky Hold", "Mold Breaker", False),
    ("Run Away", "Run Away", False),
])
def test_sticky_hold_ignorable(poke, defender_ab, attacker_ab, holds):
    """Sticky Hold is breakable (pokeplatinum Battler_IgnorableAbility)"""
    d = poke("Grimer", 20, defender_ab, ["Tackle"])
    a = poke("Rattata", 20, attacker_ab, ["Tackle"])
    assert bool(sticky_hold(d, a)) == holds


# ── Batch 15: Normalize ──────────────────────────────────────────────────────

@pytest.mark.parametrize("move, defender, ability, outcome", [
    ("Lick", "Gastly", "Levitate", MoveOutcome.INVULNERABLE),
    ("Night Shade", "Gastly", "Levitate", MoveOutcome.INVULNERABLE),
    ("Thunder Wave", "Geodude", "Sturdy", MoveOutcome.HIT),
    ("Thunder Wave", "Gastly", "Levitate", MoveOutcome.INVULNERABLE),
    ("Earthquake", "Rattata", "Levitate", MoveOutcome.HIT),
    ("Thunder Shock", "Rattata", "Volt Absorb", MoveOutcome.HIT),
    ("Water Gun", "Rattata", "Water Absorb", MoveOutcome.HIT),
    ("Ember", "Ponyta", "Flash Fire", MoveOutcome.HIT),
    ("Ember", "Bulbasaur", "Wonder Guard", MoveOutcome.INVULNERABLE),
])
def test_normalize_hit_check(monkeypatch, poke, move, defender, ability, outcome):
    """The hit check, Levitate and the absorbing abilities see Normal (pokeplatinum ApplyTypeChart,
    TriggerImmunityAbility): Ghosts are immune, Ground types and Levitate aren't, nothing absorbs"""
    _always_hit(monkeypatch)
    a = poke("Skitty", 50, "Normalize", [move])
    d = poke(defender, 50, ability, ["Tackle"])
    d[Pok.CURRENT_HP] = 10
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == outcome
    assert d[Pok.CURRENT_HP] == 10 and not d[Pok.VOL_STATUS2] & VolStatus2.FLASH_FIRE


def test_normalize_fire_move_doesnt_thaw(poke):
    """The thaw checks the move's type after Normalize (pokeplatinum AFTER_MOVE_EFFECT_THAW_DEFENDER)"""
    a = poke("Skitty", 50, "Normalize", ["Ember"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    d[Pok.STATUS] = Status.FREEZE
    assert not thaw(a, move_slice(a, 0), d) and d[Pok.STATUS] == Status.FREEZE


@pytest.mark.parametrize("foe_ab, knows", [("Synchronize", True), ("Normalize", False)])
def test_anticipation_reads_the_foes_normalize(poke, foe_ab, knows):
    """A Normalize foe's Confusion is Normal, so it doesn't make Croagunk shudder"""
    p = poke("Croagunk", 20, "Anticipation", ["Tackle"])
    foe = poke("Abra", 20, foe_ab, ["Confusion"])
    switch_in(p, foe, empty_field(), True)
    assert bool(p[Pok.AB_KNOWN]) == knows


# ── Substitute ───────────────────────────────────────────────────────────────

def _with_sub(p, hp=None):
    """p behind a Substitute of hp HP (a quarter of its max HP by default)"""
    p[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
    p[Pok.SUB_HP] = max(1, p[Pok.MAX_HP] // 4) if hp is None else hp
    return p


def test_make_substitute_pays_a_quarter_and_frees_from_bind(poke):
    """pokeplatinum BtlCmd_TrySubstitute: Divide(max HP, 4) off the user, into the Substitute"""
    p = poke("Rattata", 50, "Run Away", ["Substitute"])
    p[Pok.VOL_STATUS] = VolStatus.PARTIALLY_TRAPPED
    p[Pok.TRAP_TURNS] = 3
    hp, cost = p[Pok.CURRENT_HP], p[Pok.MAX_HP] // 4
    make_substitute(p)
    assert p[Pok.CURRENT_HP] == hp - cost and p[Pok.SUB_HP] == cost
    assert p[Pok.VOL_STATUS2] & VolStatus2.SUBSTITUTE
    assert not p[Pok.VOL_STATUS] & VolStatus.PARTIALLY_TRAPPED and p[Pok.TRAP_TURNS] == 0
    assert not p[Pok.VOL_STATUS] & VolStatus.HURT_THIS_TURN


@pytest.mark.parametrize("already_up, hp_left", [(True, None), (False, 0)])
def test_substitute_fails(poke, already_up, hp_left):
    """Already behind one, or no more HP than it costs (hp_left: HP above the cost)"""
    p = poke("Rattata", 50, "Run Away", ["Substitute"])
    if already_up:
        _with_sub(p, 3)
    else:
        p[Pok.CURRENT_HP] = p[Pok.MAX_HP] // 4 + hp_left
    hp, sub_hp = p[Pok.CURRENT_HP], p[Pok.SUB_HP]
    assert substitute_fails(p)
    make_substitute(p)
    assert p[Pok.CURRENT_HP] == hp and p[Pok.SUB_HP] == sub_hp


def test_shedinja_cant_make_a_substitute(poke):
    """1 max HP: the cost is 1, so it never has more"""
    p = poke("Shedinja", 30, "Wonder Guard", ["Substitute"])
    p[Pok.MAX_HP] = p[Pok.CURRENT_HP] = 1
    assert substitute_fails(p)


@pytest.mark.parametrize("damage, lost, left", [(5, 5, 7), (12, 12, 0), (40, 12, 0)])
def test_hit_substitute(poke, damage, lost, left):
    """The Substitute takes damage up to its HP and breaks at 0, the rest is lost"""
    p = _with_sub(poke("Rattata", 50, "Run Away", ["Tackle"]), 12)
    hp = p[Pok.CURRENT_HP]
    assert hit_substitute(p, damage) == lost
    assert p[Pok.SUB_HP] == left and p[Pok.CURRENT_HP] == hp
    assert bool(p[Pok.VOL_STATUS2] & VolStatus2.SUBSTITUTE) == (left > 0)


@pytest.mark.parametrize("move, blocked", [
    ("Thunder Wave", True), ("Growl", True), ("Sing", True), ("Supersonic", True),
    ("Leech Seed", True), ("Swagger", True), ("Worry Seed", True), ("Yawn", True),
    ("Attract", False), ("Taunt", False), ("Encore", False), ("Disable", False),
    ("Roar", False), ("Psych Up", False), ("Foresight", False),
    ("Stealth Rock", False), ("Perish Song", False), ("Harden", False), ("Tackle", False),
])
def test_sub_blocks_move(poke, move, blocked):
    """Status moves aimed at the foe fail unless they bypass it, Gen IV sound moves included"""
    me = poke("Rattata", 30, "Run Away", [move])
    foe = _with_sub(poke("Rattata", 30, "Run Away", ["Tackle"]))
    assert sub_blocks_move(move_slice(me, 0), me, foe) == blocked
    foe[Pok.VOL_STATUS2] = 0
    assert not sub_blocks_move(move_slice(me, 0), me, foe)


@pytest.mark.parametrize("species, blocked", [("Gastly", True), ("Rattata", False)])
def test_sub_blocks_only_ghost_curse(poke, species, blocked):
    """A non-Ghost's Curse boosts the user, a Ghost's is aimed at the foe"""
    me = poke(species, 30, "Levitate", ["Curse"])
    foe = _with_sub(poke("Rattata", 30, "Run Away", ["Tackle"]))
    assert sub_blocks_move(move_slice(me, 0), me, foe) == blocked


@pytest.mark.parametrize("move, ability, reveals", [
    ("Thunder Wave", "Limber", True), ("Sing", "Insomnia", True), ("Yawn", "Vital Spirit", True),
    ("Confuse Ray", "Own Tempo", True), ("Swagger", "Own Tempo", False),
    ("Thunder Wave", "Run Away", False),
])
def test_sub_still_reveals_the_blocking_ability(poke, move, ability, reveals):
    """pokeplatinum's status subscripts check the ability before the Substitute, Swagger's
    checks the Substitute first"""
    me = poke("Rattata", 30, "Run Away", [move])
    foe = _with_sub(poke("Rattata", 30, ability, ["Tackle"]))
    assert sub_blocks_status_move(move_slice(me, 0), me, foe, 0)
    assert bool(foe[Pok.AB_KNOWN]) == reveals


def test_intimidate_skips_a_foe_behind_a_substitute(poke):
    """pokeplatinum subscript_intimidate"""
    me = poke("Shinx", 50, "Intimidate", ["Tackle"])
    foe = _with_sub(poke("Rattata", 50, "Run Away", ["Tackle"]))
    switch_in(me, foe, empty_field(), True)
    assert foe[Pok.ATTACK_STAT_STAGE] == 0


def test_download_ignores_a_foe_behind_a_substitute(poke):
    """pokeplatinum skips it in both sums, so neither stat goes up"""
    me = poke("Porygon", 20, "Download", ["Tackle"])
    foe = _with_sub(poke("Rattata", 20, "Run Away", ["Tackle"]))
    download(me, foe)
    assert me[Pok.ATTACK_STAT_STAGE] == me[Pok.SPECIAL_ATTACK_STAT_STAGE] == 0


def test_toxic_spikes_dont_poison_behind_a_substitute(poke):
    """A Baton Passed Substitute keeps Toxic Spikes off (pokeplatinum subscript_poison)"""
    p = _with_sub(poke("Rattata", 20, "Run Away", ["Tackle"]))
    apply_hazards(p, _field(TSPIKES, 2), MY_SIDE)
    assert p[Pok.STATUS] == 0


def test_switch_out_drops_the_substitute(poke):
    """The Substitute and its HP go with the Pokemon"""
    p = _with_sub(poke("Rattata", 20, "Run Away", ["Tackle"]))
    reset_switch_out(p)
    assert p[Pok.SUB_HP] == 0 and not p[Pok.VOL_STATUS2] & VolStatus2.SUBSTITUTE


# ── 4.2: Focus Sash, White Herb, Sticky Barb, Shell Bell, Life Orb, Destiny Knot ──

def _sash_holder(poke, hp=None):
    d = poke("Rattata", 20, "Run Away", ["Tackle"], item="Focus Sash")
    if hp is not None:
        d[Pok.CURRENT_HP] = hp
    return d


def test_focus_sash_holds_a_ko_at_full_hp_and_is_used_up(poke):
    """1 HP left, the Sash is gone and recyclable (pokeplatinum subscript_move_followup_message)"""
    d = _sash_holder(poke)
    full = int(d[Pok.MAX_HP])
    assert engine_helper.focus_sash_ready(d)
    assert endure_damage(d, 10_000, engine_helper.focus_sash_ready(d)) == full - 1
    assert d[Item.ID] == 0 and d[Pok.CONSUMED_ITEM] == ItemNames.FOCUS_SASH


@pytest.mark.parametrize("hp, damage", [(None, 1), (10, 10_000)])
def test_focus_sash_keeps_quiet_below_full_hp_or_on_a_non_ko(poke, hp, damage):
    """A hit that doesn't KO leaves it held, and it does nothing once the holder is hurt"""
    d = _sash_holder(poke, hp)
    assert endure_damage(d, damage, engine_helper.focus_sash_ready(d)) == damage
    assert d[Item.ID] == ItemNames.FOCUS_SASH


def test_focus_sash_flag_holds_later_hits_without_the_item(poke):
    """Once the Sash found its holder at full HP, every lethal hit of the move leaves 1 HP"""
    d = _sash_holder(poke, 1)
    engine_helper.clear_item(d)
    assert endure_damage(d, 50, True) == 0


def test_endure_goes_before_the_focus_sash(poke):
    """Endure holds on and the Sash stays (pokeplatinum: focusItemActivated only without Endure)"""
    d = _sash_holder(poke)
    d[Pok.VOL_STATUS] = VolStatus.ENDURE
    assert endure_damage(d, 10_000, engine_helper.focus_sash_ready(d)) == d[Pok.MAX_HP] - 1
    assert d[Item.ID] == ItemNames.FOCUS_SASH


def test_focus_sash_skips_the_confusion_self_hit(monkeypatch, poke):
    """Showdown: the Sash only reacts to a move's damage"""
    monkeypatch.setattr(engine_helper, "calculate_damage_confusion", lambda pok: 10_000)
    d = _sash_holder(poke)
    engine_helper.confusion(d)
    assert d[Pok.CURRENT_HP] == 0 and d[Item.ID] == ItemNames.FOCUS_SASH


def test_white_herb_restores_only_lowered_stages(poke):
    """Every stage below 0 back to 0, accuracy and evasion too, raised ones stay; used up"""
    p = poke("Rattata", 20, "Run Away", ["Tackle"], item="White Herb")
    p[Pok.ATTACK_STAT_STAGE] = -2
    p[Pok.DEFENSE_STAT_STAGE] = 3
    p[Pok.EVASION_STAT_STAGE] = -1
    engine_helper.status_item(p)
    assert p[Pok.ATTACK_STAT_STAGE] == 0 and p[Pok.EVASION_STAT_STAGE] == 0
    assert p[Pok.DEFENSE_STAT_STAGE] == 3
    assert p[Item.ID] == 0 and p[Pok.CONSUMED_ITEM] == ItemNames.WHITE_HERB


def test_white_herb_stays_without_a_drop(poke):
    """No lowered stage, nothing happens"""
    p = poke("Rattata", 20, "Run Away", ["Tackle"], item="White Herb")
    p[Pok.SPEED_STAT_STAGE] = 2
    engine_helper.status_item(p)
    assert p[Item.ID] == ItemNames.WHITE_HERB


def test_white_herb_answers_intimidate_on_the_foes_switch_in(make_pokemon, make_battle):
    """pokeplatinum SWITCH_IN_CHECK_STATE_HELD_ITEM_STATUS checks every active"""
    arr = make_battle([make_pokemon("Rattata", 20, "Run Away", ["Tackle"], item="White Herb")],
                      [make_pokemon("Growlithe", 20, "Intimidate", ["Tackle"])])
    me = my_active(arr)
    assert me[Pok.ATTACK_STAT_STAGE] == 0 and me[Item.ID] == 0
    assert me[Pok.CONSUMED_ITEM] == ItemNames.WHITE_HERB


def _barb_pair(poke, move="Tackle", attacker_item=None):
    a = poke("Rattata", 20, "Run Away", [move], item=attacker_item)
    d = poke("Rattata", 20, "Run Away", ["Tackle"], item="Sticky Barb")
    return a, d


def test_sticky_barb_moves_to_an_itemless_contact_attacker(poke):
    """The KO hit too, Sticky Hold doesn't stop it (pokeplatinum TriggerHeldItemOnHit)"""
    a, d = _barb_pair(poke)
    d[Pok.CURRENT_HP] = 0
    d[Pok.AB_ID] = AbilityNames.STICKY_HOLD
    engine_helper.sticky_barb_transfer(a, d, move_slice(a, 0), 5)
    assert a[Item.ID] == ItemNames.STICKY_BARB and d[Item.ID] == 0


@pytest.mark.parametrize("move, attacker_item, knocked, dealt", [
    ("Ember", None, 0, 5),            # no contact
    ("Tackle", "Oran Berry", 0, 5),   # attacker holds an item
    ("Knock Off", None, 0, 5),
    ("Tackle", None, 1, 5),           # its own item was knocked off
    ("Tackle", None, 0, 0),           # no damage taken
])
def test_sticky_barb_stays(poke, move, attacker_item, knocked, dealt):
    """Contact, an empty hand, damage dealt, and not Knock Off"""
    a, d = _barb_pair(poke, move, attacker_item)
    a[Pok.ITEM_KNOCKED_OFF] = knocked
    engine_helper.sticky_barb_transfer(a, d, move_slice(a, 0), dealt)
    assert d[Item.ID] == ItemNames.STICKY_BARB


@pytest.mark.parametrize("hp, dealt, hit_pok, healed", [
    (10, 40, True, 5), (10, 3, True, 1), (None, 40, True, 0), (10, 40, False, 0), (10, 0, True, 0),
])
def test_shell_bell_heals_an_eighth_of_the_damage(poke, hp, dealt, hit_pok, healed):
    """At least 1, not at full HP, nothing when only a Substitute was hit (pokeplatinum
    AFTER_MOVE_HIT_STATE_SHELL_BELL)"""
    a = poke("Rattata", 20, "Run Away", ["Tackle"], item="Shell Bell")
    if hp is not None:
        a[Pok.CURRENT_HP] = hp
    before = int(a[Pok.CURRENT_HP])
    engine_helper.after_move_hit_items(a, move_slice(a, 0), dealt, hit_pok)
    assert a[Pok.CURRENT_HP] - before == healed


@pytest.mark.parametrize("move, ability, hit_pok, recoil", [
    ("Tackle", "Run Away", True, True),
    ("Tackle", "Run Away", False, False),      # a Substitute took it
    ("Tackle", "Magic Guard", True, False),
    ("Seismic Toss", "Run Away", True, False),  # fixed damage (Showdown gen4)
    ("Guillotine", "Run Away", True, False),    # OHKO
    ("Counter", "Run Away", True, False),
])
def test_life_orb_recoil(poke, move, ability, hit_pok, recoil):
    """1/10 of max HP after a move with a base power that reached the Pokemon"""
    a = poke("Rattata", 20, ability, [move], item="Life Orb")
    full = int(a[Pok.MAX_HP])
    engine_helper.after_move_hit_items(a, move_slice(a, 0), 10, hit_pok)
    assert a[Pok.CURRENT_HP] == (full - max(1, full // 10) if recoil else full)


def test_destiny_knot_through_cute_charm(monkeypatch, poke):
    """The infatuated knot holder infatuates the Cute Charm user back"""
    _fix_rolls(monkeypatch, 0)
    a = poke("Rattata", 50, "Run Away", ["Tackle"], item="Destiny Knot")
    a[Pok.GENDER] = Gender.MALE
    d = poke("Clefairy", 50, "Cute Charm", ["Pound"])
    d[Pok.GENDER] = Gender.FEMALE
    on_hit_abilities(a, d, move_slice(a, 0), 10, 0)
    assert a[Pok.VOL_STATUS] & VolStatus.ATTRACT and d[Pok.VOL_STATUS] & VolStatus.ATTRACT


# ── 4.3 Berries ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("item, status, vol, cured", [
    ("Cheri Berry", Status.PARALYSIS, 0, True),
    ("Cheri Berry", Status.BURN, 0, False),
    ("Rawst Berry", Status.BURN, 0, True),
    ("Rawst Berry", Status.FREEZE, 0, False),
    ("Aspear Berry", Status.FREEZE, 0, True),
    ("Aspear Berry", Status.SLEEP, 0, False),
    ("Persim Berry", 0, VolStatus.CONFUSION, True),
    ("Persim Berry", Status.PARALYSIS, 0, False),
])
def test_status_berries(poke, item, status, vol, cured):
    """Each cures its own condition after a move and is used up, recyclable (pokeplatinum
    BattleSystem_TriggerHeldItemOnStatus)"""
    p = poke("Rattata", 50, "Run Away", ["Tackle"], item=item)
    held = p[Item.ID]
    p[Pok.STATUS] = status
    p[Pok.VOL_STATUS] = vol
    engine_helper.status_item(p)
    if cured:
        assert p[Pok.STATUS] == 0 and p[Pok.VOL_STATUS] == 0
        assert p[Item.ID] == 0 and p[Pok.CONSUMED_ITEM] == held
    else:
        assert p[Pok.STATUS] == status and p[Item.ID] == held


def _pp(pok, slot):
    return pok[Pok.MOVE1_ID + slot * (Pok.MOVE2_ID - Pok.MOVE1_ID) + Move.PP]


def _set_pp(pok, slot, value):
    pok[Pok.MOVE1_ID + slot * (Pok.MOVE2_ID - Pok.MOVE1_ID) + Move.PP] = value


def test_leppa_waits_for_a_move_at_zero_pp(poke):
    """Held, Leppa does nothing while every move has PP, then gives the first empty one 10"""
    p = poke("Rattata", 50, "Run Away", ["Tackle", "Quick Attack", "Bite"], item="Leppa Berry")
    _set_pp(p, 0, 3)
    engine_helper.status_item(p)
    assert p[Item.ID] == ItemNames.LEPPA_BERRY
    _set_pp(p, 1, 0)
    _set_pp(p, 2, 0)
    engine_helper.status_item(p)
    assert (_pp(p, 0), _pp(p, 1), _pp(p, 2)) == (3, 10, 0)
    assert p[Item.ID] == 0 and p[Pok.CONSUMED_ITEM] == ItemNames.LEPPA_BERRY


@pytest.mark.parametrize("pp_ups, restored", [(0, 5), (3, 8)])
def test_leppa_stops_at_max_pp(poke, pp_ups, restored):
    """A 5 PP move gets back at most its max: 5 + 20% per PP Up (pokeplatinum MoveTable_CalcMaxPP)"""
    p = poke("Rattata", 50, "Run Away", ["Blizzard"], item="Leppa Berry")
    p[Pok.MOVE1_ID + Move.PP_UP] = pp_ups
    _set_pp(p, 0, 0)
    engine_helper.status_item(p)
    assert _pp(p, 0) == restored


@pytest.mark.parametrize("item, nature, confused", [
    ("Figy Berry", "Modest", True),     # -Atk dislikes spicy
    ("Figy Berry", "Adamant", False),
    ("Wiki Berry", "Adamant", True),    # -SpA, dry
    ("Mago Berry", "Brave", True),      # -Spe, sweet
    ("Aguav Berry", "Naughty", True),   # -SpD, bitter
    ("Iapapa Berry", "Lonely", True),   # -Def, sour
    ("Iapapa Berry", "Hardy", False),
])
def test_flavor_berries(make_pokemon, item, nature, confused):
    """At half HP they heal 1/8 of max HP, and confuse a nature that dislikes their flavor
    (pokeplatinum HOLD_EFFECT_HP_RESTORE_*, Gen IV numbers)"""
    p = make_pokemon("Rattata", 50, "Run Away", ["Tackle"], item=item, nature=nature).to_np()
    half = p[Pok.MAX_HP] // 2
    p[Pok.CURRENT_HP] = half + 1
    eat_berry(p)
    assert p[Item.ID] != 0
    p[Pok.CURRENT_HP] = half
    eat_berry(p)
    assert p[Pok.CURRENT_HP] == half + p[Pok.MAX_HP] // 8
    assert bool(p[Pok.VOL_STATUS] & VolStatus.CONFUSION) == confused
    if confused:
        assert 2 <= p[Pok.CONFUSION_COUNTER] <= 5
    assert p[Item.ID] == 0 and p[Pok.CONSUMED_ITEM] != 0


def test_flavor_berry_own_tempo_isnt_confused(make_pokemon):
    """Own Tempo stops the berry's confusion, the heal still happens"""
    p = make_pokemon("Spinda", 50, "Own Tempo", ["Tackle"], item="Figy Berry",
                     nature="Modest").to_np()
    p[Pok.CURRENT_HP] = 1
    eat_berry(p)
    assert p[Pok.CURRENT_HP] > 1 and not p[Pok.VOL_STATUS] & VolStatus.CONFUSION


@pytest.mark.parametrize("item, stage", [
    ("Liechi Berry", Pok.ATTACK_STAT_STAGE), ("Ganlon Berry", Pok.DEFENSE_STAT_STAGE),
    ("Petaya Berry", Pok.SPECIAL_ATTACK_STAT_STAGE),
    ("Apicot Berry", Pok.SPECIAL_DEFENSE_STAT_STAGE), ("Salac Berry", Pok.SPEED_STAT_STAGE),
])
def test_pinch_stat_berries(poke, item, stage):
    """+1 to their stat at a quarter of max HP, used up (pokeplatinum HOLD_EFFECT_PINCH_*)"""
    p = poke("Rattata", 50, "Run Away", ["Tackle"], item=item)
    quarter = p[Pok.MAX_HP] // 4
    p[Pok.CURRENT_HP] = quarter + 1
    item_on_rdmg(p)
    assert p[stage] == 0 and p[Item.ID] != 0
    p[Pok.CURRENT_HP] = quarter
    item_on_rdmg(p)
    assert p[stage] == 1 and p[Item.ID] == 0 and p[Pok.CONSUMED_ITEM] != 0


def test_pinch_berry_kept_at_plus_six(poke):
    """At +6 it has nothing to do and stays held, a stat drop lets it work after the next move"""
    p = poke("Rattata", 50, "Run Away", ["Tackle"], item="Liechi Berry")
    p[Pok.CURRENT_HP] = 1
    p[Pok.ATTACK_STAT_STAGE] = 6
    item_on_rdmg(p)
    assert p[Item.ID] == ItemNames.LIECHI_BERRY
    p[Pok.ATTACK_STAT_STAGE] = 5
    engine_helper.status_item(p)
    assert p[Pok.ATTACK_STAT_STAGE] == 6 and p[Item.ID] == 0


def test_gluttony_eats_pinch_berries_at_half(poke):
    """Gluttony halves the effect param: half HP instead of a quarter"""
    p = poke("Zigzagoon", 50, "Gluttony", ["Tackle"], item="Salac Berry")
    p[Pok.CURRENT_HP] = p[Pok.MAX_HP] // 2
    item_on_rdmg(p)
    assert p[Pok.SPEED_STAT_STAGE] == 1 and p[Item.ID] == 0


def test_gluttony_doesnt_change_the_half_hp_berries(poke):
    """Sitrus and the confusion berries already work at half"""
    p = poke("Zigzagoon", 50, "Gluttony", ["Tackle"], item="Sitrus Berry")
    p[Pok.CURRENT_HP] = p[Pok.MAX_HP] // 2 + 1
    item_on_rdmg(p)
    assert p[Item.ID] == ItemNames.SITRUS_BERRY


def test_lansat_sets_focus_energy(poke):
    """Lansat gives Focus Energy, and stays held when it's already on"""
    p = poke("Rattata", 50, "Run Away", ["Tackle"], item="Lansat Berry")
    p[Pok.CURRENT_HP] = 1
    p[Pok.VOL_STATUS] = VolStatus.FOCUS_ENERGY
    item_on_rdmg(p)
    assert p[Item.ID] == ItemNames.LANSAT_BERRY
    p[Pok.VOL_STATUS] = 0
    item_on_rdmg(p)
    assert p[Pok.VOL_STATUS] & VolStatus.FOCUS_ENERGY and p[Item.ID] == 0


def test_starf_raises_a_stat_that_isnt_maxed(poke):
    """+2 to a random stat from Attack to Speed, never one at +6, never accuracy or evasion"""
    for _ in range(20):
        p = poke("Rattata", 50, "Run Away", ["Tackle"], item="Starf Berry")
        p[Pok.CURRENT_HP] = 1
        p[Pok.ATTACK_STAT_STAGE:Pok.SPEED_STAT_STAGE] = 6
        p[Pok.SPEED_STAT_STAGE] = 5
        item_on_rdmg(p)
        assert p[Pok.SPEED_STAT_STAGE] == 6 and p[Item.ID] == 0
        assert p[Pok.ACCURACY_STAT_STAGE] == 0 and p[Pok.EVASION_STAT_STAGE] == 0
    p = poke("Rattata", 50, "Run Away", ["Tackle"], item="Starf Berry")
    p[Pok.CURRENT_HP] = 1
    p[Pok.ATTACK_STAT_STAGE:Pok.SPEED_STAT_STAGE + 1] = 6
    item_on_rdmg(p)
    assert p[Item.ID] == ItemNames.STARF_BERRY


def test_starf_rng_only_when_it_triggers(poke):
    """No RNG call above the threshold, so other scenarios keep their RNG order"""
    p = poke("Rattata", 50, "Run Away", ["Tackle"], item="Starf Berry")
    state = random.getstate()
    item_on_rdmg(p)
    assert random.getstate() == state


def test_micle_boosts_the_next_roll_only(poke):
    """x120/100 on the holder's next accuracy roll, then it's gone; an always-hit move keeps it
    (pokeplatinum BattleControllerPlayer_CheckMoveHitAccuracy)"""
    a = poke("Rattata", 50, "Run Away", ["Fury Attack", "Swift"], item="Micle Berry")
    d = poke("Geodude", 50, "Sturdy", ["Tackle"])
    a[Pok.CURRENT_HP] = 1
    item_on_rdmg(a)
    assert a[Pok.VOL_STATUS2] & VolStatus2.MICLE and a[Item.ID] == 0
    fury = move_slice(a, 0)
    assert move_accuracy(fury, a, d, 85, 0) == 85 * 120 // 100
    calculate_hit_miss(move_slice(a, 1), a, d, 0)
    assert a[Pok.VOL_STATUS2] & VolStatus2.MICLE
    calculate_hit_miss(fury, a, d, 0)
    assert not a[Pok.VOL_STATUS2] & VolStatus2.MICLE
    assert move_accuracy(fury, a, d, 85, 0) == 85


def test_micle_ends_on_switch_out(poke):
    """It's a battler flag: switching out drops it"""
    p = poke("Rattata", 50, "Run Away", ["Tackle"])
    p[Pok.VOL_STATUS2] = VolStatus2.MICLE
    reset_switch_out(p)
    assert not p[Pok.VOL_STATUS2] & VolStatus2.MICLE


@pytest.mark.parametrize("hp_quarter, first", [(True, True), (False, False)])
def test_custap_moves_first_in_its_bracket(poke, hp_quarter, first):
    """In a pinch the slower holder goes first and eats it (pokeplatinum CompareBattlerSpeed)"""
    slow = poke("Geodude", 50, "Sturdy", ["Tackle"], item="Custap Berry")
    fast = poke("Rattata", 50, "Run Away", ["Tackle"])
    slow[Pok.CURRENT_HP] = slow[Pok.MAX_HP] // 4 + (0 if hp_quarter else 1)
    assert move_order(slow, 0, fast, 0, False, False, 0)[3] is first
    assert (slow[Item.ID] == 0) == first
    if first:
        assert slow[Pok.CONSUMED_ITEM] == ItemNames.CUSTAP_BERRY


def test_custap_eaten_against_a_higher_priority(poke):
    """Quick Attack still goes first, the berry is eaten anyway"""
    slow = poke("Geodude", 50, "Sturdy", ["Tackle"], item="Custap Berry")
    fast = poke("Rattata", 50, "Run Away", ["Quick Attack"])
    slow[Pok.CURRENT_HP] = 1
    assert move_order(slow, 0, fast, 0, False, False, 0)[3] is False
    assert slow[Item.ID] == 0


def test_custap_kept_when_the_foe_switches(poke):
    """Only when both sides use a move"""
    slow = poke("Geodude", 50, "Sturdy", ["Tackle"], item="Custap Berry")
    other = poke("Rattata", 50, "Run Away", ["Tackle"])
    slow[Pok.CURRENT_HP] = 1
    move_order(slow, 0, other, -1, False, True, 0)
    assert slow[Item.ID] == ItemNames.CUSTAP_BERRY


def test_bug_bite_persim_raises_attack(poke):
    """pokeplatinum PluckBerry's CNF_RESTORE falls into ATK_UP: below +6 Attack goes up and the
    confusion stays, at +6 it cures"""
    atk = poke("Kricketune", 50, "Swarm", ["Bug Bite"])
    atk[Pok.VOL_STATUS] = VolStatus.CONFUSION
    eat_berry_bug_bite(atk, poke("Rattata", 50, "Run Away", ["Tackle"], item="Persim Berry"))
    assert atk[Pok.ATTACK_STAT_STAGE] == 1 and atk[Pok.VOL_STATUS] & VolStatus.CONFUSION
    atk[Pok.ATTACK_STAT_STAGE] = 6
    eat_berry_bug_bite(atk, poke("Rattata", 50, "Run Away", ["Tackle"], item="Persim Berry"))
    assert not atk[Pok.VOL_STATUS] & VolStatus.CONFUSION


def test_bug_bite_leppa_takes_the_move_missing_most(poke):
    """Plucked, Leppa picks the move missing the most PP, not one at 0 (pokeplatinum PluckBerry)"""
    atk = poke("Kricketune", 50, "Swarm", ["Bug Bite", "Tackle"])
    _set_pp(atk, 0, 1)   # 19 missing
    _set_pp(atk, 1, 5)   # 30 missing
    eat_berry_bug_bite(atk, poke("Rattata", 50, "Run Away", ["Tackle"], item="Leppa Berry"))
    assert (_pp(atk, 0), _pp(atk, 1)) == (1, 15)


def test_bug_bite_pinch_berry_ignores_hp(poke):
    """Plucked, a pinch berry works at full HP"""
    atk = poke("Kricketune", 50, "Swarm", ["Bug Bite"])
    eat_berry_bug_bite(atk, poke("Rattata", 50, "Run Away", ["Tackle"], item="Liechi Berry"))
    assert atk[Pok.ATTACK_STAT_STAGE] == 1


def test_bug_bite_flavor_berry_at_full_hp_does_nothing(make_pokemon, poke):
    """Plucked at full HP: no heal and no confusion, the berry is still gone"""
    atk = make_pokemon("Kricketune", 50, "Swarm", ["Bug Bite"], nature="Modest").to_np()
    dfn = poke("Rattata", 50, "Run Away", ["Tackle"], item="Figy Berry")
    eat_berry_bug_bite(atk, dfn)
    assert not atk[Pok.VOL_STATUS] & VolStatus.CONFUSION and dfn[Item.ID] == 0


@pytest.mark.parametrize("move, healed", [("Bubble", True), ("Tackle", False)])
def test_enigma_heals_after_a_super_effective_hit(poke, move, healed):
    """1/4 of max HP after a super effective hit (Showdown enigmaberry)"""
    a = poke("Squirtle", 50, "Torrent", [move])
    d = poke("Geodude", 50, "Sturdy", ["Tackle"], item="Enigma Berry")
    d[Pok.CURRENT_HP] = 10
    engine_helper.on_hit_berries(a, d, move_slice(a, 0), 5)
    assert d[Pok.CURRENT_HP] == (10 + d[Pok.MAX_HP] // 4 if healed else 10)
    assert (d[Item.ID] == 0) == healed


def test_enigma_not_on_a_ko_or_fixed_damage(poke):
    """A fainted holder doesn't heal, and a fixed damage move has no type effectiveness"""
    a = poke("Squirtle", 50, "Torrent", ["Bubble", "Seismic Toss"])
    d = poke("Geodude", 50, "Sturdy", ["Tackle"], item="Enigma Berry")
    d[Pok.CURRENT_HP] = 0
    engine_helper.on_hit_berries(a, d, move_slice(a, 0), 5)
    assert d[Item.ID] == ItemNames.ENIGMA_BERRY
    d[Pok.CURRENT_HP] = 10
    engine_helper.on_hit_berries(a, d, move_slice(a, 1), 5)
    assert d[Item.ID] == ItemNames.ENIGMA_BERRY


@pytest.mark.parametrize("item, move, hurts", [
    ("Jaboca Berry", "Tackle", True), ("Jaboca Berry", "Bubble", False),
    ("Rowap Berry", "Bubble", True), ("Rowap Berry", "Tackle", False),
])
def test_jaboca_rowap(poke, item, move, hurts):
    """Jaboca answers a physical hit, Rowap a special one: 1/8 of the attacker's max HP"""
    a = poke("Squirtle", 50, "Torrent", [move])
    d = poke("Geodude", 50, "Sturdy", ["Tackle"], item=item)
    full = int(a[Pok.MAX_HP])
    engine_helper.on_hit_berries(a, d, move_slice(a, 0), 5)
    assert a[Pok.CURRENT_HP] == (full - full // 8 if hurts else full)
    assert (d[Item.ID] == 0) == hurts


def test_jaboca_from_a_fainted_holder(poke):
    """The KO hit still costs the attacker, the holder needn't be alive"""
    a = poke("Squirtle", 50, "Torrent", ["Tackle"])
    d = poke("Geodude", 50, "Sturdy", ["Tackle"], item="Jaboca Berry")
    d[Pok.CURRENT_HP] = 0
    engine_helper.on_hit_berries(a, d, move_slice(a, 0), 5)
    assert a[Pok.CURRENT_HP] < a[Pok.MAX_HP] and d[Item.ID] == 0


def test_jaboca_magic_guard(poke):
    """Magic Guard takes nothing and the berry stays"""
    a = poke("Clefairy", 50, "Magic Guard", ["Pound"])
    d = poke("Geodude", 50, "Sturdy", ["Tackle"], item="Jaboca Berry")
    engine_helper.on_hit_berries(a, d, move_slice(a, 0), 5)
    assert a[Pok.CURRENT_HP] == a[Pok.MAX_HP] and d[Item.ID] == ItemNames.JABOCA_BERRY
