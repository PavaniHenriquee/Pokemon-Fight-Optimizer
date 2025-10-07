"""
PyTorch Neural Network for Pokemon Battle MCTS
Handles both value and policy outputs with nuzlocke death penalties
"""
import pickle
from pathlib import Path
from typing import Dict, List, Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import numpy as np
import h5py
from SearchEngine.my_mcts import GameState
from SearchEngine.my_mcts import Node
from Models.idx_const import POK_LEN, FIELD_LEN



class PokemonBattleNet(nn.Module):
    """
    Neural network for Pokemon battles
    Input: Battle state array
    Outputs: 
        - Policy: Probability distribution over actions (9 possible: 4 moves + 5 switches)
        - Value: Expected outcome (-1 to 1)
    """

    def __init__(
            self,
            state_size: int,  # Size of battle array
            action_size: int = 9,  # 4 moves + 5 switches
            hidden_size: int = 512,
            num_hidden_layers: int = 4,
            dropout_rate: float = 0.1
    ):
        super().__init__()

        self.state_size = state_size
        self.action_size = action_size

        # Shared trunk network
        layers = []

        # Input layer
        layers.append(nn.Linear(state_size, hidden_size))
        layers.append(nn.BatchNorm1d(hidden_size))
        layers.append(nn.ReLU())
        layers.append(nn.Dropout(dropout_rate))

        # Hidden layers
        for _ in range(num_hidden_layers - 1):
            layers.append(nn.Linear(hidden_size, hidden_size))
            layers.append(nn.BatchNorm1d(hidden_size))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(dropout_rate))

        self.trunk = nn.Sequential(*layers)

        # Policy head (for move selection)
        self.policy_head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Linear(hidden_size // 2, action_size)
        )

        # Value head (for position evaluation)
        self.value_head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Linear(hidden_size // 2, 1),
            nn.Tanh()  # Output between -1 and 1
        )

        # Initialize weights
        self._initialize_weights()

    def _initialize_weights(self):
        """Initialize network weights using He initialization"""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.kaiming_normal_(module.weight, mode='fan_in', nonlinearity='relu')
                if module.bias is not None:
                    nn.init.zeros_(module.bias)

    def forward(self, x, valid_actions_mask=None):
        """
        Forward pass
        Args:
            x: Battle state tensor [batch_size, state_size]
            valid_actions_mask: Binary mask for legal actions [batch_size, action_size]
        Returns:
            policy_logits: Unnormalized action probabilities [batch_size, action_size]
            value: Position evaluation [batch_size, 1]
        """
        # Shared computation
        features = self.trunk(x)

        # Policy output
        policy_logits = self.policy_head(features)

        # Mask invalid actions with very negative values
        if valid_actions_mask is not None:
            policy_logits = policy_logits.masked_fill(~valid_actions_mask, -1e9)

        # Value output
        value = self.value_head(features)

        return policy_logits, value

    def predict(self, state, valid_actions_mask=None):
        """Inference for single position"""
        self.eval()
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0)
            if valid_actions_mask is not None:
                mask_tensor = torch.BoolTensor(valid_actions_mask).unsqueeze(0)
            else:
                mask_tensor = None

            policy_logits, value = self.forward(state_tensor, mask_tensor)
            policy_probs = F.softmax(policy_logits, dim=1).squeeze(0)
            value = value.item()

        return policy_probs.numpy(), value


def encode_action(action: Tuple[str, int]) -> int:
    """
    Encode action tuple to index
    Moves: 0-3 (indices of moves)
    Switches: 4-8 (indices of pokemon to switch to, minus 1 since can't switch to self)
    """
    action_type, action_idx = action
    if action_type == 'move':
        return action_idx  # 0-3
    else:  # switch
        # Map switch indices 0-5 to positions 4-8
        # But skip current pokemon's index
        return 4 + min(action_idx, 4)  # Simple mapping, adjust based on actual logic


def decode_action(action_idx: int, current_pokemon_idx: int) -> Tuple[str, int]:
    """Decode action index back to tuple"""
    if action_idx < 4:
        return ('move', action_idx)
    else:
        # Adjust for current pokemon
        switch_idx = action_idx - 4
        if switch_idx >= current_pokemon_idx:
            switch_idx += 1  # Skip current pokemon
        return ('switch', switch_idx)


def create_action_mask(valid_actions: List[Tuple[str, int]], action_size: int = 9) -> np.ndarray:
    """Create binary mask for valid actions"""
    mask = np.zeros(action_size, dtype=bool)
    for action in valid_actions:
        idx = encode_action(action)
        mask[idx] = True
    return mask


def encode_action_probs(action_probs: Dict[Tuple[str, int], float], action_size: int = 9) -> np.ndarray:
    """Convert MCTS action probabilities to fixed-size array"""
    encoded = np.zeros(action_size)
    for action, prob in action_probs.items():
        idx = encode_action(action)
        encoded[idx] = prob
    return encoded


