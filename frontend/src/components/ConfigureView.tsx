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

const itemIcon = (name: string) =>
  `https://play.pokemonshowdown.com/sprites/itemicons/${name.toLowerCase().replace(/[\s_]+/g, "-")}.png`;

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
  const sprite = trainerDB[selectedTrainer]?.sprite ?? null;

  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-full flex-shrink-0">
        {sprite && (
          <img
            src={`https://play.pokemonshowdown.com/sprites/trainers/${sprite}.png`}
            alt={selectedTrainer}
            style={{ imageRendering: "pixelated" }}
            className="object-contain"
          />
        )}
      </div>
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
    </div>
  );
}

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
  pokemonData,
  trainerItems,
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
  pokemonData?: PokemonData;
  trainerItems?: string[];
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
          <div className="w-60">
            <OpponentHeader
              trainerDB={trainerDB}
              selectedTrainer={selectedTrainer}
              onSelectTrainer={onTrainerSelect}
            />
          </div>
        )}
      </div>

      {/* Trainer battle items — opponent side only */}
      {trainerItems !== undefined && trainerItems.some(Boolean) && (
        <div className="my-2">
          <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">
            Trainer Items
          </p>
          <div className="flex flex-wrap gap-2">
            {trainerItems.filter(Boolean).map((item, i) => (
              <div
                key={i}
                className="flex items-center gap-1.5 px-2 py-1 bg-slate-800 border border-slate-700 rounded-lg"
              >
                <img
                  src={itemIcon(item)}
                  alt=""
                  width={16}
                  height={16}
                  style={{ imageRendering: "pixelated" }}
                  onError={(e) => {
                    e.currentTarget.style.display = "none";
                  }}
                />
                <span className="text-xs text-slate-300">{item}</span>
              </div>
            ))}
          </div>
        </div>
      )}

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
              pokemonData={pokemonData}
            />
          ) : (
            <OpponentSlot
              key={idx}
              config={config}
              nameToId={nameToId ?? {}}
              pokemonData={pokemonData}
            />
          ),
        )}
      </div>

      {team.length < 6 &&
        !locked &&
        (boxEntries !== undefined ? (
          (() => {
            const availableEntries = boxEntries.filter(
              (entry) => !team.some((t) => t.name === entry.name),
            );
            return availableEntries.length === 0 ? (
              <p className="text-xs text-slate-500 italic text-center py-3 border border-dashed border-slate-700 rounded-lg">
                {boxEntries.length === 0
                  ? "Box is empty — open Box to add Pokémon"
                  : "All box Pokémon are in your team"}
              </p>
            ) : (
              <div className="flex flex-col gap-2">
                <p className="text-xs text-slate-500 uppercase tracking-wide">
                  Add from box
                </p>
                <div className="grid grid-cols-6 gap-2">
                  {availableEntries.map((entry) => (
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
                      className="flex flex-col items-center gap-1 px-2 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-sm transition-colors cursor-pointer"
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
                      <span className="text-xs truncate w-full text-center">
                        {entry.name}
                      </span>
                      <span className="text-xs text-slate-500">
                        Lv.{entry.level}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            );
          })()
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

interface Props {
  pokemonData: PokemonData | null;
  trainerDB: TrainerDB;
  myTeam: PokemonConfig[];
  setMyTeam: (team: PokemonConfig[]) => void;
  oppTeam: PokemonConfig[];
  setOppTeam: (team: PokemonConfig[]) => void;
  trainerItems: string[];
  setTrainerItems: (items: string[]) => void;
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
}: Props) {
  const [box, setBox] = useState<BoxEntry[] | null>(null);
  const [oppLocked, setOppLocked] = useState(false);
  const [selectedTrainer, setSelectedTrainer] = useState("");

  // Helper: pad a trainer_items array to always have exactly 4 slots
  function padItems(items: string[] = []): string[] {
    return [...items, "", "", "", ""].slice(0, 4);
  }

  useEffect(() => {
    const firstTrainer = Object.keys(trainerDB)[0];
    if (firstTrainer && selectedTrainer === "") {
      setSelectedTrainer(firstTrainer);
      setOppTeam(trainerDB[firstTrainer]?.team ?? []);
      setTrainerItems(padItems(trainerDB[firstTrainer]?.trainer_items));
      setOppLocked(true);
    }
  }, [trainerDB, selectedTrainer]);

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
      setTrainerItems(["", "", "", ""]);
      return;
    }
    setSelectedTrainer(trainer);
    setOppTeam(trainerDB[trainer]?.team ?? []);
    setTrainerItems(padItems(trainerDB[trainer]?.trainer_items));
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

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="flex-1 overflow-y-auto p-4">
        <div className="max-w-[95%] mx-auto space-y-3">
          <BoxView
            box={box ?? []}
            pokemonData={pokemonData}
            onBoxChange={(b) => setBox(b)}
            onSave={saveBox}
          />

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
                pokemonData={pokemonData}
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
                pokemonData={pokemonData}
                trainerItems={trainerItems}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
