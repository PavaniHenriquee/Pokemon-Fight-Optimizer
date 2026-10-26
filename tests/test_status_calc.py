"""Status, volatile status and stat-change effects"""
import pytest
from Engine.status_calc import (
    apply_status, stat_changes, vol_status, calculate_effects, sec_effects, synchronize_reflect,
)
from Models.idx_const import Pok, Move, Sec
from Models.helper import Status, Weather, VolStatus
from battle_driver import move_slice



@pytest.fixture(name="pair")
def fixture_pair(poke):
    """(attacker with a status-move kit, plain defender)"""
    a = poke("Pikachu", 50, "Static",
             ["Thunder Wave", "Growl", "Harden", "Confuse Ray"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    return a, d


def test_status_applies_once(pair):
    """Thunder Wave paralyzes; a second status can't overwrite"""
    a, d = pair
    apply_status(move_slice(a, 0), d, 0, a)
    assert d[Pok.STATUS] == Status.PARALYSIS
    mv = move_slice(a, 0).copy()
    mv[Move.STATUS] = Status.BURN
    apply_status(mv, d, 0, a)
    assert d[Pok.STATUS] == Status.PARALYSIS


def test_toxic_and_sleep_side_counters(pair):
    """Toxic starts the badly-poison counter; sleep rolls 2-5 turns"""
    a, d = pair
    mv = move_slice(a, 0).copy()
    mv[Move.STATUS] = Status.TOXIC
    apply_status(mv, d, 0, a)
    assert d[Pok.BADLY_POISON] == 1
    mv[Move.STATUS] = Status.SLEEP
    seen = set()
    for _ in range(200):
        d[Pok.STATUS] = 0
        apply_status(mv, d, 0, a)
        assert d[Pok.STATUS] == Status.SLEEP
        seen.add(int(d[Pok.SLEEP_COUNTER]))
    assert seen == {2, 3, 4, 5}


def test_no_freeze_in_sun(pair):
    """Freeze can't be inflicted under sun"""
    a, d = pair
    mv = move_slice(a, 0).copy()
    mv[Move.STATUS] = Status.FREEZE
    apply_status(mv, d, Weather.SUN, a)
    assert d[Pok.STATUS] == 0
    apply_status(mv, d, 0, a)
    assert d[Pok.STATUS] == Status.FREEZE


@pytest.mark.parametrize("inflicted, reflected", [
    (Status.BURN, Status.BURN),
    (Status.PARALYSIS, Status.PARALYSIS),
    (Status.POISON, Status.POISON),
    (Status.TOXIC, Status.POISON),
    (Status.SLEEP, 0),
])
def test_synchronize(poke, inflicted, reflected):
    """Synchronize passes BRN/PAR/PSN back, Toxic comes back as plain poison, never sleep"""
    a = poke("Rattata", 50, "Run Away", ["Tackle"])
    sync = poke("Ralts", 50, "Synchronize", ["Confusion"])
    mv = move_slice(a, 0).copy()
    mv[Move.STATUS] = inflicted
    apply_status(mv, sync, 0, a)
    assert sync[Pok.STATUS] == inflicted
    assert a[Pok.STATUS] == reflected


@pytest.mark.parametrize("name, ability, status", [
    ("Charmander", "Blaze", Status.BURN),
    ("Pikachu", "Static", Status.PARALYSIS),
    ("Geodude", "Sturdy", Status.POISON),     # Geodude isn't Poison/Steel, so it's poisoned
    ("Magnemite", "Sturdy", Status.POISON),   # Steel: immune
    ("Rattata", "Immunity", Status.POISON),
])
def test_synchronize_respects_type_immunities(poke, name, ability, status):
    """Synchronize can't give a status the source is immune to"""
    src = poke(name, 50, ability, ["Tackle"])
    sync = poke("Ralts", 50, "Synchronize", ["Confusion"])
    sync[Pok.STATUS] = status
    synchronize_reflect(sync, status, src)
    immune = (
        (status == Status.BURN and name == "Charmander")
        or (status == Status.PARALYSIS and name == "Pikachu")
        or name == "Magnemite" or ability == "Immunity"
    )
    assert src[Pok.STATUS] == (0 if immune else status)


def test_stat_drop_on_target_and_boost_on_self(pair):
    """Growl lowers the foe's Attack, Harden raises the user's Defense"""
    a, d = pair
    stat_changes(move_slice(a, 1), a, d)
    assert d[Pok.ATTACK_STAT_STAGE] == -1 and a[Pok.ATTACK_STAT_STAGE] == 0
    stat_changes(move_slice(a, 2), a, d)
    assert a[Pok.DEFENSE_STAT_STAGE] == 1 and d[Pok.DEFENSE_STAT_STAGE] == 0


def test_stat_stages_clamp(pair):
    """Stages never leave [-6, 6]"""
    a, d = pair
    for _ in range(10):
        stat_changes(move_slice(a, 1), a, d)
        stat_changes(move_slice(a, 2), a, d)
    assert d[Pok.ATTACK_STAT_STAGE] == -6
    assert a[Pok.DEFENSE_STAT_STAGE] == 6


def test_keen_eye_blocks_accuracy_drop(poke):
    """Sand Attack can't lower a Keen Eye user's accuracy"""
    a = poke("Hippopotas", 50, "Sand Veil", ["Sand Attack"])
    keen = poke("Starly", 50, "Keen Eye", ["Tackle"])
    plain = poke("Rattata", 50, "Run Away", ["Tackle"])
    stat_changes(move_slice(a, 0), a, keen)
    stat_changes(move_slice(a, 0), a, plain)
    assert keen[Pok.ACCURACY_STAT_STAGE] == 0
    assert plain[Pok.ACCURACY_STAT_STAGE] == -1


def test_confusion_volatile(pair):
    """Confuse Ray sets the bit once and a 2-5 counter"""
    a, d = pair
    vol_status(move_slice(a, 3), d, a)
    assert d[Pok.VOL_STATUS] & VolStatus.CONFUSION
    assert 2 <= d[Pok.CONFUSION_COUNTER] <= 5
    before = d[Pok.VOL_STATUS]
    vol_status(move_slice(a, 3), d, a)
    assert d[Pok.VOL_STATUS] == before


def test_ghost_curse_costs_half_hp(poke):
    """Ghost Curse: target gets cursed, user pays 1/2 max HP"""
    g = poke("Gastly", 50, "Levitate", ["Curse"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    hp = g[Pok.CURRENT_HP]
    calculate_effects(g, d, move_slice(g, 0), 0)
    assert d[Pok.VOL_STATUS] & VolStatus.CURSE
    assert g[Pok.CURRENT_HP] == hp - g[Pok.MAX_HP] // 2


def test_non_ghost_curse_is_a_stat_move(poke):
    """Non-Ghost Curse: +1 Atk, +1 Def, -1 Spe on the user, no curse"""
    p = poke("Rattata", 50, "Run Away", ["Curse"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    hp = p[Pok.CURRENT_HP]
    calculate_effects(p, d, move_slice(p, 0), 0)
    assert (p[Pok.ATTACK_STAT_STAGE], p[Pok.DEFENSE_STAT_STAGE], p[Pok.SPEED_STAT_STAGE]) == (1, 1, -1)
    assert d[Pok.VOL_STATUS] == 0 and p[Pok.CURRENT_HP] == hp


def test_secondary_effect_guaranteed_and_skipped_on_faint(poke):
    """100% secondaries always apply, but not to a fainted target"""
    a = poke("Pikachu", 50, "Static", ["Thunder Shock"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    mv = move_slice(a, 0).copy()
    mv[Sec.CHANCE] = 100
    sec_effects(mv, a, d, 0)
    assert d[Pok.STATUS] == Status.PARALYSIS
    d[Pok.STATUS] = 0
    d[Pok.CURRENT_HP] = 0
    sec_effects(mv, a, d, 0)
    assert d[Pok.STATUS] == 0


def test_secondary_chance_rate(poke):
    """10% paralysis on Thunder Shock lands about 10% of the time"""
    a = poke("Pikachu", 50, "Static", ["Thunder Shock"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    mv = move_slice(a, 0)
    n, hits = 5000, 0
    for _ in range(n):
        d[Pok.STATUS] = 0
        sec_effects(mv, a, d, 0)
        hits += d[Pok.STATUS] == Status.PARALYSIS
    assert hits / n == pytest.approx(0.10, abs=0.015)
