"""Convert MCTS Node tree → JSON-serialisable dicts."""
from __future__ import annotations
import os
import sys
from Models.idx_const import (
    Pok, Move, Item, MOVE_STRIDE, POK_LEN, Field as FieldIdx, SIDE_REFLECT_TURNS,
    SIDE_LIGHT_SCREEN_TURNS, SIDE_MIST_TURNS, SIDE_SAFEGUARD_TURNS, SIDE_LUCKY_CHANT_TURNS,
    SIDE_TOXIC_SPIKES, SIDE_TAILWIND_TURNS, SIDE_SPIKES, SIDE_WISH_TURNS, SIDE_FUTURE_TURNS,
    SIDE_FUTURE_MOVE,
)
from Models.helper import (
    BattlePhase, Gender, VolStatus, VolStatus2, SideCondition, Weather, Types, MoveCategory,
)
from DataBase.PkDB import PokIdToName, battle_sprite_id
from Engine.engine_helper import CHOICE_EFFECTS, stockpile_count
from DataBase.MoveDB import MoveIdToName, MoveName
from DataBase.ItemDB import ItemNames as _ItemNameEnum
from DataBase.AbilitiesDB import AbilityNames
from DataBase.loader import moveDB as _moveDB
from SearchEngine.models import (
    BENCH_ITEM, OPP_DIDNT_MOVE, OPP_STRUGGLED, OPP_SWITCHED, OPP_USED_ITEM, opp_turns,
)


_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ─── display helpers ─────────────────────────────────────────────────────────

STATUS = {0: "", 1: "SLP", 2: "FRZ", 3: "PAR", 4: "BRN", 5: "PSN", 6: "TOX"}
_VOL_DISPLAY_OVERRIDES = {
    "CONFUSION": "Confused",
}
VOL_BITS = {
    v: _VOL_DISPLAY_OVERRIDES.get(k, k.replace("_", " ").title())
    for k, v in vars(VolStatus).items()
    if k.isupper() and isinstance(v, int)
}
VOL2_BITS = {
    v: k.replace("_", " ").title()
    for k, v in vars(VolStatus2).items()
    if k.isupper() and isinstance(v, int)
}
STAGE_NAMES = ["Atk", "Def", "SpA", "SpD", "Spe", "Acc", "Eva"]
_ITEM_ID_TO_NAME: dict[int, str] = {
    v: k.replace("_", " ").title()
    for k, v in vars(_ItemNameEnum).items()
    if isinstance(v, int)
}

_ABILITY_NAMES: dict[int, str] = {
    v: k.replace("_", " ").title()
    for k, v in vars(AbilityNames).items()
    if k.isupper() and isinstance(v, int)
}
_GENDER_NAMES = {Gender.MALE: "Male", Gender.FEMALE: "Female"}  # genderless: None, like a box entry

_TYPE_NAMES: dict[int, str] = {
    v: k.title() for k, v in vars(Types).items() if k.isupper() and isinstance(v, int)
}
_CATEGORY_NAMES: dict[int, str] = {
    v: k.title() for k, v in vars(MoveCategory).items() if k.isupper() and isinstance(v, int)
}

_POTION_ID_TO_NAME: dict[int, str] = {
    1: "Potion", 2: "Super Potion", 3: "Hyper Potion",
    4: "Full Restore", 5: "Full Heal",
    6: "X Special", 7: "X Defend", 8: "X Speed",
}

# Map move-ID → base PP from MoveDB.json (for the frontend PP display).
# Keyed by the entry's "name" like Models/move.py, so hyphenated keys (Mud-Slap) match too.
_MOVE_ID_TO_MAX_PP: dict[int, int] = {}
for _entry in _moveDB.values():
    _mid = getattr(MoveName, _entry["name"].upper(), None)
    if _mid is not None and "pp" in _entry:
        _MOVE_ID_TO_MAX_PP[_mid] = int(_entry["pp"])

_FLD_BASE = FieldIdx.MY_POK
_FLD_ITEMS = (FieldIdx.AI_ITEM1, FieldIdx.AI_ITEM2, FieldIdx.AI_ITEM3, FieldIdx.AI_ITEM4)

