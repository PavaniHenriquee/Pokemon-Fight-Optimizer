"""test"""
import time
from Models.pokemon import Pokemon
from Utils.helper import to_battle_array
from NeuralNetwork.models import to_nn_input


charmander = Pokemon("Charmander", "Male", 5, "Blaze", "Hardy", ["Scratch", "Growl", "Ember"])
squirtle = Pokemon("Squirtle", "Male", 5, "Torrent", "Hardy", ["Tackle", "Tail Whip"])
bulbasaur = Pokemon("Bulbasaur", "Male", 5, "Overgrow", "Hardy", ["Pound", "Leer", "Razor Leaf"])
squirtle1 = Pokemon("Squirtle", "Male", 5, "Torrent", "Hardy", ["Tackle", "Tail Whip"])
charmander1 = Pokemon("Charmander", "Male", 5, "Blaze", "Hardy", ["Scratch", "Growl"])

my_party = [charmander, charmander, squirtle, squirtle, bulbasaur, bulbasaur]
opp_party = [squirtle1, squirtle1, squirtle1, charmander1, charmander1, charmander1]

s_time = time.perf_counter()
array = to_battle_array(my_party, opp_party)
for _ in range(500_000):
    features = to_nn_input(array)
e_time = time.perf_counter()
print(f"\nTime to finish search: {e_time - s_time:.2f} seconds")
cont = features['continuous']
abi  = features['ability_ids']
