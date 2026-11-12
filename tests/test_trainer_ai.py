"""Trainer AI: which expert-flag evaluation a status move is scored by, and that the AI can
pick a move with any implemented status move in its kit"""
import random
import numpy as np
import pytest
from Models import trainer_ai_helper as ai
from Engine import engine_helper
from Models.trainer_ai import return_idx, sub_after_death, MOVE_EXCEP, bench_deals_more
from Models.idx_const import Pok, Move, POK_LEN, Field, Item
from Models.helper import (
    VolStatus, VolStatus2, Status, Types, Enemy_AI_Knows, SideCondition, Weather
)
from DataBase.AbilitiesDB import AbilityNames
from DataBase.ItemDB import ItemNames
from DataBase.MoveDB import MoveName
from battle_driver import move_slice, pok_slice, _p, opp_active, my_active

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
    "Hypnosis", "Will-O-Wisp", "Confuse Ray", "Supersonic", "Trick", "Switcheroo", "Embargo",
    "Pain Split", "Swords Dance", "Calm Mind", "Cosmic Power", "Acid Armor", "Tail Glow", "Sharpen",
    "Defend Order", "Feather Dance", "Metal Sound", "Cotton Spore", "Dragon Dance", "Belly Drum",
    "Acupressure", "Captivate", "Haze", "Psych Up", "Power Swap", "Guard Swap", "Heart Swap",
    "Power Trick",
    "Toxic", "Glare", "Spore", "Lovely Kiss", "Dark Void", "Poison Gas", "Teeter Dance", "Rest",
    "Sleep Talk", "Nightmare", "Psycho Shift", "Heal Bell", "Aromatherapy",
    "Milk Drink", "Soft-Boiled", "Slack Off", "Heal Order", "Moonlight", "Morning Sun", "Roost",
    "Heal Block", "Sunny Day", "Hail", "Tailwind", "Trick Room", "Spikes", "Defog", "Magnet Rise",
    "Wish", "Stockpile", "Swallow", "Memento", "Healing Wish", "Grudge", "Torment", "Imprison", "Spite",
    "Mean Look", "Block", "Spider Web", "Lock-On", "Mind Reader", "Miracle Eye",
)
KIT_DAMAGE = (
    "Seismic Toss", "Night Shade", "Psywave", "Low Kick", "Magnitude", "Hidden Power",
    "Natural Gift", "Mirror Coat", "Assurance", "Take Down", "Bounce", "Fury Cutter", "Rollout",
    "Explosion", "Selfdestruct", "Fissure", "Guillotine", "Sheer Cold", "Thief", "Pluck", "Fling",
    "Fire Blast", "Flamethrower", "Heat Wave", "Lava Plume", "Blaze Kick", "Sacred Fire", "Scald",
    "Thunderbolt", "Discharge", "Zap Cannon", "Body Slam", "Sludge", "Sludge Bomb", "Gunk Shot",
    "Poison Jab", "Cross Poison", "Poison Tail", "Ice Punch", "Dizzy Punch", "Dynamic Punch",
    "Signal Beam", "Rock Climb", "Chatter", "Dark Pulse", "Dragon Rush", "Icicle Crash", "Needle Arm",
    "Rolling Kick", "Waterfall", "Ice Fang", "Thunder Fang", "Magma Storm",
    "Bug Buzz", "Crunch", "Crush Claw", "Earth Power", "Energy Ball", "Flash Cannon", "Focus Blast",
    "Iron Tail", "Mirror Shot", "Moonblast", "Muddy Water", "Octazooka", "Play Rough", "Psychic",
    "Rock Smash", "Shadow Ball", "Seed Flare", "Charge Beam", "Meteor Mash", "Steel Wing",
    "Ancient Power", "Ominous Wind", "Close Combat", "Superpower", "Hammer Arm", "Overheat",
    "Draco Meteor", "Leaf Storm", "Psycho Boost",
    "Aqua Tail", "Cut", "Dazzling Gleam", "Dragon Claw", "Dragon Pulse", "Drill Peck", "Egg Bomb",
    "Hyper Voice", "Judgment", "Mega Kick", "Mega Punch", "Megahorn", "Pay Day", "Power Gem",
    "Power Whip", "Strength", "X-Scissor", "Slash", "Night Slash", "Psycho Cut", "Cross Chop",
    "Stone Edge", "Leaf Blade", "Shadow Claw", "Crabhammer", "Drill Run", "Attack Order",
    "Aeroblast", "Spacial Rend", "Bullet Punch", "Ice Shard", "Shadow Sneak", "Vacuum Wave",
    "Aura Sphere", "Magnet Bomb", "Shadow Punch", "Vital Throw", "Bone Rush", "Icicle Spear",
    "Spike Cannon", "Double Hit", "Bonemerang", "Double-Edge", "Brave Bird", "Wood Hammer",
    "Head Smash", "Wild Charge", "Flare Blitz", "Giga Drain", "Leech Life", "Drain Punch",
    "Sonic Boom", "Hyper Beam", "Giga Impact", "Blast Burn", "Hydro Cannon", "Frenzy Plant", "Roar of Time",
    "Rock Wrecker", "Solar Beam", "Skull Bash", "Sky Attack", "Razor Wind",
    "Fly", "Dive", "Shadow Force", "Sky Uppercut", "Surf", "Thunder", "Hurricane",
    "Thrash", "Outrage", "Petal Dance", "Jump Kick", "High Jump Kick",
    "Eruption", "Water Spout", "Wring Out", "Crush Grip", "Reversal", "Punishment", "Trump Card",
    "Facade", "Grass Knot", "Smelling Salts", "Wake-Up Slap", "Present", "Triple Kick", "Beat Up",
    "Return", "Frustration", "Last Resort", "Secret Power",
    "Super Fang", "Endeavor", "Metal Burst", "False Swipe",
    "Avalanche", "Revenge", "Payback", "Sucker Punch", "Focus Punch",
    "Snore", "Dream Eater", "Weather Ball", "Future Sight", "Doom Desire", "Spit Up", "U-turn",
)
KIT_VOLATILE = (
    "Protect", "Endure", "Feint", "Foresight", "Odor Sleuth", "Mud Sport", "Water Sport",
    "Ingrain", "Aqua Ring", "Attract", "Leech Seed", "Charge", "Destiny Bond", "Yawn", "Rage",
    "Helping Hand", "Follow Me", "Dig", "Gravity", "Minimize", "Substitute", "Detect",
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


@pytest.mark.parametrize("move", [
    "Karate Chop", "Razor Leaf", "Air Cutter", "Blaze Kick", "Cross Poison", "Poison Tail",
    "Cut", "Slash", "Night Slash", "Psycho Cut", "Cross Chop", "Stone Edge", "Leaf Blade",
    "Shadow Claw", "Crabhammer", "Drill Run", "Attack Order", "Aeroblast", "Spacial Rend",
])
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


def _expert_at(poke, move, fast, hp_pct):
    """A faster or slower AI at that HP percent, and its target"""
    ai_pok = poke("Pikachu", 60, "Static", [move]) if fast else poke("Geodude", 10, "Sturdy", [move])
    ai_pok[Pok.MAX_HP] = 100
    ai_pok[Pok.CURRENT_HP] = hp_pct
    return ai_pok, poke("Rattata", 30, "Run Away", ["Tackle"])


@pytest.mark.parametrize("move", ["Close Combat", "Overheat", "Draco Meteor", "Leaf Storm", "Psycho Boost"])
@pytest.mark.parametrize("fast, hp_pct, effectiveness, expected", [
    (True, 100, 0.5, -1), (False, 100, 0.0, -1),   # resisted or immune
    (True, 61, 1.0, 0), (True, 60, 1.0, -1),       # faster: 60% or less
    (False, 81, 1.0, 0), (False, 80, 1.0, -1),     # slower: 80% or less
])
def test_expert_close_combat_and_overheat(poke, move, fast, hp_pct, effectiveness, expected):
    """pokeplatinum Expert_CloseCombat and Expert_Overheat, the same check"""
    ai_pok, user = _expert_at(poke, move, fast, hp_pct)
    assert _expert(ai_pok, user, effectiveness) == (expected, [])


@pytest.mark.parametrize("fast, hp_pct, queued", [
    (False, 10, []),                                 # slower: no change
    (True, 61, []),                                  # above 60%
    (True, 60, [(-1, 61)]), (True, 40, [(-1, 61)]),  # 76/256 * 206/256 = 23.9%
    (True, 39, [(-1, 206)]),                         # below 40%: 80.5%
])
def test_expert_vital_throw(poke, fast, hp_pct, queued):
    """pokeplatinum Expert_VitalThrow, which never reaches the never-miss branch"""
    ai_pok, user = _expert_at(poke, "Vital Throw", fast, hp_pct)
    ai_pok[Pok.ACCURACY_STAT_STAGE] = -5
    assert _expert(ai_pok, user) == (0, queued)


@pytest.mark.parametrize("fast, hp_pct, effectiveness, atk_stage, expected", [
    (True, 10, 0.5, 0, -1), (True, 10, 1.0, -1, -1),   # resisted, Attack below 0
    (True, 41, 1.0, 0, -1), (True, 40, 1.0, 0, 0),     # faster: above 40%
    (False, 60, 1.0, 0, -1), (False, 59, 1.0, 0, 0),   # slower: 60% or more
])
def test_expert_superpower(poke, fast, hp_pct, effectiveness, atk_stage, expected):
    """pokeplatinum Expert_Superpower"""
    ai_pok, user = _expert_at(poke, "Superpower", fast, hp_pct)
    ai_pok[Pok.ATTACK_STAT_STAGE] = atk_stage
    assert _expert(ai_pok, user, effectiveness) == (expected, [])


RECHARGE_MOVES = (
    "Hyper Beam", "Giga Impact", "Blast Burn", "Hydro Cannon", "Frenzy Plant", "Roar of Time", "Rock Wrecker",
)


@pytest.mark.parametrize("move", RECHARGE_MOVES)
@pytest.mark.parametrize("fast, hp_pct, effectiveness, expected", [
    (True, 10, 0.5, -1), (False, 10, 0.0, -1),      # resisted or immune
    (True, 41, 1.0, -1), (True, 40, 1.0, 0),        # faster: above 40%
    (False, 60, 2.0, -1), (False, 59, 1.0, 0),      # slower: 60% or more
])
def test_expert_recharge(poke, move, fast, hp_pct, effectiveness, expected):
    """pokeplatinum Expert_RechargeTurn"""
    ai_pok, user = _expert_at(poke, move, fast, hp_pct)
    assert _expert(ai_pok, user, effectiveness) == (expected, [])


@pytest.mark.parametrize("effectiveness, expected", [(1.0, (0, [(1, 176)])), (0.5, (-1, []))])
def test_expert_recharge_truant(poke, effectiveness, expected):
    """A Truant user skips the HP checks: 68.75% of +1, unless the move is resisted"""
    ai_pok, user = _expert_at(poke, "Giga Impact", True, 100)
    ai_pok[Pok.AB_ID] = AbilityNames.TRUANT
    assert _expert(ai_pok, user, effectiveness) == expected


@pytest.mark.parametrize("fast, effectiveness, expected", [
    (False, 0.5, -1), (True, 0.25, -1), (False, 1.0, 1), (True, 2.0, 0),
])
def test_expert_hammer_arm(poke, fast, effectiveness, expected):
    """pokeplatinum Expert_HammerArm: -1 if resisted, +1 if slower"""
    ai_pok, user = _expert_at(poke, "Hammer Arm", fast, 100)
    assert _expert(ai_pok, user, effectiveness) == (expected, [])


def test_expert_speed_down_only_named_moves(poke):
    """Other speed-lowering attacks (Bubble Beam) aren't scored by the speed-down check"""
    ai_pok = poke("Geodude", 10, "Sturdy", ["Bubble Beam"])
    user = poke("Rattata", 30, "Run Away", ["Tackle"])
    assert _expert(ai_pok, user) == (0, [])


@pytest.mark.parametrize("move", [
    "Aerial Ace", "Feint Attack", "Magical Leaf", "Swift", "Shock Wave", "Aura Sphere", "Magnet Bomb",
    "Shadow Punch",
])
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


@pytest.mark.parametrize("move, first, second", [
    ("Cosmic Power", Pok.DEFENSE_STAT_STAGE, Pok.SPECIAL_DEFENSE_STAT_STAGE),
    ("Defend Order", Pok.DEFENSE_STAT_STAGE, Pok.SPECIAL_DEFENSE_STAT_STAGE),
    ("Calm Mind", Pok.SPECIAL_ATTACK_STAT_STAGE, Pok.SPECIAL_DEFENSE_STAT_STAGE),
    ("Dragon Dance", Pok.ATTACK_STAT_STAGE, Pok.SPEED_STAT_STAGE),
])
@pytest.mark.parametrize("ai_ability, stages, expected", [
    ("Guts", {}, 0),
    ("Guts", {"first": 6}, -10),
    ("Guts", {"second": 6}, -8),
    ("Guts", {"first": 5, "second": 5}, 0),
    ("Simple", {"first": 3}, -10),
    ("Simple", {"second": 3}, -10),
    ("Simple", {"second": 2}, 0),
])
def test_basic_two_stat_boosts(poke, move, first, second, ai_ability, stages, expected):
    """pokeplatinum Basic_CheckCosmicPower / CalmMind / DragonDance, like Bulk Up"""
    ai_pok = poke("Machop", 20, ai_ability, [move])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    for key, val in stages.items():
        ai_pok[first if key == "first" else second] = val
    assert _basic(ai_pok, user, AbilityNames.STURDY) == expected


@pytest.mark.parametrize("move, stage, expected", [
    ("Swords Dance", Pok.ATTACK_STAT_STAGE, -10), ("Sharpen", Pok.ATTACK_STAT_STAGE, -10),
    ("Acid Armor", Pok.DEFENSE_STAT_STAGE, -10), ("Tail Glow", Pok.SPECIAL_ATTACK_STAT_STAGE, -10),
])
def test_basic_high_stat_stage_new_moves(poke, move, stage, expected):
    """pokeplatinum Basic_CheckHighStatStage_*: -10 at +6"""
    ai_pok = poke("Machop", 20, "Guts", [move])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert _basic(ai_pok, user, AbilityNames.STURDY) == 0
    ai_pok[stage] = 6
    assert _basic(ai_pok, user, AbilityNames.STURDY) == expected


@pytest.mark.parametrize("move, target_ability, stage, expected", [
    ("Feather Dance", "Hyper Cutter", None, -10), ("Feather Dance", "Sturdy", Pok.ATTACK_STAT_STAGE, -10),
    ("Metal Sound", "Soundproof", None, -10), ("Metal Sound", "Sturdy", Pok.SPECIAL_DEFENSE_STAT_STAGE, -10),
    ("Cotton Spore", "Speed Boost", None, -10), ("Cotton Spore", "Sturdy", Pok.SPEED_STAT_STAGE, -10),
    ("Feather Dance", "Sturdy", None, 0), ("Metal Sound", "Sturdy", None, 0),
    ("Cotton Spore", "Sturdy", None, 0),
])
def test_basic_new_stat_drops(poke, move, target_ability, stage, expected):
    """Basic_CheckLowStatStage_* for Feather Dance, Metal Sound, Cotton Spore; Metal Sound is on
    Basic_SoundproofMoves"""
    ai_pok = poke("Rattata", 20, "Run Away", [move])
    user = poke("Geodude", 20, target_ability, ["Tackle"])
    if stage is not None:
        user[stage] = -6
    ability = getattr(AbilityNames, target_ability.upper().replace(" ", "_"))
    assert _basic(ai_pok, user, ability) == expected


@pytest.mark.parametrize("move", ["Cosmic Power", "Defend Order", "Calm Mind"])
def test_expert_def_spdef_moves_score_as_spdef_up(poke, move):
    """pokeplatinum sends DEF_SPD_UP and SP_ATK_SP_DEF_UP to Expert_StatusSpDefenseUp: at +3 SpDef
    the first roll is its 61% of -1, the Defense branch would queue its full-HP +2"""
    ai_pok = poke("Clefairy", 20, "Cute Charm", [move])
    ai_pok[Pok.SPECIAL_DEFENSE_STAT_STAGE] = 3
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    _, queued = _expert(ai_pok, user)
    assert queued[0] == (-1, 156)


@pytest.mark.parametrize("ai_lv, hp_pct, expected", [
    (5, 100, [(1, 128)]),   # slower: 50% of +1
    (5, 20, [(1, 128)]),
    (50, 100, []),
    (50, 51, []),
    (50, 50, [(-1, 186)]),  # faster at half HP or less: 72.7% of -1
])
def test_expert_dragon_dance(poke, ai_lv, hp_pct, expected):
    """pokeplatinum Expert_DragonDance"""
    ai_pok = poke("Dratini", ai_lv, "Shed Skin", ["Dragon Dance"])
    ai_pok[Pok.MAX_HP] = 100
    ai_pok[Pok.CURRENT_HP] = hp_pct
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert _expert(ai_pok, user) == (0, expected)


@pytest.mark.parametrize("ai_ability, hp_pct, atk, expected", [
    ("Guts", 100, 0, 0), ("Guts", 51, 0, 0), ("Guts", 50, 0, -10),
    ("Guts", 100, 6, -10), ("Guts", 100, 5, 0), ("Simple", 100, 3, -10), ("Simple", 100, 2, 0),
])
def test_basic_belly_drum(poke, ai_ability, hp_pct, atk, expected):
    """pokeplatinum Basic_CheckBellyDrum, then Basic_CheckHighStatStage_Attack"""
    ai_pok = poke("Machop", 20, ai_ability, ["Belly Drum"])
    ai_pok[Pok.MAX_HP] = 100
    ai_pok[Pok.CURRENT_HP] = hp_pct
    ai_pok[Pok.ATTACK_STAT_STAGE] = atk
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert _basic(ai_pok, user, AbilityNames.STURDY) == expected


@pytest.mark.parametrize("ai_ability, stage, value, expected", [
    ("Guts", Pok.EVASION_STAT_STAGE, 6, -10), ("Guts", Pok.ACCURACY_STAT_STAGE, 6, -10),
    ("Guts", Pok.SPEED_STAT_STAGE, 5, 0), ("Simple", Pok.DEFENSE_STAT_STAGE, 3, -10),
    ("Simple", Pok.DEFENSE_STAT_STAGE, 2, 0),
])
def test_basic_acupressure(poke, ai_ability, stage, value, expected):
    """pokeplatinum Basic_CheckAcupressure: any of the seven stats at +6, +3 with Simple"""
    ai_pok = poke("Machop", 20, ai_ability, ["Acupressure"])
    ai_pok[stage] = value
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert _basic(ai_pok, user, AbilityNames.STURDY) == expected


@pytest.mark.parametrize("ai_ability, target_ability, ai_gender, target_gender, spa, expected", [
    ("Run Away", "Sturdy", "Male", "Female", 0, 0),
    ("Run Away", "Sturdy", "Female", "Male", 0, 0),
    ("Run Away", "Sturdy", "Male", "Male", 0, -10),
    ("Run Away", "Sturdy", "Genderless", "Female", 0, -10),
    ("Run Away", "Sturdy", "Female", "Genderless", 0, -10),
    ("Run Away", "Oblivious", "Male", "Female", 0, -10),
    ("Run Away", "Clear Body", "Male", "Female", 0, -10),
    ("Run Away", "White Smoke", "Male", "Female", 0, -10),
    ("Run Away", "Hyper Cutter", "Male", "Female", 0, 0),
    ("Mold Breaker", "Oblivious", "Male", "Female", 0, 0),
    ("Mold Breaker", "Oblivious", "Male", "Male", 0, -10),
    ("Run Away", "Sturdy", "Male", "Female", -6, -10),
    ("Run Away", "Sturdy", "Male", "Female", -5, 0),
])
def test_basic_captivate(poke, ai_ability, target_ability, ai_gender, target_gender, spa, expected):
    """pokeplatinum Basic_CheckCaptivate"""
    ai_pok = poke("Rattata", 20, ai_ability, ["Captivate"], gender=ai_gender)
    user = poke("Geodude", 20, target_ability, ["Tackle"], gender=target_gender)
    user[Pok.SPECIAL_ATTACK_STAT_STAGE] = spa
    ability = getattr(AbilityNames, target_ability.upper().replace(" ", "_"))
    assert _basic(ai_pok, user, ability) == expected


@pytest.mark.parametrize("move, hp_pct, expected", [
    ("Belly Drum", 100, (0, [])), ("Belly Drum", 90, (0, [])), ("Belly Drum", 89, (-2, [])),
    ("Acupressure", 50, (-1, [])), ("Acupressure", 51, (0, [(1, 96)])),
    ("Acupressure", 90, (0, [(1, 96)])), ("Acupressure", 91, (0, [(1, 192)])),
    ("Captivate", 100, (0, [])), ("Captivate", 10, (0, [])),
])
def test_expert_stage_moves(poke, move, hp_pct, expected):
    """pokeplatinum Expert_BellyDrum, Expert_Acupressure (37.5% is 128/256 * 192/256), and no
    Expert check for Captivate"""
    ai_pok = poke("Machop", 20, "Guts", [move], gender="Male")
    ai_pok[Pok.MAX_HP] = 100
    ai_pok[Pok.CURRENT_HP] = hp_pct
    user = poke("Geodude", 20, "Sturdy", ["Tackle"], gender="Female")
    assert _expert(ai_pok, user) == expected


@pytest.mark.parametrize("move", ["Haze", "Psych Up", "Heart Swap"])
@pytest.mark.parametrize("ai_stage, target_stage, expected", [
    ({}, {}, -10),
    ({Pok.ATTACK_STAT_STAGE: 2}, {Pok.DEFENSE_STAT_STAGE: -3}, -10),
    ({Pok.EVASION_STAT_STAGE: -1}, {}, 0),
    ({}, {Pok.ACCURACY_STAT_STAGE: 1}, 0),
])
def test_basic_stat_stage_imbalance(poke, move, ai_stage, target_stage, expected):
    """pokeplatinum Basic_CheckStatStageImbalance: -10 unless one of the AI's stages is below 0 or
    one of the target's above 0"""
    ai_pok = poke("Machop", 20, "Guts", [move])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    for idx, val in ai_stage.items():
        ai_pok[idx] = val
    for idx, val in target_stage.items():
        user[idx] = val
    assert _basic(ai_pok, user, AbilityNames.STURDY) == expected


@pytest.mark.parametrize("move, first, second", [
    ("Power Swap", Pok.ATTACK_STAT_STAGE, Pok.SPECIAL_ATTACK_STAT_STAGE),
    ("Guard Swap", Pok.DEFENSE_STAT_STAGE, Pok.SPECIAL_DEFENSE_STAT_STAGE),
])
@pytest.mark.parametrize("d1, d2, expected", [(0, 0, -10), (1, 0, 0), (0, 1, 0), (-2, -1, -10), (-1, 2, 0)])
def test_basic_power_guard_swap(poke, move, first, second, d1, d2, expected):
    """pokeplatinum Basic_CheckPowerSwap / GuardSwap: -10 unless the target is ahead on one of the
    two stats (DiffStatStages is the target's stage minus the AI's)"""
    ai_pok = poke("Machop", 20, "Guts", [move])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    ai_pok[first], ai_pok[second] = 1, 1
    user[first], user[second] = 1 + d1, 1 + d2
    assert _basic(ai_pok, user, AbilityNames.STURDY) == expected


@pytest.mark.parametrize("ai_stage, target_stage, expected", [
    ({}, {}, [(-1, 206)]),
    ({Pok.ATTACK_STAT_STAGE: 3}, {}, [(-3, 206), (-1, 206)]),
    ({Pok.EVASION_STAT_STAGE: 3}, {}, [(-3, 206), (-1, 206)]),
    ({Pok.ACCURACY_STAT_STAGE: 3}, {}, [(-1, 206)]),
    ({}, {Pok.ACCURACY_STAT_STAGE: -3}, [(-3, 206), (-1, 206)]),
    ({}, {Pok.SPECIAL_DEFENSE_STAT_STAGE: 3}, [(3, 206)]),
    ({Pok.ACCURACY_STAT_STAGE: -3}, {}, [(3, 206)]),
    ({Pok.EVASION_STAT_STAGE: -3}, {}, [(-1, 206)]),
    ({Pok.ATTACK_STAT_STAGE: 4}, {Pok.ATTACK_STAT_STAGE: 4}, [(-3, 206), (3, 206)]),
])
def test_expert_haze(poke, ai_stage, target_stage, expected):
    """pokeplatinum Expert_Haze: evasion on the high side, accuracy on the low"""
    ai_pok = poke("Machop", 20, "Guts", ["Haze"])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    for idx, val in ai_stage.items():
        ai_pok[idx] = val
    for idx, val in target_stage.items():
        user[idx] = val
    assert _expert(ai_pok, user) == (0, expected)


ALL_UP = {i: 1 for i in range(Pok.ATTACK_STAT_STAGE, Pok.EVASION_STAT_STAGE + 1)}


@pytest.mark.parametrize("move, ai_stage, target_stage, ai_focus, target_focus, expected", [
    ("Psych Up", {}, {}, False, False, (-2, [])),
    ("Psych Up", {}, {Pok.ATTACK_STAT_STAGE: 2}, False, False, (-2, [])),
    ("Psych Up", {}, {Pok.ATTACK_STAT_STAGE: 3}, False, False, (1, [])),
    ("Psych Up", {**ALL_UP, Pok.EVASION_STAT_STAGE: 0}, {Pok.EVASION_STAT_STAGE: 3}, False, False, (2, [])),
    ("Psych Up", ALL_UP, {Pok.EVASION_STAT_STAGE: 3}, False, False, (0, [(-2, 206)])),
    ("Psych Up", {}, {}, False, True, (-2, [])),
    ("Heart Swap", {}, {Pok.ATTACK_STAT_STAGE: 2}, False, False, (1, [])),
    ("Heart Swap", {}, {}, False, True, (1, [])),
    ("Heart Swap", ALL_UP, {Pok.SPEED_STAT_STAGE: 6}, False, True, (1, [])),
    ("Heart Swap", ALL_UP, {}, True, True, (0, [(-2, 206)])),
])
def test_expert_psych_up_heart_swap(poke, move, ai_stage, target_stage, ai_focus, target_focus, expected):
    """pokeplatinum Expert_PsychUp / Expert_HeartSwap (Heart Swap: +2 on the target is enough, its
    Focus Energy counts, the AI lacking it is +1)"""
    ai_pok = poke("Machop", 20, "Guts", [move])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    for idx, val in ai_stage.items():
        ai_pok[idx] = val
    for idx, val in target_stage.items():
        user[idx] = val
    if ai_focus:
        ai_pok[Pok.VOL_STATUS] |= VolStatus.FOCUS_ENERGY
    if target_focus:
        user[Pok.VOL_STATUS] |= VolStatus.FOCUS_ENERGY
    assert _expert(ai_pok, user) == expected


@pytest.mark.parametrize("move, first, second", [
    ("Power Swap", Pok.ATTACK_STAT_STAGE, Pok.SPECIAL_ATTACK_STAT_STAGE),
    ("Guard Swap", Pok.DEFENSE_STAT_STAGE, Pok.SPECIAL_DEFENSE_STAT_STAGE),
])
@pytest.mark.parametrize("d1, d2, top", [
    (4, 4, 5), (4, 2, 4), (4, 0, 3), (4, 1, 0), (4, -1, 0),
    (2, 4, 4), (2, 2, 3), (2, 0, 2), (2, 1, 0),
    (1, 4, 3), (1, 2, 2), (1, 0, 1), (1, 1, 0),
    (0, 4, 3), (0, 2, 2), (0, 1, 1), (0, 0, 0), (0, -1, 0),
    (-1, 4, 0),
])
def test_expert_power_guard_swap(monkeypatch, poke, move, first, second, d1, d2, top):
    """pokeplatinum Expert_PowerSwap / GuardSwap: the top bonus from the two gaps, then each 50%
    roll lowers it by one down to 0"""
    ai_pok = poke("Machop", 20, "Guts", [move])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    ai_pok[first], ai_pok[second] = -2, -2
    user[first], user[second] = -2 + d1, -2 + d2
    monkeypatch.setattr(ai.random, "getrandbits", lambda n: 255)  # every roll keeps the bonus
    assert _expert(ai_pok, user)[0] == top
    monkeypatch.setattr(ai.random, "getrandbits", lambda n: 0)    # every roll lowers it
    assert _expert(ai_pok, user)[0] == 0


def test_basic_power_trick(poke):
    """pokeplatinum Basic_CheckPowerTrick: -10 if it's already on"""
    ai_pok = poke("Shuckle", 20, "Sturdy", ["Power Trick"])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert _basic(ai_pok, user, AbilityNames.STURDY) == 0
    ai_pok[Pok.VOL_STATUS2] |= VolStatus2.POWER_TRICK
    assert _basic(ai_pok, user, AbilityNames.STURDY) == -10


@pytest.mark.parametrize("hp_pct, expected", [
    (100, (0, [(1, 160)])), (91, (0, [(1, 160)])), (90, (0, [(1, 128)])), (61, (0, [(1, 128)])),
    (60, (0, [(1, 92)])), (31, (0, [(1, 92)])), (30, (-2, [])),
])
def test_expert_power_trick(poke, hp_pct, expected):
    """pokeplatinum Expert_PowerTrick: 62.5%, 50%, 35.9% of +1 by HP, else -2"""
    ai_pok = poke("Shuckle", 20, "Sturdy", ["Power Trick"])
    ai_pok[Pok.MAX_HP] = 100
    ai_pok[Pok.CURRENT_HP] = hp_pct
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert _expert(ai_pok, user) == expected


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


@pytest.mark.parametrize("move, ai_ability, target_ability, expected", [
    ("Sand Attack", "Keen Eye", "Sturdy", 0),
    ("Sand Attack", "Run Away", "Keen Eye", -10),
    ("Sand Attack", "No Guard", "Sturdy", -10),
    ("Sweet Scent", "Run Away", "No Guard", -10),
    ("Growl", "Run Away", "Hyper Cutter", -10),
    ("Screech", "Run Away", "Hyper Cutter", 0),
    ("Screech", "Run Away", "Clear Body", -10),
    ("Growl", "Mold Breaker", "White Smoke", -10),
    ("String Shot", "Run Away", "Speed Boost", -10),
    ("Swagger", "Run Away", "Clear Body", 0),
    ("Swagger", "Run Away", "Hyper Cutter", 0),
    ("Flatter", "Run Away", "White Smoke", 0),
])
def test_basic_low_stat_stage(poke, move, ai_ability, target_ability, expected):
    """pokeplatinum Basic_CheckLowStatStage_*: only the stats the move lowers, Keen Eye read from
    the target, no Mold Breaker check; Swagger and Flatter only go through the confusion check"""
    ai_pok = poke("Rattata", 20, ai_ability, [move])
    user = poke("Geodude", 20, target_ability, ["Tackle"])
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


@pytest.mark.parametrize("move", [
    "Double-Edge", "Brave Bird", "Wood Hammer", "Head Smash", "Wild Charge", "Flare Blitz",
])
def test_expert_recoil_covers(poke, move):
    """RECOIL_THIRD, RECOIL_HALF and RECOIL_BURN_HIT all go to Expert_RecoilMove"""
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    assert _expert(poke("Rattata", 20, "Rock Head", [move]), user) == (1, [])
    assert _expert(poke("Rattata", 20, "Run Away", [move]), user) == (0, [])


@pytest.mark.parametrize("move", ["Giga Drain", "Leech Life", "Drain Punch"])
def test_expert_drain_covers(poke, move):
    """pokeplatinum Expert_DrainMove: 80.5% of -3 when resisted"""
    ai_pok = poke("Rattata", 20, "Run Away", [move])
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    assert _expert(ai_pok, user, 1.0) == (0, [])
    assert _expert(ai_pok, user, 0.5) == (0, [(-3, 206)])


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


@pytest.mark.parametrize("move", ["Fly", "Dive"])
@pytest.mark.parametrize("setup, effectiveness, expected", [
    ("power_herb", 1.0, 2), ("protect", 1.0, -1), (None, 0.5, 1), (None, 1.0, 0),
])
def test_expert_fly_and_dive(make_pokemon, move, setup, effectiveness, expected):
    """pokeplatinum Expert_ChargeTurnWithInvuln for Fly and Dive, like Bounce"""
    item = "Power Herb" if setup == "power_herb" else None
    ai_pok = make_pokemon("Pidgey", 5, "Keen Eye", [move], item=item).to_np()
    user = make_pokemon("Machop", 30, "Guts", ["Protect"]).to_np()
    seen = Enemy_AI_Knows.MOVE1 if setup == "protect" else 0
    assert _expert_charge(ai_pok, user, effectiveness, ai_know=seen) == (expected, [])


@pytest.mark.parametrize("setup, effectiveness, expected", [
    ("power_herb", 1.0, (1, [])), ("protect", 1.0, (0, [])), (None, 0.5, (1, [])),
    ("toxic", 1.0, (0, [(1, 176)])),
])
def test_expert_shadow_force(make_pokemon, setup, effectiveness, expected):
    """pokeplatinum Expert_ShadowForce: +1 for a Power Herb, a seen Protect doesn't count"""
    item = "Power Herb" if setup == "power_herb" else None
    ai_pok = make_pokemon("Gastly", 5, "Levitate", ["Shadow Force"], item=item).to_np()
    user = make_pokemon("Machop", 30, "Guts", ["Protect"]).to_np()
    if setup == "toxic":
        user[Pok.STATUS] = Status.TOXIC
    seen = Enemy_AI_Knows.MOVE1 if setup == "protect" else 0
    assert _expert_charge(ai_pok, user, effectiveness, ai_know=seen) == expected


def test_expert_protect_sees_shadow_force(poke):
    """pokeplatinum and Pokemow Expert Protect: a seen Shadow Force counts like Feint"""
    ai_pok = poke("Rattata", 20, "Run Away", ["Protect"])
    user = poke("Gastly", 20, "Levitate", ["Shadow Force"])
    assert _expert_knows(ai_pok, user, Enemy_AI_Knows.MOVE1) == (0, [(-2, 128), (2, 85), (-1, 128)])


CHARGE_NO_INVULN = ("Solar Beam", "Skull Bash", "Sky Attack", "Razor Wind")


def _expert_charge(ai_pok, user, effectiveness=1.0, weather=0, ai_know=0):
    """_expert with the field's weather and AI_KNOWS passed through"""
    rand = np.zeros((4, 5, 2), dtype=np.int16)
    score = ai.expert_flag(
        ai_pok, user, move_slice(ai_pok, 0), 1, 0, rand, weather, 0, effectiveness, 0, ai_know
    )
    queued = [tuple(int(x) for x in rand[0, i]) for i in range(5) if rand[0, i, 1]]
    return score, queued


@pytest.mark.parametrize("move", CHARGE_NO_INVULN)
@pytest.mark.parametrize("setup, hp_pct, effectiveness, expected", [
    (None, 100, 0.5, -2), (None, 100, 0.0, -2), (None, 100, 0.25, -2),   # resisted or immune
    ("power_herb", 10, 1.0, 2), ("power_herb", 100, 0.5, -2),
    ("protect", 100, 1.0, -2), ("protect_unseen", 100, 1.0, 0),
    (None, 39, 1.0, 0), (None, 38, 1.0, -1), (None, 100, 2.0, 0),
])
def test_expert_charge_no_invuln(make_pokemon, move, setup, hp_pct, effectiveness, expected):
    """pokeplatinum Expert_ChargeTurnNoInvuln, Pokemow RazorWind / Solarbeam (no random rolls)"""
    item = "Power Herb" if setup == "power_herb" else None
    ai_pok = make_pokemon("Pidgey", 20, "Keen Eye", [move], item=item).to_np()
    ai_pok[Pok.MAX_HP] = 100
    ai_pok[Pok.CURRENT_HP] = hp_pct
    user = make_pokemon("Machop", 20, "Guts", ["Protect"]).to_np()
    seen = Enemy_AI_Knows.MOVE1 if setup == "protect" else 0
    assert _expert_charge(ai_pok, user, effectiveness, ai_know=seen) == (expected, [])


@pytest.mark.parametrize("move, weather, effectiveness, expected", [
    ("Solar Beam", Weather.SUN, 1.0, 2), ("Solar Beam", Weather.SUN, 0.5, -2),
    ("Solar Beam", Weather.RAIN, 1.0, -1), ("Skull Bash", Weather.SUN, 1.0, -1),
])
def test_expert_solar_beam_in_sun(poke, move, weather, effectiveness, expected):
    """+2 for Solar Beam in sun, read off the field's weather, before the HP check"""
    ai_pok = poke("Bulbasaur", 20, "Overgrow", [move])
    ai_pok[Pok.MAX_HP] = 100
    ai_pok[Pok.CURRENT_HP] = 10
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    assert _expert_charge(ai_pok, user, effectiveness, weather) == (expected, [])


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


@pytest.mark.parametrize("move", ["Wrap", "Bind", "Clamp", "Fire Spin", "Magma Storm"])
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


@pytest.mark.parametrize("item, pp, picks", [
    ("Choice Band", 10, {0}), ("Choice Band", 0, {10}), ("Oran Berry", 10, {0, 1}),
])
def test_ai_keeps_to_its_choice_lock(make_pokemon, make_battle, item, pp, picks):
    """A choice-locked AI only scores the locked move (Growl), Struggle once it's out of PP, and a
    lock without a choice item does nothing"""
    me = make_pokemon("Rattata", 20, "Run Away", ["Tackle"])
    opp = make_pokemon("Rattata", 20, "Run Away", ["Growl", "Tackle"], item=item)
    arr = make_battle([me], [opp])
    ai_pok = pok_slice(arr, 0, opp=True)
    ai_pok[Pok.CHOICE_LOCK] = 1
    move_slice(ai_pok, 0)[Move.PP] = pp
    random.seed(2)
    assert {return_idx(arr) for _ in range(60)} == picks


def test_bound_ai_never_switches(make_pokemon, make_battle):
    """Withdraw checks are skipped while a bind traps the AI's active"""
    me = make_pokemon("Gastly", 20, "Levitate", ["Lick"])
    opp = [make_pokemon("Rattata", 20, "Run Away", ["Tackle", "Quick Attack"]),
           make_pokemon("Pikachu", 20, "Static", ["Thunder Shock"])]
    arr = make_battle([me], opp)
    pok_slice(arr, 0, opp=True)[Pok.VOL_STATUS] = VolStatus.PARTIALLY_TRAPPED
    assert all(return_idx(arr) in (0, 1) for _ in range(30))


@pytest.mark.parametrize("ai_species, ai_ability, ai_item, my_ability, switches", [
    ("Rattata", "Run Away", None, "Shadow Tag", False),
    ("Rattata", "Run Away", None, "Arena Trap", False),
    ("Pidgey", "Keen Eye", None, "Arena Trap", False),
    ("Wobbuffet", "Shadow Tag", None, "Shadow Tag", False),
    ("Rattata", "Run Away", "Shed Shell", "Shadow Tag", False),
    ("Magnemite", "Sturdy", None, "Magnet Pull", False),
    ("Rattata", "Run Away", None, "Magnet Pull", True),
    ("Pidgey", "Keen Eye", None, "Levitate", True),
])
def test_trapped_ai_never_switches(make_pokemon, make_battle, ai_species, ai_ability, ai_item,
                                   my_ability, switches):
    """pokeplatinum TrainerAI_ShouldSwitch skips the withdraws for any Shadow Tag or Arena Trap
    on my side and for Magnet Pull on a Steel type, its own Shadow Tag, Flying type or Shed
    Shell don't count"""
    me = make_pokemon("Gastly", 20, my_ability, ["Lick"])
    opp = [make_pokemon(ai_species, 20, ai_ability, ["Tackle", "Quick Attack"], item=ai_item),
           make_pokemon("Pikachu", 20, "Static", ["Thunder Shock"])]
    arr = make_battle([me], opp)
    picks = [return_idx(arr) for _ in range(30)]
    assert any(p < 0 for p in picks) == switches


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
    ("Sunny Day", {}, 0),
    ("Sunny Day", {"weather": Weather.SUN}, -8),
    ("Sunny Day", {"weather": Weather.RAIN}, 0),
    ("Sunny Day", {"user_ability": "Hydration", "user_status": Status.BURN}, -10),
    ("Sunny Day", {"user_ability": "Hydration"}, 0),
    ("Sunny Day", {"user_ability": "Hydration", "user_status": Status.BURN,
                   "ai_ability": "Leaf Guard"}, 0),
    ("Sunny Day", {"user_ability": "Hydration", "user_status": Status.BURN,
                   "ai_ability": "Solar Power", "weather": Weather.SUN}, -8),
    ("Hail", {}, 0),
    ("Hail", {"weather": Weather.HAIL}, -8),
    ("Hail", {"weather": Weather.SUN}, 0),
    ("Hail", {"user_ability": "Ice Body"}, -8),
    ("Hail", {"user_ability": "Ice Body", "ai_ability": "Ice Body"}, 0),
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


@pytest.mark.parametrize("move", ["Stealth Rock", "Toxic Spikes", "Spikes"])
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


@pytest.mark.parametrize("ai_ability, hp_pct, status, weather, expected", [
    ("Run Away", 100, 0, 0, 0),
    ("Flower Gift", 30, 0, Weather.RAIN, -1),
    ("Run Away", 100, 0, Weather.HAIL, 1),
    ("Run Away", 100, 0, Weather.RAIN, 1),
    ("Run Away", 100, 0, Weather.SUN, 0),
    ("Flower Gift", 100, 0, 0, 1),
    ("Flower Gift", 100, 0, Weather.SANDSTORM, 1),   # +1 once
    ("Leaf Guard", 100, 0, 0, 0),
    ("Leaf Guard", 100, Status.BURN, 0, 1),           # pokeplatinum's bug: a status counts
])
def test_expert_sunny_day(poke, ai_ability, hp_pct, status, weather, expected):
    """pokeplatinum Expert_SunnyDay"""
    ai_pok = poke("Cherubi", 30, ai_ability, ["Sunny Day"])
    ai_pok[Pok.CURRENT_HP] = ai_pok[Pok.MAX_HP] * hp_pct // 100
    ai_pok[Pok.STATUS] = status
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    assert _expert_field(ai_pok, user, weather=weather) == (expected, [])


@pytest.mark.parametrize("ai_ability, moves, hp_pct, weather, expected", [
    ("Run Away", ["Hail"], 100, 0, 0),
    ("Ice Body", ["Hail", "Blizzard"], 100, 0, 0),    # nothing without one of the other weathers
    ("Ice Body", ["Hail", "Blizzard"], 30, Weather.RAIN, -1),
    ("Run Away", ["Hail"], 100, Weather.HAIL, 0),
    ("Run Away", ["Hail"], 100, Weather.SUN, 1),
    ("Run Away", ["Hail", "Blizzard"], 100, Weather.RAIN, 3),
    ("Ice Body", ["Hail"], 100, Weather.SANDSTORM, 3),
    ("Ice Body", ["Hail", "Blizzard"], 100, Weather.SUN, 5),
])
def test_expert_hail(poke, ai_ability, moves, hp_pct, weather, expected):
    """pokeplatinum Expert_Hail: Blizzard and Ice Body only count after the weather's +1"""
    ai_pok = poke("Snorunt", 30, ai_ability, moves)
    ai_pok[Pok.CURRENT_HP] = ai_pok[Pok.MAX_HP] * hp_pct // 100
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    assert _expert_field(ai_pok, user, weather=weather) == (expected, [])


@pytest.mark.parametrize("weather, m_type, power", [
    (0, Types.NORMAL, 50), (Weather.SUN, Types.FIRE, 100), (Weather.RAIN, Types.WATER, 100),
    (Weather.SANDSTORM, Types.ROCK, 100), (Weather.HAIL, Types.ICE, 100),
])
def test_ai_sees_weather_ball(poke, weather, m_type, power):
    """Pokemow's damage calc sees Weather Ball's type and power under the weather"""
    ai_pok = poke("Castform", 30, "Forecast", ["Weather Ball"])
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    view = ai.ai_move_view(move_slice(ai_pok, 0), ai_pok, user, weather)
    assert (view[Move.TYPE], view[Move.POWER]) == (m_type, power)
    assert move_slice(ai_pok, 0)[Move.TYPE] == Types.NORMAL


def test_basic_weather_ball_into_water_absorb(poke):
    """Pokemow Check_VariableType: Weather Ball in rain into Water Absorb is -12"""
    ai_pok = poke("Castform", 30, "Forecast", ["Weather Ball"])
    user = poke("Lapras", 30, "Water Absorb", ["Tackle"])
    scores = []
    for weather in (0, Weather.RAIN):
        view = ai.ai_move_view(move_slice(ai_pok, 0), ai_pok, user, weather)
        scores.append(ai.basic_flag(view, AbilityNames.WATER_ABSORB, ai_pok, user, 1.0, weather, 0, 0, 0, 1))
    assert scores[0] != -12 and scores[1] == -12


def test_party_checks_see_weather_ball(poke):
    """pokeplatinum TrainerAI_MoveType / Move_CalcVariableType: the bench's Weather Ball is Fire
    in sun, super effective on my Grass type"""
    party = np.zeros(6 * POK_LEN, dtype=np.int32)
    party[:POK_LEN] = poke("Machop", 20, "Guts", ["Karate Chop"])
    party[POK_LEN:2 * POK_LEN] = poke("Castform", 20, "Forecast", ["Weather Ball"])
    grass = poke("Turtwig", 20, "Overgrow", ["Tackle"])
    assert 1 not in ai.check_super_ef_move_pty(party, grass, 0)
    assert 1 in ai.check_super_ef_move_pty(party, grass, 0, False, False, Weather.SUN)
    assert 1 in ai.check_any_damaging_move_pty(party, grass, 0, False, Weather.SUN)


def test_post_ko_switch_sees_weather_ball(poke):
    """BattleAI_PostKOSwitchIn phase 1 sees Weather Ball's weather type"""
    party = np.zeros(6 * POK_LEN, dtype=np.int32)
    party[:POK_LEN] = poke("Machop", 20, "Guts", ["Karate Chop"])
    party[:POK_LEN][Pok.CURRENT_HP] = 0
    party[POK_LEN:2 * POK_LEN] = poke("Rattata", 20, "Run Away", ["Tackle"])
    party[2 * POK_LEN:3 * POK_LEN] = poke("Castform", 20, "Forecast", ["Weather Ball"])
    grass = poke("Turtwig", 20, "Overgrow", ["Tackle"])
    dead = party[:POK_LEN]
    assert sub_after_death(party, grass, dead, 0, Weather.SUN) == 2


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


@pytest.mark.parametrize("seen, expected", [(True, [(1, 128)]), (False, [])])
def test_expert_pursuit_against_a_seen_u_turn(poke, seen, expected):
    """50% +1 once the AI saw the target use U-turn (pokeplatinum IfMoveNotKnown reads battlerMoves)"""
    ai_pok = poke("Murkrow", 20, "Insomnia", ["Pursuit"])
    ai_pok[Pok.TURNS_ACTIVE] = 2
    user = poke("Geodude", 20, "Sturdy", ["Tackle", "U-turn"])
    know = Enemy_AI_Knows.MOVE2 if seen else Enemy_AI_Knows.MOVE1
    assert _expert_field(ai_pok, user, ai_know=know) == (0, expected)


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
    ("Growl", -10), ("Sing", -10), ("Grass Whistle", -10), ("Disarming Voice", 0), ("Chatter", -10),
    ("Bug Buzz", -10),
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
    moltres = poke("Moltres", 40, "Pressure", ["Ember"])
    assert (2 in ai.check_super_ef_move_pty(party, moltres, 0, gravity)) == gravity


def test_party_checks_see_iron_ball(poke):
    """pokeplatinum CalcEffectiveness reads the defender's item: Iron Ball switches off Levitate
    and the Flying immunity to Ground, so the bench's Earthquake hits my Moltres and Gastly x2"""
    party = np.zeros(6 * POK_LEN, dtype=np.int32)
    party[:POK_LEN] = poke("Machop", 20, "Guts", ["Karate Chop"])
    party[POK_LEN:2 * POK_LEN] = poke("Geodude", 20, "Sturdy", ["Earthquake"])
    moltres = poke("Moltres", 40, "Pressure", ["Ember"], item="Iron Ball")
    assert 1 in ai.check_super_ef_move_pty(party, moltres, 0)
    attacker = poke("Geodude", 20, "Sturdy", ["Earthquake"])
    gastly = poke("Gastly", 20, "Levitate", ["Lick"], item="Iron Ball")
    eff, den = ai.party_effectiveness(Types.GROUND, attacker, gastly)
    assert eff // den == 2
    assert ai.party_super_effective(Types.GROUND, attacker, gastly)


@pytest.mark.parametrize("move_type, target, weak", [
    (Types.ELECTRIC, "Gligar", True),
    (Types.GROUND, "Aerodactyl", True),
    (Types.GROUND, "Skarmory", True),
    (Types.GHOST, "Girafarig", True),
    (Types.GROUND, "Moltres", False),     # Fire's weakness row comes before Flying's immunity
    (Types.ELECTRIC, "Quagsire", False),  # Water's row comes before Ground's
])
def test_party_check_dual_non_immunity_glitch(poke, move_type, target, weak):
    """Pokemow switching page: an immunity earlier in the type table keeps the weakness flag that a
    later row sets, so the AI's party scans see these as super effective; the immunity stays"""
    attacker = poke("Machop", 20, "Guts", ["Karate Chop"])
    defender = poke(target, 20, "Keen Eye", ["Tackle"])
    assert ai.party_super_effective(move_type, attacker, defender) == weak
    assert ai.party_effectiveness(move_type, attacker, defender)[0] == 0 or not weak


@pytest.mark.parametrize("attacker_ab, gravity, immune", [
    ("Sturdy", False, True), ("Mold Breaker", False, False), ("Sturdy", True, False),
])
def test_party_checks_see_levitate(poke, attacker_ab, gravity, immune):
    """pokeplatinum BattleSystem_CalcEffectiveness: a Levitate bench member is immune to the Ground
    move that hit the active, unless the attacker has Mold Breaker or Gravity is up"""
    party = np.zeros(6 * POK_LEN, dtype=np.int32)
    party[:POK_LEN] = poke("Machop", 20, "Guts", ["Karate Chop"])
    party[POK_LEN:2 * POK_LEN] = poke("Gastly", 20, "Levitate", ["Lick"])
    user = poke("Drifloon", 20, attacker_ab, ["Gust"])
    assert (list(ai.check_immunity_pty(party, user, Types.GROUND, 0, gravity)) == [1]) == immune


@pytest.mark.parametrize("ability, hits_ghost", [("Guts", False), ("Scrappy", True)])
def test_party_effectiveness_sees_scrappy(poke, ability, hits_ghost):
    """Scrappy's Fighting move hits a Ghost (pokeplatinum BattleSystem_CalcEffectiveness)"""
    attacker = poke("Machop", 20, ability, ["Karate Chop"])
    gastly = poke("Gastly", 20, "Levitate", ["Lick"])
    eff, _ = ai.party_effectiveness(Types.FIGHTING, attacker, gastly)
    assert (eff != 0) == hits_ghost


@pytest.mark.parametrize("attacker_ab, move_type, damaging_turn, blocked", [
    ("Guts", Types.WATER, True, True),
    ("Guts", Types.FIRE, True, False),
    ("Mold Breaker", Types.WATER, True, False),
    ("Guts", Types.WATER, False, False),
])
def test_party_effectiveness_sees_wonder_guard(poke, attacker_ab, move_type, damaging_turn, blocked):
    """Wonder Guard takes every move that isn't super effective, unless the attacker has Mold
    Breaker or the move isn't on its damaging turn (a charge move, Fire Fang)"""
    attacker = poke("Machop", 20, attacker_ab, ["Karate Chop"])
    shedinja = poke("Shedinja", 20, "Wonder Guard", ["Scratch"])
    eff, _ = ai.party_effectiveness(move_type, attacker, shedinja, False, damaging_turn)
    assert (eff == 0) == blocked


def test_sub_after_death_stage_two_skips_power_one_moves(poke):
    """pokeplatinum BattleAI_PostKOSwitchIn stage 2 skips data power 1 moves (Low Kick, Hidden
    Power, fixed damage) but scores a status move's power 0 chip"""
    party = np.zeros(6 * POK_LEN, dtype=np.int32)
    party[:POK_LEN] = poke("Machop", 20, "Guts", ["Low Kick", "Seismic Toss"])
    party[POK_LEN:2 * POK_LEN] = poke("Rattata", 20, "Run Away", ["Growl"])
    dead = poke("Machop", 20, "Guts", ["Karate Chop"])
    dead[Pok.CURRENT_HP] = 0
    user = poke("Pidgey", 20, "Keen Eye", ["Tackle"])
    assert sub_after_death(party, user, dead) == 1



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
    (100, 2, True, (-1, [(-3, 206)])),
    (100, 3, True, (-1, [(-1, 128), (-3, 206)])),
    (100, 4, True, (-1, [(-1, 128), (-3, 206)])),
])
def test_expert_explosion(poke, hp_pct, evasion, faster, expected):
    """Pokemow Expert Selfdestruction: evasion (the second -1 from +3), then the user's HP and
    speed"""
    ai_pok = poke("Geodude", 20, "Sturdy", ["Selfdestruct"])
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    ai_pok[Pok.CURRENT_HP] = ai_pok[Pok.MAX_HP] * hp_pct // 100
    if ai_pok[Pok.CURRENT_HP] * 100 // ai_pok[Pok.MAX_HP] != hp_pct:
        ai_pok[Pok.MAX_HP] = 100
        ai_pok[Pok.CURRENT_HP] = hp_pct
    user[Pok.EVASION_STAT_STAGE] = evasion
    ai_pok[Pok.SPEED], user[Pok.SPEED] = (200, 10) if faster else (10, 200)
    assert _expert(ai_pok, user) == expected


