"""test"""
import numpy as np
from Models.pokemon import Pokemon
from Utils.helper import to_battle_array
from NeuralNetwork.models import to_nn_input, NN_INPUT_SIZE


charmander = Pokemon("Charmander", "Male", 5, "Blaze", "Hardy", ["Scratch", "Growl", "Ember"])
squirtle = Pokemon("Squirtle", "Male", 5, "Torrent", "Hardy", ["Tackle", "Tail Whip"])
bulbasaur = Pokemon("Bulbasaur", "Male", 5, "Overgrow", "Hardy", ["Pound", "Leer", "Razor Leaf"])
squirtle1 = Pokemon("Squirtle", "Male", 5, "Torrent", "Hardy", ["Tackle", "Tail Whip"])
charmander1 = Pokemon("Charmander", "Male", 5, "Blaze", "Hardy", ["Scratch", "Growl"])

my_party = [charmander]
opp_party = [squirtle1]

array = to_battle_array(my_party, opp_party)

features = to_nn_input(array)
print(features.shape)    # should be (636,)
print(features.dtype)    # should be float32
print(features.min(), features.max())  # should be roughly -1.0 to 1.0
assert not np.any(np.isnan(features)), "NaN found"
assert not np.any(np.isinf(features)), "Inf found"
print(f"NN_INPUT_SIZE = {NN_INPUT_SIZE}")
