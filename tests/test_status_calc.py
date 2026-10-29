"""Status, volatile status and stat-change effects"""
import pytest
from Engine import status_calc
from Engine.status_calc import (
    apply_status, stat_changes, vol_status, calculate_effects, sec_effects, synchronize_reflect,
)
from DataBase.MoveDB import MoveName
from Models.idx_const import Pok, Move, Sec
from Models.helper import Status, Weather, VolStatus, SideCondition
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
    ("Pikachu", "Static", Status.PARALYSIS),  # Gen IV: Electric types aren't immune to paralysis
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



@pytest.mark.parametrize("move", ["Metal Claw", "Silver Wind"])
@pytest.mark.parametrize("target_fainted", [False, True])
def test_self_secondary_boosts_user(poke, move, target_fainted):
    """Metal Claw / Silver Wind raise the USER's stats, even when the hit KOs the target"""
    a = poke("Beedrill", 50, "Swarm", [move])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    if target_fainted:
        d[Pok.CURRENT_HP] = 0
    mv = move_slice(a, 0).copy()
    mv[Sec.CHANCE] = 100
    sec_effects(mv, a, d, 0)
    assert a[Pok.ATTACK_STAT_STAGE] == 1
    expected_others = 1 if move == "Silver Wind" else 0
    assert a[Pok.DEFENSE_STAT_STAGE] == expected_others
    assert a[Pok.SPECIAL_ATTACK_STAT_STAGE] == expected_others
    assert a[Pok.SPECIAL_DEFENSE_STAT_STAGE] == expected_others
    assert a[Pok.SPEED_STAT_STAGE] == expected_others
    assert not d[Pok.ATTACK_STAT_STAGE : Pok.EVASION_STAT_STAGE + 1].any()


def test_target_secondary_lowers_target(poke):
    """Mud-Slap's 100% accuracy drop lands on the target, not the user"""
    a = poke("Mudkip", 50, "Torrent", ["Mud-Slap"])
    d = poke("Rattata", 50, "Run Away", ["Tackle"])
    sec_effects(move_slice(a, 0), a, d, 0)
    assert d[Pok.ACCURACY_STAT_STAGE] == -1
    assert a[Pok.ACCURACY_STAT_STAGE] == 0


@pytest.mark.parametrize("name, status, applied", [
    ("Ponyta", Status.BURN, False),        # Fire can't be burned
    ("Rattata", Status.BURN, True),
    ("Swinub", Status.FREEZE, False),      # Ice can't be frozen
    ("Rattata", Status.FREEZE, True),
    ("Oddish", Status.POISON, False),      # Poison can't be poisoned
    ("Oddish", Status.TOXIC, False),
    ("Magnemite", Status.POISON, False),   # Steel can't be poisoned
    ("Magnemite", Status.TOXIC, False),
    ("Rattata", Status.TOXIC, True),
    ("Pikachu", Status.PARALYSIS, True),   # Gen IV: Electric isn't immune to paralysis
    ("Ponyta", Status.SLEEP, True),
])
@pytest.mark.parametrize("sec", [False, True])
def test_status_type_immunities(poke, name, status, applied, sec):
    """Type-based status immunities, for status moves and secondaries alike"""
    a = poke("Rattata", 50, "Run Away", ["Tackle"])
    d = poke(name, 50, "Run Away", ["Tackle"])
    mv = move_slice(a, 0).copy()
    mv[Sec.STATUS if sec else Move.STATUS] = status
    apply_status(mv, d, 0, a, sec)
    assert d[Pok.STATUS] == (status if applied else 0)


# ── Phase 3 volatiles ────────────────────────────────────────────────────────

@pytest.mark.parametrize("target, ability, seeded", [
    ("Rattata", "Run Away", True), ("Bulbasaur", "Overgrow", False),
])
def test_leech_seed_not_on_grass(poke, target, ability, seeded):
    """Grass types can't be seeded"""
    a = poke("Bulbasaur", 20, "Overgrow", ["Leech Seed"])
    d = poke(target, 20, ability, ["Tackle"])
    calculate_effects(a, d, move_slice(a, 0), 0)
    assert bool(d[Pok.VOL_STATUS] & VolStatus.LEECH_SEED) == seeded
    assert not a[Pok.VOL_STATUS] & VolStatus.LEECH_SEED


