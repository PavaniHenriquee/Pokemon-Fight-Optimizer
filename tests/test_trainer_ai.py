"""Trainer AI: which expert-flag evaluation a status move is scored by, and that the AI can
pick a move with any implemented status move in its kit"""
import numpy as np
import pytest
from Models import trainer_ai_helper as ai
from Models.trainer_ai import return_idx, sub_after_death, MOVE_EXCEP
from Models.idx_const import Pok, Move, POK_LEN, Field
from Models.helper import VolStatus, Status, Types, Enemy_AI_Knows, SideCondition, Weather
from DataBase.AbilitiesDB import AbilityNames
from DataBase.ItemDB import ItemNames
from DataBase.MoveDB import MoveName
from battle_driver import move_slice, pok_slice, _p, opp_active

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


# Moves the AI must be able to hold and score without crashing, one group per battle setup
KIT_STATUS = (
    "Swagger", "Flatter", "Defense Curl", "Thunder Wave", "Poison Powder", "Sleep Powder",
    "Hypnosis", "Will-O-Wisp", "Confuse Ray", "Supersonic",
)
KIT_DAMAGE = (
    "Seismic Toss", "Night Shade", "Psywave", "Low Kick", "Magnitude", "Hidden Power",
    "Natural Gift", "Mirror Coat", "Assurance", "Take Down", "Bounce", "Fury Cutter", "Rollout",
    "Explosion", "Selfdestruct", "Fissure", "Guillotine", "Sheer Cold",
)
KIT_VOLATILE = (
    "Protect", "Endure", "Feint", "Foresight", "Odor Sleuth", "Mud Sport", "Water Sport",
    "Ingrain", "Aqua Ring", "Attract", "Leech Seed", "Charge", "Destiny Bond", "Yawn", "Rage",
    "Helping Hand", "Follow Me", "Dig", "Gravity", "Minimize",
)
KIT_CALLING = ("Metronome", "Copycat", "Mirror Move", "Nature Power")


def test_ai_picks_a_legal_slot_with_every_kit(make_pokemon, make_battle):
    """For each move in the kits above, the AI holding it picks a legal slot every time"""
    battles = []
    for move in KIT_STATUS:
        for ai_faster in (True, False):
            battles.append((move, make_battle(
                [make_pokemon("Geodude", 10 if ai_faster else 30, "Sturdy", ["Tackle"])],
                [make_pokemon("Pikachu", 30 if ai_faster else 10, "Static",
                              ["Thunder Shock", move])])))
    for move in KIT_DAMAGE:
        battles.append((move, make_battle(
            [make_pokemon("Geodude", 20, "Sturdy", ["Tackle"])],
            [make_pokemon("Machop", 20, "Guts", ["Tackle", move], item="Sitrus Berry")])))
    for move in KIT_VOLATILE:
        battles.append((move, make_battle(
            [make_pokemon("Geodude", 20, "Sturdy", ["Tackle"], gender="Female")],
            [make_pokemon("Machop", 20, "Guts", ["Tackle", move])])))
    for move in KIT_CALLING:
        battles.append((move, make_battle(
            [make_pokemon("Machop", 20, "Guts", ["Tackle"])],
            [make_pokemon("Togepi", 20, "Hustle", [move, "Pound"])])))
    bad = {}
    for move, arr in battles:
        picks = {int(return_idx(arr)) for _ in range(20)}
        if not picks <= {0, 1}:
            bad[move] = picks
    assert not bad


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


def test_ai_move_view_gyro_ball(poke):
    """The AI sees Gyro Ball's speed power (pokeplatinum TrainerAI_CalcDamage), not MoveDB's 0"""
    gyro = poke("Bronzor", 20, "Levitate", ["Gyro Ball"])
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    gyro[Pok.SPEED] = 20
    user[Pok.SPEED] = 100
    assert ai.ai_move_view(move_slice(gyro, 0), gyro, user)[Move.POWER] == 126
    assert move_slice(gyro, 0)[Move.POWER] == 0


# ── Phase 3 volatiles ────────────────────────────────────────────────────────

def _expert_knows(ai_pok, user, ai_know=0):
    """_expert with the AI_KNOWS field passed through"""
    rand = np.zeros((4, 5, 2), dtype=np.int16)
    score = ai.expert_flag(ai_pok, user, move_slice(ai_pok, 0), 1, 0, rand, 0, 0, 1.0, 0, ai_know)
    queued = [tuple(int(x) for x in rand[0, i]) for i in range(5) if rand[0, i, 1]]
    return score, queued


@pytest.mark.parametrize("move, setup, expected", [
    ("Leech Seed", {}, 0),
    ("Leech Seed", {"user_vol": VolStatus.LEECH_SEED}, -10),
    ("Leech Seed", {"user": ("Bulbasaur", "Overgrow")}, -10),
    ("Leech Seed", {"user": ("Abra", "Magic Guard")}, -10),
    ("Foresight", {}, 0),
    ("Foresight", {"user_vol": VolStatus.FORESIGHT}, -10),
    ("Odor Sleuth", {"user_vol": VolStatus.FORESIGHT}, -10),
    ("Ingrain", {}, 0),
    ("Ingrain", {"ai_vol": VolStatus.INGRAIN}, -10),
    ("Aqua Ring", {"ai_vol": VolStatus.AQUA_RING}, -10),
    ("Mud Sport", {"ai_vol": VolStatus.MUD_SPORT}, -10),
    ("Water Sport", {"ai_vol": VolStatus.WATER_SPORT}, -10),
    ("Water Sport", {"user_vol": VolStatus.WATER_SPORT}, 0),
    ("Yawn", {}, 0),
    ("Yawn", {"user_status": Status.BURN}, -10),
    ("Yawn", {"user": ("Hoothoot", "Insomnia")}, -10),
    ("Helping Hand", {}, -10),
    ("Follow Me", {}, 0),
])
def test_basic_phase3_volatiles(poke, move, setup, expected):
    """pokeplatinum / Pokemow Basic checks for the Phase 3 volatiles"""
    ai_pok = poke("Bulbasaur", 20, "Overgrow", [move])
    name, ability = setup.get("user", ("Rattata", "Run Away"))
    user = poke(name, 20, ability, ["Tackle"])
    ai_pok[Pok.VOL_STATUS] = setup.get("ai_vol", 0)
    user[Pok.VOL_STATUS] = setup.get("user_vol", 0)
    user[Pok.STATUS] = setup.get("user_status", 0)
    target_ability = getattr(AbilityNames, ability.upper().replace(" ", "_"))
    assert _basic(ai_pok, user, target_ability) == expected


@pytest.mark.parametrize("ai_gender, user_gender, expected", [
    ("Male", "Female", 0), ("Male", "Male", -10), ("Genderless", "Female", -10),
    ("Female", "Genderless", -10),
])
def test_basic_attract_genders(poke, ai_gender, user_gender, expected):
    """Basic_CheckCannotAttract, a genderless AI can't Attract either (E1)"""
    ai_pok = poke("Rattata", 20, "Run Away", ["Attract"], gender=ai_gender)
    user = poke("Pikachu", 20, "Static", ["Tackle"], gender=user_gender)
    assert _basic(ai_pok, user, AbilityNames.STATIC) == expected


def test_expert_protect(poke):
    """Pokemow Expert Protect: chain, the AI's or the foe's residual damage, seen Feint/Recover"""
    ai_pok = poke("Rattata", 20, "Run Away", ["Protect"])
    user = poke("Machop", 20, "Guts", ["Feint", "Recover"])
    assert _expert_knows(ai_pok, user) == (0, [(2, 85), (-1, 128)])
    ai_pok[Pok.PROTECT_COUNT] = 1
    assert _expert_knows(ai_pok, user) == (-1, [(2, 85), (-1, 128), (-1, 128)])
    ai_pok[Pok.PROTECT_COUNT] = 2
    assert _expert_knows(ai_pok, user) == (-2, [])
    ai_pok[Pok.PROTECT_COUNT] = 0
    user[Pok.STATUS] = Status.TOXIC
    assert _expert_knows(ai_pok, user) == (2, [(-1, 128)])
    ai_pok[Pok.VOL_STATUS] = VolStatus.LEECH_SEED
    assert _expert_knows(ai_pok, user) == (-2, [])
    ai_pok[Pok.VOL_STATUS] = 0
    user[Pok.STATUS] = 0
    assert _expert_knows(ai_pok, user, Enemy_AI_Knows.MOVE1) == (0, [(-2, 128), (2, 85), (-1, 128)])
    assert _expert_knows(ai_pok, user, Enemy_AI_Knows.MOVE2) == (-2, [])


