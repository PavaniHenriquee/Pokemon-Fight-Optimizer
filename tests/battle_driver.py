"""Engine-only battle driver and fixed scenarios shared by the tests.

The driver only uses Engine/ and Models/ (turn_sim, switch_in_action, trainer AI), never
SearchEngine/, so the golden engine snapshots don't move when the search changes.
"""
import random
import numpy as np
from Models.pokemon import Pokemon
from Models.idx_const import POK_LEN, Pok, Move, MOVE_STRIDE, Field
from Models.helper import ActionType, BattlePhase, VolStatus, MoveCategory
from Models.constants import _POTIONS_POTION, _POTIONS_SUPER_POTION, _POTIONS_FULL_HEAL
from Models.trainer_ai import return_idx
from Utils.helper import to_battle_array
from Engine.engine_helper import start_of_battle
from Engine.battle import turn_sim, switch_in_action, baton_pass_action

MAX_TURNS = 400


def pok_slice(arr, slot, opp=False):
    """View of one Pokemon block, slot 0..5 on either side"""
    base = (slot + 6 if opp else slot) * POK_LEN
    return arr[base:base + POK_LEN]


def my_active(arr):
    """View of my active Pokemon"""
    return pok_slice(arr, int(arr[Field.MY_POK]))


def opp_active(arr):
    """View of the opponent active Pokemon"""
    return pok_slice(arr, int(arr[Field.OPP_POK]), opp=True)


def move_slice(pok, slot):
    """View of one move block inside a Pokemon block"""
    start = Pok.MOVE1_ID + slot * MOVE_STRIDE
    return pok[start:start + MOVE_STRIDE]


def alive_slots(arr, opp=False):
    """Party slots with HP left"""
    return [i for i in range(6) if pok_slice(arr, i, opp)[Pok.CURRENT_HP] > 0]


def is_over(arr):
    """Either side has nobody left"""
    return not alive_slots(arr) or not alive_slots(arr, opp=True)


def _blocked(active, i, mv):
    """Disable, Encore and Taunt (the slot is packed as turns * 4 + slot)"""
    vol = active[Pok.VOL_STATUS]
    if vol & VolStatus.DISABLE and i == active[Pok.DISABLE_TURNS] % 4:
        return True
    if vol & VolStatus.ENCORE and i != active[Pok.ENCORE_TURNS] % 4:
        return True
    return bool(vol & VolStatus.TAUNT and mv[Move.CATEGORY] == MoveCategory.STATUS)


def legal_actions(arr):
    """My legal actions, computed independently of SearchEngine.valid_action_mask"""
    me = int(arr[Field.MY_POK])
    switches = [(ActionType.SWITCH, i) for i in alive_slots(arr) if i != me]
    if arr[Field.PHASE] != BattlePhase.TURN_START:
        return switches
    active = my_active(arr)
    moves = []
    for i in range(4):
        mv = move_slice(active, i)
        if mv[Move.ID] == 0:
            break
        if mv[Move.PP] > 0 and not _blocked(active, i, mv):
            moves.append((ActionType.MOVE, i))
    if not moves:
        moves = [(ActionType.MOVE, 10)]
    if active[Pok.VOL_STATUS] & (VolStatus.INGRAIN | VolStatus.PARTIALLY_TRAPPED):
        return moves
    return moves + switches


def build(my_party, opp_party, trainer_items=()):
    """Battle array ready for turn 1, like main.py/backend do it"""
    arr = to_battle_array(my_party, opp_party)
    for i, item in enumerate(trainer_items):
        arr[Field.AI_ITEM1 + i] = item
    start_of_battle(arr)
    return arr


def play_turn(arr, action):
    """One decision of mine, including turns forced by a locked/charging move"""
    if arr[Field.PHASE] == BattlePhase.DEATH_END_OF_TURN:
        switch_in_action(arr, action[1])
        return
    if arr[Field.PHASE] == BattlePhase.BATON_PASS:
        baton_pass_action(arr, action[1])
        return
    opp_move = int(return_idx(arr))
    phase, _ = turn_sim(opp_move, action, arr)
    arr[Field.PHASE] = phase


