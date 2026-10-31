"""Damage formula, stat stages and modifiers (roll fixed at 100 unless stated)"""
import random
import pytest
from Engine.damage_calc import (
    apply_stat_stage, calculate_damage, calculate_damage_confusion, flail,
    weight_power, magnitude_power, variable_power, base_power_ability, charge_power,
    sport_power, matchup_types, calculate_ai_logic_damage, item_power, item_attack, raw_atk_def,
    technician_power, rivalry_power, filter_damage, crit_multiplier, MULTIPLIERS,
)
from Engine.engine_helper import struggle
from Utils.helper import get_type_effectiveness, stage_to_multiplier
from Models.idx_const import Pok, Move
from Models.move import STRUGGLE
from Models.helper import (
    Types, Status, Weather, VolStatus, VolStatus2, SideCondition, MoveCategory, Gender,
)
from DataBase.MoveDB import MoveName
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


# ── Variable power ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("weight, power", [
    (1, 20), (100, 20), (101, 40), (250, 40), (251, 60), (500, 60), (501, 80),
    (1000, 80), (1001, 100), (2000, 100), (2001, 120),
])
def test_low_kick_weight_table_is_inclusive(poke, weight, power):
    """pokeplatinum sWeightToPower: hectograms, each limit belongs to the lower band"""
    a = poke("Machop", 20, "Guts", ["Low Kick"])
    d = poke("Geodude", 20, "Sturdy", ["Tackle"])
    d[Pok.WEIGHT] = weight
    assert weight_power(d) == power
    assert variable_power(a, d, move_slice(a, 0)) == power


@pytest.mark.parametrize("roll, power", [
    (0, 10), (4, 10), (5, 30), (14, 30), (15, 50), (34, 50), (35, 70), (64, 70),
    (65, 90), (84, 90), (85, 110), (94, 110), (95, 150), (99, 150),
])
def test_magnitude_table(monkeypatch, roll, power):
    """pokeplatinum CalcMagnitudePower on a 0..99 roll"""
    monkeypatch.setattr(random, "randint", lambda lo, hi: roll)
    assert magnitude_power() == power


@pytest.mark.parametrize("count, power", [(0, 40), (1, 40), (2, 80), (3, 160), (4, 320), (5, 640)])
def test_fury_cutter_doubles_without_cap(poke, count, power):
    """Gen IV counter up to 5 on MoveDB's 40 base power, no 160 cap"""
    a = poke("Anorith", 20, "Battle Armor", ["Fury Cutter"])
    d = poke("Geodude", 20, "Sturdy", ["Tackle"])
    a[Pok.CONSEC_COUNT] = count
    assert variable_power(a, d, move_slice(a, 0)) == power


@pytest.mark.parametrize("move", ["Rollout", "Ice Ball"])
@pytest.mark.parametrize("count, power", [(1, 30), (2, 60), (3, 120), (4, 240), (5, 480)])
def test_rollout_power_and_defense_curl(poke, move, count, power):
    """30 * 2^(use - 1), doubled again after Defense Curl"""
    a = poke("Geodude", 20, "Sturdy", [move])
    d = poke("Geodude", 20, "Sturdy", ["Tackle"])
    a[Pok.CONSEC_COUNT] = count
    assert variable_power(a, d, move_slice(a, 0)) == power
    a[Pok.VOL_STATUS] = VolStatus.DEFENSE_CURL
    assert variable_power(a, d, move_slice(a, 0)) == power * 2


def test_assurance_doubles_on_hurt_target(poke):
    """Assurance doubles if the target already lost HP this turn"""
    a = poke("Murkrow", 20, "Insomnia", ["Assurance"])
    d = poke("Rattata", 20, "Run Away", ["Tackle"])
    assert variable_power(a, d, move_slice(a, 0)) == 60
    d[Pok.VOL_STATUS] = VolStatus.HURT_THIS_TURN
    assert variable_power(a, d, move_slice(a, 0)) == 120


def test_gust_doubles_on_airborne_target(poke):
    """Gust hits a Bouncing target for double power (effect script 0149)"""
    a = poke("Pidgey", 20, "Keen Eye", ["Gust"])
    d = poke("Rattata", 20, "Run Away", ["Tackle"])
    assert variable_power(a, d, move_slice(a, 0)) == 40
    d[Pok.VOL_STATUS] = VolStatus.SEMI_INVULNERABLE
    d[Pok.SEMI_INV_MOVE] = MoveName.BOUNCE
    assert variable_power(a, d, move_slice(a, 0)) == 80


@pytest.mark.parametrize("user_speed, target_speed, target_status, power", [
    (20, 100, 0, 126),                  # 1 + 25 * 100 // 20
    (10, 100, 0, 150),                  # 251 capped at 150
    (100, 20, 0, 6),                    # faster user, low power
    (100, 3, 0, 1),                     # 25 * 3 // 100 = 0
    (20, 100, Status.PARALYSIS, 32),    # target speed 100 // 4 = 25
    (0, 100, 0, 1),                     # no user speed: no division
])
def test_gyro_ball_power(poke, user_speed, target_speed, target_status, power):
    """pokeplatinum TrainerAI_CalcDamage / Showdown: 1 + 25 * target speed / user speed, max 150,
    with the effective speeds"""
    a = poke("Bronzor", 20, "Levitate", ["Gyro Ball"])
    d = poke("Rattata", 20, "Run Away", ["Tackle"])
    a[Pok.SPEED] = user_speed
    d[Pok.SPEED] = target_speed
    d[Pok.STATUS] = target_status
    assert variable_power(a, d, move_slice(a, 0)) == power


