import { useState, useEffect } from "react";
import BoxView from "./BoxView";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxList,
} from "./ui/combobox";
import type { BoxEntry, PokemonConfig, PokemonData, TrainerDB } from "../types";
import { MyTeamSlot, OpponentSlot } from "./PokemonSlots";

const API_URL = "http://localhost:8000";

// ─── single Pokemon slot ──────────────────────────────

function OpponentHeader({
  trainerDB,
  selectedTrainer,
  onSelectTrainer,
}: {
  trainerDB: TrainerDB;
  selectedTrainer: string;
  onSelectTrainer: (trainer: string | null) => void;
}) {
  const options = Object.keys(trainerDB);

  return (
    <Combobox
      value={selectedTrainer}
      onValueChange={(v) => {
        if (!v) onSelectTrainer(null);
        else onSelectTrainer(v);
      }}
      items={options}
    >
      <ComboboxInput
        className="bg-slate-700 border border-slate-600 text-slate-100 text-sm rounded px-2 py-1 w-full"
        placeholder={options[0]}
      />
      <ComboboxContent>
        <ComboboxEmpty>No results</ComboboxEmpty>
        <ComboboxList>
          {(item: string) => (
            <ComboboxItem key={item} value={item}>
              {item}
            </ComboboxItem>
          )}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  );
}

