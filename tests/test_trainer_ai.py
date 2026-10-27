"""Trainer AI: which expert-flag evaluation a status move is scored by, and that the AI can
pick a move with any implemented status move in its kit"""
import numpy as np
import pytest
from Models import trainer_ai_helper as ai
from Models.trainer_ai import return_idx
from Models.idx_const import Pok, Move
from Models.helper import VolStatus, Status, Types
from DataBase.AbilitiesDB import AbilityNames
from battle_driver import move_slice

# Status moves that carry both a volatile and a stat boost are the tricky ones
ROUTING = [
    ("Swagger", "vol"),        # confusion on the foe + Atk +2 → confuse logic (Psych Up case)
    ("Flatter", "vol"),        # confusion on the foe + SpA +1
    ("Confuse Ray", "vol"),
    ("Defense Curl", "stat"),  # Def +1, the volatile is only a Rollout marker
    ("Harden", "stat"),
    ("Growl", "stat"),
    ("Thunder Wave", "status"),
]


@pytest.mark.parametrize("move, expected", ROUTING)
def test_expert_flag_routing(monkeypatch, poke, move, expected):
    """expert_flag sends each status move to the evaluation of what the move is for"""
    called = []
    monkeypatch.setattr(ai, "expert_status", lambda *a: called.append("status") or 0)
    monkeypatch.setattr(ai, "expert_vol_status", lambda *a: called.append("vol") or 0)
    monkeypatch.setattr(ai, "expert_stat", lambda *a: called.append("stat") or 0)
    ai_pok = poke("Rattata", 20, "Run Away", [move])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    rand = np.zeros((4, 5, 2), dtype=np.int16)
    ai.expert_flag(ai_pok, user, move_slice(ai_pok, 0), 1, 0, rand, 0, 0, 1.0, 0)
    assert called == [expected]


@pytest.mark.parametrize("move", [
    "Swagger", "Flatter", "Defense Curl", "Thunder Wave", "Poison Powder", "Sleep Powder",
    "Hypnosis", "Will-O-Wisp", "Confuse Ray", "Supersonic",
])
@pytest.mark.parametrize("ai_faster", [True, False])
def test_ai_picks_a_move_with_status_kit(make_pokemon, make_battle, move, ai_faster):
    """Full-HP AI holding a status move, moving first or second, picks a legal slot"""
    me = make_pokemon("Geodude", 30 if not ai_faster else 10, "Sturdy", ["Tackle"])
    opp = make_pokemon("Pikachu", 30 if ai_faster else 10, "Static", ["Thunder Shock", move])
    arr = make_battle([me], [opp])
    for _ in range(20):
        assert return_idx(arr) in (0, 1)


def _expert(ai_pok, user, effectiveness=1.0):
    """Expert score of the AI's first move plus the random adjustments it queued"""
    rand = np.zeros((4, 5, 2), dtype=np.int16)
    score = ai.expert_flag(ai_pok, user, move_slice(ai_pok, 0), 1, 0, rand, 0, 0, effectiveness, 0)
    queued = [tuple(int(x) for x in rand[0, i]) for i in range(5) if rand[0, i, 1]]
    return score, queued


@pytest.mark.parametrize("move", ["Karate Chop", "Razor Leaf", "Air Cutter"])
@pytest.mark.parametrize("effectiveness, queued", [
    (0.0, []), (0.25, []), (0.5, []),   # resisted: no change
    (1.0, [(1, 64)]),                    # neutral: 25% of +1
    (2.0, [(1, 128)]), (4.0, [(1, 128)]),  # super effective: 50% of +1
])
def test_expert_high_crit(poke, move, effectiveness, queued):
    """pokeplatinum Expert_HighCritical"""
    ai_pok = poke("Machop", 20, "Guts", [move])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert _expert(ai_pok, user, effectiveness) == (0, queued)


@pytest.mark.parametrize("move", ["Icy Wind", "Rock Tomb", "Mud Shot"])
def test_expert_speed_down_on_hit(poke, move):
    """pokeplatinum Expert_SpeedDownOnHit: resisted no change, faster -3, slower 72.7% of +2"""
    slow_ai = poke("Geodude", 10, "Sturdy", [move])
    fast_ai = poke("Pikachu", 60, "Static", [move])
    user = poke("Rattata", 30, "Run Away", ["Tackle"])
    assert _expert(slow_ai, user, 0.5) == (0, [])
    assert _expert(fast_ai, user) == (-3, [])
    assert _expert(slow_ai, user) == (0, [(2, 186)])


