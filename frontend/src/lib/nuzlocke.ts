import type {
  BoxEntry,
  EncounterDB,
  EncounterTable,
  ItemLocationDB,
  IVs,
  NuzlockeEncounter,
  NuzlockeRun,
  PokemonConfig,
  PokemonData,
  TrainerEntry,
} from "../types";

export const NO_ENCOUNTER: NuzlockeEncounter = {
  species: "",
  status: "caught",
};

export const EMPTY_RUN: NuzlockeRun = {
  player: "",
  starter: NO_ENCOUNTER,
  encounters: {},
  last_trainer: "",
  items: [],
};

// Rival variants the run can't meet are hidden. A choice not made yet hides nothing.
export function trainerVisible(entry: TrainerEntry, run: NuzlockeRun | null): boolean {
  const starter = run?.starter.species;
  const player = run?.player;
  return (
    (!starter || !entry.if_starter || entry.if_starter === starter) &&
    (!player || !entry.if_player || entry.if_player === player)
  );
}

// A trainer the run can meet and the engine can run (nothing in "lacks")
export function trainerPickable(entry: TrainerEntry, run: NuzlockeRun | null): boolean {
  return trainerVisible(entry, run) && !entry.lacks;
}

// ─── Species clause: one Pokémon per evolution line ───────────────────────────

// Species → the name of its evolution line
export type LineOf = (species: string) => string;

export function makeLineOf(db: EncounterDB | null): LineOf {
  const lines = new Map<string, string>();
  for (const line of db?.evolution_lines ?? []) {
    for (const species of line) lines.set(species, line[0]);
  }
  return (species) => lines.get(species) ?? species;
}

export interface LineHolder {
  species: string;
  where: string; // the location, "Starter", "PC box" or "Death box"
  boxOnly: boolean; // in the box but not on the tracker yet
}

// Every line that's taken and what took it. Missed doesn't count: it was never caught.
export function lineHolders(
  run: NuzlockeRun,
  box: BoxEntry[],
  lineOf: LineOf,
): Map<string, LineHolder> {
  const holders = new Map<string, LineHolder>();
  const add = (species: string, where: string, boxOnly: boolean) => {
    const line = lineOf(species);
    if (!holders.has(line)) holders.set(line, { species, where, boxOnly });
  };
  if (run.starter.species) add(run.starter.species, "Starter", false);
  for (const [location, encounter] of Object.entries(run.encounters)) {
    if (encounter.species && encounter.status !== "missed") add(encounter.species, location, false);
  }
  for (const entry of box) add(entry.name, entry.dead ? "Death box" : "PC box", true);
  return holders;
}

// new: can be caught. boxed: already in the box but not logged, so it can only be logged, not caught
// again. blocked: its line is taken. A row's own line never blocks that row.
export type CatchState = "new" | "boxed" | "blocked";

export function catchState(
  species: string,
  ownSpecies: string,
  holders: Map<string, LineHolder>,
  lineOf: LineOf,
): CatchState {
  const line = lineOf(species);
  const holder = holders.get(line);
  if (!holder || (ownSpecies && lineOf(ownSpecies) === line)) return "new";
  return holder.boxOnly ? "boxed" : "blocked";
}

// The location's Pokémon that can still be caught, each once
export function newSpecies(
  tables: EncounterTable[],
  holders: Map<string, LineHolder>,
  lineOf: LineOf,
): string[] {
  const names = new Set(tables.flatMap((table) => table.mons.map((mon) => mon.name)));
  return [...names].filter((name) => !holders.has(lineOf(name)));
}

// ─── Tables an item unlocks: the rods and Surf ────────────────────────────────

// Method → the pickup that unlocks it. "Surf (20-40)" and "Surf and Rods" need Surf
const METHOD_NEEDS = [
  { method: "Old Rod", item: "Old Rod", label: "the Old Rod" },
  { method: "Good Rod", item: "Good Rod", label: "the Good Rod" },
  { method: "Super Rod", item: "Super Rod", label: "the Super Rod" },
  { method: "Surf", item: "HM03", label: "HM03 Surf" },
];

// What a table still needs, "" when nothing (or the item data hasn't loaded: then nothing is locked).
// Any ticked pickup of the item unlocks it.
export type LockOf = (table: EncounterTable) => string;

export function makeLockOf(itemDB: ItemLocationDB | null, run: NuzlockeRun): LockOf {
  if (!itemDB) return () => "";
  const picked = new Set(run.items);
  const owned = new Set(
    Object.values(itemDB.locations)
      .flat()
      .filter((p) => picked.has(p.id))
      .map((p) => p.item),
  );
  return (table) => {
    const need = METHOD_NEEDS.find((n) => table.method.startsWith(n.method));
    return need && !owned.has(need.item) ? need.label : "";
  };
}

