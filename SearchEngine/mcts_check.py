"""Does a passthorugh so underpopulated rng paths get its proper checks"""


def find_best_terminal_node(root):
    """Follow the highest-visit path down to the deepest node"""
    node = root
    path = [node]

    while node.children:
        # Pick the action with most total visits (the "committed" path)
        _, best_children = max(
            node.children.items(),
            key=lambda x: sum(n.visits for n in x[1])
        )
        # Pick the most visited outcome for that action
        best_child = max(best_children, key=lambda n: n.visits)
        path.append(best_child)

    return path


def find_first_rng_branch(path):
    """
    Walk up from terminal node until we find a node
    where the chosen action had more than 1 RNG outcome
    """
    # Reverse path: terminal -> root
    for i in range(len(path) - 1, 0, -1):
        node = path[i]
        parent = path[i - 1]

        # Find which action led to this node
        for _, outcome_nodes in parent.children.items():
            if node in outcome_nodes:
                if len(outcome_nodes) > 1:
                    return outcome_nodes
                break  # This action only had 1 RNG outcome, keep walking up

    return None # No RNG branch found


def pass_through(root):
    """passthrough from bottom to top checking unvisited childs and seeing their true values"""
    stable = False
    new_root = root
    while not stable:
        path = find_best_terminal_node(new_root)
        nodes = find_best_terminal_node(path)
        for n in nodes:
            if n.visits < 750:
                pass

        if stable:
            stable = True