# ── 10.2 Memento, Healing Wish, Grudge ───────────────────────────────────────

@pytest.mark.parametrize("kwargs, expected", [
    ({}, 0),
    ({"user_ability": "Clear Body"}, -10),
    ({"user_ability": "White Smoke"}, -10),
    ({"user_ability": "Clear Body", "ai_ability": "Mold Breaker"}, 0),
    ({"ai_bench": 0}, -10),
])
def test_basic_memento(kwargs, expected):
    """pokeplatinum Basic_CheckMemento: the target's stat-drop abilities, then the AI's last Pokemon"""
    assert _basic_switch("Memento", **kwargs) == expected


@pytest.mark.parametrize("atk, spatk, expected", [(-6, 0, -10), (0, -6, -8), (-6, -6, -10), (-5, -5, 0)])
def test_basic_memento_stages(poke, atk, spatk, expected):
    """-10 at -6 Attack, else -8 at -6 Sp. Atk"""
    ai_pok = poke("Murkrow", 20, "Insomnia", ["Memento"])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    user[Pok.ATTACK_STAT_STAGE] = atk
    user[Pok.SPECIAL_ATTACK_STAT_STAGE] = spatk
    assert _basic(ai_pok, user, AbilityNames.STURDY) == expected


@pytest.mark.parametrize("faster", [True, False])
def test_expert_memento_is_scored_like_explosion(poke, faster):
    """pokeplatinum Expert_Main sends Memento to Expert_Explosion"""
    scores = []
    for move in ("Memento", "Selfdestruct"):
        ai_pok = poke("Murkrow", 20, "Insomnia", [move])
        user = poke("Rattata", 20, "Run Away", ["Tackle"])
        ai_pok[Pok.SPEED], user[Pok.SPEED] = (200, 10) if faster else (10, 200)
        scores.append(_expert(ai_pok, user))
    assert scores[0] == scores[1]


