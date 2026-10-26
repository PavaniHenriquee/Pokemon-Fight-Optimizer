"""Damage formula, stat stages and modifiers (roll fixed at 100 unless stated)"""
import pytest
from Engine.damage_calc import (
    apply_stat_stage, calculate_damage, calculate_damage_confusion, flail,
)
from Utils.helper import get_type_effectiveness, stage_to_multiplier
from Models.idx_const import Pok
from Models.helper import Types, Status, Weather
from battle_driver import move_slice


def dmg(attacker, defender, slot=0, weather=0, crit=False, roll=100):
    """Damage of attacker's move `slot` against defender"""
    return calculate_damage(attacker, defender, move_slice(attacker, slot), weather, crit, roll)


def ratio(a, b):
    """a / b, for checking multipliers through integer flooring"""
    assert b > 0
    return a / b


# ── Pure math ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("stage, expected", [
    (0, 100), (1, 150), (2, 200), (6, 400), (-1, 66), (-2, 50), (-6, 25),
])
def test_apply_stat_stage(stage, expected):
    """Gen IV stage table: (2+n)/2 up, 2/(2+n) down"""
    assert apply_stat_stage(100, stage, False) == expected


def test_simple_doubles_stages_and_clamps():
    """Simple doubles the stage but still caps at ±6"""
    assert apply_stat_stage(100, 1, True) == 200
    assert apply_stat_stage(100, 4, True) == 400
    assert apply_stat_stage(100, -4, True) == 25


@pytest.mark.parametrize("stage, expected", [(0, 100), (1, 150), (-1, 66), (6, 400), (-6, 25)])
def test_stage_to_multiplier_matches_table(stage, expected):
    """Speed uses the same table through Utils.helper"""
    assert stage_to_multiplier(stage, 100) == expected


@pytest.mark.parametrize("atk, d1, d2, expected", [
    (Types.FIRE, Types.GRASS, 0, 2.0),
    (Types.WATER, Types.FIRE, 0, 2.0),
    (Types.FIRE, Types.WATER, 0, 0.5),
    (Types.NORMAL, Types.GHOST, 0, 0.0),
    (Types.ELECTRIC, Types.GROUND, 0, 0.0),
    (Types.NORMAL, Types.NORMAL, 0, 1.0),
    (Types.ELECTRIC, Types.WATER, Types.FLYING, 4.0),
    (Types.GRASS, Types.ROCK, Types.GROUND, 4.0),
    (Types.FIRE, Types.WATER, Types.ROCK, 0.25),
    (Types.FIRE, Types.GRASS, Types.WATER, 1.0),
])
def test_type_chart(atk, d1, d2, expected):
    """Effectiveness returned as (numerator, denominator)"""
    num, den = get_type_effectiveness(atk, d1, d2)
    assert num / den == expected


@pytest.mark.parametrize("hp_48ths, power", [
    (1, 200), (4, 150), (9, 100), (16, 80), (32, 40), (48, 20),
])
def test_flail_power_bands(poke, hp_48ths, power):
    """Flail power from HP*48/max thresholds"""
    p = poke("Magikarp", 100, "Swift Swim", ["Flail"])
    p[Pok.MAX_HP] = 48
    p[Pok.CURRENT_HP] = hp_48ths
    assert flail(p) == power


# ── Full damage formula ──────────────────────────────────────────────────────

def test_exact_level5_scratch(poke):
    """Charmander (Atk 11) Scratch vs Squirtle (Def 13), max roll, no crit:
    floor(4*40*11/13/50)=2, +2 = 4, neutral, no STAB → 4"""
    char = poke("Charmander", 5, "Blaze", ["Scratch"])
    squirt = poke("Squirtle", 5, "Torrent", ["Tackle"])
    assert char[Pok.ATTACK] == 11 and squirt[Pok.DEFENSE] == 13
    assert dmg(char, squirt) == 4


