"""
FastAPI backend — runs MCTS in a background thread and streams the tree.

Start from the project root:
    uvicorn backend.main:app --reload --port 8000
"""
from __future__ import annotations
import os
import sys
import threading
import asyncio
import random
import json
from typing import Optional, cast
from pydantic import BaseModel, Field
import numpy as np
from numba import njit
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from Models.idx_const import Pok, POK_LEN
from Models.constants import _FIELD_TURN
from Models.pokemon import Pokemon
from Engine.engine_helper import start_of_battle
from SearchEngine.models import GameState, Node, reconstruct_battle_array
from SearchEngine.my_mcts import _select_expand, _rollout, _backprop, find_best_terminal_node
from SearchEngine.helper import prune_dominated
from Utils.helper import to_battle_array
from Utils.loader import natures
from DataBase.loader import pkDB, moveDB, abDB
from DataBase.PkDB import PokemonName, PokIdToName
from .serializer import serialize_node   # relative import within the backend package

# Put project root on path so Models/Engine/etc. are importable
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


_DEFAULT_IVS = {
    "HP": 31, "Attack": 31, "Defense": 31,
    "Special Attack": 31, "Special Defense": 31, "Speed": 31,
}
_BOX_PATH = os.path.join(_ROOT, "UserData", "box.json")


@njit
def _seed_numba(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)


# ─── app setup ───────────────────────────────────────────────────────────────

app = FastAPI(title="Pokemon MCTS Visualiser")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # fine for local dev
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── shared state ────────────────────────────────────────────────────────────
# The MCTS thread writes here; the WebSocket handler reads it.
# Python's GIL makes simple attribute reads/writes atomic, which is enough
# for a visualisation tool (we might see a slightly stale value, never a crash).
_state: dict = {
    "root":        None,
    "battle_array": None,
    "running":     False,
    "iterations":  0,
    "stop_event":  None,
}

# ─── battle builder ──────────────────────────────────────────────────────────
class BoxEntry(BaseModel):
    """Persisted Pokémon in the player's box."""
    id: str
    name: str
    gender: Optional[str] = "Male"
    nature: str = "Hardy"
    ability: str = ""
    level: int = 5
    moves: list[str] = Field(default_factory=list)
    ivs: dict = Field(default_factory=lambda: dict(_DEFAULT_IVS))


class PokemonConfig(BaseModel):
    """
    Readable frontend data for Pokemon Entry
    """
    name: str
    gender: Optional[str] = "Male"
    level: int = 5
    ability: str
    nature: str = "Hardy"
    moves: list[str]  # empty strings filtered out before building
    ivs: Optional[dict] = None

class BattleConfig(BaseModel):
    """
    Readable frontend data for Both teams
    """
    my_team: list[PokemonConfig]
    opp_team: list[PokemonConfig]
    iterations: int = 350_000


def _find_node(root: Node, target_id: str) -> Node | None:
    """Iterative BFS — safe on deep trees, no recursion limit risk."""
    from collections import deque
    q = deque([root])
    while q:
        node = q.popleft()
        if str(id(node)) == target_id:
            return node
        for children in node.children.values():
            q.extend(children)
    return None


class ContinueConfig(BaseModel):
    """
    Continue config
    """
    node_id:       str
    iterations:    int
    my_active_hp:  Optional[int] = None   # None when phase == DEATH
    opp_active_hp: int
    bench_hps:     dict[int, int]          # slot_index → hp


