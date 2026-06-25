"""test"""
import time
from Models.pokemon import Pokemon
#from Models.idx_const import Field, POK_LEN, Pok
from Models.constants import _ACTIONTYPE_MOVE
from Utils.helper import to_battle_array
from Engine.battle import turn_sim


charmander = Pokemon("Charmander", "Male", 35, "Blaze", "Hardy", ["Astonish", "Growl", "Ember"])
squirtle = Pokemon("Squirtle", "Male", 5, "Torrent", "Hardy", ["Tackle", "Tail Whip"])
bulbasaur = Pokemon("Bulbasaur", "Male", 5, "Overgrow", "Hardy", ["Pound", "Leer", "Razor Leaf"])
squirtle1 = Pokemon("Squirtle", "Male", 25, "Torrent", "Hardy", ["Tackle", "Tail Whip"])
charmander1 = Pokemon("Charmander", "Male", 5, "Blaze", "Hardy", ["Scratch", "Growl"])

my_party = [charmander]
opp_party = [squirtle1]


s_time = time.perf_counter()
for _ in range(20):
    array = to_battle_array(my_party, opp_party)
    _ = turn_sim(0,(_ACTIONTYPE_MOVE,0),array)
    #my_active=array[Field.MY_POK]
    #opp_active = array[Field.OPP_POK]
    #cur = array[(my_active * POK_LEN):((my_active+1) * POK_LEN)]
    #opp = array[((opp_active+6) * POK_LEN):((opp_active+7) * POK_LEN)]
    #dmg = opp[Pok.MAX_HP] - opp[Pok.CURRENT_HP]
    #print(dmg)
e_time = time.perf_counter()
print(f"\nTime to finish search: {e_time - s_time:.2f} seconds")