def test_gyro_ball_uses_weather_speed(poke):
    """Swift Swim in rain doubles the target's speed for Gyro Ball too"""
    a = poke("Bronzor", 20, "Levitate", ["Gyro Ball"])
    d = poke("Magikarp", 20, "Swift Swim", ["Tackle"])
    a[Pok.SPEED] = 20
    d[Pok.SPEED] = 40
    assert variable_power(a, d, move_slice(a, 0)) == 51
    assert variable_power(a, d, move_slice(a, 0), Weather.RAIN) == 101


def test_reckless_matches_gen4_rounding(poke):
    """Gen IV Reckless is power * 12 // 10 (effect script 0048), Take Down 90 -> 108"""
    a = poke("Starly", 20, "Reckless", ["Take Down"])
    d = poke("Bidoof", 20, "Simple", ["Tackle"])
    mv = move_slice(a, 0)
    assert base_power_ability(a, d, mv, 90) == 108
    assert all(base_power_ability(a, d, mv, p) == p * 12 // 10 for p in range(1, 1024))


# ── Phase 3: Charge, Mud Sport, Water Sport, Foresight, Ingrain ──────────────

@pytest.mark.parametrize("move, doubled", [("Thunder Shock", True), ("Tackle", False)])
def test_charge_doubles_electric_power(poke, move, doubled):
    """Charge doubles the base power of an Electric move only"""
    a = poke("Pikachu", 20, "Static", [move])
    mv = move_slice(a, 0)
    a[Pok.VOL_STATUS] = VolStatus.CHARGE
    assert charge_power(a, mv, 40) == (80 if doubled else 40)


@pytest.mark.parametrize("vol, move, halved", [
    (VolStatus.MUD_SPORT, "Thunder Shock", True), (VolStatus.MUD_SPORT, "Ember", False),
    (VolStatus.WATER_SPORT, "Ember", True), (VolStatus.WATER_SPORT, "Thunder Shock", False),
])
@pytest.mark.parametrize("on_attacker", [True, False])
def test_sports_halve_power_from_either_side(poke, vol, move, halved, on_attacker):
    """Mud Sport / Water Sport halve Electric / Fire power whoever has them"""
    a = poke("Pikachu", 20, "Static", [move])
    d = poke("Rattata", 20, "Run Away", ["Tackle"])
    (a if on_attacker else d)[Pok.VOL_STATUS] = vol
    assert sport_power(a, d, move_slice(a, 0), 41) == (20 if halved else 41)


def test_charge_and_mud_sport_in_damage(poke):
    """Both modifiers reach the full damage formula"""
    a = poke("Pikachu", 30, "Static", ["Thunder Shock"])
    d = poke("Rattata", 30, "Run Away", ["Tackle"])
    base = dmg(a, d)
    a[Pok.VOL_STATUS] = VolStatus.CHARGE
    charged = dmg(a, d)
    a[Pok.VOL_STATUS] = VolStatus.MUD_SPORT
    muddy = dmg(a, d)
    assert charged > base > muddy


def test_matchup_types(poke):
    """Foresight drops Ghost vs Normal/Fighting, Ingrain drops Flying vs Ground"""
    gastly = poke("Gastly", 20, "Levitate", ["Lick"])
    gastly[Pok.VOL_STATUS] = VolStatus.FORESIGHT
    assert matchup_types(Types.NORMAL, gastly) == (0, Types.POISON)
    assert matchup_types(Types.FIRE, gastly) == (Types.GHOST, Types.POISON)
    pidgey = poke("Pidgey", 20, "Keen Eye", ["Tackle"])
    pidgey[Pok.VOL_STATUS] = VolStatus.INGRAIN
    assert matchup_types(Types.GROUND, pidgey) == (Types.NORMAL, 0)


def test_foresight_normal_damages_ghost_neutrally(poke):
    """Tackle on an identified Gastly deals what it would to a Poison type"""
    a = poke("Rattata", 30, "Run Away", ["Tackle"])
    d = poke("Gastly", 30, "Levitate", ["Lick"])
    assert dmg(a, d) == 0
    d[Pok.VOL_STATUS] = VolStatus.FORESIGHT
    assert dmg(a, d) > 0


# ── Phase 5 screens ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("slot, screen, halved", [
    (0, SideCondition.REFLECT, True),        # Tackle
    (0, SideCondition.LIGHT_SCREEN, False),
    (1, SideCondition.LIGHT_SCREEN, True),   # Ember
    (1, SideCondition.REFLECT, False),
    (2, SideCondition.REFLECT, False),       # Brick Break goes through
])
def test_screens_halve_their_category(poke, slot, screen, halved):
    """Reflect halves physical, Light Screen special damage, Brick Break ignores them"""
    a = poke("Charmander", 50, "Blaze", ["Tackle", "Ember", "Brick Break"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    mv = move_slice(a, slot)
    base = calculate_damage(a, d, mv, 0, False, 100)
    screened = calculate_damage(a, d, mv, 0, False, 100, screen)
    if halved:
        assert 0.4 < ratio(screened, base) < 0.6
    else:
        assert screened == base


def test_crit_goes_through_reflect(poke):
    """A critical hit ignores the screen"""
    a = poke("Charmander", 50, "Blaze", ["Tackle"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    mv = move_slice(a, 0)
    assert (calculate_damage(a, d, mv, 0, True, 100, SideCondition.REFLECT)
            == calculate_damage(a, d, mv, 0, True, 100))


def test_ai_damage_sees_screens(poke):
    """pokeplatinum TrainerAI_CalcDamage passes the defender's side conditions"""
    a = poke("Charmander", 50, "Blaze", ["Tackle"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    mv = move_slice(a, 0)
    base = calculate_ai_logic_damage(1.0, a, d, mv, 0)
    assert 0.4 < ratio(calculate_ai_logic_damage(1.0, a, d, mv, 0, SideCondition.REFLECT), base) < 0.6


# ── Dig, Gravity, Minimize ───────────────────────────────────────────────────

def test_gust_does_not_double_on_underground_target(poke):
    """Gust only doubles against a Pokemon in the air, not one using Dig"""
    a = poke("Pidgey", 20, "Keen Eye", ["Gust"])
    d = poke("Rattata", 20, "Run Away", ["Tackle"])
    d[Pok.VOL_STATUS] = VolStatus.SEMI_INVULNERABLE
    d[Pok.SEMI_INV_MOVE] = MoveName.DIG
    assert variable_power(a, d, move_slice(a, 0)) == 40


@pytest.mark.parametrize("semi_move, doubled", [
    (0, False), (MoveName.DIG, True), (MoveName.BOUNCE, False),
])
def test_earthquake_and_magnitude_double_on_dig(poke, semi_move, doubled):
    """Earthquake and Magnitude double their power against a Pokemon underground"""
    a = poke("Geodude", 20, "Sturdy", ["Earthquake", "Magnitude"])
    d = poke("Rattata", 20, "Run Away", ["Tackle"])
    d[Pok.SEMI_INV_MOVE] = semi_move
    mult = 2 if doubled else 1
    assert variable_power(a, d, move_slice(a, 0)) == 100 * mult
    random.seed(3)
    base = magnitude_power()
    random.seed(3)
    assert variable_power(a, d, move_slice(a, 1)) == base * mult


def test_stomp_doubles_on_minimized_target(poke):
    """Gen IV Stomp doubles its power against a minimized target"""
    a = poke("Rattata", 20, "Run Away", ["Stomp"])
    d = poke("Rattata", 20, "Run Away", ["Tackle"])
    assert variable_power(a, d, move_slice(a, 0)) == 65
    d[Pok.VOL_STATUS2] = VolStatus2.MINIMIZE
    assert variable_power(a, d, move_slice(a, 0)) == 130


def test_gravity_drops_flying_type_against_ground(poke):
    """Under Gravity Ground moves treat the Flying type as neutral, other types aren't touched"""
    d = poke("Pidgey", 20, "Keen Eye", ["Tackle"])
    assert matchup_types(Types.GROUND, d) == (Types.NORMAL, Types.FLYING)
    assert matchup_types(Types.GROUND, d, True) == (Types.NORMAL, 0)
    assert matchup_types(Types.ROCK, d, True) == (Types.NORMAL, Types.FLYING)
    a = poke("Geodude", 20, "Sturdy", ["Earthquake"])
    assert calculate_damage(a, d, move_slice(a, 0), 0, False, 100) == 0
    assert calculate_damage(a, d, move_slice(a, 0), 0, False, 100, 0, True) > 0



# ── Base formula rounding ────────────────────────────────────────────────────

def test_level_factor_is_floored(poke):
    """pokeplatinum CalcMoveDamage is integer math: level 12 gives 2*12/5 + 2 = 6, not 6.8"""
    a = poke("Machop", 12, "Guts", ["Tackle"])
    d = poke("Machop", 12, "Guts", ["Tackle"])
    a[Pok.ATTACK], d[Pok.DEFENSE] = 100, 50
    # 100 * 40 * 6 // 50 // 50 = 9, +2; the unfloored 6.8 would give 10
    assert dmg(a, d) == 11


def test_ai_damage_burn_spares_guts(poke):
    """The AI estimate uses the same burn rule as the battle: Guts isn't halved"""
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    guts = poke("Machop", 50, "Guts", ["Karate Chop"])
    mv = move_slice(guts, 0)
    plain = calculate_ai_logic_damage(2.0, guts, d, mv, 0)
    guts[Pok.STATUS] = Status.BURN
    assert ratio(calculate_ai_logic_damage(2.0, guts, d, mv, 0), plain) == pytest.approx(1.5, abs=0.05)


# ── Damage items ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("item, move_type, category, power", [
    ("Muscle Band", Types.NORMAL, MoveCategory.PHYSICAL, 110),
    ("Muscle Band", Types.NORMAL, MoveCategory.SPECIAL, 100),
    ("Charcoal", Types.FIRE, MoveCategory.SPECIAL, 120),
    ("Charcoal", Types.WATER, MoveCategory.SPECIAL, 100),
    ("Silk Scarf", Types.NORMAL, MoveCategory.PHYSICAL, 120),
    ("Expert Belt", Types.NORMAL, MoveCategory.PHYSICAL, 100),
])
def test_item_power(poke, item, move_type, category, power):
    """Type items x(100+20)/100 on their type, Muscle Band x(100+10)/100 on physical moves"""
    a = poke("Rattata", 50, "Run Away", ["Tackle"], item=item)
    assert item_power(a, move_type, category, 100) == power


@pytest.mark.parametrize("species, power", [("Pikachu", 80), ("Rattata", 40)])
def test_light_ball_doubles_pikachu_power(poke, species, power):
    """Light Ball doubles the power of Pikachu's moves, physical and special"""
    a = poke(species, 50, "Static", ["Tackle"], item="Light Ball")
    assert item_power(a, Types.ELECTRIC, MoveCategory.SPECIAL, 40) == power
    assert item_power(a, Types.NORMAL, MoveCategory.PHYSICAL, 40) == power


@pytest.mark.parametrize("species, doubled", [("Cubone", True), ("Marowak", True), ("Rattata", False)])
def test_thick_club(poke, species, doubled):
    """Thick Club doubles Cubone's and Marowak's physical Attack only"""
    a = poke(species, 50, "Rock Head", ["Tackle", "Ember"], item="Thick Club")
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    assert item_attack(a, 101) == (202 if doubled else 101)
    assert raw_atk_def(move_slice(a, 1), a, d)[0] == a[Pok.SPECIAL_ATTACK]


def test_thick_club_before_guts(poke):
    """pokeplatinum doubles the Attack before Guts' x1.5, which keeps the odd point"""
    a = poke("Marowak", 50, "Guts", ["Tackle"], item="Thick Club")
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    a[Pok.ATTACK] = 101
    a[Pok.STATUS] = Status.POISON
    assert raw_atk_def(move_slice(a, 0), a, d)[0] == 303


@pytest.mark.parametrize("defender, boosted", [("Bulbasaur", True), ("Rattata", False)])
def test_expert_belt_super_effective_only(poke, defender, boosted):
    """Expert Belt x(100+20)/100 on the final super effective damage"""
    plain = poke("Charmander", 50, "Blaze", ["Ember"])
    belt = poke("Charmander", 50, "Blaze", ["Ember"], item="Expert Belt")
    d = poke(defender, 50, "Overgrow", ["Tackle"])
    base = dmg(plain, d)
    assert dmg(belt, d) == (base * 120 // 100 if boosted else base)


def test_items_reach_damage_and_ai_estimate(poke):
    """The battle damage and the AI's estimate both see power items and Expert Belt"""
    d = poke("Bulbasaur", 50, "Overgrow", ["Tackle"])
    for item in ("Charcoal", "Expert Belt"):
        plain = poke("Charmander", 50, "Blaze", ["Ember"])
        held = poke("Charmander", 50, "Blaze", ["Ember"], item=item)
        assert dmg(held, d) > dmg(plain, d)
        assert (
            calculate_ai_logic_damage(4.0, held, d, move_slice(held, 0), 0)
            > calculate_ai_logic_damage(4.0, plain, d, move_slice(plain, 0), 0)
        )


@pytest.mark.parametrize("item, boosted", [
    ("Silk Scarf", True), ("Muscle Band", False), ("Charcoal", False),
])
def test_confusion_self_hit_items(poke, item, boosted):
    """The confusion hit counts as a Normal move: Silk Scarf boosts it, Muscle Band doesn't"""
    plain = poke("Rattata", 100, "Run Away", ["Tackle"])
    held = poke("Rattata", 100, "Run Away", ["Tackle"], item=item)
    random.seed(3)
    base = calculate_damage_confusion(plain)
    random.seed(3)
    assert (calculate_damage_confusion(held) > base) == boosted


def test_confusion_self_hit_thick_club(poke):
    """Thick Club doubles the Attack of the confusion hit too"""
    plain = poke("Marowak", 100, "Rock Head", ["Tackle"])
    held = poke("Marowak", 100, "Rock Head", ["Tackle"], item="Thick Club")
    random.seed(3)
    base = calculate_damage_confusion(plain)
    random.seed(3)
    assert ratio(calculate_damage_confusion(held), base) == pytest.approx(2.0, abs=0.1)


@pytest.mark.parametrize("item, boosted", [("Muscle Band", True), ("Silk Scarf", False)])
def test_struggle_items(poke, item, boosted):
    """Struggle is typeless: Muscle Band boosts it, a type item doesn't"""
    d = poke("Rattata", 100, "Run Away", ["Tackle"])
    plain = poke("Rattata", 100, "Run Away", ["Tackle"])
    held = poke("Rattata", 100, "Run Away", ["Tackle"], item=item)
    random.seed(5)
    base = struggle(plain, d, False)
    random.seed(5)
    assert (struggle(held, d, False) > base) == boosted


# ── Damage abilities ─────────────────────────────────────────────────────────

def with_power(pok, slot, power):
    """Copy of pok whose move `slot` has this base power"""
    c = pok.copy()
    move_slice(c, slot)[Move.POWER] = power
    return c


def test_adaptability_doubles_stab(poke):
    """Adaptability makes STAB x2 instead of x1.5 (pokeplatinum BattleSystem_ApplyTypeChart)"""
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    no_stab = poke("Rattata", 50, "Run Away", ["Tackle"])
    no_stab[Pok.TYPE1] = no_stab[Pok.TYPE2] = Types.FIRE
    base = dmg(no_stab, d)
    assert dmg(poke("Rattata", 50, "Run Away", ["Tackle"]), d) == base * 3 // 2
    assert dmg(poke("Rattata", 50, "Adaptability", ["Tackle"]), d) == base * 2


@pytest.mark.parametrize("power, boosted", [(60, 90), (61, 61), (15, 22), (1, 1)])
def test_technician_boosts_power_60_or_less(poke, power, boosted):
    """Technician: power <= 60 gets x15/10"""
    a = poke("Scyther", 20, "Technician", ["Fury Attack"])
    assert technician_power(a, move_slice(a, 0), power) == boosted
    plain = poke("Scyther", 20, "Swarm", ["Fury Attack"])
    assert technician_power(plain, move_slice(plain, 0), power) == power


def test_technician_skips_struggle(poke):
    """pokeplatinum leaves Struggle out of Technician"""
    a = poke("Scyther", 20, "Technician", ["Fury Attack"])
    assert technician_power(a, STRUGGLE, 50) == 50


def test_technician_runs_before_type_items(poke):
    """Fury Attack 15: Technician 22, then Silk Scarf 26 (items first would be 18, then 27)"""
    d = poke("Rattata", 100, "Run Away", ["Tackle"])
    a = poke("Scyther", 100, "Technician", ["Fury Attack"], item="Silk Scarf")
    plain = poke("Scyther", 100, "Swarm", ["Fury Attack"])
    assert dmg(a, d) == dmg(with_power(plain, 0, 26), d)
    assert dmg(a, d) != dmg(with_power(plain, 0, 27), d)


def test_swarm_boosts_bug_moves_in_a_pinch(poke):
    """Swarm: Bug moves x15/10 at 1/3 HP or less, like Blaze"""
    a = poke("Beedrill", 30, "Swarm", ["Twineedle", "Fury Attack"])
    d = poke("Rattata", 30, "Run Away", ["Tackle"])
    bug, normal = move_slice(a, 0), move_slice(a, 1)
    assert base_power_ability(a, d, bug, 25) == 25
    a[Pok.CURRENT_HP] = a[Pok.MAX_HP] // 3
    assert base_power_ability(a, d, bug, 25) == 37
    assert base_power_ability(a, d, normal, 15) == 15


@pytest.mark.parametrize("atk_gender, def_gender, power", [
    (Gender.MALE, Gender.MALE, 100), (Gender.FEMALE, Gender.FEMALE, 100),
    (Gender.MALE, Gender.FEMALE, 60), (Gender.MALE, Gender.GENDERLESS, 80),
    (Gender.GENDERLESS, Gender.MALE, 80),
])
def test_rivalry_by_gender(poke, atk_gender, def_gender, power):
    """Rivalry: same gender x125/100, opposite x75/100, nothing if either is genderless"""
    a = poke("Shinx", 20, "Rivalry", ["Tackle"])
    d = poke("Shinx", 20, "Rivalry", ["Tackle"])
    a[Pok.GENDER] = atk_gender
    d[Pok.GENDER] = def_gender
    assert rivalry_power(a, d, 80) == power
    assert base_power_ability(a, d, move_slice(a, 0), 80) == power


def test_thick_fat_is_the_defenders(poke):
    """Issue 1: the defender's Thick Fat halves Fire and Ice power, Mold Breaker ignores it, and
    the holder's own Fire moves aren't halved any more"""
    a = poke("Charmander", 30, "Blaze", ["Ember", "Scratch"])
    fat = poke("Snorlax", 30, "Thick Fat", ["Powder Snow"])
    assert base_power_ability(a, fat, move_slice(a, 0), 40) == 20
    assert base_power_ability(a, fat, move_slice(a, 1), 40) == 40
    assert base_power_ability(fat, a, move_slice(fat, 0), 40) == 40
    breaker = poke("Charmander", 30, "Mold Breaker", ["Ember"])
    assert base_power_ability(breaker, fat, move_slice(breaker, 0), 40) == 40
    d = poke("Rattata", 30, "Run Away", ["Tackle"])
    fat_attacker = poke("Charmander", 30, "Thick Fat", ["Ember"])
    assert dmg(fat_attacker, d) == dmg(poke("Charmander", 30, "Run Away", ["Ember"]), d)


@pytest.mark.parametrize("ability, power", [("Heatproof", 20), ("Dry Skin", 50)])
def test_heatproof_and_dry_skin_change_fire_power(poke, ability, power):
    """Defender's Heatproof halves Fire power, Dry Skin x125/100; Mold Breaker ignores both"""
    a = poke("Charmander", 30, "Blaze", ["Ember", "Scratch"])
    d = poke("Bronzor", 30, ability, ["Tackle"])
    assert base_power_ability(a, d, move_slice(a, 0), 40) == power
    assert base_power_ability(a, d, move_slice(a, 1), 40) == 40
    breaker = poke("Charmander", 30, "Mold Breaker", ["Ember"])
    assert base_power_ability(breaker, d, move_slice(breaker, 0), 40) == 40


@pytest.mark.parametrize("ability, power", [
    ("Thick Fat", 55), ("Heatproof", 56), ("Dry Skin", 140), ("Run Away", 112),
])
def test_blaze_order_against_defender_abilities(poke, ability, power):
    """Fire Punch 75 under Blaze, pokeplatinum order: Thick Fat halves before Blaze (37, then 55),
    Heatproof and Dry Skin come after it (112, then 56 or 140)"""
    a = poke("Chimchar", 30, "Blaze", ["Fire Punch"])
    a[Pok.CURRENT_HP] = a[Pok.MAX_HP] // 3
    d = poke("Bronzor", 30, ability, ["Tackle"])
    assert base_power_ability(a, d, move_slice(a, 0), 75) == power


def test_sport_runs_before_pinch_abilities(poke):
    """Issue 15: Water Sport halves before Blaze, Fire Punch 75 is 37, then 55 (not 112, then 56)"""
    a = poke("Chimchar", 30, "Blaze", ["Fire Punch"])
    a[Pok.CURRENT_HP] = a[Pok.MAX_HP] // 3
    d = poke("Rattata", 30, "Run Away", ["Tackle"])
    d[Pok.VOL_STATUS] = VolStatus.WATER_SPORT
    assert base_power_ability(a, d, move_slice(a, 0), 75) == 55


@pytest.mark.parametrize("ability", ["Filter", "Solid Rock"])
def test_filter_and_solid_rock_cut_super_effective_hits(poke, ability):
    """x3/4 on a super effective hit, at least 1; Mold Breaker ignores them"""
    a = poke("Geodude", 30, "Sturdy", ["Rock Throw"])
    d = poke("Starly", 30, ability, ["Tackle"])
    assert filter_damage(a, d, 4, 2, 100) == 75
    assert filter_damage(a, d, 4, 4, 100) == 75
    assert filter_damage(a, d, 4, 2, 1) == 1
    assert filter_damage(a, d, 2, 2, 100) == 100
    assert filter_damage(a, d, 4, 1, 100) == 100
    breaker = poke("Cranidos", 30, "Mold Breaker", ["Rock Throw"])
    assert filter_damage(breaker, d, 4, 2, 100) == 100


def test_filter_runs_before_expert_belt(poke):
    """pokeplatinum BattleSystem_ApplyTypeChart: Filter's 3/4, then Expert Belt's x120/100"""
    plain = poke("Geodude", 50, "Sturdy", ["Rock Throw"])
    belt = poke("Geodude", 50, "Sturdy", ["Rock Throw"], item="Expert Belt")
    d = poke("Starly", 50, "Keen Eye", ["Tackle"])
    filt = poke("Starly", 50, "Filter", ["Tackle"])
    assert dmg(belt, filt) == dmg(plain, d) * 3 // 4 * 120 // 100


def test_sniper_triples_crits(poke):
    """Sniper makes the crit multiplier 3 (pokeplatinum BattleSystem_CalcCriticalMulti)"""
    plain = poke("Rattata", 100, "Run Away", ["Tackle"])
    sniper = poke("Rattata", 100, "Sniper", ["Tackle"])
    d = poke("Rattata", 100, "Run Away", ["Tackle"])
    assert (crit_multiplier(plain), crit_multiplier(sniper)) == (2, 3)
    assert dmg(sniper, d) == dmg(plain, d)
    assert ratio(dmg(sniper, d, crit=True), dmg(plain, d, crit=True)) == pytest.approx(1.5, abs=0.02)


def test_unaware_ignores_the_foes_stages(poke):
    """Defending, Unaware ignores the attacker's Attack stage; attacking, the defender's Defense
    stage. Its own stages still count, and Mold Breaker ignores the defending side"""
    a = poke("Bidoof", 30, "Run Away", ["Tackle"])
    d = poke("Bidoof", 30, "Run Away", ["Tackle"])
    mv = move_slice(a, 0)
    base = raw_atk_def(mv, a, d)
    a[Pok.ATTACK_STAT_STAGE] = 2
    d[Pok.DEFENSE_STAT_STAGE] = 2
    boosted = raw_atk_def(mv, a, d)
    unaware_def = poke("Bidoof", 30, "Unaware", ["Tackle"])
    unaware_def[Pok.DEFENSE_STAT_STAGE] = 2
    assert raw_atk_def(mv, a, unaware_def) == (base[0], boosted[1])
    unaware_atk = poke("Bidoof", 30, "Unaware", ["Tackle"])
    unaware_atk[Pok.ATTACK_STAT_STAGE] = 2
    assert raw_atk_def(move_slice(unaware_atk, 0), unaware_atk, d) == (boosted[0], base[1])
    breaker = poke("Bidoof", 30, "Mold Breaker", ["Tackle"])
    breaker[Pok.ATTACK_STAT_STAGE] = 2
    assert raw_atk_def(move_slice(breaker, 0), breaker, unaware_def) == boosted


def test_marvel_scale_raises_defense_while_statused(poke):
    """Marvel Scale: Defense x15/10 with a status, Sp. Def untouched, Mold Breaker ignores it"""
    a = poke("Rattata", 30, "Run Away", ["Tackle", "Ember"])
    d = poke("Rattata", 30, "Marvel Scale", ["Tackle"])
    tackle, ember = move_slice(a, 0), move_slice(a, 1)
    assert raw_atk_def(tackle, a, d)[1] == d[Pok.DEFENSE]
    d[Pok.STATUS] = Status.BURN
    assert raw_atk_def(tackle, a, d)[1] == d[Pok.DEFENSE] * 15 // 10
    assert raw_atk_def(ember, a, d)[1] == d[Pok.SPECIAL_DEFENSE]
    breaker = poke("Rattata", 30, "Mold Breaker", ["Tackle"])
    assert raw_atk_def(move_slice(breaker, 0), breaker, d)[1] == d[Pok.DEFENSE]


def test_flower_gift_in_sun(poke):
    """In sun, Flower Gift raises the holder's Attack and its Sp. Def against special moves;
    Mold Breaker ignores the Sp. Def part"""
    fg = poke("Cherrim", 30, "Flower Gift", ["Tackle", "Ember"])
    d = poke("Rattata", 30, "Run Away", ["Tackle", "Ember"])
    assert raw_atk_def(move_slice(fg, 0), fg, d)[0] == fg[Pok.ATTACK]
    assert raw_atk_def(move_slice(fg, 0), fg, d, Weather.SUN)[0] == fg[Pok.ATTACK] * 15 // 10
    assert raw_atk_def(move_slice(fg, 1), fg, d, Weather.SUN)[0] == fg[Pok.SPECIAL_ATTACK]
    assert raw_atk_def(move_slice(d, 1), d, fg, Weather.SUN)[1] == fg[Pok.SPECIAL_DEFENSE] * 15 // 10
    assert raw_atk_def(move_slice(d, 0), d, fg, Weather.SUN)[1] == fg[Pok.DEFENSE]
    breaker = poke("Rattata", 30, "Mold Breaker", ["Ember"])
    assert raw_atk_def(move_slice(breaker, 0), breaker, fg, Weather.SUN)[1] == fg[Pok.SPECIAL_DEFENSE]


def test_pure_power_doubles_physical(poke):
    """Pure Power is Huge Power"""
    d = poke("Rattata", 100, "Run Away", ["Tackle"])
    assert dmg(poke("Meditite", 100, "Pure Power", ["Tackle"]), d) == \
        dmg(poke("Meditite", 100, "Huge Power", ["Tackle"]), d)


@pytest.mark.parametrize("ability, gender, mult", [
    ("Pure Power", Gender.MALE, 2.0), ("Rivalry", Gender.MALE, 1.25),
    ("Rivalry", Gender.GENDERLESS, 1.0),
])
def test_confusion_self_hit_pure_power_and_rivalry(poke, ability, gender, mult):
    """The confusion hit gets Pure Power, and Rivalry's same-gender boost when gendered"""
    plain = poke("Rattata", 100, "Run Away", ["Tackle"])
    held = poke("Rattata", 100, ability, ["Tackle"])
    plain[Pok.GENDER] = held[Pok.GENDER] = gender
    random.seed(3)
    base = calculate_damage_confusion(plain)
    random.seed(3)
    assert ratio(calculate_damage_confusion(held), base) == pytest.approx(mult, abs=0.05)


@pytest.mark.parametrize("atk_ab, def_ab, def_status, lower", [
    ("Rivalry", "Run Away", 0, False),
    ("Run Away", "Marvel Scale", Status.BURN, True),
    ("Run Away", "Unaware", 0, True),
])
def test_struggle_damage_abilities(poke, atk_ab, def_ab, def_status, lower):
    """Struggle goes through the same stat and power abilities (the attacker is at +2 Attack)"""
    d = poke("Rattata", 100, def_ab, ["Tackle"])
    d[Pok.STATUS] = def_status
    plain_d = poke("Rattata", 100, "Run Away", ["Tackle"])
    a = poke("Rattata", 100, atk_ab, ["Tackle"])
    plain_a = poke("Rattata", 100, "Run Away", ["Tackle"])
    a[Pok.ATTACK_STAT_STAGE] = plain_a[Pok.ATTACK_STAT_STAGE] = 2
    random.seed(5)
    base = struggle(plain_a, plain_d, False)
    random.seed(5)
    got = struggle(a, d, False)
    assert (got < base) if lower else (got > base)


def test_damage_abilities_reach_ai_estimate(poke):
    """pokeplatinum TrainerAI_CalcDamage runs BattleSystem_CalcMoveDamage and the type chart, so
    the AI's estimate sees the same abilities on both sides"""
    def est(atk, dfn):
        return calculate_ai_logic_damage(4.0, atk, dfn, move_slice(atk, 0), 0)

    tech, scyther = (poke("Scyther", 30, ab, ["Fury Attack"]) for ab in ("Technician", "Swarm"))
    rattata = poke("Rattata", 30, "Run Away", ["Tackle"])
    assert est(tech, rattata) > est(scyther, rattata)

    ember = poke("Charmander", 30, "Blaze", ["Ember"])
    assert est(ember, poke("Snorlax", 30, "Thick Fat", ["Tackle"])) < \
        est(ember, poke("Snorlax", 30, "Run Away", ["Tackle"]))

    rock = poke("Geodude", 30, "Sturdy", ["Rock Throw"])
    assert est(rock, poke("Starly", 30, "Filter", ["Tackle"])) < \
        est(rock, poke("Starly", 30, "Keen Eye", ["Tackle"]))

    boosted = poke("Rattata", 30, "Run Away", ["Tackle"])
    boosted[Pok.ATTACK_STAT_STAGE] = 2
    assert est(boosted, poke("Bidoof", 30, "Unaware", ["Tackle"])) < \
        est(boosted, poke("Bidoof", 30, "Run Away", ["Tackle"]))

    rival = poke("Shinx", 30, "Rivalry", ["Tackle"])
    assert est(rival, rattata) > est(poke("Shinx", 30, "Run Away", ["Tackle"]), rattata)


# ── Damage ranges vs a real calculator ───────────────────────────────────────
# Fill `rolls` with the calculator's 16 values (85% to 100% roll, low to high); an empty list skips
# the case. Every Pokemon: Hardy nature, 31 IVs, 0 EVs, Male. The comment under each case has the
# engine's stats (RP base stats), so check the calculator uses the same ones.
CALC_CASES = [
    pytest.param(
        dict(atk=("Onix", 14, "Rock Head", "Muscle Band"), move="Rock Throw",
             dfn=("Chimchar", 14, "Blaze")),
        # Onix Atk 30 | Chimchar HP 40, Def 21
        [32, 32, 32, 32, 32, 32, 32, 32, 36, 36, 36, 36, 36, 36, 36, 38],
        id="muscle_band_onix_rock_throw_vs_chimchar"),
    pytest.param(
        dict(atk=("Geodude", 13, "Sturdy", "Expert Belt"), move="Rock Throw",
             dfn=("Starly", 13, "Keen Eye")),
        # Geodude Atk 29 | Starly HP 37, Def 16
        [38, 43, 43, 43, 43, 43, 43, 43, 45, 45, 45, 45, 45, 45, 45, 50],
        id="expert_belt_geodude_rock_throw_vs_starly"),
    pytest.param(
        dict(atk=("Charmander", 12, "Blaze", "Charcoal"), move="Ember",
             dfn=("Bulbasaur", 12, "Overgrow")),
        # Charmander SpA 23 | Bulbasaur HP 36, SpD 24
        [14, 18, 18, 18, 18, 18, 18, 18, 18, 18, 18, 18, 18, 18, 18, 20],
        id="charcoal_charmander_ember_vs_bulbasaur"),
    pytest.param(
        dict(atk=("Machop", 12, "Guts", None), move="Karate Chop",
             dfn=("Bidoof", 12, "Simple"), status=Status.BURN),
        # Machop Atk 27, burned | Bidoof HP 39, Def 18
        [36, 36, 38, 38, 38, 38, 38, 38, 38, 42, 42, 42, 42, 42, 42, 44],
        id="guts_burned_machop_karate_chop_vs_bidoof"),
    pytest.param(
        dict(atk=("Rattata", 11, "Run Away", None), move="Tackle",
             dfn=("Geodude", 11, "Sturdy"), status=Status.BURN),
        # Rattata Atk 20, burned | Geodude HP 33, Def 30
        [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2],
        id="burned_rattata_tackle_vs_geodude"),
    pytest.param(
        dict(atk=("Pikachu", 10, "Static", "Light Ball"), move="Thunder Shock",
             dfn=("Starly", 10, "Keen Eye")),
        # Pikachu SpA 18 | Starly HP 31, SpD 14
        [32, 36, 36, 36, 36, 36, 36, 36, 38, 38, 38, 38, 38, 38, 38, 42],
        id="light_ball_pikachu_thunder_shock_vs_starly"),
    pytest.param(
        dict(atk=("Marowak", 28, "Rock Head", "Thick Club"), move="Bone Club",
             dfn=("Rattata", 28, "Run Away")),
        # Marowak Atk 58 | Rattata HP 63, Def 33
        [76, 78, 79, 79, 81, 81, 82, 84, 84, 85, 85, 87, 88, 88, 90, 91],
        id="thick_club_marowak_bone_club_vs_rattata"),
    pytest.param(
        dict(atk=("Squirtle", 7, "Torrent", None), move="Water Gun",
             dfn=("Geodude", 7, "Sturdy"), weather=Weather.RAIN),
        # Squirtle SpA 14 | Geodude HP 24, SpD 11. Rain
        [36, 36, 36, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 48],
        id="rain_squirtle_water_gun_vs_geodude"),
    pytest.param(
        dict(atk=("Charmander", 12, "Blaze", None), move="Ember",
             dfn=("Bulbasaur", 12, "Overgrow"), weather=Weather.RAIN),
        # Charmander SpA 23 | Bulbasaur HP 36, SpD 24. Rain
        [8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 12],
        id="rain_charmander_ember_vs_bulbasaur"),
    pytest.param(
        dict(atk=("Bidoof", 15, "Simple", None), move="Tackle",
             dfn=("Machop", 15, "Guts"), def_side=SideCondition.REFLECT),
        # Bidoof Atk 23 | Machop HP 50, Def 24. Reflect on Machop's side
        [6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 7],
        id="reflect_bidoof_tackle_vs_machop"),
    pytest.param(
        dict(atk=("Starly", 14, "Keen Eye", None), move="Quick Attack",
             dfn=("Turtwig", 14, "Overgrow"), crit=True),
        # Starly Atk 24 | Turtwig HP 43, Def 27. Critical hit
        [15, 15, 15, 15, 15, 15, 15, 16, 16, 16, 16, 16, 16, 16, 16, 18],
        id="crit_starly_quick_attack_vs_turtwig"),
    pytest.param(
        dict(atk=("Cranidos", 14, "Mold Breaker", None), move="Headbutt",
             dfn=("Piplup", 14, "Torrent"), atk_stage=2, def_stage=1),
        # Cranidos Atk 44 at +2 | Piplup HP 43, Def 24 at +1
        [21, 21, 21, 22, 22, 22, 22, 23, 23, 23, 23, 24, 24, 24, 24, 25],
        id="stages_cranidos_headbutt_vs_piplup"),
    pytest.param(
        dict(atk=("Starly", 14, "Keen Eye", "Silk Scarf"), move="Quick Attack",
             dfn=("Shinx", 14, "Intimidate")),
        # Starly Atk 24 | Shinx HP 40, Def 18
        [12, 12, 12, 12, 12, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 15],
        id="silk_scarf_starly_quick_attack_vs_shinx"),
]


@pytest.mark.parametrize("case, rolls", CALC_CASES)
def test_damage_matches_calculator(poke, case, rolls):
    """All 16 rolls against a real Gen IV calculator, no crit unless the case says so"""
    if not rolls:
        pytest.skip("rolls not filled in yet")
    species, level, ability, item = case["atk"]
    a = poke(species, level, ability, [case["move"]], item=item)
    d = poke(*case["dfn"], ["Tackle"])
    a[Pok.STATUS] = case.get("status", 0)
    a[Pok.ATTACK_STAT_STAGE] = case.get("atk_stage", 0)
    d[Pok.DEFENSE_STAT_STAGE] = case.get("def_stage", 0)
    got = [
        calculate_damage(
            a, d, move_slice(a, 0), case.get("weather", 0), case.get("crit", False), roll,
            case.get("def_side", 0),
        )
        for roll in MULTIPLIERS
    ]
    assert got == rolls



@pytest.mark.parametrize("move, stage, defense", [
    ("Explosion", 0, 25), ("Selfdestruct", 1, 38), ("Tackle", 1, 76), ("Explosion", -1, 17),
])
def test_explosion_halves_defense_after_stages(poke, move, stage, defense):
    """Gen IV Explosion and Selfdestruct halve the Defense after the stages (Showdown gen4):
    51 at +1 is 76, halved 38 (pokeplatinum's raw-first order would give 37)"""
    a = poke("Geodude", 30, "Sturdy", [move])
    d = poke("Rattata", 30, "Run Away", ["Tackle"])
    d[Pok.DEFENSE] = 51
    d[Pok.DEFENSE_STAT_STAGE] = stage
    assert raw_atk_def(move_slice(a, 0), a, d)[1] == defense
