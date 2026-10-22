"""helper functions"""
import random
import copy
import numpy as np
from DataBase.pok_sets import charmander, squirtle, bulbasaur
from Utils.helper import to_battle_array
from SearchEngine.models import Node


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


def multiple_nodes(child: list, key):
    """Return the existing outcome node with the same key, or None"""
    for c in child:
        if c.key == key:
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
        node.stats = None
        node.expanded = 0
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
