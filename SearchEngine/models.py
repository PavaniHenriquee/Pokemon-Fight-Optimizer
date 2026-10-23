"""Models for GameState and Nodes, and such, for MCTS to use"""
import math
import random
from dataclasses import dataclass
from typing import List, Tuple
import numpy as np
from Models.idx_const import (
    Pok, Field, POK_LEN, MOVE_STRIDE, Move, FIELD_LEN
)
from Models.constants import (
    _STATUS_TOXIC, _POK_CHARGE_RECHARGE, _POK_LOCKED_MOVE, _POK_CURRENT_HP, _POK_MAX_HP,
    _POK_STATUS, _POK_VOL_STATUS, _POK_ATTACK_STAT_STAGE, _FIELD_MY_POK, _FIELD_OPP_POK,
    _FIELD_PHASE, _BATTLEPHASE_DEATH_END_OF_TURN, _ACTIONTYPE_MOVE
)
from Models.trainer_ai import return_idx
from Models.helper import ActionType, BattlePhase
from Engine.battle import turn_sim, switch_in_action
from Utils.jit import njit


_MOVE_ID_IDXS = tuple(Pok.MOVE1_ID + i * MOVE_STRIDE for i in range(4))
_MOVE_PP_IDXS = tuple(idx + Move.PP for idx in _MOVE_ID_IDXS)
N_BINS = 6
_PP_IDXS = (
    Pok.MOVE1_ID + Move.PP,
    Pok.MOVE2_ID + Move.PP,
    Pok.MOVE3_ID + Move.PP,
    Pok.MOVE4_ID + Move.PP,
)
ACTION_ORDER = (
    tuple((ActionType.MOVE, i) for i in (0, 1, 2, 3, 10))
    + tuple((ActionType.SWITCH, i) for i in range(6))
)
ACTION_SLOT = {action: slot for slot, action in enumerate(ACTION_ORDER)}
N_SLOTS = len(ACTION_ORDER)
STATS_COLS = 2 + N_BINS
_SLOT_TYPE = tuple(a[0] for a in ACTION_ORDER)
_SLOT_IDX = tuple(a[1] for a in ACTION_ORDER)


@njit
def valid_action_mask(battle_array):
    """Valid actions as a bitmask over ACTION_ORDER slots:
    bits 0-3 moves, bit 4 Struggle, bits 5-10 switches to party slots 0-5"""
    my_active = battle_array[_FIELD_MY_POK]
    mask = 0
    if battle_array[_FIELD_PHASE] != _BATTLEPHASE_DEATH_END_OF_TURN:
        base = my_active * POK_LEN
        usable = False
        for i in range(4):
            if battle_array[base + _MOVE_ID_IDXS[i]] == 0:
                break
            if battle_array[base + _MOVE_PP_IDXS[i]] > 0:
                mask |= 1 << i
                usable = True
        if not usable:
            mask |= 1 << 4
    for i in range(6):
        if i != my_active and battle_array[i * POK_LEN + _POK_CURRENT_HP] > 0:
            mask |= 1 << (5 + i)
    return mask


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
    (unused in the death phase, where only my replacement is picked).
    Returns the last opponent move used.
    """
    if battle_array[_FIELD_PHASE] == _BATTLEPHASE_DEATH_END_OF_TURN:
        switch_in_action(battle_array, action_idx)
        return opp_move

    a_type = action_type
    a_idx = action_idx
    # Bounded on purpose, an infinite loop inside njit can't be interrupted
    for _ in range(16):
        phase, _opp_idx = turn_sim(opp_move, (a_type, a_idx), battle_array)
        battle_array[_FIELD_PHASE] = phase
        if phase == _BATTLEPHASE_DEATH_END_OF_TURN or is_terminal_arr(battle_array):
            break
        my_idx = battle_array[_FIELD_MY_POK]
        active = battle_array[my_idx * POK_LEN:(my_idx + 1) * POK_LEN]
        if active[_POK_CHARGE_RECHARGE] == 0:
            break
        a_type = _ACTIONTYPE_MOVE
        a_idx = int(active[_POK_LOCKED_MOVE])
        opp_move = return_idx(battle_array)
    return opp_move


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
    phase, opp slot, status, vol status, HP bracket and stat stages of both actives"""
    opp_idx = battle_array[_FIELD_OPP_POK]
    opp = battle_array[(opp_idx + 6) * POK_LEN:(opp_idx + 7) * POK_LEN]
    is_death = battle_array[_FIELD_PHASE] == _BATTLEPHASE_DEATH_END_OF_TURN

    k1 = np.int64(1 if is_death else 0)
    k1 |= np.int64(opp_idx) << 1
    k1 |= np.int64(opp[_POK_STATUS]) << 4
    k1 |= np.int64(_hp_bracket(opp[_POK_CURRENT_HP], opp[_POK_MAX_HP])) << 7
    k1 |= (np.int64(opp[_POK_VOL_STATUS]) & 0xFFFF) << 10
    k2 = _stages_key(opp)

    if not is_death:
        my_idx = battle_array[_FIELD_MY_POK]
        me = battle_array[my_idx * POK_LEN:(my_idx + 1) * POK_LEN]
        k1 |= np.int64(me[_POK_STATUS]) << 26
        k1 |= np.int64(_hp_bracket(me[_POK_CURRENT_HP], me[_POK_MAX_HP])) << 29
        k1 |= (np.int64(me[_POK_VOL_STATUS]) & 0xFFFF) << 32
        k2 = (k2 << 28) | _stages_key(me)
    else:
        k2 = k2 << 28
    return k1, k2


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
        if self.opp_move_cache is None and self.phase != BattlePhase.DEATH_END_OF_TURN:
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
        if self.phase == BattlePhase.DEATH_END_OF_TURN:
            step_arr(self.battle_array, my_move_idx[0], my_move_idx[1], -50)
            self.opp_move_last = None
        else:
            self.opp_move_last = int(step_arr(
                self.battle_array, my_move_idx[0], my_move_idx[1], int(self.opp_move)
            ))
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
    bench_delta:  np.ndarray  # (12, 8) int32 — [hp, status, sleep_ctr, turns, pp0..pp3] per slot
    field_block:  np.ndarray  # (FIELD_LEN,) int32

    @staticmethod
    def from_state(state: 'GameState') -> 'NodeSnapshot':
        """
        Returns the values
        """
        bench = np.zeros((12, 8), dtype=np.int32)
        for i in range(6):
            pok = state.battle_array[i * POK_LEN : (i + 1) * POK_LEN]
            bench[i, 0] = pok[Pok.CURRENT_HP]
            bench[i, 1] = pok[Pok.STATUS]
            bench[i, 2] = pok[Pok.SLEEP_COUNTER]
            bench[i, 3] = pok[Pok.TURNS]
            for m, pp_idx in enumerate(_PP_IDXS):
                bench[i, 4 + m] = pok[pp_idx]
        for i in range(6):
            pok = state.battle_array[(i + 6) * POK_LEN : (i + 7) * POK_LEN]
            bench[i + 6, 0] = pok[Pok.CURRENT_HP]
            bench[i + 6, 1] = pok[Pok.STATUS]
            bench[i + 6, 2] = pok[Pok.SLEEP_COUNTER]
            bench[i + 6, 3] = pok[Pok.TURNS]
            for m, pp_idx in enumerate(_PP_IDXS):
                bench[i + 6, 4 + m] = pok[pp_idx]

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

    # 1. Patch the 8 mutable bench fields for all 12 party slots
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


