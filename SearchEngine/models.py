"""Models for GameState and Nodes, and such, for MCTS to use"""
import math
import random
import time
from dataclasses import dataclass
from typing import List, Tuple
import numpy as np
from Models.idx_const import (
    Pok, Field, POK_LEN, MOVE_STRIDE, Move, FIELD_LEN, ITEM_LEN
)
from Models.item import ITEM_TABLE
from Models.constants import (
    _STATUS_TOXIC, _POK_CHARGE_RECHARGE, _POK_LOCKED_MOVE, _POK_CURRENT_HP, _POK_MAX_HP,
    _POK_STATUS, _POK_VOL_STATUS, _POK_ATTACK_STAT_STAGE, _FIELD_MY_POK, _FIELD_OPP_POK,
    _FIELD_PHASE, _BATTLEPHASE_DEATH_END_OF_TURN, _ACTIONTYPE_MOVE, _FIELD_WEATHER, _FIELD_MY_SIDE_COND,
    _FIELD_OPP_SIDE_COND, _FIELD_MY_TOXIC_SPIKES, _FIELD_OPP_TOXIC_SPIKES, _BATTLEPHASE_TURN_START,
    _BATTLEPHASE_BATON_PASS, _FIELD_GRAVITY_TURNS, _POK_VOL_STATUS2, _ITEM_ID, _POK_AB_ID,
    _POK_METRONOME_COUNT, _POK_BASE_AB_ID, _FIELD_OPP_MOVE_RAN, _FIELD_PENDING_OPP_MOVE
)
from Models.trainer_ai import return_idx
from Models.helper import ActionType, BattlePhase
from Engine.battle import turn_sim, switch_in_action, baton_pass_action, OPP_RAN_PP_STEP
from Engine.engine_helper import move_blocked, truant_loafs, is_trapped
from Engine.speed import slow_start_active
from Utils.jit import njit


_MOVE_ID_IDXS = tuple(Pok.MOVE1_ID + i * MOVE_STRIDE for i in range(4))
_MOVE_PP_IDXS = tuple(idx + Move.PP for idx in _MOVE_ID_IDXS)
_PP_IDXS = (
    Pok.MOVE1_ID + Move.PP,
    Pok.MOVE2_ID + Move.PP,
    Pok.MOVE3_ID + Move.PP,
    Pok.MOVE4_ID + Move.PP,
)
# NodeSnapshot.bench_delta columns after hp, status, sleep_ctr, turns, pp0..pp3
BENCH_ITEM = 8
BENCH_CONSUMED_ITEM = 9
BENCH_KNOCKED_OFF = 10
BENCH_COLS = BENCH_KNOCKED_OFF + 1
ACTION_ORDER = (
    tuple((ActionType.MOVE, i) for i in (0, 1, 2, 3, 10))
    + tuple((ActionType.SWITCH, i) for i in range(6))
)
ACTION_SLOT = {action: slot for slot, action in enumerate(ACTION_ORDER)}
N_SLOTS = len(ACTION_ORDER)
STATS_COLS = 2
# c at the root only. Above best_action's c, so a first move that needs follow-ups gets enough
# visits, with less exploration noise in the means below it (NN_PLAN.md Step 1a)
ROOT_C = 1.2
_SLOT_TYPE = tuple(a[0] for a in ACTION_ORDER)
_SLOT_IDX = tuple(a[1] for a in ACTION_ORDER)


# step_arr's answer: what the foe did in each turn of a step, OPP_TURN_BITS a turn and the oldest highest.
# 0 is a step with no foe turn (I only picked who comes in). opp_turns unpacks it. What it did is one of
# these, or a move slot + 1
OPP_DIDNT_MOVE = 0
OPP_STRUGGLED = 5
OPP_SWITCHED = 6
OPP_USED_ITEM = 7
OPP_TURN_BITS = 8
# 7 turns stay below the sign bit, no forced chain is that long (Uproar is the longest with 6)
OPP_TURNS_KEPT = (1 << 7 * OPP_TURN_BITS) - 1


@njit
def _foe_turn(battle_array, foe, pick):
    """What foe (its party slot) did in the turn that just ran, one packed turn of step_arr's answer"""
    if pick < 0:  # A switch or an item always happens, at the start of the turn
        what = OPP_SWITCHED if pick >= -6 else OPP_USED_ITEM
        paid = 0
    else:
        ran = battle_array[_FIELD_OPP_MOVE_RAN]
        slot_plus_one = ran % OPP_RAN_PP_STEP
        what = OPP_STRUGGLED if slot_plus_one > 4 else slot_plus_one
        paid = ran // OPP_RAN_PP_STEP
    return (np.int64(foe) << 5 | what << 2 | paid) + 1


