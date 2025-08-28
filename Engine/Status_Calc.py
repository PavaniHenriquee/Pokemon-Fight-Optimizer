

def calculate_status(attacker, defender, move):
    if move['category'] != "Status":
       return None
    
    for eff in move['effects']:
        if eff['effect_type'] == 'stat_change':
            if (eff['target'] == 'self' or eff['target'] == 'ally_side'):
                attacker.stat_stages[eff['stat']] += eff['stages']
            elif (eff['target'] == 'target' or eff['target'] == 'foe_side' or eff['target'] == 'all_opponents' or eff['target'] == 'all_adjacent_opponents'):
                defender.stat_stages[eff['stat']] += eff['stages']
                print(f"{defender.name}'s {eff['stat']} changed by {eff['stages']} stages.")