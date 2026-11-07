import { Crown, Minus, Plus, X } from "lucide-react";
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
import { spriteBox, type CardFit, type CardSize } from "@/lib/cardFit";
import { frontStatic, itemIcon, pokIcon } from "@/lib/sprites";
import { displayName } from "@/lib/format";
import { moveInfoFor } from "@/lib/hiddenPower";
import type { PokemonConfig, IVs, PokemonData, MoveInfo, BaseStats } from "../types";
import { Sprite } from "./common/Sprite";
import { ItemIcon } from "./common/ItemIcon";
import { Chip, TypeBadges, TypeIcon } from "./common/Badges";

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
  itemLabel,
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  items: string[];
  placeholder?: string;
  clearable?: boolean;
  renderItem?: (item: string) => React.ReactNode;
  itemLabel?: (item: string) => string; // the text in the box and what a search matches
  className?: string;
}) {
  return (
    <Combobox
      value={value}
      onValueChange={(v) => onChange(v ?? "")}
      items={items}
      itemToStringLabel={itemLabel}
    >
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
      <TypeIcon type={info?.type} />
      <span className="flex-1 truncate">{name}</span>
      {!!info?.power && <span className="num text-[10px] text-subtle-foreground">{info.power}</span>}
    </span>
  );
}

const INPUT_SIZE: Record<CardSize, string> = {
  sm: "h-8",
  md: "h-9",
  lg: "h-11 [&_input]:text-base",
};

// Move picker: type symbol in front of the field, type + power in the list
export function MoveSelect({
  value,
  onChange,
  ivs,
  pokemonData,
  clearable = true,
  size = "sm",
}: {
  value: string;
  onChange: (v: string) => void;
  ivs?: IVs;
  pokemonData?: PokemonData;
  clearable?: boolean;
  size?: CardSize;
}) {
  const moveInfo = pokemonData?.moveInfo;
  const type = value ? moveInfoFor(moveInfo, value, ivs)?.type : undefined;
  return (
    <div className="flex min-w-0 items-center gap-1.5">
      {type ? (
        <TypeIcon type={type} size={size === "lg" ? 20 : 16} />
      ) : (
        // an empty slot keeps the space, so the fields stay lined up
        <span
          className={cn(
            "shrink-0 rounded-full ring-1 ring-foreground/10",
            size === "lg" ? "size-5" : "size-4",
          )}
        />
      )}
      <NameSelect
        value={value}
        onChange={onChange}
        items={pokemonData?.moves ?? []}
        placeholder="Empty"
        clearable={clearable && !!value}
        renderItem={(m) => <MoveOption name={m} info={moveInfoFor(moveInfo, m, ivs)} />}
        className={INPUT_SIZE[size]}
      />
    </div>
  );
}

