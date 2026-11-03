import { Minus, Plus, X } from "lucide-react";
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
import { Button } from "./ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "./ui/tooltip";
import { cn } from "@/lib/utils";
import { frontStatic, itemIcon, pokIcon } from "@/lib/sprites";
import { displayName } from "@/lib/format";
import type { PokemonConfig, IVs, PokemonData, MoveInfo, BaseStats } from "../types";
import { Sprite } from "./common/Sprite";
import { ItemIcon } from "./common/ItemIcon";
import { TypeBadges, TypeDot } from "./common/Badges";

const IV_KEYS: (keyof IVs)[] = [
  "HP",
  "Attack",
  "Defense",
  "Special Attack",
  "Special Defense",
  "Speed",
];
const IV_SHORT = ["HP", "Atk", "Def", "SpA", "SpD", "Spe"];

// ─── Inputs shared with the box editor ────────────────────────────────────────

export function LevelStepper({
  value,
  onChange,
  min = 1,
  max = 100,
  className,
}: {
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  className?: string;
}) {
  return (
    <InputGroup className={cn("h-7 w-[92px] shrink-0", className)}>
      <InputGroupAddon align="inline-start">
        <InputGroupButton size="icon-xs" onClick={() => onChange(Math.max(min, value - 1))}>
          <Minus />
        </InputGroupButton>
      </InputGroupAddon>
      <InputGroupInput
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Math.max(min, Math.min(max, parseInt(e.target.value) || min)))}
        className="num text-center"
      />
      <InputGroupAddon align="inline-end">
        <InputGroupButton size="icon-xs" onClick={() => onChange(Math.min(max, value + 1))}>
          <Plus />
        </InputGroupButton>
      </InputGroupAddon>
    </InputGroup>
  );
}

// Searchable select over a list of names, with an optional leading element per item
export function NameSelect({
  value,
  onChange,
  items,
  placeholder,
  clearable,
  renderItem,
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  items: string[];
  placeholder?: string;
  clearable?: boolean;
  renderItem?: (item: string) => React.ReactNode;
  className?: string;
}) {
  return (
    <Combobox value={value} onValueChange={(v) => onChange(v ?? "")} items={items}>
      <ComboboxInput
        className={cn("h-8 w-full min-w-0", className)}
        placeholder={placeholder}
        showClear={clearable}
        // select the current text so typing replaces it (search "Roark" over "Test")
        onFocus={(e) => e.currentTarget.select()}
      />
      <ComboboxContent className="min-w-60">
        <ComboboxEmpty>No results</ComboboxEmpty>
        <ComboboxList>
          {(item: string) => (
            <ComboboxItem key={item} value={item}>
              {renderItem ? renderItem(item) : item}
            </ComboboxItem>
          )}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  );
}

function MoveOption({ name, info }: { name: string; info?: MoveInfo }) {
  return (
    <span className="flex w-full items-center gap-2">
      <TypeDot type={info?.type} />
      <span className="flex-1 truncate">{name}</span>
      {!!info?.power && <span className="num text-[10px] text-subtle-foreground">{info.power}</span>}
    </span>
  );
}

// Move picker: type dot in front of the field, type + power in the list
export function MoveSelect({
  value,
  onChange,
  pokemonData,
  clearable = true,
}: {
  value: string;
  onChange: (v: string) => void;
  pokemonData?: PokemonData;
  clearable?: boolean;
}) {
  const moveInfo = pokemonData?.moveInfo;
  const type = value ? moveInfo?.[value]?.type : undefined;
  return (
    <div className="flex min-w-0 items-center gap-1.5">
      <span
        className="size-2 shrink-0 rounded-full ring-1 ring-foreground/10"
        style={type ? { background: `var(--type-${type.toLowerCase()})` } : undefined}
        title={type}
      />
      <NameSelect
        value={value}
        onChange={onChange}
        items={pokemonData?.moves ?? []}
        placeholder="Empty"
        clearable={clearable && !!value}
        renderItem={(m) => <MoveOption name={m} info={moveInfo?.[m]} />}
      />
    </div>
  );
}

