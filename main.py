from Models.pokemon import Pokemon
from Engine.Battle import battle


charmander = Pokemon("Charmander",5,"Blaze","Hardy",["Scratch", "Growl"])
squirtle = Pokemon("Squirtle",5,"Torrent","Hardy",["Tackle", "Tail Whip"])
squirtle1 = Pokemon("Squirtle",5,"Torrent","Hardy",["Tackle", "Tail Whip"])
charmander1 = Pokemon("Charmander",5,"Blaze","Hardy",["Scratch", "Growl"])

my_party = [charmander, squirtle1]
opp_party = [squirtle, charmander1]



battle(my_party, opp_party)