def opp_turns(did: int) -> list[tuple[int, int, int]]:
    """step_arr's answer as (foe's party slot, what it did, PP it paid) per turn, oldest first"""
    turns = []
    while did:
        value = (did & (1 << OPP_TURN_BITS) - 1) - 1
        turns.append((value >> 5, value >> 2 & 7, value & 3))
        did >>= OPP_TURN_BITS
    turns.reverse()
    return turns


@njit
def valid_action_mask(battle_array):
    """Valid actions as a bitmask over ACTION_ORDER slots:
    bits 0-3 moves, bit 4 Struggle, bits 5-10 switches to party slots 0-5.
    The death and Baton Pass phases only pick who comes in"""
    my_active = battle_array[_FIELD_MY_POK]
    mask = 0
    if battle_array[_FIELD_PHASE] == _BATTLEPHASE_TURN_START:
        base = my_active * POK_LEN
        usable = False
        for i in range(4):
            if battle_array[base + _MOVE_ID_IDXS[i]] == 0:
                break
            if (
                battle_array[base + _MOVE_PP_IDXS[i]] > 0
                and not move_blocked(
                    battle_array[base:base + POK_LEN], i, battle_array[_FIELD_GRAVITY_TURNS] > 0
                )
            ):
                mask |= 1 << i
                usable = True
        if not usable:
            mask |= 1 << 4
        # Ingrain, a bind and the foe's trapping abilities keep it in, unless Shed Shell
        opp_base = (battle_array[_FIELD_OPP_POK] + 6) * POK_LEN
        if is_trapped(
            battle_array[base:base + POK_LEN], battle_array[opp_base:opp_base + POK_LEN],
            battle_array[_FIELD_GRAVITY_TURNS] > 0
        ):
            return mask
    for i in range(6):
        if i != my_active and battle_array[i * POK_LEN + _POK_CURRENT_HP] > 0:
            mask |= 1 << (5 + i)
    return mask


@njit
def random_untried_slot(untried):
    """
    Uniform pick among a valid_action_mask's set bits. On Numba's RNG, thread-local: Python's global
    one is also drawn from by the websocket's keepalive pings (websockets ping()), so with the app
    connected they'd shift the search
    """
    n = 0
    for s in range(N_SLOTS):
        if untried >> s & 1:
            n += 1
    pick = random.randrange(n)
    for s in range(N_SLOTS):
        if untried >> s & 1:
            if pick == 0:
                return s
            pick -= 1
    return -1


@njit
def valid_actions_array(battle_array):
    """Valid actions as an (n, 2) int16 array of (action_type, idx), the format rollout_pref takes"""
    mask = valid_action_mask(battle_array)
    out = np.empty((N_SLOTS, 2), dtype=np.int16)
    n = 0
    for s in range(N_SLOTS):
        if mask & (1 << s):
            out[n, 0] = _SLOT_TYPE[s]
            out[n, 1] = _SLOT_IDX[s]
            n += 1
    return out[:n]


@njit
def is_terminal_arr(battle_array):
    """True when either side has no Pokemon left alive"""
    my_alive = False
    opp_alive = False
    for i in range(6):
        if battle_array[i * POK_LEN + _POK_CURRENT_HP] > 0:
            my_alive = True
        if battle_array[(i + 6) * POK_LEN + _POK_CURRENT_HP] > 0:
            opp_alive = True
    return not (my_alive and opp_alive)