@pytest.mark.parametrize("hp, expected", [(3, (-1, [])), (20, (0, [(1, 186)])), (50, (-1, []))])
def test_expert_endure(poke, hp, expected):
    """Pokemow Expert Endure by the AI's HP percent"""
    ai_pok = poke("Rattata", 20, "Run Away", ["Endure"])
    user = poke("Machop", 20, "Guts", ["Tackle"])
    ai_pok[Pok.CURRENT_HP] = ai_pok[Pok.MAX_HP] * hp // 100 + (1 if hp == 20 else 0)
    if hp == 3:
        ai_pok[Pok.CURRENT_HP] = 1
    assert _expert_knows(ai_pok, user) == expected


def test_expert_foresight_checks_its_own_ghost_type(poke):
    """The AI's own Ghost type (pokeplatinum bug), then the target's evasion"""
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    assert _expert_knows(poke("Gastly", 20, "Levitate", ["Foresight"]), user) == (0, [(2, 121)])
    ai_pok = poke("Machop", 20, "Guts", ["Foresight"])
    assert _expert_knows(ai_pok, user) == (-2, [])
    user[Pok.EVASION_STAT_STAGE] = 3
    assert _expert_knows(ai_pok, user) == (0, [(2, 176)])


def test_expert_destiny_bond(poke):
    """Slower or above 70% HP: -1, otherwise rolls by HP"""
    ai_pok = poke("Gastly", 50, "Levitate", ["Destiny Bond"])
    user = poke("Rattata", 5, "Run Away", ["Tackle"])
    assert _expert_knows(ai_pok, user) == (-1, [])
    ai_pok[Pok.CURRENT_HP] = ai_pok[Pok.MAX_HP] // 4
    assert _expert_knows(ai_pok, user) == (0, [(-1, 128), (1, 128), (2, 156)])
    slow_ai = poke("Gastly", 5, "Levitate", ["Destiny Bond"])
    slow_ai[Pok.CURRENT_HP] = 1
    assert _expert_knows(slow_ai, poke("Rattata", 50, "Run Away", ["Tackle"])) == (-1, [])


def test_expert_leech_seed(poke):
    """Pokemow's Toxic check: low HP with a damaging move, knowing Protect"""
    ai_pok = poke("Bulbasaur", 20, "Overgrow", ["Leech Seed", "Tackle", "Protect"])
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    assert _expert_knows(ai_pok, user) == (0, [(2, 196)])
    ai_pok[Pok.CURRENT_HP] = ai_pok[Pok.MAX_HP] // 2
    user[Pok.CURRENT_HP] = user[Pok.MAX_HP] // 2
    assert _expert_knows(ai_pok, user) == (0, [(-3, 206), (-3, 206), (2, 196)])
    status_only = poke("Bulbasaur", 20, "Overgrow", ["Leech Seed"])
    status_only[Pok.CURRENT_HP] = 1
    assert _expert_knows(status_only, user) == (0, [])


@pytest.mark.parametrize("move, target, ai_hp_half, expected", [
    ("Mud Sport", "Pikachu", False, 1), ("Mud Sport", "Rattata", False, -1),
    ("Mud Sport", "Pikachu", True, -1), ("Water Sport", "Charmander", False, 1),
    ("Water Sport", "Pikachu", False, -1),
])
def test_expert_sports(poke, move, target, ai_hp_half, expected):
    """Pokemow Expert Mud Sport / Water Sport"""
    ai_pok = poke("Rattata", 20, "Run Away", [move])
    user = poke(target, 20, "Static", ["Tackle"])
    if ai_hp_half:
        ai_pok[Pok.CURRENT_HP] = ai_pok[Pok.MAX_HP] // 3
    assert _expert_knows(ai_pok, user) == (expected, [])


def test_expert_aqua_ring(poke):
    """50% of +1 from 30% HP up"""
    ai_pok = poke("Squirtle", 20, "Torrent", ["Aqua Ring"])
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    assert _expert_knows(ai_pok, user) == (0, [(1, 128)])
    ai_pok[Pok.CURRENT_HP] = 1
    assert _expert_knows(ai_pok, user) == (0, [])


def test_expert_feint(poke):
    """Pokemow Expert Feint once the AI saw Protect, by the target's Protect chain"""
    ai_pok = poke("Rattata", 20, "Run Away", ["Feint"])
    user = poke("Machop", 20, "Guts", ["Protect"])
    seen = Enemy_AI_Knows.MOVE1
    assert _expert_knows(ai_pok, user, seen) == (0, [(1, 128)])
    user[Pok.CURRENT_HP] -= 1
    assert _expert_knows(ai_pok, user, seen) == (0, [(1, 128), (1, 128)])
    user[Pok.PROTECT_COUNT] = 1
    assert _expert_knows(ai_pok, user, seen) == (0, [(1, 128), (1, 64)])
    user[Pok.PROTECT_COUNT] = 2
    assert _expert_knows(ai_pok, user, seen) == (-2, [(1, 128)])


@pytest.mark.parametrize("move", ["Attract", "Yawn", "Ingrain", "Charge", "Rage", "Follow Me",
                                  "Helping Hand"])
def test_expert_phase3_without_check_scores_zero(poke, move):
    """No Expert script, the fallback scores 0 instead of raising"""
    ai_pok = poke("Pikachu", 20, "Static", [move])
    user = poke("Rattata", 20, "Run Away", ["Tackle"], gender="Female")
    assert _expert_knows(ai_pok, user)[0] == 0


def test_ingrained_ai_never_switches(make_pokemon, make_battle):
    """Withdraw checks are skipped while Ingrain roots the AI's active"""
    me = make_pokemon("Gastly", 20, "Levitate", ["Lick"])
    opp = [make_pokemon("Rattata", 20, "Run Away", ["Tackle", "Quick Attack"]),
           make_pokemon("Pikachu", 20, "Static", ["Thunder Shock"])]
    arr = make_battle([me], opp)
    picks = [return_idx(arr) for _ in range(30)]
    assert any(p < 0 for p in picks)
    pok_slice(arr, 0, opp=True)[Pok.VOL_STATUS] = VolStatus.INGRAIN
    assert all(return_idx(arr) in (0, 1) for _ in range(30))


def test_expert_bounce_seen_protect(poke):
    """Pokemow Fly check: -1 once the AI saw the target use Protect"""
    ai_pok = poke("Pidgey", 50, "Keen Eye", ["Bounce"])
    user = poke("Rattata", 30, "Run Away", ["Tackle", "Protect"])
    assert _expert_knows(ai_pok, user) == (0, [(1, 176)])
    assert _expert_knows(ai_pok, user, Enemy_AI_Knows.MOVE1) == (0, [(1, 176)])
    assert _expert_knows(ai_pok, user, Enemy_AI_Knows.MOVE2) == (-1, [])


@pytest.mark.parametrize("ability, expected", [
    ("Run Away", 0), ("Insomnia", -10), ("Vital Spirit", -10),
])
def test_basic_sleep_move_vs_insomnia(poke, ability, expected):
    """Basic_CheckCannotSleep: Insomnia blocks sleep moves like Vital Spirit"""
    ai_pok = poke("Abra", 20, "Synchronize", ["Hypnosis"])
    user = poke("Hoothoot", 20, ability, ["Tackle"])
    target_ability = getattr(AbilityNames, ability.upper().replace(" ", "_"))
    assert _basic(ai_pok, user, target_ability) == expected


