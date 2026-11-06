import { useState, useEffect, useRef } from "react";
import { MapPin, Plus, Users } from "lucide-react";
import BoxView from "./BoxView";
import type { BoxEntry, NuzlockeRun, PokemonConfig, PokemonData, TrainerDB } from "../types";
import { MyTeamSlot, NameSelect, OpponentSlot } from "./PokemonSlots";
import { trainerVisible } from "@/lib/nuzlocke";
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
          {error ? `Couldn't load the box, so saving is off: ${error}` : "Loading the box…"}
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
  const options = Object.keys(trainerDB).filter((t) => trainerVisible(trainerDB[t], run));
  const sprite = trainerDB[selectedTrainer]?.sprite;
  const items = trainerItems.filter(Boolean);

  return (
    <aside className="flex min-h-0 flex-col border-l bg-card/40">
      <div className="flex h-11 shrink-0 items-center border-b px-3">
        <PanelTitle count={`${team.length}/6`}>Opponent</PanelTitle>
      </div>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
        {/* trainer card */}
        <div
          className="relative overflow-hidden rounded-xl border p-3"
          style={{
            background:
              "radial-gradient(ellipse 70% 90% at 85% 50%, oklch(0.32 0.06 250 / 45%), transparent 70%), var(--card)",
          }}
        >
          <div className="flex items-center gap-3">
            <div className="flex size-16 shrink-0 items-center justify-center">
              {sprite ? (
                <Sprite
                  srcs={trainerSprite(sprite)}
                  alt={selectedTrainer}
                  width={64}
                  height={64}
                />
              ) : (
                <Users className="size-6 text-subtle-foreground" />
              )}
            </div>
            <div className="min-w-0 flex-1">
              <div className="mb-1 text-[11px] text-subtle-foreground">
                Trainer
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
          <div className="space-y-2">
            {team.map((config, idx) => (
              <OpponentSlot
                key={idx}
                config={config}
                nameToId={pokemonData.nameToId}
                pokemonData={pokemonData}
              />
            ))}
          </div>
        )}

        {!locked && team.length < 6 && (
          <button
            onClick={onAddSlot}
            className="flex w-full items-center justify-center gap-1.5 rounded-xl border border-dashed py-2 text-sm text-muted-foreground transition-colors hover:border-foreground/20 hover:text-foreground cursor-pointer"
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
  boxState: BoxState;
  onSetDead: (entry: BoxEntry, dead: boolean) => void;
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
  boxState,
  onSetDead,
}: Props) {
  const { box } = boxState;
  const [oppLocked, setOppLocked] = useState(false);
  const [selectedTrainer, setSelectedTrainer] = useState("");
  const trainerInitialized = useRef(false); // the first trainer is picked once, not after a clear

  // Helper: pad a trainer_items array to always have exactly 4 slots
  function padItems(items: string[] = []): string[] {
    return [...items, "", "", "", ""].slice(0, 4);
  }

  useEffect(() => {
    const firstTrainer = Object.keys(trainerDB)[0];
    if (firstTrainer && selectedTrainer === "" && !trainerInitialized.current) {
      trainerInitialized.current = true;
      setSelectedTrainer(firstTrainer);
      setOppTeam(trainerDB[firstTrainer]?.team ?? []);
      setTrainerItems(padItems(trainerDB[firstTrainer]?.trainer_items));
      setTerrain(trainerDB[firstTrainer]?.terrain ?? "plain");
      setOppLocked(true);
    }
  }, [trainerDB, selectedTrainer]);

  // A starter or gender choice (or the run loading) hid the selected rival variant
  useEffect(() => {
    const selected = trainerDB[selectedTrainer];
    if (selected && !trainerVisible(selected, run)) {
      const first = Object.keys(trainerDB).find((t) => trainerVisible(trainerDB[t], run));
      handleSelectTrainer(first ?? null);
    }
  }, [trainerDB, selectedTrainer, run]);

  function clearBox() {
    setMyTeam([]);
    boxState.commit([]);
  }

  function handleSelectTrainer(trainer: string | null) {
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

  const { pokemon, nameToId } = pokemonData;

  function update(idx: number, updated: PokemonConfig) {
    const next = [...myTeam];
    next[idx] = updated;
    setMyTeam(next);
  }

  function addFromBox(entry: BoxEntry) {
    if (entry.dead || myTeam.length >= 6 || myTeam.some((t) => t.name === entry.name)) return;
    setMyTeam([
      ...myTeam,
      {
        name: entry.name,
        gender: entry.gender,
        level: entry.level,
        ability: entry.ability,
        nature: entry.nature,
        moves: [...entry.moves],
        ivs: { ...entry.ivs },
      },
    ]);
  }

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
    <div className="grid h-full grid-cols-[292px_minmax(0,1fr)_360px] 2xl:grid-cols-[320px_minmax(0,1fr)_420px]">
      {box === null ? (
        <BoxUnavailable error={boxState.error} onRetry={boxState.retry} />
      ) : (
        <BoxView
          box={box}
          pokemonData={pokemonData}
          onBoxChange={boxState.edit}
          onSave={() => boxState.save()}
          onClear={clearBox}
          onSetDead={onSetDead}
          onDelete={(entry) => boxState.commit(box.filter((e) => e.id !== entry.id))}
          dirty={boxState.dirty}
          saved={boxState.saved}
          team={myTeam}
          onAdd={addFromBox}
        />
      )}

      {/* My team */}
      <section className="flex min-h-0 flex-col">
        <div className="flex h-11 shrink-0 items-center border-b px-4">
          <PanelTitle count={`${myTeam.length}/6`}>Your team</PanelTitle>
          {myTeam.length > 0 && (
            <span className="ml-auto text-[11px] text-subtle-foreground">
              Lead first · hover a sprite for stats
            </span>
          )}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-3">
            {myTeam.map((config, idx) => (
              <MyTeamSlot
                key={idx}
                config={config}
                nameToId={nameToId}
                onChange={(updated) => update(idx, updated)}
                onRemove={() => setMyTeam(myTeam.filter((_, i) => i !== idx))}
                pokemonData={pokemonData}
              />
            ))}
            {myTeam.length < 6 && (
              <div className="flex min-h-[220px] flex-col items-center justify-center gap-2 rounded-xl border border-dashed p-6 text-center">
                <div className="flex size-9 items-center justify-center rounded-full bg-foreground/5">
                  <Plus className="size-4 text-muted-foreground" />
                </div>
                <p className="text-sm text-muted-foreground">
                  {myTeam.length === 0
                    ? "Build your team"
                    : "Add another Pokémon"}
                </p>
                <p className="text-xs text-subtle-foreground">
                  {box === null
                    ? "Your PC box isn't loaded."
                    : box.some((entry) => !entry.dead)
                      ? "Double-click a Pokémon in your PC box, or use Add to party."
                      : "Your box is empty: use + in the box to add one."}
                </p>
              </div>
            )}
          </div>
        </div>
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
