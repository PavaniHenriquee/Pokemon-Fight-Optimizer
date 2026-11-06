import type {
  BoxEntry,
  EncounterDB,
  EncounterTable,
  NuzlockeEncounter,
  NuzlockeRun,
  TrainerEntry,
} from "../types";

export const NO_ENCOUNTER: NuzlockeEncounter = {
  species: "",
  nickname: "",
  status: "caught",
};

export const EMPTY_RUN: NuzlockeRun = {
  player: "",
  starter: NO_ENCOUNTER,
  encounters: {},
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

// How many of a location's Pokémon can still be caught
export function countNew(
  tables: EncounterTable[],
  holders: Map<string, LineHolder>,
  lineOf: LineOf,
): number {
  const names = new Set(tables.flatMap((table) => table.mons.map((mon) => mon.name)));
  return [...names].filter((name) => !holders.has(lineOf(name))).length;
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
