"""helper functions"""
import random
import copy
import numpy as np
from DataBase.pok_sets import charmander, squirtle, bulbasaur
from Utils.helper import to_battle_array
from Models.idx_const import Pok
from Models.constants import _BATTLEPHASE_DEATH_END_OF_TURN
from SearchEngine.models import Node, GameState, NodeSnapshot


def create_random_initial_state():
    """random team selector"""
    team_pool = [charmander, squirtle, bulbasaur]

    def random_team(pool, max_size=3):
        size = random.randint(1, max_size)  # random team size 1–3
        chosen = random.sample(pool, size)  # pick without replacement
        team = [copy.deepcopy(p) for p in chosen]  # make independent copies
        random.shuffle(team)  # randomize order
        return team

    my_team = random_team(team_pool)
    opp_team = random_team(team_pool)
    battle_array = to_battle_array(my_team, opp_team)
    return battle_array


def _bracket(pct: float) -> int:
    """HP brackets pre-computed as ints — avoids recalculating per child"""
    if pct >= .75:
        return 3
    if pct >= .50:
        return 2
    if pct >= .25:
        return 1
    if pct == 0:
        return -1
    return 0


def multiple_nodes(child: list, new_state: GameState):
    """Check to see if the current state needs to create a new node"""
    #TODO: Weather because of speed ties
    # Pre-compute everything from new_state ONCE, outside the loop
    new_snap      = NodeSnapshot.from_state(new_state)
    new_phase_eot = new_snap.phase == _BATTLEPHASE_DEATH_END_OF_TURN

    if new_phase_eot:
        new_my_brack = _bracket(0)
    else:
        new_my_brack  = _bracket(new_snap.my_slice[Pok.CURRENT_HP]  / new_snap.my_slice[Pok.MAX_HP])
    new_opp_brack = _bracket(new_snap.opp_slice[Pok.CURRENT_HP] / new_snap.opp_slice[Pok.MAX_HP])

    # .tobytes() → C-level bytes comparison
    if new_phase_eot:
        new_my_stages = np.zeros(7).tobytes()
    else:
        new_my_stages  = new_snap.my_slice[Pok.ATTACK_STAT_STAGE:Pok.EVASION_STAT_STAGE + 1].tobytes()
    new_opp_stages = new_snap.opp_slice[Pok.ATTACK_STAT_STAGE:Pok.EVASION_STAT_STAGE + 1].tobytes()

    for c in child:
        # Cheapest checks first (scalar int comparisons) → bail early
        s = c.snapshot
        s_phase_eot = s.phase == _BATTLEPHASE_DEATH_END_OF_TURN
        if s.phase      != new_snap.phase:      continue
        if s.opp_active != new_snap.opp_active: continue
        if not s_phase_eot and s.my_slice[Pok.STATUS]    != new_snap.my_slice[Pok.STATUS]:  continue
        if s.opp_slice[Pok.STATUS]   != new_snap.opp_slice[Pok.STATUS]: continue
        if not s_phase_eot and s.my_slice[Pok.VOL_STATUS]  != new_snap.my_slice[Pok.VOL_STATUS]: continue
        if s.opp_slice[Pok.VOL_STATUS] != new_snap.opp_slice[Pok.VOL_STATUS]: continue
        if (
            not s_phase_eot
            and _bracket(s.my_slice[Pok.CURRENT_HP]  / s.my_slice[Pok.MAX_HP])  != new_my_brack
        ):
            continue
        if _bracket(s.opp_slice[Pok.CURRENT_HP] / s.opp_slice[Pok.MAX_HP]) != new_opp_brack: continue
        if (
            not s_phase_eot
            and s.my_slice[Pok.ATTACK_STAT_STAGE:Pok.EVASION_STAT_STAGE + 1].tobytes()  != new_my_stages
        ):
            continue
        if s.opp_slice[Pok.ATTACK_STAT_STAGE:Pok.EVASION_STAT_STAGE + 1].tobytes() != new_opp_stages: continue

        c.snapshot = new_snap
        return c

    return None

def find_best_terminal_node(root: Node):
    """Follow the highest-visit path down to the deepest node"""
    node = root
    path = [node]
    actions = []

    while node.children:
        # Pick the action with most total visits (the "committed" path)
        best_action, best_children = max(
            node.children.items(),
            key=lambda x: sum(n.visits for n in x[1])
        )
        # Pick the most visited outcome for that action
        best_child = max(best_children, key=lambda n: n.visits)
        actions.append(best_action)
        node = best_child
        path.append(node)

    return node, path, actions
