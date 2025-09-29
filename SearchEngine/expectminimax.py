"""Expect minmax"""
from typing import Tuple, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import numpy as np

# Import your existing modules
from Models.idx_nparray import PokArray, MoveArray, MoveFlags, SecondaryArray, BaseArray, AbilityIdx
from Models.helper import Status, MoveCategory, count_party
from Models.trainer_ai import TrainerAI
from Engine.damage_calc import calculate_damage
from Engine.engine_helper import check_speed
from Utils.helper import get_type_effectiveness
from DataBase.PkDB import PokemonName
from DataBase.MoveDB import MoveName

class ActionType(Enum):
    """Move Action"""
    MOVE = "move"
    SWITCH = "switch"

@dataclass
class BattleState:
    """Represents the complete battle state using numpy arrays"""
    battle_array: np.ndarray  # The full 12-pokemon battle array
    my_active_idx: int  # 0-5 index in my party
    opp_active_idx: int  # 0-5 index in opponent party
    turn_count: int

    def copy(self):
        """Deep copy the battle state"""
        return BattleState(
            battle_array=self.battle_array.copy(),
            my_active_idx=self.my_active_idx,
            opp_active_idx=self.opp_active_idx,
            turn_count=self.turn_count
        )

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

    def get_active_my(self) -> np.ndarray:
        """Get my active pokemon"""
        return self.get_my_pokemon(self.my_active_idx)

    def get_active_opp(self) -> np.ndarray:
        """Get opponent's active pokemon"""
        return self.get_opp_pokemon(self.opp_active_idx)

    def is_terminal(self) -> bool:
        """Check if battle is over"""
        my_alive = count_party(self.battle_array[0:(6 * len(PokArray))])
        opp_alive = count_party(self.battle_array[(6 * len(PokArray)):(12 * len(PokArray))])
        return my_alive == 0 or opp_alive == 0

    def get_valid_actions(self, is_player: bool = True) -> List[Tuple[str, int]]:
        """Get all valid actions for current player"""
        actions = []

        if is_player:
            active = self.get_active_my()
        else:
            active = self.get_active_opp()

        # Add move actions (only if not disabled by status)
        if active[PokArray.STATUS] not in [Status.SLEEP, Status.FREEZE]:
            # Check each move slot
            for i in range(4):
                move_id_idx = PokArray.MOVE1_ID + (i * (len(MoveArray) + len(MoveFlags) + len(SecondaryArray)))
                if active[move_id_idx] != 0:  # Move exists
                    actions.append((ActionType.MOVE.value, i))

        # Add switch actions
        for i in range(6):
            pokemon = self.get_my_pokemon(i) if is_player else self.get_opp_pokemon(i)
            # Can switch if pokemon is alive and not currently active
            if pokemon[PokArray.CURRENT_HP] > 0 and i != (self.my_active_idx if is_player else self.opp_active_idx):
                actions.append((ActionType.SWITCH.value, i))

        return actions