@pytest.mark.parametrize("user_gender, target_gender, attracted", [
    ("Male", "Female", True), ("Female", "Male", True), ("Male", "Male", False),
    ("Female", "Female", False), ("Male", "Genderless", False), ("Genderless", "Female", False),
])
def test_attract_needs_opposite_genders(poke, user_gender, target_gender, attracted):
    """Infatuation only between a male and a female"""
    a = poke("Pikachu", 20, "Static", ["Attract"], gender=user_gender)
    d = poke("Rattata", 20, "Run Away", ["Tackle"], gender=target_gender)
    calculate_effects(a, d, move_slice(a, 0), 0)
    assert bool(d[Pok.VOL_STATUS] & VolStatus.ATTRACT) == attracted


@pytest.mark.parametrize("status, drowsy", [(0, True), (Status.PARALYSIS, False)])
def test_yawn_sets_two_turn_counter(poke, status, drowsy):
    """Yawn fails on a target with a status, otherwise it counts 2 turns"""
    a = poke("Rattata", 20, "Run Away", ["Yawn"])
    d = poke("Pikachu", 20, "Static", ["Tackle"])
    d[Pok.STATUS] = status
    calculate_effects(a, d, move_slice(a, 0), 0)
    assert bool(d[Pok.VOL_STATUS] & VolStatus.YAWN) == drowsy
    assert d[Pok.YAWN_TURNS] == (2 if drowsy else 0)


@pytest.mark.parametrize("move, vol, on_user", [
    ("Mud Sport", VolStatus.MUD_SPORT, True), ("Water Sport", VolStatus.WATER_SPORT, True),
    ("Ingrain", VolStatus.INGRAIN, True), ("Aqua Ring", VolStatus.AQUA_RING, True),
    ("Destiny Bond", VolStatus.DESTINY_BOND, True), ("Foresight", VolStatus.FORESIGHT, False),
    ("Odor Sleuth", VolStatus.FORESIGHT, False),
])
def test_phase3_volatile_targets(poke, move, vol, on_user):
    """Field-targeted Sports and self moves mark the user, Foresight marks the target"""
    a = poke("Rattata", 20, "Run Away", [move])
    d = poke("Gastly", 20, "Levitate", ["Lick"])
    calculate_effects(a, d, move_slice(a, 0), 0)
    assert bool(a[Pok.VOL_STATUS] & vol) == on_user
    assert bool(d[Pok.VOL_STATUS] & vol) != on_user


def test_charge_sets_volatile_and_spdef(poke):
    """Charge raises SpDef by one and marks the next Electric move"""
    a = poke("Pikachu", 20, "Static", ["Charge"])
    d = poke("Rattata", 20, "Run Away", ["Tackle"])
    calculate_effects(a, d, move_slice(a, 0), 0)
    assert a[Pok.VOL_STATUS] & VolStatus.CHARGE
    assert a[Pok.SPECIAL_DEFENSE_STAT_STAGE] == 1


@pytest.mark.parametrize("move", ["Helping Hand", "Follow Me"])
def test_singles_only_moves_do_nothing(poke, move):
    """Helping Hand fails and Follow Me has no effect in a single battle"""
    a = poke("Rattata", 20, "Run Away", [move])
    d = poke("Pikachu", 20, "Static", ["Tackle"])
    calculate_effects(a, d, move_slice(a, 0), 0)
    assert a[Pok.VOL_STATUS] == 0 == d[Pok.VOL_STATUS]


# ── Phase 4 volatiles ────────────────────────────────────────────────────────

def _use(pok, slot):
    """The move in this slot is the one the Pokemon used last"""
    pok[Pok.LAST_MOVE_ID] = move_slice(pok, slot)[Move.ID]


def test_taunt_lasts_3_to_5_turns_and_isnt_refreshed(poke):
    """Gen IV Taunt: 3-5 turns, fails on a taunted target"""
    a = poke("Murkrow", 20, "Run Away", ["Taunt"])
    d = poke("Rattata", 20, "Run Away", ["Growl"])
    seen = set()
    for _ in range(200):
        d[Pok.VOL_STATUS] = 0
        vol_status(move_slice(a, 0), d, a)
        assert d[Pok.VOL_STATUS] & VolStatus.TAUNT
        seen.add(int(d[Pok.TAUNT_TURNS]))
    assert seen == {3, 4, 5}
    d[Pok.TAUNT_TURNS] = 1
    vol_status(move_slice(a, 0), d, a)
    assert d[Pok.TAUNT_TURNS] == 1


