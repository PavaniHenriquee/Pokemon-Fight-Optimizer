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
import time
import traceback
from contextlib import asynccontextmanager
from typing import Literal, Optional, cast
from pydantic import BaseModel, Field
import numpy as np
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from Models.idx_const import Pok, POK_LEN
from Models.constants import (
    _FIELD_TURN,
    _FIELD_AI_ITEM1, _FIELD_AI_ITEM2, _FIELD_AI_ITEM3, _FIELD_AI_ITEM4, _FIELD_TERRAIN,
)
from Models.helper import Terrain
from Models.pokemon import Pokemon
from Engine.engine_helper import start_of_battle
from SearchEngine.models import GameState, Node, reconstruct_battle_array, real_position
from SearchEngine.my_mcts import _select_expand, _rollout, _backprop, find_best_terminal_node
from SearchEngine.helper import prune_dominated
from Utils.jit import njit
from Utils.helper import to_battle_array
from Utils.loader import natures
from DataBase.loader import pkDB, moveDB, abDB, itemDB
from DataBase.PkDB import PokemonName, PokIdToName, sprite_id
from DataBase.support import TRAINER_ITEMS, trainer_lacks
from .serializer import serialize_node, opp_move_label   # relative import within the backend package

# Put project root on path so Models/Engine/etc. are importable
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


_DEFAULT_IVS = {
    "HP": 31, "Attack": 31, "Defense": 31,
    "Special Attack": 31, "Special Defense": 31, "Speed": 31,
}


def _box_path() -> str:
    """UserData/box.json, or PBO_BOX_PATH (the Electron app keeps the box in %APPDATA%)"""
    return os.environ.get("PBO_BOX_PATH") or os.path.join(_ROOT, "UserData", "box.json")


_BOX_PATH = _box_path()


def _nuzlocke_path() -> str:
    """UserData/nuzlocke.json, or PBO_NUZLOCKE_PATH (the Electron app keeps it in %APPDATA%)"""
    return os.environ.get("PBO_NUZLOCKE_PATH") or os.path.join(_ROOT, "UserData", "nuzlocke.json")


_NUZLOCKE_PATH = _nuzlocke_path()

_TRAINER_ITEM_FIELDS = (
    _FIELD_AI_ITEM1, _FIELD_AI_ITEM2, _FIELD_AI_ITEM3, _FIELD_AI_ITEM4,
)

@njit
def _seed_numba(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)


def _seed_search() -> None:
    """Seeds every RNG with PBO_SEED when it's set (dev.bat sets it, so dev runs repeat). The
    installed app doesn't set it, so its searches are random."""
    seed = os.environ.get("PBO_SEED")
    if seed:
        random.seed(int(seed))
        np.random.seed(int(seed))
        _seed_numba(int(seed))


# ─── app setup ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Compile the engine in the background at startup, unless JIT is off (pytest)"""
    global _warmup_running  #pylint:disable=W0603
    if os.environ.get("NUMBA_DISABLE_JIT") != "1":
        _warmup_running = True
        threading.Thread(target=_warm_up, daemon=True).start()
    if os.environ.get("PBO_EXIT_WITH_PARENT") == "1" and sys.stdin is not None:
        threading.Thread(target=_exit_when_parent_closes, args=(sys.stdin.fileno(),), daemon=True).start()
    yield


def _exit_when_parent_closes(fd: int) -> None:
    """Electron starts the backend with a stdin pipe that closes when Electron exits, crash
    included, so the backend never outlives the app. Reads the raw fd: a thread blocked in
    sys.stdin's buffered reader holds its lock and crashes the interpreter's shutdown."""
    try:
        while os.read(fd, 1024):
            pass
    except (OSError, ValueError):
        pass
    os._exit(0)


