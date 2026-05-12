"""test"""
from Models.pokemon import Pokemon
from Models.idx_const import POK_LEN, Pok, MOVE_STRIDE
from Engine.damage_calc import calculate_damage
from Utils.helper import to_battle_array


charmander = Pokemon("Charmander", "Male", 5, "Blaze", "Hardy", ["Scratch", "Growl", "Ember"])
squirtle = Pokemon("Squirtle", "Male", 5, "Torrent", "Hardy", ["Tackle", "Tail Whip"])
bulbasaur = Pokemon("Bulbasaur", "Male", 5, "Overgrow", "Hardy", ["Pound", "Leer", "Razor Leaf"])
squirtle1 = Pokemon("Squirtle", "Male", 5, "Torrent", "Hardy", ["Tackle", "Tail Whip"])
charmander1 = Pokemon("Charmander", "Male", 5, "Blaze", "Hardy", ["Scratch", "Growl"])

my_party = [charmander]
opp_party = [squirtle1]

array = to_battle_array(my_party, opp_party)
pok = array[0:POK_LEN]
opp = array[POK_LEN*6:POK_LEN*7]
opp[Pok.SPECIAL_DEFENSE_STAT_STAGE] = -1
pok[Pok.ATTACK_STAT_STAGE] = -3
move = pok[Pok.MOVE1_ID:(Pok.MOVE1_ID + MOVE_STRIDE)]
print(calculate_damage(pok,opp,move,weather=1,roll_multiplier=85))
print(calculate_damage(pok,opp,move,weather=1,roll_multiplier=86))
print(calculate_damage(pok,opp,move,weather=1,roll_multiplier=87))
print(calculate_damage(pok,opp,move,weather=1,roll_multiplier=88))
print(calculate_damage(pok,opp,move,weather=1,roll_multiplier=89))
print(calculate_damage(pok,opp,move,weather=1,roll_multiplier=90))
print(calculate_damage(pok,opp,move,weather=1,roll_multiplier=91))
print(calculate_damage(pok,opp,move,weather=1,roll_multiplier=92))
print(calculate_damage(pok,opp,move,weather=1,roll_multiplier=93))
print(calculate_damage(pok,opp,move,weather=1,roll_multiplier=94))
print(calculate_damage(pok,opp,move,weather=1,roll_multiplier=95))
print(calculate_damage(pok,opp,move,weather=1,roll_multiplier=96))
print(calculate_damage(pok,opp,move,weather=1,roll_multiplier=97))
print(calculate_damage(pok,opp,move,weather=1,roll_multiplier=98))
print(calculate_damage(pok,opp,move,weather=1,roll_multiplier=99))
print(calculate_damage(pok,opp,move,weather=1,roll_multiplier=100))