class NuzlockeLoss(nn.Module):
    """
    Custom loss that heavily penalizes pokemon deaths in nuzlocke
    """

    def __init__(
            self,
            value_weight: float = 1.0,
            policy_weight: float = 1.0,
            death_penalty: float = 2.0
    ):  # Extra penalty for losses with deaths
        super().__init__()
        self.value_weight = value_weight
        self.policy_weight = policy_weight
        self.death_penalty = death_penalty

    def forward(
            self,
            policy_logits: torch.Tensor,
            value_pred: torch.Tensor,
            policy_target: torch.Tensor,
            value_target: torch.Tensor,
            pokemon_deaths: torch.Tensor = None
    ):
        """
        Calculate combined loss
        Args:
            policy_logits: Predicted policy logits [batch_size, action_size]
            value_pred: Predicted values [batch_size, 1]
            policy_target: Target action probabilities from MCTS [batch_size, action_size]
            value_target: Target values (game outcome) [batch_size, 1]
            pokemon_deaths: Number of pokemon lost [batch_size, 1]
        """
        # Policy loss (cross-entropy between MCTS distribution and network output)
        # Use KL divergence for probability distributions
        policy_probs = F.log_softmax(policy_logits, dim=1)
        policy_loss = -torch.sum(policy_target * policy_probs, dim=1).mean()

        # Value loss with death penalty
        value_loss = F.mse_loss(value_pred, value_target, reduction='none')

        # Apply extra penalty for games with pokemon deaths
        if pokemon_deaths is not None:
            # Scale loss by (1 + death_penalty * death_rate)
            death_multiplier = 1.0 + self.death_penalty * pokemon_deaths
            value_loss = value_loss * death_multiplier

        value_loss = value_loss.mean()

        # Combined loss
        total_loss = self.policy_weight * policy_loss + self.value_weight * value_loss

        return total_loss, policy_loss, value_loss


class BattleDataset(Dataset):
    """Dataset for loading training positions"""

    def __init__(self, data_dir: str, generation: int = None):
        self.data_dir = Path(data_dir)
        self.positions = []
        self.load_data(generation)

    def load_data(self, generation: int = None):
        """Load positions from HDF5 files"""
        pattern = f"gen{generation:03d}_*.h5" if generation is not None else "*.h5"

        for file_path in self.data_dir.glob(pattern):
            with h5py.File(file_path, 'r') as f:
                for game_key in f.keys():  # pylint:disable=C0206
                    if not game_key.startswith('game_'):
                        continue

                    game = f[game_key]
                    states = game['states'][:]
                    mcts_values = game['mcts_values'][:]
                    outcomes = game['outcomes'][:]
                    turns = game['turns'][:]

                    # Load pickled action probabilities
                    action_probs_data = game['action_probs'][()]
                    action_probs_list = pickle.loads(action_probs_data.tobytes())

                    for i in range(len(states)):  #pylint:disable=C0200
                        self.positions.append({
                            'state': states[i],
                            'mcts_value': mcts_values[i],
                            'outcome': outcomes[i],
                            'turn': turns[i],
                            'action_probs': action_probs_list[i]
                        })

    def __len__(self):
        return len(self.positions)

    def __getitem__(self, idx):
        position = self.positions[idx]

        # Convert to tensors
        state = torch.FloatTensor(position['state'])

        # Encode action probabilities to fixed-size array
        action_probs = encode_action_probs(position['action_probs'])
        action_probs = torch.FloatTensor(action_probs)

        # Value target (game outcome)
        value = torch.FloatTensor([position['outcome']])

        # MCTS value for comparison
        mcts_value = torch.FloatTensor([position['mcts_value']])

        return state, action_probs, value, mcts_value