@njit
def step_arr(battle_array, action_type, action_idx, opp_move):
    """
    Array version of GameState.step: simulates one whole turn in place, including the extra
    turns forced by locked/charging moves. opp_move is the trainer AI move already chosen
    (unused in the death and Baton Pass phases, where only my replacement is picked, the Baton
    Pass one finishing the paused turn).
    Returns what the foe did, see OPP_TURN_BITS.
    """
    if battle_array[_FIELD_PHASE] == _BATTLEPHASE_DEATH_END_OF_TURN:
        switch_in_action(battle_array, action_idx)
        return 0
    if battle_array[_FIELD_PHASE] == _BATTLEPHASE_BATON_PASS:
        pending = battle_array[_FIELD_PENDING_OPP_MOVE]
        foe = battle_array[_FIELD_OPP_POK]
        baton_pass_action(battle_array, action_idx)
        return _foe_turn(battle_array, foe, 0) if pending else 0

    a_type = action_type
    a_idx = action_idx
    did = np.int64(0)
    # Bounded on purpose, an infinite loop inside njit can't be interrupted
    for _ in range(16):
        foe = battle_array[_FIELD_OPP_POK]
        phase, _opp_idx = turn_sim(opp_move, (a_type, a_idx), battle_array)
        battle_array[_FIELD_PHASE] = phase
        # My Baton Pass paused the turn, a slower foe's move comes with my pick
        if phase != _BATTLEPHASE_BATON_PASS or not battle_array[_FIELD_PENDING_OPP_MOVE]:
            did = (did << OPP_TURN_BITS & OPP_TURNS_KEPT) | _foe_turn(battle_array, foe, opp_move)
        if phase != _BATTLEPHASE_TURN_START or is_terminal_arr(battle_array):
            break
        my_idx = battle_array[_FIELD_MY_POK]
        active = battle_array[my_idx * POK_LEN:(my_idx + 1) * POK_LEN]
        if active[_POK_CHARGE_RECHARGE] == 0 and active[_POK_LOCKED_MOVE] == -1:
            break
        a_type = _ACTIONTYPE_MOVE
        a_idx = int(active[_POK_LOCKED_MOVE])
        opp_move = return_idx(battle_array)
    return did


@njit
def _hp_bracket(hp, max_hp):
    """HP bracket shifted to 0..5 (fainted=0, full=5), same thresholds as the old _bracket"""
    if hp <= 0:
        return 0
    if hp == max_hp:
        return 5
    if hp * 4 >= max_hp * 3:
        return 4
    if hp * 2 >= max_hp:
        return 3
    if hp * 4 >= max_hp:
        return 2
    return 1


# Bits node_key gives each active's VOL_STATUS2
VOL2_KEY_BITS = 3
# Bits node_key gives each active's changed ability id, from k1 bit 12 (opp) then mine
AB_KEY_BITS = 7
AB_KEY_SHIFT = 12
# k3 bit right above each side's VolStatus (opp, then +32 mine): Truant loafs or Slow Start is on
TURN_AB_KEY_BIT = 31


@njit
def _turn_ability_on(pok):
    """Truant loafs this turn or Slow Start still holds (one Pokemon can't have both)"""
    return truant_loafs(pok) or slow_start_active(pok)


@njit
def _stages_key(pok):
    """The 7 stat stages (atk..evasion) packed 4 bits each"""
    packed = np.int64(0)
    for i in range(7):
        packed = (packed << 4) | np.int64(pok[_POK_ATTACK_STAT_STAGE + i] + 6)
    return packed


