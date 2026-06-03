import { useState } from "react";
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
  "w-full bg-slate-700 border border-slate-600 text-slate-100 text-sm rounded px-2 py-1 focus:outline-none focus:border-violet-500";

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

  const [isOpen, setIsOpen] = useState(false);
  const [backupValue, setBackupValue] = useState("");

  // Filter the list based on what's typed in config.name
  const filteredPokemon = allPokemon.filter((p) =>
    p.toLowerCase().includes(config.name.toLowerCase()),
  );

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-3 space-y-2">
      {/* Row 1: name, level, gender */}
      <div className="inline-grid grid-cols-4 gap-2 items-center">
        {/* Searchable Dropdown Container */}
        <div className="relative flex-1">
          <input
            type="text"
            value={config.name}
            onFocus={() => {
              setBackupValue(config.name); // Save current value in case they cancel
              setIsOpen(true);
            }}
            onChange={(e) => set("name", e.target.value)}
            onBlur={() => {
              // Wrap in timeout so click selection can process first
              setTimeout(() => {
                setIsOpen(false);
                // If what they typed isn't a valid option, revert to previous value
                const valid = allPokemon.some(
                  (p) => p.toLowerCase() === config.name.toLowerCase(),
                );
                if (!valid) set("name", backupValue);
              }, 150);
            }}
            className={`${inp} w-full`}
            placeholder="Search Pokémon..."
          />

          {/* Custom Dropdown Menu */}
          {isOpen && (
            <ul className="absolute z-50 left-0 right-0 mt-1 max-h-60 overflow-y-auto rounded-md border border-slate-700 bg-slate-900 py-1 shadow-lg">
              {filteredPokemon.length === 0 ? (
                <li className="px-3 py-2 text-xs text-slate-500">
                  No results found
                </li>
              ) : (
                filteredPokemon.map((p) => (
                  <li
                    key={p}
                    // onMouseDown fires BEFORE input onBlur handles reversion
                    onMouseDown={() => {
                      set("name", p);
                      setIsOpen(false);
                    }}
                    className="cursor-pointer px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 transition-colors"
                  >
                    {p}
                  </li>
                ))
              )}
            </ul>
          )}
        </div>

        {/* --- Rest of your existing level/gender code remains identical --- */}
        <div className="flex items-center gap-1 shrink-0">
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

        <input
          type="text"
          list="gender-list"
          value={config.gender ?? "None"}
          onChange={(e) =>
            set("gender", e.target.value === "None" ? null : e.target.value)
          }
          className={`${inp} w-24 shrink-0`}
        />
        <datalist id="gender-list">
          <option value="Male" />
          <option value="Female" />
          <option value="None" />
        </datalist>

        <button
          onClick={onRemove}
          className="text-slate-500 hover:text-red-400 transition-colors shrink-0 text-lg leading-none"
        >
          x
        </button>
      </div>

      {/* Row 2: ability, nature */}
      <div className="flex gap-2">
        <input
          type="text"
          list="ability-list"
          value={config.ability}
          onChange={(e) => set("ability", e.target.value)}
          className={`${inp} flex-1`}
        />
        <datalist id="ability-list">
          {allAbilities.map((n) => (
            <option key={n} value={n} />
          ))}
        </datalist>
        <input
          type="text"
          list="nature-list"
          value={config.nature}
          onChange={(e) => set("nature", e.target.value)}
          className={`${inp} flex-1`}
        />
        <datalist id="nature-list">
          {allNatures.map((n) => (
            <option key={n} value={n} />
          ))}
        </datalist>
      </div>

      {/* Row 3: moves */}
      <div className="grid grid-cols-2 gap-2">
        {config.moves.map((move, i) => (
          <div key={i}>
            <input
              type="text"
              list="moves-list"
              value={move}
              onChange={(e) => setMove(i, e.target.value)}
              placeholder="— empty —"
              className={inp}
            />
            <datalist id="moves-list">
              {allMoves.map((m) => (
                <option key={m} value={m} />
              ))}
            </datalist>
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