@app.get("/pokemon-data")
async def get_pokemon_data() -> dict:
    """Everything the team builder needs to populate its dropdowns."""

    def _to_enum_key(name: str) -> str:
        """Transform a pkDB display name to its PokemonName attribute key."""
        return (name.upper()
                .replace(" ", "_")
                .replace(".", "")
                .replace("'", "")
                .replace("-", "_")
                .replace("\u2640", "_F")   # ♀
                .replace("\u2642", "_M"))  # ♂

    name_to_id: dict[str, int] = {}
    base_stats: dict[str, dict] = {}
    for pk_name in pkDB.keys():
        pk_id = getattr(PokemonName, _to_enum_key(pk_name), None)
        if pk_id is not None:
            name_to_id[pk_name] = pk_id
        base_stats[pk_name] = pkDB[pk_name].get("base stats", {})

    return {
        "pokemon":   sorted(pkDB.keys()),
        "moves":     sorted(moveDB.keys()),
        "natures":   sorted(natures.keys()),
        "abilities": sorted(abDB.keys()),
        "nameToId":  name_to_id,
        "baseStats": base_stats,
        "natureMultipliers": natures,
    }

# ─── MCTS worker ─────────────────────────────────────────────────────────────

def _mcts_worker(root: Node, root_state: GameState, stop_event: threading.Event, max_iterations: int) -> None:
    """
    Mirrors mcts_loop() from my_mcts.py but checks stop_event each iteration
    so the WebSocket endpoint can stop it cleanly.
    """
    random.seed(37)
    np.random.seed(37)
    _seed_numba(37)

    for i in range(max_iterations):
        if stop_event.is_set():
            break

        state = root_state.clone()
        state, path = _select_expand(state, root)
        value, win, dead = _rollout(state)
        _backprop(path, value, win, dead)
        _state["iterations"] = i + 1   # simple int write — GIL-atomic

        if i % 2500 == 0 and i > 0:
            terminal_node, _, _ = find_best_terminal_node(root)
            _ = prune_dominated(root)

            if terminal_node.snapshot.terminal and terminal_node.visits >= 1_000:
                print(f"[MCTS] converged at {i:,} iterations")
                break

    _state["running"] = False
    print(f"[MCTS] done — {_state['iterations']:,} iterations")

# ─── REST endpoints ───────────────────────────────────────────────────────────

@app.post("/start")
async def start_mcts(config: BattleConfig) -> dict:
    """
    Start from app
    """
    if ev := _state.get("stop_event"):
        ev.set()
    await asyncio.sleep(0.1)

    def make_pokemon(p: PokemonConfig) -> Pokemon:
        moves = [m for m in p.moves if m]  # strip empty slots
        return Pokemon(p.name, p.gender, p.level, p.ability, p.nature, moves, ivs=p.ivs)

    my_party  = [make_pokemon(p) for p in config.my_team]
    opp_party = [make_pokemon(p) for p in config.opp_team]
    battle    = to_battle_array(my_party, opp_party)

    if battle[_FIELD_TURN] == 0:
        start_of_battle(battle)

    root_state = GameState(battle)
    root       = Node(root_state)
    stop_event = threading.Event()

    _state.update(root=root, battle_array=battle.copy(),
                  running=True, iterations=0, stop_event=stop_event)

    threading.Thread(target=_mcts_worker,
                     args=(root, root_state, stop_event, config.iterations),
                     daemon=True).start()
    return {"status": "started"}


