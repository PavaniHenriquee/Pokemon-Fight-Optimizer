import { Fragment, useState } from "react";
import {
  ChevronUp,
  HeartPulse,
  Lock,
  Moon,
  RotateCcw,
  Search,
  Skull,
  Sun,
  Sunrise,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { displayName, typeColor } from "@/lib/format";
import {
  boxEntryOf,
  catchDraft,
  catchState,
  countNew,
  encounterLevel,
  lineHolders,
  makeLockOf,
  newSpecies,
  shownRates,
  starterLocked,
  withRow,
  type LineHolder,
  type LineOf,
  type LockOf,
} from "@/lib/nuzlocke";
import {
  battleSprite,
  frontStatic,
  pokIcon,
  trainerSprite,
} from "@/lib/sprites";
import type {
  BoxEntry,
  EncounterDB,
  EncounterStatus,
  EncounterTable,
  ItemLocationDB,
  NuzlockeEncounter,
  NuzlockeRun,
  PokemonData,
} from "../types";
import BoxEditor from "./BoxEditor";
import ItemTracker from "./ItemTracker";
import { Button } from "./ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "./ui/tooltip";
import { Sprite } from "./common/Sprite";

const PLAYERS = [
  { id: "Male", label: "Boy", sprite: "lucas-gen4pt", rival: "Dawn" },
  { id: "Female", label: "Girl", sprite: "dawn-gen4pt", rival: "Lucas" },
] as const;

const SUB_TABS = [
  { id: "pokemon", label: "Pokémon" },
  { id: "items", label: "Items" },
] as const;
type SubTab = (typeof SUB_TABS)[number]["id"];

const STARTER_LEVEL = 5; // Sandgem Town's briefcase table
const OPEN_ICONS = 4; // Pokémon shown on the card of an open location
// The sheet's three rates for grass, caves and the ground
const TIMES = [
  { label: "Morning", Icon: Sunrise },
  { label: "Day", Icon: Sun },
  { label: "Night", Icon: Moon },
];

const tableLabel = (table: EncounterTable) =>
  [table.area, table.method].filter(Boolean).join(" · ");

// A soft glow in the Pokémon's type behind its sprite
const typeGlow = (type: string | undefined) =>
  `radial-gradient(ellipse 85% 60% at 50% 45%, color-mix(in oklab, ${typeColor(type)} 24%, transparent), transparent 75%), var(--card)`;

// What the popup is open on. A row is a new catch for that place (where: null is the starter).
interface Popup {
  entry: BoxEntry | null;
  draft: Omit<BoxEntry, "id">;
  row?: { where: string | null; species: string };
}

// ─── Hover buttons on a Pokémon: it died, it's back, clear ─────────────────────

function RowActions({
  status,
  locked,
  onStatus,
  onClear,
}: {
  status: EncounterStatus;
  locked?: boolean; // it can't be cleared
  onStatus: (status: EncounterStatus) => void;
  onClear: () => void;
}) {
  const [confirming, setConfirming] = useState<"dead" | "clear" | null>(null);
  return (
    <div
      onMouseLeave={() => setConfirming(null)}
      className={cn(
        "absolute top-1 right-1 z-10 flex gap-0.5 rounded-md bg-card/85 transition-opacity group-hover:opacity-100 focus-within:opacity-100",
        !confirming && "opacity-0",
      )}
    >
      {status === "caught" && confirming !== "clear" && (
        <Button
          variant={confirming === "dead" ? "destructive" : "ghost"}
          size={confirming === "dead" ? "xs" : "icon-xs"}
          title={
            confirming === "dead"
              ? "Click again to move it to the death box"
              : "It died"
          }
          aria-label="It died"
          onClick={() => {
            setConfirming(confirming === "dead" ? null : "dead");
            if (confirming === "dead") onStatus("dead");
          }}
        >
          <Skull />
          {confirming === "dead" && "It died?"}
        </Button>
      )}
      {status === "dead" && confirming !== "clear" && (
        <Button
          variant="ghost"
          size="icon-xs"
          title="Revive: back to the PC box"
          aria-label="Revive"
          onClick={() => onStatus("caught")}
        >
          <HeartPulse />
        </Button>
      )}
      {confirming !== "dead" && !locked && (
        <Button
          variant={confirming === "clear" ? "destructive" : "ghost"}
          size={confirming === "clear" ? "xs" : "icon-xs"}
          title={
            status === "missed"
              ? "Clear this encounter"
              : confirming === "clear"
                ? "Click again: it leaves the tracker, the box and the party"
                : "Clear: it leaves the tracker, the box and the party"
          }
          aria-label="Clear"
          onClick={() => {
            if (status === "missed" || confirming === "clear") onClear();
            else setConfirming("clear");
          }}
        >
          <X />
          {confirming === "clear" && "Remove?"}
        </Button>
      )}
    </div>
  );
}

// ─── Top: you, your starter, the run ──────────────────────────────────────────

function PlayerPicker({
  player,
  locked,
  onChange,
}: {
  player: NuzlockeRun["player"];
  locked: boolean;
  onChange: (player: NuzlockeRun["player"]) => void;
}) {
  const frozen = locked && !!player; // a run with no gender yet can still choose one
  return (
    <div className="flex gap-1">
      {PLAYERS.map((p) => {
        const chosen = player === p.id;
        return (
          <button
            key={p.id}
            type="button"
            aria-pressed={chosen}
            aria-label={p.label}
            disabled={frozen}
            title={
              frozen
                ? "Your choice is locked: you've caught another Pokémon"
                : `${p.label}: you meet ${p.rival} on Route 202`
            }
            onClick={() => onChange(chosen ? "" : p.id)}
            className={cn(
              "flex h-36 w-24 items-center justify-center overflow-hidden rounded-xl ring-1 transition-all",
              !frozen && "cursor-pointer",
              chosen ? "bg-primary/15 ring-primary/50" : "ring-transparent",
              !chosen && !frozen && "hover:bg-foreground/5",
              player && !chosen && "opacity-35 grayscale",
              player && !chosen && !frozen && "hover:opacity-70",
            )}
          >
            {/* 2× of the 80px sprite; its transparent padding may spill out of the box */}
            <Sprite
              srcs={trainerSprite(p.sprite)}
              alt={p.label}
              width={160}
              height={160}
              className="pointer-events-none max-w-none shrink-0"
            />
          </button>
        );
      })}
    </div>
  );
}

function ChosenStarter({
  encounter,
  boxEntry,
  pokemonData,
  locked,
  onOpen,
  onStatus,
  onClear,
}: {
  encounter: NuzlockeEncounter;
  boxEntry: BoxEntry | undefined;
  pokemonData: PokemonData;
  locked: boolean;
  onOpen: () => void;
  onStatus: (status: EncounterStatus) => void;
  onClear: () => void;
}) {
  const species = boxEntry?.name ?? encounter.species; // it may have evolved
  const id = pokemonData.nameToId[species];
  const dead = encounter.status === "dead";
  const body = (
    <>
      <span className="relative flex h-[136px] w-full items-end justify-center pb-3">
        <span
          className="absolute bottom-1 left-1/2 h-8 w-36 -translate-x-1/2 rounded-[50%]"
          style={{
            background:
              "radial-gradient(closest-side, oklch(1 0 0 / 14%), oklch(1 0 0 / 5%) 65%, transparent)",
          }}
        />
        {id && (
          <Sprite
            key={id}
            srcs={battleSprite(id, "front")}
            alt={species}
            className={cn(
              "relative drop-shadow-[0_6px_10px_rgb(0_0_0/45%)]",
              dead && "grayscale",
            )}
            style={{ transform: "scale(2)", transformOrigin: "bottom center" }}
          />
        )}
      </span>
      <span className="flex items-center gap-1.5 text-lg font-semibold tracking-tight">
        {dead && <Skull className="size-4 text-bad" />}
        {displayName(species)}
      </span>
      {boxEntry ? (
        <span className="num text-xs text-subtle-foreground">
          Lv {boxEntry.level}
        </span>
      ) : (
        <span className="text-xs text-warn">Not in your box</span>
      )}
    </>
  );
  return (
    <div
      className="group relative w-52 rounded-2xl pb-2 ring-1 ring-foreground/10"
      style={{
        background: typeGlow(
          dead ? undefined : pokemonData.pokemonTypes?.[species]?.[0],
        ),
      }}
    >
      {dead ? (
        <div className="flex flex-col items-center">{body}</div>
      ) : (
        <button
          type="button"
          onClick={onOpen}
          title={boxEntry ? "Edit it" : "Store it in the box"}
          className="flex w-full cursor-pointer flex-col items-center"
        >
          {body}
        </button>
      )}
      <RowActions
        status={encounter.status}
        locked={locked}
        onStatus={onStatus}
        onClear={onClear}
      />
    </div>
  );
}

function StarterPicker({
  starters,
  run,
  box,
  pokemonData,
  holders,
  lineOf,
  onPick,
  onOpen,
  onStatus,
  onClear,
}: {
  starters: string[];
  run: NuzlockeRun;
  box: BoxEntry[];
  pokemonData: PokemonData;
  holders: Map<string, LineHolder>;
  lineOf: LineOf;
  onPick: (species: string) => void;
  onOpen: () => void;
  onStatus: (status: EncounterStatus) => void;
  onClear: () => void;
}) {
  const { starter } = run;
  const locked = starterLocked(run, box, lineOf);
  return (
    <div className="flex items-center gap-1">
      {starters.map((name) => {
        if (starter.species === name) {
          return (
            <ChosenStarter
              key={name}
              encounter={starter}
              boxEntry={boxEntryOf(box, lineOf, name)}
              pokemonData={pokemonData}
              locked={locked}
              onOpen={onOpen}
              onStatus={onStatus}
              onClear={onClear}
            />
          );
        }
        const id = pokemonData.nameToId[name];
        const passed = !!starter.species;
        const blocked = catchState(name, "", holders, lineOf) === "blocked";
        return (
          <button
            key={name}
            type="button"
            disabled={passed || blocked}
            title={
              passed
                ? locked
                  ? "Your starter is locked: you've caught another Pokémon"
                  : "Clear your starter to change it"
                : blocked
                  ? `Already caught: ${holderText(holders.get(lineOf(name)))}`
                  : `Choose ${displayName(name)}`
            }
            onClick={() => onPick(name)}
            className={cn(
              "flex items-center justify-center overflow-hidden rounded-2xl transition-all",
              passed ? "size-16 opacity-35 grayscale" : "size-36",
              !passed && !blocked && "cursor-pointer hover:bg-foreground/5",
              blocked && !passed && "cursor-not-allowed opacity-35 grayscale",
            )}
          >
            {id && (
              <Sprite
                srcs={frontStatic(id)}
                alt={name}
                width={passed ? 96 : 192}
                height={passed ? 96 : 192}
                className="pointer-events-none max-w-none shrink-0"
              />
            )}
          </button>
        );
      })}
    </div>
  );
}

function RunSummary({
  run,
  onNewRun,
}: {
  run: NuzlockeRun;
  onNewRun: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const entries = [
    ...Object.values(run.encounters),
    ...(run.starter.species ? [run.starter] : []),
  ];
  const count = (status: EncounterStatus) =>
    entries.filter((e) => e.status === status).length;
  return (
    <div className="ml-auto flex flex-col items-end gap-2 self-center">
      <div className="num flex items-baseline gap-3 text-sm text-muted-foreground">
        <span>
          <span className="text-lg font-semibold text-good">
            {count("caught")}
          </span>{" "}
          alive
        </span>
        <span>
          <span className="text-lg font-semibold text-bad">
            {count("dead")}
          </span>{" "}
          dead
        </span>
        <span>
          <span className="text-lg font-semibold text-warn">
            {count("missed")}
          </span>{" "}
          missed
        </span>
      </div>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant={confirming ? "destructive" : "ghost"}
            size="sm"
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
        </TooltipTrigger>
        <TooltipContent>
          {confirming
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

// What the locked tables with something new still need: ["the Good Rod", "HM03 Surf"]
function lockedNeeds(
  tables: EncounterTable[],
  lockOf: LockOf,
  holders: Map<string, LineHolder>,
  lineOf: LineOf,
): string[] {
  const needs = tables
    .filter((t) => lockOf(t) && countNew([t], holders, lineOf) > 0)
    .map(lockOf);
  return [...new Set(needs)];
}

function LocationTables({
  tables,
  nameToId,
  ownSpecies,
  holders,
  lineOf,
  lockOf,
  onPick,
}: {
  tables: EncounterTable[];
  nameToId: Record<string, number>;
  ownSpecies: string;
  holders: Map<string, LineHolder>;
  lineOf: LineOf;
  lockOf: LockOf;
  onPick: (species: string, level: number) => void;
}) {
  const counts = (species: string) =>
    catchState(species, ownSpecies, holders, lineOf) === "new";
  return (
    <div className="grid items-start gap-x-4 gap-y-3 border-t p-3 sm:grid-cols-2 xl:grid-cols-3">
      {tables.map((table) => {
        const rates = shownRates(table, counts);
        const columns = Math.max(0, ...rates.map((r) => r.length));
        const lock = lockOf(table); // still pickable: the item may just not be ticked yet
        return (
          <div
            key={tableLabel(table)}
            className={cn(
              "grid min-w-0 items-center gap-x-1 gap-y-0.5",
              lock && "opacity-50",
            )}
            style={{
              gridTemplateColumns: `minmax(0,1fr) repeat(${columns}, 2.5rem)`,
            }}
          >
            <div
              className="mb-1 flex min-w-0 items-center gap-1 text-[11px] font-medium text-subtle-foreground"
              title={
                lock ? `${tableLabel(table)}: needs ${lock}` : tableLabel(table)
              }
            >
              {lock && <Lock className="size-3 shrink-0 text-warn" />}
              <span className="truncate">{tableLabel(table)}</span>
            </div>
            {columns === TIMES.length
              ? TIMES.map(({ label, Icon }) => (
                  <span
                    key={label}
                    title={label}
                    aria-label={label}
                    className="mb-1 flex justify-end pr-1 text-subtle-foreground"
                  >
                    <Icon className="size-3.5" />
                  </span>
                ))
              : Array.from({ length: columns }, (_, i) => (
                  <span key={i} className="mb-1" />
                ))}
            {table.mons.map((mon, m) => {
              const state = catchState(mon.name, ownSpecies, holders, lineOf);
              const holder = holderText(holders.get(lineOf(mon.name)));
              const content = (
                <>
                  {nameToId[mon.name] && (
                    <Sprite
                      srcs={pokIcon(nameToId[mon.name])}
                      alt={mon.name}
                      width={40}
                      height={30}
                      className={cn(
                        "shrink-0",
                        state === "blocked" && "grayscale",
                      )}
                    />
                  )}
                  <span
                    className={cn(
                      "truncate",
                      state === "blocked" && "line-through",
                    )}
                  >
                    {displayName(mon.name)}
                  </span>
                  {mon.level && (
                    <span className="num ml-auto shrink-0 text-subtle-foreground">
                      {mon.level}
                    </span>
                  )}
                </>
              );
              return (
                <Fragment key={mon.name}>
                  {/* A span, not a disabled button: its tooltip has to say what took the line */}
                  {state === "blocked" ? (
                    <span
                      title={`Already caught: ${holder}`}
                      className="flex h-8 min-w-0 cursor-not-allowed items-center gap-1 rounded-lg pr-2.5 text-xs opacity-40"
                    >
                      {content}
                    </span>
                  ) : (
                    <button
                      type="button"
                      onClick={() =>
                        onPick(
                          mon.name,
                          encounterLevel(mon.level, table.method),
                        )
                      }
                      title={
                        state === "boxed"
                          ? `Log it here, it's your ${holder}`
                          : `Pick ${displayName(mon.name)}`
                      }
                      className={cn(
                        "flex h-8 min-w-0 cursor-pointer items-center gap-1 rounded-lg pr-2.5 text-left text-xs transition-colors hover:bg-foreground/10",
                        state === "boxed"
                          ? "bg-foreground/5 ring-1 ring-info/40 ring-inset"
                          : "bg-foreground/5",
                      )}
                    >
                      {content}
                    </button>
                  )}
                  {Array.from({ length: columns }, (_, i) => (
                    <RateCell
                      key={i}
                      shown={rates[m][i]}
                      sheet={mon.rates?.[i]}
                      when={
                        columns === TIMES.length ? TIMES[i].label : undefined
                      }
                    />
                  ))}
                </Fragment>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}

// A Pokémon's chance in one column. "—": it can't be met then, or the species clause skips it.
function RateCell({
  shown,
  sheet,
  when,
}: {
  shown: number | undefined;
  sheet: number | undefined;
  when?: string;
}) {
  if (shown === undefined || sheet === undefined) return <span />;
  const text = shown === 0 ? "—" : shown < 1 ? "<1%" : `${Math.round(shown)}%`;
  const time = when ? ` at ${when.toLowerCase()}` : "";
  return (
    <span
      title={
        shown === 0
          ? sheet === 0
            ? `Not met${time}`
            : `Skipped by the species clause (${sheet}%)`
          : `${text}${time}${Math.round(shown) === sheet ? "" : ` (${sheet}%)`}`
      }
      className={cn(
        "num pr-1 text-right text-xs",
        shown === 0 ? "text-subtle-foreground/60" : "text-muted-foreground",
      )}
    >
      {text}
    </span>
  );
}

// A caught or dead Pokémon: the sprite is the card
function CaughtCard({
  name,
  encounter,
  boxEntry,
  pokemonData,
  onOpen,
  onStatus,
  onClear,
}: {
  name: string;
  encounter: NuzlockeEncounter;
  boxEntry: BoxEntry | undefined;
  pokemonData: PokemonData;
  onOpen: () => void;
  onStatus: (status: EncounterStatus) => void;
  onClear: () => void;
}) {
  const species = boxEntry?.name ?? encounter.species; // it may have evolved
  const id = pokemonData.nameToId[species];
  const dead = encounter.status === "dead";
  const body = (
    <>
      {/* 2× of the 96px sprite; its transparent padding may spill out of the box */}
      <span className="flex h-[124px] w-full items-center justify-center">
        {id && (
          <Sprite
            srcs={frontStatic(id)}
            alt={species}
            width={192}
            height={192}
            className={cn(
              "pointer-events-none max-w-none shrink-0",
              dead && "opacity-60 grayscale",
            )}
          />
        )}
      </span>
      <span className="relative flex max-w-full items-center gap-1 px-2 text-sm font-semibold tracking-tight [text-shadow:0_1px_3px_rgb(0_0_0/80%)]">
        {dead && <Skull className="size-3.5 shrink-0 text-bad" />}
        <span className="truncate">{displayName(species)}</span>
      </span>
      {boxEntry ? (
        <span className="num relative text-[11px] text-subtle-foreground">
          Lv {boxEntry.level}
        </span>
      ) : (
        <span className="relative text-[11px] text-warn">Not in your box</span>
      )}
    </>
  );
  return (
    <div
      className="group relative row-span-2 overflow-hidden rounded-xl border pb-2 transition-colors hover:border-foreground/20"
      style={{
        background: typeGlow(
          dead ? undefined : pokemonData.pokemonTypes?.[species]?.[0],
        ),
      }}
    >
      <div
        className="relative z-[1] truncate px-2.5 pt-1.5 text-[11px] font-medium text-muted-foreground [text-shadow:0_1px_3px_rgb(0_0_0/80%)]"
        title={name}
      >
        {name}
      </div>
      {dead ? (
        <div className="flex flex-col items-center">{body}</div>
      ) : (
        <button
          type="button"
          onClick={onOpen}
          title={boxEntry ? "Edit it" : "Store it in the box"}
          className="flex w-full cursor-pointer flex-col items-center"
        >
          {body}
        </button>
      )}
      <RowActions
        status={encounter.status}
        onStatus={onStatus}
        onClear={onClear}
      />
    </div>
  );
}

// A location with nothing caught yet, or a missed encounter
function OpenCard({
  name,
  tables,
  needs,
  encounter,
  nameToId,
  holders,
  lineOf,
  onExpand,
  onClear,
}: {
  name: string;
  tables: EncounterTable[]; // the unlocked ones
  needs: string[]; // what the locked ones with something new need
  encounter: NuzlockeEncounter | undefined;
  nameToId: Record<string, number>;
  holders: Map<string, LineHolder>;
  lineOf: LineOf;
  onExpand: () => void;
  onClear: () => void;
}) {
  const species = newSpecies(tables, holders, lineOf);
  const missed = encounter?.status === "missed";
  const missedId = encounter?.species ? nameToId[encounter.species] : undefined;
  return (
    <div className="group relative rounded-xl border border-dashed bg-card/40 transition-colors hover:border-foreground/20 hover:bg-card">
      <button
        type="button"
        onClick={onExpand}
        title={missed ? "Pick what it was" : "Show what's here"}
        className="flex h-full w-full cursor-pointer flex-col p-2.5 text-left"
      >
        <span className="truncate text-[13px] font-medium" title={name}>
          {name}
        </span>
        {missed ? (
          <span className="mt-1.5 flex h-6 items-center gap-1">
            {missedId && (
              <Sprite
                srcs={pokIcon(missedId)}
                alt={encounter?.species}
                title={encounter?.species && displayName(encounter.species)}
                width={32}
                height={24}
                className="opacity-50 grayscale"
              />
            )}
            <span className="text-xs font-medium text-warn">Missed</span>
          </span>
        ) : (
          <>
            <span className="mt-1.5 flex items-center gap-x-0.5 opacity-60 transition-opacity group-hover:opacity-100">
              {species
                .slice(0, OPEN_ICONS)
                .map(
                  (mon) =>
                    nameToId[mon] && (
                      <Sprite
                        key={mon}
                        srcs={pokIcon(nameToId[mon])}
                        alt={mon}
                        title={displayName(mon)}
                        width={32}
                        height={24}
                      />
                    ),
                )}
              {species.length > OPEN_ICONS && (
                <span className="num pl-1 text-[11px] text-subtle-foreground">
                  +{species.length - OPEN_ICONS}
                </span>
              )}
            </span>
            {species.length === 0 &&
              (needs.length ? (
                <span
                  className="mt-auto flex min-w-0 items-center gap-1 text-[11px] text-subtle-foreground"
                  title={`Needs ${needs.join(", ")}`}
                >
                  <Lock className="size-3 shrink-0 text-warn" />
                  <span className="truncate">Needs {needs.join(", ")}</span>
                </span>
              ) : (
                <span className="mt-auto text-[11px] text-warn">
                  Nothing new
                </span>
              ))}
          </>
        )}
      </button>
      {missed && (
        <RowActions status="missed" onStatus={() => {}} onClear={onClear} />
      )}
    </div>
  );
}

// An open location, showing what can be met there
function ExpandedCard({
  name,
  tables,
  encounter,
  nameToId,
  holders,
  lineOf,
  lockOf,
  onCollapse,
  onPick,
  onMissed,
  onClear,
}: {
  name: string;
  tables: EncounterTable[];
  encounter: NuzlockeEncounter | undefined;
  nameToId: Record<string, number>;
  holders: Map<string, LineHolder>;
  lineOf: LineOf;
  lockOf: LockOf;
  onCollapse: () => void;
  onPick: (species: string, level: number) => void;
  onMissed: () => void;
  onClear: () => void;
}) {
  const missed = encounter?.status === "missed";
  return (
    <div className="col-span-full overflow-hidden rounded-xl border bg-card">
      <div className="flex items-center gap-3 px-3 py-2">
        <button
          type="button"
          onClick={onCollapse}
          title="Close"
          className="flex min-w-0 cursor-pointer items-center gap-1.5 text-sm font-semibold"
        >
          <ChevronUp className="size-4 shrink-0 text-subtle-foreground" />
          <span className="truncate">{name}</span>
        </button>
        {missed && (
          <span className="text-xs text-warn">
            Missed. Pick what it was, if you saw it.
          </span>
        )}
        <div className="ml-auto shrink-0">
          {missed ? (
            <Button
              variant="ghost"
              size="xs"
              onClick={onClear}
              title="It wasn't missed after all"
            >
              <X />
              Undo missed
            </Button>
          ) : (
            <Button
              variant="outline"
              size="xs"
              onClick={onMissed}
              title="The encounter is used up: it fainted or fled"
            >
              Missed it
            </Button>
          )}
        </div>
      </div>
      <LocationTables
        tables={tables}
        nameToId={nameToId}
        ownSpecies={encounter?.species ?? ""}
        holders={holders}
        lineOf={lineOf}
        lockOf={lockOf}
        onPick={onPick}
      />
    </div>
  );
}

// ─── Exported: the tab ────────────────────────────────────────────────────────

export default function TrackerView({
  run,
  encounterDB,
  itemDB,
  pokemonData,
  box,
  lineOf,
  error,
  onRetry,
  onChange,
  onStore,
  onClearRow,
  onNewRun,
}: {
  run: NuzlockeRun | null;
  encounterDB: EncounterDB | null;
  itemDB: ItemLocationDB | null; // only the Items tab waits for it
  pokemonData: PokemonData | null;
  box: BoxEntry[] | null;
  lineOf: LineOf;
  error: string | null;
  onRetry: () => void;
  onChange: (run: NuzlockeRun) => void;
  onStore: (entry: BoxEntry, run?: NuzlockeRun) => void;
  onClearRow: (run: NuzlockeRun, entry?: BoxEntry) => void;
  onNewRun: () => void;
}) {
  const [query, setQuery] = useState("");
  const [canCatchOnly, setCanCatchOnly] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [popup, setPopup] = useState<Popup | null>(null);
  const [tab, setTab] = useState<SubTab>("pokemon");

  // Nothing here may save until the real run and box have loaded: an empty one would replace them
  if (!run || !encounterDB || !pokemonData || !box) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
        <p className="max-w-md text-sm text-muted-foreground">
          {error
            ? `Couldn't load the Nuzlocke run: ${error}`
            : "Loading the Nuzlocke run…"}
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
  const holders = lineHolders(run, box, lineOf);
  const lockOf = makeLockOf(itemDB, run);
  const unlocked = (tables: EncounterTable[]) =>
    tables.filter((t) => !lockOf(t));
  const q = query.trim().toLowerCase();
  // A search also finds where a Pokémon lives
  const shown = locations.filter(([name, tables]) => {
    if (
      canCatchOnly &&
      (run.encounters[name] ||
        countNew(unlocked(tables), holders, lineOf) === 0)
    )
      return false;
    if (!q || name.toLowerCase().includes(q)) return true;
    return tables.some((t) =>
      t.mons.some((m) => displayName(m.name).toLowerCase().includes(q)),
    );
  });

  // Picking a Pokémon: the popup, unless there's nothing to store
  function pick(where: string | null, species: string, level: number) {
    if (!run || !pokemonData) return;
    const encounter = where === null ? undefined : run.encounters[where];
    const holder = holders.get(lineOf(species));
    if (encounter?.status === "missed") {
      onChange(withRow(run, where, { ...encounter, species }));
      setExpanded(null);
    } else if (holder?.boxOnly) {
      // Already in the box: it only gets logged here. A line in the death box already died.
      onChange(
        withRow(run, where, {
          species,
          status: holder.where === "Death box" ? "dead" : "caught",
        }),
      );
      setExpanded(null);
    } else {
      setPopup({
        entry: null,
        draft: catchDraft(pokemonData, species, level),
        row: { where, species },
      });
    }
  }

  // Clicking a caught Pokémon: its box entry, or storing it if an older run never did
  function openRow(
    where: string | null,
    encounter: NuzlockeEncounter,
    tables: EncounterTable[],
  ) {
    if (!box || !pokemonData) return;
    const entry = boxEntryOf(box, lineOf, encounter.species);
    if (entry) {
      setPopup({
        entry,
        draft: { ...entry, moves: [...entry.moves], ivs: { ...entry.ivs } },
      });
      return;
    }
    const { species } = encounter;
    const table = tables.find((t) => t.mons.some((m) => m.name === species));
    const mon = table?.mons.find((m) => m.name === species);
    const level =
      table && mon ? encounterLevel(mon.level, table.method) : STARTER_LEVEL;
    setPopup({
      entry: null,
      draft: catchDraft(pokemonData, species, level),
      row: { where, species },
    });
  }

  function clearRow(
    where: string | null,
    encounter: NuzlockeEncounter | undefined,
  ) {
    if (!run || !box) return;
    // A missed one never reached the box, what's there of its line was caught somewhere else
    const entry =
      encounter && encounter.status !== "missed"
        ? boxEntryOf(box, lineOf, encounter.species)
        : undefined;
    onClearRow(withRow(run, where, null), entry);
  }

  const subTabs = (
    <nav className="flex shrink-0 rounded-lg bg-card/60 p-0.5 ring-1 ring-border">
      {SUB_TABS.map((t) => (
        <button
          key={t.id}
          type="button"
          onClick={() => setTab(t.id)}
          aria-pressed={tab === t.id}
          className={cn(
            "h-7 cursor-pointer rounded-md px-3.5 text-xs font-medium transition-colors",
            tab === t.id
              ? "bg-elevated text-foreground shadow-sm ring-1 ring-foreground/10"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {t.label}
        </button>
      ))}
    </nav>
  );

  return (
    <div className="h-full min-h-0 overflow-y-auto">
      <div className="border-b bg-card/40">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-8 gap-y-3 px-4 py-4">
          <PlayerPicker
            player={run.player}
            locked={starterLocked(run, box, lineOf)}
            onChange={(player) => onChange({ ...run, player })}
          />
          <StarterPicker
            starters={encounterDB.starters}
            run={run}
            box={box}
            pokemonData={pokemonData}
            holders={holders}
            lineOf={lineOf}
            onPick={(species) => pick(null, species, STARTER_LEVEL)}
            onOpen={() => openRow(null, run.starter, [])}
            onStatus={(status) =>
              onChange(withRow(run, null, { ...run.starter, status }))
            }
            onClear={() => clearRow(null, run.starter)}
          />
          <RunSummary run={run} onNewRun={onNewRun} />
        </div>
      </div>

      {/* Hidden, not unmounted, so the search and the open card are still there on the way back */}
      <div
        className={cn(
          "mx-auto max-w-6xl px-4 pb-6",
          tab !== "pokemon" && "hidden",
        )}
      >
        <div className="sticky top-0 z-20 flex items-center gap-2 bg-background py-3">
          {subTabs}
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

        {/* dense: open cards fill in around the taller caught ones, an expanded card opens under its row */}
        <div className="grid grid-flow-dense auto-rows-[minmax(90px,auto)] grid-cols-[repeat(auto-fill,minmax(168px,1fr))] gap-2">
          {shown.map(([name, tables]) => {
            const encounter = run.encounters[name];
            if (encounter && encounter.status !== "missed") {
              return (
                <CaughtCard
                  key={name}
                  name={name}
                  encounter={encounter}
                  boxEntry={boxEntryOf(box, lineOf, encounter.species)}
                  pokemonData={pokemonData}
                  onOpen={() => openRow(name, encounter, tables)}
                  onStatus={(status) =>
                    onChange(withRow(run, name, { ...encounter, status }))
                  }
                  onClear={() => clearRow(name, encounter)}
                />
              );
            }
            if (expanded === name) {
              return (
                <ExpandedCard
                  key={name}
                  name={name}
                  tables={tables}
                  encounter={encounter}
                  nameToId={nameToId}
                  holders={holders}
                  lineOf={lineOf}
                  lockOf={lockOf}
                  onCollapse={() => setExpanded(null)}
                  onPick={(species, level) => pick(name, species, level)}
                  onMissed={() =>
                    onChange(
                      withRow(run, name, { species: "", status: "missed" }),
                    )
                  }
                  onClear={() => clearRow(name, encounter)}
                />
              );
            }
            return (
              <OpenCard
                key={name}
                name={name}
                tables={unlocked(tables)}
                needs={lockedNeeds(tables, lockOf, holders, lineOf)}
                encounter={encounter}
                nameToId={nameToId}
                holders={holders}
                lineOf={lineOf}
                onExpand={() => setExpanded(name)}
                onClear={() => clearRow(name, encounter)}
              />
            );
          })}
        </div>
        {shown.length === 0 && (
          <p className="py-8 text-center text-sm text-subtle-foreground">
            No locations match.
          </p>
        )}
      </div>

      <div className={cn(tab !== "items" && "hidden")}>
        <ItemTracker
          itemDB={itemDB}
          run={run}
          error={error}
          tabs={subTabs}
          onRetry={onRetry}
          onChange={onChange}
        />
      </div>

      {popup && (
        <BoxEditor
          entry={popup.entry}
          draft={popup.draft}
          pokemonData={pokemonData}
          catching={!!popup.row}
          evolutions={encounterDB.evolutions}
          onSave={(entry) => {
            const { row } = popup;
            onStore(
              entry,
              row &&
                withRow(run, row.where, {
                  species: row.species,
                  status: "caught",
                }),
            );
            setPopup(null);
            setExpanded(null);
          }}
          onCancel={() => setPopup(null)}
        />
      )}
    </div>
  );
}