app = FastAPI(title="Pokemon MCTS Visualiser", lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # fine for local dev
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── shared state ────────────────────────────────────────────────────────────
class Session:
    """Everything that belongs to one MCTS run."""
    def __init__(self, root: Node, battle_array: np.ndarray, max_iterations: int):
        self.root = root
        self.battle_array = battle_array
        self.max_iterations = max_iterations
        self.iterations = 0
        self.running = True
        self.error: str | None = None
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None


_session: Session | None = None
_warmup_running = False  # True while the startup warm-up compiles / loads the engine

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
    item: Optional[str] = None
    dead: bool = False  # in the death box: can't join the party, still counts for the species clause


class NuzlockeEncounter(BaseModel):
    """What happened at one location of a run. The box matches it by evolution line."""
    species: str = ""
    status: Literal["caught", "missed", "dead"] = "caught"


class NuzlockeRun(BaseModel):
    """Persisted Nuzlocke run. A location with no entry is still open."""
    player: Literal["", "Male", "Female"] = ""
    starter: NuzlockeEncounter = Field(default_factory=NuzlockeEncounter)  # no species until chosen
    encounters: dict[str, NuzlockeEncounter] = Field(default_factory=dict)
    last_trainer: str = ""  # the trainer picked last in Setup, empty until one is
    items: list[str] = Field(default_factory=list)  # ItemLocationDB ids picked up, on the Items tab


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
    item: Optional[str] = None

class BattleConfig(BaseModel):
    """
    Readable frontend data for Both teams
    """
    my_team: list[PokemonConfig]
    opp_team: list[PokemonConfig]
    iterations: int = 350_000
    trainer_items: list[str] = Field(default_factory=list)
    terrain: str = "plain"


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


class PathStep(BaseModel):
    """One click on the way to the node Continue starts from"""
    node_id:  str
    opp_move: Optional[str] = None     # the label of the row it was picked under


def _clicked_path(root: Node, steps: list[PathStep], battle_array: np.ndarray) -> list[tuple] | None:
    """
    The clicks as real_position wants them: (parent, action, node, what the foe did). A row can be
    several packed values when the PP paid differs, the most seen one counts. None if a node isn't in
    the tree anymore
    """
    path = []
    parent = root
    for step in steps:
        found = next(
            ((action, child) for action, children in parent.children.items() for child in children
             if str(id(child)) == step.node_id),
            None,
        )
        if found is None:
            return None
        action, node = found
        seen = node.opp_moves.copy()
        picked = {
            did: n for did, n in seen.items() if opp_move_label(did, battle_array) == step.opp_move
        } or seen
        path.append((parent, action, node, max(picked, key=picked.get) if picked else None))
        parent = node
    return path


class ContinueConfig(BaseModel):
    """
    Continue config
    """
    node_id:       str
    iterations:    int
    my_active_hp:  Optional[int] = None   # None when phase == DEATH
    opp_active_hp: int
    bench_hps:     dict[int, int]          # slot_index → hp
    path:          list[PathStep] = Field(default_factory=list)  # root → node, what the foe really did


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
            name_to_id[pk_name] = sprite_id(pk_id)
        base_stats[pk_name] = pkDB[pk_name].get("base stats", {})

    # Struggle is the engine's fallback at 0 PP, nothing can learn it
    pickable = {name: m for name, m in moveDB.items() if name != "Struggle"}

    return {
        "pokemon":   sorted(pkDB.keys()),
        "moves":     sorted(pickable.keys()),
        "natures":   sorted(natures.keys()),
        "abilities": sorted(abDB.keys()),
        "items":     sorted(itemDB.keys()),
        "nameToId":  name_to_id,
        "baseStats": base_stats,
        "natureMultipliers": natures,
        "moveInfo": {
            name: {
                "type":     m.get("type", ""),
                "category": m.get("category", ""),
                "power":    m.get("power", 0),
                "accuracy": m.get("accuracy"),
                "pp":       m.get("pp"),
            }
            for name, m in pickable.items()
        },
        "pokemonTypes": {name: list(pkDB[name].get("type", [])) for name in pkDB},
        # PkDB lists a species with one ability twice
        "pokemonAbilities": {name: list(dict.fromkeys(pkDB[name].get("abilities", []))) for name in pkDB},
        "learnsets": {name: pkDB[name].get("learnset", []) for name in pkDB},
        "genderless": [name for name in pkDB if pkDB[name].get("genderless")],
    }

# ─── MCTS worker ─────────────────────────────────────────────────────────────

def _mcts_worker(session: Session, root_state: GameState) -> None:
    try:
        _seed_search()
        root = session.root

        for i in range(session.max_iterations):
            if session.stop_event.is_set():
                break

            state = root_state.clone()
            state, path, actions = _select_expand(state, root)
            value, win, dead = _rollout(state)
            _backprop(path, actions, value, win, dead)
            session.iterations = i + 1

            if i % 2500 == 0 and i > 0:
                terminal_node, _, _ = find_best_terminal_node(root)
                _ = prune_dominated(root)
                if terminal_node.snapshot.terminal and terminal_node.visits >= 5_000:
                    print(f"[MCTS] converged at {i:,} iterations")
                    break
    except Exception:
        session.error = traceback.format_exc()
        traceback.print_exc()
    finally:
        session.running = False
        print(f"[MCTS] done — {session.iterations:,} iterations")


async def _launch(root_state: GameState, battle: np.ndarray, max_iterations: int) -> None:
    """Stop the current run (if any), then start a new independent one."""
    global _session  #pylint:disable=W0603
    old = _session
    if old is not None:
        old.stop_event.set()
        if old.thread is not None:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, old.thread.join, 5)

    session = Session(Node(root_state), battle.copy(), max_iterations)
    session.thread = threading.Thread(
        target=_mcts_worker, args=(session, root_state), daemon=True
    )
    _session = session
    session.thread.start()

