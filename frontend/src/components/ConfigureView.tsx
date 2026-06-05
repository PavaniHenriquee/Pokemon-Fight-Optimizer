import { useState } from "react";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxList,
} from "./ui/combobox";
import type { PokemonConfig, PokemonData } from "../types";

// ─── default teams mirror what was hardcoded in Python ────────────────────────
const DEFAULT_MY_TEAM: PokemonConfig[] = [
  {
    name: "Charmander",
    gender: "Male",
    level: 5,
    ability: "Blaze",
    nature: "Hardy",
    moves: ["Scratch", "Growl", "Ember", ""],
  },
  {
    name: "Bulbasaur",
    gender: "Male",
    level: 5,
    ability: "Overgrow",
    nature: "Hardy",
    moves: ["Pound", "Leer", "Razor Leaf", ""],
  },
  {
    name: "Squirtle",
    gender: "Male",
    level: 7,
    ability: "Torrent",
    nature: "Hardy",
    moves: ["Tackle", "Tail Whip", "Bubble", ""],
  },
  {
    name: "Charmeleon",
    gender: "Male",
    level: 5,
    ability: "Blaze",
    nature: "Hardy",
    moves: ["Scratch", "Growl", "", ""],
  },
  {
    name: "Ivysaur",
    gender: "Male",
    level: 5,
    ability: "Overgrow",
    nature: "Hardy",
    moves: ["Pound", "Leer", "", ""],
  },
  {
    name: "Wartortle",
    gender: "Male",
    level: 5,
    ability: "Torrent",
    nature: "Hardy",
    moves: ["Tackle", "Tail Whip", "", ""],
  },
];

const DEFAULT_OPP_TEAM: PokemonConfig[] = [
  {
    name: "Squirtle",
    gender: "Male",
    level: 5,
    ability: "Torrent",
    nature: "Hardy",
    moves: ["Tackle", "Tail Whip", "", ""],
  },
  {
    name: "Charmander",
    gender: "Male",
    level: 5,
    ability: "Blaze",
    nature: "Hardy",
    moves: ["Scratch", "Growl", "", ""],
  },
  {
    name: "Charmander",
    gender: "Male",
    level: 5,
    ability: "Blaze",
    nature: "Hardy",
    moves: ["Scratch", "Growl", "", ""],
  },
  {
    name: "Charmander",
    gender: "Male",
    level: 5,
    ability: "Blaze",
    nature: "Hardy",
    moves: ["Scratch", "Growl", "", ""],
  },
  {
    name: "Charmander",
    gender: "Male",
    level: 5,
    ability: "Blaze",
    nature: "Hardy",
    moves: ["Scratch", "Growl", "", ""],
  },
];

// ─── shared select style ───────────────────────────────────────────────────────
const inp =
  "bg-slate-700 border border-slate-600 text-slate-100 text-sm rounded px-2 py-1 focus:outline-none focus:border-violet-500";