// How many of a location's Pokémon can still be caught
export function countNew(
  tables: EncounterTable[],
  holders: Map<string, LineHolder>,
  lineOf: LineOf,
): number {
  return newSpecies(tables, holders, lineOf).length;
}

// A table's rates as you'd meet them now: per Pokémon, one per column (morning, day, night, or the only
// one). The species clause skips a Pokémon whose line is taken, so the ones still counted share its
// weight. Only a full table (a column adding up to 100) is spread again: Poké Radar's 22% and the Great
// Marsh's odds of being the day's Pokémon stay as the sheet gives them. A skipped Pokémon gets 0.
export function shownRates(table: EncounterTable, counts: (species: string) => boolean): number[][] {
  const columns = Math.max(0, ...table.mons.map((mon) => mon.rates?.length ?? 0));
  const total = (i: number, countedOnly: boolean) =>
    table.mons.reduce(
      (sum, mon) => sum + (!countedOnly || counts(mon.name) ? (mon.rates?.[i] ?? 0) : 0),
      0,
    );
  const scale = Array.from({ length: columns }, (_, i) => {
    if (total(i, false) !== 100) return 1;
    const left = total(i, true);
    return left > 0 ? 100 / left : 0;
  });
  return table.mons.map((mon) =>
    (mon.rates ?? []).map((rate, i) => (counts(mon.name) ? rate * scale[i] : 0)),
  );
}

// ─── Catching: what a new box Pokémon starts with ─────────────────────────────

const DEFAULT_IVS: IVs = {
  HP: 31,
  Attack: 31,
  Defense: 31,
  "Special Attack": 31,
  "Special Defense": 31,
  Speed: 31,
};

// A Pokémon's friendship when the box doesn't say: the most Return gets (backend MY_FRIENDSHIP)
export const MAX_FRIENDSHIP = 255;

export function makeBlank(): Omit<BoxEntry, "id"> {
  return {
    name: "",
    gender: "Male",
    nature: "Hardy",
    ability: "",
    level: 5,
    moves: ["", "", "", ""],
    ivs: { ...DEFAULT_IVS },
    friendship: MAX_FRIENDSHIP,
  };
}

// The moves a Pokémon is created with ([pp] BoxPokemon_SetDefaultMoves): it learns its level-up moves
// in order, a move it knows is skipped, and with four known the oldest makes room.
export function defaultMoves(learnset: [number, string][], level: number): string[] {
  const moves: string[] = [];
  for (const [learnedAt, move] of learnset) {
    if (learnedAt > level) break;
    if (moves.includes(move)) continue;
    if (moves.length === 4) moves.shift();
    moves.push(move);
  }
  return moves;
}

// Those moves as the popup's four slots. A move that isn't in MoveDB stops a search from starting, so
// it leaves its slot empty and comes back in leftOut.
export function startingMoves(
  data: PokemonData,
  species: string,
  level: number,
): { moves: string[]; leftOut: string[] } {
  const known = defaultMoves(data.learnsets?.[species] ?? [], level);
  const usable = known.filter((move) => data.moves.includes(move));
  return {
    moves: [...usable, "", "", "", ""].slice(0, 4),
    leftOut: known.filter((move) => !usable.includes(move)),
  };
}

// The level the popup starts at: the low end of the table's range. The sheet leaves some of them empty
// with the level in the method ("Honey Tree (39)", the Old Rod's in "Rods (O-10, G-25, S-50)"). Trades
// and the Great Marsh have none, so they start at the blank entry's level.
export function encounterLevel(level: string, method: string): number {
  const found = /\d+/.exec(level || method);
  return found ? Number(found[0]) : makeBlank().level;
}

// A genderless species has no gender, and any other species always has one
export function genderFor(data: PokemonData, species: string, gender: string | null): string | null {
  return data.genderless?.includes(species) ? null : (gender ?? "Male");
}

export function catchDraft(data: PokemonData, species: string, level: number): Omit<BoxEntry, "id"> {
  const abilities = data.pokemonAbilities?.[species] ?? [];
  const blank = makeBlank();
  return {
    ...blank,
    name: species,
    gender: genderFor(data, species, blank.gender),
    level,
    // With two to choose from it stays empty until you say which: the search depends on it
    ability: abilities.length === 1 ? abilities[0] : "",
    moves: startingMoves(data, species, level).moves,
  };
}

// ─── The tracker and the box: they match by evolution line ────────────────────