_WEATHER_NAMES = {
    Weather.SUN: "Sun", Weather.RAIN: "Rain", Weather.HAIL: "Hail",
    Weather.SANDSTORM: "Sandstorm",
}
# (bit, label, turns slot relative to SIDE_COND)
_SIDE_TIMERS = (
    (SideCondition.REFLECT, "Reflect", SIDE_REFLECT_TURNS),
    (SideCondition.LIGHT_SCREEN, "Light Screen", SIDE_LIGHT_SCREEN_TURNS),
    (SideCondition.MIST, "Mist", SIDE_MIST_TURNS),
    (SideCondition.SAFEGUARD, "Safeguard", SIDE_SAFEGUARD_TURNS),
    (SideCondition.TAILWIND, "Tailwind", SIDE_TAILWIND_TURNS),
    (SideCondition.LUCKY_CHANT, "Lucky Chant", SIDE_LUCKY_CHANT_TURNS),
    (SideCondition.WISH, "Wish", SIDE_WISH_TURNS),
)
_HAZARDS = (
    (SideCondition.STEALTH_ROCK, "Stealth Rock"),
    (SideCondition.SPIKES, "Spikes"),
    (SideCondition.TOXIC_SPIKES, "Toxic Spikes"),
)


def _move_fields(base_slice, offset: int) -> dict:
    """Live type, category and power of the move slot at offset (Hidden Power keeps its IV type)"""
    return {
        "type":     _TYPE_NAMES.get(int(base_slice[offset + Move.TYPE]), ""),
        "category": _CATEGORY_NAMES.get(int(base_slice[offset + Move.CATEGORY]), ""),
        "power":    int(base_slice[offset + Move.POWER]),
    }


def battle_sprite(arr) -> int:
    """The sprite id of a Pokemon's array slice, Castform's in its current form"""
    return battle_sprite_id(int(arr[Pok.ID]), _TYPE_NAMES.get(int(arr[Pok.TYPE1]), ""))


def _types(arr) -> list[str]:
    """Live types from the TYPE1 / TYPE2 slots (0 = no second type)"""
    out = []
    for t in (int(arr[Pok.TYPE1]), int(arr[Pok.TYPE2])):
        name = _TYPE_NAMES.get(t)
        if name and name not in out:
            out.append(name)
    return out


def _extract_moves(base_slice, current_pps=None) -> list[dict]:
    """
    Extract list of {'name': str, 'pp': int, 'max_pp': int}
    from a Pokemon array slice.
    """
    if base_slice is None or len(base_slice) < Pok.MOVE1_ID:
        return []
    moves = []
    for m in range(4):
        offset = Pok.MOVE1_ID + m * MOVE_STRIDE
        if offset + Move.ID >= len(base_slice):
            break
        move_id = int(base_slice[offset + Move.ID])
        if move_id == 0:
            continue
        move_name = MoveIdToName.get(move_id, f"Move#{move_id}").replace("_", " ").title()
        if current_pps is not None and m < len(current_pps):
            cur_pp = int(current_pps[m])
        else:
            cur_pp = int(base_slice[offset + Move.PP])
        base_pp = _MOVE_ID_TO_MAX_PP.get(move_id, cur_pp)
        pp_up = int(base_slice[offset + Move.PP_UP]) if offset + Move.PP_UP < len(base_slice) else 0
        max_pp = base_pp + (base_pp * pp_up * 2) // 10 if base_pp is not None else cur_pp
        moves.append({
            "name":   move_name,
            "pp":     cur_pp,
            "max_pp": max_pp,
            **_move_fields(base_slice, offset),
        })
    return moves


def _bench_entry(battle_array, snap, i: int, is_my: bool) -> dict | None:
    """One bench slot. Returns None for empty party slots (pok_id == 0)."""
    delta_i = i if is_my else i + 6
    base    = i * POK_LEN if is_my else (i + 6) * POK_LEN
    pok_id  = int(battle_array[base + Pok.ID])
    if pok_id == 0:
        return None
    bench_pps = [snap.bench_delta[delta_i, 4 + m] for m in range(4)]
    moves = _extract_moves(battle_array[base : base + POK_LEN], current_pps=bench_pps)
    return {
        "slot":   i,
        "id":     battle_sprite(battle_array[base : base + POK_LEN]),
        "name":   PokIdToName.get(pok_id, "?").capitalize(),
        "hp":     int(snap.bench_delta[delta_i, 0]),
        "max_hp": int(battle_array[base + Pok.MAX_HP]),
        "status": STATUS.get(int(snap.bench_delta[delta_i, 1]), ""),
        "level":  int(battle_array[base + Pok.LEVEL]),
        "gender": _GENDER_NAMES.get(int(battle_array[base + Pok.GENDER])),
        "ability": _ABILITY_NAMES.get(int(battle_array[base + Pok.AB_ID]), ""),
        "types":  _types(battle_array[base : base + POK_LEN]),
        "item":   _ITEM_ID_TO_NAME.get(int(snap.bench_delta[delta_i, BENCH_ITEM]), ""),
        "moves":  moves,
    }