@pytest.mark.parametrize("bench, status, hurt, expected", [
    (1, False, True, -20), (1, True, False, -20), (1, False, False, -30), (0, True, True, -30),
])
def test_basic_healing_wish(poke, bench, status, hurt, expected):
    """pokeplatinum Basic_CheckHealingWish: -20, -10 more on the last Pokemon or with nobody to heal"""
    ai_pok = poke("Clefairy", 20, "Cute Charm", ["Healing Wish"])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    score = ai.basic_flag(
        move_slice(ai_pok, 0), AbilityNames.STURDY, ai_pok, user, 1.0, 0, ai_bench=bench,
        ai_bench_status=status, ai_bench_hurt=hurt
    )
    assert score == expected


@pytest.mark.parametrize("hp_pct, faster, roll, has_se, bench_more, expected", [
    (80, True, 0, False, False, (0, [(-5, 64)])),               # healthy and faster
    (80, False, 0, False, False, (0, [(-1, 206)])),             # slower: on to the HP checks
    (51, True, 0, False, False, (0, [(-1, 206)])),
    (50, True, 191, False, True, (0, [])),                      # 75%: skips the +1 section
    (50, True, 192, False, True, (1, [(1, 64), (1, 128)])),
    (50, True, 192, True, False, (1, [])),
    (30, True, 191, True, True, (0, [(1, 128)])),               # 30% or less: 50% of +1
])
def test_expert_healing_wish(monkeypatch, poke, hp_pct, faster, roll, has_se, bench_more, expected):
    """pokeplatinum Expert_HealingWish"""
    monkeypatch.setattr(ai.random, "getrandbits", lambda k: roll)
    ai_pok = poke("Clefairy", 20, "Cute Charm", ["Healing Wish"])
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    ai_pok[Pok.MAX_HP] = 100
    ai_pok[Pok.CURRENT_HP] = hp_pct
    ai_pok[Pok.SPEED], user[Pok.SPEED] = (200, 10) if faster else (10, 200)
    rand = np.zeros((4, 5, 2), dtype=np.int16)
    score = ai.expert_flag(
        ai_pok, user, move_slice(ai_pok, 0), 1, 0, rand, 0, 0, 1.0, 0, has_se=has_se,
        bench_more=bench_more
    )
    queued = [tuple(int(x) for x in rand[0, i]) for i in range(5) if rand[0, i, 1]]
    assert (score, queued) == expected