@app.get("/trainers")
async def get_trainers() -> dict:
    """Load trainer parties from TrainerDB.json."""
    try:
        trainer_db_path = os.path.join(_ROOT, "DataBase", "TrainerDB.json")
        with open(trainer_db_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


@app.post("/stop")
async def stop_mcts() -> dict:
    """
    Stop MCTS
    """
    if ev := _state.get("stop_event"):
        ev.set()
    return {"status": "stopped"}

@app.get("/box")
async def get_box() -> list:
    """Load the player's Pokémon box from disk."""
    try:
        with open(_BOX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


@app.post("/box")
async def save_box(entries: list[BoxEntry]) -> dict:
    """Persist the player's Pokémon box to disk."""
    os.makedirs(os.path.dirname(_BOX_PATH), exist_ok=True)
    with open(_BOX_PATH, "w", encoding="utf-8") as f:
        json.dump([e.model_dump() for e in entries], f, indent=2)
    return {"status": "saved"}


@app.get("/node_info/{node_id}")
async def node_info(node_id: str) -> dict:
    """
    Node info
    """
    root    = _state["root"]
    initial = cast(np.ndarray, _state.get("battle_array"))
    if root is None or initial is None:
        return {"error": "no active battle"}

    node = _find_node(root, node_id)
    if node is None:
        return {"error": "node not found"}

    snap = node.snapshot

    def _entry(pok_id: int, hp: int, max_hp: int, slot: int) -> dict:
        return {
            "slot":   slot,
            "pok_id": pok_id,
            "name":   PokIdToName.get(pok_id, "?").capitalize(),
            "hp":     hp,
            "max_hp": max_hp,
        }

    my_active_slot = snap.my_active
    my_active = (
        _entry(
            int(snap.my_slice[Pok.ID]),
            int(snap.my_slice[Pok.CURRENT_HP]),
            int(snap.my_slice[Pok.MAX_HP]),
            my_active_slot,
        )
        if my_active_slot >= 0 else None
    )

    opp_active = _entry(
        int(snap.opp_slice[Pok.ID]),
        int(snap.opp_slice[Pok.CURRENT_HP]),
        int(snap.opp_slice[Pok.MAX_HP]),
        snap.opp_active,
    )

    my_bench = []
    for i in range(6):
        if i == my_active_slot:
            continue
        pok_id  = int(initial[i * POK_LEN + Pok.ID])
        bench_hp = int(snap.bench_delta[i, 0])
        if pok_id == 0 or bench_hp == 0:   # empty slot or fainted — skip
            continue
        my_bench.append(_entry(
            pok_id,
            bench_hp,
            int(initial[i * POK_LEN + Pok.MAX_HP]),
            i,
        ))

    return {"my_active": my_active, "opp_active": opp_active, "my_bench": my_bench}


@app.post("/continue_from_node")
async def continue_from_node(config: ContinueConfig) -> dict:
    """
    Continue from node
    """
    if ev := _state.get("stop_event"):
        ev.set()
    await asyncio.sleep(0.1)

    root    = _state["root"]
    initial = _state["battle_array"]
    if root is None:
        return {"error": "no active battle"}

    node = _find_node(root, config.node_id)
    if node is None:
        return {"error": "node not found"}

    snap   = node.snapshot
    battle = reconstruct_battle_array(snap, initial)

    # HP overrides on top of reconstruction
    if config.my_active_hp is not None and snap.my_active >= 0:
        battle[snap.my_active * POK_LEN + Pok.CURRENT_HP] = config.my_active_hp
    battle[(snap.opp_active + 6) * POK_LEN + Pok.CURRENT_HP] = config.opp_active_hp
    for slot, hp in config.bench_hps.items():
        battle[int(slot) * POK_LEN + Pok.CURRENT_HP] = hp

    root_state = GameState(battle)
    new_root   = Node(root_state)
    stop_event = threading.Event()

    _state.update(
        root=new_root, battle_array=battle.copy(),
        running=True, iterations=0, stop_event=stop_event,
    )
    threading.Thread(
        target=_mcts_worker,
        args=(new_root, root_state, stop_event, config.iterations),
        daemon=True,
    ).start()
    return {"status": "started"}

# ─── WebSocket ────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    """
    Websocket
    """
    await ws.accept()
    loop = asyncio.get_running_loop()
    last_sent = -1   # tracks what iteration count we last serialized

    try:
        while True:
            iterations = _state["iterations"]
            running    = _state["running"]
            root       = _state["root"]

            if iterations != last_sent and root is not None and root.visits > 0:
                # Something changed — serialize and push the full tree
                tree = await loop.run_in_executor(
                    None, serialize_node, root, _state["battle_array"]
                )
                await ws.send_json({
                    "type": "tree_update",
                    "iterations": iterations,
                    "running": running,
                    "tree": tree,
                })
                last_sent = iterations
            else:
                # Nothing changed — cheap ping so the frontend knows we're alive
                await ws.send_json({
                    "type": "status",
                    "iterations": iterations,
                    "running": running,
                })

            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        pass
