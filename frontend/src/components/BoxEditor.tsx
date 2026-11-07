import { useMemo, useRef, useState } from "react";
import { Minus, Plus, Search, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { battleSprite, pokIcon } from "@/lib/sprites";
import { displayName, typeColor } from "@/lib/format";
import { hiddenPower, moveInfoFor } from "@/lib/hiddenPower";
import { genderFor, startingMoves } from "@/lib/nuzlocke";
import type { BoxEntry, IVs, PokemonData } from "../types";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "./ui/dialog";
import { Button } from "./ui/button";
import { ComboboxPortalContainer } from "./ui/combobox";
import { Sprite } from "./common/Sprite";
import { CategoryIcon, PokeballIcon, TypeBadge, TypeBadges } from "./common/Badges";
import { NameSelect, calculateStats } from "./PokemonSlots";

// ─── Constants ────────────────────────────────────────────────────────────────

const STAT_KEYS: (keyof IVs)[] = [
  "HP",
  "Attack",
  "Defense",
  "Special Attack",
  "Special Defense",
  "Speed",
];
const STAT_SHORT: Record<keyof IVs, string> = {
  HP: "HP",
  Attack: "Atk",
  Defense: "Def",
  "Special Attack": "SpA",
  "Special Defense": "SpD",
  Speed: "Spe",
};

// Nature grid: row = raised stat, column = lowered stat, neutral natures on the diagonal
const NATURE_STATS = ["Attack", "Defense", "Special Attack", "Special Defense", "Speed"] as const;
const NEUTRAL_NATURE: Record<string, string> = {
  Attack: "Hardy",
  Defense: "Docile",
  "Special Attack": "Bashful",
  "Special Defense": "Quirky",
  Speed: "Serious",
};

// Game convention: raised stat in red, lowered in blue
const UP = "text-[oklch(0.72_0.17_25)]";
const DOWN = "text-[oklch(0.72_0.12_240)]";

type Draft = Omit<BoxEntry, "id">;
type Page = "info" | "moves" | "stats";

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-2 text-[11px] font-medium tracking-widest text-subtle-foreground uppercase">
      {children}
    </div>
  );
}

// ─── Left panel: sprite, gender, level ─────────────────────────────────────────