export function ItemSelect({
  value,
  onChange,
  items,
  size = "sm",
}: {
  value: string;
  onChange: (v: string) => void;
  items: string[];
  size?: CardSize;
}) {
  return (
    <div className="flex min-w-0 items-center gap-1.5">
      <span
        className={cn(
          "flex shrink-0 items-center justify-center rounded-md bg-foreground/5",
          size === "sm" ? "size-6" : "size-8",
        )}
      >
        {value && <Sprite srcs={itemIcon(value)} alt="" width={20} height={20} />}
      </span>
      <NameSelect
        value={value}
        onChange={onChange}
        items={items}
        placeholder="No item"
        clearable={!!value}
        className={INPUT_SIZE[size]}
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

// ─── Stat bars: hover card, roomy cards, the box's summary ────────────────────

export function StatBars({
  pokemon,
  pokemonData,
  heading,
  large,
  className,
}: {
  pokemon: Pick<PokemonConfig, "name" | "level" | "nature" | "ivs">;
  pokemonData?: PokemonData;
  heading?: boolean;
  large?: boolean;
  className?: string;
}) {
  const natureMults = pokemonData?.natureMultipliers?.[pokemon.nature] ?? {};
  const stats = calculateStats(
    pokemon.name,
    pokemon.level,
    pokemon.nature,
    pokemon.ivs,
    pokemonData?.baseStats,
    pokemonData?.natureMultipliers,
  );
  if (!stats) return null;

  return (
    <div className={className}>
      {heading && (
        <p className="mb-1.5 text-[10px] font-medium tracking-wider text-subtle-foreground uppercase">
          Stats
        </p>
      )}
      <div className={large ? "space-y-1.5" : "space-y-1"}>
        {IV_KEYS.map((k, i) => {
          const mult = natureMults[k] ?? 1;
          return (
            <div key={k} className={cn("flex items-center gap-2", large ? "text-sm" : "text-xs")}>
              <span
                className={cn(
                  large ? "w-8" : "w-7",
                  "text-subtle-foreground",
                  mult > 1 && "text-good",
                  mult < 1 && "text-bad",
                )}
              >
                {IV_SHORT[i]}
              </span>
              <span className={cn("num text-right font-medium", large ? "w-9" : "w-8")}>{stats[k]}</span>
              <div
                className={cn(
                  "flex-1 overflow-hidden rounded-full bg-foreground/8",
                  large ? "h-1.5" : "h-1",
                )}
              >
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
  );
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

      <StatBars pokemon={config} pokemonData={pokemonData} heading />

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
  scale = 2,
  side = "right",
}: {
  config: PokemonConfig;
  nameToId: Record<string, number>;
  pokemonData?: PokemonData;
  size?: number;
  scale?: number; // the sprite is this × its 96px art
  side?: "left" | "right";
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
            // its transparent padding may spill out of the box
            <Sprite
              srcs={frontStatic(id)}
              alt={config.name}
              width={96 * scale}
              height={96 * scale}
              className="pointer-events-none max-w-none shrink-0"
            />
          ) : (
            <span className="text-xs text-subtle-foreground">?</span>
          )}
        </div>
      </HoverCardTrigger>
      <HoverCardContent side={side} align="start" className="w-64">
        <SlotDetails config={config} pokemonData={pokemonData} />
      </HoverCardContent>
    </HoverCard>
  );
}

// ─── Text sizes of a party card ───────────────────────────────────────────────

const NAME_TEXT: Record<CardSize, string> = { sm: "text-[15px]", md: "text-xl", lg: "text-3xl" };
const INFO_TEXT: Record<CardSize, string> = { sm: "text-xs", md: "text-sm", lg: "text-base" };
const BADGE_HEIGHT: Record<CardSize, number> = { sm: 16, md: 16, lg: 24 };
const LEVEL_SIZE: Record<CardSize, string | undefined> = {
  sm: undefined,
  md: "h-8 w-[100px]",
  lg: "h-10 w-[124px]",
};

// ─── My Team slot: editable level, moves and item; remove ─────────────────────

export function MyTeamSlot({
  config,
  nameToId,
  onChange,
  onRemove,
  onMakeLead,
  isLead,
  fit,
  pokemonData,
}: {
  config: PokemonConfig;
  nameToId: Record<string, number>;
  onChange: (updated: PokemonConfig) => void;
  onRemove: () => void;
  onMakeLead: () => void;
  isLead: boolean;
  fit: CardFit;
  pokemonData?: PokemonData;
}) {
  function setMove(idx: number, value: string) {
    const moves = [...config.moves];
    moves[idx] = value;
    onChange({ ...config, moves });
  }

  const { size } = fit;
  const sprite = (
    <SpriteWithHover
      config={config}
      nameToId={nameToId}
      pokemonData={pokemonData}
      size={fit.box}
      scale={fit.scale}
    />
  );
  const info = (
    <div className="min-w-0">
      {/* room for the remove button */}
      <div className={cn("truncate pr-6 font-semibold tracking-tight", NAME_TEXT[size])}>
        {displayName(config.name) || "—"}
      </div>
      <TypeBadges
        types={pokemonData?.pokemonTypes?.[config.name]}
        height={BADGE_HEIGHT[size]}
        className="mt-1 flex-wrap"
      />
      <div className={cn("mt-1 truncate text-muted-foreground", INFO_TEXT[size])}>
        {config.ability || "No ability"} · {config.nature}
      </div>
      <div className="mt-2 flex items-center gap-2">
        <span className={cn("text-subtle-foreground", size === "sm" ? "text-[11px]" : "text-xs")}>
          Level
        </span>
        <LevelStepper
          value={config.level}
          onChange={(v) => onChange({ ...config, level: v })}
          className={LEVEL_SIZE[size]}
        />
      </div>
    </div>
  );
  const stats = fit.stats && (
    <StatBars pokemon={config} pokemonData={pokemonData} large={size === "lg"} />
  );
  const inputs = (
    <div className="flex flex-col gap-2">
      <div className={cn("grid gap-x-2 gap-y-1.5", fit.moveColumns === 2 && "grid-cols-2")}>
        {config.moves.map((move, i) => (
          <MoveSelect
            key={i}
            value={move}
            onChange={(v) => setMove(i, v)}
            ivs={config.ivs}
            pokemonData={pokemonData}
            size={size}
          />
        ))}
      </div>
      <ItemSelect
        value={config.item ?? ""}
        onChange={(v) => onChange({ ...config, item: v || undefined })}
        items={pokemonData?.items ?? []}
        size={size}
      />
    </div>
  );

  return (
    <div className="group relative h-full rounded-xl border bg-card p-3 transition-colors hover:border-foreground/15">
      {isLead ? (
        <Chip tone="primary" className="absolute top-2 left-2 z-10">
          <Crown className="size-3" />
          Lead
        </Chip>
      ) : (
        <Button
          variant="ghost"
          size="xs"
          onClick={onMakeLead}
          className="absolute top-2 left-2 z-10 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"
        >
          <Crown />
          Make lead
        </Button>
      )}
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

      {fit.layout === "wide" ? (
        <div className="flex h-full items-center gap-10 px-6">
          {sprite}
          <div className="flex min-w-0 flex-1 flex-col gap-8">
            {info}
            {stats}
            {inputs}
          </div>
        </div>
      ) : fit.layout === "tall" ? (
        <div className="flex h-full flex-col gap-4">
          <div className="flex min-h-0 flex-1 items-center justify-center">{sprite}</div>
          {info}
          {stats}
          {inputs}
        </div>
      ) : (
        <div className="flex h-full flex-col gap-3">
          <div className="flex flex-1 items-center gap-3">
            {sprite}
            <div className="flex min-w-0 flex-1 flex-col gap-2">
              {info}
              {stats}
            </div>
          </div>
          {inputs}
        </div>
      )}
    </div>
  );
}

// ─── Opponent slot: read-only, by how much height it gets ──────────────────────

export function OpponentSlot({
  config,
  nameToId,
  pokemonData,
  height,
}: {
  config: PokemonConfig;
  nameToId: Record<string, number>;
  pokemonData?: PokemonData;
  height: number;
}) {
  const id = nameToId[config.name];
  const moveInfo = pokemonData?.moveInfo;
  const types = pokemonData?.pokemonTypes?.[config.name];
  const large = height >= 114; // room for the bigger tile with the item's name under it

  const moves = (
    <div className={cn("grid gap-1", height < 620 && "grid-cols-2")}>
      {config.moves.map((move, i) => (
        <span
          key={i}
          className={cn(
            "flex items-center gap-1.5 truncate rounded-md px-2",
            large ? "py-1 text-sm" : "py-0.5 text-xs",
            move ? "bg-foreground/5 text-foreground/90" : "text-subtle-foreground italic",
          )}
        >
          {move && (
            <TypeIcon type={moveInfoFor(moveInfo, move, config.ivs)?.type} size={large ? 16 : 14} />
          )}
          <span className="truncate">{move || "—"}</span>
        </span>
      ))}
    </div>
  );

  const itemChip = config.item && (
    <Chip className="bg-elevated">
      <ItemIcon name={config.item} size={16} />
      {config.item}
    </Chip>
  );

  // Name, level and types, then ability and nature, for a card with a real sprite
  const heading = (
    <div>
      <div className="flex items-baseline gap-2">
        <span className="min-w-0 truncate text-lg font-semibold tracking-tight">
          {displayName(config.name) || "—"}
        </span>
        <span className="num shrink-0 text-sm whitespace-nowrap text-subtle-foreground">
          Lv {config.level}
        </span>
      </div>
      <TypeBadges types={types} height={18} className="mt-1" />
      <div className="mt-1 truncate text-sm text-muted-foreground">
        {config.ability || "No ability"} · {config.nature}
      </div>
    </div>
  );

  // Only one Pokémon: sprite on top, everything below it
  if (height >= 620) {
    return (
      <div className="flex h-full min-h-0 flex-col gap-3 overflow-hidden rounded-xl border bg-card p-3">
        <div className="flex min-h-0 flex-1 items-center justify-center">
          <SpriteWithHover
            config={config}
            nameToId={nameToId}
            pokemonData={pokemonData}
            size={spriteBox(3)}
            scale={3}
            side="left"
          />
        </div>
        <div>
          {heading}
          {itemChip && <div className="mt-1.5">{itemChip}</div>}
        </div>
        <StatBars pokemon={config} pokemonData={pokemonData} />
        {moves}
      </div>
    );
  }

  // Two or three: sprite beside the info, moves below
  if (height >= 220) {
    return (
      <div className="flex h-full min-h-0 flex-col gap-2 overflow-hidden rounded-xl border bg-card p-3">
        <div className="flex min-h-0 flex-1 items-center">
          <div className="flex w-full items-stretch gap-3">
            <div className="relative flex shrink-0 items-center">
              <SpriteWithHover
                config={config}
                nameToId={nameToId}
                pokemonData={pokemonData}
                size={spriteBox(2)}
                side="left"
              />
              {/* level with the last line beside it, and it doesn't push the sprite up */}
              {itemChip && (
                <div className="pointer-events-none absolute inset-x-0 -bottom-0.5 flex justify-center">
                  {itemChip}
                </div>
              )}
            </div>
            <div className="flex min-w-0 flex-1 flex-col justify-center gap-2">
              {heading}
              {height >= 340 && <StatBars pokemon={config} pokemonData={pokemonData} />}
            </div>
          </div>
        </div>
        {moves}
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 items-center gap-3 overflow-hidden rounded-xl border bg-card p-2.5">
      <div
        className={cn(
          "flex shrink-0 flex-col items-center gap-1.5",
          large ? "w-[72px] roomy:w-20" : "w-16",
        )}
      >
        <HoverCard openDelay={200} closeDelay={80}>
          <HoverCardTrigger asChild>
            <div
              className={cn(
                "relative flex shrink-0 cursor-help items-center justify-center rounded-lg bg-foreground/4 ring-1 ring-foreground/8",
                large ? "size-[72px]" : "size-12",
              )}
            >
              {id ? (
                <Sprite
                  srcs={pokIcon(id)}
                  alt={config.name}
                  width={large ? 80 : 40}
                  height={large ? 60 : 30}
                  className="max-w-none shrink-0"
                />
              ) : (
                "?"
              )}
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
        {config.item && (
          <Chip
            title={config.item}
            className={cn(
              "h-4 w-full justify-center px-0.5 roomy:px-1",
              !large && "px-0 text-[10px] font-normal",
            )}
          >
            <span className="min-w-0 truncate">{config.item}</span>
          </Chip>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className={cn("min-w-0 truncate font-semibold", large ? "text-base" : "text-sm")}>
            {displayName(config.name) || "—"}
          </span>
          <span className="num shrink-0 text-xs whitespace-nowrap text-subtle-foreground">
            Lv {config.level}
          </span>
          <TypeBadges types={types} height={large ? 16 : 14} className="ml-auto shrink-0" />
        </div>
        <div className="mt-1.5">{moves}</div>
      </div>
    </div>
  );
}
