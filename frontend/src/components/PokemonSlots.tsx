import { HoverCard, HoverCardTrigger, HoverCardContent } from "./ui/hover-card";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxList,
} from "./ui/combobox";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "./ui/input-group";
import type { PokemonConfig, IVs, PokemonData } from "../types";

const inp =
  "bg-slate-700 border border-slate-600 text-slate-100 text-xs rounded px-2 py-1 focus:outline-none focus:border-violet-500 w-full h-6";

const IV_KEYS: (keyof IVs)[] = [
  "HP",
  "Attack",
  "Defense",
  "Special Attack",
  "Special Defense",
  "Speed",
];
const IV_SHORT = ["HP", "Atk", "Def", "SpA", "SpD", "Spe"];

const itemIcon = (name: string) =>
  `https://play.pokemonshowdown.com/sprites/itemicons/${name.toLowerCase().replace(/[\s_]+/g, "-")}.png`;

// ─── Sprite ───────────────────────────────────────────────────────────────────

function FrontSprite({
  name,
  nameToId,
}: {
  name: string;
  nameToId: Record<string, number>;
}) {
  const id = nameToId[name];
  if (!id) {
    return (
      <div className="w-24 h-24 rounded-lg bg-slate-700 flex items-center justify-center text-slate-500 text-xs select-none">
        ?
      </div>
    );
  }
  return (
    <img
      src={`https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${id}.png`}
      alt={name}
      width={96}
      height={96}
      draggable={false}
      style={{ imageRendering: "pixelated" }}
    />
  );
}

// ─── Stat calculation ────────────────────────────────────────────────────────

function calculateStats(
  name: string,
  level: number,
  nature: string,
  ivs: IVs | undefined,
  baseStats: Record<string, any> | undefined,
  natureMultipliers: Record<string, Record<string, number>> | undefined,
) {
  if (!baseStats || !baseStats[name]) return null;

  const base = baseStats[name];
  const ivVals = ivs || {
    HP: 31,
    Attack: 31,
    Defense: 31,
    "Special Attack": 31,
    "Special Defense": 31,
    Speed: 31,
  };

  const stats: Record<string, number> = {};

  // HP: ((2 * base + iv) * level / 100) + level + 10 (not affected by nature)
  stats.HP = Math.floor(((2 * base.HP + ivVals.HP) * level) / 100) + level + 10;

  // Get nature multipliers, default to 1.0 for neutral natures
  const natureMults = natureMultipliers?.[nature] || {};

  // Other stats: (((2 * base + iv) * level / 100) + 5) * nature_multiplier
  stats.Attack = Math.floor(
    (((2 * base.Attack + ivVals.Attack) * level) / 100 + 5) *
      (natureMults.Attack || 1),
  );
  stats.Defense = Math.floor(
    (((2 * base.Defense + ivVals.Defense) * level) / 100 + 5) *
      (natureMults.Defense || 1),
  );
  stats["Special Attack"] = Math.floor(
    (((2 * base["Special Attack"] + ivVals["Special Attack"]) * level) / 100 +
      5) *
      (natureMults["Special Attack"] || 1),
  );
  stats["Special Defense"] = Math.floor(
    (((2 * base["Special Defense"] + ivVals["Special Defense"]) * level) / 100 +
      5) *
      (natureMults["Special Defense"] || 1),
  );
  stats.Speed = Math.floor(
    (((2 * base.Speed + ivVals.Speed) * level) / 100 + 5) *
      (natureMults.Speed || 1),
  );

  return stats;
}

// ─── Hover card content ───────────────────────────────────────────────────────