@pytest.mark.parametrize("move, vol, field, turns", [
    ("Encore", VolStatus.ENCORE, Pok.ENCORE_TURNS, {3, 4, 5, 6, 7}),
    ("Disable", VolStatus.DISABLE, Pok.DISABLE_TURNS, {3, 4, 5, 6}),
])
def test_encore_disable_pack_the_last_move_slot(poke, move, vol, field, turns):
    """The counter holds turns * 4 + the slot of the target's last move"""
    a = poke("Rattata", 20, "Run Away", [move])
    d = poke("Rattata", 20, "Run Away", ["Tackle", "Growl"])
    _use(d, 1)
    seen = set()
    for _ in range(300):
        d[Pok.VOL_STATUS] = 0
        vol_status(move_slice(a, 0), d, a)
        assert d[Pok.VOL_STATUS] & vol and d[field] % 4 == 1
        seen.add(int(d[field]) // 4)
    assert seen == turns


@pytest.mark.parametrize("move, vol, field", [
    ("Encore", VolStatus.ENCORE, Pok.ENCORE_TURNS),
    ("Disable", VolStatus.DISABLE, Pok.DISABLE_TURNS),
])
@pytest.mark.parametrize("case", ["no_last_move", "no_pp", "already", "struggle"])
def test_encore_disable_fail(poke, move, vol, field, case):
    """Both fail without a last move, on a move out of PP, on Struggle, or when already set"""
    a = poke("Rattata", 20, "Run Away", [move])
    d = poke("Rattata", 20, "Run Away", ["Tackle", "Growl"])
    _use(d, 0)
    if case == "no_last_move":
        d[Pok.LAST_MOVE_ID] = 0
    elif case == "no_pp":
        move_slice(d, 0)[Move.PP] = 0
    elif case == "already":
        d[Pok.VOL_STATUS] = vol
        d[field] = 5 * 4 + 1
    else:
        d[Pok.LAST_MOVE_ID] = MoveName.STRUGGLE
    before = int(d[field])
    vol_status(move_slice(a, 0), d, a)
    assert d[field] == before
    assert bool(d[Pok.VOL_STATUS] & vol) == (case == "already")


def test_encore_fails_on_encore_and_mirror_move_disable_doesnt(poke):
    """Gen IV can't Encore Encore or Mirror Move, Disable has no such list"""
    encore = poke("Rattata", 20, "Run Away", ["Encore"])
    disable = poke("Rattata", 20, "Run Away", ["Disable"])
    d = poke("Pidgey", 20, "Run Away", ["Encore", "Mirror Move"])
    for slot in (0, 1):
        _use(d, slot)
        d[Pok.VOL_STATUS] = 0
        vol_status(move_slice(encore, 0), d, encore)
        assert not d[Pok.VOL_STATUS] & VolStatus.ENCORE
        vol_status(move_slice(disable, 0), d, disable)
        assert d[Pok.VOL_STATUS] & VolStatus.DISABLE


@pytest.mark.parametrize("holder", ["source", "target"])
@pytest.mark.parametrize("ability, sleeps", [("Run Away", False), ("Soundproof", True)])
def test_sleep_fails_during_uproar(poke, holder, ability, sleeps):
    """Nobody falls asleep while either active makes an uproar, except a Soundproof target"""
    a = poke("Abra", 20, "Run Away", ["Hypnosis"])
    d = poke("Rattata", 20, ability, ["Tackle"])
    (a if holder == "source" else d)[Pok.VOL_STATUS] = VolStatus.UPROAR
    apply_status(move_slice(a, 0), d, 0, a)
    assert (d[Pok.STATUS] == Status.SLEEP) == sleeps


def test_fainted_uproar_holder_doesnt_block_sleep(poke):
    """The uproar ends with its user"""
    a = poke("Abra", 20, "Run Away", ["Hypnosis"])
    d = poke("Rattata", 20, "Run Away", ["Tackle"])
    a[Pok.VOL_STATUS] = VolStatus.UPROAR
    a[Pok.CURRENT_HP] = 0
    apply_status(move_slice(a, 0), d, 0, a)
    assert d[Pok.STATUS] == Status.SLEEP


# ── Phase 5 Mist and Safeguard ───────────────────────────────────────────────

MIST = SideCondition.MIST
SAFEGUARD = SideCondition.SAFEGUARD


def test_mist_blocks_drops_from_the_foe(poke):
    """Growl and Sand Attack do nothing to a Misted side, the user's own boosts still apply"""
    a = poke("Rattata", 20, "Run Away", ["Growl", "Sand Attack", "Harden"])
    d = poke("Rattata", 20, "Run Away", ["Tackle"])
    stat_changes(move_slice(a, 0), a, d, False, MIST)
    stat_changes(move_slice(a, 1), a, d, False, MIST)
    assert d[Pok.ATTACK_STAT_STAGE] == 0 and d[Pok.ACCURACY_STAT_STAGE] == 0
    stat_changes(move_slice(a, 2), a, d, False, MIST)
    assert a[Pok.DEFENSE_STAT_STAGE] == 1


def test_mist_lets_raises_through(poke):
    """Swagger still raises the Misted target's Attack"""
    a = poke("Rattata", 20, "Run Away", ["Swagger"])
    d = poke("Rattata", 20, "Run Away", ["Tackle"])
    stat_changes(move_slice(a, 0), a, d, False, MIST)
    assert d[Pok.ATTACK_STAT_STAGE] == 2


def test_mist_blocks_secondary_drops(monkeypatch, poke):
    """A secondary drop (Bubble's Speed -1) doesn't land through Mist"""
    a = poke("Squirtle", 20, "Torrent", ["Bubble"])
    d = poke("Rattata", 20, "Run Away", ["Tackle"])
    monkeypatch.setattr(status_calc.random, "randint", lambda lo, hi: lo)
    sec_effects(move_slice(a, 0), a, d, 0, MIST)
    assert d[Pok.SPEED_STAT_STAGE] == 0
    sec_effects(move_slice(a, 0), a, d, 0)
    assert d[Pok.SPEED_STAT_STAGE] == -1


def test_safeguard_blocks_status_confusion_and_yawn(poke):
    """Safeguard stops major status, confusion and Yawn, not Leech Seed"""
    a = poke("Pikachu", 20, "Static", ["Thunder Wave", "Confuse Ray", "Yawn", "Leech Seed"])
    d = poke("Rattata", 20, "Run Away", ["Tackle"])
    for slot in range(4):
        calculate_effects(a, d, move_slice(a, slot), 0, SAFEGUARD)
    assert d[Pok.STATUS] == 0
    assert d[Pok.VOL_STATUS] == VolStatus.LEECH_SEED


def test_safeguard_blocks_secondary_status(monkeypatch, poke):
    """Ember's burn doesn't land through Safeguard"""
    a = poke("Charmander", 20, "Blaze", ["Ember"])
    d = poke("Rattata", 20, "Run Away", ["Tackle"])
    monkeypatch.setattr(status_calc.random, "randint", lambda lo, hi: lo)
    sec_effects(move_slice(a, 0), a, d, 0, SAFEGUARD)
    assert d[Pok.STATUS] == 0
    sec_effects(move_slice(a, 0), a, d, 0)
    assert d[Pok.STATUS] == Status.BURN


# ── Phase 7: Insomnia and Vital Spirit ───────────────────────────────────────

@pytest.mark.parametrize("ability", ["Insomnia", "Vital Spirit"])
@pytest.mark.parametrize("atk_ability, sleeps", [("Run Away", False), ("Mold Breaker", True)])
def test_sleep_abilities_block_sleep_and_yawn(poke, ability, atk_ability, sleeps):
    """Insomnia and Vital Spirit stop sleep moves and Yawn landing, Mold Breaker ignores them"""
    a = poke("Rattata", 20, atk_ability, ["Hypnosis", "Yawn"])
    d = poke("Murkrow", 20, ability, ["Tackle"])
    calculate_effects(a, d, move_slice(a, 1), 0)
    assert bool(d[Pok.VOL_STATUS] & VolStatus.YAWN) == sleeps
    calculate_effects(a, d, move_slice(a, 0), 0)
    assert (d[Pok.STATUS] == Status.SLEEP) == sleeps


# ── Phase 8: Tri Attack ──────────────────────────────────────────────────────

@pytest.mark.parametrize("pick, status", [
    (0, Status.BURN), (1, Status.PARALYSIS), (2, Status.FREEZE),
])
def test_tri_attack_picks_one_of_three(monkeypatch, poke, pick, status):
    """The 20% secondary burns, paralyzes or freezes, one of the three at random"""
    monkeypatch.setattr(status_calc.random, "randint", lambda a, b: 1)
    monkeypatch.setattr(status_calc.random, "randrange", lambda n: pick)
    a = poke("Rattata", 20, "Run Away", ["Tri Attack"])
    d = poke("Machop", 20, "Guts", ["Tackle"])
    sec_effects(move_slice(a, 0), a, d, 0)
    assert d[Pok.STATUS] == status