def test_charge_has_no_ai_check(poke):
    """Pokemow has no Basic or Expert check for Charge, even at +6 SpDef or vs Volt Absorb"""
    ai_pok = poke("Pikachu", 20, "Static", ["Charge"])
    user = poke("Rattata", 20, "Volt Absorb", ["Tackle"])
    ai_pok[Pok.SPECIAL_DEFENSE_STAT_STAGE] = 6
    assert _basic(ai_pok, user, AbilityNames.VOLT_ABSORB) == 0
    assert _expert_knows(ai_pok, user) == (0, [])


# ── Phase 4 volatiles ────────────────────────────────────────────────────────

@pytest.mark.parametrize("move, vol", [("Encore", VolStatus.ENCORE), ("Disable", VolStatus.DISABLE)])
def test_basic_encore_disable_already_set(poke, move, vol):
    """Basic_CheckCannotEncore / Basic_CheckCannotDisable: -8 on a target that already has it"""
    ai_pok = poke("Rattata", 20, "Run Away", [move])
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    assert _basic(ai_pok, user, AbilityNames.RUN_AWAY) == 0
    user[Pok.VOL_STATUS] = vol
    assert _basic(ai_pok, user, AbilityNames.RUN_AWAY) == -8


def test_expert_encore(poke):
    """Pokemow Encore: Disabled target 88.3% +3, AI slower -2, last move on the list 88.3% +3"""
    user = poke("Rattata", 30, "Run Away", ["Tackle", "Protect"])
    slow_ai = poke("Rattata", 10, "Run Away", ["Encore"])
    fast_ai = poke("Rattata", 60, "Run Away", ["Encore"])
    assert _expert(slow_ai, user) == (-2, [])
    user[Pok.LAST_MOVE_ID] = move_slice(user, 0)[Move.ID]
    assert _expert(fast_ai, user) == (-2, [])
    user[Pok.LAST_MOVE_ID] = move_slice(user, 1)[Move.ID]
    assert _expert(fast_ai, user) == (0, [(3, 226)])
    user[Pok.VOL_STATUS] = VolStatus.DISABLE
    assert _expert(slow_ai, user) == (0, [(3, 226)])


def test_expert_disable(poke):
    """Pokemow Disable: AI slower no change, status or no last move 60.9% -1, damaging +1"""
    user = poke("Rattata", 30, "Run Away", ["Tackle", "Protect"])
    slow_ai = poke("Rattata", 10, "Run Away", ["Disable"])
    fast_ai = poke("Rattata", 60, "Run Away", ["Disable"])
    user[Pok.LAST_MOVE_ID] = move_slice(user, 0)[Move.ID]
    assert _expert(slow_ai, user) == (0, [])
    assert _expert(fast_ai, user) == (1, [])
    user[Pok.LAST_MOVE_ID] = move_slice(user, 1)[Move.ID]
    assert _expert(fast_ai, user) == (0, [(-1, 156)])
    user[Pok.LAST_MOVE_ID] = 0
    assert _expert(fast_ai, user) == (0, [(-1, 156)])


@pytest.mark.parametrize("move", ["Wrap", "Bind", "Clamp", "Fire Spin"])
def test_expert_binding_moves(poke, move):
    """pokeplatinum Expert_BindingMove: 50% +1 vs Toxic, Curse or Attract (not plain poison)"""
    ai_pok = poke("Rattata", 20, "Run Away", [move])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert _expert(ai_pok, user) == (0, [])
    user[Pok.STATUS] = Status.POISON
    assert _expert(ai_pok, user) == (0, [])
    user[Pok.STATUS] = Status.TOXIC
    assert _expert(ai_pok, user) == (0, [(1, 128)])
    user[Pok.STATUS] = 0
    for vol in (VolStatus.CURSE, VolStatus.ATTRACT):
        user[Pok.VOL_STATUS] = vol
        assert _expert(ai_pok, user) == (0, [(1, 128)])


def test_expert_whirlpool_has_no_check(poke):
    """Whirlpool has its own effect in Gen IV, without an Expert check"""
    ai_pok = poke("Psyduck", 20, "Damp", ["Whirlpool"])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    user[Pok.STATUS] = Status.TOXIC
    assert _expert(ai_pok, user) == (0, [])


@pytest.mark.parametrize("move", ["Counter", "Mirror Coat"])
def test_expert_counter_mirror_coat_taunted_target(poke, move):
    """60.9% chance of +1 more when the target is taunted"""
    user = poke("Psyduck", 20, "Damp", ["Tackle"])
    ai_pok = poke("Wobbuffet", 20, "Shadow Tag", [move])
    score, queued = _expert(ai_pok, user)
    user[Pok.VOL_STATUS] = VolStatus.TAUNT
    assert _expert(ai_pok, user) == (score, [(1, 156)] + queued)


@pytest.mark.parametrize("vol, field, packed, moves, pick", [
    (VolStatus.TAUNT, Pok.TAUNT_TURNS, 3, ["Growl", "Tackle"], 1),
    (VolStatus.ENCORE, Pok.ENCORE_TURNS, 3 * 4 + 0, ["Growl", "Tackle"], 0),
    (VolStatus.DISABLE, Pok.DISABLE_TURNS, 3 * 4 + 1, ["Growl", "Tackle"], 0),
    (VolStatus.TAUNT, Pok.TAUNT_TURNS, 3, ["Growl"], 10),
])
def test_ai_skips_blocked_moves(make_pokemon, make_battle, vol, field, packed, moves, pick):
    """Taunt, Encore and Disable make moves invalid for the AI, Struggle if none is left"""
    me = make_pokemon("Rattata", 20, "Run Away", ["Tackle"])
    opp = make_pokemon("Rattata", 20, "Run Away", moves)
    arr = make_battle([me], [opp])
    ai_pok = pok_slice(arr, 0, opp=True)
    ai_pok[Pok.VOL_STATUS] = vol
    ai_pok[field] = packed
    assert all(return_idx(arr) == pick for _ in range(30))


def test_bound_ai_never_switches(make_pokemon, make_battle):
    """Withdraw checks are skipped while a bind traps the AI's active"""
    me = make_pokemon("Gastly", 20, "Levitate", ["Lick"])
    opp = [make_pokemon("Rattata", 20, "Run Away", ["Tackle", "Quick Attack"]),
           make_pokemon("Pikachu", 20, "Static", ["Thunder Shock"])]
    arr = make_battle([me], opp)
    pok_slice(arr, 0, opp=True)[Pok.VOL_STATUS] = VolStatus.PARTIALLY_TRAPPED
    assert all(return_idx(arr) in (0, 1) for _ in range(30))


# ── Phase 5 side conditions and weather ──────────────────────────────────────

SC = SideCondition


def poke_np(*args):
    """Pokemon array outside a fixture, for the parametrized Basic table"""
    return _p(*args).to_np()


def _basic_field(move, ai_side=0, user_side=0, tspikes=0, bench=1, weather=0,
                 ai_ability="Run Away", user_ability="Sturdy", user_status=0):
    ai_pok = poke_np("Rattata", 20, ai_ability, [move])
    user = poke_np("Geodude", 20, user_ability, ["Tackle"])
    user[Pok.STATUS] = user_status
    ability = getattr(AbilityNames, user_ability.upper().replace(" ", "_"))
    return ai.basic_flag(
        move_slice(ai_pok, 0), ability, ai_pok, user, 1.0, weather, ai_side, user_side,
        tspikes, bench
    )