// The box Pokémon behind a tracker row, in the PC box or the death box
export function boxEntryOf(
  box: BoxEntry[],
  lineOf: LineOf,
  species: string,
): BoxEntry | undefined {
  const line = lineOf(species);
  return box.find((entry) => lineOf(entry.name) === line);
}

// The starter and the player's gender (they decide the rival) can't change once the box holds a Pokémon
// of another line, dead or alive. Clearing that catch frees them again.
export function starterLocked(run: NuzlockeRun, box: BoxEntry[], lineOf: LineOf): boolean {
  const { species } = run.starter;
  return !!species && box.some((entry) => lineOf(entry.name) !== lineOf(species));
}

// The run with a row changed. where: a location, null for the starter. No encounter clears it.
export function withRow(
  run: NuzlockeRun,
  where: string | null,
  encounter: NuzlockeEncounter | null,
): NuzlockeRun {
  if (where === null) return { ...run, starter: encounter ?? NO_ENCOUNTER };
  const encounters = { ...run.encounters };
  if (encounter) encounters[where] = encounter;
  else delete encounters[where];
  return { ...run, encounters };
}

// The party with an edited box Pokémon's copy updated
export function partyAfterEdit(
  team: PokemonConfig[],
  oldName: string,
  entry: BoxEntry,
): PokemonConfig[] {
  return team.map((member) =>
    member.name === oldName
      ? {
          ...member,
          name: entry.name,
          gender: entry.gender,
          level: entry.level,
          ability: entry.ability,
          nature: entry.nature,
          moves: [...entry.moves],
          ivs: { ...entry.ivs },
          item: entry.item ?? undefined,
          friendship: entry.friendship,
        }
      : member,
  );
}

// The box with a party member's edits. They match by name, the same way "in the party" does. The same
// array if it isn't in the box.
export function boxAfterPartyEdit(box: BoxEntry[], member: PokemonConfig): BoxEntry[] {
  const target = box.find((entry) => !entry.dead && entry.name === member.name);
  if (!target) return box;
  return box.map((entry) =>
    entry === target
      ? {
          ...entry,
          gender: member.gender,
          level: member.level,
          ability: member.ability,
          nature: member.nature,
          moves: [...member.moves],
          ivs: member.ivs ? { ...member.ivs } : entry.ivs,
          item: member.item ?? null,
          friendship: member.friendship ?? entry.friendship,
        }
      : entry,
  );
}

// ─── Deaths: the tracker and the box agree, by evolution line ─────────────────

// The Pokémon a tracker change just killed or brought back
export function deathChanges(
  prev: NuzlockeRun,
  next: NuzlockeRun,
): { species: string; dead: boolean }[] {
  const changes: { species: string; dead: boolean }[] = [];
  const compare = (before: NuzlockeEncounter | undefined, after: NuzlockeEncounter | undefined) => {
    if (!after?.species) return;
    if (after.status === "dead" && before?.status !== "dead") {
      changes.push({ species: after.species, dead: true });
    } else if (
      after.status === "caught" &&
      before?.status === "dead" &&
      before.species === after.species
    ) {
      changes.push({ species: after.species, dead: false });
    }
  };
  compare(prev.starter, next.starter);
  for (const [location, encounter] of Object.entries(next.encounters)) {
    compare(prev.encounters[location], encounter);
  }
  return changes;
}

// The box with that species' line moved to or out of the death box. The same array if nothing moved.
export function setDeadInBox(
  box: BoxEntry[],
  lineOf: LineOf,
  species: string,
  dead: boolean,
): BoxEntry[] {
  const line = lineOf(species);
  const moves = (entry: BoxEntry) => lineOf(entry.name) === line && !!entry.dead !== dead;
  if (!box.some(moves)) return box;
  return box.map((entry) => (moves(entry) ? { ...entry, dead } : entry));
}

// The run with that species' line marked Dead or back to Caught. The same run if nothing changed.
export function setDeadInRun(
  run: NuzlockeRun,
  lineOf: LineOf,
  species: string,
  dead: boolean,
): NuzlockeRun {
  const line = lineOf(species);
  const update = (encounter: NuzlockeEncounter): NuzlockeEncounter => {
    const from = dead ? "caught" : "dead";
    if (encounter.species && lineOf(encounter.species) === line && encounter.status === from) {
      return { ...encounter, status: dead ? "dead" : "caught" };
    }
    return encounter;
  };
  const starter = update(run.starter);
  const encounters = Object.fromEntries(
    Object.entries(run.encounters).map(([location, encounter]) => [location, update(encounter)]),
  );
  const changed =
    starter !== run.starter ||
    Object.keys(encounters).some((location) => encounters[location] !== run.encounters[location]);
  return changed ? { ...run, starter, encounters } : run;
}