@njit
def node_key(battle_array):
    """Integer fingerprint of what decides whether two outcomes of an action share a node:
    phase, opp slot, status, every vol status bit (both bitmaps), HP bracket and stat stages of
    both actives, whether each active holds an item, an ability Trace or Worry Seed changed (it
    depends on the history), Truant's loaf turn or an active Slow Start, the weather, Gravity, each
    side's conditions and Toxic Spikes layers
    (not the turns left), my active slot (Roar picks it at random), the Baton Pass phase and each
    active's Metronome item move and count (k4, opp low 32 bits, mine high)"""
    opp_idx = battle_array[_FIELD_OPP_POK]
    opp = battle_array[(opp_idx + 6) * POK_LEN:(opp_idx + 7) * POK_LEN]
    is_death = battle_array[_FIELD_PHASE] == _BATTLEPHASE_DEATH_END_OF_TURN

    k1 = np.int64(1 if is_death else 0)
    k1 |= np.int64(opp_idx) << 1
    k1 |= np.int64(opp[_POK_STATUS]) << 4
    k1 |= np.int64(_hp_bracket(opp[_POK_CURRENT_HP], opp[_POK_MAX_HP])) << 7
    if opp[_ITEM_ID]:
        k1 |= np.int64(1) << 10
    if opp[_POK_BASE_AB_ID]:
        k1 |= np.int64(opp[_POK_AB_ID]) << AB_KEY_SHIFT
    k2 = _stages_key(opp)
    k3 = np.int64(opp[_POK_VOL_STATUS])
    k4 = np.int64(opp[_POK_METRONOME_COUNT])
    if _turn_ability_on(opp):
        k3 |= np.int64(1) << TURN_AB_KEY_BIT
    k1 |= np.int64(battle_array[_FIELD_WEATHER]) << 32
    k1 |= np.int64(battle_array[_FIELD_OPP_SIDE_COND]) << 35
    k1 |= np.int64(battle_array[_FIELD_OPP_TOXIC_SPIKES]) << 45

    if not is_death:
        my_idx = battle_array[_FIELD_MY_POK]
        me = battle_array[my_idx * POK_LEN:(my_idx + 1) * POK_LEN]
        k1 |= np.int64(me[_POK_STATUS]) << 26
        k1 |= np.int64(_hp_bracket(me[_POK_CURRENT_HP], me[_POK_MAX_HP])) << 29
        if me[_ITEM_ID]:
            k1 |= np.int64(1) << 11
        if me[_POK_BASE_AB_ID]:
            k1 |= np.int64(me[_POK_AB_ID]) << AB_KEY_SHIFT + AB_KEY_BITS
        k2 = (k2 << 28) | _stages_key(me)
        k3 |= np.int64(me[_POK_VOL_STATUS]) << 32
        k4 |= np.int64(me[_POK_METRONOME_COUNT]) << 32
        if _turn_ability_on(me):
            k3 |= np.int64(1) << TURN_AB_KEY_BIT + 32
        k1 |= np.int64(battle_array[_FIELD_MY_SIDE_COND]) << 47
        k1 |= np.int64(battle_array[_FIELD_MY_TOXIC_SPIKES]) << 57
        k1 |= np.int64(my_idx) << 59
        if battle_array[_FIELD_PHASE] == _BATTLEPHASE_BATON_PASS:
            k1 |= np.int64(1) << 62
    else:
        k2 = k2 << 28
    # Bits 56+ of k2 are free above the two 28-bit stage packs
    k2 |= np.int64(opp[_POK_VOL_STATUS2]) << 56
    if not is_death:
        k2 |= np.int64(me[_POK_VOL_STATUS2]) << VOL2_KEY_BITS + 56
    if battle_array[_FIELD_GRAVITY_TURNS] > 0:
        k2 |= np.int64(1) << 2 * VOL2_KEY_BITS + 56
    return k1, k2, k3, k4


class GameState():
    """Screenshot of the current gamestate"""
    __slots__ = (
        'battle_array', 'my_active', 'opp_active', 'turn', 'phase', '_opp_ai', 'opp_move_cache',
        'opp_move_last'
    )
    def __init__(self, battle_array):
        self.battle_array = np.copy(battle_array)
        self.my_active = self.battle_array[Field.MY_POK]  # Index of 0..5
        self.opp_active = self.battle_array[Field.OPP_POK]  # Index of 0..5
        self.phase = self.battle_array[Field.PHASE]
        self._opp_ai = None
        self.opp_move_cache = None
        self.opp_move_last = None

    @property
    def opp_move(self):
        """Only do opp ai moves when necessary"""
        if self.opp_move_cache is None and self.phase == BattlePhase.TURN_START:
            self.opp_move_cache = self.opp_move_choice()
        return self.opp_move_cache

    @property
    def my_pty(self):
        """My party"""
        return self.battle_array[0:(6 * POK_LEN)]

    @property
    def opp_pty(self):
        """Opp party"""
        return self.battle_array[(6 * POK_LEN):(12 * POK_LEN)]

    def clone(self):
        """Clone"""
        return GameState(self.battle_array)

    def get_my_pokemon(self, idx: int) -> np.ndarray:
        """Get pokemon from my party by index (0-5)"""
        start = idx * POK_LEN
        end = (idx + 1) * POK_LEN
        return self.battle_array[start:end]

    def get_opp_pokemon(self, idx: int) -> np.ndarray:
        """Get pokemon from opponent party by index (0-5)"""
        start = (6 + idx) * POK_LEN
        end = (7 + idx) * POK_LEN
        return self.battle_array[start:end]

    def get_my_active(self) -> np.ndarray:
        """Get my active pokemon"""
        return self.get_my_pokemon(self.my_active)

    def get_opp_active(self) -> np.ndarray:
        """Get opponent's active pokemon"""
        return self.get_opp_pokemon(self.opp_active)

    def is_terminal(self) -> bool:
        """Check if battle is over"""
        return is_terminal_arr(self.battle_array)

    def get_valid_actions(self) -> List[Tuple[int, int]]:
        """Get all valid actions for current player"""
        mask = valid_action_mask(self.battle_array)
        return [ACTION_ORDER[s] for s in range(N_SLOTS) if mask >> s & 1]

    def opp_move_choice(self) -> int:
        """Uses the trainer AI to choose the move"""
        opp_idx = return_idx(self.battle_array)
        return opp_idx

    def step(self, my_move_idx):
        """Simulate the entire turn"""
        if self.phase != BattlePhase.TURN_START:
            # Only a Baton Pass pick has a foe turn in it, the foe's slower move
            self.opp_move_last = int(step_arr(self.battle_array, my_move_idx[0], my_move_idx[1], -50)) or None
        else:
            self.opp_move_last = int(step_arr(
                self.battle_array, my_move_idx[0], my_move_idx[1], int(self.opp_move)
            )) or None
        self.opp_move_cache = None  # Needs to clear the cache so it picks a new one next time
        battle = self.battle_array
        self.phase = int(battle[Field.PHASE])
        self.opp_active = int(battle[Field.OPP_POK])
        if self.phase == BattlePhase.DEATH_END_OF_TURN:
            self.my_active = -1
        else:
            self.my_active = int(battle[Field.MY_POK])
        return self