@pytest.mark.parametrize("move, kwargs, expected", [
    ("Reflect", {}, 0),
    ("Reflect", {"ai_side": SC.REFLECT}, -8),
    ("Light Screen", {"ai_side": SC.LIGHT_SCREEN}, -8),
    ("Light Screen", {"ai_side": SC.REFLECT}, 0),
    ("Mist", {"ai_side": SC.MIST}, -8),
    ("Safeguard", {"ai_side": SC.SAFEGUARD}, -8),
    ("Lucky Chant", {"ai_side": SC.LUCKY_CHANT}, -10),
    ("Toxic Spikes", {"tspikes": 1}, 0),
    ("Toxic Spikes", {"tspikes": 2}, -10),
    ("Toxic Spikes", {"bench": 0}, -10),
    ("Stealth Rock", {}, 0),
    ("Stealth Rock", {"user_side": SC.STEALTH_ROCK}, -10),
    ("Stealth Rock", {"bench": 0}, -10),
    ("Sandstorm", {"weather": Weather.SANDSTORM}, -8),
    ("Sandstorm", {"weather": Weather.RAIN}, 0),
    ("Rain Dance", {"weather": Weather.RAIN}, -8),
    ("Rain Dance", {"user_ability": "Hydration", "user_status": Status.BURN}, -8),
    ("Rain Dance", {"user_ability": "Hydration", "user_status": Status.BURN,
                    "ai_ability": "Swift Swim"}, 0),
])
def test_basic_side_and_weather_moves(move, kwargs, expected):
    """pokeplatinum Basic checks for screens, Mist, Safeguard, Lucky Chant, hazards, weather"""
    assert _basic_field(move, **kwargs) == expected


@pytest.mark.parametrize("move", [
    "Stun Spore", "Confuse Ray", "Will-O-Wisp", "Hypnosis", "Poison Powder", "Yawn"
])
def test_basic_safeguard_blocks_status_moves(move):
    """Safeguard on the target's side scores status, confusion and Yawn -10"""
    assert _basic_field(move) != -10
    assert _basic_field(move, user_side=SC.SAFEGUARD) == -10


def _expert_field(ai_pok, user, my_last_move=0, ai_know=0, user_side=0, weather=0):
    rand = np.zeros((4, 5, 2), dtype=np.int16)
    score = ai.expert_flag(
        ai_pok, user, move_slice(ai_pok, 0), 1, 0, rand, weather, my_last_move, 1.0, 0,
        ai_know, user_side
    )
    queued = [tuple(int(x) for x in rand[0, i]) for i in range(5) if rand[0, i, 1]]
    return score, queued


@pytest.mark.parametrize("move, hp_pct, expected", [
    ("Reflect", 40, (-2, [])),
    ("Reflect", 100, (0, [(1, 128), (1, 192)])),    # no move yet counts as Physical
    ("Reflect", 70, (0, [(1, 192)])),
    ("Light Screen", 100, (0, [(1, 128)])),
])
def test_expert_screens(poke, move, hp_pct, expected):
    """pokeplatinum Expert_Reflect / Expert_LightScreen"""
    ai_pok = poke("Rattata", 20, "Run Away", [move])
    ai_pok[Pok.CURRENT_HP] = ai_pok[Pok.MAX_HP] * hp_pct // 100
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert _expert_field(ai_pok, user) == expected


def test_expert_light_screen_after_a_special_move(poke):
    """The target's last move was special: 75% of +1"""
    ai_pok = poke("Rattata", 20, "Run Away", ["Light Screen"])
    ai_pok[Pok.CURRENT_HP] = ai_pok[Pok.MAX_HP] * 70 // 100
    user = poke("Charmander", 20, "Blaze", ["Ember"])
    last = move_slice(user, 0)[Move.ID]
    assert _expert_field(ai_pok, user, my_last_move=last) == (0, [(1, 192)])


@pytest.mark.parametrize("user_side, expected", [(0, 0), (SC.REFLECT, 1), (SC.LIGHT_SCREEN, 1)])
def test_expert_brick_break(poke, user_side, expected):
    """+1 when the target's side has a screen"""
    ai_pok = poke("Machop", 20, "Guts", ["Brick Break"])
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    assert _expert_field(ai_pok, user, user_side=user_side) == (expected, [])


def test_expert_lucky_chant(poke):
    """-1 under 70% HP, +1 after seeing a high crit move, else 25% of +1"""
    ai_pok = poke("Rattata", 20, "Run Away", ["Lucky Chant"])
    user = poke("Machop", 20, "Guts", ["Tackle", "Karate Chop"])
    assert _expert_field(ai_pok, user) == (0, [(1, 64)])
    assert _expert_field(ai_pok, user, ai_know=Enemy_AI_Knows.MOVE2) == (1, [])
    ai_pok[Pok.CURRENT_HP] = ai_pok[Pok.MAX_HP] // 2
    assert _expert_field(ai_pok, user) == (-1, [])


@pytest.mark.parametrize("move", ["Stealth Rock", "Toxic Spikes"])
@pytest.mark.parametrize("skip, roar, expected", [
    (1, False, (0, [])),
    (0, False, (1, [])),
    (0, True, (1, [(1, 192)])),
])
def test_expert_hazards(monkeypatch, poke, move, skip, roar, expected):
    """50% to skip, else +1 and 75% of another +1 with Roar or Whirlwind"""
    moves = [move, "Roar"] if roar else [move]
    ai_pok = poke("Geodude", 20, "Sturdy", moves)
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    monkeypatch.setattr(ai.random, "getrandbits", lambda k: skip)
    assert _expert_field(ai_pok, user) == expected


@pytest.mark.parametrize("ai_level, ai_ability, hp_pct, weather, expected", [
    (10, "Swift Swim", 100, 0, 1),                 # slower with Swift Swim
    (60, "Swift Swim", 100, 0, 0),
    (60, "Rain Dish", 30, 0, -1),
    (60, "Run Away", 100, Weather.SANDSTORM, 1),
    (60, "Rain Dish", 100, 0, 1),
])
def test_expert_rain_dance(poke, ai_level, ai_ability, hp_pct, weather, expected):
    """pokeplatinum Expert_RainDance"""
    ai_pok = poke("Lotad", ai_level, ai_ability, ["Rain Dance"])
    ai_pok[Pok.CURRENT_HP] = ai_pok[Pok.MAX_HP] * hp_pct // 100
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    assert _expert_field(ai_pok, user, weather=weather) == (expected, [])


@pytest.mark.parametrize("move", ["Mist", "Safeguard", "Sandstorm"])
def test_expert_side_moves_without_a_check(poke, move):
    """No Expert script, and not the always-hit branch either"""
    ai_pok = poke("Rattata", 20, "Run Away", [move])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert _expert_field(ai_pok, user) == (0, [])


@pytest.mark.parametrize("target, ability, expected", [
    ("Geodude", "Sturdy", False), ("Steelix", "Sturdy", True), ("Zubat", "Inner Focus", True),
    ("Geodude", "Poison Heal", True), ("Geodude", "Poison Point", False),
])
def test_basic_poison_only_fails_on_steel_and_poison(target, ability, expected):
    """pokeplatinum Basic poison check: -10 into Steel or Poison types, not the others"""
    ai_pok = poke_np("Rattata", 20, "Run Away", ["Poison Powder"])
    user = poke_np(target, 20, ability, ["Tackle"])
    ab = getattr(AbilityNames, ability.upper().replace(" ", "_"))
    assert ai.basic_move_status(move_slice(ai_pok, 0), ab, user, ai_pok, 0) == expected


# ── Phase 6 switching moves ──────────────────────────────────────────────────

def _basic_switch(move, user_bench=1, ai_bench=1, ai_ability="Run Away", user_ability="Sturdy"):
    ai_pok = poke_np("Rattata", 20, ai_ability, [move])
    user = poke_np("Geodude", 20, user_ability, ["Tackle"])
    ability = getattr(AbilityNames, user_ability.upper().replace(" ", "_"))
    return ai.basic_flag(
        move_slice(ai_pok, 0), ability, ai_pok, user, 1.0, 0, 0, 0, 0, user_bench, ai_bench
    )


@pytest.mark.parametrize("move, kwargs, expected", [
    ("Roar", {}, 0),
    ("Roar", {"user_bench": 0}, -10),
    ("Whirlwind", {"user_ability": "Suction Cups"}, -10),
    ("Whirlwind", {"user_ability": "Suction Cups", "ai_ability": "Mold Breaker"}, 0),
    ("Roar", {"user_ability": "Soundproof"}, -10),
    ("Baton Pass", {}, 0),
    ("Baton Pass", {"ai_bench": 0}, -10),
    ("Teleport", {}, -10),
    ("Pursuit", {}, 0),
])
def test_basic_switching_moves(move, kwargs, expected):
    """pokeplatinum Basic_CheckCanForceSwitch / Basic_CheckBatonPass, Teleport flees"""
    assert _basic_switch(move, **kwargs) == expected


