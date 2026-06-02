"""Convert MCTS Node tree → JSON-serialisable dicts."""
from __future__ import annotations
import os
import sys
from Models.idx_const import Pok, Move, MOVE_STRIDE, POK_LEN
from Models.helper import BattlePhase
from DataBase.PkDB import PokIdToName
from DataBase.MoveDB import MoveIdToName


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
        # Only include non-zero stages so the frontend doesn't clutter
        "stages":     {STAGE_NAMES[i]: int(arr[Pok.ATTACK_STAT_STAGE + i])
                       for i in range(7)
                       if int(arr[Pok.ATTACK_STAT_STAGE + i]) != 0},
    }


def _snapshot(snap) -> dict:
    is_death = snap.phase == BattlePhase.DEATH_END_OF_TURN
    return {
        "phase":      "DEATH" if is_death else "TURN_START",
        "opp_active": int(snap.opp_active),
        "terminal":   bool(snap.terminal),
        # When it's DEATH phase, my_slice is an empty array (my_active == -1)
        "my":  _pok(snap.my_slice if not is_death else None),
        "opp": _pok(snap.opp_slice),
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
        "snapshot":   _snapshot(node.snapshot),
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
                serialize_node(c, battle_array, min_visits, max_depth, _depth + 1)
                for c in children
                if c.visits >= min_visits or _depth == 0
            ],
        }

    return result