@pytest.mark.parametrize("eff, bench, hp_pct, faster, roll, has_se, bench_more, expected", [
    (0.5, 1, 100, True, 0, False, True, (-1, [])),                  # resisted: -1 and stop
    (0.0, 1, 100, True, 0, False, True, (-1, [])),
    (1.0, 0, 100, True, 0, True, False, (0, [])),                    # nobody else alive
    (1.0, 1, 100, True, 0, True, True, (1, [(-2, 192), (1, 192), (1, 128)])),
    (1.0, 1, 100, True, 64, True, False, (-2, [(-2, 192)])),         # no stronger bench: 75% -2, stop
    (1.0, 1, 50, False, 63, False, False, (0, [(1, 128), (1, 128)])),
    (1.0, 1, 71, False, 0, False, True, (0, [(1, 192), (1, 128), (1, 128)])),
    (1.0, 1, 30, True, 0, False, True, (1, [(1, 64)])),               # the AI's own HP, Pokemow
])
def test_expert_u_turn(monkeypatch, poke, eff, bench, hp_pct, faster, roll, has_se, bench_more, expected):
    """Pokemow Expert UTurn with its effectiveness pre-check"""
    monkeypatch.setattr(ai.random, "getrandbits", lambda k: roll)
    ai_pok = poke("Yanmega", 40, "Speed Boost", ["U-turn"])
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    ai_pok[Pok.MAX_HP] = 100
    ai_pok[Pok.CURRENT_HP] = hp_pct
    user[Pok.MAX_HP] = 100
    user[Pok.CURRENT_HP] = 100 - hp_pct + 1     # the target's HP mustn't matter
    ai_pok[Pok.SPEED], user[Pok.SPEED] = (200, 10) if faster else (10, 200)
    rand = np.zeros((4, 5, 2), dtype=np.int16)
    score = ai.expert_flag(
        ai_pok, user, move_slice(ai_pok, 0), 1, 0, rand, 0, 0, eff, 0, ai_bench=bench, has_se=has_se,
        bench_more=bench_more
    )
    queued = [tuple(int(x) for x in rand[0, i]) for i in range(5) if rand[0, i, 1]]
    assert (score, queued) == expected


@pytest.mark.parametrize("bench_moves, more", [
    (["Pound"], False),       # same move, its own higher level doesn't count
    (["Strength"], True),     # a stronger move does
    (["Growl"], False),
])
def test_bench_deals_more_uses_the_active_battler(make_pokemon, make_battle, bench_moves, more):
    """pokeplatinum IfPartyMemberDealsMoreDamage works the bench's moves out on the active's battler"""
    arr = make_battle(
        [make_pokemon("Geodude", 20, "Sturdy", ["Tackle"])],
        [make_pokemon("Clefairy", 20, "Cute Charm", ["Healing Wish", "Pound"]),
         make_pokemon("Machamp", 60, "Guts", bench_moves)],
    )
    assert bench_deals_more(arr, opp_active(arr), my_active(arr), 0, 0, 0, False) == more


def test_encore_and_heal_block_lists_have_the_new_moves():
    """pokeplatinum Expert_Encore's table lists Grudge's and Healing Wish's effects, Expert_HealBlock
    Healing Wish's"""
    assert MoveName.GRUDGE in ai.ENCORE_ENCOURAGED_M and MoveName.HEALING_WISH in ai.ENCORE_ENCOURAGED_M
    assert MoveName.HEALING_WISH in ai.HEAL_BLOCK_GOOD_M



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


# ── Batch 8: Levitate, Wonder Guard, Scrappy in the AI's type chart ──────────

@pytest.mark.parametrize("ai_ab, gravity, immune", [
    ("Run Away", False, True), ("Mold Breaker", False, False), ("Run Away", True, False),
])
def test_ai_effectiveness_levitate(poke, ai_ab, gravity, immune):
    """pokeplatinum's AI runs ApplyTypeChart, which has Levitate"""
    ai_pok = poke("Diglett", 30, ai_ab, ["Mud-Slap"])
    user = poke("Misdreavus", 30, "Levitate", ["Astonish"])
    eff, _ = ai.trainer_ai_effectiveness(move_slice(ai_pok, 0), ai_pok, user, gravity)
    assert (eff == 0) == immune


@pytest.mark.parametrize("move, immune", [
    ("Tackle", True), ("Karate Chop", False), ("Fire Fang", False), ("Thunder Wave", False),
])
def test_ai_effectiveness_wonder_guard(poke, move, immune):
    """Wonder Guard: immune to damaging moves that aren't super effective, Fire Fang excepted"""
    ai_pok = poke("Rattata", 30, "Run Away", [move])
    user = poke("Rattata", 30, "Wonder Guard", ["Tackle"])
    eff, _ = ai.trainer_ai_effectiveness(move_slice(ai_pok, 0), ai_pok, user)
    assert (eff == 0) == immune


def test_ai_effectiveness_scrappy(poke):
    """A Scrappy AI's Normal move is neutral into a Ghost"""
    user = poke("Gastly", 30, "Levitate", ["Lick"])
    plain = poke("Kangaskhan", 30, "Run Away", ["Tackle"])
    scrappy = poke("Kangaskhan", 30, "Scrappy", ["Tackle"])
    assert ai.trainer_ai_effectiveness(move_slice(plain, 0), plain, user)[0] == 0
    assert ai.trainer_ai_effectiveness(move_slice(scrappy, 0), scrappy, user)[0] == 1.5


@pytest.mark.parametrize("known, expected", [(1, AbilityNames.STURDY), (0, AbilityNames.ROCK_HEAD)])
def test_ai_uses_a_revealed_ability(monkeypatch, make_pokemon, make_battle, known, expected):
    """Pok.AB_KNOWN: the AI reads my real ability instead of guessing from the species pool"""
    from Models import trainer_ai
    arr = make_battle([make_pokemon("Geodude", 20, "Sturdy", ["Tackle"])],
                      [make_pokemon("Rattata", 20, "Run Away", ["Tackle"])])
    pok_slice(arr, 0)[Pok.AB_KNOWN] = known
    seen = []
    monkeypatch.setattr(trainer_ai.random, "getrandbits", lambda k: 0)
    monkeypatch.setattr(trainer_ai, "basic_flag", lambda move, ability, *a, **k: seen.append(ability) or 0)
    return_idx(arr)
    assert seen and set(seen) == {expected}


@pytest.mark.parametrize("ability", ["Insomnia", "Poison Heal", "Sticky Hold", "Truant", "Multitype"])
def test_abilities_the_ai_reads_are_relevant(ability):
    """Abilities the AI script compares my ability against make it guess for my species"""
    assert getattr(AbilityNames, ability.upper().replace(" ", "_")) in ai.RELEVANT_ABILITIES


def test_ai_guesses_insomnia_on_an_unrevealed_drowzee(monkeypatch, make_pokemon, make_battle):
    """Drowzee is Insomnia or Forewarn: with nothing revealed the AI guesses from the pool"""
    from Models import trainer_ai
    arr = make_battle([make_pokemon("Drowzee", 20, "Forewarn", ["Pound"])],
                      [make_pokemon("Rattata", 20, "Run Away", ["Tackle"])])
    pok_slice(arr, 0)[Pok.AB_KNOWN] = 0
    seen = []
    monkeypatch.setattr(trainer_ai.random, "getrandbits", lambda k: 0)
    monkeypatch.setattr(trainer_ai, "basic_flag", lambda move, ability, *a, **k: seen.append(ability) or 0)
    return_idx(arr)
    assert seen and set(seen) == {AbilityNames.INSOMNIA}


def test_ai_script_reads_weather_through_cloud_nine(monkeypatch, make_pokemon, make_battle):
    """pokeplatinum AICmd_LoadCurrentWeather reads the field, the damage estimate and the speed
    compare see Cloud Nine (CalcMoveDamage, CompareBattlerSpeed)"""
    from Models import trainer_ai
    arr = make_battle([make_pokemon("Psyduck", 20, "Cloud Nine", ["Tackle"])],
                      [make_pokemon("Squirtle", 20, "Torrent", ["Water Gun"])])
    arr[Field.WEATHER] = Weather.RAIN
    damage, script, speed = [], [], []
    monkeypatch.setattr(trainer_ai, "ai_move_damage", lambda *a: damage.append(a[4]) or 10)
    monkeypatch.setattr(trainer_ai, "basic_flag", lambda *a: script.append(a[5]) or 0)
    real_expert = trainer_ai.expert_flag

    def spy(*args):
        script.append(args[6])
        speed.append(args[14])
        return real_expert(*args)
    monkeypatch.setattr(trainer_ai, "expert_flag", spy)
    return_idx(arr)
    assert damage and set(damage) == {0}
    assert script and set(script) == {Weather.RAIN}
    assert speed == [0]


@pytest.mark.parametrize("ai_ab, u_ab, claw_guess, expected", [
    ("Run Away", "Sturdy", 0, -1),   # Geodude is slower than Rattata: the AI (Geodude) is second
    ("Run Away", "Sturdy", 1, 1),    # its guessed Quick Claw puts it first
    ("Run Away", "Sturdy", 3, -1),   # both guessed: speed
    ("Run Away", "Stall", 0, 1),     # the faster target has Stall
    ("Stall", "Stall", 0, 1),        # both Stall: the slower first (pokeplatinum)
    ("Stall", "Sturdy", 2, -1),      # a guessed Quick Claw beats Stall
])
def test_ai_speed_order(poke, ai_ab, u_ab, claw_guess, expected):
    """pokeplatinum CompareBattlerSpeed as the AI sees it: Quick Claw guess, Stall, then speed"""
    ai_pok = poke("Geodude", 20, ai_ab, ["Tackle"])
    user = poke("Rattata", 20, u_ab, ["Tackle"])
    assert ai.ai_speed_order(ai_pok, user, 0, claw_guess) == expected


@pytest.mark.parametrize("ai_item, u_item, u_ab, expected", [
    (None, "Lagging Tail", "Sturdy", 1),            # the faster target holds one: the AI first
    ("Full Incense", None, "Sturdy", -1),           # the faster AI holds one: it goes second
    ("Lagging Tail", "Full Incense", "Sturdy", -1),  # both: the slower first (pokeplatinum)
    ("Lagging Tail", None, "Stall", -1),            # checked before Stall
    ("Macho Brace", None, "Sturdy", -1),            # halved: 30 -> 15, under Geodude's 19
])
def test_ai_speed_order_sees_speed_items(poke, ai_item, u_item, u_ab, expected):
    """pokeplatinum CompareBattlerSpeed as the AI calls it, with the order and speed items"""
    ai_pok = poke("Rattata", 20, "Run Away", ["Tackle"], item=ai_item)
    ai_pok[Pok.SPEED] = 30
    user = poke("Geodude", 20, u_ab, ["Tackle"], item=u_item)
    assert ai.ai_speed_order(ai_pok, user, 0, 0) == expected


def test_ai_speed_order_sees_quick_feet(poke):
    """The speed abilities reach the AI through check_speed"""
    ai_pok = poke("Geodude", 20, "Quick Feet", ["Tackle"])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    ai_pok[Pok.STATUS] = user[Pok.STATUS] = Status.PARALYSIS
    assert ai.ai_speed_order(ai_pok, user, 0, 0) == 1


@pytest.mark.parametrize("ai_side, user_side, trick_room, claw_guess, expected", [
    (0, 0, False, 0, -1),                                    # Geodude 30 under Rattata 50
    (SideCondition.TAILWIND, 0, False, 0, 1),                # 60 over 50
    (0, SideCondition.TAILWIND, False, 0, -1),
    (0, 0, True, 0, 1),                                      # the slower first
    (SideCondition.TAILWIND, 0, True, 0, -1),
    (0, 0, True, 3, -1),                                     # both guessed Quick Claws: speed
])
def test_ai_speed_order_sees_tailwind_and_trick_room(poke, ai_side, user_side, trick_room, claw_guess,
                                                     expected):
    """pokeplatinum CompareBattlerSpeed as the AI calls it: Tailwind doubles, Trick Room flips the
    last branch only"""
    ai_pok = poke("Geodude", 20, "Sturdy", ["Tackle"])
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    ai_pok[Pok.SPEED], user[Pok.SPEED] = 30, 50
    assert ai.ai_speed_order(ai_pok, user, 0, claw_guess, ai_side, user_side, trick_room) == expected


def _tr_pair(poke, move, ai_fast):
    """An AI faster (50 over 30) or slower than its target, holding move"""
    ai_pok = poke("Abra", 20, "Synchronize", [move])
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    ai_pok[Pok.SPEED], user[Pok.SPEED] = (50, 30) if ai_fast else (30, 50)
    return ai_pok, user


def _basic_tr(ai_pok, user, **kwargs):
    return ai.basic_flag(move_slice(ai_pok, 0), AbilityNames.RUN_AWAY, ai_pok, user, 1.0, 0, **kwargs)


@pytest.mark.parametrize("trick_room, ai_side, expected", [
    (False, 0, 0),
    (True, 0, -10),
    (False, SideCondition.TAILWIND, -10),
    (False, SideCondition.REFLECT, 0),
])
def test_basic_tailwind(poke, trick_room, ai_side, expected):
    """Pokemow Basic Tailwind and Check_TrickRoom (pokeplatinum Basic_CheckTailwind)"""
    ai_pok, user = _tr_pair(poke, "Tailwind", False)
    assert _basic_tr(ai_pok, user, ai_side=ai_side, trick_room=trick_room) == expected


@pytest.mark.parametrize("ai_fast, trick_room, expected", [
    (True, False, -10),
    (False, False, 0),
    (False, True, -10),     # it already moves first: Trick Room again would end it
    (True, True, 0),
])
def test_basic_trick_room(poke, ai_fast, trick_room, expected):
    """Pokemow Basic TrickRoom: -10 if the AI moves first"""
    ai_pok, user = _tr_pair(poke, "Trick Room", ai_fast)
    assert _basic_tr(ai_pok, user, trick_room=trick_room) == expected


def test_basic_trick_room_speed_tie_is_half(poke):
    """Pokemow Basic TrickRoom: a speed tie is -10 half the time"""
    ai_pok, user = _tr_pair(poke, "Trick Room", True)
    user[Pok.SPEED] = ai_pok[Pok.SPEED]
    assert {_basic_tr(ai_pok, user) for _ in range(100)} == {0, -10}


@pytest.mark.parametrize("move, expected", [
    ("Agility", -10), ("Rock Polish", -10), ("Cotton Spore", -10), ("Scary Face", -10),
    ("String Shot", -10), ("Dragon Dance", -10), ("Swords Dance", 0), ("Growl", 0),
])
def test_basic_speed_moves_under_trick_room(poke, move, expected):
    """Pokemow Check_TrickRoom on the moves that only raise the AI's Speed or only lower the
    target's, and Dragon Dance"""
    ai_pok, user = _tr_pair(poke, move, False)
    assert _basic_tr(ai_pok, user, trick_room=True) == expected
    assert _basic_tr(ai_pok, user) == 0


def _expert_tr(ai_pok, user, trick_room=False, ai_bench=1):
    rand = np.zeros((4, 5, 2), dtype=np.int16)
    score = ai.expert_flag(
        ai_pok, user, move_slice(ai_pok, 0), 1, 0, rand, 0, 0, 1.0, 0, ai_bench=ai_bench,
        trick_room=trick_room
    )
    return score, [tuple(int(x) for x in rand[0, i]) for i in range(5) if rand[0, i, 1]]


