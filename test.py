"""test"""
import time
#import os
#os.environ['NUMBA_DISABLE_JIT'] = '1'
from Models.pokemon import Pokemon
from Models.constants import _FIELD_TURN
from SearchEngine.my_mcts import mcts, GameState
from Engine.engine_helper import start_of_battle
from Utils.helper import to_battle_array


pok1 = Pokemon("Rapidash", "Male", 70, "Blaze", "Hardy", ["Counter"], item="Oran Berry")
pok2 = Pokemon("Scizor", "Male", 70, "Torrent", "Hardy", ["Tackle"])

my_party = [pok2]
opp_party = [pok1]


s_time = time.perf_counter()
array = to_battle_array(my_party, opp_party)
if array[_FIELD_TURN] == 0:
    start_of_battle(array)
root = GameState(array)
mcts(root, max_iterations=10000)
e_time = time.perf_counter()
print(f"\nTime to finish search: {e_time - s_time:.2f} seconds")