def test_expert_speed_down_only_named_moves(poke):
    """Other speed-lowering attacks (Bubble Beam) aren't scored by the speed-down check"""
    ai_pok = poke("Geodude", 10, "Sturdy", ["Bubble Beam"])
    user = poke("Rattata", 30, "Run Away", ["Tackle"])
    assert _expert(ai_pok, user) == (0, [])


@pytest.mark.parametrize("move", ["Aerial Ace", "Feint Attack", "Magical Leaf", "Swift", "Shock Wave"])
def test_expert_never_miss_covers(poke, move):
    """CannotMiss branch: user accuracy -3 queues 60.9% of +1, -5 also adds a flat +1"""
    ai_pok = poke("Pidgey", 20, "Keen Eye", [move])
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    assert _expert(ai_pok, user) == (0, [])
    ai_pok[Pok.ACCURACY_STAT_STAGE] = -3
    assert _expert(ai_pok, user) == (0, [(1, 156)])
    ai_pok[Pok.ACCURACY_STAT_STAGE] = -5
    assert _expert(ai_pok, user) == (1, [(1, 156)])


def test_expert_focus_energy_scores_zero(poke):
    """Focus Energy has no Expert check"""
    ai_pok = poke("Rattata", 10, "Run Away", ["Focus Energy"])
    user = poke("Geodude", 10, "Sturdy", ["Tackle"])
    assert _expert(ai_pok, user) == (0, [])


def _basic(ai_pok, user, ability):
    return ai.basic_flag(move_slice(ai_pok, 0), ability, ai_pok, user, 1.0, 0)


@pytest.mark.parametrize("ai_ability, stages, expected", [
    ("Guts", {}, 0),
    ("Guts", {Pok.ATTACK_STAT_STAGE: 6}, -10),
    ("Guts", {Pok.DEFENSE_STAT_STAGE: 6}, -8),
    ("Guts", {Pok.ATTACK_STAT_STAGE: 5, Pok.DEFENSE_STAT_STAGE: 5}, 0),
    ("Simple", {Pok.ATTACK_STAT_STAGE: 3}, -10),
    ("Simple", {Pok.DEFENSE_STAT_STAGE: 3}, -10),
    ("Simple", {Pok.DEFENSE_STAT_STAGE: 2}, 0),
])
def test_basic_bulk_up(poke, ai_ability, stages, expected):
    """pokeplatinum Basic_CheckBulkUp"""
    ai_pok = poke("Machop", 20, ai_ability, ["Bulk Up"])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    for idx, val in stages.items():
        ai_pok[idx] = val
    assert _basic(ai_pok, user, AbilityNames.STURDY) == expected


@pytest.mark.parametrize("ai_ability, target_ability, stages, expected", [
    ("Run Away", "Sturdy", {}, 0),
    ("Run Away", "Clear Body", {}, -10),
    ("Run Away", "White Smoke", {}, -10),
    ("Mold Breaker", "Clear Body", {}, 0),
    ("Run Away", "Sturdy", {Pok.ATTACK_STAT_STAGE: -6}, -10),
    ("Run Away", "Sturdy", {Pok.DEFENSE_STAT_STAGE: -6}, -8),
])
def test_basic_tickle(poke, ai_ability, target_ability, stages, expected):
    """pokeplatinum Basic_CheckTickle"""
    ai_pok = poke("Rattata", 20, ai_ability, ["Tickle"])
    user = poke("Geodude", 20, target_ability, ["Tackle"])
    for idx, val in stages.items():
        user[idx] = val
    ability = getattr(AbilityNames, target_ability.upper().replace(" ", "_"))
    assert _basic(ai_pok, user, ability) == expected


def test_basic_focus_energy(poke):
    """pokeplatinum Basic_CheckAlreadyPumpedUp: -10 only if the AI already has Focus Energy"""
    ai_pok = poke("Rattata", 10, "Run Away", ["Focus Energy"])
    user = poke("Geodude", 10, "Sturdy", ["Tackle"])
    assert _basic(ai_pok, user, AbilityNames.STURDY) == 0
    user[Pok.VOL_STATUS] = VolStatus.FOCUS_ENERGY
    assert _basic(ai_pok, user, AbilityNames.STURDY) == 0
    ai_pok[Pok.VOL_STATUS] = VolStatus.FOCUS_ENERGY
    assert _basic(ai_pok, user, AbilityNames.STURDY) == -10


def test_ai_with_focus_energy(make_pokemon, make_battle):
    """The AI can score Focus Energy without crashing"""
    arr = make_battle(
        [make_pokemon("Geodude", 10, "Sturdy", ["Tackle"])],
        [make_pokemon("Rattata", 10, "Run Away", ["Tackle", "Focus Energy"])],
    )
    assert 0 <= return_idx(arr) <= 1



