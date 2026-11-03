import type { ActionData, TreeNode } from "../types";

// Card order on screen: moves then switches, each most visited first.
// The 1–9 shortcuts follow this order.
export function orderActions(node: TreeNode): [string, ActionData][] {
  return Object.entries(node.actions).sort(([, a], [, b]) => {
    if (a.action_type !== b.action_type) return a.action_type - b.action_type;
    return b.total_visits - a.total_visits;
  });
}

// MCTS recommends the most visited action (first one wins a tie)
export function bestActionKey(node: TreeNode): string | null {
  let best: string | null = null;
  let visits = -1;
  for (const [key, action] of Object.entries(node.actions)) {
    if (action.total_visits > visits) {
      best = key;
      visits = action.total_visits;
    }
  }
  return best;
}

export interface PathStep {
  node: TreeNode;
  action: ActionData | null; // the action that led here, null for the root
}

// Root → current, stopping at the first node the latest snapshot pruned
export function pathSteps(
  root: TreeNode,
  pathIds: string[],
  nodeMap: Map<string, TreeNode>,
): PathStep[] {
  const steps: PathStep[] = [{ node: root, action: null }];
  let parent = root;
  for (const id of pathIds) {
    const child = nodeMap.get(id);
    if (!child) break;
    const action =
      Object.values(parent.actions).find((a) => a.nodes.some((n) => n.id === id)) ?? null;
    steps.push({ node: child, action });
    parent = child;
  }
  return steps;
}