@pytest.mark.parametrize("turns_active, user_side, stage, expected", [
    (5, 0, 0, (0, [(2, 192), (2, 128)])),
    (4, 0, 0, (-3, [])),
    (1, SC.STEALTH_ROCK, 0, (0, [(2, 128)])),
    (1, SC.TOXIC_SPIKES, 0, (0, [(2, 128)])),
    (1, 0, 3, (0, [(2, 128)])),
    (1, 0, 2, (-3, [])),
])
def test_expert_force_switch(poke, turns_active, user_side, stage, expected):
    """pokeplatinum Expert_ForceSwitch, its turn count is TURNS_ACTIVE - 1"""
    ai_pok = poke("Growlithe", 20, "Intimidate", ["Roar"])
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    user[Pok.TURNS_ACTIVE] = turns_active
    user[Pok.SPECIAL_ATTACK_STAT_STAGE] = stage
    assert _expert_field(ai_pok, user, user_side=user_side) == expected


@pytest.mark.parametrize("ai_name, stage, hp_pct, expected", [
    ("Rattata", 3, 60, (0, [(2, 176)])),     # faster, HP <= 60
    ("Rattata", 3, 65, (0, [])),
    ("Geodude", 3, 70, (0, [(2, 176)])),     # slower, HP <= 70
    ("Geodude", 3, 75, (0, [])),
    ("Rattata", 2, 65, (-2, [])),
    ("Rattata", 2, 60, (0, [])),
    ("Geodude", 2, 80, (-2, [])),
    ("Geodude", 2, 60, (0, [])),
    ("Rattata", 0, 100, (-2, [])),
])
def test_expert_baton_pass(poke, ai_name, stage, hp_pct, expected):
    """pokeplatinum Expert_BatonPass as the script runs it"""
    ai_pok = poke(ai_name, 20, "Sturdy", ["Baton Pass"])
    ai_pok[Pok.EVASION_STAT_STAGE] = stage
    ai_pok[Pok.CURRENT_HP] = ai_pok[Pok.MAX_HP] * hp_pct // 100
    user = poke("Machop", 20, "Guts", ["Tackle"])
    assert _expert_field(ai_pok, user) == expected


@pytest.mark.parametrize("turns_active, target, expected", [
    (1, "Geodude", [(1, 128)]),
    (2, "Gastly", [(1, 128)]),
    (2, "Abra", [(1, 128)]),
    (2, "Geodude", []),
])
def test_expert_pursuit(poke, turns_active, target, expected):
    """50% +1 on the AI's first turn, or against a Ghost or Psychic type"""
    ai_pok = poke("Murkrow", 20, "Insomnia", ["Pursuit"])
    ai_pok[Pok.TURNS_ACTIVE] = turns_active
    user = poke(target, 20, "Levitate", ["Tackle"])
    assert _expert_field(ai_pok, user) == (0, expected)


def test_sub_after_death_skips_the_excluded_slot(poke):
    """Baton Pass: the passer is alive but can't be picked"""
    party = np.zeros(6 * POK_LEN, dtype=np.int32)
    party[:POK_LEN] = poke("Machop", 20, "Guts", ["Karate Chop"])
    party[POK_LEN:2 * POK_LEN] = poke("Rattata", 20, "Run Away", ["Tackle"])
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    assert sub_after_death(party, user, party[:POK_LEN], 0, 0, 0) == 1


def test_sub_after_death_scores_full_damage(poke):
    """Phase 2 scores each move at full damage (pokeplatinum BattleAI_PostKOSwitchIn passes
    criticalMul 1, no roll), so the harder hitter wins over party order"""
    party = np.zeros(6 * POK_LEN, dtype=np.int32)
    party[:POK_LEN] = poke("Rattata", 20, "Run Away", ["Tackle"])
    party[POK_LEN:2 * POK_LEN] = poke("Geodude", 20, "Sturdy", ["Rock Slide"])
    dead = poke("Machop", 20, "Guts", ["Karate Chop"])
    dead[Pok.CURRENT_HP] = 0
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    assert sub_after_death(party, user, dead) == 1


@pytest.mark.parametrize("took_dmg", [0, Types.NORMAL])
def test_natural_cure_withdraw_never_picks_the_active(monkeypatch, make_pokemon, make_battle, took_dmg):
    """Asleep with Natural Cure: the AI's best pick is its own active, it sends the bench one"""
    from Models import trainer_ai
    me = make_pokemon("Geodude", 20, "Sturdy", ["Tackle"])
    opp = [make_pokemon("Staryu", 20, "Natural Cure", ["Water Gun"]),
           make_pokemon("Rattata", 20, "Run Away", ["Tackle"])]
    arr = make_battle([me], opp)
    pok_slice(arr, 0, opp=True)[Pok.STATUS] = Status.SLEEP
    pok_slice(arr, 0, opp=True)[Pok.SLEEP_COUNTER] = 3
    arr[Field.AI_TOOK_DMG_LAST_TURN] = took_dmg
    monkeypatch.setattr(trainer_ai.random, "getrandbits", lambda k: 1)
    assert return_idx(arr) == 1 - 6


def test_natural_cure_withdraw_needs_a_bench(monkeypatch, make_pokemon, make_battle):
    """Last Pokemon: no withdraw, it picks a move"""
    from Models import trainer_ai
    me = make_pokemon("Geodude", 20, "Sturdy", ["Tackle"])
    arr = make_battle([me], [make_pokemon("Staryu", 20, "Natural Cure", ["Water Gun"])])
    opp_active(arr)[Pok.STATUS] = Status.SLEEP
    opp_active(arr)[Pok.SLEEP_COUNTER] = 3
    arr[Field.AI_TOOK_DMG_LAST_TURN] = Types.NORMAL
    monkeypatch.setattr(trainer_ai.random, "getrandbits", lambda k: 1)
    assert return_idx(arr) >= 0


# ── Phase 7 healing, items, misc ─────────────────────────────────────────────

def _basic_know(ai_pok, user, ability, ai_know=0):
    return ai.basic_flag(
        move_slice(ai_pok, 0), ability, ai_pok, user, 1.0, 0, 0, 0, 0, 1, 1, ai_know
    )


@pytest.mark.parametrize("move, hp_full, expected", [
    ("Recover", True, -8), ("Recover", False, 0), ("Synthesis", True, -8), ("Synthesis", False, 0),
])
def test_basic_recovery(poke, move, hp_full, expected):
    """Basic_CheckCanRecoverHP: -8 at full HP"""
    ai_pok = poke("Bulbasaur", 20, "Overgrow", [move])
    if not hp_full:
        ai_pok[Pok.CURRENT_HP] -= 1
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert _basic(ai_pok, user, AbilityNames.STURDY) == expected


@pytest.mark.parametrize("status, expected", [
    (0, -10), (Status.SLEEP, -10), (Status.FREEZE, -10), (Status.BURN, 0), (Status.POISON, 0),
    (Status.TOXIC, 0), (Status.PARALYSIS, 0),
])
def test_basic_refresh(poke, status, expected):
    """Basic_CheckCanRefreshStatus: -10 unless burned, poisoned or paralyzed"""
    ai_pok = poke("Rattata", 20, "Run Away", ["Refresh"])
    ai_pok[Pok.STATUS] = status
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert _basic(ai_pok, user, AbilityNames.STURDY) == expected


@pytest.mark.parametrize("item, ability, expected", [
    ("Oran Berry", "STURDY", 0), (None, "STURDY", -10), ("Oran Berry", "STICKY_HOLD", -10),
])
def test_basic_knock_off(poke, item, ability, expected):
    """Basic_CheckCanRemoveItem: -10 against Sticky Hold or a target without an item"""
    ai_pok = poke("Murkrow", 20, "Insomnia", ["Knock Off"])
    user = poke("Machop", 20, "Guts", ["Tackle"], item=item)
    assert _basic(ai_pok, user, getattr(AbilityNames, ability)) == expected