@njit
def cvar_from_hist(hist, visits, alpha=0.15):
    """Mean of the worst alpha fraction of outcomes"""
    cutoff = visits * alpha
    accumulated = 0
    total_val = 0.0
    for i in range(N_BINS):
        count = hist[i]
        if count == 0:
            continue
        bin_mid = (i + 0.5) / N_BINS
        if accumulated + count <= cutoff:
            total_val += count * bin_mid
            accumulated += count
        else:
            # partial bin
            remaining = cutoff - accumulated
            total_val += remaining * bin_mid
            accumulated = cutoff
            break
    return total_val / cutoff if cutoff > 0 else 0.0


@njit
def best_slot(stats, parent_visits, c, risk_lambda, alpha):
    """UCB with CVaR penalty over the per-action stats rows, returns the winning slot"""
    log_parent_visits = math.log(parent_visits) if parent_visits > 1 else 0.0
    best = -1
    best_val = -np.inf
    for i in range(stats.shape[0]):
        visits = stats[i, 0]
        if visits == 0:
            continue
        avg = stats[i, 1] / visits
        cvar = cvar_from_hist(stats[i, 2:], visits, alpha)
        tail_gap = max(0.0, avg - cvar)
        exploration = c * math.sqrt(2 * log_parent_visits / visits)
        ucb_val = avg - risk_lambda * tail_gap + exploration
        if ucb_val > best_val or (ucb_val == best_val and random.getrandbits(1)):
            best_val = ucb_val
            best = i
    return best


class Node():
    """Tree node, stats holds one row per action: visits, total value, outcome histogram"""
    __slots__ = (
        'snapshot', 'children', 'visits', 'total_value', 'key',
        'wins', 'dead', 'win_chance', 'dead_avg', 'stats', 'expanded'
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

    def best_action(self, c=0.42, risk_lambda=0.3, alpha=0.15):
        """Best action by risk-adjusted UCB, returns (action key, outcome list)"""
        slot = best_slot(self.stats, self.visits, c, risk_lambda, alpha)
        if slot < 0:
            raise ValueError("best_action called on a node with no explored actions")
        key = ACTION_ORDER[slot]
        return key, self.children[key]