def _choice_chip(arr) -> list[str]:
    """'Choice: <move>' while a choice item keeps the Pokemon to one move"""
    lock = int(arr[Pok.CHOICE_LOCK])
    if not lock or int(arr[Item.HOLD_EFFECT]) not in CHOICE_EFFECTS:
        return []
    move_id = int(arr[Pok.MOVE1_ID + (lock - 1) * MOVE_STRIDE + Move.ID])
    return [f"Choice: {MoveIdToName.get(move_id, f'Move#{move_id}').replace('_', ' ').title()}"]


def _stockpile_chip(arr) -> list[str]:
    """'Stockpile <count>' while the Pokemon has something stockpiled"""
    count = int(stockpile_count(arr))
    return [f"Stockpile {count}"] if count else []


def _pok(arr) -> dict | None:
    """Serialize the key display fields from one Pokemon's array slice."""
    if arr is None or len(arr) == 0:
        return None
    pok_id = int(arr[Pok.ID])
    return {
        "id":         battle_sprite(arr),
        "name":       PokIdToName.get(pok_id, "?").capitalize(),
        "level":      int(arr[Pok.LEVEL]),
        "gender":     _GENDER_NAMES.get(int(arr[Pok.GENDER])),
        "ability":    _ABILITY_NAMES.get(int(arr[Pok.AB_ID]), ""),
        "types":      _types(arr),
        "hp":         int(arr[Pok.CURRENT_HP]),
        "max_hp":     int(arr[Pok.MAX_HP]),
        "status":     STATUS.get(int(arr[Pok.STATUS]), ""),
        "vol_status": [name for bit, name in VOL_BITS.items()
                       if int(arr[Pok.VOL_STATUS]) & bit]
                      + [name for bit, name in VOL2_BITS.items()
                         if int(arr[Pok.VOL_STATUS2]) & bit]
                      + _choice_chip(arr)
                      + _stockpile_chip(arr),
        "stages":     {STAGE_NAMES[i]: int(arr[Pok.ATTACK_STAT_STAGE + i])
                       for i in range(7)
                       if int(arr[Pok.ATTACK_STAT_STAGE + i]) != 0},
        "item":       _ITEM_ID_TO_NAME.get(int(arr[Pok.ITEM_ID]), ""),
        "moves":      _extract_moves(arr),
    }


def _side(field_block, side_cond) -> list[dict]:
    """Side conditions up on one side: timed ones with turns left, Spikes and Toxic Spikes with layers"""
    base = side_cond - _FLD_BASE
    mask = int(field_block[base])
    out = []
    for bit, name, turns in _SIDE_TIMERS:
        if mask & bit:
            out.append({"name": name, "turns": int(field_block[base + turns])})
    # Future Sight or Doom Desire waiting to hit this side, named by the move
    if mask & SideCondition.FUTURE_SIGHT:
        move_id = int(field_block[base + SIDE_FUTURE_MOVE])
        out.append({
            "name": MoveIdToName.get(move_id, f"Move#{move_id}").replace("_", " ").title(),
            "turns": int(field_block[base + SIDE_FUTURE_TURNS]),
        })
    # Healing Wish waiting for the Pokemon that comes in (the Baton Pass phase's pick)
    if mask & SideCondition.HEALING_WISH:
        out.append({"name": "Healing Wish"})
    for bit, name in _HAZARDS:
        if mask & bit:
            entry = {"name": name}
            if bit == SideCondition.TOXIC_SPIKES:
                entry["layers"] = int(field_block[base + SIDE_TOXIC_SPIKES])
            elif bit == SideCondition.SPIKES:
                entry["layers"] = int(field_block[base + SIDE_SPIKES])
            out.append(entry)
    return out


