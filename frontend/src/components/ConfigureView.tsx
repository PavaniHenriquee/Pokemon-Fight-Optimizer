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
import type { BoxEntry, PokemonConfig, PokemonData } from "../types";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "./ui/input-group";

const API_URL = "http://localhost:8000";

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
        {/*Name*/}
        <div className="flex-1 min-w-38 shrink-0">
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

        {/*Level*/}
        <div className="flex items-center shrink-0">
          <InputGroup className="w-24">
            <InputGroupAddon align="inline-start">
              <InputGroupButton
                onClick={() => set("level", Math.max(1, config.level - 1))}
              >
                -
              </InputGroupButton>
            </InputGroupAddon>

            <InputGroupInput
              type="number"
              min={1}
              max={100}
              value={config.level}
              onChange={(e) => set("level", parseInt(e.target.value) || 1)}
              className="text-center"
            />

            <InputGroupAddon align="inline-end">
              <InputGroupButton
                onClick={() => set("level", Math.min(100, config.level + 1))}
              >
                +
              </InputGroupButton>
            </InputGroupAddon>
          </InputGroup>
        </div>

        {/*Gender*/}
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
          className="absolute -top-5 -right-5.5 text-slate-300 hover:text-red-600 transition-all w-6 h-6 rounded-full bg-red-500/40 hover:bg-red-500/60 flex items-center justify-center cursor-pointer"
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
  boxEntries,
  nameToId,
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

      {team.length < 6 &&
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
  // ── box ──────────────────────────────────────────────────────────────────────
  const [box, setBox] = useState<BoxEntry[] | null>(null);

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

  if (!pokemonData) {
    return (
      <div className="flex-1 flex items-center justify-center text-slate-500">
        Loading Pokémon data…
      </div>
    );
  }

  const { pokemon, moves, natures, abilities, nameToId } = pokemonData;
  const canStart = myTeam.length > 0 && oppTeam.length > 0;

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Teams */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="max-w-5xl mx-auto space-y-3">
          {/* Box trigger */}
          <BoxView
            box={box ?? []}
            pokemonData={pokemonData}
            onBoxChange={(b) => setBox(b)}
            onSave={saveBox}
          />

          {/* Teams */}
          <div className="flex gap-4 items-start">
            <TeamPanel
              label="My Team"
              team={myTeam}
              allPokemon={pokemon}
              allMoves={moves}
              allNatures={natures}
              allAbilities={abilities}
              onChange={setMyTeam}
              boxEntries={box ?? []}
              nameToId={nameToId}
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
