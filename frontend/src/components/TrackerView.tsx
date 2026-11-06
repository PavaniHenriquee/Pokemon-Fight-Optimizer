import { useState } from "react";
import { ChevronDown, ChevronRight, RotateCcw, Search, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { displayName } from "@/lib/format";
import {
  NO_ENCOUNTER,
  catchState,
  countNew,
  lineHolders,
  type LineHolder,
  type LineOf,
} from "@/lib/nuzlocke";
import { frontStatic, pokIcon } from "@/lib/sprites";
import type {
  BoxEntry,
  EncounterDB,
  EncounterStatus,
  EncounterTable,
  NuzlockeEncounter,
  NuzlockeRun,
  PokemonData,
} from "../types";
import { Button } from "./ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "./ui/tooltip";
import { Chip } from "./common/Badges";
import { Sprite } from "./common/Sprite";
import { NameSelect } from "./PokemonSlots";

const STATUSES: { id: EncounterStatus; label: string; hint: string; active: string }[] = [
  {
    id: "caught",
    label: "Caught",
    hint: "Caught and alive",
    active: "bg-good/15 text-good ring-good/30",
  },
  {
    id: "missed",
    label: "Missed",
    hint: "Encounter used up: it fainted or fled",
    active: "bg-warn/15 text-warn ring-warn/30",
  },
  {
    id: "dead",
    label: "Dead",
    hint: "Caught, then fainted",
    active: "bg-bad/15 text-bad ring-bad/30",
  },
];

const tableLabel = (table: EncounterTable) =>
  [table.area, table.method].filter(Boolean).join(" · ");

function SegmentButton({
  active,
  activeClass,
  disabled,
  title,
  onClick,
  children,
}: {
  active: boolean;
  activeClass: string;
  disabled?: boolean;
  title: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      title={title}
      disabled={disabled}
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "h-7 rounded-md px-2.5 text-[11px] font-medium ring-1 ring-inset transition-colors",
        disabled
          ? "cursor-not-allowed text-subtle-foreground/50 ring-transparent"
          : "cursor-pointer",
        !disabled && (active ? activeClass : "text-muted-foreground ring-transparent hover:text-foreground"),
      )}
    >
      {children}
    </button>
  );
}

function StatusPicker({
  status,
  hasSpecies,
  allowMissed,
  onChange,
}: {
  status: EncounterStatus | null;
  hasSpecies: boolean;
  allowMissed: boolean;
  onChange: (status: EncounterStatus) => void;
}) {
  return (
    <div className="flex shrink-0 gap-0.5 rounded-lg bg-background/60 p-0.5 ring-1 ring-border">
      {STATUSES.filter((s) => allowMissed || s.id !== "missed").map((s) => (
        <SegmentButton
          key={s.id}
          active={status === s.id}
          activeClass={s.active}
          // Missed can have no species (it fled before you saw much), the others need one
          disabled={s.id !== "missed" && !hasSpecies}
          title={s.id !== "missed" && !hasSpecies ? "Pick the Pokémon first" : s.hint}
          onClick={() => onChange(s.id)}
        >
          {s.label}
        </SegmentButton>
      ))}
    </div>
  );
}

// Typing only saves when the field loses focus, not on every letter
function NicknameInput({
  value,
  disabled,
  onCommit,
  className,
}: {
  value: string;
  disabled: boolean;
  onCommit: (nickname: string) => void;
  className?: string;
}) {
  const [draft, setDraft] = useState(value);
  const [shown, setShown] = useState(value);
  if (value !== shown) {
    setShown(value);
    setDraft(value);
  }
  return (
    <input
      value={draft}
      disabled={disabled}
      placeholder="Nickname"
      maxLength={10}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => {
        if (draft !== value) onCommit(draft);
      }}
      className={cn(
        "h-8 min-w-0 rounded-lg border border-input bg-input/30 px-2 text-sm outline-none placeholder:text-subtle-foreground focus:border-ring focus:ring-3 focus:ring-ring/50 disabled:opacity-40",
        className,
      )}
    />
  );
}