class ExpectiminimaxAI:
    """Don't know"""
    def __init__(self, max_depth: int = 3, nuzlocke_mode: bool = True, use_opponent_ai: bool = True):
        self.max_depth = max_depth
        self.nuzlocke_mode = nuzlocke_mode
        self.use_opponent_ai = use_opponent_ai
        self.trainer_ai = TrainerAI() if use_opponent_ai else None
        self.nodes_evaluated = 0

        # Weights for evaluation function - heavily favor survival for Nuzlocke
        self.weights = {
            'hp_weight': 100,
            'death_penalty': -10000 if nuzlocke_mode else -1000,
            'opponent_hp_weight': -50,
            'type_advantage': 20,
            'speed_advantage': 10,
            'status_weight': 30,
            'stat_stage_bonus': 5
        }

    def evaluate_state(self, state: BattleState) -> float:
        """Evaluate the current battle state"""
        score = 0

        # Check terminal states first
        if state.is_terminal():
            my_alive = count_party(state.battle_array[0:(6 * len(PokArray))])
            opp_alive = count_party(state.battle_array[(6 * len(PokArray)):(12 * len(PokArray))])

            if my_alive == 0:
                return -100000  # Loss
            elif opp_alive == 0:
                # Win, but penalize deaths in nuzlocke
                my_deaths = 6 - my_alive
                return 100000 + (my_deaths * self.weights['death_penalty'])

        # Evaluate HP differential for all pokemon
        for i in range(6):
            my_pok = state.get_my_pokemon(i)
            opp_pok = state.get_opp_pokemon(i)

            # My pokemon
            if my_pok[PokArray.CURRENT_HP] > 0:
                hp_percent = my_pok[PokArray.CURRENT_HP] / my_pok[PokArray.MAX_HP]
                score += hp_percent * self.weights['hp_weight']
            else:
                score += self.weights['death_penalty']

            # Opponent pokemon
            if opp_pok[PokArray.CURRENT_HP] > 0:
                hp_percent = opp_pok[PokArray.CURRENT_HP] / opp_pok[PokArray.MAX_HP]
                score += hp_percent * self.weights['opponent_hp_weight']

        # Active Pokemon advantages
        my_active = state.get_active_my()
        opp_active = state.get_active_opp()

        # Speed advantage (accounting for paralysis and stat stages)
        my_speed, opp_speed = check_speed(my_active, opp_active)
        if my_speed > opp_speed:
            score += self.weights['speed_advantage']

        # Status conditions
        if opp_active[PokArray.STATUS] != 0:
            score += self.weights['status_weight']
        if my_active[PokArray.STATUS] != 0:
            score -= self.weights['status_weight']

        # Stat stages
        stat_stages = [
            PokArray.ATTACK_STAT_STAGE,
            PokArray.DEFENSE_STAT_STAGE,
            PokArray.SPECIAL_ATTACK_STAT_STAGE,
            PokArray.SPECIAL_DEFENSE_STAT_STAGE,
            PokArray.SPEED_STAT_STAGE
        ]
        for stage_idx in stat_stages:
            score += my_active[stage_idx] * self.weights['stat_stage_bonus']
            score -= opp_active[stage_idx] * self.weights['stat_stage_bonus']

        # Type advantage for my moves vs opponent
        max_effectiveness = 0
        for i in range(4):
            move_type_idx = PokArray.MOVE1_TYPE + (i * (len(MoveArray) + len(MoveFlags) + len(SecondaryArray)))
            move_cat_idx = PokArray.MOVE1_CATEGORY + (i * (len(MoveArray) + len(MoveFlags) + len(SecondaryArray)))

            if my_active[move_type_idx] != 0 and my_active[move_cat_idx] != MoveCategory.STATUS:
                effectiveness = get_type_effectiveness(
                    my_active[move_type_idx],
                    opp_active[PokArray.TYPE1],
                    opp_active[PokArray.TYPE2]
                )
                max_effectiveness = max(max_effectiveness, effectiveness)

        score += (max_effectiveness - 1) * self.weights['type_advantage']

        return score

    def get_move_array(self, pokemon: np.ndarray, move_idx: int) -> np.ndarray:
        """Extract move array from pokemon array"""
        move_offset = len(MoveArray) + len(MoveFlags) + len(SecondaryArray)
        base_offset = len(BaseArray) + len(AbilityIdx)  # BaseArray + AbilityIdx lengths
        start = base_offset + (move_offset * move_idx)
        end = base_offset + (move_offset * (move_idx + 1))
        return pokemon[start:end]

    def expectiminimax(self, state: BattleState, depth: int, alpha: float, beta: float,
                      is_max_node: bool, is_chance_node: bool = False) -> Tuple[float, Optional[Tuple]]:
        """Main expectiminimax algorithm with alpha-beta pruning"""
        self.nodes_evaluated += 1

        # Terminal or depth limit
        if state.is_terminal() or depth == 0:
            return self.evaluate_state(state), None

        # Handle chance nodes
        if is_chance_node:
            return self.evaluate_chance_node(state, depth, alpha, beta, is_max_node)

        if is_max_node:
            # Player's turn - maximize score
            max_eval = float('-inf')
            best_action = None

            for action in state.get_valid_actions(is_player=True):
                # Create child state
                child_state = self.apply_action(state.copy(), action, is_player=True)

                # Recursively evaluate (next node is opponent's turn)
                eval_score, _ = self.expectiminimax(child_state, depth, alpha, beta, False, False)

                if eval_score > max_eval:
                    max_eval = eval_score
                    best_action = action

                alpha = max(alpha, eval_score)
                if beta <= alpha:
                    break  # Beta cutoff

            return max_eval, best_action

        else:
            # Opponent's turn
            if self.use_opponent_ai:
                return self.evaluate_opponent_turn_with_ai(state, depth, alpha, beta)
            else:
                # Simple minimax for opponent
                min_eval = float('inf')
                best_action = None

                for action in state.get_valid_actions(is_player=False):
                    child_state = self.apply_action(state.copy(), action, is_player=False)
                    eval_score, _ = self.expectiminimax(child_state, depth - 1, alpha, beta, True, True)

                    if eval_score < min_eval:
                        min_eval = eval_score
                        best_action = action

                    beta = min(beta, eval_score)
                    if beta <= alpha:
                        break  # Alpha cutoff

                return min_eval, best_action

    def evaluate_chance_node(self, state: BattleState, depth: int, alpha: float, beta: float,
                           is_max_node: bool) -> Tuple[float, None]:
        """Evaluate chance nodes by calculating expected value"""
        expected_value = 0

        # Simplified: just consider damage roll variance
        # Min damage (85%), average (92.5%), max (100%)
        damage_outcomes = [
            (0.85, 0.2),   # Min damage
            (0.925, 0.6),  # Average damage
            (1.0, 0.2)     # Max damage
        ]

        for _, prob in damage_outcomes:
            # In a real implementation, you'd apply the damage multiplier to the last move
            # For now, just evaluate the current state
            eval_score, _ = self.expectiminimax(state, depth - 1, alpha, beta, is_max_node, False)
            expected_value += eval_score * prob

        return expected_value, None

    def evaluate_opponent_turn_with_ai(self, state: BattleState, depth: int, alpha: float, beta: float) -> Tuple[float, None]:
        """Evaluate opponent's turn using your TrainerAI"""
        my_active = state.get_active_my()
        opp_active = state.get_active_opp()

        # Get opponent's moves
        opp_moves = []
        for i in range(4):
            move = self.get_move_array(opp_active, i)
            if move[MoveArray.ID] != 0:
                opp_moves.append(move)

        # Use TrainerAI to get move scores
        my_pty = state.battle_array[0:(6 * len(PokArray))]
        opp_pty = state.battle_array[(6 * len(PokArray)):(12 * len(PokArray))]

        move_scores = self.trainer_ai.choose_move(
            opp_active,
            my_active,
            my_pty,
            opp_pty,
            state.turn_count,
            opp_active[PokArray.MOVE1_ID:PokArray.MOVE2_ID],
            opp_active[PokArray.MOVE2_ID:PokArray.MOVE3_ID],
            opp_active[PokArray.MOVE3_ID:PokArray.MOVE4_ID],
            opp_active[PokArray.MOVE4_ID:PokArray.ITEM_ID]
        )

        # Convert scores to probabilities
        if move_scores:
            max_score = max(info['score'] for info in move_scores.values())
            best_moves = [idx for idx, info in move_scores.items() if info['score'] == max_score]

            # Evaluate the most likely move(s)
            expected_value = 0
            for move_idx in best_moves:
                prob = 1.0 / len(best_moves)
                action = (ActionType.MOVE.value, move_idx)
                child_state = self.apply_action(state.copy(), action, is_player=False)
                eval_score, _ = self.expectiminimax(child_state, depth - 1, alpha, beta, True, True)
                expected_value += eval_score * prob

            return expected_value, None

        # Fallback if no moves available
        return self.evaluate_state(state), None

    def apply_action(self, state: BattleState, action: Tuple, is_player: bool) -> BattleState:
        """Apply an action to create a new state"""
        action_type, action_index = action

        if action_type == ActionType.SWITCH.value:
            if is_player:
                state.my_active_idx = action_index
            else:
                state.opp_active_idx = action_index

        elif action_type == ActionType.MOVE.value:
            # Apply move effects (simplified)
            if is_player:
                attacker = state.get_active_my()
                defender = state.get_active_opp() 
                move = self.get_move_array(attacker, action_index)
            else:
                attacker = state.get_active_opp()
                defender = state.get_active_my()
                move = self.get_move_array(attacker, action_index)

            if move[MoveArray.CATEGORY] != MoveCategory.STATUS:
                # Use your existing damage calculation with average roll
                damage, _ = calculate_damage(attacker, defender, move, roll_multiplier=0.925)
                defender[PokArray.CURRENT_HP] = max(0, defender[PokArray.CURRENT_HP] - damage)

        state.turn_count += 1
        return state

    def get_action_probabilities(self, battle_array: np.ndarray, my_active_idx: int,
                                 opp_active_idx: int, turn: int) -> Dict[str, float]:
        """Main method to call - returns probabilities for each possible action"""
        self.nodes_evaluated = 0

        # Create initial state
        state = BattleState(
            battle_array=battle_array.copy(),
            my_active_idx=my_active_idx,
            opp_active_idx=opp_active_idx,
            turn_count=turn
        )

        actions = state.get_valid_actions(is_player=True)
        action_values = {}

        # Evaluate each possible action
        for action in actions:
            child_state = self.apply_action(state.copy(), action, is_player=True)
            value, _ = self.expectiminimax(child_state, self.max_depth - 1,
                                          float('-inf'), float('inf'), False, False)
            action_values[action] = value

        # Convert to probabilities using softmax
        action_probs = self.value_to_probability(action_values)

        # Format for display
        formatted_probs = {}
        for action, prob in action_probs.items():
            action_type, index = action
            if action_type == ActionType.MOVE.value:
                my_active = state.get_active_my()
                move_id_idx = PokArray.MOVE1_ID + (index * (len(MoveArray) + len(MoveFlags) + len(SecondaryArray)))
                move_name = MoveName(my_active[move_id_idx]).name if my_active[move_id_idx] != 0 else "None"
                formatted_probs[f"move_{index}_{move_name}"] = prob
            else:
                pokemon = state.get_my_pokemon(index)
                pokemon_name = PokemonName(pokemon[PokArray.ID]).name if pokemon[PokArray.ID] != 0 else "None"
                formatted_probs[f"switch_{index}_{pokemon_name}"] = prob

        return formatted_probs

    def value_to_probability(self, action_values: Dict, temperature: float = 0.1) -> Dict:
        """Convert action values to probabilities using softmax"""
        if not action_values:
            return {}

        # Lower temperature = more deterministic
        max_value = max(action_values.values())
        exp_values = {}
        for action, value in action_values.items():
            exp_values[action] = np.exp((value - max_value) / temperature)

        total = sum(exp_values.values())
        return {action: v / total for action, v in exp_values.items()}