@dataclass(slots=True)
class NodeSnapshot:
    """
    Snapshot of the state so i don't need to store the entire battle_array
    """
    phase:        int
    opp_active:   int
    my_active:    int
    my_slice:     np.ndarray
    opp_slice:    np.ndarray
    terminal:     bool
    opp_move_idx: int
    # (12, BENCH_COLS) int32 — [hp, status, sleep_ctr, turns, pp0..pp3, item, consumed item,
    # knocked off] per slot
    bench_delta:  np.ndarray
    field_block:  np.ndarray  # (FIELD_LEN,) int32

    @staticmethod
    def from_state(state: 'GameState') -> 'NodeSnapshot':
        """
        Returns the values
        """
        bench = np.zeros((12, BENCH_COLS), dtype=np.int32)
        for i in range(6):
            pok = state.battle_array[i * POK_LEN : (i + 1) * POK_LEN]
            bench[i, 0] = pok[Pok.CURRENT_HP]
            bench[i, 1] = pok[Pok.STATUS]
            bench[i, 2] = pok[Pok.SLEEP_COUNTER]
            bench[i, 3] = pok[Pok.TURNS]
            for m, pp_idx in enumerate(_PP_IDXS):
                bench[i, 4 + m] = pok[pp_idx]
            bench[i, BENCH_ITEM] = pok[Pok.ITEM_ID]
            bench[i, BENCH_CONSUMED_ITEM] = pok[Pok.CONSUMED_ITEM]
            bench[i, BENCH_KNOCKED_OFF] = pok[Pok.ITEM_KNOCKED_OFF]
        for i in range(6):
            pok = state.battle_array[(i + 6) * POK_LEN : (i + 7) * POK_LEN]
            bench[i + 6, 0] = pok[Pok.CURRENT_HP]
            bench[i + 6, 1] = pok[Pok.STATUS]
            bench[i + 6, 2] = pok[Pok.SLEEP_COUNTER]
            bench[i + 6, 3] = pok[Pok.TURNS]
            for m, pp_idx in enumerate(_PP_IDXS):
                bench[i + 6, 4 + m] = pok[pp_idx]
            bench[i + 6, BENCH_ITEM] = pok[Pok.ITEM_ID]
            bench[i + 6, BENCH_CONSUMED_ITEM] = pok[Pok.CONSUMED_ITEM]
            bench[i + 6, BENCH_KNOCKED_OFF] = pok[Pok.ITEM_KNOCKED_OFF]

        field_start = POK_LEN * 12
        return NodeSnapshot(
            phase        = int(state.phase),
            opp_active   = int(state.opp_active),
            my_active    = int(state.my_active),
            my_slice     = state.get_my_active().copy(),
            opp_slice    = state.get_opp_active().copy(),
            terminal     = state.is_terminal(),
            opp_move_idx = -1 if state.opp_move_last is None else int(state.opp_move_last),
            bench_delta  = bench,
            field_block  = state.battle_array[field_start : field_start + FIELD_LEN].copy(),
        )


