"""Models for GameState and Nodes, and such, for MCTS to use"""
import math
import random
from dataclasses import dataclass
from typing import List, Tuple
import numpy as np
from Models.idx_const import (
    Pok, Field, POK_LEN, MOVE_STRIDE, Move, FIELD_LEN
)
from Models.constants import _STATUS_TOXIC, _POK_CHARGE_RECHARGE, _POK_LOCKED_MOVE
from Models.trainer_ai import return_idx
from Models.helper import count_party, ActionType, BattlePhase
from Engine.battle import turn_sim, switch_in_action


_MOVE_ID_IDXS = tuple(Pok.MOVE1_ID + i * MOVE_STRIDE for i in range(4))
_MOVE_PP_IDXS = tuple(idx + Move.PP for idx in _MOVE_ID_IDXS)
_POK_HP_OFFSETS = tuple(i * POK_LEN + Pok.CURRENT_HP for i in range(6))
N_BINS = 10
_PP_IDXS = (
    Pok.MOVE1_ID + Move.PP,
    Pok.MOVE2_ID + Move.PP,
    Pok.MOVE3_ID + Move.PP,
    Pok.MOVE4_ID + Move.PP,
)


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
        return count_party(self.my_pty) == 0 or count_party(self.opp_pty) == 0

    def get_valid_actions(self) -> List[Tuple[int, int]]:
        """Get all valid actions for current player"""
        actions = []
        ba = self.battle_array
        my_active = self.my_active

        if self.phase == BattlePhase.DEATH_END_OF_TURN:
            for i, hp_off in enumerate(_POK_HP_OFFSETS):
                if ba[hp_off] > 0 and i != my_active:
                    actions.append((ActionType.SWITCH, i))
            return actions

        pok_start = my_active * POK_LEN
        usable_moves = False
        for i, (mid, mpp) in enumerate(zip(_MOVE_ID_IDXS, _MOVE_PP_IDXS)):
            if ba[pok_start + mid] != 0:
                if ba[pok_start + mpp] > 0:
                    actions.append((ActionType.MOVE, i))
                    usable_moves = True
                else:
                    break
            else:
                break

        if not usable_moves:
            actions.append((ActionType.MOVE, 10))

        for i, hp_off in enumerate(_POK_HP_OFFSETS):
            if ba[hp_off] > 0 and i != my_active:
                actions.append((ActionType.SWITCH, i))

        return actions

    def opp_move_choice(self) -> int:
        """Uses the trainer AI to choose the move"""
        opp_idx = return_idx(self.battle_array)
        return opp_idx

    def step(self, my_move_idx):
        """Simulate the entire turn"""
        if self.phase == BattlePhase.DEATH_END_OF_TURN:
            switch_in_action(self.battle_array, my_move_idx[1])
            self.my_active = my_move_idx[1]
            self.phase = BattlePhase.TURN_START
            self.opp_move_last = None
            return self
        opp_move_idx = self.opp_move
        self.opp_move_last = int(opp_move_idx)
        self.phase, opp_idx = turn_sim(opp_move_idx, my_move_idx, self.battle_array)
        self.battle_array[Field.PHASE] = self.phase
        if opp_idx >= 0:
            self.opp_active = opp_idx
        if my_move_idx[0] == ActionType.SWITCH:
            self.my_active = my_move_idx[1]
        if self.phase == BattlePhase.DEATH_END_OF_TURN:
            self.my_active = -1

        self.opp_move_cache = None # Needs to clear the cache so it picks a new one next time
        if self.phase != BattlePhase.DEATH_END_OF_TURN and not self.is_terminal():
            active_pok = self.get_my_active()
            if active_pok[_POK_CHARGE_RECHARGE] != 0:
                locked_move = int(active_pok[_POK_LOCKED_MOVE])
                if locked_move >= 0:
                    return self.step((ActionType.MOVE, locked_move))
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


HIST = np.zeros(N_BINS, dtype=np.uint32)


class Node():
    """
    - Store: state, parent, children, visit count, total value, untried actions
    - Key: nodes represent decision points, not chance outcomes
    """
    __slots__ = (
        'snapshot', 'children', 'visits', 'total_value',
        'wins', 'dead', 'win_chance', 'dead_avg', 'hist'
    )
    def __init__(self, state):
        self.snapshot = NodeSnapshot.from_state(state)
        self.children = {}
        self.visits = 0
        self.total_value = 0
        self.wins = 0
        self.dead = 0
        self.win_chance = 0.0
        self.dead_avg = 0
        self.hist = HIST.copy()

    def best_action(self, c=0.42, risk_lambda=0.3, alpha=0.15):
        """Best outcome using UCB; break ties and unvisited bias fairly."""

        best_key, best_node = None, None
        best_val = -float("inf")

        # guard: if parent visits is 0/1, exploration term becomes 0
        log_parent_visits = math.log(self.visits) if self.visits > 1 else 0.0

        for key, child in self.children.items():
            c_total_value = 0
            c_visits = 0
            c_hist = HIST.copy()
            for chi in child:
                c_total_value += chi.total_value
                c_visits      += chi.visits
                c_hist        += chi.hist

            avg         = c_total_value / c_visits
            cvar        = cvar_from_hist(c_hist, c_visits, alpha)
            tail_gap    = max(0.0, avg - cvar)          # how far the tail falls below the mean
            exploration = c * math.sqrt(2 * log_parent_visits / c_visits)
            ucb_val     = avg - risk_lambda * tail_gap + exploration

            if ucb_val > best_val or (ucb_val == best_val and random.getrandbits(1)):
                best_val, best_key, best_node = ucb_val, key, child

        return best_key, best_node
