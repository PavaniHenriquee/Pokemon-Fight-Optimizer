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
    is_grounded, ohko_fails, move_accuracy,
)
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
    Status, Weather, VolStatus, VolStatus2, Potions, MoveOutcome, Types, SideCondition,
)
from DataBase.ItemDB import ItemNames
from battle_driver import move_slice


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
