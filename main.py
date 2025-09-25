"""Main"""
import numpy as np
from Models.pokemon import Pokemon
from Models.idx_nparray import PokArray, MoveFlags, MoveArray, SecondaryArray
from Engine.damage_calc import calculate_damage
from DataBase.MoveDB import MoveName
# from Engine.new_battle import battle


charmander = Pokemon("Charmander", "Male", 5, "Blaze", "Hardy", ["Scratch", "Growl", "Ember"])
squirtle = Pokemon("Squirtle", "Male", 5, "Torrent", "Hardy", ["Tackle", "Tail Whip"])
squirtle1 = Pokemon("Squirtle", "Male", 5, "Torrent", "Hardy", ["Tackle", "Tail Whip"])
charmander1 = Pokemon("Charmander", "Male", 5, "Blaze", "Hardy", ["Scratch", "Growl"])

my_party = np.concatenate([charmander.to_np(), squirtle.to_np()])
opp_party = np.concatenate([squirtle1.to_np(), charmander1.to_np()])
battle_array = np.concatenate([my_party, opp_party])

pokarray_len = len(PokArray)
char_array = battle_array[0:pokarray_len]
squi = battle_array[pokarray_len:(2 * pokarray_len)]
squi1 = battle_array[(2 * pokarray_len):(3 * pokarray_len)]
char1 = battle_array[(3 * pokarray_len):(4 * pokarray_len)]
move1 = char_array[PokArray.MOVE1_ID:PokArray.MOVE2_ID]
move2 = char_array[PokArray.MOVE2_ID:PokArray.MOVE3_ID]
move3 = char_array[PokArray.MOVE3_ID:PokArray.MOVE4_ID]
m = move3[len(MoveArray) + len(MoveFlags) + SecondaryArray.CHANCE]
print(battle_array)
print(battle_array.dtype)
print(len(battle_array))
damage, eff = calculate_damage(char_array, squi, move3, roll_multiplier=1)
print(MoveName(move3[MoveArray.ID]).name)
print(damage)
print(eff)
print(m)
print(move2[MoveArray.BOOST_ATK])
print(any(move2[MoveArray.BOOST_ATK: MoveArray.BOOST_EV + 1]))