def forced_action(arr):
    """Locked/charging move the engine expects me to keep using, or None"""
    if arr[Field.PHASE] != BattlePhase.TURN_START:
        return None
    active = my_active(arr)
    if active[Pok.LOCKED_MOVE] >= 0:
        return (ActionType.MOVE, int(active[Pok.LOCKED_MOVE]))
    return None


def play_battle(arr, seed, on_turn=None, max_turns=MAX_TURNS):
    """Play random legal actions until the battle ends. Returns the number of decisions"""
    random.seed(seed)
    np.random.seed(seed)
    turns = 0
    while not is_over(arr) and turns < max_turns:
        action = forced_action(arr) or random.choice(legal_actions(arr))
        play_turn(arr, action)
        turns += 1
        if on_turn is not None:
            on_turn(arr, action)
    return turns


# ── Scenarios ────────────────────────────────────────────────────────────────
# Fixed teams chosen to hit as many implemented mechanics as possible. Abilities don't
# have to be legal for the species. Changing a scenario changes its golden snapshot.

def _p(name, level, ability, moves, item=None, nature="Hardy", gender="Male"):
    return Pokemon(name, gender, level, ability, nature, moves, item=item)


def scenario_starters():
    """main.py's build_battle: basic damage, switching, trainer potion, Oran Berry"""
    my = [
        _p("Charmander", 5, "Blaze", ["Scratch", "Growl", "Ember"], item="Oran Berry"),
        _p("Bulbasaur", 5, "Overgrow", ["Pound", "Leer", "Razor Leaf"]),
        _p("Squirtle", 7, "Torrent", ["Tackle", "Tail Whip", "Bubble"]),
        _p("Charmeleon", 5, "Blaze", ["Scratch", "Growl"]),
        _p("Wartortle", 5, "Torrent", ["Tackle", "Tail Whip"]),
        _p("Ivysaur", 5, "Overgrow", ["Pound", "Leer"]),
    ]
    opp = [
        _p("Squirtle", 5, "Torrent", ["Tackle", "Tail Whip"]),
        _p("Charmander", 5, "Blaze", ["Scratch", "Growl"]),
    ]
    return my, opp, (_POTIONS_POTION,)


def scenario_status():
    """Paralysis, poison, sleep, confusion, Curse, Synchronize, Static, Magic Guard; AI status moves"""
    my = [
        _p("Pikachu", 12, "Static", ["Thunder Wave", "Thunder Shock", "Quick Attack", "Double Team"]),
        _p("Oddish", 12, "Chlorophyll", ["Poison Powder", "Sleep Powder", "Absorb", "Mega Drain"],
           item="Sitrus Berry"),
        _p("Ponyta", 12, "Flash Fire", ["Will-O-Wisp", "Ember", "Stomp", "Tail Whip"]),
    ]
    opp = [
        _p("Ralts", 12, "Synchronize", ["Confusion", "Hypnosis", "Thunder Wave", "Growl"]),
        _p("Gastly", 12, "Magic Guard", ["Lick", "Confuse Ray", "Curse", "Astonish"]),
        _p("Machop", 12, "Guts", ["Karate Chop", "Poison Powder", "Leer", "Force Palm"]),
    ]
    return my, opp, (_POTIONS_FULL_HEAL,)


def scenario_damage_sources():
    """Bide, Counter, Mirror Coat, Fake Out, priority, Intimidate, Iron Fist, Selfdestruct"""
    my = [
        _p("Geodude", 14, "Sturdy", ["Bide", "Defense Curl", "Rock Throw", "Selfdestruct"]),
        _p("Machop", 14, "Guts", ["Counter", "Karate Chop", "Focus Energy", "Force Palm"]),
        _p("Abra", 14, "Synchronize", ["Mirror Coat", "Confusion", "Dragon Rage", "Flash"]),
    ]
    opp = [
        _p("Chimchar", 14, "Iron Fist", ["Mach Punch", "Fire Punch", "Fake Out", "Leer"]),
        _p("Shinx", 14, "Intimidate", ["Bite", "Tackle", "Leer", "Spark"]),
        _p("Koffing", 14, "Aftermath", ["Selfdestruct", "Smog", "Tackle", "Smokescreen"]),
    ]
    return my, opp, (_POTIONS_SUPER_POTION, _POTIONS_POTION)


