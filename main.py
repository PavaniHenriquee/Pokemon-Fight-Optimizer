"""Main"""
import random
import numpy as np
from Models.pokemon import Pokemon
from SearchEngine.my_mcts import GameState, mcts
from Utils.helper import to_battle_array


def build_battle():
    """Build battle"""
    charmander = Pokemon("Charmander", "Male", 5, "Blaze", "Hardy", ["Scratch", "Growl", "Ember"])
    squirtle = Pokemon("Squirtle", "Male", 5, "Torrent", "Hardy", ["Tackle", "Tail Whip", "Bubble"])
    bulbasaur = Pokemon("Bulbasaur", "Male", 5, "Overgrow", "Hardy", ["Pound", "Leer", "Razor Leaf"])
    squirtle1 = Pokemon("Squirtle", "Male", 5, "Torrent", "Hardy", ["Tackle", "Tail Whip"])
    charmander1 = Pokemon("Charmander", "Male", 5, "Blaze", "Hardy", ["Scratch", "Growl"])

    my_party = [charmander, bulbasaur, squirtle, squirtle, squirtle, squirtle]
    opp_party = [squirtle1, charmander1, charmander1, charmander1, charmander1, charmander1]

    return to_battle_array(my_party, opp_party)


def run_single(root):
    """Run slower but can profile"""
    from cProfile import Profile
    from pstats import Stats, SortKey
    with Profile() as profile:
        mcts(root, max_iterations=5000)
        Stats(profile).strip_dirs().sort_stats(SortKey.TIME).print_stats()


def run_parallel(root):
    """Run Faster but can't debug or profile"""
    import time
    # from SearchEngine.mcts_multi import parallel_mcts
    from SearchEngine.mcts_async import mcts_async
    s_time = time.perf_counter()
    # parallel_mcts(root)
    mcts_async(root)
    e_time = time.perf_counter()
    print(f"\nTime to finish search: {e_time - s_time:.2f} seconds")



if __name__ =='__main__':
    SEED = 37
    random.seed(SEED)
    np.random.seed(SEED)

    battle = build_battle()
    root_state = GameState(battle)
    run_single(root_state)
    # run_parallel(root_state)
