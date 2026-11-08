import { useCallback, useState, useEffect } from "react";
import {
  ChevronLeft,
  ChevronRight,
  MapPin,
  Plus,
  Undo2,
  Users,
} from "lucide-react";
import BoxView from "./BoxView";
import type {
  BoxEntry,
  Evolution,
  NuzlockeRun,
  PokemonConfig,
  PokemonData,
  TrainerDB,
} from "../types";
import { MyTeamSlot, NameSelect, OpponentSlot } from "./PokemonSlots";
import { OPPONENT_MIN_HEIGHT, teamCardFit } from "@/lib/cardFit";
import {
  boxAfterPartyEdit,
  partyAfterEdit,
  trainerVisible,
} from "@/lib/nuzlocke";
import { displayName } from "@/lib/format";
import { trainerSprite } from "@/lib/sprites";
import type { BoxState } from "@/lib/useBox";
import { Sprite } from "./common/Sprite";
import { ItemIcon } from "./common/ItemIcon";
import { Chip } from "./common/Badges";
import { Button } from "./ui/button";

function PanelTitle({
  children,
  count,
}: {
  children: React.ReactNode;
  count?: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <h2 className="text-[11px] font-medium tracking-wider text-subtle-foreground uppercase">
        {children}
      </h2>
      {count && (
        <span className="num text-[11px] text-subtle-foreground/70">
          {count}
        </span>
      )}
    </div>
  );
}