// ─── Top strip: starter, gender, counts ───────────────────────────────────────

function StarterCard({
  starters,
  run,
  nameToId,
  onChange,
}: {
  starters: string[];
  run: NuzlockeRun;
  nameToId: Record<string, number>;
  onChange: (starter: NuzlockeEncounter) => void;
}) {
  const { starter } = run;
  return (
    <div className="flex items-center gap-3">
      <div className="flex gap-1">
        {starters.map((name) => {
          const chosen = starter.species === name;
          return (
            <button
              key={name}
              type="button"
              title={chosen ? "Clear the starter" : `Choose ${displayName(name)}`}
              aria-pressed={chosen}
              onClick={() => onChange(chosen ? NO_ENCOUNTER : { ...NO_ENCOUNTER, species: name })}
              className={cn(
                "flex size-14 cursor-pointer items-center justify-center rounded-lg ring-1 transition-colors",
                chosen ? "bg-primary/15 ring-primary/50" : "bg-background/60 ring-border hover:bg-foreground/5",
                starter.species && !chosen && "opacity-40",
              )}
            >
              {nameToId[name] && (
                <Sprite
                  srcs={frontStatic(nameToId[name])}
                  alt={name}
                  width={48}
                  height={48}
                  className={cn(starter.status === "dead" && chosen && "grayscale")}
                />
              )}
            </button>
          );
        })}
      </div>
      <div className="flex min-w-0 flex-col gap-1.5">
        <NicknameInput
          value={starter.nickname}
          disabled={!starter.species}
          onCommit={(nickname) => onChange({ ...starter, nickname })}
          className="w-36"
        />
        <StatusPicker
          status={starter.species ? starter.status : null}
          hasSpecies={!!starter.species}
          allowMissed={false}
          onChange={(status) => onChange({ ...starter, status })}
        />
      </div>
    </div>
  );
}