def test_basic_knock_off_keeps_the_immunity_check(poke):
    """It still deals damage, so Wonder Guard's -12 comes before the item check"""
    ai_pok = poke("Murkrow", 20, "Insomnia", ["Knock Off"])
    user = poke("Machop", 20, "Guts", ["Tackle"], item="Oran Berry")
    assert _basic(ai_pok, user, AbilityNames.WONDER_GUARD) == -12


def test_basic_recycle(poke):
    """Basic_CheckCanRecycle: -10 with nothing to recycle"""
    ai_pok = poke("Rattata", 20, "Run Away", ["Recycle"])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert _basic(ai_pok, user, AbilityNames.STURDY) == -10
    ai_pok[Pok.CONSUMED_ITEM] = ItemNames.ORAN_BERRY
    assert _basic(ai_pok, user, AbilityNames.STURDY) == 0


@pytest.mark.parametrize("ability, asleep, ai_know, expected", [
    ("STURDY", False, 0, 0),
    ("TRUANT", False, 0, -10), ("INSOMNIA", False, 0, -10), ("VITAL_SPIRIT", False, 0, -10),
    ("MULTITYPE", False, 0, -10),
    ("STURDY", True, 0, -10),
    ("STURDY", True, Enemy_AI_Knows.MOVE2, 0),    # saw it use Sleep Talk
])
def test_basic_worry_seed(poke, ability, asleep, ai_know, expected):
    """Basic_CheckWorrySeed, the sleep part needs the target seen using Sleep Talk"""
    ai_pok = poke("Bulbasaur", 20, "Overgrow", ["Worry Seed"])
    user = poke("Geodude", 20, "Sturdy", ["Tackle", "Sleep Talk"])
    if asleep:
        user[Pok.STATUS] = Status.SLEEP
    assert _basic_know(ai_pok, user, getattr(AbilityNames, ability), ai_know) == expected


def test_basic_perish_song(poke):
    """Basic_CheckPerishSong: -10 if the target has it, no Soundproof check"""
    ai_pok = poke("Rattata", 20, "Run Away", ["Perish Song"])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert _basic(ai_pok, user, AbilityNames.SOUNDPROOF) == 0
    user[Pok.VOL_STATUS] = VolStatus.PERISH_SONG
    assert _basic(ai_pok, user, AbilityNames.STURDY) == -10


@pytest.mark.parametrize("move, expected", [
    ("Growl", -10), ("Sing", -10), ("Grass Whistle", -10), ("Disarming Voice", 0),
])
def test_basic_soundproof_uses_the_cartridge_list(poke, move, expected):
    """pokeplatinum Basic_SoundproofMoves, not the sound flag"""
    ai_pok = poke("Rattata", 20, "Run Away", [move])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert _basic(ai_pok, user, AbilityNames.SOUNDPROOF) == expected


def _at_pct(pok, pct):
    """HP percent exactly pct, the AI reads only the percent"""
    pok[Pok.MAX_HP] = 100
    pok[Pok.CURRENT_HP] = pct


def _expert_weather(ai_pok, user, weather=0):
    rand = np.zeros((4, 5, 2), dtype=np.int16)
    score = ai.expert_flag(ai_pok, user, move_slice(ai_pok, 0), 1, 0, rand, weather, 0, 1.0, 0)
    queued = [tuple(int(x) for x in rand[0, i]) for i in range(5) if rand[0, i, 1]]
    return score, queued


@pytest.mark.parametrize("move, weather, ai_lv, hp_pct, roll, expected", [
    ("Recover", 0, 10, 100, 0, (-3, [])),
    ("Recover", 0, 40, 50, 0, (-8, [])),          # moves first
    ("Recover", 0, 10, 80, 30, (-3, [])),         # over 69%, the 226/256 -3
    ("Recover", 0, 10, 80, 29, (0, [(2, 236)])),
    ("Recover", 0, 10, 60, 255, (0, [(2, 236)])),
    ("Synthesis", Weather.RAIN, 10, 60, 0, (-2, [(2, 236)])),
    ("Synthesis", Weather.SUN, 10, 60, 0, (0, [(2, 236)])),
    ("Synthesis", Weather.SANDSTORM, 10, 100, 0, (-5, [])),
])
def test_expert_recovery(monkeypatch, poke, move, weather, ai_lv, hp_pct, roll, expected):
    """Expert_Recovery and Expert_Synthesis"""
    monkeypatch.setattr(ai.random, "getrandbits", lambda k: roll if k == 8 else 0)
    ai_pok = poke("Bulbasaur", ai_lv, "Overgrow", [move])
    _at_pct(ai_pok, hp_pct)
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert _expert_weather(ai_pok, user, weather) == expected


@pytest.mark.parametrize("hp_pct, expected", [(49, -1), (50, 0)])
def test_expert_refresh(poke, hp_pct, expected):
    """Expert_Refresh: -1 when the target is under 50%"""
    ai_pok = poke("Rattata", 20, "Run Away", ["Refresh"])
    user = poke("Machop", 20, "Guts", ["Tackle"])
    _at_pct(user, hp_pct)
    assert _expert(ai_pok, user) == (expected, [])


@pytest.mark.parametrize("hp_pct, turns_active, expected", [
    (100, 2, [(1, 76)]), (100, 1, []), (29, 2, []), (30, 2, [(1, 76)]),
])
def test_expert_knock_off(poke, hp_pct, turns_active, expected):
    """Expert_KnockOff: 76/256 +1 against 30% or more, not on the AI's first turn"""
    ai_pok = poke("Murkrow", 20, "Insomnia", ["Knock Off"])
    ai_pok[Pok.TURNS_ACTIVE] = turns_active
    user = poke("Machop", 20, "Guts", ["Tackle"])
    _at_pct(user, hp_pct)
    assert _expert(ai_pok, user) == (0, expected)


@pytest.mark.parametrize("item, expected", [
    ("LUM_BERRY", (0, [(1, 206)])), ("CHESTO_BERRY", (0, [(1, 206)])), ("ORAN_BERRY", (-2, [])),
    (None, (-2, [])),
])
def test_expert_recycle(poke, item, expected):
    """Expert_Recycle likes a Chesto or Lum Berry"""
    ai_pok = poke("Rattata", 20, "Run Away", ["Recycle"])
    ai_pok[Pok.CONSUMED_ITEM] = getattr(ItemNames, item) if item else 0
    user = poke("Machop", 20, "Guts", ["Tackle"])
    assert _expert(ai_pok, user) == expected


@pytest.mark.parametrize("hp_pct, expected", [(50, [(1, 128), (1, 192)]), (49, [(1, 192)])])
def test_expert_worry_seed(poke, hp_pct, expected):
    """Pokemow Worry Seed: 50% +1 with the target over 49%, then 192/256 +1"""
    ai_pok = poke("Bulbasaur", 20, "Overgrow", ["Worry Seed"])
    user = poke("Machop", 20, "Guts", ["Tackle"])
    _at_pct(user, hp_pct)
    assert _expert(ai_pok, user) == (0, expected)


@pytest.mark.parametrize("move", ["Perish Song", "Splash"])
def test_expert_perish_song_and_splash_score_nothing(poke, move):
    """No Expert check, they don't fall into the always-hit branch"""
    ai_pok = poke("Rattata", 20, "Run Away", [move])
    ai_pok[Pok.ACCURACY_STAT_STAGE] = -6
    user = poke("Machop", 20, "Guts", ["Tackle"])
    assert _expert(ai_pok, user) == (0, [])


def test_wearing_down_counts_perish_song(poke):
    """Expert Protect and Feint treat Perish Song like Toxic or Curse"""
    p = poke("Machop", 20, "Guts", ["Tackle"])
    assert not ai.wearing_down(p)
    p[Pok.VOL_STATUS] = VolStatus.PERISH_SONG
    assert ai.wearing_down(p)