function GenderToggle({
  value,
  genderless,
  onChange,
}: {
  value: string | null;
  genderless: boolean; // the species has no gender: "—" is the only choice, and otherwise it isn't one
  onChange: (g: string | null) => void;
}) {
  const opts: { v: string | null; label: string; cls: string; title: string }[] = [
    { v: "Male", label: "♂", cls: "text-[oklch(0.7_0.14_245)]", title: "Male" },
    { v: "Female", label: "♀", cls: "text-[oklch(0.72_0.16_350)]", title: "Female" },
    { v: null, label: "—", cls: "text-muted-foreground", title: "Genderless" },
  ];
  return (
    <div className="flex rounded-lg bg-background/50 p-0.5 ring-1 ring-foreground/10">
      {opts.filter((o) => (o.v === null) === genderless).map((o) => (
        <button
          key={o.title}
          title={o.title}
          onClick={() => onChange(o.v)}
          className={cn(
            "h-7 w-8 rounded-md text-base font-semibold transition-colors cursor-pointer",
            o.cls,
            value === o.v ? "bg-elevated ring-1 ring-foreground/15" : "opacity-45 hover:opacity-100",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

function ProfilePanel({
  draft,
  patch,
  pokemonData,
}: {
  draft: Draft;
  patch: (p: Partial<Draft>) => void;
  pokemonData: PokemonData;
}) {
  const id = pokemonData.nameToId[draft.name];
  const types = pokemonData.pokemonTypes?.[draft.name];
  const tint = types?.[0] ? typeColor(types[0]) : "var(--primary)";
  return (
    <div
      className="flex w-[280px] shrink-0 flex-col items-center gap-3 border-r p-5"
      style={{
        background: `radial-gradient(ellipse 90% 55% at 50% 30%, color-mix(in oklab, ${tint} 26%, transparent), transparent 75%), linear-gradient(180deg, var(--elevated), var(--card))`,
      }}
    >
      {/* sprite on its platform */}
      <div className="relative flex h-[188px] w-full items-end justify-center pb-6">
        <div
          className="absolute bottom-3 left-1/2 h-10 w-44 -translate-x-1/2 rounded-[50%]"
          style={{
            background:
              "radial-gradient(closest-side, oklch(1 0 0 / 14%), oklch(1 0 0 / 5%) 65%, transparent)",
          }}
        />
        {id ? (
          <Sprite
            key={id}
            srcs={battleSprite(id, "front")}
            alt={draft.name}
            className="relative drop-shadow-[0_6px_10px_rgb(0_0_0/45%)]"
            style={{ transform: "scale(2)", transformOrigin: "bottom center" }}
          />
        ) : (
          <div className="relative mb-4 flex flex-col items-center gap-2 text-subtle-foreground">
            <PokeballIcon className="size-12 opacity-40 grayscale" />
            <span className="text-xs">Choose a species</span>
          </div>
        )}
      </div>

      <div className="flex w-full items-center justify-between gap-2">
        <span className="truncate text-xl font-semibold tracking-tight">
          {draft.name ? displayName(draft.name) : "???"}
        </span>
        <GenderToggle
          value={draft.gender}
          genderless={genderFor(pokemonData, draft.name, draft.gender) === null}
          onChange={(g) => patch({ gender: g })}
        />
      </div>
      <div className="flex min-h-[18px] w-full">
        <TypeBadges types={types} />
      </div>

      {/* level */}
      <div className="mt-auto w-full rounded-xl bg-background/40 p-3 ring-1 ring-foreground/8">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-medium tracking-widest text-subtle-foreground uppercase">
            Level
          </span>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={() => patch({ level: Math.max(1, draft.level - 1) })}
              aria-label="Level down"
            >
              <Minus />
            </Button>
            <span className="num w-9 text-center text-2xl font-semibold">{draft.level}</span>
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={() => patch({ level: Math.min(100, draft.level + 1) })}
              aria-label="Level up"
            >
              <Plus />
            </Button>
          </div>
        </div>
        <input
          type="range"
          min={1}
          max={100}
          value={draft.level}
          onChange={(e) => patch({ level: parseInt(e.target.value) })}
          className="mt-2 w-full cursor-pointer accent-(--primary)"
          aria-label="Level"
        />
      </div>
    </div>
  );
}

// ─── INFO page: species, ability, nature ───────────────────────────────────────

function InfoPage({
  draft,
  patch,
  pokemonData,
  catching,
  speciesChoices,
}: {
  draft: Draft;
  patch: (p: Partial<Draft>) => void;
  pokemonData: PokemonData;
  catching: boolean;
  speciesChoices?: string[];
}) {
  const { pokemon, nameToId, natureMultipliers, abilities } = pokemonData;
  const speciesAbilities = pokemonData.pokemonAbilities?.[draft.name] ?? [];
  const abilityChoices =
    draft.ability && !speciesAbilities.includes(draft.ability)
      ? [...speciesAbilities, draft.ability]
      : speciesAbilities;

  const natureAt = (up: string, down: string) =>
    up === down
      ? NEUTRAL_NATURE[up]
      : (Object.keys(natureMultipliers).find(
          (n) => (natureMultipliers[n][up] ?? 1) > 1 && (natureMultipliers[n][down] ?? 1) < 1,
        ) ?? "");

  return (
    <div className="space-y-5">
      {!catching && (
        <div>
          <SectionLabel>Species</SectionLabel>
          <NameSelect
            value={draft.name}
            onChange={(v) => {
              // a new species keeps the ability only when it can have it
              const next = pokemonData.pokemonAbilities?.[v] ?? [];
              patch({
                name: v,
                gender: genderFor(pokemonData, v, draft.gender),
                ability: next.includes(draft.ability) ? draft.ability : (next[0] ?? ""),
              });
            }}
            items={speciesChoices ?? pokemon}
            itemLabel={displayName}
            placeholder="Search a Pokémon"
            clearable={!!draft.name}
            renderItem={(p) => (
              <span className="flex items-center gap-2">
                {nameToId[p] ? (
                  <Sprite srcs={pokIcon(nameToId[p])} alt="" width={32} height={24} />
                ) : (
                  <span className="w-8" />
                )}
                {displayName(p)}
              </span>
            )}
          />
        </div>
      )}

      <div>
        <SectionLabel>Ability</SectionLabel>
        {draft.name && abilityChoices.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {abilityChoices.map((a) => (
              <button
                key={a}
                onClick={() => patch({ ability: a })}
                className={cn(
                  "h-9 rounded-lg px-4 text-sm font-medium ring-1 transition-colors ring-inset cursor-pointer",
                  draft.ability === a
                    ? "bg-primary/18 text-foreground ring-primary/50"
                    : "bg-foreground/4 text-muted-foreground ring-foreground/10 hover:bg-foreground/8 hover:text-foreground",
                )}
              >
                {a}
              </button>
            ))}
          </div>
        ) : (
          <NameSelect
            value={draft.ability}
            onChange={(v) => patch({ ability: v })}
            items={abilities}
            placeholder="Choose a species first, or search any ability"
            clearable={!!draft.ability}
          />
        )}
      </div>

      <div>
        <SectionLabel>Nature</SectionLabel>
        <div className="grid grid-cols-[44px_repeat(5,minmax(0,1fr))] gap-1 text-xs">
          <span />
          {NATURE_STATS.map((s) => (
            <span key={s} className={cn("pb-0.5 text-center text-[10px] font-semibold", DOWN)}>
              −{STAT_SHORT[s]}
            </span>
          ))}
          {NATURE_STATS.map((up) => (
            <div key={up} className="contents">
              <span className={cn("flex items-center text-[10px] font-semibold", UP)}>
                +{STAT_SHORT[up]}
              </span>
              {NATURE_STATS.map((down) => {
                const n = natureAt(up, down);
                const neutral = up === down;
                const selected = draft.nature === n;
                return (
                  <button
                    key={down}
                    onClick={() => n && patch({ nature: n })}
                    className={cn(
                      "h-8 truncate rounded-md px-1 transition-colors cursor-pointer",
                      selected
                        ? "bg-primary font-semibold text-primary-foreground shadow-[0_0_14px_-4px_var(--primary)]"
                        : neutral
                          ? "bg-foreground/3 text-subtle-foreground hover:bg-foreground/8"
                          : "bg-foreground/6 text-foreground/85 hover:bg-foreground/12",
                    )}
                  >
                    {n}
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── MOVES page: four battle-style slots + a move list ─────────────────────────

function MoveSlotCard({
  move,
  ivs,
  pokemonData,
  active,
  onClick,
  onClear,
}: {
  move: string;
  ivs: IVs;
  pokemonData: PokemonData;
  active: boolean;
  onClick: () => void;
  onClear: () => void;
}) {
  const info = move ? moveInfoFor(pokemonData.moveInfo, move, ivs) : undefined;
  if (!move) {
    return (
      <button
        onClick={onClick}
        className={cn(
          "flex h-[72px] items-center justify-center rounded-xl border border-dashed text-sm text-subtle-foreground transition-colors cursor-pointer hover:border-foreground/25 hover:text-muted-foreground",
          active && "border-primary/60 text-primary",
        )}
      >
        {active ? "Pick a move below" : "Empty slot"}
      </button>
    );
  }
  const color = typeColor(info?.type);
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => e.key === "Enter" && onClick()}
      className={cn(
        "group relative flex h-[72px] cursor-pointer flex-col justify-between overflow-hidden rounded-xl p-2.5 pl-3 ring-1 transition-all ring-inset",
        active ? "ring-2 ring-primary" : "hover:brightness-110",
      )}
      style={{
        background: `linear-gradient(135deg, color-mix(in oklab, ${color} 42%, var(--card)), color-mix(in oklab, ${color} 12%, var(--card)))`,
        ...(active ? {} : { boxShadow: `inset 0 0 0 1px color-mix(in oklab, ${color} 45%, transparent)` }),
      }}
    >
      <div className="flex items-center gap-2 pr-6">
        <span className="truncate text-[15px] font-semibold tracking-tight">{move}</span>
      </div>
      <div className="flex items-center gap-2 text-[11px] text-foreground/75">
        {info?.type && <TypeBadge type={info.type} height={14} />}
        <CategoryIcon category={info?.category} />
        <span className="num ml-auto">
          {info?.power ? `${info.power} BP` : "—"} ·{" "}
          {info?.accuracy === true ? "—" : `${info?.accuracy ?? "—"}%`} · {info?.pp ?? "—"} PP
        </span>
      </div>
      <button
        onClick={(e) => {
          e.stopPropagation();
          onClear();
        }}
        className="absolute top-1.5 right-1.5 flex size-5 items-center justify-center rounded-md text-foreground/60 opacity-0 transition-opacity group-hover:opacity-100 hover:bg-black/25 hover:text-foreground cursor-pointer"
        aria-label={`Forget ${move}`}
      >
        <X className="size-3.5" />
      </button>
    </div>
  );
}

function MovesPage({
  draft,
  patch,
  pokemonData,
}: {
  draft: Draft;
  patch: (p: Partial<Draft>) => void;
  pokemonData: PokemonData;
}) {
  const firstEmpty = draft.moves.findIndex((m) => !m);
  const [active, setActive] = useState(firstEmpty === -1 ? 0 : firstEmpty);
  const [query, setQuery] = useState("");
  const moveInfo = pokemonData.moveInfo ?? {};

  const list = useMemo(() => {
    const q = query.trim().toLowerCase();
    return pokemonData.moves.filter((m) => !q || m.toLowerCase().includes(q));
  }, [pokemonData.moves, query]);

  function setMove(i: number, v: string) {
    const moves = [...draft.moves];
    moves[i] = v;
    patch({ moves });
    // jump to the next empty slot, like teaching moves one after another
    const next = moves.findIndex((m, j) => !m && j !== i);
    if (v && next !== -1) setActive(next);
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2.5">
        {draft.moves.map((m, i) => (
          <MoveSlotCard
            key={i}
            move={m}
            ivs={draft.ivs}
            pokemonData={pokemonData}
            active={active === i}
            onClick={() => setActive(i)}
            onClear={() => {
              setMove(i, "");
              setActive(i);
            }}
          />
        ))}
      </div>

      <div className="rounded-xl ring-1 ring-foreground/8">
        <div className="flex items-center gap-2 border-b px-3 py-2">
          <Search className="size-3.5 text-subtle-foreground" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={`Search a move for slot ${active + 1}`}
            className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-subtle-foreground"
          />
          <span className="num text-[11px] text-subtle-foreground">{list.length}</span>
        </div>
        <div className="max-h-[208px] overflow-y-auto p-1">
          {list.map((m) => {
            const info = moveInfoFor(moveInfo, m, draft.ivs);
            const known = draft.moves.includes(m);
            return (
              <button
                key={m}
                disabled={known}
                onClick={() => setMove(active, m)}
                className={cn(
                  "flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left text-sm transition-colors",
                  known ? "opacity-40" : "cursor-pointer hover:bg-foreground/6",
                )}
              >
                <span className="w-[68px] shrink-0">
                  {info?.type && <TypeBadge type={info.type} height={14} />}
                </span>
                <span className="flex-1 truncate">{m}</span>
                <CategoryIcon category={info?.category} />
                <span className="num w-10 text-right text-xs text-muted-foreground">
                  {info?.power || "—"}
                </span>
                <span className="num w-10 text-right text-xs text-muted-foreground">
                  {info?.accuracy === true ? "—" : (info?.accuracy ?? "—")}
                </span>
                <span className="num w-8 text-right text-xs text-subtle-foreground">
                  {info?.pp ?? ""}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ─── STATS page: IV sliders and the resulting stats ────────────────────────────

function StatsPage({
  draft,
  patch,
  pokemonData,
}: {
  draft: Draft;
  patch: (p: Partial<Draft>) => void;
  pokemonData: PokemonData;
}) {
  const stats = calculateStats(
    draft.name,
    draft.level,
    draft.nature,
    draft.ivs,
    pokemonData.baseStats,
    pokemonData.natureMultipliers,
  );
  const base = pokemonData.baseStats[draft.name];
  const mults = pokemonData.natureMultipliers[draft.nature] ?? {};
  const hp = hiddenPower(draft.ivs);
  const setIv = (s: keyof IVs, v: number) =>
    patch({ ivs: { ...draft.ivs, [s]: Math.max(0, Math.min(31, v)) } });
  const setAll = (v: number) =>
    patch({ ivs: Object.fromEntries(STAT_KEYS.map((k) => [k, v])) as unknown as IVs });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <SectionLabel>Individual values</SectionLabel>
        <div className="-mt-2 flex gap-1.5">
          <Button variant="outline" size="xs" onClick={() => setAll(31)}>
            All 31
          </Button>
          <Button variant="outline" size="xs" onClick={() => setAll(0)}>
            All 0
          </Button>
        </div>
      </div>

      <div className="space-y-1.5">
        <div className="grid grid-cols-[44px_1fr_48px_44px_52px] gap-3 px-1 text-[10px] tracking-wider text-subtle-foreground uppercase">
          <span>Stat</span>
          <span>IV</span>
          <span />
          <span className="text-right">Base</span>
          <span className="text-right">Lv {draft.level}</span>
        </div>
        {STAT_KEYS.map((k) => {
          const m = mults[k] ?? 1;
          const tone = m > 1 ? UP : m < 1 ? DOWN : "text-foreground";
          const iv = draft.ivs[k];
          return (
            <div
              key={k}
              className="grid grid-cols-[44px_1fr_48px_44px_52px] items-center gap-3 rounded-lg bg-foreground/3 px-1 py-1.5"
            >
              <span className={cn("pl-1 text-xs font-semibold", tone)}>
                {STAT_SHORT[k]}
                {m > 1 ? " ↑" : m < 1 ? " ↓" : ""}
              </span>
              <input
                type="range"
                min={0}
                max={31}
                value={iv}
                onChange={(e) => setIv(k, parseInt(e.target.value))}
                className="w-full cursor-pointer accent-(--primary)"
                aria-label={`${k} IV`}
              />
              <input
                type="number"
                min={0}
                max={31}
                value={iv}
                onChange={(e) => setIv(k, parseInt(e.target.value) || 0)}
                className={cn(
                  "num h-7 w-full rounded-md border border-input bg-input/30 text-center text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50",
                  iv < 31 ? "text-warn" : "text-foreground",
                )}
              />
              <span className="num text-right text-xs text-subtle-foreground">{base?.[k] ?? "—"}</span>
              <span className={cn("num pr-1 text-right text-base font-semibold", tone)}>
                {stats?.[k] ?? "—"}
              </span>
            </div>
          );
        })}
      </div>

      <div className="flex items-center gap-2 rounded-lg bg-foreground/4 px-3 py-2 text-xs text-muted-foreground ring-1 ring-foreground/8">
        Hidden Power from these IVs:
        <TypeBadge type={hp.type} height={14} />
        <span className="num font-semibold text-foreground">{hp.power}</span> BP
      </div>
    </div>
  );
}

// ─── Exported dialog ──────────────────────────────────────────────────────────

export default function BoxEditor({
  entry,
  draft: initial,
  pokemonData,
  catching = false,
  speciesChoices,
  onSave,
  onCancel,
}: {
  entry: BoxEntry | null;
  draft: Draft;
  pokemonData: PokemonData;
  catching?: boolean; // a new catch from the Tracker: the species is set, the moves follow the level
  speciesChoices?: string[]; // what the species can change to, any by default
  onSave: (entry: BoxEntry) => void;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState<Draft>(() => ({
    ...initial,
    gender: genderFor(pokemonData, initial.name, initial.gender), // a box saved before PkDB knew it
  }));
  const [page, setPage] = useState<Page>("info");
  const [autoMoves, setAutoMoves] = useState(catching); // until a move is edited by hand
  const popupRoot = useRef<HTMLDivElement>(null); // combobox lists mount here, inside the dialog

  function patch(p: Partial<Draft>) {
    if (p.moves) setAutoMoves(false);
    const refill =
      autoMoves && p.level !== undefined
        ? { moves: startingMoves(pokemonData, draft.name, p.level).moves }
        : {};
    setDraft((d) => ({ ...d, ...p, ...refill }));
  }

  const leftOut = autoMoves ? startingMoves(pokemonData, draft.name, draft.level).leftOut : [];
  const moveCount = draft.moves.filter(Boolean).length;
  const missing = [
    !draft.name && "a species",
    !draft.ability && "an ability",
    moveCount === 0 && "a move",
  ].filter(Boolean) as string[];
  const canSave = missing.length === 0;

  const PAGES: { id: Page; label: string; badge?: string }[] = [
    { id: "info", label: "Info" },
    { id: "moves", label: "Moves", badge: `${moveCount}/4` },
    { id: "stats", label: "Stats" },
  ];

  return (
    <Dialog open onOpenChange={(open) => !open && onCancel()}>
      <DialogContent className="gap-0 p-0 sm:max-w-[880px]">
        <DialogTitle className="sr-only">
          {entry ? `Edit ${displayName(entry.name)}` : "Add a Pokémon to the box"}
        </DialogTitle>
        <DialogDescription className="sr-only">
          Species, ability, nature, moves and IVs of a box Pokémon
        </DialogDescription>
        <div ref={popupRoot} />
        <ComboboxPortalContainer.Provider value={popupRoot}>
          <div className="flex overflow-hidden rounded-[inherit]">
            <ProfilePanel draft={draft} patch={patch} pokemonData={pokemonData} />

            <div className="flex min-h-[560px] min-w-0 flex-1 flex-col">
              {/* summary pages */}
              <div className="flex items-center gap-1 border-b px-5 pt-4">
                {PAGES.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => setPage(p.id)}
                    className={cn(
                      "relative -mb-px flex items-center gap-1.5 border-b-2 px-3 pb-2.5 text-xs font-semibold tracking-widest uppercase transition-colors cursor-pointer",
                      page === p.id
                        ? "border-primary text-foreground"
                        : "border-transparent text-subtle-foreground hover:text-muted-foreground",
                    )}
                  >
                    {p.label}
                    {p.badge && (
                      <span className="num rounded bg-foreground/8 px-1 text-[10px] tracking-normal">
                        {p.badge}
                      </span>
                    )}
                  </button>
                ))}
              </div>

              <div className="min-h-0 flex-1 overflow-y-auto p-5">
                {page === "info" && (
                  <InfoPage
                    draft={draft}
                    patch={patch}
                    pokemonData={pokemonData}
                    catching={catching}
                    speciesChoices={speciesChoices}
                  />
                )}
                {page === "moves" && <MovesPage draft={draft} patch={patch} pokemonData={pokemonData} />}
                {page === "stats" && <StatsPage draft={draft} patch={patch} pokemonData={pokemonData} />}
              </div>

              <div className="flex items-center gap-3 border-t px-5 py-3">
                <span className="text-xs text-subtle-foreground">
                  {canSave ? "Ready to store in the box." : `Still needs ${missing.join(", ")}.`}
                  {leftOut.length > 0 && (
                    <span className="block text-warn">Not in the engine yet, left out: {leftOut.join(", ")}.</span>
                  )}
                </span>
                <div className="ml-auto flex gap-2">
                  <Button variant="outline" onClick={onCancel}>
                    Cancel
                  </Button>
                  <Button
                    disabled={!canSave}
                    onClick={() => canSave && onSave({ ...draft, id: entry?.id ?? crypto.randomUUID() })}
                  >
                    <PokeballIcon />
                    {entry ? "Save changes" : "Store in box"}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </ComboboxPortalContainer.Provider>
      </DialogContent>
    </Dialog>
  );
}
