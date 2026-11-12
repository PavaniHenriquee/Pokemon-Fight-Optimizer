// Describes the shape of every JSON object the backend sends.
// Having this lets TypeScript catch mistakes as you write the frontend.

export interface MoveEntry {
  name: string;
  pp: number;
  max_pp: number;
  type?: string; // live type from the battle array ("Fire"), Hidden Power keeps its IV type
  category?: string; // "Physical" | "Special" | "Status"
  power?: number;
}

export interface PokemonState {
  id: number;
  name: string;
  level?: number;
  gender?: string | null; // "Male" | "Female", null when genderless
  ability?: string; // live, so Worry Seed or Trace shows
  types?: string[]; // live types, e.g. ["Grass", "Poison"]
  hp: number;
  max_hp: number;
  status: string; // "BRN" | "PAR" | "SLP" | ""
  vol_status: string[]; // ["Confused", "Leech Seed", "Choice: Tackle"]
  stages: Record<string, number>; // { "Atk": 2, "SpD": -1 } — only non-zero
  item?: string;
  moves?: MoveEntry[];
}

export interface SnapshotData {
  phase: "TURN_START" | "DEATH" | "BATON_PASS";
  opp_active: number;
  terminal: boolean;
  my: PokemonState | null; // null when phase === "DEATH"
  opp: PokemonState | null;
  my_bench: BenchEntry[];
  opp_bench: BenchEntry[];
  trainer_items?: string[];
  turn: number;
  field?: FieldState;
}

// A side condition that's up: timed ones carry turns left, Spikes and Toxic Spikes their layers
export interface SideEffect {
  name: string;
  turns?: number;
  layers?: number;
}

export interface FieldState {
  weather: string; // "" | "Rain" | "Sandstorm" | "Sun" | "Hail"
  weather_turns: number; // 0 = permanent
  gravity_turns: number; // 0 = no Gravity
  trick_room_turns: number; // 0 = no Trick Room
  my_side: SideEffect[];
  opp_side: SideEffect[];
}

// One thing the foe did after an action, a dropdown in the outcome pane
export interface OppMoveRow {
  label: string; // "Pound", "Didn't move", "Pound, then Leer" over forced turns
  visits: number;
  win_chance: number; // 0–1
}

export interface ActionData {
  action_type: number; // 1 = MOVE, 2 = SWITCH
  action_idx: number;
  label: string; // e.g. "Ember" or "→ Squirtle"
  total_visits: number;
  win_chance: number; // 0–1
  dead_avg: number;
  current_pp: number | null; // current PP for moves, null for switches
  max_pp: number | null;     // max base PP from MoveDB, null for switches
  pp_up?: number;            // PP Up count (0-3)
  move_type?: string | null; // null for switches and Struggle
  category?: string | null;
  power?: number | null;
  opp_moves: OppMoveRow[]; // most often first, empty when the foe had no turn (I picked a replacement)
  nodes: TreeNode[]; // the multiple possible outcomes after this action
}

export interface TreeNode {
  id: string;
  visits: number;
  wins: number;
  win_chance: number;
  dead_avg: number;
  snapshot: SnapshotData;
  opp_moves: Record<string, number>; // visits that got here per OppMoveRow label
  actions: Record<string, ActionData>; // key = "1_0", "2_3", etc.
}

// What the backend sends over WebSocket
export interface WSMessage {
  type: "tree_update" | "waiting" | "status";
  iterations: number;
  running: boolean;
  error?: string | null; // traceback when the MCTS worker crashed
  compiling?: boolean; // the backend's startup warm-up is compiling / loading the engine
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
  item?: string | null; // set from the party, the box has no field for it
  friendship?: number; // 0-255, for Return and Frustration; missing means 255
  dead?: boolean; // in the death box: can't join the party, still counts for the species clause
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
  friendship?: number; // missing: 255 for mine, the species' base friendship for a trainer's
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
  moveInfo?: Record<string, MoveInfo>;
  pokemonTypes?: Record<string, string[]>;
  pokemonAbilities?: Record<string, string[]>; // each species' possible abilities
  learnsets?: Record<string, [number, string][]>; // level-up moves in game order, some not in MoveDB yet
  genderless?: string[];
}

export interface MoveInfo {
  type: string;
  category: string;
  power: number;
  accuracy: number | boolean | null; // true = never misses
  pp: number | null;
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

// One click on the way to a node, what ContinueConfig.path takes
export interface PathClick {
  node_id: string;
  opp_move: string | null; // the OppMoveRow label it was picked under
}

export interface TrainerEntry {
  split: string; // the sheet's split tab ("Roark" ... "Champion"), the file is in story order
  id?: number; // [pp] trainer id, missing when the sheet doesn't give one
  sprite: string;
  team: PokemonConfig[];
  trainer_items?: string[];
  terrain?: string; // Nature Power's battle terrain, plain when missing
  if_starter?: string; // a rival variant: only met if the player chose this starter
  if_player?: string; // only met if the player is this gender ("Male" / "Female")
  lacks?: string[]; // added by /trainers: what the engine can't run yet, missing when nothing
}

export type TrainerDB = Record<string, TrainerEntry>;

// DataBase/EncounterDB.json: what can be met at each location, in the sheet's story order
export interface EncounterTable {
  area: string; // part of the location the sheet's block covers ("South", "B1F"), can be empty
  method: string; // "Grass (6-7)", "Old Rod (10)", "Gift from Mom", ...
  // rates: the sheet's percentages, [morning, day, night] or a single one (surf, a rod, Poké Radar).
  // Missing for a gift, a trade or a static encounter.
  mons: { name: string; level: string; rates?: number[] }[];
}

export interface Evolution {
  name: string;
  how: string; // the sheet's words: "Lv. 16", "Use Water Stone", "Male Use Dawn Stone"
}

export interface EncounterDB {
  starters: string[];
  locations: Record<string, EncounterTable[]>;
  evolution_lines: string[][]; // for the species clause
  evolutions: Record<string, Evolution[]>; // what a species evolves into, only the ones that evolve
}

export type EncounterStatus = "caught" | "missed" | "dead";

export interface NuzlockeEncounter {
  species: string;
  status: EncounterStatus;
}

export interface NuzlockeRun {
  player: "" | "Male" | "Female";
  starter: NuzlockeEncounter; // species is empty until chosen
  encounters: Record<string, NuzlockeEncounter>; // by location, a missing one is still open
  last_trainer: string; // the trainer picked last in Setup, empty until one is
  items: string[]; // ItemPickup ids picked up, on the Tracker's Items tab
}

// DataBase/ItemLocationDB.json: what can be picked up at each location, in story order
export type PickupKind = "item" | "key" | "tm"; // key: only the rods

export interface ItemPickup {
  id: string; // what the run keeps
  item: string; // "Quick Claw", "TM76", "Good Rod"
  kind: PickupKind;
  area: string; // part of the location ("North", "Game Corner"), can be empty
  how: string; // "Hidden", "Gift from Roark", "Held by the gift Bulbasaur", can be empty
  move?: string; // a TM or HM's move and its type
  type?: string;
}

export interface ItemLocationDB {
  locations: Record<string, ItemPickup[]>;
}

export interface BenchEntry {
  slot: number;
  id: number;
  name: string;
  hp: number;
  max_hp: number;
  status: string;
  level: number;
  gender?: string | null;
  ability?: string;
  types?: string[];
  item?: string;
  moves?: MoveEntry[];
}
