"""Models for GameState and Nodes, and such, for MCTS to use"""
import math
import random
from dataclasses import dataclass
from typing import List, Tuple
import numpy as np
from Models.idx_const import (
    Pok, Field, POK_LEN, MOVE_STRIDE, Move
)
from Models.trainer_ai import return_idx
from Models.helper import count_party, ActionType, BattlePhase
from Engine.battle import turn_sim, switch_in_action


_MOVE_ID_IDXS = tuple(Pok.MOVE1_ID + i * MOVE_STRIDE for i in range(4))
_MOVE_PP_IDXS = tuple(idx + Move.PP for idx in _MOVE_ID_IDXS)
_POK_HP_OFFSETS = tuple(i * POK_LEN + Pok.CURRENT_HP for i in range(6))
N_BINS = 10


class GameState():
    """Screenshot of the current gamestate"""
    __slots__ = (
        'battle_array', 'my_active', 'opp_active', 'turn', 'phase', '_opp_ai', 'opp_move_cache'
    )
    def __init__(self, battle_array):
        self.battle_array = np.copy(battle_array)
        self.my_active = self.battle_array[Field.MY_POK]  # Index of 0..5
        self.opp_active = self.battle_array[Field.OPP_POK]  # Index of 0..5
        self.phase = self.battle_array[Field.PHASE]
        self._opp_ai = None
        self.opp_move_cache = None

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
            return self
        opp_move_idx = self.opp_move
        self.phase, opp_idx = turn_sim(opp_move_idx, my_move_idx, self.battle_array)
        self.battle_array[Field.PHASE] = self.phase
        if opp_idx >= 0:
            self.opp_active = opp_idx
        if my_move_idx[0] == ActionType.SWITCH:
            self.my_active = my_move_idx[1]
        if self.phase == BattlePhase.DEATH_END_OF_TURN:
            self.my_active = -1

        self.opp_move_cache = None # Needs to clear the cache so it picks a new one next time
        return self


@dataclass(slots=True)
class NodeSnapshot:
    """Just what i need to save in the node from the GameState so i save memory"""
    phase:      int
    opp_active: int
    my_slice:   np.ndarray
    opp_slice:  np.ndarray
    terminal:   bool

    @staticmethod
    def from_state(state: GameState) -> 'NodeSnapshot':
        """return the values"""
        return NodeSnapshot(
            phase      = state.phase,
            opp_active = state.opp_active,
            my_slice   = state.get_my_active().copy(),
            opp_slice  = state.get_opp_active().copy(),
            terminal   = state.is_terminal()
        )


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


HIST = np.zeros(N_BINS, dtype=np.uint16)


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