export function ItemSelect({
  value,
  onChange,
  items,
}: {
  value: string;
  onChange: (v: string) => void;
  items: string[];
}) {
  return (
    <div className="flex min-w-0 items-center gap-1.5">
      <span className="flex size-6 shrink-0 items-center justify-center rounded-md bg-foreground/5">
        {value && <Sprite srcs={itemIcon(value)} alt="" width={20} height={20} />}
      </span>
      <NameSelect
        value={value}
        onChange={onChange}
        items={items}
        placeholder="No item"
        clearable={!!value}
        renderItem={(it) => (
          <span className="flex items-center gap-2">
            <Sprite srcs={itemIcon(it)} alt="" width={18} height={18} />
            {it}
          </span>
        )}
      />
    </div>
  );
}

// ─── Stat calculation ────────────────────────────────────────────────────────

export function calculateStats(
  name: string,
  level: number,
  nature: string,
  ivs: IVs | undefined,
  baseStats: Record<string, BaseStats> | undefined,
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
  const natureMults = pokemonData?.natureMultipliers?.[config.nature] ?? {};

  const stats = calculateStats(
    config.name,
    config.level,
    config.nature,
    ivs,
    pokemonData?.baseStats,
    pokemonData?.natureMultipliers,
  );

  return (
    <div className="flex flex-col gap-3">
      <div>
        <div className="flex items-baseline gap-2">
          <span className="font-semibold">{displayName(config.name)}</span>
          <span className="num text-xs text-subtle-foreground">Lv {config.level}</span>
          {config.gender && (
            <span className="ml-auto text-xs text-muted-foreground">{config.gender}</span>
          )}
        </div>
        <div className="mt-0.5 text-xs text-muted-foreground">
          {config.ability || "No ability"} · {config.nature}
        </div>
      </div>

      {stats && (
        <div>
          <p className="mb-1.5 text-[10px] font-medium tracking-wider text-subtle-foreground uppercase">
            Stats
          </p>
          <div className="space-y-1">
            {IV_KEYS.map((k, i) => {
              const mult = natureMults[k] ?? 1;
              return (
                <div key={k} className="flex items-center gap-2 text-xs">
                  <span
                    className={cn(
                      "w-7 text-subtle-foreground",
                      mult > 1 && "text-good",
                      mult < 1 && "text-bad",
                    )}
                  >
                    {IV_SHORT[i]}
                  </span>
                  <span className="num w-8 text-right font-medium">{stats[k]}</span>
                  <div className="h-1 flex-1 overflow-hidden rounded-full bg-foreground/8">
                    <div
                      className="h-full rounded-full bg-primary/70"
                      style={{ width: `${(stats[k] / Math.max(...Object.values(stats), 1)) * 100}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* IVs — only when something is non-31 */}
      {hasCustomIvs && (
        <div>
          <p className="mb-1 text-[10px] font-medium tracking-wider text-subtle-foreground uppercase">
            IVs
          </p>
          <div className="grid grid-cols-3 gap-x-3 gap-y-0.5">
            {IV_KEYS.map((k, i) => {
              const val = ivs![k] ?? 31;
              return (
                <span key={k} className="num text-xs">
                  <span className="text-subtle-foreground">{IV_SHORT[i]} </span>
                  <span className={val < 31 ? "text-warn" : "text-foreground"}>{val}</span>
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
  size = 100,
}: {
  config: PokemonConfig;
  nameToId: Record<string, number>;
  pokemonData?: PokemonData;
  size?: number;
}) {
  const id = nameToId[config.name];
  return (
    <HoverCard openDelay={250} closeDelay={100}>
      <HoverCardTrigger asChild>
        {/* div wrapper needed — img alone can't be a Radix trigger */}
        <div
          className="flex shrink-0 cursor-help items-center justify-center rounded-xl select-none"
          style={{
            width: size,
            height: size,
            background: "radial-gradient(closest-side, oklch(1 0 0 / 7%), transparent)",
          }}
        >
          {id ? (
            // 2× of the 96px sprite; its transparent padding may spill out of the box
            <Sprite
              srcs={frontStatic(id)}
              alt={config.name}
              width={192}
              height={192}
              className="pointer-events-none max-w-none"
            />
          ) : (
            <span className="text-xs text-subtle-foreground">?</span>
          )}
        </div>
      </HoverCardTrigger>
      <HoverCardContent side="right" align="start" className="w-64">
        <SlotDetails config={config} pokemonData={pokemonData} />
      </HoverCardContent>
    </HoverCard>
  );
}

// ─── My Team slot: editable level, moves and item; remove ─────────────────────

export function MyTeamSlot({
  config,
  nameToId,
  onChange,
  onRemove,
  pokemonData,
}: {
  config: PokemonConfig;
  nameToId: Record<string, number>;
  onChange: (updated: PokemonConfig) => void;
  onRemove: () => void;
  pokemonData?: PokemonData;
}) {
  function setMove(idx: number, value: string) {
    const moves = [...config.moves];
    moves[idx] = value;
    onChange({ ...config, moves });
  }

  return (
    <div className="group relative rounded-xl border bg-card p-3 transition-colors hover:border-foreground/15">
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={onRemove}
            className="absolute top-2 right-2 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 hover:text-bad"
            aria-label="Remove from team"
          >
            <X />
          </Button>
        </TooltipTrigger>
        <TooltipContent>Remove from team</TooltipContent>
      </Tooltip>

      <div className="flex gap-3">
        <SpriteWithHover config={config} nameToId={nameToId} pokemonData={pokemonData} />
        <div className="min-w-0 flex-1 pr-6">
          <div className="truncate text-[15px] font-semibold tracking-tight">
            {displayName(config.name) || "—"}
          </div>
          <TypeBadges types={pokemonData?.pokemonTypes?.[config.name]} className="mt-1" />
          <div className="mt-1 truncate text-xs text-muted-foreground">
            {config.ability || "No ability"} · {config.nature}
          </div>
          <div className="mt-2 flex items-center gap-2">
            <span className="text-[11px] text-subtle-foreground">Level</span>
            <LevelStepper value={config.level} onChange={(v) => onChange({ ...config, level: v })} />
          </div>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-x-2 gap-y-1.5">
        {config.moves.map((move, i) => (
          <MoveSelect key={i} value={move} onChange={(v) => setMove(i, v)} pokemonData={pokemonData} />
        ))}
      </div>
      <div className="mt-2">
        <ItemSelect
          value={config.item ?? ""}
          onChange={(v) => onChange({ ...config, item: v || undefined })}
          items={pokemonData?.items ?? []}
        />
      </div>
    </div>
  );
}

// ─── Opponent slot: compact read-only row ──────────────────────────────────────

export function OpponentSlot({
  config,
  nameToId,
  pokemonData,
}: {
  config: PokemonConfig;
  nameToId: Record<string, number>;
  pokemonData?: PokemonData;
}) {
  const id = nameToId[config.name];
  const moveInfo = pokemonData?.moveInfo;
  return (
    <div className="flex gap-3 rounded-xl border bg-card p-2.5">
      <HoverCard openDelay={200} closeDelay={80}>
        <HoverCardTrigger asChild>
          <div className="relative flex size-12 shrink-0 cursor-help items-center justify-center rounded-lg bg-foreground/4 ring-1 ring-foreground/8">
            {id ? <Sprite srcs={pokIcon(id)} alt={config.name} width={40} height={30} /> : "?"}
            {/* held item on the tile's corner, like the games mark it */}
            {config.item && (
              <span className="absolute -right-1.5 -bottom-1.5 flex size-5 items-center justify-center rounded-full bg-elevated ring-1 ring-foreground/15">
                <ItemIcon name={config.item} size={16} />
              </span>
            )}
          </div>
        </HoverCardTrigger>
        <HoverCardContent side="left" align="start" className="w-64">
          <SlotDetails config={config} pokemonData={pokemonData} />
        </HoverCardContent>
      </HoverCard>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="min-w-0 truncate text-sm font-semibold">{displayName(config.name) || "—"}</span>
          <span className="num shrink-0 text-xs whitespace-nowrap text-subtle-foreground">
            Lv {config.level}
          </span>
          <TypeBadges
            types={pokemonData?.pokemonTypes?.[config.name]}
            height={14}
            className="ml-auto shrink-0"
          />
        </div>
        <div className="mt-1.5 grid grid-cols-2 gap-1">
          {config.moves.map((move, i) => (
            <span
              key={i}
              className={cn(
                "flex items-center gap-1.5 truncate rounded-md px-2 py-0.5 text-xs",
                move ? "bg-foreground/5 text-foreground/90" : "text-subtle-foreground italic",
              )}
            >
              {move && <TypeDot type={moveInfo?.[move]?.type} />}
              <span className="truncate">{move || "—"}</span>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