# ─── REST endpoints ───────────────────────────────────────────────────────────

def _build_battle(config: BattleConfig) -> np.ndarray:
    """Battle array for a config: both parties, start of battle, trainer items, terrain"""
    def make_pokemon(p: PokemonConfig) -> Pokemon:
        moves = [m for m in p.moves if m]
        # A box saved before PkDB knew it can still say Male
        gender = None if pkDB[p.name].get("genderless") else p.gender
        return Pokemon(
            p.name, gender, p.level, p.ability, p.nature, moves,
            ivs=p.ivs,
            item=p.item if p.item else None,
        )

    my_party  = [make_pokemon(p) for p in config.my_team]
    opp_party = [make_pokemon(p) for p in config.opp_team]
    battle    = to_battle_array(my_party, opp_party)

    if battle[_FIELD_TURN] == 0:
        start_of_battle(battle)

    for i, item_name in enumerate(config.trainer_items[:4]):
        val = TRAINER_ITEMS.get(item_name, 0)
        if val:
            battle[_TRAINER_ITEM_FIELDS[i]] = val
    battle[_FIELD_TERRAIN] = getattr(Terrain, config.terrain.upper())
    return battle


_WARMUP_CONFIG = BattleConfig(
    my_team=[PokemonConfig(name="Charmander", level=5, ability="Blaze",
                           moves=["Scratch", "Growl", "Ember"], item="Oran Berry")],
    opp_team=[PokemonConfig(name="Squirtle", level=5, ability="Torrent", moves=["Tackle", "Tail Whip"]),
              PokemonConfig(name="Bulbasaur", level=5, ability="Overgrow", moves=["Tackle", "Growl"])],
    iterations=300,
    trainer_items=["Potion"],
)


def _warm_up() -> None:
    """Compile (or load from the Numba cache) everything a search runs, on a throwaway session,
    so the first real search doesn't wait on compilation"""
    global _warmup_running  #pylint:disable=W0603
    t0 = time.perf_counter()
    try:
        battle = _build_battle(_WARMUP_CONFIG)
        state = GameState(battle)
        _mcts_worker(Session(Node(state), battle.copy(), _WARMUP_CONFIG.iterations), state)
        print(f"[warm-up] engine ready in {time.perf_counter() - t0:.1f}s")
    except Exception:
        traceback.print_exc()
    finally:
        _warmup_running = False


@app.post("/start")
async def start_mcts(config: BattleConfig) -> dict:
    """Start from app"""
    # Build everything BEFORE touching the current run, so a bad config
    # reports an error instead of killing a working search.
    lacks = trainer_lacks([p.model_dump() for p in config.opp_team], config.trainer_items)
    if lacks:
        return {"status": "error", "error": "Not supported yet: " + ", ".join(lacks)}
    try:
        battle = _build_battle(config)
    except Exception as exc:
        traceback.print_exc()
        return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}

    await _launch(GameState(battle), battle, config.iterations)
    return {"status": "started"}


@app.get("/trainers")
async def get_trainers() -> dict:
    """Load trainer parties from TrainerDB.json, each with what it lacks ("lacks") when it lacks something."""
    try:
        trainer_db_path = os.path.join(_ROOT, "DataBase", "TrainerDB.json")
        with open(trainer_db_path, "r", encoding="utf-8") as f:
            trainers = json.load(f)
    except FileNotFoundError:
        return {}
    for entry in trainers.values():
        lacks = trainer_lacks(entry["team"], entry.get("trainer_items", []))
        if lacks:
            entry["lacks"] = lacks
    return trainers


@app.get("/encounters")
async def get_encounters() -> dict:
    """What can be met at each location, from EncounterDB.json (DataBase/import_encounters.py)."""
    with open(os.path.join(_ROOT, "DataBase", "EncounterDB.json"), "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/item-locations")
async def get_item_locations() -> dict:
    """Where each item, TM and plate is picked up, from ItemLocationDB.json (DataBase/import_items.py)."""
    with open(os.path.join(_ROOT, "DataBase", "ItemLocationDB.json"), "r", encoding="utf-8") as f:
        return json.load(f)


@app.post("/stop")
async def stop_mcts() -> dict:
    """
    STOP MCTS
    """
    if _session is not None:
        _session.stop_event.set()
    return {"status": "stopped"}

