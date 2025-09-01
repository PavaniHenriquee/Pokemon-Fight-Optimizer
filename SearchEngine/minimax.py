from SearchEngine.evaluate import evaluate_state

def search_best_move(state, depth):
    if depth == 0 or state.is_terminal():
        return evaluate_state(state), None

    best_score = float("-inf")
    best_move = None

    for move in state.available_moves(player="me"):
        # simulate my move and opponent's response
        new_state = state.clone()
        new_state.apply_move("me", move)
        
        # Opponent plays optimally/randomly (depends on your AI)
        for opp_move in new_state.available_moves(player="opp"):
            opp_state = new_state.clone()
            opp_state.apply_move("opp", opp_move)
            
            score, _ = search_best_move(opp_state, depth - 1)
            score = -score  # because next turn is opponent’s advantage

            if score > best_score:
                best_score = score
                best_move = move

    return best_score, best_move
