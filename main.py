"""Main"""
import random
import numpy as np
# Profile command
# py-spy record -s -f speedscope -o flamegraph.speedscope.json -- python main.py


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


def run_single():
    """Run slower but can profile"""
    import os
    os.environ['NUMBA_DISABLE_JIT'] = '1'
    from cProfile import Profile
    from pstats import Stats, SortKey
    from SearchEngine.my_mcts import mcts, GameState
    battle = build_battle()
    root = GameState(battle)
    with Profile() as profile:
        mcts(root, max_iterations=10000)
        Stats(profile).strip_dirs().sort_stats(SortKey.TIME).print_stats()


def run_parallel():
    """Run Faster but can't debug or profile"""
    #import os
    #os.environ['NUMBA_DISABLE_JIT'] = '1'
    import time
    from SearchEngine.mcts_async import mcts_async, GameState
    battle = build_battle()
    root = GameState(battle)
    s_time = time.perf_counter()
    mcts_async(root)
    e_time = time.perf_counter()
    print(f"\nTime to finish search: {e_time - s_time:.2f} seconds")


def run_jit():
    """Run Faster but can't debug or profile"""
    from SearchEngine.my_mcts import mcts, GameState
    import time
    battle = build_battle()
    root = GameState(battle)
    s_time = time.perf_counter()
    mcts(root, max_iterations=10000)
    e_time = time.perf_counter()
    print(f"\nTime to finish search: {e_time - s_time:.2f} seconds")

def run_jit_base_time():
    """Compare to see real performance changes that numba is doing"""
    import os
    os.environ['NUMBA_DISABLE_JIT'] = '1'
    from SearchEngine.my_mcts import mcts, GameState
    import time
    battle = build_battle()
    root = GameState(battle)
    s_time = time.perf_counter()
    mcts(root, max_iterations=10000)
    e_time = time.perf_counter()
    print(f"\nTime to finish search: {e_time - s_time:.2f} seconds")



if __name__ =='__main__':
    SEED = 37
    random.seed(SEED)
    np.random.seed(SEED)

    run_single()
    #run_parallel()
    #run_jit()
    #run_jit_base_time()