// ─── single Pokemon slot ──────────────────────────────────────────────────────
function PokemonSlot({
  config,
  allPokemon,
  allMoves,
  allNatures,
  allAbilities,
  onChange,
  onRemove,
}: {
  config: PokemonConfig;
  allPokemon: string[];
  allMoves: string[];
  allNatures: string[];
  allAbilities: string[];
  onChange: (updated: PokemonConfig) => void;
  onRemove: () => void;
}) {
  function set<K extends keyof PokemonConfig>(key: K, value: PokemonConfig[K]) {
    onChange({ ...config, [key]: value });
  }

  function setMove(idx: number, value: string) {
    const moves = [...config.moves];
    moves[idx] = value;
    onChange({ ...config, moves });
  }

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-3 space-y-2">
      {/* Row 1: name, level, gender */}
      <div className="relative flex flex-wrap flex-row gap-2 items-center">
        <div className="relative flex-1 w-10 shrink-0">
          <Combobox
            value={config.name ?? ""}
            onValueChange={(v) => set("name", v ?? "")}
            items={allPokemon}
          >
            <ComboboxInput className={`${inp} w-full`} showClear />
            <ComboboxContent>
              <ComboboxEmpty>No results found</ComboboxEmpty>
              <ComboboxList>
                {(item) => (
                  <ComboboxItem key={item} value={item}>
                    {item}
                  </ComboboxItem>
                )}
              </ComboboxList>
            </ComboboxContent>
          </Combobox>
        </div>

        {/* --- Rest of your existing level/gender code remains identical --- */}
        <div className="flex items-center gap-1 shrink-0 w-18">
          <span className="text-slate-400 text-xs">Lv</span>
          <input
            type="number"
            min={1}
            max={100}
            value={config.level}
            onChange={(e) => set("level", parseInt(e.target.value) || 1)}
            className={`${inp} w-14 text-center`}
          />
        </div>

        <Combobox
          value={config.gender ?? "None"}
          onValueChange={(value) =>
            set("gender", value === "None" ? null : value)
          }
          items={["Male", "Female", "None"]}
        >
          <ComboboxInput className={`${inp} w-27 shrink-0`} />
          <ComboboxContent>
            <ComboboxList>
              <ComboboxItem value="Male">Male</ComboboxItem>
              <ComboboxItem value="Female">Female</ComboboxItem>
              <ComboboxItem value="None">None</ComboboxItem>
            </ComboboxList>
          </ComboboxContent>
        </Combobox>

        <button
          onClick={onRemove}
          className="absolute -top-5 -right-5.5 text-slate-300 hover:text-red-600 transition-all w-6 h-6 rounded-full bg-red-500/40 hover:bg-red-500/60 flex items-center justify-center"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="pr-0.25 w-4 h-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>

      {/* Row 2: ability, nature */}
      <div className="flex gap-2">
        <Combobox
          value={config.ability}
          onValueChange={(value) => set("ability", value ?? "")}
        >
          <ComboboxInput className={`${inp} flex-1`} />
          <ComboboxContent>
            <ComboboxEmpty>No results found</ComboboxEmpty>
            <ComboboxList>
              {allAbilities.map((n) => (
                <ComboboxItem key={n} value={n}>
                  {n}
                </ComboboxItem>
              ))}
            </ComboboxList>
          </ComboboxContent>
        </Combobox>
        <Combobox
          value={config.nature}
          onValueChange={(value) => set("nature", value ?? "")}
        >
          {" "}
          <ComboboxInput className={`${inp} flex-1`} />
          <ComboboxContent>
            <ComboboxEmpty>No results found</ComboboxEmpty>
            <ComboboxList>
              {allNatures.map((n) => (
                <ComboboxItem key={n} value={n}>
                  {n}
                </ComboboxItem>
              ))}
            </ComboboxList>
          </ComboboxContent>
        </Combobox>
      </div>

      {/* Row 3: moves */}
      <div className="grid grid-cols-2 gap-2">
        {config.moves.map((move, i) => (
          <div key={i}>
            <Combobox
              value={move}
              onValueChange={(value) => setMove(i, value ?? "")}
            >
              <ComboboxInput className={inp} placeholder="— empty —" />
              <ComboboxContent>
                <ComboboxEmpty>No results found</ComboboxEmpty>
                <ComboboxList>
                  {allMoves.map((m) => (
                    <ComboboxItem key={m} value={m}>
                      {m}
                    </ComboboxItem>
                  ))}
                </ComboboxList>
              </ComboboxContent>
            </Combobox>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── one team column ──────────────────────────────────────────────────────────
function TeamPanel({
  label,
  team,
  allPokemon,
  allMoves,
  allNatures,
  allAbilities,
  onChange,
}: {
  label: string;
  team: PokemonConfig[];
  allPokemon: string[];
  allMoves: string[];
  allNatures: string[];
  allAbilities: string[];
  onChange: (team: PokemonConfig[]) => void;
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
      <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
        {label} <span className="text-slate-600">({team.length}/6)</span>
      </h2>

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
          />
        ))}
      </div>

      {team.length < 6 && (
        <button
          onClick={addSlot}
          className="w-full py-2 border border-dashed border-slate-600 text-slate-500 hover:text-slate-300 hover:border-slate-500 rounded-lg text-sm transition-colors"
        >
          + Add Pokémon
        </button>
      )}
    </div>
  );
}

// ─── main view ────────────────────────────────────────────────────────────────
interface Props {
  pokemonData: PokemonData | null;
  onStart: (myTeam: PokemonConfig[], oppTeam: PokemonConfig[]) => void;
  running: boolean;
}

export default function ConfigureView({
  pokemonData,
  onStart,
  running,
}: Props) {
  const [myTeam, setMyTeam] = useState<PokemonConfig[]>(DEFAULT_MY_TEAM);
  const [oppTeam, setOppTeam] = useState<PokemonConfig[]>(DEFAULT_OPP_TEAM);

  if (!pokemonData) {
    return (
      <div className="flex-1 flex items-center justify-center text-slate-500">
        Loading Pokémon data…
      </div>
    );
  }

  const { pokemon, moves, natures, abilities } = pokemonData;
  const canStart = myTeam.length > 0 && oppTeam.length > 0;

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Teams */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="flex gap-4 items-start max-w-5xl mx-auto">
          <TeamPanel
            label="Your Team"
            team={myTeam}
            allPokemon={pokemon}
            allMoves={moves}
            allNatures={natures}
            allAbilities={abilities}
            onChange={setMyTeam}
          />
          <div className="w-px bg-slate-700 self-stretch shrink-0" />
          <TeamPanel
            label="Opponent Team"
            team={oppTeam}
            allPokemon={pokemon}
            allMoves={moves}
            allNatures={natures}
            allAbilities={abilities}
            onChange={setOppTeam}
          />
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