@pytest.mark.parametrize("ai_fast, hp_pct, expected", [
    (True, 100, (0, [(-1, 192)])),
    (False, 30, (0, [(-1, 192)])),
    (False, 31, (0, [(1, 144)])),
    (False, 75, (0, [(1, 144)])),
    (False, 76, (0, [(1, 192)])),
])
def test_expert_tailwind(poke, ai_fast, hp_pct, expected):
    """Pokemow / pokeplatinum Expert_Tailwind, its 25% of nothing folded into each chance"""
    ai_pok, user = _tr_pair(poke, "Tailwind", ai_fast)
    _set_hp_pct(ai_pok, hp_pct)
    assert _expert_tr(ai_pok, user) == expected


@pytest.mark.parametrize("ai_fast, hp_pct, ai_bench, trick_room, expected", [
    (False, 100, 1, False, (0, [(3, 192)])),
    (True, 100, 1, False, (-1, [])),
    (True, 100, 1, True, (0, [(3, 192)])),    # under Trick Room the faster one is second
    (False, 30, 0, False, (0, [])),
    (False, 30, 1, False, (0, [(3, 192)])),
    (True, 31, 0, False, (-1, [])),
])
def test_expert_trick_room(poke, ai_fast, hp_pct, ai_bench, trick_room, expected):
    """Pokemow / pokeplatinum Expert_TrickRoom"""
    ai_pok, user = _tr_pair(poke, "Trick Room", ai_fast)
    _set_hp_pct(ai_pok, hp_pct)
    assert _expert_tr(ai_pok, user, trick_room, ai_bench) == expected


def test_ai_move_view_gyro_ball_sees_tailwind(poke):
    """The AI's Gyro Ball power reads monSpeedValues, Tailwind included (pokeplatinum)"""
    gyro = poke("Bronzor", 20, "Levitate", ["Gyro Ball"])
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    gyro[Pok.SPEED], user[Pok.SPEED] = 20, 40
    mv = move_slice(gyro, 0)
    assert ai.ai_move_view(mv, gyro, user)[Move.POWER] == 51
    assert ai.ai_move_view(mv, gyro, user, 0, 0, SideCondition.TAILWIND)[Move.POWER] == 101
    assert ai.ai_move_view(mv, gyro, user, 0, SideCondition.TAILWIND, 0)[Move.POWER] == 26


def test_ai_reads_trick_room_from_the_field(make_pokemon, make_battle):
    """return_idx passes Trick Room on: a slower Abra under it never picks Trick Room (-10)"""
    arr = make_battle([make_pokemon("Rattata", 30, "Run Away", ["Tackle"])],
                      [make_pokemon("Geodude", 10, "Sturdy", ["Trick Room", "Tackle"])])
    arr[Field.TRICKROOM] = 3
    for _ in range(20):
        assert return_idx(arr) == 1


def test_quick_claw_guess(monkeypatch, poke):
    """One bit per holder, and no RNG call when nobody holds a Quick Claw"""
    plain = poke("Geodude", 20, "Sturdy", ["Tackle"])
    claw = poke("Rattata", 20, "Run Away", ["Tackle"], item="Quick Claw")
    state = ai.random.getstate()
    assert ai.quick_claw_guess(plain, plain) == 0
    assert ai.random.getstate() == state
    monkeypatch.setattr(ai.random, "randint", lambda lo, hi: 0)
    assert ai.quick_claw_guess(plain, claw) == 2
    assert ai.quick_claw_guess(claw, claw) == 3


# ── Batch 15: Normalize ──────────────────────────────────────────────────────

def test_ai_effectiveness_normalize(poke):
    """pokeplatinum's AI runs ApplyTypeChart with the attacker's Normalize: STAB on Skitty's
    neutral Ember, nothing into a Ghost"""
    plain = poke("Skitty", 30, "Cute Charm", ["Ember"])
    norm = poke("Skitty", 30, "Normalize", ["Ember"])
    grass = poke("Bulbasaur", 30, "Overgrow", ["Tackle"])
    assert ai.trainer_ai_effectiveness(move_slice(plain, 0), plain, grass)[0] == 2.0
    assert ai.trainer_ai_effectiveness(move_slice(norm, 0), norm, grass)[0] == 1.5
    ghost = poke("Gastly", 30, "Levitate", ["Lick"])
    assert ai.trainer_ai_effectiveness(move_slice(norm, 0), norm, ghost)[0] == 0


@pytest.mark.parametrize("ability, has_se", [("Cute Charm", True), ("Normalize", False)])
def test_party_checks_see_normalize(poke, ability, has_se):
    """BattleSystem_CalcEffectiveness takes the party member's ability: a Normalize Ember isn't
    super effective"""
    party = np.zeros(6 * POK_LEN, dtype=np.int32)
    party[:POK_LEN] = poke("Machop", 20, "Guts", ["Leer"])
    party[POK_LEN:2 * POK_LEN] = poke("Skitty", 20, ability, ["Ember"])
    grass = poke("Bulbasaur", 20, "Overgrow", ["Tackle"])
    assert (1 in ai.check_super_ef_move_pty(party, grass, 0)) == has_se


def test_ineffective_moves_withdraw_scans_count_only_damaging_moves(poke):
    """Pokemow: the ineffective-moves withdraw only counts a bench member's damaging moves, the
    Wonder Guard one counts any move (Taunt can trigger it)"""
    party = np.zeros(6 * POK_LEN, dtype=np.int32)
    party[:POK_LEN] = poke("Machop", 20, "Guts", ["Karate Chop"])
    party[POK_LEN:2 * POK_LEN] = poke("Murkrow", 20, "Insomnia", ["Taunt", "Growl"])
    psychic = poke("Abra", 20, "Synchronize", ["Teleport"])
    assert list(ai.check_super_ef_move_pty(party, psychic, 0)) == [1]
    assert list(ai.check_super_ef_move_pty(party, psychic, 0, False, True)) == []
    assert list(ai.check_any_damaging_move_pty(party, psychic, 0)) == []


