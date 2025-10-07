"""
Self-play data collection pipeline for MCTS with proper storage and quality control
"""
import json
import pickle
import hashlib
from datetime import datetime
from pathlib import Path
from collections import deque
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
import numpy as np
import h5py
from SearchEngine.helper import create_random_initial_state


@dataclass
class GamePosition:
    """Single position from a game"""
    state: np.ndarray  # Battle array
    valid_actions: List[Tuple[str, int]]  # Legal moves
    action_probs: Dict[Tuple[str, int], float]  # MCTS visit distribution
    mcts_value: float  # MCTS evaluation (-1 to 1)
    turn: int
    phase: int

    # Filled at game end
    game_outcome: Optional[float] = None  # +1 win, -1 loss
    discounted_outcome: Optional[float] = None  # With decay

    # Metadata for quality control
    mcts_iterations: int = 0
    visit_confidence: float = 0.0  # Root visit count / iterations
    state_hash: Optional[str] = None

    def to_dict(self):
        """Convert to serializable dict"""
        return {
            'state': self.state.tolist() if isinstance(self.state, np.ndarray) else self.state,
            'valid_actions': self.valid_actions,
            'action_probs': {str(k): v for k, v in self.action_probs.items()},
            'mcts_value': self.mcts_value,
            'turn': self.turn,
            'phase': self.phase,
            'game_outcome': self.game_outcome,
            'discounted_outcome': self.discounted_outcome,
            'mcts_iterations': self.mcts_iterations,
            'visit_confidence': self.visit_confidence,
            'state_hash': self.state_hash
        }


class DataQualityFilter:
    """Filter out low-quality training positions"""

    def __init__(
            self,
            min_visits: int = 100,  # Minimum MCTS visits for position
            min_confidence: float = 0.05,  # Min visit_count/iterations ratio
            max_turn: int = 60,  # Skip very long games (likely loops)
            min_action_entropy: float = 0.1,  # Skip positions with no exploration
    ):
        self.min_visits = min_visits
        self.min_confidence = min_confidence
        self.max_turn = max_turn
        self.min_action_entropy = min_action_entropy

    def is_quality_position(self, position: GamePosition) -> bool:
        """Check if position meets quality standards"""

        # Skip if insufficient MCTS exploration
        if position.mcts_iterations < self.min_visits:
            return False

        # Skip if confidence too low
        if position.visit_confidence < self.min_confidence:
            return False

        # Skip extremely long games
        if position.turn > self.max_turn:
            return False

        # Calculate action entropy (diversity of action probabilities)
        if position.action_probs:
            probs = np.array(list(position.action_probs.values()))
            probs = probs[probs > 0]
            if len(probs) > 1:
                entropy = -np.sum(probs * np.log(probs + 1e-8))
                if entropy < self.min_action_entropy:
                    return False

        return True

    def filter_game(self, positions: List[GamePosition]) -> List[GamePosition]:
        """Filter a complete game's positions"""

        # Skip games that are too short or too long (loops)
        if len(positions) > self.max_turn:
            return []

        # Check game outcome consistency
        outcomes = [p.game_outcome for p in positions if p.game_outcome is not None]
        if len(set(outcomes)) > 1:  # Inconsistent outcomes
            print("Warning: Inconsistent game outcomes in positions")
            return []

        # Filter individual positions
        filtered = [p for p in positions if self.is_quality_position(p)]

        # Keep minimum percentage of positions from each game
        if len(filtered) < len(positions) * 0.3:  # Less than 30% passed
            return []  # Game likely had issues

        return filtered