function RunSummary({
  run,
  total,
  canStartOver,
  onNewRun,
}: {
  run: NuzlockeRun;
  total: number;
  canStartOver: boolean; // it erases the box too, so the box has to be loaded
  onNewRun: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const entries = [...Object.values(run.encounters), ...(run.starter.species ? [run.starter] : [])];
  const count = (status: EncounterStatus) => entries.filter((e) => e.status === status).length;
  return (
    <div className="ml-auto flex flex-wrap items-center justify-end gap-1.5">
      <Chip title="Locations whose one encounter is used">
        {Object.keys(run.encounters).length}/{total} locations
      </Chip>
      <Chip tone="good" title="Alive, starter included">
        {count("caught")} alive
      </Chip>
      <Chip tone="bad" title="Caught, then fainted, starter included">
        {count("dead")} dead
      </Chip>
      <Chip tone="warn" title="Encounters that fainted or fled">
        {count("missed")} missed
      </Chip>
      <Tooltip>
        <TooltipTrigger asChild>
          {/* span wrapper: a disabled button doesn't fire hover events */}
          <span>
            <Button
              variant={confirming ? "destructive" : "ghost"}
              size="sm"
              disabled={!canStartOver}
              onClick={() => {
                if (!confirming) {
                  setConfirming(true);
                  return;
                }
                onNewRun();
                setConfirming(false);
              }}
              onMouseLeave={() => setConfirming(false)}
            >
              <RotateCcw />
              {confirming ? "Erase run and box?" : "New run"}
            </Button>
          </span>
        </TooltipTrigger>
        <TooltipContent>
          {!canStartOver
            ? "The box isn't loaded, so it couldn't be erased with the run"
            : confirming
              ? "Click again to erase the run, PC box, death box and party"
              : "Start over: erases the run, PC box, death box and party"}
        </TooltipContent>
      </Tooltip>
    </div>
  );
}

// ─── One location ─────────────────────────────────────────────────────────────

// The species clause in a word, for a Pokémon that can't simply be caught here
function holderText(holder: LineHolder | undefined): string {
  if (!holder) return "";
  return `${displayName(holder.species)} (${holder.where})`;
}

function LocationTables({
  tables,
  nameToId,
  ownSpecies,
  holders,
  lineOf,
  onPick,
}: {
  tables: EncounterTable[];
  nameToId: Record<string, number>;
  ownSpecies: string;
  holders: Map<string, LineHolder>;
  lineOf: LineOf;
  onPick: (species: string) => void;
}) {
  return (
    <div className="grid gap-2 border-t bg-background/30 p-2.5 sm:grid-cols-2 xl:grid-cols-3">
      {tables.map((table) => (
        <div key={tableLabel(table)} className="min-w-0">
          <div className="mb-1 truncate text-[11px] font-medium text-subtle-foreground" title={tableLabel(table)}>
            {tableLabel(table)}
          </div>
          <div className="flex flex-wrap gap-1">
            {table.mons.map((mon) => {
              const state = catchState(mon.name, ownSpecies, holders, lineOf);
              const holder = holderText(holders.get(lineOf(mon.name)));
              const content = (
                <>
                  {nameToId[mon.name] && (
                    <Sprite
                      srcs={pokIcon(nameToId[mon.name])}
                      alt={mon.name}
                      width={32}
                      height={24}
                      className={cn(state === "blocked" && "grayscale")}
                    />
                  )}
                  <span className={cn(state === "blocked" && "line-through")}>{displayName(mon.name)}</span>
                  {mon.level && <span className="num text-subtle-foreground">{mon.level}</span>}
                </>
              );
              // A span, not a disabled button: its tooltip has to say what took the line
              if (state === "blocked") {
                return (
                  <span
                    key={mon.name}
                    title={`Already caught: ${holder}`}
                    className="flex h-7 cursor-not-allowed items-center gap-1 rounded-md pr-2 text-[11px] opacity-40"
                  >
                    {content}
                  </span>
                );
              }
              return (
                <button
                  key={mon.name}
                  type="button"
                  onClick={() => onPick(mon.name)}
                  title={state === "boxed" ? `Log it here, it's your ${holder}` : `Pick ${displayName(mon.name)}`}
                  className={cn(
                    "flex h-7 cursor-pointer items-center gap-1 rounded-md pr-2 text-[11px] transition-colors hover:bg-foreground/10",
                    state === "boxed" ? "bg-foreground/5 ring-1 ring-info/40 ring-inset" : "bg-foreground/5",
                  )}
                >
                  {content}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

function LocationRow({
  name,
  tables,
  encounter,
  nameToId,
  holders,
  lineOf,
  onChange,
}: {
  name: string;
  tables: EncounterTable[];
  encounter: NuzlockeEncounter | undefined;
  nameToId: Record<string, number>;
  holders: Map<string, LineHolder>;
  lineOf: LineOf;
  onChange: (encounter: NuzlockeEncounter | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const species = encounter?.species ?? "";
  const status = encounter?.status ?? null;
  const newHere = countNew(tables, holders, lineOf);

  // A species can be in several tables: the picker lists it once, under the first
  const firstTable = new Map<string, EncounterTable>();
  for (const table of tables) {
    for (const mon of table.mons) {
      if (!firstTable.has(mon.name)) firstTable.set(mon.name, table);
    }
  }

  // The species clause: only what can be caught here, and what this row already holds
  const pickable = [...firstTable.keys()].filter(
    (mon) => catchState(mon, species, holders, lineOf) !== "blocked",
  );
  if (species && !pickable.includes(species)) pickable.unshift(species);

  function pick(next: string) {
    if (next) {
      // Logging a line that's in the death box: it already died
      const died = holders.get(lineOf(next))?.where === "Death box";
      onChange({
        ...NO_ENCOUNTER,
        ...encounter,
        species: next,
        status: died ? "dead" : (status ?? "caught"),
      });
    } else if (status === "missed") onChange({ ...NO_ENCOUNTER, ...encounter, species: "" });
    else onChange(null);
  }

  return (
    <div className={cn("overflow-hidden rounded-lg border", encounter ? "bg-card" : "bg-card/40")}>
      <div className="grid grid-cols-[minmax(180px,230px)_minmax(170px,1fr)_minmax(90px,150px)_auto_28px] items-center gap-2 px-2 py-1.5">
        <button
          type="button"
          onClick={() => setOpen(!open)}
          aria-expanded={open}
          title="Show what's here"
          className="flex min-w-0 cursor-pointer items-center gap-1 text-left text-[13px] font-medium"
        >
          {open ? (
            <ChevronDown className="size-3.5 shrink-0 text-subtle-foreground" />
          ) : (
            <ChevronRight className="size-3.5 shrink-0 text-subtle-foreground" />
          )}
          <span className="truncate">{name}</span>
          {!encounter && (
            <span
              className={cn(
                "num ml-auto shrink-0 pl-1 text-[10px] font-normal",
                newHere > 0 ? "text-subtle-foreground" : "text-warn",
              )}
              title="Pokémon here you can still catch"
            >
              {newHere > 0 ? `${newHere} new` : "nothing new"}
            </span>
          )}
        </button>

        <div className="flex min-w-0 items-center gap-1.5">
          <span className="flex h-6 w-8 shrink-0 items-center justify-center">
            {species && nameToId[species] && (
              <Sprite
                srcs={pokIcon(nameToId[species])}
                alt={species}
                width={32}
                height={24}
                className={cn(status === "dead" && "grayscale", status === "missed" && "opacity-40")}
              />
            )}
          </span>
          <div className="min-w-0 flex-1">
            <NameSelect
              value={species}
              onChange={pick}
              items={pickable}
              itemLabel={displayName}
              placeholder="Pokémon"
              clearable={!!species}
              renderItem={(item) => {
                const table = firstTable.get(item);
                const boxed = catchState(item, species, holders, lineOf) === "boxed";
                return (
                  <span className="flex w-full min-w-0 items-center gap-1.5">
                    {nameToId[item] && (
                      <Sprite srcs={pokIcon(nameToId[item])} alt="" width={32} height={24} className="shrink-0" />
                    )}
                    <span className="truncate">{displayName(item)}</span>
                    {table && (
                      <span
                        className={cn(
                          "ml-auto truncate pl-2 text-[10px]",
                          boxed ? "text-info" : "text-subtle-foreground",
                        )}
                      >
                        {boxed ? "in your box" : tableLabel(table)}
                      </span>
                    )}
                  </span>
                );
              }}
            />
          </div>
        </div>

        <NicknameInput
          value={encounter?.nickname ?? ""}
          disabled={!species}
          onCommit={(nickname) => onChange({ ...NO_ENCOUNTER, ...encounter, nickname })}
        />

        <StatusPicker
          status={status}
          hasSpecies={!!species}
          allowMissed
          onChange={(next) => onChange({ ...NO_ENCOUNTER, ...encounter, status: next })}
        />

        <Button
          variant="ghost"
          size="icon-xs"
          disabled={!encounter}
          onClick={() => onChange(null)}
          aria-label={`Clear ${name}`}
          title="Clear this location"
        >
          <X />
        </Button>
      </div>

      {open && (
        <LocationTables
          tables={tables}
          nameToId={nameToId}
          ownSpecies={species}
          holders={holders}
          lineOf={lineOf}
          onPick={(next) => {
            pick(next);
            setOpen(false);
          }}
        />
      )}
    </div>
  );
}

// ─── Exported: the tab ────────────────────────────────────────────────────────

export default function TrackerView({
  run,
  encounterDB,
  pokemonData,
  box,
  lineOf,
  error,
  onRetry,
  onChange,
  onNewRun,
}: {
  run: NuzlockeRun | null;
  encounterDB: EncounterDB | null;
  pokemonData: PokemonData | null;
  box: BoxEntry[] | null;
  lineOf: LineOf;
  error: string | null;
  onRetry: () => void;
  onChange: (run: NuzlockeRun) => void;
  onNewRun: () => void;
}) {
  const [query, setQuery] = useState("");
  const [canCatchOnly, setCanCatchOnly] = useState(false);

  // Nothing here may save until the real run has loaded: an empty run would replace it
  if (!run || !encounterDB || !pokemonData) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
        <p className="max-w-md text-sm text-muted-foreground">
          {error ? `Couldn't load the Nuzlocke run: ${error}` : "Loading the Nuzlocke run…"}
        </p>
        {error && (
          <Button variant="outline" size="sm" onClick={onRetry}>
            Try again
          </Button>
        )}
      </div>
    );
  }

  const { nameToId } = pokemonData;
  const locations = Object.entries(encounterDB.locations);
  const holders = lineHolders(run, box ?? [], lineOf);
  const q = query.trim().toLowerCase();
  // A search also finds where a Pokémon lives
  const shown = locations.filter(([name, tables]) => {
    if (canCatchOnly && (run.encounters[name] || countNew(tables, holders, lineOf) === 0)) return false;
    if (!q || name.toLowerCase().includes(q)) return true;
    return tables.some((t) => t.mons.some((m) => displayName(m.name).toLowerCase().includes(q)));
  });

  function setEncounter(name: string, encounter: NuzlockeEncounter | null) {
    if (!run) return;
    const encounters = { ...run.encounters };
    if (encounter) encounters[name] = encounter;
    else delete encounters[name];
    onChange({ ...run, encounters });
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="shrink-0 border-b bg-card/40">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-5 gap-y-2 px-4 py-2.5">
          <div>
            <div className="mb-1 text-[11px] font-medium tracking-wider text-subtle-foreground uppercase">
              Starter
            </div>
            <StarterCard
              starters={encounterDB.starters}
              run={run}
              nameToId={nameToId}
              onChange={(starter) => onChange({ ...run, starter })}
            />
          </div>

          <div>
            <div className="mb-1 text-[11px] font-medium tracking-wider text-subtle-foreground uppercase">
              Playing as
            </div>
            <div className="flex gap-0.5 rounded-lg bg-background/60 p-0.5 ring-1 ring-border">
              {(
                [
                  { id: "Male", label: "Boy", rival: "Dawn" },
                  { id: "Female", label: "Girl", rival: "Lucas" },
                ] as const
              ).map((p) => (
                <SegmentButton
                  key={p.id}
                  active={run.player === p.id}
                  activeClass="bg-primary/15 text-primary ring-primary/30"
                  title={`You meet ${p.rival} on Route 202`}
                  onClick={() => onChange({ ...run, player: run.player === p.id ? "" : p.id })}
                >
                  {p.label}
                </SegmentButton>
              ))}
            </div>
          </div>

          <RunSummary
            run={run}
            total={locations.length}
            canStartOver={box !== null}
            onNewRun={onNewRun}
          />
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-6xl flex-col gap-1.5 px-4 py-3">
          <div className="flex items-center gap-2 pb-1">
            <div className="flex h-8 flex-1 items-center gap-2 rounded-lg border border-input bg-input/30 px-2 focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50">
              <Search className="size-3.5 text-subtle-foreground" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search a location or a Pokémon"
                className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-subtle-foreground"
              />
            </div>
            <Button
              variant={canCatchOnly ? "secondary" : "ghost"}
              size="sm"
              aria-pressed={canCatchOnly}
              title="Unused locations with at least one Pokémon you can still catch"
              onClick={() => setCanCatchOnly(!canCatchOnly)}
            >
              Can still catch
            </Button>
          </div>

          {shown.map(([name, tables]) => (
            <LocationRow
              key={name}
              name={name}
              tables={tables}
              encounter={run.encounters[name]}
              nameToId={nameToId}
              holders={holders}
              lineOf={lineOf}
              onChange={(encounter) => setEncounter(name, encounter)}
            />
          ))}
          {shown.length === 0 && (
            <p className="py-8 text-center text-sm text-subtle-foreground">No locations match.</p>
          )}
        </div>
      </div>
    </div>
  );
}