def _field(field_block) -> dict:
    """Weather (0 turns left means permanent), Gravity's and Trick Room's turns left and both sides'
    conditions"""
    return {
        "weather":       _WEATHER_NAMES.get(int(field_block[FieldIdx.WEATHER - _FLD_BASE]), ""),
        "weather_turns": int(field_block[FieldIdx.WEATHER_DURATION - _FLD_BASE]),
        "gravity_turns": int(field_block[FieldIdx.GRAVITY_TURNS - _FLD_BASE]),
        "trick_room_turns": int(field_block[FieldIdx.TRICKROOM - _FLD_BASE]),
        "my_side":       _side(field_block, FieldIdx.MY_SIDE_COND),
        "opp_side":      _side(field_block, FieldIdx.OPP_SIDE_COND),
    }


_OPP_DID = {
    OPP_DIDNT_MOVE: "Didn't move",
    OPP_STRUGGLED:  "Struggle",
    OPP_SWITCHED:   "Switched",
    OPP_USED_ITEM:  "Used item",
}


def opp_move_label(did: int, battle_array) -> str:
    """
    step_arr's answer as text: "Pound", or "Pound, then Torchic: Ember" for a step with forced turns,
    the foe's name once it changes. The names come from the battle_array since a foe's moves don't
    change and it may be gone by the end of the step
    """
    parts = []
    last_foe = None
    for foe, what, _paid in opp_turns(did):
        base = (foe + 6) * POK_LEN
        if what in _OPP_DID:
            name = _OPP_DID[what] if not parts else _OPP_DID[what].lower()
        else:
            move_id = int(battle_array[base + Pok.MOVE1_ID + (what - 1) * MOVE_STRIDE + Move.ID])
            name = MoveIdToName.get(move_id, f"Move#{move_id}").replace("_", " ").title()
        if last_foe is not None and foe != last_foe:
            name = f"{PokIdToName.get(int(battle_array[base + Pok.ID]), '?').capitalize()}: {name}"
        parts.append(name)
        last_foe = foe
    return ", then ".join(parts)


def _opp_move_counts(node, battle_array) -> dict[str, int]:
    """Visits that got to this node per thing the foe did"""
    counts: dict[str, int] = {}
    # .copy() so MCTS adding a key mid-loop doesn't raise RuntimeError
    for did, n in node.opp_moves.copy().items():
        label = opp_move_label(did, battle_array)
        counts[label] = counts.get(label, 0) + n
    return counts


def _opp_move_rows(children, battle_array) -> list[dict]:
    """The outcome pane's rows for an action: what the foe did over its outcomes, most often first"""
    rows: dict[str, list] = {}
    for child in children:
        for label, n in _opp_move_counts(child, battle_array).items():
            row = rows.setdefault(label, [0, 0.0])
            row[0] += n
            row[1] += child.win_chance * n
    total = sum(row[0] for row in rows.values())
    # By the rounded share, so two equal moves don't swap places on every update
    ordered = sorted(rows.items(), key=lambda item: -round(item[1][0] * 100 / total))
    return [
        {"label": label, "visits": visits, "win_chance": round(float(wins / visits), 4)}
        for label, (visits, wins) in ordered
    ]


_PHASE_NAMES = {BattlePhase.TURN_START: "TURN_START", BattlePhase.BATON_PASS: "BATON_PASS"}


def _snapshot(snap, battle_array=None) -> dict:
    is_death = snap.phase == BattlePhase.DEATH_END_OF_TURN
    my_bench, opp_bench = [], []
    if battle_array is not None:
        for i in range(6):
            if i != snap.my_active:
                e = _bench_entry(battle_array, snap, i, True)
                if e:
                    my_bench.append(e)
            if i != snap.opp_active:
                e = _bench_entry(battle_array, snap, i, False)
                if e:
                    opp_bench.append(e)
    return {
        "phase":         "DEATH" if is_death else _PHASE_NAMES.get(int(snap.phase), "TURN_START"),
        "opp_active":    int(snap.opp_active),
        "terminal":      bool(snap.terminal),
        "my":            _pok(snap.my_slice if not is_death else None),
        "opp":           _pok(snap.opp_slice),
        "my_bench":      my_bench,
        "opp_bench":     opp_bench,
        "trainer_items": [
            _POTION_ID_TO_NAME.get(int(snap.field_block[fi - _FLD_BASE]), "")
            for fi in _FLD_ITEMS
        ],
        "turn":          int(snap.field_block[FieldIdx.TURN - _FLD_BASE]),
        "field":         _field(snap.field_block),
    }


