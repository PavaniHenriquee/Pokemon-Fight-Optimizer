import json
#import numpy

round = 1
myPartyPk = ['Charmander']
oppPartyPk = ['Squirtle']
with open("Database\PkDB.json","r") as f:
    pkDB = json.load(f)
with open("Database\AbilitiesDB.json","r") as f:
    abDB = json.load(f)
with open("Database\ItemDB.json","r") as f:
    itemDB = json.load(f)
with open("Database\MoveDB.json","r") as f:
    moveDB = json.load(f)
myParty = {pkDB[myPartyPk[0]]:{
            'ability': abDB['Blaze'],
            'move1': moveDB['Tackle'],
            'move2': moveDB['Growl']}
            }
oppParty = {pkDB[oppPartyPk[0]]:{
            'ability': abDB['Blaze'],
            'move1': moveDB['Tackle'],
            'move2': moveDB['Growl']}
            }
def battleStart():
    myPokemon = {}
    oppPokemon = {}

