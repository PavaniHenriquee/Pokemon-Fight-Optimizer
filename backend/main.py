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
import numpy as np
from numba import njit
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from Models.constants import _FIELD_TURN
from Models.pokemon import Pokemon
from Engine.engine_helper import start_of_battle
from SearchEngine.models import GameState, Node
from SearchEngine.my_mcts import _select_expand, _rollout, _backprop, find_best_terminal_node
from Utils.helper import to_battle_array
from .serializer import serialize_node   # relative import within the backend package

# Put project root on path so Models/Engine/etc. are importable
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


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

def _build_battle() -> np.ndarray:
    """Same battle as in main.py — change this to whatever you want to analyse."""
    charmander  = Pokemon("Charmander",  "Male", 5, "Blaze",    "Hardy", ["Scratch","Growl","Ember"])
    squirtle    = Pokemon("Squirtle",    "Male", 8, "Torrent",  "Hardy", ["Tackle","Tail Whip","Bubble"])
    bulbasaur   = Pokemon("Bulbasaur",   "Male", 5, "Overgrow", "Hardy", ["Pound","Leer","Razor Leaf"])
    charmeleon  = Pokemon("Charmeleon",  "Male", 5, "Blaze",    "Hardy", ["Scratch","Growl"])
    wartortle   = Pokemon("Wartortle",   "Male", 5, "Torrent",  "Hardy", ["Tackle","Tail Whip"])
    ivysaur     = Pokemon("Ivysaur",     "Male", 5, "Overgrow", "Hardy", ["Pound","Leer"])
    squirtle1   = Pokemon("Squirtle",    "Male", 5, "Torrent",  "Hardy", ["Tackle","Tail Whip"])
    charmander1 = Pokemon("Charmander",  "Male", 5, "Blaze",    "Hardy", ["Scratch","Growl"])
    return to_battle_array(
        [charmander, bulbasaur, squirtle, charmeleon, ivysaur, wartortle],
        [squirtle1, charmander1, charmander1, charmander1, charmander1],
    )

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

        if i % 500 == 0 and i > 0:
            terminal_node, _, _ = find_best_terminal_node(root)
            if terminal_node.snapshot.terminal and terminal_node.visits >= 1_000:
                print(f"[MCTS] converged at {i:,} iterations")
                break

    _state["running"] = False
    print(f"[MCTS] done — {_state['iterations']:,} iterations")

# ─── REST endpoints ───────────────────────────────────────────────────────────

@app.post("/start")
async def start_mcts() -> dict:
    """
    Start the MCTS
    """
    # Stop any existing run
    if ev := _state.get("stop_event"):
        ev.set()
    await asyncio.sleep(0.1)   # let the old thread notice before we replace state

    random.seed(37)
    np.random.seed(37)
    _seed_numba(37)

    battle = _build_battle()
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

# ─── WebSocket ────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
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