# ── Substitute ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("sub_up, hp_pct, expected", [
    (True, 100, -8), (False, 25, -10), (False, 26, 0),
])
def test_basic_substitute(poke, sub_up, hp_pct, expected):
    """pokeplatinum Basic_CheckCannotSubstitute: -8 behind one, -10 under 26% HP"""
    ai_pok = poke("Machop", 20, "Guts", ["Substitute"])
    ai_pok[Pok.MAX_HP], ai_pok[Pok.CURRENT_HP] = 100, hp_pct
    if sub_up:
        ai_pok[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
        ai_pok[Pok.SUB_HP] = 25
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    score = ai.basic_flag(move_slice(ai_pok, 0), AbilityNames.RUN_AWAY, ai_pok, user, 1.0, 0)
    assert score == expected


@pytest.mark.parametrize("ai_moves, hp_pct, expected", [
    (["Substitute"], 100, []),
    (["Substitute", "Focus Punch"], 100, [(1, 160)]),
    (["Substitute"], 91, []),
    (["Substitute"], 90, [(-1, 156)]),
    (["Substitute"], 70, [(-1, 156), (-1, 156)]),
    (["Substitute"], 50, [(-1, 156), (-1, 156), (-1, 156)]),
])
def test_expert_substitute_hp_rolls(poke, ai_moves, hp_pct, expected):
    """pokeplatinum / Pokemow Expert_Substitute: Focus Punch, then one roll per HP threshold"""
    ai_pok = poke("Machop", 40, "Guts", ai_moves)
    ai_pok[Pok.MAX_HP], ai_pok[Pok.CURRENT_HP] = 100, hp_pct
    user = poke("Rattata", 5, "Run Away", ["Tackle"])
    assert _expert_field(ai_pok, user, MoveName.TACKLE) == (0, expected)


@pytest.mark.parametrize("last, user_status, user_vol, ai_lv, expected", [
    ("Thunder Wave", 0, 0, 40, [(1, 156)]),
    ("Thunder Wave", Status.PARALYSIS, 0, 40, []),
    ("Thunder Wave", 0, 0, 5, []),                 # the AI moves second
    ("Will-O-Wisp", 0, 0, 40, [(1, 156)]),
    ("Confuse Ray", 0, 0, 40, [(1, 156)]),
    ("Confuse Ray", 0, VolStatus.CONFUSION, 40, []),
    ("Leech Seed", 0, 0, 40, [(1, 156)]),
    ("Leech Seed", 0, VolStatus.LEECH_SEED, 40, []),
    ("Swagger", 0, 0, 40, []),                     # not BATTLE_EFFECT_STATUS_CONFUSE
    ("Tackle", 0, 0, 40, []),
])
def test_expert_substitute_target_last_move(poke, last, user_status, user_vol, ai_lv, expected):
    """Moving first, +1 when the target's last status move didn't stick"""
    ai_pok = poke("Machop", ai_lv, "Guts", ["Substitute"])
    user = poke("Rattata", 20, "Run Away", [last])
    user[Pok.STATUS] = user_status
    user[Pok.VOL_STATUS] = user_vol
    assert _expert_field(ai_pok, user, getattr(MoveName, last.upper().replace(" ", "_")
                                               .replace("-", "_"))) == (0, expected)


def test_quick_claw_guess_counts_custap(poke):
    """A Custap holder in a pinch always counts as an activated Quick Claw, no RNG (pokeplatinum
    CompareBattlerSpeed)"""
    plain = poke("Geodude", 20, "Sturdy", ["Tackle"])
    custap = poke("Rattata", 20, "Run Away", ["Tackle"], item="Custap Berry")
    assert ai.quick_claw_guess(plain, custap) == 0
    custap[Pok.CURRENT_HP] = custap[Pok.MAX_HP] // 4
    state = ai.random.getstate()
    assert ai.quick_claw_guess(custap, plain) == 1
    assert ai.random.getstate() == state
    assert custap[Item.ID] == ItemNames.CUSTAP_BERRY


# ── 4.5: Thief, Pluck, Trick, Switcheroo, Embargo, Fling ─────────────────────

def _item_poke(poke, species, ability, moves, item=""):
    return poke(species, 20, ability, moves, item=item)


def test_fling_is_left_out_of_the_damage_compare():
    """Pokemow's excluded moves"""
    assert MoveName.FLING in MOVE_EXCEP


@pytest.mark.parametrize("move", ["Trick", "Switcheroo"])
@pytest.mark.parametrize("user_ability, user_item, expected", [
    ("Sticky Hold", "Leftovers", -10), ("Sturdy", "", -10), ("Sturdy", "Leftovers", 0),
])
def test_basic_trick(poke, move, user_ability, user_item, expected):
    """Basic_CheckCanRemoveItem, shared with Knock Off"""
    ai_pok = _item_poke(poke, "Abra", "Synchronize", [move], "Everstone")
    user = _item_poke(poke, "Geodude", user_ability, ["Tackle"], user_item)
    ability = getattr(AbilityNames, user_ability.upper().replace(" ", "_"))
    assert _basic(ai_pok, user, ability) == expected


def test_basic_embargo(poke):
    """Basic_CheckEmbargo: -10 on a target already under it"""
    ai_pok = poke("Murkrow", 20, "Insomnia", ["Embargo"])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"], item="Leftovers")
    assert _basic(ai_pok, user, AbilityNames.STURDY) == 0
    user[Pok.VOL_STATUS2] |= VolStatus2.EMBARGO
    assert _basic(ai_pok, user, AbilityNames.STURDY) == -10


def _basic_fling(poke, item, user="Rattata", user_ability="Run Away", ai_species="Machop",
                 ai_ability="No Guard", user_side=0, ai_side=0):
    ai_pok = poke(ai_species, 20, ai_ability, ["Fling"], item=item)
    target = poke(user, 20, user_ability, ["Tackle"])
    ability = getattr(AbilityNames, user_ability.upper().replace(" ", "_"))
    return ai.basic_flag(
        move_slice(ai_pok, 0), ability, ai_pok, target, 1.0, 0, ai_side, user_side
    )


@pytest.mark.parametrize("kwargs, expected", [
    ({"item": ""}, -10),
    ({"item": "Iron Ball"}, 0),
    # The target can be poisoned: no change
    ({"item": "Toxic Orb"}, 0),
    # It can't, and neither can the AI: -5; the AI can: +3
    ({"item": "Toxic Orb", "user": "Grimer"}, 3),
    ({"item": "Poison Barb", "user": "Grimer", "ai_species": "Grimer"}, -5),
    ({"item": "Toxic Orb", "user": "Grimer", "ai_ability": "Guts"}, -5),
    ({"item": "Toxic Orb", "ai_ability": "Poison Heal"}, -5),
    ({"item": "Flame Orb", "user": "Ponyta"}, 3),
    ({"item": "Flame Orb", "user": "Ponyta", "ai_side": SideCondition.SAFEGUARD}, -5),
    ({"item": "Light Ball"}, 0),
    ({"item": "Light Ball", "user_ability": "Limber"}, -5),
    ({"item": "Light Ball", "user_side": SideCondition.SAFEGUARD}, -5),
])
def test_basic_fling(poke, kwargs, expected):
    """Pokemow Basic Fling"""
    assert _basic_fling(poke, **kwargs) == expected


def test_expert_thief_is_covets(poke):
    """Expert_Thief scores both: an item on the list is 80.5% of +1, anything else -2"""
    user = poke("Geodude", 20, "Sturdy", ["Tackle"], item="Leftovers")
    ai_pok = poke("Murkrow", 20, "Insomnia", ["Thief"])
    assert _expert(ai_pok, user) == (0, [(1, 206)])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"], item="Everstone")
    assert _expert(ai_pok, user) == (-2, [])


def test_expert_pluck_is_bug_bites(poke):
    """Expert_Pluck scores both: resisted -1, else 50% of +1 (75% more on the first turn)"""
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    ai_pok = poke("Starly", 20, "Keen Eye", ["Pluck"])
    assert _expert(ai_pok, user, 0.5) == (-1, [])
    ai_pok[Pok.TURNS] = 2
    assert _expert(ai_pok, user) == (0, [(1, 128)])


def test_expert_embargo(poke):
    """Expert_Embargo: 50% of +1"""
    ai_pok = poke("Murkrow", 20, "Insomnia", ["Embargo"])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert _expert(ai_pok, user) == (0, [(1, 128)])


@pytest.mark.parametrize("item, effectiveness, expected", [
    # Resisted: -1 unless the item has a good effect
    ("Iron Ball", 0.5, (-1, [])),
    ("King's Rock", 0.5, (0, [])),
    # By Fling power
    ("Oran Berry", 1.0, (-2, [])),
    ("Iron Ball", 2.0, (4, [(1, 192)])),
    ("Iron Ball", 1.0, (0, [(1, 128), (1, 192)])),
    ("Poison Barb", 1.0, (0, [(1, 192)])),
    ("Everstone", 1.0, (0, [(-1, 128)])),
])
def test_expert_fling(poke, item, effectiveness, expected):
    """Expert_Fling"""
    ai_pok = poke("Machop", 20, "Guts", ["Fling"], item=item)
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert _expert(ai_pok, user, effectiveness) == expected


def _expert_trick(poke, ai_item, user_item="", user="Rattata", user_ability="Run Away",
                  ai_species="Abra", ai_ability="Synchronize"):
    ai_pok = poke(ai_species, 20, ai_ability, ["Trick"], item=ai_item)
    target = poke(user, 20, user_ability, ["Tackle"], item=user_item)
    return _expert(ai_pok, target)


@pytest.mark.parametrize("kwargs, expected", [
    # A bad item on the target: -3 whatever the AI holds
    ({"ai_item": "Choice Scarf", "user_item": "Iron Ball"}, (-3, [])),
    ({"ai_item": "Choice Band"}, (5, [])),
    ({"ai_item": "Lagging Tail"}, (5, [])),
    ({"ai_item": "Power Weight"}, (5, [])),
    # Macho Brace is only on the bad-trade list
    ({"ai_item": "Macho Brace"}, (-3, [])),
    ({"ai_item": "Toxic Orb"}, (5, [])),
    ({"ai_item": "Toxic Orb", "user": "Grimer"}, (5, [])),
    ({"ai_item": "Toxic Orb", "user": "Grimer", "ai_species": "Magnemite"}, (-3, [])),
    ({"ai_item": "Flame Orb", "user": "Ponyta", "ai_species": "Ponyta"}, (-3, [])),
    ({"ai_item": "Black Sludge", "user": "Grimer"}, (5, [])),
    ({"ai_item": "Black Sludge", "user": "Grimer", "ai_species": "Grimer"}, (-3, [])),
    # A Magic Guard target sends the script to the Toxic Orb's AI checks (Pokemow agrees)
    ({"ai_item": "Black Sludge", "user": "Clefairy", "user_ability": "Magic Guard",
      "ai_species": "Magnemite"}, (-3, [])),
    ({"ai_item": "Figy Berry"}, (0, [(2, 206)])),
    ({"ai_item": "Figy Berry", "user_item": "Wiki Berry"}, (-3, [])),
    ({"ai_item": "Leftovers"}, (-3, [])),
    ({"ai_item": ""}, (-3, [])),
])
def test_expert_trick(poke, kwargs, expected):
    """Expert_Trick as Pokemow reads it"""
    assert _expert_trick(poke, **kwargs) == expected


def test_expert_trick_sees_through_embargo(poke):
    """LoadHeldItemEffect reads the raw item: an Embargoed Choice Scarf is still one to give away"""
    ai_pok = poke("Abra", 20, "Synchronize", ["Trick"], item="Choice Scarf")
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    ai_pok[Pok.VOL_STATUS2] |= VolStatus2.EMBARGO
    ai_pok[Item.HOLD_EFFECT] = 0
    assert _expert(ai_pok, user) == (5, [])


def test_switcheroo_shares_tricks_expert_check(poke):
    """Same battle effect, same check"""
    ai_pok = poke("Sneasel", 20, "Inner Focus", ["Switcheroo"], item="Choice Band")
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    assert _expert(ai_pok, user) == (5, [])


def test_encore_likes_the_item_moves():
    """Pokemow List_Encore has Trick, Switcheroo and Fling"""
    for move in (MoveName.TRICK, MoveName.SWITCHEROO, MoveName.FLING):
        assert move in ai.ENCORE_ENCOURAGED_M


# ── Phase 7.1: variable power ────────────────────────────────────────────────

@pytest.mark.parametrize("fast, hp_pct, expected", [
    (True, 34, (-1, [])), (True, 21, (0, [])), (True, 8, (0, [(1, 156)])),
    (True, 7, (1, [(1, 156)])), (False, 61, (-1, [])), (False, 41, (0, [])),
    (False, 40, (0, [(1, 156)])),
])
def test_expert_reversal_is_flails(poke, fast, hp_pct, expected):
    """pokeplatinum Expert_Reversal covers both moves"""
    ai_pok, user = _expert_at(poke, "Reversal", fast, hp_pct)
    assert _expert(ai_pok, user) == expected


@pytest.mark.parametrize("status, expected", [
    (0, 0), (Status.BURN, 1), (Status.POISON, 1), (Status.TOXIC, 1), (Status.PARALYSIS, 1),
    (Status.SLEEP, 0),
])
def test_expert_facade_reads_the_targets_status(poke, status, expected):
    """pokeplatinum Expert_Facade's quirk: the target's status, the AI's own doesn't count"""
    ai_pok = poke("Purugly", 30, "Thick Fat", ["Facade"])
    ai_pok[Pok.STATUS] = Status.BURN if not status else 0
    user = poke("Geodude", 30, "Sturdy", ["Tackle"])
    user[Pok.STATUS] = status
    assert _expert(ai_pok, user, 0.5) == (expected, [])


def test_expert_smelling_salts(poke):
    """pokeplatinum Expert_SmellingSalts: +1 on a paralyzed target, no resist check"""
    ai_pok = poke("Hariyama", 30, "Thick Fat", ["Smelling Salts"])
    user = poke("Geodude", 30, "Sturdy", ["Tackle"])
    assert _expert(ai_pok, user) == (0, [])
    user[Pok.STATUS] = Status.PARALYSIS
    assert _expert(ai_pok, user, 0.5) == (1, [])


def test_expert_wake_up_slap(poke):
    """pokeplatinum Expert_WakeUpSlap: -1 resisted, +1 on a sleeping target"""
    ai_pok = poke("Machoke", 30, "Guts", ["Wake-Up Slap"])
    user = poke("Geodude", 30, "Sturdy", ["Tackle"])
    assert _expert(ai_pok, user) == (0, [])
    user[Pok.STATUS] = Status.SLEEP
    assert _expert(ai_pok, user) == (1, [])
    assert _expert(ai_pok, user, 0.5) == (-1, [])


@pytest.mark.parametrize("move", ["Eruption", "Water Spout"])
@pytest.mark.parametrize("fast, target_pct, effectiveness, expected", [
    (True, 100, 0.5, -1), (True, 51, 1.0, 0), (True, 50, 1.0, -1),
    (False, 71, 1.0, 0), (False, 70, 1.0, -1),
])
def test_expert_water_spout_reads_the_targets_hp(poke, move, fast, target_pct, effectiveness, expected):
    """pokeplatinum Expert_WaterSpout's quirk: the target's HP, not the user's"""
    ai_pok, user = _expert_at(poke, move, fast, 1)
    user[Pok.MAX_HP] = 100
    user[Pok.CURRENT_HP] = target_pct
    assert _expert(ai_pok, user, effectiveness) == (expected, [])


@pytest.mark.parametrize("pp_left, ability, acc, ev, expected", [
    (1, "Sturdy", 0, 0, (3, [])),
    (2, "Sturdy", 0, 0, (1, [(1, 156)])),
    (3, "Sturdy", 0, 0, (0, [(1, 156)])),
    (5, "Sturdy", 0, 0, (0, [])),
    (5, "Pressure", 0, 0, (0, [(1, 226)])),
    (5, "Sturdy", 0, 3, (0, [(1, 156)])),
    (5, "Sturdy", -5, 0, (1, [(1, 156)])),
    (5, "Pressure", 0, 5, (1, [(1, 226), (1, 156)])),
])
def test_expert_trump_card(poke, pp_left, ability, acc, ev, expected):
    """pokeplatinum Expert_TrumpCard"""
    ai_pok = poke("Slowking", 30, "Oblivious", ["Trump Card"])
    move_slice(ai_pok, 0)[Move.PP] = pp_left
    ai_pok[Pok.ACCURACY_STAT_STAGE] = acc
    user = poke("Geodude", 30, ability, ["Tackle"])
    user[Pok.EVASION_STAT_STAGE] = ev
    assert _expert(ai_pok, user) == expected
    assert _expert(ai_pok, user, 0.5) == (-1, [])


def test_expert_trump_card_uses_the_guessed_ability(poke):
    """The Pressure check reads the ability the AI sees"""
    ai_pok = poke("Slowking", 30, "Oblivious", ["Trump Card"])
    user = poke("Geodude", 30, "Sturdy", ["Tackle"])
    rand = np.zeros((4, 5, 2), dtype=np.int16)
    ai.expert_flag(ai_pok, user, move_slice(ai_pok, 0), 1, 0, rand, 0, 0, 1.0, 0,
                   ability=AbilityNames.PRESSURE)
    assert tuple(rand[0, 0]) == (1, 226)


@pytest.mark.parametrize("move", ["Wring Out", "Crush Grip"])
@pytest.mark.parametrize("fast, target_pct, effectiveness, expected", [
    (True, 100, 0.5, (-1, [])), (True, 49, 1.0, (-1, [])), (True, 50, 1.0, (0, [])),
    (True, 85, 1.0, (0, [])), (True, 86, 1.0, (0, [(1, 231)])),
    (True, 100, 1.0, (2, [(1, 231)])), (False, 100, 1.0, (1, [(1, 231)])),
])
def test_expert_wring_out(poke, move, fast, target_pct, effectiveness, expected):
    """pokeplatinum Expert_WringOut"""
    ai_pok, user = _expert_at(poke, move, fast, 100)
    user[Pok.MAX_HP] = 100
    user[Pok.CURRENT_HP] = target_pct
    assert _expert(ai_pok, user, effectiveness) == expected


@pytest.mark.parametrize("stages, queued", [
    ({Pok.ATTACK_STAT_STAGE: 2}, []),
    ({Pok.ATTACK_STAT_STAGE: 3}, [(1, 128)]),
    ({Pok.ATTACK_STAT_STAGE: 4}, [(1, 128)]),
    ({Pok.ATTACK_STAT_STAGE: 5}, [(2, 128), (1, 128)]),
    ({Pok.ATTACK_STAT_STAGE: 6}, [(3, 128), (2, 128), (1, 128)]),
    ({Pok.ATTACK_STAT_STAGE: 6, Pok.EVASION_STAT_STAGE: 1}, [(4, 128), (3, 128), (2, 128), (1, 128)]),
    ({Pok.ATTACK_STAT_STAGE: 6, Pok.DEFENSE_STAT_STAGE: -6}, [(3, 128), (2, 128), (1, 128)]),
])
def test_expert_punishment(poke, stages, queued):
    """pokeplatinum Expert_Punishment: each step falls through to the next, independent 50% rolls"""
    ai_pok = poke("Sneasel", 30, "Inner Focus", ["Punishment"])
    user = poke("Geodude", 30, "Sturdy", ["Tackle"])
    for stat, stage in stages.items():
        user[stat] = stage
    assert _expert(ai_pok, user) == (0, queued)
    assert _expert(ai_pok, user, 0.5) == (0, [])


@pytest.mark.parametrize("used, expected", [(0b001, -10), (0b011, 0)])
def test_basic_last_resort(poke, used, expected):
    """pokeplatinum Basic_CheckLastResort: -10 until it would work"""
    ai_pok = poke("Vaporeon", 30, "Water Absorb", ["Tackle", "Growl", "Last Resort"])
    ai_pok[Pok.LAST_RESORT] = used
    user = poke("Geodude", 30, "Sturdy", ["Tackle"])
    assert ai.basic_flag(move_slice(ai_pok, 2), AbilityNames.STURDY, ai_pok, user, 1.0, 0) == expected


@pytest.mark.parametrize("used, effectiveness, expected", [
    (0b001, 1.0, (0, [])), (0b011, 1.0, (1, [])), (0b011, 0.5, (-1, [])),
])
def test_expert_last_resort(poke, used, effectiveness, expected):
    """pokeplatinum Expert_LastResort: -1 resisted, +1 when it would work"""
    ai_pok = poke("Vaporeon", 30, "Water Absorb", ["Last Resort", "Tackle", "Growl"])
    ai_pok[Pok.LAST_RESORT] = used << 1
    user = poke("Geodude", 30, "Sturdy", ["Tackle"])
    assert _expert(ai_pok, user, effectiveness) == expected


# ── 7.2 fixed and HP-based damage ─────────────────────────────────────────────

def _set_hp_pct(pok, pct):
    """pct% of a 100 max HP"""
    pok[Pok.MAX_HP] = 100
    pok[Pok.CURRENT_HP] = pct


def test_fixed_damage_moves_skip_the_damage_compare():
    """pokeplatinum power 1 and Pokemow's excluded moves: Super Fang, Endeavor, Metal Burst"""
    assert {MoveName.SUPER_FANG, MoveName.ENDEAVOR, MoveName.METAL_BURST} <= set(MOVE_EXCEP)


def test_encore_likes_super_fang():
    """Pokemow List_Encore (pokeplatinum Expert_Encore_EncouragedMoveEffects BATTLE_EFFECT_HALVE_HP)"""
    assert MoveName.SUPER_FANG in ai.ENCORE_ENCOURAGED_M


@pytest.mark.parametrize("move", ["Super Fang", "Endeavor", "Metal Burst"])
@pytest.mark.parametrize("ability, effectiveness, expected", [
    (AbilityNames.LEVITATE, 0.0, -10),     # a Ghost: immune
    (AbilityNames.WONDER_GUARD, 1.0, -12),
])
def test_basic_fixed_damage_immunity_and_wonder_guard(poke, move, ability, effectiveness, expected):
    """Pokemow Check_DamageImmunity and Check_WonderGuard"""
    ai_pok = poke("Steelix", 5, "Sturdy", [move])
    user = poke("Raticate", 30, "Run Away", ["Tackle"])
    assert ai.basic_flag(move_slice(ai_pok, 0), ability, ai_pok, user, effectiveness, 0) == expected


@pytest.mark.parametrize("ai_level, ai_ability, ai_item, user_ability, user_item, expected", [
    (5, "Sturdy", None, AbilityNames.RUN_AWAY, 0, 0),                          # AI slower
    (50, "Sturdy", None, AbilityNames.RUN_AWAY, 0, -10),                       # AI faster
    (5, "Sturdy", None, AbilityNames.STALL, 0, -10),                           # Stall target
    (5, "Sturdy", None, AbilityNames.RUN_AWAY, ItemNames.SHINY_STONE, -10),    # [pp] bug, copied
    (50, "Sturdy", "Shiny Stone", AbilityNames.RUN_AWAY, 0, 0),                # AI's own: no check
])
def test_basic_metal_burst(make_pokemon, poke, ai_level, ai_ability, ai_item, user_ability,
                           user_item, expected):
    """pokeplatinum Basic_CheckMetalBurst"""
    ai_pok = make_pokemon("Steelix", ai_level, ai_ability, ["Metal Burst"], item=ai_item).to_np()
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    user[Pok.ITEM_ID] = user_item
    assert ai.basic_flag(move_slice(ai_pok, 0), user_ability, ai_pok, user, 1.0, 0) == expected


@pytest.mark.parametrize("target_pct, expected", [(50, (-1, [])), (51, (0, []))])
def test_expert_super_fang(poke, target_pct, expected):
    """pokeplatinum Expert_SuperFang: -1 at 50% HP or less"""
    ai_pok = poke("Raticate", 20, "Run Away", ["Super Fang"])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    _set_hp_pct(user, target_pct)
    assert _expert(ai_pok, user) == expected


@pytest.mark.parametrize("move, faster, target_pct, ai_pct, expected", [
    ("Endeavor", True, 69, 10, -1),     # target under 70%
    ("Endeavor", True, 100, 41, -1),    # faster: above 40%
    ("Endeavor", True, 100, 40, 1),
    ("Endeavor", False, 100, 51, -1),   # slower: above 50%
    ("Endeavor", False, 100, 50, 1),
    ("Pain Split", True, 79, 10, -1),   # target under 80%
    ("Pain Split", True, 100, 41, -1),
    ("Pain Split", True, 100, 40, 1),
    ("Pain Split", False, 100, 61, -1),  # slower: above 60%
    ("Pain Split", False, 100, 60, 1),
])
def test_expert_endeavor_pain_split(poke, move, faster, target_pct, ai_pct, expected):
    """pokeplatinum Expert_Endeavor / Expert_PainSplit, Pokemow agrees"""
    ai_pok = poke("Raticate" if faster else "Wobbuffet", 20, "Run Away", [move])
    user = poke("Machop", 20, "Guts", ["Tackle"])
    _set_hp_pct(user, target_pct)
    _set_hp_pct(ai_pok, ai_pct)
    assert _expert(ai_pok, user) == (expected, [])


def _expert_burst(ai_pok, user, my_last_move=0, ai_know=0):
    rand = np.zeros((4, 6, 2), dtype=np.int16)
    score = ai.expert_flag(
        ai_pok, user, move_slice(ai_pok, 0), 1, 0, rand, 0, my_last_move, 1.0, 0, ai_know
    )
    return score, [tuple(int(x) for x in rand[0, i]) for i in range(6) if rand[0, i, 1]]


def test_expert_metal_burst(poke):
    """pokeplatinum Expert_MetalBurst, Pokemow agrees"""
    ai_pok = poke("Steelix", 20, "Sturdy", ["Metal Burst"])
    user = poke("Machop", 20, "Guts", ["Focus Punch", "Tackle"])
    assert _expert_burst(ai_pok, user) == (0, [(1, 64)])
    _set_hp_pct(ai_pok, 50)
    assert _expert_burst(ai_pok, user) == (0, [(-1, 156), (1, 64)])
    _set_hp_pct(ai_pok, 30)
    assert _expert_burst(ai_pok, user) == (0, [(-1, 246), (-1, 156), (1, 64)])
    user[Pok.VOL_STATUS] = VolStatus.TAUNT
    # Taunted: +1 more if its last move deals damage, and +1 again
    assert _expert_burst(ai_pok, user, MoveName.TACKLE) == (
        0, [(-1, 246), (-1, 156), (1, 64), (1, 156), (1, 156)])
    assert _expert_burst(ai_pok, user, MoveName.GROWL) == (
        0, [(-1, 246), (-1, 156), (1, 64), (1, 156)])
    # Seen using Focus Punch, or asleep: -1
    assert _expert_burst(ai_pok, user, 0, Enemy_AI_Knows.MOVE1) == (-1, [])
    user[Pok.STATUS] = Status.SLEEP
    assert _expert_burst(ai_pok, user) == (-1, [])


def _expert_turn(ai_pok, user, effectiveness=1.0):
    rand = np.zeros((4, 6, 2), dtype=np.int16)
    score = ai.expert_flag(ai_pok, user, move_slice(ai_pok, 0), 1, 0, rand, 0, 0, effectiveness, 0)
    return score, [tuple(int(x) for x in rand[0, i]) for i in range(6) if rand[0, i, 1]]


@pytest.mark.parametrize("move", ["Revenge", "Avalanche"])
def test_expert_revenge(poke, move):
    """pokeplatinum Expert_Revenge, Avalanche shares its effect: -2 into a sleeping, infatuated or
    confused target, else 180/256 of -2 and 76/256 of +2"""
    ai_pok = poke("Hariyama", 20, "Thick Fat", [move])
    user = poke("Machop", 20, "Guts", ["Tackle"])
    assert _expert_turn(ai_pok, user) == (-2, [(4, 76)])
    user[Pok.VOL_STATUS] = VolStatus.CONFUSION
    assert _expert_turn(ai_pok, user) == (-2, [])


def test_expert_focus_punch(poke):
    """pokeplatinum Expert_FocusPunch"""
    ai_pok = poke("Machop", 20, "Guts", ["Focus Punch"])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert _expert_turn(ai_pok, user, 0.5) == (-1, [])
    # First turn in battle: nothing, after it 56/256 of +1
    ai_pok[Pok.TURNS_ACTIVE] = 1
    assert _expert_turn(ai_pok, user) == (0, [])
    ai_pok[Pok.TURNS_ACTIVE] = 2
    assert _expert_turn(ai_pok, user) == (0, [(1, 56)])
    user[Pok.VOL_STATUS] = VolStatus.ATTRACT
    assert _expert_turn(ai_pok, user) == (0, [(1, 156)])
    user[Pok.STATUS] = Status.SLEEP
    assert _expert_turn(ai_pok, user) == (1, [])
    ai_pok[Pok.VOL_STATUS2] |= VolStatus2.SUBSTITUTE
    assert _expert_turn(ai_pok, user) == (5, [])


def test_expert_payback(poke):
    """pokeplatinum Expert_Payback: slower with 30% HP or more, 192/256 of +1"""
    slow = poke("Steelix", 20, "Sturdy", ["Payback"])
    fast = poke("Raticate", 20, "Run Away", ["Payback"])
    user = poke("Machop", 20, "Guts", ["Tackle"])
    assert _expert_turn(slow, user, 0.5) == (-1, [])
    assert _expert_turn(slow, user) == (0, [(1, 192)])
    assert _expert_turn(fast, user) == (0, [])
    _set_hp_pct(slow, 29)
    assert _expert_turn(slow, user) == (0, [])


def test_expert_sucker_punch(poke):
    """pokeplatinum Expert_SuckerPunch: -1 if resisted, else 192/256 of +1"""
    ai_pok = poke("Raticate", 20, "Run Away", ["Sucker Punch"])
    user = poke("Machop", 20, "Guts", ["Tackle"])
    assert _expert_turn(ai_pok, user, 0.5) == (-1, [])
    assert _expert_turn(ai_pok, user) == (0, [(1, 192)])


def test_ai_scores_metal_burst_into_a_4x_target(make_pokemon, make_battle):
    """6 queued rolls (the 4x bonus plus every Metal Burst one) fit in the roll slots"""
    arr = make_battle([make_pokemon("Glalie", 20, "Inner Focus", ["Tackle"])],
                      [make_pokemon("Steelix", 20, "Sturdy", ["Metal Burst"])])
    my_active(arr)[Pok.VOL_STATUS] = VolStatus.TAUNT
    arr[Field.MY_LAST_MOVE] = MoveName.TACKLE
    foe = opp_active(arr)
    foe[Pok.CURRENT_HP] = foe[Pok.MAX_HP] * 3 // 10
    assert all(int(return_idx(arr)) == 0 for _ in range(20))


# ── 8.2 status and sleep ─────────────────────────────────────────────────────

def _basic_side(ai_pok, user, ability, user_side=0):
    """_basic with the target's Field.SIDE_COND"""
    return ai.basic_flag(move_slice(ai_pok, 0), ability, ai_pok, user, 1.0, 0, 0, user_side)


@pytest.mark.parametrize("move, ai_asleep, user_asleep, user_vol, ability, expected", [
    ("Dream Eater", False, True, 0, "STURDY", 0),
    ("Dream Eater", False, False, 0, "STURDY", -8),
    ("Snore", True, False, 0, "STURDY", 0),
    ("Snore", False, False, 0, "STURDY", -8),
    ("Snore", True, False, 0, "SOUNDPROOF", -10),
    ("Sleep Talk", True, False, 0, "STURDY", 0),
    ("Sleep Talk", False, False, 0, "STURDY", -8),
    ("Nightmare", False, True, 0, "STURDY", 0),
    ("Nightmare", False, True, VolStatus.NIGHTMARE, "STURDY", -10),
    ("Nightmare", False, False, 0, "STURDY", -8),
    ("Nightmare", False, True, 0, "MAGIC_GUARD", -10),
])
def test_basic_sleep_moves(poke, move, ai_asleep, user_asleep, user_vol, ability, expected):
    """Basic_CheckDreamEater, Basic_CheckAttackerAsleep (Snore after the Soundproof check, Sleep
    Talk) and Basic_CheckNightmare"""
    ai_pok = poke("Drowzee", 20, "Insomnia", [move])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    if ai_asleep:
        ai_pok[Pok.STATUS] = Status.SLEEP
    if user_asleep:
        user[Pok.STATUS] = Status.SLEEP
    user[Pok.VOL_STATUS] |= user_vol
    assert _basic(ai_pok, user, getattr(AbilityNames, ability)) == expected


def test_basic_dream_eater_immune_target(poke):
    """The type immunity comes first: -10 on a sleeping Dark type"""
    ai_pok = poke("Drowzee", 20, "Insomnia", ["Dream Eater"])
    user = poke("Murkrow", 20, "Insomnia", ["Peck"])
    user[Pok.STATUS] = Status.SLEEP
    assert ai.basic_flag(move_slice(ai_pok, 0), AbilityNames.INSOMNIA, ai_pok, user, 0.0, 0) == -10


@pytest.mark.parametrize("status, user, ai_ab, ability, side, expected", [
    (0, ("Geodude", "Sturdy"), "Run Away", "STURDY", 0, -10),
    (Status.BURN, ("Geodude", "Sturdy"), "Run Away", "STURDY", 0, 0),
    (Status.BURN, ("Geodude", "Sturdy"), "Run Away", "STURDY", SideCondition.SAFEGUARD, -10),
    (Status.BURN, ("Ponyta", "Run Away"), "Run Away", "RUN_AWAY", 0, -10),
    (Status.BURN, ("Geodude", "Sturdy"), "Run Away", "WATER_VEIL", 0, -10),
    (Status.BURN, ("Geodude", "Sturdy"), "Run Away", "MAGIC_GUARD", 0, -10),
    (Status.POISON, ("Geodude", "Sturdy"), "Run Away", "STURDY", 0, 0),
    (Status.TOXIC, ("Geodude", "Sturdy"), "Poison Heal", "STURDY", 0, -10),
    (Status.POISON, ("Magnemite", "Sturdy"), "Run Away", "STURDY", 0, -10),
    (Status.TOXIC, ("Geodude", "Sturdy"), "Run Away", "IMMUNITY", 0, -10),
    (Status.PARALYSIS, ("Geodude", "Sturdy"), "Run Away", "LIMBER", 0, -10),
    (Status.PARALYSIS, ("Geodude", "Sturdy"), "Run Away", "STURDY", 0, 0),
    (Status.SLEEP, ("Geodude", "Sturdy"), "Run Away", "INSOMNIA", 0, 0),
])
def test_basic_psycho_shift(poke, status, user, ai_ab, ability, side, expected):
    """Basic_CheckCanPsychoShift and its per-status branches (no sleep branch)"""
    ai_pok = poke("Rattata", 20, ai_ab, ["Psycho Shift"])
    ai_pok[Pok.STATUS] = status
    target = poke(user[0], 20, user[1], ["Tackle"])
    assert _basic_side(ai_pok, target, getattr(AbilityNames, ability), side) == expected
    target[Pok.STATUS] = Status.POISON
    assert _basic_side(ai_pok, target, getattr(AbilityNames, ability), side) == -10


@pytest.mark.parametrize("move, asleep, expected", [
    ("Snore", False, (2, [])), ("Snore", True, (2, [])),
    ("Sleep Talk", True, (10, [])), ("Sleep Talk", False, (-5, [])),
])
def test_expert_snore_and_sleep_talk(poke, move, asleep, expected):
    """Snore's effect goes to Expert_Nightmare (+2), Expert_SleepTalk +10 asleep, else -5"""
    ai_pok = poke("Snorlax", 20, "Thick Fat", [move])
    if asleep:
        ai_pok[Pok.STATUS] = Status.SLEEP
    user = poke("Machop", 20, "Guts", ["Tackle"])
    assert _expert(ai_pok, user) == expected


def test_expert_nightmare_has_no_check(poke):
    """Nightmare has a Basic check but no Expert one"""
    ai_pok = poke("Gastly", 20, "Levitate", ["Nightmare"])
    user = poke("Machop", 20, "Guts", ["Tackle"])
    user[Pok.STATUS] = Status.SLEEP
    assert _expert(ai_pok, user) == (0, [])


@pytest.mark.parametrize("move", ["Heal Bell", "Aromatherapy"])
@pytest.mark.parametrize("own, bench, expected", [
    (0, False, -5), (Status.BURN, False, 0), (0, True, 0),
])
def test_expert_heal_bell(poke, move, own, bench, expected):
    """Expert_HealBell: -5 unless the AI or a living Pokemon on its bench has a status"""
    ai_pok = poke("Chansey", 20, "Natural Cure", [move])
    ai_pok[Pok.STATUS] = own
    user = poke("Machop", 20, "Guts", ["Tackle"])
    rand = np.zeros((4, 5, 2), dtype=np.int16)
    score = ai.expert_flag(
        ai_pok, user, move_slice(ai_pok, 0), 1, 0, rand, 0, 0, 1.0, 0, ai_bench_status=bench
    )
    assert score == expected


def test_choose_move_sees_a_statused_bench(make_pokemon, make_battle):
    """Heal Bell is picked for a burned bench Pokemon, not with a healthy one (fainted ones don't
    count)"""
    def _battle(status, bench_hp):
        arr = make_battle([make_pokemon("Machop", 20, "Guts", ["Leer"])],
                          [make_pokemon("Chansey", 20, "Natural Cure", ["Heal Bell", "Growl"]),
                           make_pokemon("Rattata", 20, "Run Away", ["Tackle"])])
        bench = pok_slice(arr, 1, opp=True)
        bench[Pok.STATUS] = status
        bench[Pok.CURRENT_HP] = bench_hp
        return arr
    assert any(int(return_idx(_battle(Status.BURN, 30))) == 0 for _ in range(10))
    assert all(int(return_idx(_battle(Status.BURN, 0))) == 1 for _ in range(10))
    assert all(int(return_idx(_battle(0, 30))) == 1 for _ in range(10))


@pytest.mark.parametrize("ai_status, user_hp, expected", [
    (0, 100, (-10, [])), (Status.BURN, 30, (0, [(1, 128)])), (Status.BURN, 29, (0, [])),
])
def test_expert_psycho_shift(poke, ai_status, user_hp, expected):
    """Expert_PsychoShift: -10 without a status, else 50% of +1 with the target at 30% HP or more"""
    ai_pok = poke("Rattata", 20, "Run Away", ["Psycho Shift"])
    ai_pok[Pok.STATUS] = ai_status
    user = poke("Machop", 20, "Guts", ["Tackle"])
    _at_pct(user, user_hp)
    assert _expert(ai_pok, user) == expected


@pytest.mark.parametrize("fast, hp_pct, roll, expected", [
    (True, 100, 0, (-8, [])),
    (True, 51, 0, (-3, [])),
    (True, 50, 70, (-3, [])), (True, 50, 69, (0, [(3, 246)])),
    (True, 40, 70, (-3, [])), (True, 39, 255, (0, [(3, 246)])),
    (False, 71, 0, (-3, [])),
    (False, 70, 50, (-3, [])), (False, 70, 49, (0, [(3, 246)])),
    (False, 59, 255, (0, [(3, 246)])),
])
def test_expert_rest(poke, monkeypatch, fast, hp_pct, roll, expected):
    """Expert_Rest: faster at full HP -8, over 50% -3, 40-50% 186/256 of -3; slower over 70% -3,
    60-70% 206/256 of -3; otherwise 246/256 of +3 (no Snatch in MoveDB)"""
    monkeypatch.setattr(ai.random, "getrandbits", lambda n: roll)
    ai_pok, user = _expert_at(poke, "Rest", fast, hp_pct)
    assert _expert(ai_pok, user) == expected


@pytest.mark.parametrize("hp_pct, queued", [
    (50, [(-3, 206), (-3, 206), (2, 196)]), (51, [(2, 196)]),
])
def test_expert_toxic(poke, hp_pct, queued):
    """Expert_ToxicLeechSeed: with a damaging move 206/256 of -3 for each side at 50% or less,
    knowing Protect 196/256 of +2"""
    ai_pok = poke("Gengar", 20, "Levitate", ["Toxic", "Shadow Ball", "Protect"])
    user = poke("Machop", 20, "Guts", ["Tackle"])
    _at_pct(ai_pok, hp_pct)
    _at_pct(user, hp_pct)
    assert _expert(ai_pok, user) == (0, queued)


def test_expert_worry_seed_into_a_known_rest(poke):
    """Pokemow Worry Seed: +1 more when the target was seen using Rest"""
    ai_pok = poke("Bulbasaur", 20, "Overgrow", ["Worry Seed"])
    user = poke("Snorlax", 20, "Thick Fat", ["Tackle", "Rest"])
    _at_pct(user, 49)
    rand = np.zeros((4, 5, 2), dtype=np.int16)
    args = (ai_pok, user, move_slice(ai_pok, 0), 1, 0, rand, 0, 0, 1.0, 0)
    assert ai.expert_flag(*args, Enemy_AI_Knows.MOVE2) == 1
    assert ai.expert_flag(*args, Enemy_AI_Knows.MOVE1) == 0


def test_teeter_dance_has_no_ai_check(poke):
    """Pokemow and pokeplatinum give Teeter Dance no Basic and no Expert check"""
    ai_pok = poke("Spinda", 20, "Own Tempo", ["Teeter Dance"])
    user = poke("Machop", 20, "Guts", ["Tackle"])
    user[Pok.VOL_STATUS] |= VolStatus.CONFUSION
    assert _basic(ai_pok, user, AbilityNames.OWN_TEMPO) == 0
    assert _expert(ai_pok, user) == (0, [])


# ── 8.3 healing ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("move", [
    "Soft-Boiled", "Milk Drink", "Slack Off", "Heal Order", "Roost", "Moonlight", "Morning Sun",
])
def test_basic_recovery_new_moves(poke, move):
    """Basic_CheckCanRecoverHP for RESTORE_HALF_HP, Roost and HEAL_HALF_MORE_IN_SUN: -8 at full HP"""
    ai_pok = poke("Bulbasaur", 20, "Overgrow", [move])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert _basic(ai_pok, user, AbilityNames.STURDY) == -8
    ai_pok[Pok.CURRENT_HP] -= 1
    assert _basic(ai_pok, user, AbilityNames.STURDY) == 0


