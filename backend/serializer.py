"""Convert MCTS Node tree → JSON-serialisable dicts."""
from __future__ import annotations
import os
import sys
from Models.idx_const import Pok, Move, MOVE_STRIDE, POK_LEN, Field as FieldIdx
from Models.helper import BattlePhase
from DataBase.PkDB import PokIdToName
from DataBase.MoveDB import MoveIdToName
from DataBase.ItemDB import ItemNames as _ItemNameEnum


_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ─── display helpers ─────────────────────────────────────────────────────────

STATUS = {0: "", 1: "SLP", 2: "FRZ", 3: "PAR", 4: "BRN", 5: "PSN", 6: "TOX"}
VOL_BITS = {
    1: "Flinch", 2: "Confused", 4: "Heal Block",
    8: "Salt Cure", 32: "Trapped", 64: "Leech Seed",
    128: "Curse", 256: "Attracted",
}
STAGE_NAMES = ["Atk", "Def", "SpA", "SpD", "Spe", "Acc", "Eva"]
_ITEM_ID_TO_NAME: dict[int, str] = {
    v: k.replace("_", " ").title()
    for k, v in vars(_ItemNameEnum).items()
    if isinstance(v, int)
}

_POTION_ID_TO_NAME: dict[int, str] = {
    1: "Potion", 2: "Super Potion", 3: "Hyper Potion",
    4: "Full Restore", 5: "Full Heal",
    6: "X Special", 7: "X Defend", 8: "X Speed",
}

_FLD_BASE = FieldIdx.MY_POK
_FLD_ITEMS = (FieldIdx.AI_ITEM1, FieldIdx.AI_ITEM2, FieldIdx.AI_ITEM3, FieldIdx.AI_ITEM4)


def _bench_entry(battle_array, snap, i: int, is_my: bool) -> dict | None:
    """One bench slot. Returns None for empty party slots (pok_id == 0)."""
    delta_i = i if is_my else i + 6
    base    = i * POK_LEN if is_my else (i + 6) * POK_LEN
    pok_id  = int(battle_array[base + Pok.ID])
    if pok_id == 0:
        return None
    return {
        "slot":   i,
        "id":     pok_id,
        "name":   PokIdToName.get(pok_id, "?").capitalize(),
        "hp":     int(snap.bench_delta[delta_i, 0]),
        "max_hp": int(battle_array[base + Pok.MAX_HP]),
        "status": STATUS.get(int(snap.bench_delta[delta_i, 1]), ""),
        "level":  int(battle_array[base + Pok.LEVEL]),
        "item":   _ITEM_ID_TO_NAME.get(int(battle_array[base + Pok.ITEM_ID]), ""),
    }


def _pok(arr) -> dict | None:
    """Serialize the key display fields from one Pokemon's array slice."""
    if arr is None or len(arr) == 0:
        return None
    pok_id = int(arr[Pok.ID])
    return {
        "id":         pok_id,
        "name":       PokIdToName.get(pok_id, "?").capitalize(),
        "hp":         int(arr[Pok.CURRENT_HP]),
        "max_hp":     int(arr[Pok.MAX_HP]),
        "status":     STATUS.get(int(arr[Pok.STATUS]), ""),
        "vol_status": [name for bit, name in VOL_BITS.items()
                       if int(arr[Pok.VOL_STATUS]) & bit],
        "stages":     {STAGE_NAMES[i]: int(arr[Pok.ATTACK_STAT_STAGE + i])
                       for i in range(7)
                       if int(arr[Pok.ATTACK_STAT_STAGE + i]) != 0},
        "item":       _ITEM_ID_TO_NAME.get(int(arr[Pok.ITEM_ID]), ""),
    }


def _opp_move_label(opp_move_idx: int, parent_opp_slice) -> str | None:
    """
    Turn the raw opp_move_idx into a readable string.
    Needs parent_opp_slice because the move name lives in the opp's Pokemon
    array from BEFORE the turn, not after.
    """
    if opp_move_idx < 0:
        if opp_move_idx >= -6:
            return "Switched"         # -1 to -6 are switch indices
        return "Used item"            # -10, -20, -30, -40
    if opp_move_idx == 10:
        return "Struggle"
    # Normal move: look up the name from the parent's opp Pokemon array
    if parent_opp_slice is not None and len(parent_opp_slice) > 0:
        move_id = int(parent_opp_slice[Pok.MOVE1_ID + opp_move_idx * MOVE_STRIDE + Move.ID])
        return MoveIdToName.get(move_id, f"Move#{move_id}").replace("_", " ").title()
    return f"Move {opp_move_idx}"


def _snapshot(snap, parent_opp_slice=None, battle_array=None) -> dict:
    is_death = snap.phase == BattlePhase.DEATH_END_OF_TURN
    opp_move = None
    if parent_opp_slice is not None and snap.opp_move_idx != -1:
        opp_move = _opp_move_label(snap.opp_move_idx, parent_opp_slice)
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
        "phase":         "DEATH" if is_death else "TURN_START",
        "opp_active":    int(snap.opp_active),
        "terminal":      bool(snap.terminal),
        "opp_move":      opp_move,
        "my":            _pok(snap.my_slice if not is_death else None),
        "opp":           _pok(snap.opp_slice),
        "my_bench":      my_bench,
        "opp_bench":     opp_bench,
        "trainer_items": [
            _POTION_ID_TO_NAME.get(int(snap.field_block[fi - _FLD_BASE]), "")
            for fi in _FLD_ITEMS
        ],
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
    _parent_opp_slice=None,
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
        "snapshot":   _snapshot(node.snapshot, _parent_opp_slice, battle_array),
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

        result["actions"][key] = {
            "action_type":  int(action[0]),
            "action_idx":   int(action[1]),
            "label":        _action_label(action, node.snapshot, battle_array),
            "total_visits": total_visits,
            "win_chance":   round(agg_win,  4),
            "dead_avg":     round(agg_dead, 4),
            # Child nodes: only serialize if above threshold (or at root level)
            "nodes": [
                serialize_node(
                    c, battle_array, min_visits, max_depth, _depth + 1,
                    _parent_opp_slice=node.snapshot.opp_slice,
                )
                for c in children
                if c.visits >= min_visits or _depth == 0
            ],
        }

    return result
