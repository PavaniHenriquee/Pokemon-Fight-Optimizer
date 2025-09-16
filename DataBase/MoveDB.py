"""Database for moves in python, where it gives everything a move does"""  # pylint:disable=C0103
"""
Template:
'move':{
    'name': 'move'
    'category': 'Physical' | 'Special' | 'Status'
    'type': String
    'target': 'adjacentAlly' | 'adjacentAllyOrSelf' | 'adjacentFoe' | 'all' | 'allAdjacent' | 'allAdjacentFoes' |
    'allies' | 'allySide' | 'allyTeam' | 'any' | 'foeSide' | 'normal' | 'randomNormal' | 'scripted' | 'self';
    'power': Number
    'accuracy': True | Number
    'crit_ratio': Number
    'will_crit': Bool
    'oh_ko': Bool
    'secondary': List | Null
    'sheer_force': Bool
    'priority': Number
    'override_off_pok': 'target' | 'source'
    'override_off_stat': 'Attack' | 'Defense' | 'Special Attack' | 'Special Defense' | 'Speed'
    'override_def_stat': 'Attack' | 'Defense' | 'Special Attack' | 'Special Defense' | 'Speed'
    'ignore_def': Bool  # Chip Away, Sacred Sword, Darkest Lariat
    'ignore_immunity': Bool
    'pp': Number
    'ppup': 1 | 2 | 3
    'multi_hit': Number | [min, max]
    'flags': Obj
    'self_switch': Bool
    'non_ghost': 'self'  # Used for Curse
    'ignore_ab': Bool
    'damage': Number | 'level'
    'spread_hit': Bool
    'spread_mod': Number
    'crit_mod': Number
    'force_stab': Bool  # Used for pledge moves
    'vol_status': ID  # Like Heal block, Grudge
}

"""
