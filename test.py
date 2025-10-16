"""test"""
import numpy as np
from Models.pokemon import Pokemon
from Models.trainer_ai import add_adjustment
# from Engine.new_battle import battle
from Utils.helper import pick_probabilities


charmander = Pokemon("Charmander", "Male", 5, "Blaze", "Hardy", ["Scratch", "Growl", "Ember"])
squirtle = Pokemon("Squirtle", "Male", 5, "Torrent", "Hardy", ["Tackle", "Tail Whip"])
squirtle1 = Pokemon("Squirtle", "Male", 5, "Torrent", "Hardy", ["Tackle", "Tail Whip"])
charmander1 = Pokemon("Charmander", "Male", 5, "Blaze", "Hardy", ["Scratch", "Growl"])

my_party = [charmander, squirtle]
opp_party = [squirtle1, charmander1]

# battle(my_party, opp_party)
data = np.zeros(4, dtype=np.float64)
data[0] = 30
data[1] = 28
rand = np.full((4, 5, 2), np.nan)
add_adjustment(rand,0,1,64)
add_adjustment(rand,0,1,128)
add_adjustment(rand,1,2,100)

prob = pick_probabilities(data, rand)
print(prob)
