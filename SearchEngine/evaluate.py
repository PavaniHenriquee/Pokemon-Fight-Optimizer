def evaluate_state(state):
    # state has both teams’ HP, statuses, etc.
    my_hp = sum(p.hp for p in state.my_party)
    opp_hp = sum(p.hp for p in state.opp_party)
    
    # simple version: difference in total HP
    return my_hp - opp_hp