@pytest.mark.parametrize("move, weather, expected", [
    ("Roost", Weather.RAIN, (0, [(2, 236)])),
    ("Slack Off", Weather.HAIL, (0, [(2, 236)])),
    ("Moonlight", Weather.RAIN, (-2, [(2, 236)])),
    ("Morning Sun", Weather.SANDSTORM, (-2, [(2, 236)])),
    ("Moonlight", Weather.SUN, (0, [(2, 236)])),
])
def test_expert_recovery_new_moves(monkeypatch, poke, move, weather, expected):
    """Expert_Recovery for RESTORE_HALF_HP and Roost, Expert_Synthesis's weather -2 for Moonlight and
    Morning Sun"""
    monkeypatch.setattr(ai.random, "getrandbits", lambda k: 0)
    ai_pok = poke("Bulbasaur", 10, "Overgrow", [move])
    _at_pct(ai_pok, 60)
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert _expert_weather(ai_pok, user, weather) == expected


def test_basic_heal_block(poke):
    """Basic_CheckHealBlock: -10 on a target already under it"""
    ai_pok = poke("Abra", 20, "Synchronize", ["Heal Block"])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert _basic(ai_pok, user, AbilityNames.STURDY) == 0
    user[Pok.VOL_STATUS] |= VolStatus.HEAL_BLOCK
    assert _basic(ai_pok, user, AbilityNames.STURDY) == -10


@pytest.mark.parametrize("user_moves, seen, setup, roll, expected", [
    (["Recover"], Enemy_AI_Knows.MOVE1, None, 255, (0, [(1, 231)])),
    (["Giga Drain"], Enemy_AI_Knows.MOVE1, None, 255, (0, [(1, 231)])),
    (["Recover"], 0, None, 255, (0, [])),               # not seen yet
    (["Tackle"], 0, None, 95, (0, [(1, 231)])),          # the 96/256 roll
    (["Tackle"], 0, "ingrain", 255, (0, [(1, 231)])),
    (["Tackle"], 0, "seeded", 255, (0, [(1, 231)])),
])
def test_expert_heal_block(monkeypatch, poke, user_moves, seen, setup, roll, expected):
    """Pokemow Expert Heal Block: 231/256 of +1 with a seen healing or drain move, the target's
    Ingrain or Aqua Ring, or the AI seeded; otherwise 96/256, then 231/256"""
    monkeypatch.setattr(ai.random, "getrandbits", lambda k: roll)
    ai_pok = poke("Abra", 20, "Synchronize", ["Heal Block"])
    user = poke("Oddish", 20, "Chlorophyll", user_moves)
    if setup == "ingrain":
        user[Pok.VOL_STATUS] |= VolStatus.INGRAIN
    if setup == "seeded":
        ai_pok[Pok.VOL_STATUS] |= VolStatus.LEECH_SEED
    assert _expert_knows(ai_pok, user, seen) == expected


@pytest.mark.parametrize("move", ["Soft-Boiled", "Milk Drink", "Slack Off", "Heal Order"])
def test_expert_protect_sees_every_recover_move(poke, move):
    """Pokemow Expert Protect's list: Recover, Softboiled, Milk Drink, Slack Off, Heal Order"""
    ai_pok = poke("Rattata", 20, "Run Away", ["Protect"])
    user = poke("Machop", 20, "Guts", [move])
    assert _expert_knows(ai_pok, user, Enemy_AI_Knows.MOVE1) == (-2, [])


# ── 9.3 Spikes, Defog, Magnet Rise ───────────────────────────────────────────

@pytest.mark.parametrize("spikes, bench, expected", [(0, 1, 0), (2, 1, 0), (3, 1, -10), (0, 0, -10)])
def test_basic_spikes(poke, spikes, bench, expected):
    """pokeplatinum Basic_CheckSpikes: 3 layers or the target's last Pokemon"""
    ai_pok = poke("Geodude", 20, "Sturdy", ["Spikes"])
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    score = ai.basic_flag(
        move_slice(ai_pok, 0), AbilityNames.RUN_AWAY, ai_pok, user, 1.0, 0,
        user_side=SideCondition.SPIKES if spikes else 0, user_bench=bench, user_spikes=spikes
    )
    assert score == expected


@pytest.mark.parametrize("species, ability, risen, expected", [
    ("Magnemite", "Sturdy", False, 0),
    ("Magnemite", "Sturdy", True, -10),
    ("Gastly", "Levitate", False, -10),
    ("Pidgey", "Keen Eye", False, -10),
])
def test_basic_magnet_rise(poke, species, ability, risen, expected):
    """pokeplatinum Basic_CheckMagnetRise"""
    ai_pok = poke(species, 20, ability, ["Magnet Rise"])
    if risen:
        ai_pok[Pok.VOL_STATUS2] |= VolStatus2.MAGNET_RISE
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    score = ai.basic_flag(move_slice(ai_pok, 0), AbilityNames.RUN_AWAY, ai_pok, user, 1.0, 0)
    assert score == expected


@pytest.mark.parametrize("evasion, user_side, bench, expected", [
    (0, 0, 1, 0),                                       # evasion not at -6: no check
    (-6, SideCondition.REFLECT, 0, 0),                  # screens: no check
    (-6, 0, 1, -10),                                    # no hazards
    (-6, SideCondition.SPIKES, 1, 0),
    (-6, SideCondition.SPIKES, 0, -10),                 # last Pokemon
])
def test_basic_defog(poke, evasion, user_side, bench, expected):
    """pokeplatinum Basic_CheckDefog, Pokemow agrees"""
    ai_pok = poke("Pidgey", 20, "Keen Eye", ["Defog"])
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    user[Pok.EVASION_STAT_STAGE] = evasion
    score = ai.basic_flag(
        move_slice(ai_pok, 0), AbilityNames.RUN_AWAY, ai_pok, user, 1.0, 0,
        user_side=user_side, user_bench=bench
    )
    assert score == expected


@pytest.mark.parametrize("target, ai_hp, seen, expected", [
    ("Rattata", 100, 0, (0, [])),
    ("Rattata", 100, Enemy_AI_Knows.MOVE1, (1, [])),       # saw Earthquake
    ("Geodude", 100, 0, (0, [(1, 128)])),                 # Ground type: 50%
    ("Geodude", 100, Enemy_AI_Knows.MOVE1, (1, [(1, 128)])),
    ("Geodude", 49, Enemy_AI_Knows.MOVE1, (0, [])),       # under 50% HP
])
def test_expert_magnet_rise(poke, target, ai_hp, seen, expected):
    """Pokemow Expert MagnetRise"""
    ai_pok = poke("Magnemite", 20, "Sturdy", ["Magnet Rise"])
    ai_pok[Pok.MAX_HP], ai_pok[Pok.CURRENT_HP] = 100, ai_hp
    user = poke(target, 20, "Sturdy" if target == "Geodude" else "Run Away", ["Earthquake"])
    assert _expert_knows(ai_pok, user, seen) == expected


def _expert_defog(ai_hp, u_hp, user_side, ai_bench=1, evasion=0):
    ai_pok = poke_np("Pidgey", 20, "Keen Eye", ["Defog"])
    user = poke_np("Rattata", 20, "Run Away", ["Tackle"])
    ai_pok[Pok.MAX_HP], ai_pok[Pok.CURRENT_HP] = 100, ai_hp
    user[Pok.MAX_HP], user[Pok.CURRENT_HP] = 100, u_hp
    user[Pok.EVASION_STAT_STAGE] = evasion
    rand = np.zeros((4, 5, 2), dtype=np.int16)
    score = ai.expert_flag(
        ai_pok, user, move_slice(ai_pok, 0), 1, 0, rand, 0, 0, 1.0, 0, 0, user_side,
        ai_bench=ai_bench
    )
    queued = [tuple(int(x) for x in rand[0, i]) for i in range(5) if rand[0, i, 1]]
    return score, queued