class SelfPlayDataCollector:
    """Manages self-play data collection with versioning and quality control"""

    def __init__(
            self,
            save_dir: str = "training_data",
            buffer_size: int = 10000,  # Positions in memory before save
            games_per_file: int = 100,
            use_compression: bool = True
    ):

        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)

        self.buffer_size = buffer_size
        self.games_per_file = games_per_file
        self.use_compression = use_compression

        # Data buffers
        self.position_buffer = deque(maxlen=buffer_size)
        self.game_buffer = []
        self.current_game = []

        # Quality control
        self.quality_filter = DataQualityFilter()

        # Statistics
        self.stats = {
            'total_games': 0,
            'total_positions': 0,
            'filtered_games': 0,
            'filtered_positions': 0,
            'generation': 0
        }

        # Load existing stats if available
        self.load_stats()

    def start_game(self):
        """Begin collecting a new game"""
        self.current_game = []

    def add_position(
            self,
            state: np.ndarray,
            valid_actions: List[Tuple[str, int]],
            action_probs: Dict,
            mcts_value: float,
            mcts_iterations: int,
            root_visits: int,
            turn: int,
            phase: int
    ):
        """Add a position from ongoing game"""

        # Create position
        position = GamePosition(
            state=state.copy(),
            valid_actions=valid_actions.copy(),
            action_probs=action_probs.copy(),
            mcts_value=mcts_value,
            turn=turn,
            phase=phase,
            mcts_iterations=mcts_iterations,
            visit_confidence=root_visits / max(1, mcts_iterations),
            state_hash=hashlib.md5(state.tobytes()).hexdigest()[:16]
        )

        self.current_game.append(position)

    def end_game(self, outcome: float):
        """Finish game and process positions"""

        if not self.current_game:
            return  # need to have current_game

        # Assign outcomes with discount factor
        game_length = len(self.current_game)
        discount = 0.99  # Slightly prefer shorter games

        for i, position in enumerate(self.current_game):
            position.game_outcome = outcome
            # Discount based on distance from game end
            position.discounted_outcome = outcome * (discount ** (game_length - i - 1))

        # Quality filtering
        filtered_positions = self.quality_filter.filter_game(self.current_game)

        if filtered_positions:
            self.game_buffer.append(filtered_positions)
            self.position_buffer.extend(filtered_positions)

            # Update stats
            self.stats['total_games'] += 1
            self.stats['total_positions'] += len(filtered_positions)
        else:
            self.stats['filtered_games'] += 1
            self.stats['filtered_positions'] += len(self.current_game)

        # Save if buffer full
        if len(self.game_buffer) >= self.games_per_file:
            self.save_batch()

        # Clear current game
        self.current_game = []

    def save_batch(self):
        """Save current batch of games to disk"""

        if not self.game_buffer:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        gen = self.stats['generation']

        # Use HDF5 for efficient storage
        filename = self.save_dir / f"gen{gen:03d}_{timestamp}.h5"

        with h5py.File(filename, 'w') as f:
            # Create groups for organization
            f.attrs['generation'] = gen
            f.attrs['num_games'] = len(self.game_buffer)
            f.attrs['timestamp'] = timestamp

            for game_idx, game_positions in enumerate(self.game_buffer):
                game_group = f.create_group(f'game_{game_idx:04d}')

                # Stack all states for efficient storage
                states = np.array([p.state for p in game_positions])
                game_group.create_dataset(
                    'states',
                    data=states,
                    compression='gzip' if self.use_compression else None
                )

                # Store other data
                game_group.create_dataset(
                    'mcts_values', data=[p.mcts_value for p in game_positions]
                )
                game_group.create_dataset(
                    'outcomes', data=[p.game_outcome for p in game_positions]
                )
                game_group.create_dataset(
                    'turns', data=[p.turn for p in game_positions]
                )

                # Store action probabilities (variable size, so use pickle)
                action_probs_data = [p.action_probs for p in game_positions]
                game_group.create_dataset(
                    'action_probs', data=np.void(pickle.dumps(action_probs_data))
                )

                # Metadata
                game_group.attrs['game_length'] = len(game_positions)
                game_group.attrs['final_outcome'] = game_positions[0].game_outcome

        print(f"Saved {len(self.game_buffer)} games to {filename}")

        # Clear buffer
        self.game_buffer = []

        # Save stats
        self.save_stats()

    def save_stats(self):
        """Save collection statistics"""
        stats_file = self.save_dir / "collection_stats.json"
        with open(stats_file, 'w') as f:
            json.dump(self.stats, f, indent=2)

    def load_stats(self):
        """Load existing statistics"""
        stats_file = self.save_dir / "collection_stats.json"
        if stats_file.exists():
            with open(stats_file, 'r') as f:
                self.stats = json.load(f)

    def get_training_batch(self, batch_size: int = 512) -> Dict[str, np.ndarray]:
        """Sample a training batch from buffer"""

        if len(self.position_buffer) < batch_size:
            return None

        # Random sample from buffer
        indices = np.random.choice(len(self.position_buffer), batch_size, replace=False)
        batch = [self.position_buffer[i] for i in indices]

        # Format for neural network training
        states = np.array([p.state for p in batch])

        # Create action probability targets (you'll need to encode these based on your action space)
        # This is simplified - you'll need to map to your actual action encoding
        action_targets = np.zeros((batch_size, 10))  # Assuming max 10 possible actions
        value_targets = np.array([p.discounted_outcome for p in batch])

        return {
            'states': states,
            'action_targets': action_targets,  # You'll need to properly encode these
            'value_targets': value_targets,
            'mcts_values': np.array([p.mcts_value for p in batch])  # For comparison
        }


