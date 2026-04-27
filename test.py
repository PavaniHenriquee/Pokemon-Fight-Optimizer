"""test"""
from Models.pokemon import Pokemon
from Models.idx_const import POK_LEN, Pok, MOVE_STRIDE
from Utils.helper import to_battle_array
from Engine.damage_calc import calculate_damage


charmander = Pokemon("Charmander", "Male", 5, "Blaze", "Hardy", ["Scratch", "Growl", "Ember"])
squirtle = Pokemon("Squirtle", "Male", 5, "Torrent", "Hardy", ["Tackle", "Tail Whip"])
bulbasaur = Pokemon("Bulbasaur", "Male", 5, "Overgrow", "Hardy", ["Pound", "Leer", "Razor Leaf"])
squirtle1 = Pokemon("Squirtle", "Male", 5, "Torrent", "Hardy", ["Tackle", "Tail Whip"])
charmander1 = Pokemon("Charmander", "Male", 5, "Blaze", "Hardy", ["Scratch", "Growl"])

my_party = [bulbasaur]
opp_party = [squirtle1]

array = to_battle_array(my_party, opp_party)
pok = array[0:POK_LEN]
opp = array[POK_LEN*6:POK_LEN*7]
opp[Pok.DEFENSE_STAT_STAGE] = -1
move = pok[Pok.MOVE3_ID:(Pok.MOVE3_ID + MOVE_STRIDE)]
print(calculate_damage(pok,opp,move,roll_multiplier=0.85))
print(calculate_damage(pok,opp,move,roll_multiplier=0.86))
print(calculate_damage(pok,opp,move,roll_multiplier=0.87))
print(calculate_damage(pok,opp,move,roll_multiplier=0.88))
print(calculate_damage(pok,opp,move,roll_multiplier=0.89))
print(calculate_damage(pok,opp,move,roll_multiplier=0.90))
print(calculate_damage(pok,opp,move,roll_multiplier=0.91))
print(calculate_damage(pok,opp,move,roll_multiplier=0.92))
print(calculate_damage(pok,opp,move,roll_multiplier=0.93))
print(calculate_damage(pok,opp,move,roll_multiplier=0.94))
print(calculate_damage(pok,opp,move,roll_multiplier=0.95))
print(calculate_damage(pok,opp,move,roll_multiplier=0.96))
print(calculate_damage(pok,opp,move,roll_multiplier=0.97))
print(calculate_damage(pok,opp,move,roll_multiplier=0.98))
print(calculate_damage(pok,opp,move,roll_multiplier=0.99))
print(calculate_damage(pok,opp,move,roll_multiplier=1))
print(pok[Pok.ATTACK])
print(opp[Pok.DEFENSE])