REF = SideCondition.REFLECT
SPK = SideCondition.SPIKES


@pytest.mark.parametrize("args, expected", [
    ((100, 100, 0), (0, [])),
    ((100, 100, SPK), (-2, [])),                          # hazards, no screens
    ((60, 70, SPK), (-4, [(-2, 206)])),                   # low HP and a hurt foe
    ((100, 100, 0, 1, -3), (0, [(-2, 206)])),             # foe at -3 evasion
    ((100, 100, REF), (1, [])),                           # screens: +1
    ((100, 100, REF, 0), (1, [])),                        # +1, then stops on the last Pokemon
    ((100, 100, REF | SPK), (1, [(-1, 128)])),
    ((30, 70, REF, 0), (-2, [(-2, 206)])),                # 30% HP on the last Pokemon
    ((30, 100, REF, 1), (0, [(-2, 206)])),                # 30% HP with a bench: no +1
])
def test_expert_defog(args, expected):
    """Pokemow Expert Defog"""
    assert _expert_defog(*args) == expected


def test_expert_gravity_against_magnet_rise(poke):
    """pokeplatinum Expert_Gravity: 75% of +1 against a Magnet Rise target"""
    ai_pok = poke("Abra", 20, "Synchronize", ["Gravity"])
    user = poke("Rattata", 20, "Run Away", ["Tackle"])
    user[Pok.VOL_STATUS2] |= VolStatus2.MAGNET_RISE
    user[Pok.MAGNET_RISE_TURNS] = 3
    assert _expert(ai_pok, user) == (0, [(1, 192)])


def test_ai_sees_magnet_rise(poke):
    """Ground moves into Magnet Rise are immune for the AI's type check (ApplyTypeChart) and
    score -10, the bench check doesn't see it (CalcEffectiveness)"""
    ai_pok = poke("Geodude", 20, "Sturdy", ["Earthquake"])
    user = poke("Pikachu", 20, "Static", ["Tackle"])
    mv = move_slice(ai_pok, 0)
    assert ai.trainer_ai_effectiveness(mv, ai_pok, user)[0] == 2.0
    user[Pok.MAGNET_RISE_TURNS] = 3
    user[Pok.VOL_STATUS2] |= VolStatus2.MAGNET_RISE
    eff, _ = ai.trainer_ai_effectiveness(mv, ai_pok, user)
    assert eff == 0.0
    assert ai.basic_flag(mv, AbilityNames.STATIC, ai_pok, user, eff, 0) == -10
    assert ai.party_super_effective(Types.GROUND, ai_pok, user)


def test_magnet_rise_is_an_encore_target():
    """pokeplatinum Expert_Encore_EncouragedMoveEffects lists GIVE_GROUND_IMMUNITY"""
    assert MoveName.MAGNET_RISE in ai.ENCORE_ENCOURAGED_M


# ── 10.1 delayed effects ────────────────────────────────────────────────────

@pytest.mark.parametrize("move", ["Future Sight", "Doom Desire"])
@pytest.mark.parametrize("ai_side, user_side, expected", [
    (0, 0, 0), (SideCondition.FUTURE_SIGHT, 0, -12), (0, SideCondition.FUTURE_SIGHT, -12),
])
def test_basic_future_sight(poke, move, ai_side, user_side, expected):
    """pokeplatinum Basic_CheckFutureSight: -12 while one is waiting on either side"""
    ai_pok = poke("Abra", 20, "Synchronize", [move])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert ai.basic_flag(
        move_slice(ai_pok, 0), AbilityNames.STURDY, ai_pok, user, 1.0, 0, ai_side, user_side
    ) == expected


def test_basic_future_sight_into_dark_is_immune(poke):
    """The general immunity check comes first (Basic_CheckForImmunity), the hit itself is typeless"""
    ai_pok = poke("Abra", 20, "Synchronize", ["Future Sight"])
    user = poke("Murkrow", 20, "Insomnia", ["Peck"])
    eff, _ = ai.trainer_ai_effectiveness(move_slice(ai_pok, 0), ai_pok, user)
    assert eff == 0.0
    assert ai.basic_flag(move_slice(ai_pok, 0), AbilityNames.INSOMNIA, ai_pok, user, eff, 0) == -10


@pytest.mark.parametrize("count, expected", [(0, 0), (2, 0), (3, -10)])
def test_basic_stockpile(poke, count, expected):
    """pokeplatinum Basic_CheckMaxStockpile: -10 at 3"""
    ai_pok = poke("Swalot", 30, "Sticky Hold", ["Stockpile"])
    ai_pok[Pok.STOCKPILE] = count
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert _basic(ai_pok, user, AbilityNames.STURDY) == expected


@pytest.mark.parametrize("move, count, full_hp, ghost, expected", [
    ("Spit Up", 0, False, False, -10), ("Spit Up", 1, False, False, 0), ("Spit Up", 1, False, True, -10),
    ("Swallow", 0, False, False, -10), ("Swallow", 1, False, False, 0), ("Swallow", 1, True, False, -8),
    ("Swallow", 2, False, True, -10),
])
def test_basic_spit_up_swallow(poke, move, count, full_hp, ghost, expected):
    """pokeplatinum Basic_CheckCanSpitUpOrSwallow: -10 with nothing stockpiled or into a type immune to the
    move (Swallow too, a quirk), then Swallow's recovery check: -8 at full HP"""
    ai_pok = poke("Swalot", 30, "Sticky Hold", [move])
    ai_pok[Pok.STOCKPILE] = count
    if not full_hp:
        ai_pok[Pok.CURRENT_HP] -= 1
    user = poke("Gastly" if ghost else "Geodude", 20, "Levitate" if ghost else "Sturdy", ["Tackle"])
    ability = AbilityNames.LEVITATE if ghost else AbilityNames.STURDY
    eff, _ = ai.trainer_ai_effectiveness(move_slice(ai_pok, 0), ai_pok, user)
    assert ai.basic_flag(move_slice(ai_pok, 0), ability, ai_pok, user, eff, 0) == expected


@pytest.mark.parametrize("count, queued", [(1, []), (2, [(2, 176)]), (3, [(2, 176)])])
def test_expert_spit_up(poke, count, queued):
    """pokeplatinum Expert_SpitUp: 176/256 of +2 with 2 or more stockpiled"""
    ai_pok = poke("Swalot", 30, "Sticky Hold", ["Spit Up"])
    ai_pok[Pok.STOCKPILE] = count
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert _expert(ai_pok, user) == (0, queued)


def test_expert_swallow_is_a_recovery_move(poke):
    """pokeplatinum Expert_Recovery scores Swallow: -3 at full HP"""
    ai_pok = poke("Swalot", 30, "Sticky Hold", ["Swallow"])
    ai_pok[Pok.STOCKPILE] = 1
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert _expert(ai_pok, user) == (-3, [])


def test_delayed_effect_tables():
    """Doom Desire shares Future Sight's kill bonus, Spit Up is out of the damage compare, Swallow and Wish
    are Heal Block moves, and Expert Encore and Expert Heal Block see them (pokeplatinum script.s,
    sMovesAffectedByHealBlock)"""
    assert MoveName.DOOM_DESIRE in ai.FUTURE_ATTACK_MOVES
    assert MoveName.SPIT_UP in MOVE_EXCEP
    assert {MoveName.SWALLOW, MoveName.WISH} <= set(engine_helper.HEAL_BLOCK_MOVES)
    assert {MoveName.DOOM_DESIRE, MoveName.STOCKPILE, MoveName.SPIT_UP, MoveName.SWALLOW} <= set(
        ai.ENCORE_ENCOURAGED_M
    )
    assert MoveName.SWALLOW in ai.HEAL_BLOCK_GOOD_M


# ── Restriction and trapping ─────────────────────────────────────────────────

@pytest.mark.parametrize("move", ["Mean Look", "Block", "Spider Web"])
def test_basic_mean_look(poke, move):
    """Basic_CheckMeanLook: -10 on a target already under it, a bind doesn't count"""
    ai_pok = poke("Gastly", 20, "Levitate", [move])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    user[Pok.VOL_STATUS] = VolStatus.PARTIALLY_TRAPPED
    assert _basic(ai_pok, user, AbilityNames.STURDY) == 0
    user[Pok.VOL_STATUS2] = VolStatus2.MEAN_LOOK
    assert _basic(ai_pok, user, AbilityNames.STURDY) == -10


def test_basic_torment(poke):
    """Basic_CheckTorment: -10 on a target already under it"""
    ai_pok = poke("Murkrow", 20, "Insomnia", ["Torment"])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert _basic(ai_pok, user, AbilityNames.STURDY) == 0
    user[Pok.VOL_STATUS2] = VolStatus2.TORMENT
    assert _basic(ai_pok, user, AbilityNames.STURDY) == -10


def test_basic_imprison(poke):
    """Basic_CheckCanImprison: -10 while the AI already has it up. The target's
    MOVE_EFFECT_IMPRISONED half isn't kept, so no shared move still scores 0"""
    ai_pok = poke("Abra", 20, "Synchronize", ["Imprison"])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert _basic(ai_pok, user, AbilityNames.STURDY) == 0
    ai_pok[Pok.VOL_STATUS2] = VolStatus2.IMPRISON
    assert _basic(ai_pok, user, AbilityNames.STURDY) == -10


@pytest.mark.parametrize("turns_active, expected", [(2, [(2, 156)]), (1, [])])
def test_expert_imprison(poke, turns_active, expected):
    """Expert_Imprison: 156/256 of +2 when it isn't the AI's first turn"""
    ai_pok = poke("Abra", 20, "Synchronize", ["Imprison"])
    ai_pok[Pok.TURNS_ACTIVE] = turns_active
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert _expert(ai_pok, user) == (0, expected)


@pytest.mark.parametrize("move", ["Mean Look", "Block", "Spider Web"])
@pytest.mark.parametrize("status, vol, expected", [
    (0, 0, []), (Status.TOXIC, 0, [(1, 128)]), (0, VolStatus.CURSE, [(1, 128)]),
    (0, VolStatus.ATTRACT, [(1, 128)]), (0, VolStatus.PERISH_SONG, [(1, 128)]),
    (Status.POISON, 0, []),
])
def test_expert_mean_look(poke, move, status, vol, expected):
    """Expert_BindingMove: 50% +1 on a target badly poisoned, Cursed, attracted or under Perish
    Song"""
    ai_pok = poke("Gastly", 20, "Levitate", [move])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    user[Pok.STATUS] = status
    user[Pok.VOL_STATUS] = vol
    assert _expert(ai_pok, user) == (0, expected)


@pytest.mark.parametrize("move", ["Torment", "Spite"])
def test_expert_torment_and_spite_score_nothing(poke, move):
    """No Expert check of their own"""
    ai_pok = poke("Murkrow", 20, "Insomnia", [move])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert _expert(ai_pok, user) == (0, [])


@pytest.mark.parametrize("move", ["Mean Look", "Block", "Spider Web", "Torment", "Imprison"])
def test_expert_encore_likes_the_restricting_moves(poke, move):
    """They're on Pokemow List_Encore (pokeplatinum Expert_Encore_EncouragedMoveEffects)"""
    user = poke("Rattata", 30, "Run Away", ["Tackle", move])
    fast_ai = poke("Rattata", 60, "Run Away", ["Encore"])
    user[Pok.LAST_MOVE_ID] = move_slice(user, 1)[Move.ID]
    assert _expert(fast_ai, user) == (0, [(3, 226)])


def test_ai_never_picks_a_sealed_move(make_pokemon, make_battle):
    """My Imprison makes its Tackle invalid (CheckInvalidMoves in the AI's move loop)"""
    arr = make_battle(
        [make_pokemon("Murkrow", 20, "Insomnia", ["Imprison", "Tackle"])],
        [make_pokemon("Rattata", 20, "Run Away", ["Tackle", "Quick Attack"])],
    )
    my_active(arr)[Pok.VOL_STATUS2] = VolStatus2.IMPRISON
    random.seed(1)
    assert {return_idx(arr) for _ in range(30)} == {1}


def test_ai_never_picks_its_tormented_move(make_pokemon, make_battle):
    """Torment keeps its last move out of the loop"""
    arr = make_battle(
        [make_pokemon("Geodude", 20, "Sturdy", ["Tackle"])],
        [make_pokemon("Rattata", 20, "Run Away", ["Tackle", "Quick Attack"])],
    )
    foe = opp_active(arr)
    foe[Pok.VOL_STATUS2] = VolStatus2.TORMENT
    foe[Pok.LAST_MOVE_ID] = MoveName.QUICK_ATTACK
    random.seed(1)
    assert {return_idx(arr) for _ in range(30)} == {0}


def test_mean_looked_ai_never_switches(make_pokemon, make_battle):
    """TrainerAI_ShouldSwitch skips the withdraws for VOLATILE_CONDITION_TRAPPED, Mean Look too"""
    me = make_pokemon("Gastly", 20, "Levitate", ["Lick"])
    opp = [make_pokemon("Rattata", 20, "Run Away", ["Tackle", "Quick Attack"]),
           make_pokemon("Pikachu", 20, "Static", ["Thunder Shock"])]
    arr = make_battle([me], opp)
    pok_slice(arr, 0, opp=True)[Pok.VOL_STATUS2] = VolStatus2.MEAN_LOOK
    assert all(return_idx(arr) in (0, 1) for _ in range(30))


# ── 11.2 Accuracy locks and protection ───────────────────────────────────────

@pytest.mark.parametrize("move", ["Lock-On", "Mind Reader"])
@pytest.mark.parametrize("setup, expected", [
    (None, 0), ("locked", -10), ("ai_no_guard", -10), ("target_no_guard", -10),
])
def test_basic_lock_on(poke, move, setup, expected):
    """Basic_CheckLockOn (Mind Reader shares the effect): -10 on a target already locked onto, or with
    No Guard on either side"""
    ai_pok = poke("Machop", 20, "No Guard" if setup == "ai_no_guard" else "Guts", [move])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    if setup == "locked":
        ai_pok[Pok.VOL_STATUS2] = VolStatus2.LOCK_ON
    ability = AbilityNames.NO_GUARD if setup == "target_no_guard" else AbilityNames.STURDY
    assert _basic(ai_pok, user, ability) == expected


@pytest.mark.parametrize("move", ["Lock-On", "Mind Reader"])
def test_expert_lock_on(poke, move):
    """Expert_LockOn: 50% of +2"""
    ai_pok = poke("Machop", 20, "Guts", [move])
    user = poke("Geodude", 20, "Sturdy", ["Tackle"])
    assert _expert(ai_pok, user) == (0, [(2, 128)])


def test_basic_miracle_eye(poke):
    """Basic_CheckMiracleEye: -10 on a target already under it"""
    ai_pok = poke("Abra", 20, "Synchronize", ["Miracle Eye"])
    user = poke("Murkrow", 20, "Insomnia", ["Peck"])
    assert _basic(ai_pok, user, AbilityNames.INSOMNIA) == 0
    user[Pok.VOL_STATUS2] = VolStatus2.MIRACLE_EYE
    assert _basic(ai_pok, user, AbilityNames.INSOMNIA) == -10


@pytest.mark.parametrize("user, evasion, expected", [
    ("Murkrow", 0, (0, [(2, 121)])),     # Dark: two 176/256 gates
    ("Rattata", 3, (0, [(2, 176)])),
    ("Rattata", 2, (-2, [])),
])
def test_expert_miracle_eye(poke, user, evasion, expected):
    """Expert_MiracleEye: the target's Dark type, then its evasion at +3 or more, else -2"""
    ai_pok = poke("Abra", 20, "Synchronize", ["Miracle Eye"])
    target = poke(user, 20, "Insomnia" if user == "Murkrow" else "Run Away", ["Tackle"])
    target[Pok.EVASION_STAT_STAGE] = evasion
    assert _expert(ai_pok, target) == expected


@pytest.mark.parametrize("move", ["Protect", "Detect"])
def test_expert_protect_under_my_lock_on(poke, move):
    """Expert_Protect: locked onto, the AI wearing down ends with no change instead of -2, and the +2
    is sure (Expert_Protect_CheckAttackerLockedOnto)"""
    ai_pok = poke("Rattata", 20, "Run Away", [move])
    user = poke("Machop", 20, "Guts", ["Tackle"])
    user[Pok.VOL_STATUS2] = VolStatus2.LOCK_ON
    assert _expert_knows(ai_pok, user) == (2, [(-1, 128)])
    ai_pok[Pok.VOL_STATUS] = VolStatus.LEECH_SEED
    assert _expert_knows(ai_pok, user) == (0, [])


def test_detect_is_protect_for_the_ai():
    """IfMoveEffectKnown BATTLE_EFFECT_PROTECT covers both, and both are on Pokemow List_Encore with the
    other 11.2 moves"""
    assert MoveName.DETECT in ai.PROTECT_LIKE_M
    assert {MoveName.LOCK_ON, MoveName.MIND_READER, MoveName.DETECT, MoveName.MIRACLE_EYE} <= set(
        ai.ENCORE_ENCOURAGED_M
    )


def test_expert_feint_sees_detect(poke):
    """A Detect the AI saw counts like Protect for Feint"""
    ai_pok = poke("Rattata", 20, "Run Away", ["Feint"])
    user = poke("Machop", 20, "Guts", ["Detect"])
    _, queued = _expert_knows(ai_pok, user, Enemy_AI_Knows.MOVE1)
    assert (1, 128) in queued


@pytest.mark.parametrize("last, expected", [(None, [(1, 176)]), ("Lock-On", []), ("Mind Reader", [])])
def test_expert_bounce_after_my_lock_on(make_pokemon, poke, last, expected):
    """Expert_ChargeTurnWithInvuln_CompareSpeed: the faster AI skips its +1 when my last move was Lock-On
    or Mind Reader"""
    ai_pok = make_pokemon("Pidgey", 50, "Keen Eye", ["Bounce"]).to_np()
    user = poke("Rattata", 30, "Run Away", ["Tackle"])
    if last:
        user[Pok.LAST_MOVE_ID] = getattr(MoveName, last.upper().replace("-", "_").replace(" ", "_"))
    assert _expert(ai_pok, user) == (0, expected)