def test_expert_binding_move_vs_perish_song(poke):
    """Expert_BindingMove: 50% +1 against a target under Perish Song"""
    ai_pok = poke("Rattata", 20, "Run Away", ["Wrap"])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    user[Pok.VOL_STATUS] = VolStatus.PERISH_SONG
    assert _expert(ai_pok, user) == (0, [(1, 128)])


def _perish_ai(make_pokemon, make_battle, turns, bench=True, vol=0):
    me = make_pokemon("Geodude", 20, "Sturdy", ["Tackle"])
    opp = [make_pokemon("Machop", 20, "Guts", ["Karate Chop"])]
    if bench:
        opp.append(make_pokemon("Rattata", 20, "Run Away", ["Tackle"]))
    arr = make_battle([me], opp)
    active = opp_active(arr)
    active[Pok.VOL_STATUS] = VolStatus.PERISH_SONG | vol
    active[Pok.PERISH_TURNS] = turns
    return arr


def test_ai_withdraws_on_perish_count_zero(make_pokemon, make_battle):
    """Withdraw 1: the count is 0, it faints this turn, so it switches to the post-KO pick"""
    arr = _perish_ai(make_pokemon, make_battle, 0)
    assert return_idx(arr) == 1 - 6


@pytest.mark.parametrize("turns, bench, vol", [
    (1, True, 0), (0, False, 0), (0, True, VolStatus.INGRAIN),
])
def test_ai_perish_withdraw_needs_count_zero_a_bench_and_freedom(
        make_pokemon, make_battle, turns, bench, vol):
    """A count left, no bench or rooted by Ingrain: it picks a move"""
    arr = _perish_ai(make_pokemon, make_battle, turns, bench, vol)
    assert return_idx(arr) >= 0


# ── Phase 8 move-calling ─────────────────────────────────────────────────────

@pytest.mark.parametrize("turn, expected", [(1, -10), (2, 0)])
def test_basic_copycat(poke, turn, expected):
    """Basic_CheckCopycat as Pokemow has it: -10 on the battle's first turn"""
    ai_pok = poke("Togepi", 20, "Hustle", ["Copycat"])
    user = poke("Machop", 20, "Guts", ["Tackle"])
    assert ai.basic_flag(
        move_slice(ai_pok, 0), AbilityNames.GUTS, ai_pok, user, 1.0, 0, 0, 0, 0, 1, 1, 0, turn
    ) == expected


@pytest.mark.parametrize("ai_lv, last, expected", [
    (40, "Hypnosis", [(2, 128)]),    # faster, last move on the list
    (5, "Hypnosis", []),             # slower, on the list
    (40, "Tackle", [(-1, 176)]),
    (5, None, [(-1, 176)]),          # no move yet
])
def test_expert_mirror_move(poke, ai_lv, last, expected):
    """Expert_MirrorMove reads the target's last move"""
    ai_pok = poke("Pidgey", ai_lv, "Keen Eye", ["Mirror Move"])
    user = poke("Machop", 20, "Guts", ["Tackle", "Hypnosis"])
    if last:
        user[Pok.LAST_MOVE_ID] = getattr(MoveName, last.upper())
    assert _expert(ai_pok, user) == (0, expected)


def _expert_copycat(ai_pok, user, beats):
    rand = np.zeros((4, 5, 2), dtype=np.int16)
    score = ai.expert_flag(
        ai_pok, user, move_slice(ai_pok, 0), 1, 0, rand, 0, 0, 1.0, 0, 0, 0, beats
    )
    return score, [tuple(int(x) for x in rand[0, i]) for i in range(5) if rand[0, i, 1]]


@pytest.mark.parametrize("ai_lv, beats, last, expected", [
    (40, True, "Tackle", [(2, 224)]),
    (5, True, "Tackle", []),
    (40, False, "Hypnosis", [(2, 128)]),
    (5, False, "Hypnosis", []),
    (40, False, "Tackle", [(-1, 176)]),
    (5, False, "Tackle", [(-1, 176)]),
])
def test_expert_copycat(poke, ai_lv, beats, last, expected):
    """Expert_Copycat: out-damaging the AI or an encouraged last move"""
    ai_pok = poke("Togepi", ai_lv, "Hustle", ["Copycat"])
    user = poke("Machop", 20, "Guts", ["Tackle", "Hypnosis"])
    user[Pok.LAST_MOVE_ID] = getattr(MoveName, last.upper())
    assert _expert_copycat(ai_pok, user, beats) == (0, expected)


def test_copycat_beats(poke):
    """The target's strong last move beats the AI's only weak attack, a status move never does"""
    from Models.trainer_ai import copycat_beats
    ai_pok = poke("Togepi", 10, "Hustle", ["Copycat", "Pound"])
    user = poke("Machop", 30, "Guts", ["Karate Chop", "Leer"])
    assert not copycat_beats(ai_pok, user, 0, 0)
    user[Pok.LAST_MOVE_ID] = MoveName.KARATE_CHOP
    assert copycat_beats(ai_pok, user, 0, 0)
    user[Pok.LAST_MOVE_ID] = MoveName.LEER
    assert not copycat_beats(ai_pok, user, 0, 0)


@pytest.mark.parametrize("move", ["Metronome", "Nature Power"])
def test_expert_metronome_and_nature_power_score_nothing(poke, move):
    """No Expert check, they don't fall into the always-hit branch"""
    ai_pok = poke("Munchlax", 20, "Thick Fat", [move])
    ai_pok[Pok.ACCURACY_STAT_STAGE] = -6
    user = poke("Machop", 20, "Guts", ["Tackle"])
    assert _expert(ai_pok, user) == (0, [])


@pytest.mark.parametrize("check", ["check_immunity_pty", "check_resistance_pty"])
def test_nobody_is_immune_to_or_resists_struggle(poke, check):
    """Gen IV gives Struggle no effectiveness, a Ghost on the bench isn't immune to it"""
    party = np.zeros(6 * POK_LEN, dtype=np.int32)
    party[:POK_LEN] = poke("Machop", 20, "Guts", ["Karate Chop"])
    party[POK_LEN:2 * POK_LEN] = poke("Gastly", 20, "Levitate", ["Lick"])
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    assert getattr(ai, check)(party, user, Types.TYPELESS, 0).size == 0


def test_ai_survives_my_struggle(make_pokemon, make_battle):
    """My Struggle hit the AI last turn, its withdraw checks still run"""
    arr = make_battle([make_pokemon("Rattata", 20, "Run Away", ["Tackle"])],
                      [make_pokemon("Machop", 20, "Guts", ["Leer"]),
                       make_pokemon("Gastly", 20, "Levitate", ["Lick"])])
    arr[Field.AI_TOOK_DMG_LAST_TURN] = Types.TYPELESS
    for _ in range(20):
        assert return_idx(arr) in (0, -5)


@pytest.mark.parametrize("target, weather, expected", [
    ("Geodude", 0, (0, [])),
    ("Geodude", Weather.HAIL, (1, [])),
    ("Squirtle", Weather.HAIL, (0, [(-3, 206)])),    # resisted: the roll ends it
])
def test_expert_blizzard(poke, target, weather, expected):
    """Pokemow Expert Blizzard"""
    ai_pok = poke("Rattata", 20, "Run Away", ["Blizzard"])
    user = poke(target, 20, "Sturdy", ["Tackle"])
    eff = 0.5 if target == "Squirtle" else 1.0
    assert _expert_weather_eff(ai_pok, user, weather, eff) == expected


def _expert_weather_eff(ai_pok, user, weather, effectiveness):
    rand = np.zeros((4, 5, 2), dtype=np.int16)
    score = ai.expert_flag(
        ai_pok, user, move_slice(ai_pok, 0), 1, 0, rand, weather, 0, effectiveness, 0
    )
    return score, [tuple(int(x) for x in rand[0, i]) for i in range(5) if rand[0, i, 1]]


# ── Dig, Gravity, Minimize ───────────────────────────────────────────────────

