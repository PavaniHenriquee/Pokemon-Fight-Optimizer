"""Main"""
from Models.pokemon import Pokemon
# from Engine.new_battle import battle


charmander = Pokemon("Charmander", "Male", 5, "Blaze", "Hardy", ["Scratch"])
# squirtle = Pokemon("Squirtle", "Male", 5, "Torrent", "Hardy", ["Tackle", "Tail Whip"])
# squirtle1 = Pokemon("Squirtle", "Male", 5, "Torrent", "Hardy", ["Tackle", "Tail Whip"])
# charmander1 = Pokemon("Charmander", "Male", 5, "Blaze", "Hardy", ["Scratch", "Growl"])

# my_party = [charmander, squirtle1]
# opp_party = [squirtle, charmander1]

print(charmander.to_np())
print(charmander.to_np().dtype)
print(len(charmander.to_np()))
