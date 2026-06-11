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
from typing import Optional
from pydantic import BaseModel, Field
import numpy as np
from numba import njit
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from Models.constants import _FIELD_TURN
from Models.pokemon import Pokemon
from Engine.engine_helper import start_of_battle
from SearchEngine.models import GameState, Node
from SearchEngine.my_mcts import _select_expand, _rollout, _backprop, find_best_terminal_node
from SearchEngine.helper import prune_dominated
from Utils.helper import to_battle_array
from Utils.loader import natures
from DataBase.loader import pkDB, moveDB, abDB
from DataBase.PkDB import PokemonName
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
    REadable frontend data for Both teams
    """
    my_team: list[PokemonConfig]
    opp_team: list[PokemonConfig]


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
    for pk_name in pkDB.keys():
        pk_id = getattr(PokemonName, _to_enum_key(pk_name), None)
        if pk_id is not None:
            name_to_id[pk_name] = pk_id

    return {
        "pokemon":   sorted(pkDB.keys()),
        "moves":     sorted(moveDB.keys()),
        "natures":   sorted(natures.keys()),
        "abilities": sorted(abDB.keys()),
        "nameToId":  name_to_id,
    }

# ─── MCTS worker ─────────────────────────────────────────────────────────────

def _mcts_worker(root: Node, root_state: GameState, stop_event: threading.Event) -> None:
    """
    Mirrors mcts_loop() from my_mcts.py but checks stop_event each iteration
    so the WebSocket endpoint can stop it cleanly.
    """
    for i in range(350_000):
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

    random.seed(37)
    np.random.seed(37)
    _seed_numba(37)

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
                     args=(root, root_state, stop_event),
                     daemon=True).start()
    return {"status": "started"}



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