@pytest.mark.parametrize("setup, ai_level, expected", [
    ("power_herb", 20, (2, [])),
    (None, 50, (0, [(1, 176)])),            # AI faster
    (None, 5, (0, [])),                     # AI slower
])
def test_expert_dig_is_charge_turn_with_invuln(make_pokemon, poke, setup, ai_level, expected):
    """Dig goes to pokeplatinum Expert_ChargeTurnWithInvuln like Bounce"""
    item = "Power Herb" if setup == "power_herb" else None
    ai_pok = make_pokemon("Diglett", ai_level, "Sand Veil", ["Dig"], item=item).to_np()
    user = poke("Rattata", 30, "Run Away", ["Tackle"])
    assert _expert(ai_pok, user) == expected


@pytest.mark.parametrize("gravity, expected", [(False, 0), (True, -10)])
def test_basic_gravity_already_active(poke, gravity, expected):
    """pokeplatinum Basic_CheckGravityActive"""
    ai_pok = poke("Abra", 20, "Synchronize", ["Gravity"])
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    score = ai.basic_flag(
        move_slice(ai_pok, 0), AbilityNames.RUN_AWAY, ai_pok, user, 1.0, 0, gravity=gravity
    )
    assert score == expected


@pytest.mark.parametrize("target, ai_hp, expected", [
    ("Pidgey", 100, (0, [(1, 192)])),       # Flying: 75%
    ("Rattata", 60, (0, [(1, 96)])),        # HP >= 60%: 37.5%
    ("Rattata", 59, (0, [])),
])
def test_expert_gravity(poke, target, ai_hp, expected):
    """pokeplatinum Expert_Gravity"""
    ai_pok = poke("Abra", 20, "Synchronize", ["Gravity"])
    ai_pok[Pok.MAX_HP], ai_pok[Pok.CURRENT_HP] = 100, ai_hp
    user = poke(target, 20, "Keen Eye" if target == "Pidgey" else "Run Away", ["Tackle"])
    assert _expert(ai_pok, user) == expected


def test_ai_never_picks_a_move_gravity_blocks(make_pokemon, make_battle):
    """Under Gravity the AI scores Splash like a move with no PP"""
    me = make_pokemon("Geodude", 20, "Sturdy", ["Tackle"])
    opp = make_pokemon("Magikarp", 20, "Swift Swim", ["Splash", "Tackle"])
    arr = make_battle([me], [opp])
    arr[Field.GRAVITY_TURNS] = 3
    for _ in range(20):
        assert return_idx(arr) == 1


@pytest.mark.parametrize("gravity", [False, True])
def test_party_checks_see_gravity(poke, gravity):
    """pokeplatinum ApplyTypeChart and CalcEffectiveness drop Ground's Flying immunity under
    Gravity: a Flying bench member stops being immune, Ground hits a Rock/Flying target"""
    party = np.zeros(6 * POK_LEN, dtype=np.int32)
    party[:POK_LEN] = poke("Machop", 20, "Guts", ["Karate Chop"])
    party[POK_LEN:2 * POK_LEN] = poke("Pidgey", 20, "Keen Eye", ["Ember"])
    party[2 * POK_LEN:3 * POK_LEN] = poke("Geodude", 20, "Sturdy", ["Earthquake"])
    steel = poke("Skarmory", 20, "Keen Eye", ["Peck"])
    immune = list(ai.check_immunity_pty(party, steel, Types.GROUND, 0, gravity))
    assert immune == ([] if gravity else [1])
    aerodactyl = poke("Aerodactyl", 40, "Rock Head", ["Bite"])
    assert (2 in ai.check_super_ef_move_pty(party, aerodactyl, 0, gravity)) == gravity



# ── Explosion / Selfdestruct ─────────────────────────────────────────────────

@pytest.mark.parametrize("kwargs, expected", [
    ({}, 0),
    ({"user_ability": "Damp"}, -10),
    ({"user_ability": "Damp", "ai_ability": "Mold Breaker"}, 0),
    ({"ai_bench": 0}, -10),
    ({"ai_bench": 0, "user_bench": 0}, -1),
])
def test_basic_explosion(kwargs, expected):
    """pokeplatinum Basic_CheckCannotExplode: Damp, then the AI's last Pokemon"""
    assert _basic_switch("Explosion", **kwargs) == expected


@pytest.mark.parametrize("hp_pct, evasion, faster, expected", [
    (100, 0, True, (0, [(-3, 206)])),
    (100, 0, False, (0, [(-1, 206)])),
    (60, 0, True, (0, [(-1, 206)])),
    (40, 0, True, (0, [(1, 128)])),
    (30, 0, True, (0, [(1, 128), (1, 206)])),
    (100, 1, True, (-1, [(-3, 206)])),
    (100, 4, True, (-1, [(-1, 128), (-3, 206)])),
])
def test_expert_explosion(poke, hp_pct, evasion, faster, expected):
    """pokeplatinum Expert_Explosion: evasion, then the user's HP and speed"""
    ai_pok = poke("Geodude", 20, "Sturdy", ["Selfdestruct"])
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    ai_pok[Pok.CURRENT_HP] = ai_pok[Pok.MAX_HP] * hp_pct // 100
    if ai_pok[Pok.CURRENT_HP] * 100 // ai_pok[Pok.MAX_HP] != hp_pct:
        ai_pok[Pok.MAX_HP] = 100
        ai_pok[Pok.CURRENT_HP] = hp_pct
    user[Pok.EVASION_STAT_STAGE] = evasion
    ai_pok[Pok.SPEED], user[Pok.SPEED] = (200, 10) if faster else (10, 200)
    assert _expert(ai_pok, user) == expected



# ── OHKO moves ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ai_lv, ai_ability, user_ability, expected", [
    (20, "Run Away", "Run Away", 0),
    (19, "Run Away", "Run Away", -10),
    (20, "Run Away", "Sturdy", -10),
    (20, "Mold Breaker", "Sturdy", 0),
    (19, "Mold Breaker", "Sturdy", -10),
])
def test_basic_ohko(ai_lv, ai_ability, user_ability, expected):
    """pokeplatinum Basic_CheckOHKOWouldFail: Sturdy unless Mold Breaker, then a lower level"""
    ai_pok = poke_np("Rattata", ai_lv, ai_ability, ["Guillotine"])
    user = poke_np("Geodude", 20, user_ability, ["Tackle"])
    ability = getattr(AbilityNames, user_ability.upper().replace(" ", "_"))
    assert ai.basic_flag(move_slice(ai_pok, 0), ability, ai_pok, user, 1.0, 0) == expected


def test_basic_ohko_immune():
    """Fissure into a Flying type is the generic immunity -10"""
    ai_pok = poke_np("Geodude", 50, "Sturdy", ["Fissure"])
    user = poke_np("Pidgey", 20, "Keen Eye", ["Tackle"])
    assert ai.basic_flag(move_slice(ai_pok, 0), AbilityNames.KEEN_EYE, ai_pok, user, 0.0, 0) == -10


@pytest.mark.parametrize("move", ["Fissure", "Guillotine", "Sheer Cold"])
def test_expert_ohko(move):
    """pokeplatinum Expert_OHKOMove: a 25% chance of +1"""
    ai_pok = poke_np("Rattata", 20, "Run Away", [move])
    user = poke_np("Rattata", 20, "Run Away", ["Tackle"])
    assert _expert(ai_pok, user) == (0, [(1, 64)])


def test_ohko_never_counts_as_the_best_damage(make_pokemon, make_battle):
    """Guillotine is in MOVE_EXCEP, so its power 0 chip never counts as a kill: into a 1 HP
    target only Tackle gets the kill bonus"""
    ai_pok = make_pokemon("Rattata", 50, "Run Away", ["Guillotine", "Tackle"])
    user = make_pokemon("Rattata", 5, "Run Away", ["Tackle"])
    assert MoveName.GUILLOTINE in MOVE_EXCEP
    arr = make_battle([user], [ai_pok])
    arr[Pok.CURRENT_HP] = 1
    picks = {int(return_idx(arr)) for _ in range(40)}
    assert picks == {1}