def _action_label(action: tuple, parent_snap, battle_array) -> str:
    """Human-readable label for an action tuple (action_type, action_idx)."""
    act_type, act_idx = action
    if act_type == 1:  # MOVE
        if act_idx == 10:
            return "Struggle"
        my = parent_snap.my_slice
        if my is not None and len(my) > 0:
            move_id = int(my[Pok.MOVE1_ID + act_idx * MOVE_STRIDE + Move.ID])
            return MoveIdToName.get(move_id, f"Move#{move_id}").replace("_", " ").title()
        return f"Move {act_idx}"
    else:  # SWITCH — look up the pokemon name from the initial battle_array
        if battle_array is not None:
            pok_id = int(battle_array[act_idx * POK_LEN + Pok.ID])
            return f"→ {PokIdToName.get(pok_id, f'#{pok_id}').capitalize()}"
        return f"Switch {act_idx}"


# ─── main entry point ────────────────────────────────────────────────────────

def serialize_node(
    node,
    battle_array=None,
    min_visits: int = 100,
    max_depth: int = 12,
    _depth: int = 0,
) -> dict:
    """
    Transform the node in a type that is ready for the webapp
    """
    result = {
        "id":         str(id(node)),   # stable for the lifetime of the object
        "visits":     node.visits,
        "wins":       node.wins,
        "win_chance": round(float(node.win_chance), 4),
        "dead_avg":   round(float(node.dead_avg), 4),
        "snapshot":   _snapshot(node.snapshot, battle_array),
        "opp_moves":  _opp_move_counts(node, battle_array),
        "actions":    {},
    }

    if _depth >= max_depth:
        return result

    # .copy() so MCTS adding a new key mid-loop doesn't raise RuntimeError
    for action, children in node.children.copy().items():
        total_visits = sum(c.visits for c in children)

        # Always show root's actions regardless of visit count
        if _depth > 0 and total_visits < min_visits:
            continue

        total_wins = sum(c.wins for c in children)
        agg_win  = (sum(c.win_chance * c.visits for c in children) / total_visits
                    if total_visits > 0 else 0.0)
        agg_dead = (sum(c.dead_avg * c.wins   for c in children) / total_wins
                    if total_wins  > 0 else 0.0)

        key = f"{action[0]}_{action[1]}"

        # PP info for MOVE actions
        act_type, act_idx = action
        current_pp = None
        max_pp = None
        pp_up = 0
        move_info = {"type": None, "category": None, "power": None}
        if act_type == 1 and act_idx != 10:  # MOVE, not Struggle
            my = node.snapshot.my_slice
            if my is not None and len(my) > 0:
                move_info = _move_fields(my, Pok.MOVE1_ID + act_idx * MOVE_STRIDE)
                current_pp = int(my[Pok.MOVE1_ID + act_idx * MOVE_STRIDE + Move.PP])
                move_id = int(my[Pok.MOVE1_ID + act_idx * MOVE_STRIDE + Move.ID])
                base_pp = _MOVE_ID_TO_MAX_PP.get(move_id)
                pp_up_offset = Pok.MOVE1_ID + act_idx * MOVE_STRIDE + Move.PP_UP
                if pp_up_offset < len(my):
                    pp_up = int(my[pp_up_offset])
                if base_pp is not None:
                    max_pp = base_pp + (base_pp * pp_up * 2) // 10

        result["actions"][key] = {
            "action_type":  int(action[0]),
            "action_idx":   int(action[1]),
            "label":        _action_label(action, node.snapshot, battle_array),
            "total_visits": total_visits,
            "win_chance":   round(agg_win,  4),
            "dead_avg":     round(agg_dead, 4),
            "current_pp":   current_pp,
            "max_pp":       max_pp,
            "pp_up":        pp_up,
            "move_type":    move_info["type"],
            "category":     move_info["category"],
            "power":        move_info["power"],
            "opp_moves":    _opp_move_rows(children, battle_array),
            # Child nodes: only serialize if above threshold (or at root level)
            "nodes": [
                serialize_node(c, battle_array, min_visits, max_depth, _depth + 1)
                for c in children
                if c.visits >= min_visits or _depth == 0
            ],
        }

    return result
