// Describes the shape of every JSON object the backend sends.
// Having this lets TypeScript catch mistakes as you write the frontend.

export interface PokemonState {
  id: number;
  name: string;
  hp: number;
  max_hp: number;
  status: string; // "BRN" | "PAR" | "SLP" | ""
  vol_status: string[]; // ["Confused", "Leech Seed"]
  stages: Record<string, number>; // { "Atk": 2, "SpD": -1 } — only non-zero
}

export interface SnapshotData {
  phase: "TURN_START" | "DEATH";
  opp_active: number;
  terminal: boolean;
  my: PokemonState | null; // null when phase === "DEATH"
  opp: PokemonState | null;
}

export interface ActionData {
  action_type: number; // 1 = MOVE, 2 = SWITCH
  action_idx: number;
  label: string; // e.g. "Ember" or "→ Squirtle"
  total_visits: number;
  win_chance: number; // 0–1
  dead_avg: number;
  nodes: TreeNode[]; // the multiple possible outcomes after this action
}

export interface TreeNode {
  id: string;
  visits: number;
  wins: number;
  win_chance: number;
  dead_avg: number;
  snapshot: SnapshotData;
  actions: Record<string, ActionData>; // key = "1_0", "2_3", etc.
}

// What the backend sends over WebSocket
export interface WSMessage {
  type: "tree_update" | "waiting" | "status";
  iterations: number;
  running: boolean;
  tree?: TreeNode;
}