def test_damage_is_deterministic_with_fixed_roll(poke):
    """Same inputs, same damage, nothing mutated"""
    a = poke("Charmander", 50, "Blaze", ["Ember"])
    d = poke("Bulbasaur", 50, "Overgrow", ["Tackle"])
    before = (a.copy(), d.copy())
    assert dmg(a, d) == dmg(a, d)
    assert (a == before[0]).all() and (d == before[1]).all()


def test_random_roll_stays_in_85_100_band(poke):
    """Without a fixed roll the result is between the min and max roll"""
    a = poke("Charmander", 100, "Blaze", ["Ember"])
    d = poke("Squirtle", 100, "Torrent", ["Tackle"])
    low, high = dmg(a, d, roll=85), dmg(a, d, roll=100)
    for _ in range(200):
        assert low <= calculate_damage(a, d, move_slice(a, 0), 0, False) <= high


def test_stab(poke):
    """Same-type attack bonus is 1.5x"""
    a = poke("Charmander", 100, "Solar Power", ["Ember"])
    d = poke("Rattata", 100, "Guts", ["Tackle"])
    stab = dmg(a, d)
    a[Pok.TYPE1] = Types.NORMAL
    assert ratio(stab, dmg(a, d)) == pytest.approx(1.5, abs=0.05)


def test_super_effective_and_resisted(poke):
    """Fire vs Grass 2x, Fire vs Water 0.5x, relative to a Normal target"""
    a = poke("Charmander", 100, "Solar Power", ["Ember"])
    d = poke("Rattata", 100, "Guts", ["Tackle"])
    neutral = dmg(a, d)
    d[Pok.TYPE1] = Types.GRASS
    assert ratio(dmg(a, d), neutral) == pytest.approx(2.0, abs=0.05)
    d[Pok.TYPE1] = Types.WATER
    assert ratio(dmg(a, d), neutral) == pytest.approx(0.5, abs=0.05)


def test_immunity_is_zero(poke):
    """Normal into Ghost does nothing, even with crit and max roll"""
    a = poke("Rattata", 100, "Guts", ["Tackle"])
    d = poke("Gastly", 100, "Levitate", ["Lick"])
    assert dmg(a, d) == 0
    assert dmg(a, d, crit=True) == 0


def test_crit_doubles(poke):
    """Gen IV crit is 2x"""
    a = poke("Rattata", 100, "Run Away", ["Tackle"])
    d = poke("Geodude", 100, "Sturdy", ["Tackle"])
    d[Pok.TYPE1], d[Pok.TYPE2] = Types.NORMAL, 0
    assert ratio(dmg(a, d, crit=True), dmg(a, d)) == pytest.approx(2.0, abs=0.1)


def test_crit_ignores_bad_attacker_stages_and_good_defender_stages(poke):
    """On crit: negative attack stages and positive defense stages are dropped"""
    a = poke("Rattata", 100, "Run Away", ["Tackle"])
    d = poke("Rattata", 100, "Run Away", ["Tackle"])
    clean = dmg(a, d, crit=True)
    a[Pok.ATTACK_STAT_STAGE] = -2
    d[Pok.DEFENSE_STAT_STAGE] = 2
    assert dmg(a, d, crit=True) == clean
    assert dmg(a, d) < clean


def test_attack_stage_scales_damage(poke):
    """+2 Attack roughly doubles damage"""
    a = poke("Rattata", 100, "Run Away", ["Tackle"])
    d = poke("Rattata", 100, "Run Away", ["Tackle"])
    base = dmg(a, d)
    a[Pok.ATTACK_STAT_STAGE] = 2
    assert ratio(dmg(a, d), base) == pytest.approx(2.0, abs=0.1)


def test_burn_halves_physical_but_not_with_guts(poke):
    """Burn halves physical damage; Guts ignores the cut and boosts Atk 1.5x"""
    a = poke("Rattata", 100, "Run Away", ["Tackle", "Ember"])
    d = poke("Rattata", 100, "Run Away", ["Tackle"])
    phys, spec = dmg(a, d, 0), dmg(a, d, 1)
    a[Pok.STATUS] = Status.BURN
    assert ratio(dmg(a, d, 0), phys) == pytest.approx(0.5, abs=0.05)
    assert dmg(a, d, 1) == spec
    guts = poke("Rattata", 100, "Guts", ["Tackle"])
    guts[Pok.STATUS] = Status.BURN
    assert ratio(dmg(guts, d), phys) == pytest.approx(1.5, abs=0.05)