def reconstruct_battle_array(snap: NodeSnapshot, initial: np.ndarray) -> np.ndarray:
    """
    Rebuild a battle_array from a NodeSnapshot and the initial array at MCTS start.
    Bench fields restored from bench_delta; active slots overwritten with exact slices;
    field block (turn, weather, indices, phase...) fully replaced.
    """
    out = initial.copy()

    # 1. Patch the mutable bench fields for all 12 party slots
    for i in range(12):
        base = i * POK_LEN
        out[base + Pok.ITEM_ID : base + Pok.ITEM_ID + ITEM_LEN] = ITEM_TABLE[
            snap.bench_delta[i, BENCH_ITEM]
        ]
        out[base + Pok.CONSUMED_ITEM] = snap.bench_delta[i, BENCH_CONSUMED_ITEM]
        out[base + Pok.ITEM_KNOCKED_OFF] = snap.bench_delta[i, BENCH_KNOCKED_OFF]
    for i in range(6):
        base = i * POK_LEN
        out[base + Pok.CURRENT_HP]    = snap.bench_delta[i, 0]
        out[base + Pok.STATUS]         = snap.bench_delta[i, 1]
        out[base + Pok.SLEEP_COUNTER]  = snap.bench_delta[i, 2]
        out[base + Pok.TURNS]          = snap.bench_delta[i, 3]
        out[base + Pok.BADLY_POISON]   = 1 if snap.bench_delta[i, 1] == _STATUS_TOXIC else 0
        for m, pp_idx in enumerate(_PP_IDXS):
            out[base + pp_idx] = snap.bench_delta[i, 4 + m]

    for i in range(6):
        base = (i + 6) * POK_LEN
        out[base + Pok.CURRENT_HP]    = snap.bench_delta[i + 6, 0]
        out[base + Pok.STATUS]         = snap.bench_delta[i + 6, 1]
        out[base + Pok.SLEEP_COUNTER]  = snap.bench_delta[i + 6, 2]
        out[base + Pok.TURNS]          = snap.bench_delta[i + 6, 3]
        out[base + Pok.BADLY_POISON]   = 1 if snap.bench_delta[i + 6, 1] == _STATUS_TOXIC else 0
        for m, pp_idx in enumerate(_PP_IDXS):
            out[base + pp_idx] = snap.bench_delta[i + 6, 4 + m]

    # 2. Overwrite active slots with the full exact slice (stat stages, vol_status, etc.)
    if snap.my_active >= 0:
        out[snap.my_active * POK_LEN : (snap.my_active + 1) * POK_LEN] = snap.my_slice

    out[(snap.opp_active + 6) * POK_LEN : (snap.opp_active + 7) * POK_LEN] = snap.opp_slice

    # 3. Restore field block — includes MY_POK, OPP_POK, turn, weather, phase, AI fields
    out[POK_LEN * 12 : POK_LEN * 12 + FIELD_LEN] = snap.field_block

    return out


def foe_pp_along_path(out: np.ndarray, initial: np.ndarray, moves: list[int | None]) -> None:
    """
    The foe's PP after a path: the root's minus what each move it really used paid. A node's own PP
    comes from the visit that created it, which may have gone through other moves. moves is
    step_arr's answer for each step of the path, None for a step with no foe turn
    """
    for i in range(6):
        base = (i + 6) * POK_LEN
        for idx in _MOVE_PP_IDXS:
            out[base + idx] = initial[base + idx]
    for did in moves:
        for foe, what, paid in opp_turns(did or 0):
            if 1 <= what <= 4:
                idx = (foe + 6) * POK_LEN + _MOVE_PP_IDXS[what - 1]
                out[idx] = max(0, out[idx] - paid)


# node_key's k1 bits with both HP brackets
KEY_HP_BITS = (7 << 7) | (7 << 29)
# Re-running a path's last step gives up after this long, in seconds. The snapshot is the answer then
LAST_STEP_BUDGET = 0.1
_HP_IDXS = np.arange(12) * POK_LEN + Pok.CURRENT_HP


