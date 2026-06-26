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
  item?: string;
}

export interface SnapshotData {
  phase: "TURN_START" | "DEATH";
  opp_active: number;
  terminal: boolean;
  opp_move: string | null;
  my: PokemonState | null; // null when phase === "DEATH"
  opp: PokemonState | null;
  my_bench: BenchEntry[];
  opp_bench: BenchEntry[];
  trainer_items?: string[];
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

export interface IVs {
  HP: number;
  Attack: number;
  Defense: number;
  "Special Attack": number;
  "Special Defense": number;
  Speed: number;
}

export interface BoxEntry {
  id: string;
  name: string;
  gender: string | null;
  nature: string;
  ability: string;
  level: number;
  moves: string[];
  ivs: IVs;
}

export interface PokemonConfig {
  name: string;
  gender: string | null;
  level: number;
  ability: string;
  nature: string;
  moves: string[]; // up to 4, empty string = unused slot
  ivs?: IVs;
  item?: string;
}

export interface BaseStats {
  HP: number;
  Attack: number;
  Defense: number;
  "Special Attack": number;
  "Special Defense": number;
  Speed: number;
}

export interface PokemonData {
  pokemon: string[];
  moves: string[];
  natures: string[];
  abilities: string[];
  items: string[];
  nameToId: Record<string, number>;
  baseStats: Record<string, BaseStats>;
  natureMultipliers: Record<string, Record<string, number>>;
}

export interface PokemonEntry {
  slot: number;
  pok_id: number;
  name: string;
  hp: number;
  max_hp: number;
}

export interface NodeInfoData {
  my_active: PokemonEntry | null; // null in DEATH phase
  opp_active: PokemonEntry;
  my_bench: PokemonEntry[]; // alive bench only
}

export interface TrainerEntry {
  sprite: string;
  team: PokemonConfig[];
  trainer_items?: string[];
}

export type TrainerDB = Record<string, TrainerEntry>;

export interface BenchEntry {
  slot: number;
  id: number;
  name: string;
  hp: number;
  max_hp: number;
  status: string;
  level: number;
  item?: string;
}