// An element's content size, kept up to date. Hidden (another tab) it reads 0 × 0.
function useSize() {
  const [size, setSize] = useState({ width: 0, height: 0 });
  const measure = useCallback((element: HTMLElement | null) => {
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setSize((prev) =>
        prev.width === width && prev.height === height
          ? prev
          : { width, height },
      );
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return [size, measure] as const;
}

// ─── Party layout: the fewer Pokémon, the bigger their cards ──────────────────

const CARD_GAP = 12;
const MIN_CARD_WIDTH = 280;
const MIN_CARD_HEIGHT = 250;
const PARTY_ROWS = [[], [1], [2], [3], [2, 2], [2, 3], [3, 3]]; // cards per row, by party size

// A window too narrow for that shape gets as many per row as fit
function partyRows(count: number, width: number): number[] {
  const fit = Math.max(
    1,
    Math.floor((width + CARD_GAP) / (MIN_CARD_WIDTH + CARD_GAP)),
  );
  const rows = PARTY_ROWS[count];
  if (rows.every((perRow) => perRow <= fit)) return rows;
  const wrapped: number[] = [];
  for (let left = count; left > 0; left -= fit)
    wrapped.push(Math.min(left, fit));
  return wrapped;
}

function PartyGrid({
  team,
  pokemonData,
  emptyHint,
  onChange,
  onRemove,
  onMakeLead,
}: {
  team: PokemonConfig[];
  pokemonData: PokemonData;
  emptyHint: string;
  onChange: (idx: number, updated: PokemonConfig) => void;
  onRemove: (idx: number) => void;
  onMakeLead: (idx: number) => void;
}) {
  const [size, measure] = useSize();
  const rows = partyRows(team.length, size.width);
  const cardHeight = Math.max(
    MIN_CARD_HEIGHT,
    (size.height - CARD_GAP * (rows.length - 1)) / rows.length,
  );
  const perRowOf = rows.flatMap((perRow) => Array<number>(perRow).fill(perRow)); // by party slot

  return (
    <div ref={measure} className="min-h-0 flex-1 overflow-y-auto p-4">
      {team.length === 0 ? (
        <div className="flex h-full flex-col items-center justify-center gap-3 rounded-xl border border-dashed p-6 text-center">
          <div className="flex size-14 items-center justify-center rounded-full bg-foreground/5">
            <Plus className="size-6 text-muted-foreground" />
          </div>
          <p className="text-lg text-muted-foreground">Build your team</p>
          <p className="text-sm text-subtle-foreground">{emptyHint}</p>
        </div>
      ) : (
        <div
          className="grid min-h-full grid-cols-6"
          style={{
            gap: CARD_GAP,
            gridTemplateRows: `repeat(${rows.length}, minmax(${MIN_CARD_HEIGHT}px, 1fr))`,
          }}
        >
          {team.map((config, idx) => {
            const perRow = perRowOf[idx];
            const width = (size.width - CARD_GAP * (perRow - 1)) / perRow;
            return (
              <div
                key={idx}
                className="min-w-0"
                style={{ gridColumn: `span ${6 / perRow}` }}
              >
                <MyTeamSlot
                  config={config}
                  nameToId={pokemonData.nameToId}
                  onChange={(updated) => onChange(idx, updated)}
                  onRemove={() => onRemove(idx)}
                  onMakeLead={() => onMakeLead(idx)}
                  isLead={idx === 0}
                  fit={teamCardFit(width, cardHeight)}
                  pokemonData={pokemonData}
                />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── The box's place until the real box has loaded: nothing to edit or save ───

function BoxUnavailable({
  error,
  onRetry,
}: {
  error: string | null;
  onRetry: () => void;
}) {
  return (
    <aside className="flex min-h-0 flex-col border-r bg-card/40">
      <div className="flex h-11 shrink-0 items-center border-b px-3">
        <PanelTitle>PC Box</PanelTitle>
      </div>
      <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-3 p-4 text-center">
        <p className="text-xs break-words text-muted-foreground">
          {error
            ? `Couldn't load the box, so saving is off: ${error}`
            : "Loading the box…"}
        </p>
        {error && (
          <Button variant="outline" size="sm" onClick={onRetry}>
            Try again
          </Button>
        )}
      </div>
    </aside>
  );
}

// ─── Opponent side: trainer picker, items, read-only team ─────────────────────

function OpponentPanel({
  trainerDB,
  run,
  selectedTrainer,
  onSelectTrainer,
  team,
  locked,
  trainerItems,
  terrain,
  pokemonData,
  onAddSlot,
}: {
  trainerDB: TrainerDB;
  run: NuzlockeRun | null;
  selectedTrainer: string;
  onSelectTrainer: (trainer: string | null) => void;
  team: PokemonConfig[];
  locked: boolean;
  trainerItems: string[];
  terrain: string;
  pokemonData: PokemonData;
  onAddSlot: () => void;
}) {
  const options = Object.keys(trainerDB).filter((t) =>
    trainerVisible(trainerDB[t], run),
  );
  const position = options.indexOf(selectedTrainer); // -1 with none selected: › goes to the first
  const sprite = trainerDB[selectedTrainer]?.sprite;
  const items = trainerItems.filter(Boolean);
  const [teamSize, measureTeam] = useSize();
  const slotGap = 8;
  const slotHeight =
    (teamSize.height - slotGap * (team.length - 1)) / Math.max(1, team.length);

  return (
    <aside className="flex min-h-0 flex-col border-l bg-card/40">
      <div className="flex h-11 shrink-0 items-center border-b px-3">
        <PanelTitle count={`${team.length}/6`}>Opponent</PanelTitle>
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-3">
        {/* trainer card */}
        <div
          className="relative shrink-0 overflow-hidden rounded-xl border p-3"
          style={{
            background:
              "radial-gradient(ellipse 70% 90% at 85% 50%, oklch(0.32 0.06 250 / 45%), transparent 70%), var(--card)",
          }}
        >
          <div className="flex items-center gap-3">
            <div className="flex size-16 shrink-0 items-center justify-center roomy:size-20">
              {sprite ? (
                <Sprite
                  srcs={trainerSprite(sprite)}
                  alt={selectedTrainer}
                  width={64}
                  height={64}
                  className="roomy:size-20"
                />
              ) : (
                <Users className="size-6 text-subtle-foreground" />
              )}
            </div>
            <div className="min-w-0 flex-1">
              <div className="mb-1 flex items-center justify-between text-[11px] text-subtle-foreground">
                Trainer
                <div className="flex gap-0.5">
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    onClick={() => onSelectTrainer(options[position - 1])}
                    disabled={position <= 0}
                    title="Previous trainer"
                    aria-label="Previous trainer"
                  >
                    <ChevronLeft />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    onClick={() => onSelectTrainer(options[position + 1])}
                    disabled={position >= options.length - 1}
                    title="Next trainer"
                    aria-label="Next trainer"
                  >
                    <ChevronRight />
                  </Button>
                </div>
              </div>
              <NameSelect
                value={selectedTrainer}
                onChange={(v) => onSelectTrainer(v || null)}
                items={options}
                placeholder={options[0]}
                clearable={!!selectedTrainer}
              />
            </div>
          </div>
          {(selectedTrainer || items.length > 0) && (
            <div className="mt-3 flex flex-wrap items-center gap-1.5">
              <Chip title="Nature Power's battle terrain">
                <MapPin className="size-3" />
                <span className="capitalize">{terrain}</span>
              </Chip>
              {items.map((item, i) => (
                <Chip key={i}>
                  <ItemIcon name={item} size={16} />
                  {item}
                </Chip>
              ))}
            </div>
          )}
        </div>

        {team.length === 0 ? (
          <p className="rounded-xl border border-dashed px-4 py-8 text-center text-xs text-muted-foreground">
            Pick a trainer to load their team.
          </p>
        ) : (
          <div
            ref={measureTeam}
            className="grid flex-1"
            style={{
              gap: slotGap,
              minHeight:
                OPPONENT_MIN_HEIGHT * team.length + slotGap * (team.length - 1),
              gridTemplateRows: `repeat(${team.length}, minmax(0, 1fr))`,
            }}
          >
            {team.map((config, idx) => (
              <div key={idx} className="min-h-0 min-w-0">
                <OpponentSlot
                  config={config}
                  nameToId={pokemonData.nameToId}
                  pokemonData={pokemonData}
                  height={slotHeight}
                />
              </div>
            ))}
          </div>
        )}

        {!locked && team.length < 6 && (
          <button
            onClick={onAddSlot}
            className="flex w-full shrink-0 items-center justify-center gap-1.5 rounded-xl border border-dashed py-2 text-sm text-muted-foreground transition-colors hover:border-foreground/20 hover:text-foreground cursor-pointer"
          >
            <Plus className="size-4" /> Add Pokémon
          </button>
        )}
      </div>
    </aside>
  );
}

interface Props {
  pokemonData: PokemonData | null;
  trainerDB: TrainerDB;
  myTeam: PokemonConfig[];
  setMyTeam: (team: PokemonConfig[]) => void;
  oppTeam: PokemonConfig[];
  setOppTeam: (team: PokemonConfig[]) => void;
  trainerItems: string[];
  setTrainerItems: (items: string[]) => void;
  terrain: string;
  setTerrain: (terrain: string) => void;
  run: NuzlockeRun | null;
  onRunChange: (run: NuzlockeRun) => void;
  boxState: BoxState;
  onSetDead: (entry: BoxEntry, dead: boolean) => void;
  evolutions?: Record<string, Evolution[]>;
}

export default function ConfigureView({
  pokemonData,
  trainerDB,
  myTeam,
  setMyTeam,
  oppTeam,
  setOppTeam,
  trainerItems,
  setTrainerItems,
  terrain,
  setTerrain,
  run,
  onRunChange,
  boxState,
  onSetDead,
  evolutions,
}: Props) {
  const { box } = boxState;
  const [oppLocked, setOppLocked] = useState(false);
  const [selectedTrainer, setSelectedTrainer] = useState("");
  // Who just left the party and from which slot, so adding them straight back undoes it
  const [lastRemoved, setLastRemoved] = useState<{
    name: string;
    index: number;
  } | null>(null);
  const savedTrainer = run?.last_trainer; // undefined until the run has loaded

  // Helper: pad a trainer_items array to always have exactly 4 slots
  function padItems(items: string[] = []): string[] {
    return [...items, "", "", "", ""].slice(0, 4);
  }

  // The run's trainer once both have loaded, or the first one it can meet. A new run empties it, so this
  // also goes back to the start. A pick made here is already selected when its save comes back.
  useEffect(() => {
    if (savedTrainer === undefined || Object.keys(trainerDB).length === 0)
      return;
    if (savedTrainer && savedTrainer === selectedTrainer) return;
    const first = Object.keys(trainerDB).find((t) =>
      trainerVisible(trainerDB[t], run),
    );
    loadTrainer(trainerDB[savedTrainer] ? savedTrainer : (first ?? null));
  }, [trainerDB, savedTrainer]);

  // A starter or gender choice (or the run loading) hid the selected rival variant
  useEffect(() => {
    const selected = trainerDB[selectedTrainer];
    if (selected && !trainerVisible(selected, run)) {
      const first = Object.keys(trainerDB).find((t) =>
        trainerVisible(trainerDB[t], run),
      );
      handleSelectTrainer(first ?? null);
    }
  }, [trainerDB, selectedTrainer, run]);

  function clearBox() {
    setMyTeam([]);
    boxState.commit([]);
  }

  function loadTrainer(trainer: string | null) {
    if (trainer === null) {
      setOppLocked(false);
      setSelectedTrainer("");
      setTrainerItems(["", "", "", ""]);
      setTerrain("plain");
      return;
    }
    setSelectedTrainer(trainer);
    setOppTeam(trainerDB[trainer]?.team ?? []);
    setTrainerItems(padItems(trainerDB[trainer]?.trainer_items));
    setTerrain(trainerDB[trainer]?.terrain ?? "plain");
    setOppLocked(true);
  }

  // Clearing isn't saved: the app reopens on the last real trainer
  function handleSelectTrainer(trainer: string | null) {
    loadTrainer(trainer);
    if (trainer && run) onRunChange({ ...run, last_trainer: trainer });
  }

  if (!pokemonData) {
    return (
      <div className="grid h-full grid-cols-[292px_minmax(0,1fr)_360px] gap-px">
        {[0, 1, 2].map((i) => (
          <div key={i} className="space-y-3 p-4">
            {[0, 1, 2].map((j) => (
              <div
                key={j}
                className="h-24 animate-pulse rounded-xl bg-foreground/5"
              />
            ))}
          </div>
        ))}
      </div>
    );
  }

  const { pokemon } = pokemonData;

  function update(idx: number, updated: PokemonConfig) {
    const next = [...myTeam];
    next[idx] = updated;
    setMyTeam(next);
    // The box follows, unsaved until a search starts or its Save button
    const nextBox = box && boxAfterPartyEdit(box, updated);
    if (nextBox && nextBox !== box) boxState.edit(nextBox);
  }

  function addFromBox(entry: BoxEntry) {
    if (
      entry.dead ||
      myTeam.length >= 6 ||
      myTeam.some((t) => t.name === entry.name)
    )
      return;
    const slot =
      lastRemoved?.name === entry.name ? lastRemoved.index : myTeam.length;
    setLastRemoved(null);
    setMyTeam([
      ...myTeam.slice(0, slot),
      {
        name: entry.name,
        gender: entry.gender,
        level: entry.level,
        ability: entry.ability,
        nature: entry.nature,
        moves: [...entry.moves],
        ivs: { ...entry.ivs },
        item: entry.item ?? undefined,
      },
      ...myTeam.slice(slot),
    ]);
  }

  function removeFromParty(idx: number) {
    setLastRemoved({ name: myTeam[idx].name, index: idx });
    setMyTeam(myTeam.filter((_, i) => i !== idx));
  }

  // Clicking a box slot: in the party it leaves, otherwise it joins (dead or a full party: nothing)
  function toggleFromBox(entry: BoxEntry) {
    if (entry.dead) return;
    const idx = myTeam.findIndex((t) => t.name === entry.name);
    if (idx >= 0) removeFromParty(idx);
    else addFromBox(entry);
  }

  function makeLead(idx: number) {
    setLastRemoved(null);
    setMyTeam([myTeam[idx], ...myTeam.filter((_, i) => i !== idx)]);
  }

  // Gone if it died or left the box in the meantime
  const putBack =
    lastRemoved && !myTeam.some((t) => t.name === lastRemoved.name)
      ? box?.find((entry) => !entry.dead && entry.name === lastRemoved.name)
      : undefined;

  function addOppSlot() {
    if (oppTeam.length >= 6) return;
    setOppTeam([
      ...oppTeam,
      {
        name: pokemon[0] ?? "",
        gender: "Male",
        level: 5,
        ability: "",
        nature: "Hardy",
        moves: ["", "", "", ""],
      },
    ]);
  }

  return (
    <div className="grid h-full grid-cols-[292px_minmax(0,1fr)_360px] 2xl:grid-cols-[320px_minmax(0,1fr)_420px] roomy:grid-cols-[380px_minmax(0,1fr)_420px]">
      {box === null ? (
        <BoxUnavailable error={boxState.error} onRetry={boxState.retry} />
      ) : (
        <BoxView
          box={box}
          pokemonData={pokemonData}
          onBoxChange={boxState.edit}
          onEdited={(before, after) =>
            setMyTeam(partyAfterEdit(myTeam, before.name, after))
          }
          onSave={() => boxState.save()}
          onClear={clearBox}
          onSetDead={onSetDead}
          onDelete={(entry) =>
            boxState.commit(box.filter((e) => e.id !== entry.id))
          }
          dirty={boxState.dirty}
          saved={boxState.saved}
          team={myTeam}
          onToggle={toggleFromBox}
          evolutions={evolutions}
        />
      )}

      {/* My team */}
      <section className="flex min-h-0 flex-col">
        <div className="flex h-11 shrink-0 items-center gap-3 border-b px-4">
          <PanelTitle count={`${myTeam.length}/6`}>Your team</PanelTitle>
          {putBack && (
            <Button
              variant="outline"
              size="xs"
              onClick={() => addFromBox(putBack)}
            >
              <Undo2 />
              Put {displayName(putBack.name)} back
            </Button>
          )}
          {myTeam.length > 0 && (
            <span className="ml-auto truncate text-xs text-subtle-foreground">
              Click a Pokémon in the box to add or remove it · hover a sprite
              for stats
            </span>
          )}
        </div>
        <PartyGrid
          team={myTeam}
          pokemonData={pokemonData}
          emptyHint={
            box === null
              ? "Your PC box isn't loaded."
              : box.some((entry) => !entry.dead)
                ? "Click a Pokémon in your PC box to add it."
                : "Your box is empty: use + in the box to add one."
          }
          onChange={update}
          onRemove={removeFromParty}
          onMakeLead={makeLead}
        />
      </section>

      <OpponentPanel
        trainerDB={trainerDB}
        run={run}
        selectedTrainer={selectedTrainer}
        onSelectTrainer={handleSelectTrainer}
        team={oppTeam}
        locked={oppLocked}
        trainerItems={trainerItems}
        terrain={terrain}
        pokemonData={pokemonData}
        onAddSlot={addOppSlot}
      />
    </div>
  );
}