class IterativeTrainingManager:
    """Manages the iterative self-play and training loop"""

    def __init__(
            self,
            initial_iterations: int = 800,
            min_iterations: int = 200,
            games_per_generation: int = 1000
    ):
        self.current_generation = 0
        self.mcts_iterations = initial_iterations
        self.min_iterations = min_iterations
        self.games_per_generation = games_per_generation

        # Track performance over generations
        self.generation_stats = []

    def adjust_mcts_iterations(self):
        """Reduce MCTS iterations as NN improves"""
        # As NN gets better, need fewer MCTS iterations
        # But keep a minimum for exploration
        if self.current_generation > 0:
            reduction_factor = 0.9  # Reduce by 10% each generation
            new_iterations = int(self.mcts_iterations * reduction_factor)
            self.mcts_iterations = max(self.min_iterations, new_iterations)

    def should_train_value_first(self) -> bool:
        """Decide if we should train value network first"""
        # For first few generations, focus on value network
        # This gives better evaluations for MCTS
        return self.current_generation < 3

    def get_training_schedule(self) -> Dict:
        """Get training hyperparameters for current generation"""

        if self.current_generation == 0:
            # Initial training from random play
            return {
                'value_epochs': 10,
                'policy_epochs': 5,
                'learning_rate': 1e-3,
                'batch_size': 256
            }
        elif self.current_generation < 5:
            # Early generations - more training
            return {
                'value_epochs': 5,
                'policy_epochs': 5,
                'learning_rate': 5e-4,
                'batch_size': 512
            }
        else:
            # Later generations - fine-tuning
            return {
                'value_epochs': 3,
                'policy_epochs': 3,
                'learning_rate': 1e-4,
                'batch_size': 1024
            }


# Example usage
def run_self_play_game(
        collector: SelfPlayDataCollector,
        initial_state,
        mcts_iterations: int = 800
):
    """Run one self-play game with data collection"""

    from SearchEngine.my_mcts import mcts, GameState, Node  # pylint:disable=(C0415,W0611)

    # Start new game
    collector.start_game()

    state = initial_state
    turn = 0

    while not state.is_terminal():
        # Run MCTS
        root = Node(state)

        # Your MCTS implementation
        for _ in range(mcts_iterations):
            # ... MCTS iterations
            pass

        # Collect position data
        action_probs = {}
        total_visits = sum(sum(n.visits for n in nodes) for nodes in root.children.values())

        for action, nodes in root.children.items():
            visits = sum(n.visits for n in nodes)
            action_probs[action] = visits / total_visits if total_visits > 0 else 0

        # Add position to collector
        collector.add_position(
            state=state.battle_array,
            valid_actions=state.get_valid_actions(),
            action_probs=action_probs,
            mcts_value=root.total_value / root.visits if root.visits > 0 else 0,
            mcts_iterations=mcts_iterations,
            root_visits=root.visits,
            turn=turn,
            phase=state.phase
        )

        # Select action (sample from distribution for training diversity)
        if action_probs:
            actions = list(action_probs.keys())
            probs = list(action_probs.values())
            selected_action = np.random.choice(len(actions), p=probs)
            state = state.step(actions[selected_action-1])
        else:
            break

        turn += 1

    # Game ended - get outcome
    from SearchEngine.mcts_eval import evaluate_terminal  # pylint:disable=C0415
    outcome, _, _ = evaluate_terminal(state)
    collector.end_game(outcome)


# Training loop example
def training_pipeline():
    """Complete training pipeline"""

    collector = SelfPlayDataCollector()
    manager = IterativeTrainingManager()

    for generation in range(10):  # 10 generations
        print(f"\n=== Generation {generation} ===")

        # Adjust MCTS iterations
        manager.adjust_mcts_iterations()
        print(f"MCTS iterations: {manager.mcts_iterations}")

        # Run self-play games
        for game in range(manager.games_per_generation):
            initial_state = create_random_initial_state()

            run_self_play_game(
                collector,
                initial_state,
                manager.mcts_iterations
            )

            if game % 100 == 0:
                print(f"Game {game}, Total positions: {collector.stats['total_positions']}")

        # Save remaining data
        collector.save_batch()

        # Train neural networks
        schedule = manager.get_training_schedule()

        if manager.should_train_value_first():
            print("Training value network first...")
            # train_value_network(collector, schedule)  # You implement

            print("Training policy network...")
            # train_policy_network(collector, schedule)  # You implement
        else:
            print("Training both networks jointly...")
            # train_networks_jointly(collector, schedule)  # You implement

        # Increment generation
        manager.current_generation += 1
        collector.stats['generation'] = manager.current_generation