class Trainer:
    """Handles training of the neural network"""

    def __init__(
            self,
            network: PokemonBattleNet,
            learning_rate: float = 1e-3,
            weight_decay: float = 1e-4,
            device: str = None
    ):
        self.network = network
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.network.to(self.device)

        self.optimizer = optim.Adam(
            self.network.parameters(),
            lr=learning_rate,
            weight_decay=weight_decay
        )

        self.loss_fn = NuzlockeLoss()
        self.scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode='min', factor=0.5, patience=3
        )

        self.training_history = {
            'total_loss': [],
            'policy_loss': [],
            'value_loss': []
        }

    def train_epoch(self, dataloader: DataLoader):
        """Train for one epoch"""
        self.network.train()

        epoch_losses = {'total': 0, 'policy': 0, 'value': 0}
        num_batches = 0

        for batch in dataloader:
            states, action_probs, values, mcts_values = batch
            states = states.to(self.device)
            action_probs = action_probs.to(self.device)
            values = values.to(self.device)

            # Forward pass
            policy_logits, value_pred = self.network(states)

            # Calculate loss
            total_loss, policy_loss, value_loss = self.loss_fn(
                policy_logits, value_pred, action_probs, values
            )

            # Backward pass
            self.optimizer.zero_grad()
            total_loss.backward()
            torch.nn.utils.clip_grad_norm_(self.network.parameters(), 1.0)  # Gradient clipping
            self.optimizer.step()

            # Track losses
            epoch_losses['total'] += total_loss.item()
            epoch_losses['policy'] += policy_loss.item()
            epoch_losses['value'] += value_loss.item()
            num_batches += 1

        # Average losses
        for key in epoch_losses:
            epoch_losses[key] /= num_batches

        return epoch_losses

    def train(self,
              data_dir: str,
              epochs: int = 10,
              batch_size: int = 256,
              validation_split: float = 0.1):
        """Full training loop"""

        # Load dataset
        dataset = BattleDataset(data_dir)

        # Split into train and validation
        val_size = int(len(dataset) * validation_split)
        train_size = len(dataset) - val_size
        train_dataset, val_dataset = torch.utils.data.random_split(
            dataset, [train_size, val_size]
        )

        train_loader = DataLoader(
            train_dataset, batch_size=batch_size, shuffle=True, num_workers=4
        )
        val_loader = DataLoader(
            val_dataset, batch_size=batch_size, shuffle=False, num_workers=4
        )

        best_val_loss = float('inf')

        for epoch in range(epochs):
            # Training
            train_losses = self.train_epoch(train_loader)

            # Validation
            val_losses = self.validate(val_loader)

            # Update learning rate
            self.scheduler.step(val_losses['total'])

            # Save best model
            if val_losses['total'] < best_val_loss:
                best_val_loss = val_losses['total']
                self.save_checkpoint(f'best_model_epoch_{epoch}.pth')

            print(f"Epoch {epoch+1}/{epochs}")
            print(f"  Train - Total: {train_losses['total']:.4f}, "
                  f"Policy: {train_losses['policy']:.4f}, Value: {train_losses['value']:.4f}")
            print(f"  Val   - Total: {val_losses['total']:.4f}, "
                  f"Policy: {val_losses['policy']:.4f}, Value: {val_losses['value']:.4f}")

            # Track history
            self.training_history['total_loss'].append(train_losses['total'])
            self.training_history['policy_loss'].append(train_losses['policy'])
            self.training_history['value_loss'].append(train_losses['value'])

    def validate(self, dataloader: DataLoader):
        """Validate the network"""
        self.network.eval()

        epoch_losses = {'total': 0, 'policy': 0, 'value': 0}
        num_batches = 0

        with torch.no_grad():
            for batch in dataloader:
                states, action_probs, values, mcts_values = batch
                states = states.to(self.device)
                action_probs = action_probs.to(self.device)
                values = values.to(self.device)

                # Forward pass
                policy_logits, value_pred = self.network(states)

                # Calculate loss
                total_loss, policy_loss, value_loss = self.loss_fn(
                    policy_logits, value_pred, action_probs, values
                )

                # Track losses
                epoch_losses['total'] += total_loss.item()
                epoch_losses['policy'] += policy_loss.item()
                epoch_losses['value'] += value_loss.item()
                num_batches += 1

        # Average losses
        for key in epoch_losses:
            epoch_losses[key] /= num_batches

        return epoch_losses

    def save_checkpoint(self, path: str):
        """Save model checkpoint"""
        torch.save({
            'model_state_dict': self.network.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'training_history': self.training_history
        }, path)

    def load_checkpoint(self, path: str):
        """Load model checkpoint"""
        checkpoint = torch.load(path, map_location=self.device)
        self.network.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self.training_history = checkpoint.get('training_history', {})


# Integration with MCTS
def run_mcts_with_nn(state, network: PokemonBattleNet, iterations: int = 100):
    """
    Modified MCTS that uses neural network for evaluation and priors
    """

    root = Node(state)

    # Get NN evaluation for root
    state_array = state.battle_array
    valid_actions_mask = create_action_mask(state.get_valid_actions())
    policy_probs, value_estimate = network.predict(state_array, valid_actions_mask)

    # Use NN policy as priors for root children
    for action in state.get_valid_actions():
        action_idx = encode_action(action)
        if action not in root.children:
            root.children[action] = []
        # Set prior probability from NN
        # (You'll need to modify Node class to store priors)

    # Run MCTS with NN-guided simulations
    for _ in range(iterations):
        # Your MCTS implementation, but use NN value for leaf evaluation
        # instead of rollouts when confidence is high
        pass

    return root


# Example usage
def integrated_self_play_with_nn(initial_battle_array):
    """Run self-play using trained neural network"""

    # Initialize network
    state_size = 12 * POK_LEN + FIELD_LEN  # Your battle array size
    network = PokemonBattleNet(state_size=state_size)

    # Load trained weights if available
    if Path('best_model.pth').exists():
        checkpoint = torch.load('best_model.pth')
        network.load_state_dict(checkpoint['model_state_dict'])

    # Run game with NN-enhanced MCTS

    initial_state = GameState(initial_battle_array)  # Your initialization

    state = initial_state
    while not state.is_terminal():
        # Use NN with MCTS
        root = run_mcts_with_nn(state, network, iterations=100)

        # Select action based on visits
        best_action = max(root.children.items(),
                         key=lambda x: sum(n.visits for n in x[1]))
        state = state.step(best_action[0])

    return state