@pytest.mark.parametrize("weather, fire_mult, water_mult", [
    (Weather.SUN, 1.5, 0.5),
    (Weather.RAIN, 0.5, 1.5),
])
def test_weather_modifiers(poke, weather, fire_mult, water_mult):
    """Sun/Rain boost and cut Fire/Water"""
    a = poke("Rattata", 100, "Run Away", ["Ember", "Water Gun"])
    d = poke("Rattata", 100, "Run Away", ["Tackle"])
    fire, water = dmg(a, d, 0), dmg(a, d, 1)
    assert ratio(dmg(a, d, 0, weather), fire) == pytest.approx(fire_mult, abs=0.07)
    assert ratio(dmg(a, d, 1, weather), water) == pytest.approx(water_mult, abs=0.07)


@pytest.mark.parametrize("weather", [Weather.HAIL, Weather.SANDSTORM])
def test_special_damage_unaffected_by_unrelated_weather(poke, weather):
    """Regression: clear weather used to give every special hit the Sandstorm Sp.Def boost.
    Hail, and Sandstorm on a non-Rock target, deal the same as clear weather"""
    a = poke("Rattata", 100, "Run Away", ["Ember"])
    d = poke("Rattata", 100, "Run Away", ["Tackle"])
    assert dmg(a, d, weather=weather) == dmg(a, d)


def test_sandstorm_boosts_rock_defender_spdef(poke):
    """Rock-type DEFENDER gets 1.5x Sp.Def in Sandstorm; a Rock attacker gets nothing"""
    a = poke("Rattata", 100, "Run Away", ["Ember"])
    rock = poke("Rattata", 100, "Run Away", ["Tackle"])
    rock[Pok.TYPE1] = Types.ROCK
    assert ratio(dmg(a, rock, weather=Weather.SANDSTORM), dmg(a, rock)) == \
        pytest.approx(2 / 3, abs=0.05)
    rock_attacker = poke("Rattata", 100, "Run Away", ["Ember"])
    rock_attacker[Pok.TYPE1] = Types.ROCK
    plain = poke("Rattata", 100, "Run Away", ["Tackle"])
    assert dmg(rock_attacker, plain, weather=Weather.SANDSTORM) == dmg(rock_attacker, plain)


def test_blaze_below_one_third(poke):
    """Blaze boosts Fire moves 1.5x at <= 1/3 HP, not above"""
    a = poke("Charmander", 100, "Blaze", ["Ember", "Scratch"])
    d = poke("Rattata", 100, "Run Away", ["Tackle"])
    full_fire, full_normal = dmg(a, d, 0), dmg(a, d, 1)
    a[Pok.CURRENT_HP] = a[Pok.MAX_HP] // 3
    assert ratio(dmg(a, d, 0), full_fire) == pytest.approx(1.5, abs=0.05)
    assert dmg(a, d, 1) == full_normal


def test_huge_power_doubles_physical(poke):
    """Huge Power doubles Attack"""
    a = poke("Rattata", 100, "Run Away", ["Tackle"])
    d = poke("Rattata", 100, "Run Away", ["Tackle"])
    base = dmg(a, d)
    huge = poke("Rattata", 100, "Huge Power", ["Tackle"])
    assert ratio(dmg(huge, d), base) == pytest.approx(2.0, abs=0.1)


def test_confusion_self_hit_damage(poke):
    """Confusion hit is a typeless 40 BP physical hit on yourself"""
    p = poke("Rattata", 50, "Run Away", ["Tackle"])
    for _ in range(50):
        assert 1 <= calculate_damage_confusion(p) < p[Pok.MAX_HP]