def test_expert_fake_tears_reads_target_spdef(poke):
    """pokeplatinum Expert_StatusSpDefenseDown checks the target's SpDef stage"""
    ai_pok = poke("Eevee", 20, "Run Away", ["Fake Tears"])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert _expert(ai_pok, user) == (0, [])
    ai_pok[Pok.SPECIAL_DEFENSE_STAT_STAGE] = -3
    assert _expert(ai_pok, user) == (0, [])
    user[Pok.SPECIAL_DEFENSE_STAT_STAGE] = -3
    assert _expert(ai_pok, user) == (0, [(-2, 206)])


def test_expert_accuracy_down_reads_target_accuracy(poke):
    """pokeplatinum Expert_StatusAccuracyDown: stop if AI HP > 70% or the TARGET's accuracy is +0"""
    ai_pok = poke("Pidgey", 20, "Keen Eye", ["Sand Attack"])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    ai_pok[Pok.MAX_HP], ai_pok[Pok.CURRENT_HP] = 100, 70
    assert _expert(ai_pok, user) == (0, [])            # target accuracy +0
    user[Pok.ACCURACY_STAT_STAGE] = 1
    assert _expert(ai_pok, user) == (0, [(-2, 186)])   # exactly 70% is not over 70%
    ai_pok[Pok.CURRENT_HP] = 71
    assert _expert(ai_pok, user) == (0, [])


def test_expert_tickle_uses_defense_down(poke):
    """pokeplatinum routes BATTLE_EFFECT_ATK_DEF_DOWN to Expert_StatusDefenseDown"""
    ai_pok = poke("Rattata", 20, "Run Away", ["Tickle"])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    user[Pok.ATTACK_STAT_STAGE] = -1     # would score -1 under the Atk-drop logic
    assert _expert(ai_pok, user) == (0, [])
    user[Pok.DEFENSE_STAT_STAGE] = -3
    assert _expert(ai_pok, user) == (0, [(-2, 206)])


# ── Phase 2: damage mechanics ────────────────────────────────────────────────

def test_basic_natural_gift_needs_berry(make_pokemon, poke):
    """pokeplatinum Basic_CheckNaturalGift: -10 without an eligible berry"""
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    no_berry = poke("Rattata", 20, "Run Away", ["Natural Gift"])
    berry = make_pokemon("Rattata", 20, "Run Away", ["Natural Gift"], item="Sitrus Berry").to_np()
    assert _basic(no_berry, user, AbilityNames.RUN_AWAY) == -10
    assert _basic(berry, user, AbilityNames.RUN_AWAY) == 0


@pytest.mark.parametrize("move, ai_ability, expected", [
    ("Seismic Toss", "Guts", -12),        # neutral on Normal/Flying
    ("Seismic Toss", "Mold Breaker", 0),
    ("Rock Throw", "Guts", 0),            # super effective goes through
])
def test_basic_wonder_guard(poke, move, ai_ability, expected):
    """Pokemow Check_WonderGuard: -12 unless the move is 2x/4x (or the AI has Mold Breaker)"""
    ai_pok = poke("Machop", 20, ai_ability, [move])
    user = poke("Pidgey", 20, "Keen Eye", ["Tackle"])
    assert _basic(ai_pok, user, AbilityNames.WONDER_GUARD) == expected


@pytest.mark.parametrize("move, ability, expected", [
    ("Thunder Shock", "Volt Absorb", -12), ("Thunder Shock", "Motor Drive", -12),
    ("Water Gun", "Water Absorb", -12), ("Ember", "Flash Fire", -12),
    ("Mud-Slap", "Levitate", -12), ("Growl", "Soundproof", -10), ("Tackle", "Levitate", 0),
])
def test_basic_absorbing_abilities(poke, move, ability, expected):
    """Pokemow Basic ability checks"""
    ai_pok = poke("Pikachu", 20, "Static", [move])
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    target = getattr(AbilityNames, ability.upper().replace(" ", "_"))
    assert _basic(ai_pok, user, target) == expected


@pytest.mark.parametrize("ai_ability, effectiveness, expected", [
    ("Rock Head", 1.0, 1), ("Magic Guard", 1.0, 1), ("Run Away", 1.0, 0), ("Rock Head", 0.5, 0),
])
def test_expert_recoil(poke, ai_ability, effectiveness, expected):
    """pokeplatinum Expert_RecoilMove: +1 with Rock Head or Magic Guard unless resisted"""
    ai_pok = poke("Rattata", 20, ai_ability, ["Take Down"])
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    assert _expert(ai_pok, user, effectiveness) == (expected, [])


