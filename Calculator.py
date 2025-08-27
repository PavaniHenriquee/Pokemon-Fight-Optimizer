import json
#import numpy

round = 1
pokemon = {my:{}, opp:{}}
currentHP = {my:0, opp:0}
with open("PkDB.json","r") as f:
    pkBD = json.load(f)
print(pkDB["Bulbasaur"]["type"])

def battleStart():
    myPokemon = {}
    oppPokemon = {}
    currentHP = myPokemon[HP]
    currentOppHp = oppPokemon[HP]