@app.get("/box")
async def get_box() -> list:
    """Load the player's Pokémon box from disk. No file or an empty one is an empty box (the committed
    file is empty). An unreadable one is an error, not an empty box: saving that would wipe the file."""
    try:
        with open(_BOX_PATH, "r", encoding="utf-8") as f:
            text = f.read()
        return json.loads(text) if text.strip() else []
    except FileNotFoundError:
        return []
    except ValueError as e:  # bad JSON and bad encoding are both ValueErrors
        raise HTTPException(500, f"Can't read {_BOX_PATH}: {e}") from e


@app.post("/box")
async def save_box(entries: list[BoxEntry]) -> dict:
    """Persist the player's Pokémon box to disk."""
    os.makedirs(os.path.dirname(_BOX_PATH), exist_ok=True)
    with open(_BOX_PATH, "w", encoding="utf-8") as f:
        json.dump([e.model_dump() for e in entries], f, indent=2)
    return {"status": "saved"}


@app.get("/nuzlocke")
async def get_nuzlocke() -> dict:
    """Load the Nuzlocke run. No file yet is an empty run. An unreadable file is an error, not an empty
    run: the tracker saves every change, so an empty answer would end up replacing the real run."""
    try:
        with open(_NUZLOCKE_PATH, "r", encoding="utf-8") as f:
            return NuzlockeRun.model_validate(json.load(f)).model_dump()
    except FileNotFoundError:
        return NuzlockeRun().model_dump()
    except ValueError as e:  # bad JSON and pydantic's ValidationError are both ValueErrors
        raise HTTPException(500, f"Can't read {_NUZLOCKE_PATH}: {e}") from e


@app.post("/nuzlocke")
async def save_nuzlocke(run: NuzlockeRun) -> dict:
    """Persist the Nuzlocke run, through a temp file so a crash mid-write can't lose it."""
    os.makedirs(os.path.dirname(_NUZLOCKE_PATH), exist_ok=True)
    temp_path = f"{_NUZLOCKE_PATH}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(run.model_dump(), f, indent=2)
    os.replace(temp_path, _NUZLOCKE_PATH)
    return {"status": "saved"}


@app.get("/node_info/{node_id}")
async def node_info(node_id: str) -> dict:
    """
    Node info
    """
    sess = _session
    if sess is None:
        return {"error": "no active battle"}
    root    = sess.root
    initial = cast(np.ndarray, sess.battle_array)

    node = _find_node(root, node_id)
    if node is None:
        return {"error": "node not found"}

    snap = node.snapshot

    def _entry(pok_id: int, hp: int, max_hp: int, slot: int) -> dict:
        return {
            "slot":   slot,
            "pok_id": sprite_id(pok_id),
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
    """Continue from node"""
    sess = _session
    if sess is None:
        return {"error": "no active battle"}

    node = _find_node(sess.root, config.node_id)
    if node is None:
        return {"error": "node not found"}

    snap   = node.snapshot
    path   = _clicked_path(sess.root, config.path, sess.battle_array)
    if path and path[-1][2] is node:
        _seed_search()
        battle = real_position(sess.battle_array, path)
    else:
        battle = reconstruct_battle_array(snap, sess.battle_array)

    if config.my_active_hp is not None and snap.my_active >= 0:
        battle[snap.my_active * POK_LEN + Pok.CURRENT_HP] = config.my_active_hp
    battle[(snap.opp_active + 6) * POK_LEN + Pok.CURRENT_HP] = config.opp_active_hp
    for slot, hp in config.bench_hps.items():
        battle[int(slot) * POK_LEN + Pok.CURRENT_HP] = hp

    await _launch(GameState(battle), battle, config.iterations)
    return {"status": "started"}

# ─── WebSocket ────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    """
    Websocket
    """
    await ws.accept()
    loop = asyncio.get_running_loop()
    last_sess: Session | None = None
    last_sent = -1

    try:
        while True:
            sess = _session
            if sess is None:
                await ws.send_json({"type": "status", "iterations": 0, "running": False,
                                    "compiling": _warmup_running})
            else:
                iterations = sess.iterations
                changed = sess is not last_sess or iterations != last_sent
                if changed and sess.root.visits > 0:
                    tree = await loop.run_in_executor(
                        None, serialize_node, sess.root, sess.battle_array
                    )
                    await ws.send_json({
                        "type": "tree_update",
                        "iterations": iterations,
                        "running": sess.running,
                        "error": sess.error,
                        "compiling": _warmup_running,
                        "tree": tree,
                    })
                    last_sess, last_sent = sess, iterations
                else:
                    await ws.send_json({
                        "type": "status",
                        "iterations": iterations,
                        "running": sess.running,
                        "error": sess.error,
                        "compiling": _warmup_running,
                    })
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        pass