def scenario_multihit_items():
    """Multi-hit, Bug Bite, Covet, drain, Simple, Swift Swim, Rain Dance, berries; AI Swagger/Defense Curl"""
    my = [
        _p("Beedrill", 15, "Swarm", ["Twineedle", "Fury Attack", "Pin Missile", "Focus Energy"]),
        _p("Paras", 15, "Effect Spore", ["Bug Bite", "Absorb", "Stun Spore", "Fury Cutter"]),
        _p("Buizel", 15, "Swift Swim", ["Aqua Jet", "Water Gun", "Rain Dance", "Covet"]),
    ]
    opp = [
        _p("Bidoof", 15, "Simple", ["Tackle", "Growl", "Defense Curl", "Headbutt"], item="Oran Berry"),
        _p("Lotad", 15, "Rain Dish", ["Absorb", "Rain Dance", "Water Gun", "Growl"],
           item="Sitrus Berry"),
        _p("Starly", 15, "Keen Eye", ["Wing Attack", "Quick Attack", "Swagger", "Growl"]),
    ]
    return my, opp, ()


def scenario_weather_charge():
    """Sandstorm, Flail, Hyper Beam recharge, Dig charge, Hustle, Speed Boost, Water Absorb"""
    my = [
        _p("Rattata", 16, "Hustle", ["Hyper Fang", "Quick Attack", "Hyper Beam", "Dig"]),
        _p("Magikarp", 16, "Swift Swim", ["Flail", "Splash", "Tackle"], item="Sitrus Berry"),
        _p("Ninjask", 16, "Speed Boost", ["Fury Cutter", "Scratch", "Harden", "Sand Attack"]),
    ]
    opp = [
        _p("Hippopotas", 16, "Sand Veil", ["Sandstorm", "Bite", "Tackle", "Sand Attack"]),
        _p("Mudkip", 16, "Water Absorb", ["Water Gun", "Mud-Slap", "Growl", "Bide"]),
        _p("Onix", 16, "Rock Head", ["Rock Throw", "Rock Tomb", "Screech", "Harden"]),
    ]
    return my, opp, (_POTIONS_POTION,)


def scenario_switching():
    """Roar, Whirlwind, Baton Pass both ways, Pursuit on a switch, Teleport, Suction Cups, Ingrain,
    Stealth Rock on forced switch-ins"""
    my = [
        _p("Rattata", 14, "Run Away", ["Baton Pass", "Focus Energy", "Agility", "Tackle"]),
        _p("Geodude", 14, "Sturdy", ["Stealth Rock", "Roar", "Tackle", "Defense Curl"]),
        _p("Murkrow", 14, "Insomnia", ["Pursuit", "Peck", "Teleport", "Confuse Ray"]),
        _p("Zubat", 12, "Inner Focus", ["Whirlwind", "Bite", "Leech Seed"]),
    ]
    opp = [
        _p("Growlithe", 14, "Intimidate", ["Roar", "Ember", "Leer", "Bite"]),
        _p("Starly", 14, "Keen Eye", ["Pursuit", "Quick Attack", "Growl"]),
        _p("Ninjask", 14, "Speed Boost", ["Baton Pass", "Harden", "Agility", "Absorb"]),
        _p("Machop", 15, "Suction Cups", ["Whirlwind", "Low Kick", "Leer", "Ingrain"]),
    ]
    return my, opp, (_POTIONS_POTION,)


SCENARIOS = {
    "starters": scenario_starters,
    "status": scenario_status,
    "damage_sources": scenario_damage_sources,
    "multihit_items": scenario_multihit_items,
    "weather_charge": scenario_weather_charge,
    "switching": scenario_switching,
}


def build_scenario(name):
    """Fresh battle array for a named scenario"""
    my, opp, items = SCENARIOS[name]()
    return build(my, opp, items)