@pytest.mark.parametrize("ai_ability, ai_level, effectiveness, expected", [
    ("Insomnia", 20, 0.5, (-1, [])),
    ("Insomnia", 50, 1.0, (0, [])),           # AI faster
    ("Insomnia", 5, 1.0, (0, [(1, 64)])),     # slower: 25%
    ("Rough Skin", 5, 1.0, (0, [(1, 128)])),  # slower with Rough Skin: 50%
])
def test_expert_assurance(poke, ai_ability, ai_level, effectiveness, expected):
    """pokeplatinum Expert_Assurance"""
    ai_pok = poke("Murkrow", ai_level, ai_ability, ["Assurance"])
    user = poke("Pikachu", 30, "Static", ["Tackle"])
    assert _expert(ai_pok, user, effectiveness) == expected


def test_expert_mirror_coat(poke):
    """pokeplatinum Expert_MirrorCoat: -1 vs a sleeping target, +4 at 60.9% with Counter known"""
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    ai_pok = poke("Wobbuffet", 20, "Shadow Tag", ["Mirror Coat", "Counter"])
    assert _expert(ai_pok, user) == (0, [(4, 156)])
    user[Pok.STATUS] = Status.SLEEP
    assert _expert(ai_pok, user) == (-1, [])
    user[Pok.STATUS] = 0
    alone = poke("Wobbuffet", 20, "Shadow Tag", ["Mirror Coat"])
    assert _expert(alone, user) == (0, [(4, 126)])          # Geodude has no special type
    assert _expert(alone, poke("Abra", 20, "Synchronize", ["Tackle"])) == (0, [])


def test_expert_counter_knows_mirror_coat(poke):
    """pokeplatinum Expert_Counter: +4 at 60.9% if the AI also knows Mirror Coat"""
    user = poke("Abra", 20, "Synchronize", ["Tackle"])
    ai_pok = poke("Wobbuffet", 20, "Shadow Tag", ["Counter", "Mirror Coat"])
    assert _expert(ai_pok, user) == (0, [(4, 156)])


@pytest.mark.parametrize("setup, ai_level, effectiveness, expected", [
    ("power_herb", 20, 1.0, (2, [])),
    (None, 20, 0.5, (1, [])),               # resisted: +1 (pokeplatinum quirk)
    ("toxic", 5, 1.0, (0, [(1, 176)])),
    (None, 50, 1.0, (0, [(1, 176)])),       # AI faster
    (None, 5, 1.0, (0, [])),                # AI slower
])
def test_expert_bounce(make_pokemon, poke, setup, ai_level, effectiveness, expected):
    """pokeplatinum Expert_ChargeTurnWithInvuln"""
    item = "Power Herb" if setup == "power_herb" else None
    ai_pok = make_pokemon("Pidgey", ai_level, "Keen Eye", ["Bounce"], item=item).to_np()
    user = poke("Rattata", 30, "Run Away", ["Tackle"])
    if setup == "toxic":
        user[Pok.STATUS] = Status.TOXIC
    assert _expert(ai_pok, user, effectiveness) == expected


def test_ai_move_view(make_pokemon, poke):
    """The AI damage calc sees Natural Gift's berry and Low Kick's weight power"""
    user = poke("Onix", 20, "Sturdy", ["Tackle"])
    gift = make_pokemon("Rattata", 20, "Run Away", ["Natural Gift"], item="Sitrus Berry").to_np()
    view = ai.ai_move_view(move_slice(gift, 0), gift, user)
    assert (view[Move.TYPE], view[Move.POWER]) == (Types.PSYCHIC, 60)
    assert move_slice(gift, 0)[Move.POWER] == 0
    kick = poke("Machop", 20, "Guts", ["Low Kick", "Tackle"])
    assert ai.ai_move_view(move_slice(kick, 0), kick, user)[Move.POWER] == 120
    tackle = move_slice(kick, 1)
    assert ai.ai_move_view(tackle, kick, user) is tackle


@pytest.mark.parametrize("move", [
    "Seismic Toss", "Night Shade", "Psywave", "Low Kick", "Magnitude", "Hidden Power",
    "Natural Gift", "Mirror Coat", "Assurance", "Take Down", "Bounce", "Fury Cutter", "Rollout",
])
def test_ai_picks_a_move_with_phase2_kit(make_pokemon, make_battle, move):
    """The AI scores every Phase 2 move without crashing and returns a legal slot"""
    me = make_pokemon("Geodude", 20, "Sturdy", ["Tackle"])
    opp = make_pokemon("Machop", 20, "Guts", ["Tackle", move], item="Sitrus Berry")
    arr = make_battle([me], [opp])
    for _ in range(20):
        assert return_idx(arr) in (0, 1)
