"""Engine helpers: speed, turn order, accuracy, crits, switching, items, residuals"""
import random
import pytest
from Engine.engine_helper import (
    check_speed, move_order, calculate_hit_miss, calculate_crit, reset_switch_out,
    switch_in, trainer_ai_items, eat_berry, drain, weather_dmg, early_returns, struggle,
    thaw, heal_weather, on_residual, flinch_checker,
)
from Models.idx_const import Pok, Move, Item, Sec
from Models.helper import Status, Weather, VolStatus, Potions, MoveOutcome
from DataBase.ItemDB import ItemNames
from battle_driver import move_slice



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
    """Water move into Water Absorb heals 1/4 and doesn't land"""
    a = poke("Squirtle", 50, "Torrent", ["Water Gun"])
    d = poke("Mudkip", 50, "Water Absorb", ["Tackle"])
    d[Pok.CURRENT_HP] = 10
    assert calculate_hit_miss(move_slice(a, 0), a, d, 0) == MoveOutcome.MISS
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
    switch_in(me, foe)
    assert foe[Pok.ATTACK_STAT_STAGE] == -1
    foe[Pok.ATTACK_STAT_STAGE] = -6
    switch_in(me, foe)
    assert foe[Pok.ATTACK_STAT_STAGE] == -6
    switch_in(foe, me)
    assert me[Pok.ATTACK_STAT_STAGE] == 0


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


def test_drain_half_with_minimum_one(poke):
    """Absorb heals half the damage dealt, at least 1, capped at max"""
    p = poke("Oddish", 50, "Chlorophyll", ["Absorb"])
    absorb = move_slice(p, 0)
    p[Pok.CURRENT_HP] = 10
    drain(p, absorb, 20)
    assert p[Pok.CURRENT_HP] == 20
    drain(p, absorb, 1)
    assert p[Pok.CURRENT_HP] == 21
    drain(p, absorb, 10_000)
    assert p[Pok.CURRENT_HP] == p[Pok.MAX_HP]


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
])
def test_weather_damage(poke, name, ability, weather, fraction):
    """Sandstorm/Hail chip 1/16 unless immune; Solar Power costs 1/8 in sun"""
    p = poke(name, 100, ability, ["Tackle"])
    expected = p[Pok.MAX_HP] // fraction if fraction else 0
    assert weather_dmg(p, weather, p[Pok.MAX_HP]) == expected


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
    assert not thaw(move_slice(a, 1), d) and d[Pok.STATUS] == Status.FREEZE
    assert thaw(move_slice(a, 0), d) and d[Pok.STATUS] == 0


# ── early_returns (the "can I act this turn" gate) ───────────────────────────

def test_sleep_blocks_until_counter_runs_out(poke):
    """Asleep with counter > 0: blocked and counts down; at 0 wakes and acts"""
    a = poke("Rattata", 50, "Run Away", ["Tackle"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    mv = move_slice(a, 0)
    a[Pok.STATUS] = Status.SLEEP
    a[Pok.SLEEP_COUNTER] = 2
    assert early_returns(a, d, 1, False, mv)
    assert early_returns(a, d, 1, False, mv)
    assert a[Pok.SLEEP_COUNTER] == 0
    assert not early_returns(a, d, 1, False, mv)
    assert a[Pok.STATUS] == 0


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
    assert early_returns(a, d, 2, False, mv)
    a[Pok.DMG_TAKEN] = 20
    assert early_returns(a, d, 1, False, mv)
    assert not early_returns(a, d, 2, False, mv)


def test_attack_into_fainted_target_fails(poke):
    """Targeting a fainted foe fails, self-targeting moves still go"""
    a = poke("Geodude", 50, "Sturdy", ["Tackle", "Harden"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    d[Pok.CURRENT_HP] = 0
    assert early_returns(a, d, 2, False, move_slice(a, 0))
    assert not early_returns(a, d, 2, False, move_slice(a, 1))


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
    assert flinch_checker(mv, d, True)
    assert not flinch_checker(mv, d)
    d2 = poke("Rattata", 50, "Inner Focus", ["Tackle"])
    assert not flinch_checker(mv, d2, True)