function SlotDetails({
  config,
  pokemonData,
}: {
  config: PokemonConfig;
  pokemonData?: PokemonData;
}) {
  const ivs = config.ivs;
  // Only show IVs section when at least one is below 31
  const hasCustomIvs = ivs && IV_KEYS.some((k) => (ivs[k] ?? 31) < 31);

  const stats = calculateStats(
    config.name,
    config.level,
    config.nature,
    ivs,
    pokemonData?.baseStats,
    pokemonData?.natureMultipliers,
  );

  return (
    <div className="p-3 flex flex-col gap-2.5 min-w-[160px]">
      {/* Name + Level */}
      <div className="flex items-center gap-2">
        <span className="font-semibold text-slate-100">{config.name}</span>
        <span className="text-sm text-slate-400">Lv.{config.level}</span>
      </div>
      {/* Ability + Nature + Gender */}
      <div className="flex flex-col gap-0.5">
        {config.ability && (
          <span className="text-sm text-slate-200">{config.ability}</span>
        )}
        <div className="flex gap-2 text-xs text-slate-400">
          <span>{config.nature}</span>
          {config.gender && <span>· {config.gender}</span>}
        </div>
      </div>

      {/* Calculated stats */}
      {stats && (
        <div>
          <p className="text-xs text-slate-500 mb-1">Stats</p>
          <div className="grid grid-cols-3 gap-x-3 gap-y-0.5">
            {IV_KEYS.map((k, i) => {
              const val = stats[k];
              return (
                <span key={k} className="text-xs">
                  <span className="text-slate-500">{IV_SHORT[i]} </span>
                  <span className="text-slate-300">{val}</span>
                </span>
              );
            })}
          </div>
        </div>
      )}

      {/* IVs — only when something is non-31 */}
      {hasCustomIvs && (
        <div>
          <p className="text-xs text-slate-500 mb-1">IVs</p>
          <div className="grid grid-cols-3 gap-x-3 gap-y-0.5">
            {IV_KEYS.map((k, i) => {
              const val = ivs![k] ?? 31;
              return (
                <span key={k} className="text-xs">
                  <span className="text-slate-500">{IV_SHORT[i]} </span>
                  <span
                    className={val < 31 ? "text-yellow-400" : "text-slate-300"}
                  >
                    {val}
                  </span>
                </span>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Sprite wrapped in hover card ─────────────────────────────────────────────

function SpriteWithHover({
  config,
  nameToId,
  pokemonData,
}: {
  config: PokemonConfig;
  nameToId: Record<string, number>;
  pokemonData?: PokemonData;
}) {
  return (
    <HoverCard openDelay={250} closeDelay={100}>
      <HoverCardTrigger asChild>
        {/* div wrapper needed — img alone can't be a Radix trigger */}
        <div className="flex justify-center cursor-default select-none">
          <FrontSprite name={config.name} nameToId={nameToId} />
        </div>
      </HoverCardTrigger>
      <HoverCardContent className="bg-slate-800 border border-slate-600 rounded-lg shadow-xl z-50 animate-in fade-in-0 zoom-in-95">
        <SlotDetails config={config} pokemonData={pokemonData} />
      </HoverCardContent>
    </HoverCard>
  );
}

// ─── My Team slot: editable level + moves, read-only name, remove ─────────────

export function MyTeamSlot({
  config,
  allMoves,
  nameToId,
  onChange,
  onRemove,
  pokemonData,
}: {
  config: PokemonConfig;
  allMoves: string[];
  nameToId: Record<string, number>;
  onChange: (updated: PokemonConfig) => void;
  onRemove: () => void;
  pokemonData?: PokemonData;
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
      {/* Row 1: Name (read-only) + Level +/- + Remove */}
      <div className="relative flex items-center gap-2">
        <span className="flex-1 font-semibold text-slate-100 truncate min-w-0">
          {config.name || "—"}
        </span>

        <InputGroup className="w-24 shrink-0">
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

        <button
          onClick={onRemove}
          className="absolute -top-5 -right-5.5 text-slate-300 hover:text-red-400 transition-colors w-6 h-6 rounded-full bg-red-500/40 hover:bg-red-500/60 flex items-center justify-center cursor-pointer"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="w-4 h-4"
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

      {/* Row 2: Sprite + hover card */}
      <SpriteWithHover
        config={config}
        nameToId={nameToId}
        pokemonData={pokemonData}
      />

      {/* Row 3: Move comboboxes */}
      <div className="grid grid-cols-2 gap-2">
        {config.moves.map((move, i) => (
          <Combobox
            key={i}
            value={move}
            onValueChange={(v) => setMove(i, v ?? "")}
            items={allMoves}
          >
            <ComboboxInput className={inp} placeholder="— empty —" />
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
        ))}
      </div>
      {/* Item */}
      <div>
        <label className="block text-xs text-slate-500 mb-0.5">Item</label>
        <div className="flex items-center gap-1">
          {config.item ? (
            <img
              src={itemIcon(config.item)}
              alt=""
              width={18}
              height={18}
              style={{ imageRendering: "pixelated", flexShrink: 0 }}
              onError={(e) => {
                e.currentTarget.style.display = "none";
              }}
            />
          ) : (
            <div style={{ width: 18, flexShrink: 0 }} />
          )}
          <div className="flex-1 min-w-0">
            <Combobox
              value={config.item ?? ""}
              onValueChange={(v) =>
                onChange({ ...config, item: v ?? undefined })
              }
              items={pokemonData?.items ?? []}
            >
              <ComboboxInput className={inp} placeholder="— none —" showClear />
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
        </div>
      </div>
    </div>
  );
}

// ─── Opponent slot: fully read-only info display ──────────────────────────────

export function OpponentSlot({
  config,
  nameToId,
  pokemonData,
}: {
  config: PokemonConfig;
  nameToId: Record<string, number>;
  pokemonData?: PokemonData;
}) {
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-3 space-y-2">
      {/* Row 1: Name + Level */}
      <div className="flex justify-between items-center">
        <span className="font-semibold text-slate-100">
          {config.name || "—"}
        </span>
        <span className="text-sm text-slate-400">Lv.{config.level}</span>
      </div>

      {/* Row 2: Sprite + hover card */}
      <SpriteWithHover
        config={config}
        nameToId={nameToId}
        pokemonData={pokemonData}
      />

      {/* Row 3: Moves as read-only badges */}
      <div className="grid grid-cols-2 gap-1.5">
        {config.moves.map((move, i) => (
          <span
            key={i}
            className={`text-xs px-2 py-1 rounded text-center truncate ${
              move ? "bg-slate-700 text-slate-200" : "text-slate-600 italic"
            }`}
          >
            {move || "—"}
          </span>
        ))}
      </div>
      {config.item && (
        <div className="flex items-center gap-1">
          <img
            src={itemIcon(config.item)}
            alt=""
            width={16}
            height={16}
            style={{ imageRendering: "pixelated" }}
            onError={(e) => {
              e.currentTarget.style.display = "none";
            }}
          />
          <span className="text-xs text-slate-300">{config.item}</span>
        </div>
      )}
    </div>
  );
}
