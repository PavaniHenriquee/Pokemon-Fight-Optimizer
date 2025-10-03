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
import builtins
import random
from enum import Enum
from typing import List, Tuple
import numpy as np
from Models.idx_nparray import PokArray, MoveArray, MoveFlags, SecondaryArray
from Models.helper import count_party
from Models.trainer_ai import TrainerAI
from Engine.new_battle import Battle
from SearchEngine.mcts_eval import evaluate_terminal, rollout_pref, evaluate_state


class ActionType(Enum):
    """Move Action"""
    MOVE = "move"
    SWITCH = "switch"


class BattlePhase(Enum):
    """Where in the battle i am"""
    TURN_START = 1
    DEATH_END_OF_TURN = 2



class GameState():
    """Screenshot of the current gamestate"""
    def __init__(self, battle_array, my_active=0, opp_active=0, turn=1, phase=BattlePhase.TURN_START):
        self.battle_array = copy.deepcopy(battle_array)
        self.my_active = my_active  # Index of 0..5
        self.opp_active = opp_active  # Index of 0..5
        self.my_pty = self.battle_array[0:(6 * len(PokArray))]
        self.opp_pty = self.battle_array[(6 * len(PokArray)):(12 * len(PokArray))]
        self.turn = turn
        self.phase = phase
        self.opp_ai = TrainerAI()
        if self.phase != BattlePhase.DEATH_END_OF_TURN:
            self.opp_move = self.opp_move_choice()
        else:
            self.opp_move = None

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
                if pokemon[PokArray.CURRENT_HP] > 0 and i != (self.my_active if is_player else self.opp_active):
                    actions.append((ActionType.SWITCH.value, i))
            return actions  # Return here to prevent adding move actions

        # Normal turn phase - get active pokemon
        if is_player:
            active = self.get_my_active()
        else:
            active = self.get_opp_active()

        # Check each move slot
        for i in range(4):
            move_id_idx = PokArray.MOVE1_ID + (i * (len(MoveArray) + len(MoveFlags) + len(SecondaryArray)))
            if active[move_id_idx] != 0:  # Move exists
                actions.append((ActionType.MOVE.value, i))

        # Add switch actions for normal turn
        for i in range(6):
            pokemon = self.get_my_pokemon(i) if is_player else self.get_opp_pokemon(i)
            # Can switch if pokemon is alive and not currently active
            if pokemon[PokArray.CURRENT_HP] > 0 and i != (self.my_active if is_player else self.opp_active):
                actions.append((ActionType.SWITCH.value, i))

        return actions

    def opp_move_choice(self):
        """Uses the trainer AI to choose the move"""
        opp_idx = self.opp_ai.return_idx(
            self.battle_array[0:(6 * len(PokArray))],
            self.battle_array[(6 * len(PokArray)):(12 * len(PokArray))],
            self.get_my_active(),
            self.get_opp_active(),
            self.turn,
            self.get_opp_active()[PokArray.MOVE1_ID:PokArray.MOVE2_ID],
            self.get_opp_active()[PokArray.MOVE2_ID:PokArray.MOVE3_ID],
            self.get_opp_active()[PokArray.MOVE3_ID:PokArray.MOVE4_ID],
            self.get_opp_active()[PokArray.MOVE4_ID:PokArray.ITEM_ID]
        )
        return opp_idx
    
    def step(self, my_move_idx):
        """Simulate the entire turn"""
        new = self.clone()
        battle = Battle(
            battle_array=new.battle_array,
            my_active=new.my_active,
            opp_active=new.opp_active,
            turn=new.turn
        )
        if self.phase == BattlePhase.DEATH_END_OF_TURN:
            battle.end_of_turn(search=my_move_idx[1])
            if my_move_idx[0] == "switch":
                new.my_active = my_move_idx[1]
            else:
                pass
            new.phase = BattlePhase.TURN_START
            if new.my_active > 1:
                pass
            return new
        if my_move_idx[0] == 'switch':
            new.my_active = my_move_idx[1]
        opp_move_idx = self.opp_move
        orig_print = builtins.print
        try:
            builtins.print = lambda *a, **k: None
            new.phase, opp_idx = battle.turn_sim(opp_move_idx, my_move_idx)
            if opp_idx:
                new.opp_active = opp_idx
        finally:
            builtins.print = orig_print

        return new


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

    def best_action(self, c=1.4):
        """Best outcome using UCB; break ties and unvisited bias fairly."""
        # prefer a random unvisited child to avoid insertion-order bias
        unvisited = [(k, n) for k, n in self.children.items() if n.visits == 0]
        if unvisited:
            return random.choice(unvisited)

        best_key, best_node = None, None
        best_val = -float("inf")

        # guard: if parent visits is 0/1, exploration term becomes 0
        log_parent_visits = math.log(self.visits) if self.visits > 1 else 0.0

        for key, child in self.children.items():
            # average value
            avg = child.total_value / child.visits
            # UCB: avg + c * sqrt(2 * ln(N) / n)
            ucb_val = avg + c * math.sqrt(2 * (log_parent_visits) / child.visits)
            if ucb_val > best_val or (ucb_val == best_val and random.random() < 0.5):
                best_val, best_key, best_node = ucb_val, key, child

        return best_key, best_node


def mcts(root_state: GameState, iterations: int):
    """MCTS"""
    root = Node(root_state)

    for _ in range(iterations):
        node = root
        state = root_state.clone()
        path = [node]

        # 1) Selection
        while not state.is_terminal():
            untried_actions = [
                a for a in state.get_valid_actions() if a not in node.children
            ]

            if untried_actions:
                # We have unexplored actions, time to expand
                break
            elif node.children:
                # All actions explored, select best child
                action_key, action = node.best_action()  # Pick action with best UCB
                node = action
                state = state.step(action_key)
                path.append(node)
            else:
                raise ValueError("Failbreak")

        # 2) Expansion (if not terminal)
        if not state.is_terminal() and untried_actions:
            action = random.choice(untried_actions)
            state = state.step(action)
            child = Node(state, parent=node, move=action)
            child.total_value = evaluate_state(state, root)  # Set initial value based on heuristic
            node.children[action] = child
            path.append(child)
            node = child

        # 3) Simulation
        sim_state = state.clone()
        while not sim_state.is_terminal():
            # Random rollout handling phases
            if sim_state.phase == BattlePhase.DEATH_END_OF_TURN:
                valid = sim_state.get_valid_actions()
                action = random.choice(valid)
            else:
                action = rollout_pref(
                    sim_state.get_my_active(),
                    sim_state.get_opp_active(),
                    sim_state.opp_move,
                    sim_state.get_valid_actions()
                )
            sim_state = sim_state.step(action)

        # 4) Backpropagation
        value = evaluate_terminal(sim_state)  # Your evaluation
        for node in reversed(path):
            node.visits += 1
            node.total_value += value

    for actions, nodes in root.children.items():
        win_rate = (nodes.total_value / nodes.visits + 1) / 2
        print(f'actions: {actions}, visits: {(nodes.visits)}, total value: {int(nodes.total_value)}'
              f', win_rate: {round(win_rate*100, 2)}%')