class AIBattleInterface:
    """Interface to use with your Battle class"""

    def __init__(self, nuzlocke_mode: bool = True, max_depth: int = 3):
        self.ai = ExpectiminimaxAI(max_depth=max_depth, nuzlocke_mode=nuzlocke_mode)

    def get_ai_decision(self, battle_instance):
        """
        Get AI decision for current battle state
        battle_instance: Your Battle class instance
        """
        # Find active indices
        my_active_idx = 0
        opp_active_idx = 0

        for i in range(6):
            if np.array_equal(battle_instance.current_pokemon, 
                             battle_instance.my_pty[(i * len(PokArray)):((i+1) * len(PokArray))]):
                my_active_idx = i
                break

        for i in range(6):
            if np.array_equal(battle_instance.current_opp,
                             battle_instance.opp_pty[(i * len(PokArray)):((i+1) * len(PokArray))]):
                opp_active_idx = i
                break

        # Get action probabilities
        action_probs = self.ai.get_action_probabilities(
            battle_instance.battle_array,
            my_active_idx,
            opp_active_idx,
            battle_instance.turn
        )

        # Get best action
        state = BattleState(
            battle_array=battle_instance.battle_array.copy(),
            my_active_idx=my_active_idx,
            opp_active_idx=opp_active_idx,
            turn_count=battle_instance.turn
        )

        _, best_action = self.ai.expectiminimax(state, self.ai.max_depth,
                                               float('-inf'), float('inf'), True, False)

        return {
            'probabilities': action_probs,
            'best_action': best_action,
            'nodes_evaluated': self.ai.nodes_evaluated
        }

    def format_for_display(self, ai_decision):
        """Format AI decision for display"""
        print("\n=== AI Recommendation ===")
        print(f"Nodes evaluated: {ai_decision['nodes_evaluated']}")
        print("\nAction Probabilities:")

        sorted_actions = sorted(ai_decision['probabilities'].items(),
                              key=lambda x: x[1], reverse=True)

        for action_str, prob in sorted_actions:
            print(f"  {action_str}: {prob:.1%}")

        if ai_decision['best_action']:
            action_type, idx = ai_decision['best_action']
            if action_type == ActionType.MOVE.value:
                print(f"\nBest Action: Use move {idx + 1}")
            else:
                print(f"\nBest Action: Switch to Pokemon {idx + 1}")

        return ai_decision


'''# Integration with your existing Battle class
def integrate_ai_with_battle(battle_instance):
    """
    Example of how to integrate the AI with your Battle class
    Call this in your selection() method
    """
    ai_interface = AIBattleInterface(nuzlocke_mode=True, max_depth=3)
    ai_decision = ai_interface.get_ai_decision(battle_instance)
    ai_interface.format_for_display(ai_decision)

    # Return the best action for automatic play, or just display for manual play
    return ai_decision


# Modified selection method for your Battle class
def ai_enhanced_selection(self):
    """
    Modified selection method that shows AI recommendations
    Add this to your Battle class or use it to replace the selection method
    """
    # Get opponent move first (as you already do)
    opp_move = self.opp_ai.return_idx(
        self.current_opp,
        self.current_pokemon,
        self.my_pty,
        self.opp_pty,
        self.turn,
        self.op_move1,
        self.op_move2,
        self.op_move3,
        self.op_move4
    )

    # Get AI recommendation
    print("\n" + "="*50)
    ai_decision = integrate_ai_with_battle(self)
    print("="*50 + "\n")

    # Still let player choose
    current_move_idx, switch_move_idx = battle_menu(self.current_pokemon, self.my_pty)

    return opp_move, current_move_idx, switch_move_idx'''
