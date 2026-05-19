"""Main"""
import random
import numpy as np


def build_battle():
    """Build battle"""
    from Models.pokemon import Pokemon
    from Utils.helper import to_battle_array
    charmander = Pokemon("Charmander", "Male", 5, "Blaze", "Hardy", ["Scratch", "Growl", "Ember"])
    squirtle = Pokemon("Squirtle", "Male", 5, "Torrent", "Hardy", ["Tackle", "Tail Whip", "Bubble"])
    bulbasaur =Pokemon("Bulbasaur", "Male", 5, "Overgrow", "Hardy", ["Pound", "Leer", "Razor Leaf"])
    squirtle1 = Pokemon("Squirtle", "Male", 5, "Torrent", "Hardy", ["Tackle", "Tail Whip"])
    charmander1 = Pokemon("Charmander", "Male", 5, "Blaze", "Hardy", ["Scratch", "Growl"])

    my_party = [charmander, bulbasaur, squirtle, squirtle, squirtle, squirtle]
    opp_party = [squirtle1, charmander1, charmander1, charmander1, charmander1, charmander1]

    return to_battle_array(my_party, opp_party)


def run_single(battle1):
    """Run slower but can profile"""
    import os
    os.environ['NUMBA_DISABLE_JIT'] = '1'
    from cProfile import Profile
    from pstats import Stats, SortKey
    from SearchEngine.my_mcts import mcts, GameState
    root = GameState(battle1)
    with Profile() as profile:
        mcts(root, max_iterations=10000)
        Stats(profile).strip_dirs().sort_stats(SortKey.TIME).print_stats()


def run_parallel(battle1):
    """Run Faster but can't debug or profile"""
    import time
    from SearchEngine.mcts_async import mcts_async, GameState
    root = GameState(battle1)
    s_time = time.perf_counter()
    mcts_async(root)
    e_time = time.perf_counter()
    print(f"\nTime to finish search: {e_time - s_time:.2f} seconds")


def run_jit(battle1):
    """Run Faster but can't debug or profile"""
    #import os
    #os.environ['NUMBA_DISABLE_JIT'] = '1'
    from SearchEngine.my_mcts import mcts, GameState
    import time
    root = GameState(battle1)
    s_time = time.perf_counter()
    mcts(root, max_iterations=10000)
    e_time = time.perf_counter()
    print(f"\nTime to finish search: {e_time - s_time:.2f} seconds")



if __name__ =='__main__':
    SEED = 37
    random.seed(SEED)
    np.random.seed(SEED)

    battle = build_battle()
    # run_single(battle)
    # run_parallel(battle)
    run_jit(battle)