@njit
def _retry_step(start, a_type, a_idx, pick, did, k1, k2, k3, k4, tries):
    """
    Tries one step from start until the foe does exactly did and it lands on the node's key, whatever
    the HP bracket since the HP comes from elsewhere. pick >= 0 is the foe's first move, else the AI
    picks. Returns the new state and whether it got there
    """
    for _ in range(tries):
        arr = start.copy()
        if arr[_FIELD_PHASE] != _BATTLEPHASE_TURN_START:
            opp_move = -50
        elif pick >= 0:
            opp_move = pick
        else:
            opp_move = int(return_idx(arr))
        if step_arr(arr, a_type, a_idx, opp_move) != did:
            continue
        key = node_key(arr)
        if (
            (key[0] & ~KEY_HP_BITS) == (k1 & ~KEY_HP_BITS)
            and key[1] == k2 and key[2] == k3 and key[3] == k4
        ):
            return arr, True
    return start, False


def _rerun_last_step(start: np.ndarray, action: tuple, key: tuple, did: int) -> np.ndarray | None:
    """The state after one step from start where the foe does did, None if it isn't found in time"""
    what = opp_turns(did)[0][1]
    pick = what - 1 if 1 <= what <= 4 else 10 if what == OPP_STRUGGLED else -1
    k1, k2, k3, k4 = (int(k) for k in key)
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < LAST_STEP_BUDGET:
        out, found = _retry_step(start, int(action[0]), int(action[1]), pick, did, k1, k2, k3, k4, 200)
        if found:
            return out
    return None


def real_position(initial: np.ndarray, path: list[tuple]) -> np.ndarray:
    """
    The battle at the end of a clicked path, for Continue from here. path is (parent, action, node,
    what the foe really did) per step. The node's snapshot is the base: it always exists and it's
    instant however rare the node. Replaying the whole path to get its history right isn't an option,
    rare steps that need a rare state before them don't come back even in 30 s.
    Only when the foe really did something else than the visit that made the snapshot, its last step
    runs again from its parent's snapshot, for what follows from the move (a Rollout lock, the last
    move, Mirror Move). The foe's PP comes from the whole path, see foe_pp_along_path
    """
    parent, action, node, did = path[-1]
    out = reconstruct_battle_array(node.snapshot, initial)
    if did is not None and did != node.snapshot.opp_move_idx:
        rerun = _rerun_last_step(reconstruct_battle_array(parent.snapshot, initial), action, node.key, did)
        if rerun is not None:
            rerun[_HP_IDXS] = out[_HP_IDXS]
            out = rerun
    foe_pp_along_path(out, initial, [step[3] for step in path])
    return out


@njit
def best_slot(stats, parent_visits, c):
    """UCB over the per-action stats rows, returns the winning slot"""
    log_parent_visits = math.log(parent_visits) if parent_visits > 1 else 0.0
    best = -1
    best_val = -np.inf
    for i in range(stats.shape[0]):
        visits = stats[i, 0]
        if visits == 0:
            continue
        avg = stats[i, 1] / visits
        exploration = c * math.sqrt(2 * log_parent_visits / visits)
        ucb_val = avg + exploration
        if ucb_val > best_val or (ucb_val == best_val and random.getrandbits(1)):
            best_val = ucb_val
            best = i
    return best


class Node():
    """Tree node, stats holds one row per action: visits, total value"""
    __slots__ = (
        'snapshot', 'children', 'visits', 'total_value', 'key',
        'wins', 'dead', 'win_chance', 'dead_avg', 'stats', 'expanded', 'opp_moves'
    )
    def __init__(self, state, key=None):
        self.snapshot = NodeSnapshot.from_state(state)
        self.key = node_key(state.battle_array) if key is None else key
        self.expanded = 0
        self.children = {}
        self.visits = 0
        self.total_value = 0
        self.wins = 0
        self.dead = 0
        self.win_chance = 0.0
        self.dead_avg = 0
        self.stats = None
        self.opp_moves = {}

    def count_opp_move(self, move):
        """A visit got here with the foe doing this (step_arr's answer, None: it had no turn). node_key
        doesn't see the move, so every move that leaves the same state merges into one node"""
        if move is not None:
            self.opp_moves[move] = self.opp_moves.get(move, 0) + 1

    def best_action(self, c=0.3):
        """
        Best action by UCB, returns (action key, outcome list) \n
        the higher the c the more it favours explorations
        """
        slot = best_slot(self.stats, self.visits, c)
        if slot < 0:
            raise ValueError("best_action called on a node with no explored actions")
        key = ACTION_ORDER[slot]
        return key, self.children[key]
