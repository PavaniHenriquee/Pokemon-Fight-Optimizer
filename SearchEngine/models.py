"""Models for GameState and Nodes, and such, for MCTS to use"""
import math
import random
from dataclasses import dataclass
import numpy as np
from types import SimpleNamespace
from typing import List, Tuple
from Models.idx_const import (
    Pok, Field, POK_LEN, MOVE_STRIDE
)
from Models.trainer_ai import TrainerAI
from Models.helper import count_party
from Engine.new_battle import Battle
from Engine.engine_helper import start_of_battle

ActionType = SimpleNamespace(
    MOVE = "move",
    SWITCH = "switch"
)


BattlePhase = SimpleNamespace(
    TURN_START = 0,
    DEATH_END_OF_TURN = 1
)


class GameState():
    """Screenshot of the current gamestate"""
    __slots__ = (
        'battle_array', 'my_active', 'opp_active', 'turn', 'phase', '_opp_ai', '_opp_move'
    )
    def __init__(self, battle_array, share_array=False):
        if share_array:
            self.battle_array = battle_array
        else:
            self.battle_array = np.copy(battle_array)
        self.my_active = int(self.battle_array[Field.MY_POK])  # Index of 0..5
        self.opp_active = int(self.battle_array[Field.OPP_POK])  # Index of 0..5
        self.turn = self.battle_array[Field.TURN]
        self.phase = self.battle_array[Field.PHASE]
        self._opp_ai = None
        self._opp_move = None

    @property
    def opp_ai(self):
        """Only apply Trainer AI to states that are necessary"""
        if self._opp_ai is None:
            self._opp_ai = TrainerAI()
        return self._opp_ai

    @property
    def opp_move(self):
        """Only do opp ai moves when necessary"""
        if self._opp_move is None and self.phase != BattlePhase.DEATH_END_OF_TURN:
            self._opp_move = self.opp_move_choice()
        return self._opp_move

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
        return self.battle_array[int(start):int(end)]

    def get_opp_pokemon(self, idx: int) -> np.ndarray:
        """Get pokemon from opponent party by index (0-5)"""
        start = (6 + idx) * POK_LEN
        end = (7 + idx) * POK_LEN
        return self.battle_array[int(start):int(end)]

    def get_my_active(self) -> np.ndarray:
        """Get my active pokemon"""
        return self.get_my_pokemon(self.my_active)

    def get_opp_active(self) -> np.ndarray:
        """Get opponent's active pokemon"""
        return self.get_opp_pokemon(self.opp_active)

    def is_terminal(self) -> bool:
        """Check if battle is over"""
        my_alive = count_party(self.my_pty)
        opp_alive = count_party(self.opp_pty)
        return my_alive == 0 or opp_alive == 0

    def get_valid_actions(self, is_player: bool = True) -> List[Tuple[str, int]]:
        """Get all valid actions for current player"""
        actions = []

        # Handle death phase first and return immediately
        if self.phase == BattlePhase.DEATH_END_OF_TURN:
            for i in range(6):
                pokemon = self.get_my_pokemon(i) if is_player else self.get_opp_pokemon(i)
                if pokemon[Pok.CURRENT_HP] > 0 and i != (self.my_active if is_player else self.opp_active):
                    actions.append((ActionType.SWITCH, i))
            return actions  # Return here to prevent adding move actions

        # Normal turn phase - get active pokemon
        if is_player:
            active = self.get_my_active()
        else:
            active = self.get_opp_active()

        # Check each move slot
        for i in range(4):
            move_id_idx = Pok.MOVE1_ID + (i * MOVE_STRIDE)
            if active[move_id_idx] != 0:  # Move exists
                actions.append((ActionType.MOVE, i))

        # Add switch actions for normal turn
        for i in range(6):
            pokemon = self.get_my_pokemon(i) if is_player else self.get_opp_pokemon(i)
            # Can switch if pokemon is alive and not currently active
            if pokemon[Pok.CURRENT_HP] > 0 and i != (self.my_active if is_player else self.opp_active):
                actions.append((ActionType.SWITCH, i))

        return actions

    def opp_move_choice(self) -> int:
        """Uses the trainer AI to choose the move"""
        opp_idx = self.opp_ai.return_idx(
            self.get_opp_active(),
            self.get_my_active(),
            self.battle_array[0:(6 * POK_LEN)],
            self.battle_array[(6 * POK_LEN):(12 * POK_LEN)],
            self.turn
        )
        return opp_idx

    def step(self, my_move_idx):
        """Simulate the entire turn"""
        new = self.clone()
        if new.turn == 0:
            start_of_battle(new.battle_array)
        battle = Battle(
            battle_array=new.battle_array
        )
        if new.phase == BattlePhase.DEATH_END_OF_TURN:
            battle.switch_in_action(my_move_idx[1])
            if my_move_idx[0] == "switch":
                new.my_active = my_move_idx[1]
                new.battle_array[Field.MY_POK] = my_move_idx[1]
            else:
                pass
            new.phase = int(BattlePhase.TURN_START)
            new.battle_array[Field.PHASE] = BattlePhase.TURN_START
            return new
        opp_move_idx = self.opp_move
        new.phase, opp_idx = battle.turn_sim(opp_move_idx, my_move_idx)
        new.battle_array[Field.PHASE] = new.phase
        if opp_idx:
            new.opp_active = opp_idx
        if my_move_idx[0] == 'switch':
            new.my_active = my_move_idx[1]
            new.battle_array[Field.MY_POK] = my_move_idx[1]

        return new


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
            phase      = int(state.phase),
            opp_active = int(state.opp_active),
            my_slice   = state.get_my_active().copy(),
            opp_slice  = state.get_opp_active().copy(),
            terminal   = state.is_terminal()
        )


class Node():
    """
    - Store: state, parent, children, visit count, total value, untried actions
    - Key: nodes represent decision points, not chance outcomes
    """
    __slots__ = (
        'snapshot', 'children', 'visits', 'total_value',
        'wins', 'dead', 'win_chance', 'dead_avg'
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

    def best_action(self, c=0.6):
        """Best outcome using UCB; break ties and unvisited bias fairly."""
        # prefer a random unvisited child to avoid insertion-order bias

        best_key, best_node = None, None
        best_val = -float("inf")

        # guard: if parent visits is 0/1, exploration term becomes 0
        log_parent_visits = math.log(self.visits) if self.visits > 1 else 0.0

        for key, child in self.children.items():
            # average value
            c_total_value = 0
            c_visits = 0
            for chi in child:
                c_total_value += chi.total_value
                c_visits += chi.visits
            avg = c_total_value / c_visits
            # UCB: avg + c * sqrt(2 * ln(N) / n)
            ucb_val = avg + c * math.sqrt(2 * (log_parent_visits) / c_visits)
            if ucb_val > best_val or (ucb_val == best_val and random.getrandbits(1)):
                best_val, best_key, best_node = ucb_val, key, child

        return best_key, best_node