// ─── one team column ──────────────────────────────────────────────────────────
/*
function TeamPanel({
  label,
  team,
  allPokemon,
  allMoves,
  allNatures,
  allAbilities,
  onChange,
  boxEntries,
  nameToId,
  trainerDB,
  selectedTrainer,
  onTrainerSelect,
  locked = false,
}: {
  label: string;
  team: PokemonConfig[];
  allPokemon: string[];
  allMoves: string[];
  allNatures: string[];
  allAbilities: string[];
  onChange: (team: PokemonConfig[]) => void;
  boxEntries?: BoxEntry[]; // undefined = Opponent, defined = My Team
  nameToId?: Record<string, number>;
  trainerDB?: TrainerDB;
  selectedTrainer?: string;
  onTrainerSelect?: (trainer: string | null) => void; // if provided, shows trainer select dropdown
  locked?: boolean; // if true, disables team editing (used for Opponent when trainer is selected)
}) {
  function addSlot() {
    if (team.length >= 6) return;
    const first = allPokemon[0];
    onChange([
      ...team,
      {
        name: first,
        gender: "Male",
        level: 5,
        ability: "",
        nature: "Hardy",
        moves: ["", "", "", ""],
      },
    ]);
  }

  function update(idx: number, updated: PokemonConfig) {
    const next = [...team];
    next[idx] = updated;
    onChange(next);
  }

  function remove(idx: number) {
    onChange(team.filter((_, i) => i !== idx));
  }

  return (
    <div className="flex-1 min-w-0 space-y-3">
      <div className="flex flex-wrap items-center gap-3 justify-between">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
          {label} <span className="text-slate-600">({team.length}/6)</span>
        </h2>
        {onTrainerSelect && trainerDB && selectedTrainer !== undefined && (
          <div className="w-full sm:w-52">
            <OpponentHeader
              trainerDB={trainerDB}
              selectedTrainer={selectedTrainer}
              onSelectTrainer={onTrainerSelect}
            />
          </div>
        )}
      </div>
      {locked && onTrainerSelect ? (
        <p className="text-xs text-slate-500">
          Trainer-selected teams are locked.
        </p>
      ) : null}

      <div className="space-y-2">
        {team.map((config, idx) => (
          <PokemonSlot
            key={idx}
            config={config}
            allPokemon={allPokemon}
            allMoves={allMoves}
            allNatures={allNatures}
            allAbilities={allAbilities}
            onChange={(updated) => update(idx, updated)}
            onRemove={() => remove(idx)}
            disabled={locked}
          />
        ))}
      </div>

      {team.length < 6 &&
        !locked &&
        (boxEntries !== undefined ? (
          // ── My Team: pick from box ────────────────────────────────────────
          boxEntries.length === 0 ? (
            <p className="text-xs text-slate-500 italic text-center py-3 border border-dashed border-slate-700 rounded-lg">
              Box is empty — open Box to add Pokémon
            </p>
          ) : (
            <div className="flex flex-col gap-1">
              <p className="text-xs text-slate-500 uppercase tracking-wide mb-0.5">
                Add from box
              </p>
              {boxEntries.map((entry) => (
                <button
                  key={entry.id}
                  onClick={() =>
                    onChange([
                      ...team,
                      {
                        name: entry.name,
                        gender: entry.gender,
                        level: entry.level,
                        ability: entry.ability,
                        nature: entry.nature,
                        moves: [...entry.moves],
                        ivs: { ...entry.ivs },
                      },
                    ])
                  }
                  className="flex items-center gap-2 px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-sm text-left transition-colors"
                >
                  {nameToId?.[entry.name] && (
                    <img
                      src={`https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/versions/generation-v/icons/${nameToId[entry.name]}.png`}
                      width={32}
                      height={24}
                      alt=""
                      draggable={false}
                      style={{ imageRendering: "pixelated" }}
                    />
                  )}
                  <span className="flex-1 truncate">{entry.name}</span>
                  <span className="text-xs text-slate-500 shrink-0">
                    Lv.{entry.level}
                  </span>
                </button>
              ))}
            </div>
          )
        ) : (
          // ── Opponent Team: blank slot ──────────────────────────────────────
          <button
            onClick={addSlot}
            className="w-full py-2 border border-dashed border-slate-600 text-slate-500 hover:text-slate-300 hover:border-slate-500 rounded-lg text-sm transition-colors"
          >
            + Add Pokémon
          </button>
        ))}
    </div>
  );
}
*/
function TeamPanel({
  label,
  team,
  allPokemon,
  allMoves,
  onChange,
  boxEntries,
  nameToId,
  slotVariant = "my",
  trainerDB,
  selectedTrainer,
  onTrainerSelect,
  locked = false,
}: {
  label: string;
  team: PokemonConfig[];
  allPokemon: string[];
  allMoves: string[];
  onChange: (team: PokemonConfig[]) => void;
  boxEntries?: BoxEntry[];
  nameToId?: Record<string, number>;
  slotVariant?: "my" | "opp";
  trainerDB?: TrainerDB;
  selectedTrainer?: string;
  onTrainerSelect?: (trainer: string | null) => void;
  locked?: boolean;
}) {
  function addSlot() {
    if (team.length >= 6) return;
    onChange([
      ...team,
      {
        name: allPokemon[0] ?? "",
        gender: "Male",
        level: 5,
        ability: "",
        nature: "Hardy",
        moves: ["", "", "", ""],
      },
    ]);
  }

  function update(idx: number, updated: PokemonConfig) {
    const next = [...team];
    next[idx] = updated;
    onChange(next);
  }

  function remove(idx: number) {
    onChange(team.filter((_, i) => i !== idx));
  }

  return (
    <div className="flex-1">
      <div className="flex flex-wrap items-center gap-3 justify-between">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
          {label} <span className="text-slate-600">({team.length}/6)</span>
        </h2>
        {onTrainerSelect && trainerDB && selectedTrainer !== undefined && (
          <div className="w-full sm:w-52">
            <OpponentHeader
              trainerDB={trainerDB}
              selectedTrainer={selectedTrainer}
              onSelectTrainer={onTrainerSelect}
            />
          </div>
        )}
      </div>
      {locked && onTrainerSelect ? (
        <p className="text-xs text-slate-500">
          Trainer-selected teams are locked.
        </p>
      ) : null}

      <div className="grid grid-cols-2 gap-3">
        {team.map((config, idx) =>
          slotVariant === "my" ? (
            <MyTeamSlot
              key={idx}
              config={config}
              allMoves={allMoves}
              nameToId={nameToId ?? {}}
              onChange={(updated) => update(idx, updated)}
              onRemove={() => remove(idx)}
            />
          ) : (
            <OpponentSlot key={idx} config={config} nameToId={nameToId ?? {}} />
          ),
        )}
      </div>

      {team.length < 6 &&
        !locked &&
        (boxEntries !== undefined ? (
          boxEntries.length === 0 ? (
            <p className="text-xs text-slate-500 italic text-center py-3 border border-dashed border-slate-700 rounded-lg">
              Box is empty — open Box to add Pokémon
            </p>
          ) : (
            <div className="flex flex-col gap-1">
              <p className="text-xs text-slate-500 uppercase tracking-wide mb-0.5">
                Add from box
              </p>
              {boxEntries.map((entry) => (
                <button
                  key={entry.id}
                  onClick={() =>
                    onChange([
                      ...team,
                      {
                        name: entry.name,
                        gender: entry.gender,
                        level: entry.level,
                        ability: entry.ability,
                        nature: entry.nature,
                        moves: [...entry.moves],
                        ivs: { ...entry.ivs },
                      },
                    ])
                  }
                  className="flex items-center gap-2 px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-sm text-left transition-colors"
                >
                  {nameToId?.[entry.name] && (
                    <img
                      src={`https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/versions/generation-v/icons/${nameToId[entry.name]}.png`}
                      width={32}
                      height={24}
                      alt=""
                      draggable={false}
                      style={{ imageRendering: "pixelated" }}
                    />
                  )}
                  <span className="flex-1 truncate">{entry.name}</span>
                  <span className="text-xs text-slate-500 shrink-0">
                    Lv.{entry.level}
                  </span>
                </button>
              ))}
            </div>
          )
        ) : (
          <button
            onClick={addSlot}
            className="w-full py-2 border border-dashed border-slate-600 text-slate-500 hover:text-slate-300 hover:border-slate-500 rounded-lg text-sm transition-colors"
          >
            + Add Pokémon
          </button>
        ))}
    </div>
  );
}
// ─── main view ────────────────────────────────────────────────────────────────
interface Props {
  pokemonData: PokemonData | null;
  onStart: (myTeam: PokemonConfig[], oppTeam: PokemonConfig[]) => void;
  running: boolean;
  trainerDB: TrainerDB;
}

