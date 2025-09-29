"""
MCTS which is done in 4 steps:
1. Selection: The algorithm travels from the root of the tree to a leaf node,
using heuristics like the Upper Confidence Bound (UCB) to balance exploration and exploitation
2. Expansion: If the selected node isn/'t terminal,
MCTS expands the tree by adding child nodes representing possible future actions.
3. Simulation (Rollout): A random playout is run from the new node to a terminal state,
estimating its potential value.
4. Backpropagation: The results of the simulation are then propagated up the tree…"""
import copy
import math
from enum import Enum
from typing import List, Tuple
import numpy as np
from Models.idx_nparray import PokArray, MoveArray, MoveFlags, SecondaryArray
from Models.helper import count_party


class ActionType(Enum):
    """Move Action"""
    MOVE = "move"
    SWITCH = "switch"


class GameState():
    """Screenshot of the current gamestate"""
    def __init__(self, battle_array, my_active=0, opp_active=0, turn=1):
        self.battle_array = copy.deepcopy(battle_array)
        self.my_active = my_active  # Index of 0..5
        self.opp_active = opp_active  # Index of 0..5
        self.turn = turn

    def clone(self):
        """Clone"""
        return GameState(self.battle_array, self.my_active, self.opp_active, self.turn)

    def get_my_pokemon(self, idx: int) -> np.ndarray:
        """Get pokemon from my party by index (0-5)"""
        start = idx * len(PokArray)
        end = (idx + 1) * len(PokArray)
        return self.battle_array[start:end]

    def get_opp_pokemon(self, idx: int) -> np.ndarray:
        """Get pokemon from opponent party by index (0-5)"""
        start = (6 + idx) * len(PokArray)
        end = (7 + idx) * len(PokArray)
        return self.battle_array[start:end]

    def get_my_active(self) -> np.ndarray:
        """Get my active pokemon"""
        return self.get_my_pokemon(self.my_active)

    def get_opp_active(self) -> np.ndarray:
        """Get opponent's active pokemon"""
        return self.get_opp_pokemon(self.opp_active)

    def is_terminal(self) -> bool:
        """Check if battle is over"""
        my_alive = count_party(self.battle_array[0:(6 * len(PokArray))])
        opp_alive = count_party(self.battle_array[(6 * len(PokArray)):(12 * len(PokArray))])
        return my_alive == 0 or opp_alive == 0

    def get_valid_actions(self, is_player: bool = True) -> List[Tuple[str, int]]:
        """Get all valid actions for current player"""
        actions = []

        if is_player:
            active = self.get_my_active()
        else:
            active = self.get_opp_active()

        # Check each move slot
        for i in range(4):
            move_id_idx = PokArray.MOVE1_ID + (i * (len(MoveArray) + len(MoveFlags) + len(SecondaryArray)))
            if active[move_id_idx] != 0:  # Move exists
                actions.append((ActionType.MOVE.value, i))

        # Add switch actions
        for i in range(6):
            pokemon = self.get_my_pokemon(i) if is_player else self.get_opp_pokemon(i)
            # Can switch if pokemon is alive and not currently active
            if pokemon[PokArray.CURRENT_HP] > 0 and i != (self.my_active if is_player else self.opp_active):
                actions.append((ActionType.SWITCH.value, i))

        return actions


class Node():
    """
    - Store: state, parent, children, visit count, total value, untried actions
    - Key: nodes represent decision points, not chance outcomes
    """
    def __init__(self, state, parent=None, move=None):
        self.state = state
        self.parent = parent
        self.move = move
        self.children = {}
        self.visits = 0
        self.total_value = 0
        self.legal_moves = state.get_valid_actions(is_player=True)

    def ucb(self):
        """
        - Basic formula: value/visits + C * sqrt(ln(parent_visits)/visits)
        - For Nuzlocke: Modify C (exploration constant) to be conservative (~0.5)
        """
        c = 0.5
        if self.visits == 0:
            return float('inf')
        # Ensure parent.visits used in log is at least 1 to avoid log(0)
        if self.parent is None:
            parent_visits = 1
        else:
            parent_visits = max(1, self.parent.visits)
        return (self.total_value / self.visits) + c * math.sqrt(math.log(parent_visits) / self.visits)

    def best_child(self, c=0.5):
        """Best outcome"""
        return max(self.children.values(), key=lambda n: n.ucb(c))


def mcts(root_state, iterations):
    """MCTS"""
    root = Node(root_state)

    for _ in range(iterations):
        node = root
        state = root_state

        # 1) Selection
        while not node.legal_moves and node.children:
            node = node.best_child()
            # node.move is the action used to reach `node` from its parent
            if node.move is not None:
                state = state.step(node.move)
