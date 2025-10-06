"""Main"""
from cProfile import Profile
from pstats import Stats, SortKey
from Models.pokemon import Pokemon
from SearchEngine.my_mcts import GameState, mcts
from Engine.engine_helper import to_battle_array


charmander = Pokemon("Charmander", "Male", 5, "Blaze", "Hardy", ["Scratch", "Growl", "Ember"])
squirtle = Pokemon("Squirtle", "Male", 5, "Torrent", "Hardy", ["Tackle", "Tail Whip"])
squirtle1 = Pokemon("Squirtle", "Male", 5, "Torrent", "Hardy", ["Tackle", "Tail Whip"])
charmander1 = Pokemon("Charmander", "Male", 5, "Blaze", "Hardy", ["Scratch", "Growl"])

my_party = [charmander, squirtle]
opp_party = [squirtle1, charmander1]

battle = to_battle_array(my_party, opp_party)
root = GameState(battle)


with Profile() as profile:
    mcts(root, 1000)
    (
        Stats(profile)
        .strip_dirs()
        .sort_stats(SortKey.TIME)
        .print_stats()
    )
