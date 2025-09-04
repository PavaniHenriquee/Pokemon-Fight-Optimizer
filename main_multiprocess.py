"""my_mcts_runner.py"""
import copy
import random
import os
from concurrent.futures import ProcessPoolExecutor
from SearchEngine.mcts import GameState, mcts_decide


def play_match(my_partyy, opp_partyy, iters_per_turn=800, max_turns=200):
    """Play"""
    state = GameState(my_partyy, opp_partyy)
    while not state.is_terminal() and state.turn < max_turns:
        best_move, _ = mcts_decide(state, iterations=iters_per_turn)
        if best_move is None:
            break  # no legal moves (Defensive)
        state = state.step(best_move)
    return state.evaluate()  # +1 win, -1 loss, 0 draw


def _worker_play_one(args):
    """Play one"""
    template_my_partyy, template_opp_partyy, iters_per_turn, seed = args
    random.seed(seed)
    my_partyy = copy.deepcopy(template_my_partyy)
    opp_partyy = copy.deepcopy(template_opp_partyy)
    result = play_match(my_partyy, opp_partyy, iters_per_turn=iters_per_turn)
    return 1 if result > 0 else 0


def winrate_vs_ai_parallel(template_my_party, template_opp_party, games=50, iters=600, max_workers=None):
    """Winrate"""
    max_workers = max_workers or (os.cpu_count() or 2)
    rng = random.Random(12345)
    seeds = [rng.randrange(2**30) for _ in range(games)]
    args_iter = [(template_my_party, template_opp_party, iters, s) for s in seeds]

    wins = 0
    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        for win in ex.map(_worker_play_one, args_iter):
            wins += win

    return wins / games


# ----- only run work when executed as script -----
if __name__ == '__main__':
    """main"""
    from Models.pokemon import Pokemon
    charmander = Pokemon("Charmander", "Male", 5, "Blaze", "Hardy", ["Scratch", "Growl", "Ember"])
    squirtle = Pokemon("Squirtle", "Male", 5, "Torrent", "Hardy", ["Tackle", "Tail Whip"])
    squirtle1 = Pokemon("Squirtle", "Male", 5, "Torrent", "Hardy", ["Tackle", "Tail Whip"])
    charmander1 = Pokemon("Charmander", "Male", 5, "Blaze", "Hardy", ["Scratch", "Growl"])

    my_party = [charmander, squirtle1]
    opp_party = [squirtle, charmander1]

    # determine best first move via MCTS (same iterations as used in games)
    random.seed(0)  # make initial decision reproducible
    init_state = GameState(my_party, opp_party)
    best_move_idx, _ = mcts_decide(init_state, iterations=800)
    if best_move_idx is None:
        best_move_name = "No move"
    else:
        mv = my_party[init_state.cur_my_idx].moves[best_move_idx]
        best_move_name = mv['name'] if isinstance(mv, dict) else getattr(mv, 'name', str(best_move_idx))

    winrate = winrate_vs_ai_parallel(my_party, opp_party, games=10, iters=100)
    print(f"Best first move: {best_move_name}  |  Winrate vs built-in AI: {winrate*100:.2f}%")
