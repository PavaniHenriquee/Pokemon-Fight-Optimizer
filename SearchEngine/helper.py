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
    if pct == 1.0:
        return 4
    if pct >= .75:
        return 3
    if pct >= .50:
        return 2
    if pct >= .25:
        return 1
    if pct == 0:
        return -1
    return 0


EOT_ZEROS = np.zeros(7).tobytes()


def multiple_nodes(child: list, new_state: GameState):
    """Check to see if the current state needs to create a new node"""
    #TODO: Weather because speed ties can result in different weathers
    new_snap      = NodeSnapshot.from_state(new_state)

    # If phase is to choose a new one, i don't have a current one, ->
    # so most checks are not only useless they will give errors
    new_phase_eot = new_snap.phase == _BATTLEPHASE_DEATH_END_OF_TURN

    if new_phase_eot:
        new_my_brack = _bracket(0)
    else:
        new_my_brack  = _bracket(new_snap.my_slice[Pok.CURRENT_HP]  / new_snap.my_slice[Pok.MAX_HP])
    new_opp_brack = _bracket(new_snap.opp_slice[Pok.CURRENT_HP] / new_snap.opp_slice[Pok.MAX_HP])

    # .tobytes() → C-level bytes comparison
    if new_phase_eot:
        new_my_stages = EOT_ZEROS
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


def _truncate_subtree(node: Node, keep_depth: int):
    """Clear children below keep_depth levels."""
    if keep_depth <= 0:
        node.children.clear()
        return
    for nodes in node.children.values():
        for child in nodes:
            _truncate_subtree(child, keep_depth - 1)


def prune_dominated(node: Node, threshold=0.88, min_visits=200, keep_depth=1) -> int:
    """
    Follow the best path recursively. At each node, if one action holds
    >= threshold fraction of visits, truncate all other actions' subtrees.
    Returns count of pruned action entries.

    """
    if node.visits < min_visits or not node.children:
        return 0

    action_visits = {
        key: sum(n.visits for n in nodes)
        for key, nodes in node.children.items()
    }
    total = sum(action_visits.values())
    if total == 0:
        return 0

    best_key = max(action_visits, key=action_visits.get)
    pruned = 0

    if action_visits[best_key] / total >= threshold:
        for key in list(node.children.keys()):
            if key != best_key:
                # Truncate, don't delete — keep keep_depth levels visible
                for child in node.children[key]:
                    _truncate_subtree(child, keep_depth - 1)
                pruned += 1

    # Recurse fully only into the best action
    for child in node.children.get(best_key, []):
        pruned += prune_dominated(child, threshold, min_visits, keep_depth)

    return pruned
