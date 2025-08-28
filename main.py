from Models.pokemon import Pokemon
from Engine.Battle import battle


charmander = Pokemon("Charmander",5,"Blaze","Hardy",["Scratch", "Growl"])
squirtle = Pokemon("Squirtle",5,"Torrent","Hardy",["Tackle", "Tail Whip"])

my_party = [charmander]
opp_party = [squirtle]



battle(my_party, opp_party)