export default function ConfigureView({
  pokemonData,
  onStart,
  running,
  trainerDB,
}: Props) {
  const [myTeam, setMyTeam] = useState<PokemonConfig[]>([]);
  const [oppTeam, setOppTeam] = useState<PokemonConfig[]>([]);
  const [box, setBox] = useState<BoxEntry[] | null>(null);
  const [oppLocked, setOppLocked] = useState(false);
  const [selectedTrainer, setSelectedTrainer] = useState("");

  // Select the first loaded trainer once when trainerDB arrives.
  useEffect(() => {
    const firstTrainer = Object.keys(trainerDB)[0];
    if (firstTrainer && selectedTrainer === "") {
      setSelectedTrainer(firstTrainer);
      setOppTeam(trainerDB[firstTrainer] ?? []);
      setOppLocked(true);
    }
  }, [trainerDB, selectedTrainer]);

  // Load once on mount
  useEffect(() => {
    fetch(`${API_URL}/box`)
      .then((r) => r.json())
      .then((data: BoxEntry[]) => setBox(data))
      .catch(() => setBox([]));
  }, []);

  function saveBox() {
    if (box === null) return;
    fetch(`${API_URL}/box`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(box),
    }).catch(console.error);
  }

  function handleSelectTrainer(trainer: string | null) {
    if (trainer === null) {
      setOppLocked(false);
      setSelectedTrainer("");
      return;
    }

    setSelectedTrainer(trainer);
    setOppTeam(trainerDB[trainer] ?? []);
    setOppLocked(true);
  }

  if (!pokemonData) {
    return (
      <div className="flex-1 flex items-center justify-center text-slate-500">
        Loading Pokémon data…
      </div>
    );
  }

  const { pokemon, moves, nameToId } = pokemonData;
  const canStart = myTeam.length > 0 && oppTeam.length > 0;

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Teams */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="max-w-[95%] mx-auto space-y-3">
          {/* Box trigger */}
          <BoxView
            box={box ?? []}
            pokemonData={pokemonData}
            onBoxChange={(b) => setBox(b)}
            onSave={saveBox}
          />

          {/* Teams */}
          <div className="flex gap-4 items-start">
            <div style={{ flex: 1.15, minWidth: 0 }}>
              <TeamPanel
                label="My Team"
                slotVariant="my"
                team={myTeam}
                allPokemon={pokemon}
                allMoves={moves}
                onChange={setMyTeam}
                boxEntries={box ?? []}
                nameToId={nameToId}
              />
            </div>
            <div className="w-px bg-slate-700 self-stretch shrink-0" />
            <div style={{ flex: 0.85, minWidth: 0 }}>
              <TeamPanel
                label="Opponent Team"
                slotVariant="opp"
                team={oppTeam}
                allPokemon={pokemon}
                allMoves={moves}
                onChange={setOppTeam}
                nameToId={nameToId}
                trainerDB={trainerDB}
                selectedTrainer={selectedTrainer}
                onTrainerSelect={handleSelectTrainer}
                locked={oppLocked}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Start bar */}
      <div className="border-t border-slate-700 bg-slate-900 px-4 py-3 flex items-center justify-end gap-3">
        <span className="text-slate-500 text-sm">
          {myTeam.length} vs {oppTeam.length} Pokémon
        </span>
        <button
          onClick={() => onStart(myTeam, oppTeam)}
          disabled={!canStart || running}
          className="px-6 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition-colors"
        >
          {running ? "Running…" : "▶ Start MCTS"}
        </button>
      </div>
    </div>
  );
}
