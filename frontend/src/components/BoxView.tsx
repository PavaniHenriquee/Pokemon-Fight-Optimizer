import { useState } from "react";
import { Check, ChevronLeft, ChevronRight, HeartPulse, Pencil, Plus, Save, Search, Skull, Trash2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { battleSprite, pokIcon } from "@/lib/sprites";
import { displayName } from "@/lib/format";
import { moveInfoFor } from "@/lib/hiddenPower";
import { makeBlank } from "@/lib/nuzlocke";
import type { BoxEntry, PokemonConfig, PokemonData } from "../types";
import { Button } from "./ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "./ui/tooltip";
import { Sprite } from "./common/Sprite";
import { GenderMark, PokeballIcon, TypeBadges, TypeIcon } from "./common/Badges";
import BoxEditor from "./BoxEditor";
import { StatBars } from "./PokemonSlots";

const SLOTS = 30; // a PC box: 6 × 5
const WALLPAPER_HUES = [250, 155, 25, 345, 65, 200];
const DEATH_BOX_HUE = 15;

// ─── Summary of the hovered / selected Pokémon ────────────────────────────────

function Summary({
  entry,
  pokemonData,
  inTeam,
  teamFull,
  onToggle,
  onEdit,
  onSetDead,
  onDelete,
}: {
  entry: BoxEntry | null;
  pokemonData: PokemonData;
  inTeam: boolean;
  teamFull: boolean;
  onToggle: () => void;
  onEdit: () => void;
  onSetDead: (dead: boolean) => void;
  onDelete: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  // a different Pokémon resets the confirmation
  const [shownId, setShownId] = useState(entry?.id);
  if (entry?.id !== shownId) {
    setShownId(entry?.id);
    setConfirming(false);
  }

  if (!entry) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 rounded-xl border border-dashed p-4 text-center">
        <PokeballIcon className="size-6 opacity-40 grayscale" />
        <p className="text-xs text-subtle-foreground">
          Hover a Pokémon to see its summary. Click to add it to your party or take it out, right-click
          to edit it.
        </p>
      </div>
    );
  }

  const id = pokemonData.nameToId[entry.name];
  const moveInfo = pokemonData.moveInfo;
  return (
    <div className="flex h-full flex-col rounded-xl border bg-card p-3">
      {/* the negative margin: a tall sprite at 2× may reach into the card's padding */}
      <div className="min-h-0 flex-1 overflow-y-auto roomy:-mt-3 roomy:pt-3">
        <div className="flex gap-3 roomy:flex-col roomy:gap-1">
          <div className="relative flex size-[84px] shrink-0 items-end justify-center pb-1.5 roomy:h-[152px] roomy:w-full">
            <div
              className="absolute bottom-0.5 left-1/2 h-5 w-20 -translate-x-1/2 rounded-[50%] roomy:h-8 roomy:w-44"
              style={{ background: "radial-gradient(closest-side, oklch(1 0 0 / 12%), transparent)" }}
            />
            {id && (
              <Sprite
                key={id}
                srcs={battleSprite(id, "front")}
                alt={entry.name}
                className={cn(
                  "relative max-h-[84px] max-w-[96px] roomy:origin-bottom roomy:scale-200",
                  entry.dead && "grayscale",
                )}
              />
            )}
          </div>
          <div className="min-w-0 flex-1">
            <div className="roomy:flex roomy:items-baseline roomy:gap-2">
              <div className="flex min-w-0 items-center gap-1.5">
                <span className="truncate text-[15px] font-semibold tracking-tight roomy:text-xl">
                  {displayName(entry.name)}
                </span>
                <GenderMark gender={entry.gender} className="roomy:text-lg" />
              </div>
              <div className="num text-xs text-subtle-foreground roomy:text-sm">Lv {entry.level}</div>
            </div>
            <TypeBadges
              types={pokemonData.pokemonTypes?.[entry.name]}
              height={14}
              className="mt-1 roomy:[&_img]:h-[18px]!"
            />
            <div className="mt-1 truncate text-[11px] text-muted-foreground roomy:text-sm">
              {entry.ability} · {entry.nature}
            </div>
          </div>
        </div>

        <StatBars pokemon={entry} pokemonData={pokemonData} className="mt-2 hidden roomy-tall:block" />

        <div className="mt-2.5 grid grid-cols-2 gap-1 roomy:mt-2">
          {entry.moves.map((m, i) => (
            <span
              key={i}
              className={cn(
                "flex items-center gap-1.5 truncate rounded-md px-2 py-1 text-[11px] roomy:text-[13px] roomy:leading-4",
                m ? "bg-foreground/5" : "text-subtle-foreground italic",
              )}
            >
              {m && <TypeIcon type={moveInfoFor(moveInfo, m, entry.ivs)?.type} />}
              <span className="truncate">{m || "—"}</span>
            </span>
          ))}
        </div>
      </div>

      {entry.dead ? (
        <div className="mt-auto flex gap-1.5 pt-3">
          <Button variant="outline" size="sm" className="flex-1" onClick={() => onSetDead(false)}>
            <HeartPulse />
            Revive
          </Button>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant={confirming ? "destructive" : "ghost"}
                size={confirming ? "sm" : "icon-sm"}
                onClick={() => {
                  if (confirming) onDelete();
                  else setConfirming(true);
                }}
                aria-label="Delete"
              >
                <Trash2 />
                {confirming && "Delete?"}
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              {confirming
                ? "Click again to delete: its evolution line can be caught again"
                : "Delete for good (it stops counting for the species clause)"}
            </TooltipContent>
          </Tooltip>
        </div>
      ) : (
        <div className="mt-auto flex gap-1.5 pt-3">
          <Button
            size="sm"
            variant={inTeam ? "outline" : "default"}
            className="flex-1"
            onClick={onToggle}
            disabled={!inTeam && teamFull}
          >
            {inTeam ? <X /> : <PokeballIcon />}
            {inTeam ? "Remove from party" : teamFull ? "Party full" : "Add to party"}
          </Button>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="outline" size="icon-sm" onClick={onEdit} aria-label="Edit">
                <Pencil />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Edit</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant={confirming ? "destructive" : "ghost"}
                size={confirming ? "sm" : "icon-sm"}
                onClick={() => {
                  if (confirming) onSetDead(true);
                  else setConfirming(true);
                }}
                aria-label="Move to death box"
              >
                <Skull />
                {confirming && "It died?"}
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              {confirming ? "Click again to move it to the death box" : "Move to death box"}
            </TooltipContent>
          </Tooltip>
        </div>
      )}
    </div>
  );
}

// ─── Exported: the box as a PC-box side rail ──────────────────────────────────

export default function BoxView({
  box,
  pokemonData,
  onBoxChange,
  onEdited,
  onSave,
  onClear,
  onSetDead,
  onDelete,
  dirty,
  saved,
  team,
  onToggle,
}: {
  box: BoxEntry[];
  pokemonData: PokemonData;
  onBoxChange: (box: BoxEntry[]) => void;
  onEdited: (before: BoxEntry, after: BoxEntry) => void;
  onSave: () => void;
  onClear: () => void;
  onSetDead: (entry: BoxEntry, dead: boolean) => void;
  onDelete: (entry: BoxEntry) => void;
  dirty: boolean;
  saved: boolean;
  team: PokemonConfig[];
  onToggle: (entry: BoxEntry) => void; // in or out of the party
}) {
  const [editEntry, setEditEntry] = useState<BoxEntry | "new" | null>(null);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const [hovered, setHovered] = useState<BoxEntry | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [confirmingClear, setConfirmingClear] = useState(false);
  const [showDead, setShowDead] = useState(false); // the death box instead of the PC box
  const { nameToId } = pokemonData;

  const alive = box.filter((e) => !e.dead);
  const dead = box.filter((e) => e.dead);
  const pool = showDead ? dead : alive;
  const q = query.trim().toLowerCase();
  const shown = q ? pool.filter((e) => displayName(e.name).toLowerCase().includes(q)) : pool;
  const pageCount = Math.max(1, Math.ceil(shown.length / SLOTS));
  const current = Math.min(page, pageCount - 1);
  const slots = shown.slice(current * SLOTS, current * SLOTS + SLOTS);
  const hue = showDead ? DEATH_BOX_HUE : WALLPAPER_HUES[current % WALLPAPER_HUES.length];

  function switchBox(toDead: boolean) {
    setShowDead(toDead);
    setPage(0);
    setHovered(null);
    setSelectedId(null);
  }

  const selected = box.find((e) => e.id === selectedId) ?? null;
  const focus = hovered ?? selected;
  const teamFull = team.length >= 6;
  const inTeam = (e: BoxEntry) => team.some((t) => t.name === e.name);

  return (
    <aside className="flex min-h-0 flex-col border-r bg-card/40">
      <div className="flex h-11 shrink-0 items-center gap-2 border-b px-3">
        <div className="flex rounded-md bg-background/60 p-0.5 ring-1 ring-border">
          {[
            { toDead: false, label: "PC Box", count: alive.length },
            { toDead: true, label: "Death Box", count: dead.length },
          ].map((tab) => (
            <button
              key={tab.label}
              type="button"
              aria-pressed={showDead === tab.toDead}
              onClick={() => switchBox(tab.toDead)}
              className={cn(
                "h-6 cursor-pointer rounded px-1.5 text-[11px] font-medium whitespace-nowrap transition-colors",
                showDead === tab.toDead
                  ? "bg-elevated text-foreground ring-1 ring-foreground/10"
                  : "text-subtle-foreground hover:text-foreground",
              )}
            >
              {tab.label} <span className="num opacity-70">{tab.count}</span>
            </button>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-1">
          <Tooltip>
            <TooltipTrigger asChild>
              {/* span wrapper: a disabled button doesn't fire hover events */}
              <span>
                <Button
                  variant={confirmingClear ? "destructive" : "ghost"}
                  size={confirmingClear ? "sm" : "icon-sm"}
                  disabled={box.length === 0}
                  onClick={() => {
                    if (!confirmingClear) {
                      setConfirmingClear(true);
                      return;
                    }
                    onClear();
                    setConfirmingClear(false);
                    setQuery("");
                    setPage(0);
                    setHovered(null);
                    setSelectedId(null);
                  }}
                  onMouseLeave={() => setConfirmingClear(false)}
                  aria-label="Clear box"
                >
                  <Trash2 />
                  {confirmingClear && "Clear?"}
                </Button>
              </span>
            </TooltipTrigger>
            <TooltipContent>
              {box.length === 0
                ? "The box is already empty"
                : confirmingClear
                  ? "Click again to delete the whole box, death box and party"
                  : "Clear box, death box and party"}
            </TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon-sm" onClick={onSave} aria-label="Save box" className="relative">
                {saved ? <Check className="text-good" /> : <Save />}
                {dirty && !saved && (
                  <span className="absolute top-1 right-1 size-1.5 rounded-full bg-warn" />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent>{dirty ? "Save box (unsaved changes)" : "Save box"}</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button size="icon-sm" onClick={() => setEditEntry("new")} aria-label="New Pokémon">
                <Plus />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Store a new Pokémon</TooltipContent>
          </Tooltip>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-2 p-2">
        <div className="flex h-8 shrink-0 items-center gap-2 rounded-lg border border-input bg-input/30 px-2 focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50">
          <Search className="size-3.5 text-subtle-foreground" />
          <input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(0); // a search starts again from the first box
            }}
            placeholder={showDead ? "Search death box" : "Search box"}
            className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-subtle-foreground"
          />
        </div>

        {/* the box */}
        <div
          className="shrink-0 overflow-hidden rounded-xl ring-1"
          style={{ boxShadow: `inset 0 0 0 1px oklch(0.6 0.08 ${hue} / 35%)` }}
        >
          <div
            className="flex h-8 items-center justify-between px-1"
            style={{ background: `oklch(0.34 0.07 ${hue})` }}
          >
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={() => setPage((current - 1 + pageCount) % pageCount)}
              disabled={pageCount === 1}
              aria-label="Previous box"
            >
              <ChevronLeft />
            </Button>
            <span className="text-xs font-bold tracking-[0.2em] text-white/90 uppercase">
              {q ? "Search" : showDead ? "Death Box" : `Box ${current + 1}`}
              {pageCount > 1 && (
                <span className="num ml-1.5 font-medium tracking-normal text-white/50">
                  {current + 1}/{pageCount}
                </span>
              )}
            </span>
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={() => setPage((current + 1) % pageCount)}
              disabled={pageCount === 1}
              aria-label="Next box"
            >
              <ChevronRight />
            </Button>
          </div>
          <div
            className="grid grid-cols-6 gap-0.5 p-1.5"
            style={{
              background: [
                `radial-gradient(ellipse 80% 60% at 50% 0%, oklch(0.42 0.08 ${hue} / 35%), transparent 70%)`,
                `repeating-linear-gradient(45deg, oklch(0.25 0.04 ${hue}) 0 9px, oklch(0.225 0.035 ${hue}) 9px 18px)`,
              ].join(", "),
            }}
            onMouseLeave={() => setHovered(null)}
          >
            {Array.from({ length: SLOTS }).map((_, i) => {
              const entry = slots[i];
              if (!entry) {
                return <div key={`empty-${i}`} className="aspect-square rounded-md bg-black/10" />;
              }
              const id = nameToId[entry.name];
              const isSelected = entry.id === selectedId;
              const member = inTeam(entry);
              return (
                <button
                  key={entry.id}
                  onMouseEnter={() => setHovered(entry)}
                  onClick={() => {
                    setSelectedId(entry.id);
                    onToggle(entry);
                  }}
                  onContextMenu={(e) => {
                    e.preventDefault();
                    setSelectedId(entry.id);
                    if (!entry.dead) setEditEntry(entry);
                  }}
                  title={displayName(entry.name)}
                  className={cn(
                    "group relative flex aspect-square items-center justify-center rounded-md transition-colors cursor-pointer",
                    isSelected
                      ? "bg-white/20 ring-2 ring-white/70"
                      : member
                        ? "bg-best/15 ring-2 ring-best/90 hover:bg-best/25"
                        : "bg-black/10 hover:bg-white/12",
                  )}
                >
                  {id && (
                    <Sprite
                      srcs={pokIcon(id)}
                      alt={entry.name}
                      width={40}
                      height={30}
                      className={cn(
                        "pointer-events-none max-w-none shrink-0 roomy:h-[60px] roomy:w-20",
                        entry.dead ? "opacity-70 grayscale" : "group-hover:animate-hop",
                        isSelected && !entry.dead && "animate-hop",
                      )}
                    />
                  )}
                  {member && (
                    <PokeballIcon className="absolute right-0 bottom-0 size-2.5 roomy:size-3.5" />
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {pool.length === 0 && (
          <p className="text-center text-[11px] text-subtle-foreground">
            {showDead
              ? "No deaths. A Pokémon moved here still counts for the species clause."
              : "The box is empty: use + to store the Pokémon you've caught."}
          </p>
        )}

        <div className="min-h-[220px] flex-1">
          <Summary
            entry={focus}
            pokemonData={pokemonData}
            inTeam={focus ? inTeam(focus) : false}
            teamFull={teamFull}
            onToggle={() => focus && onToggle(focus)}
            onEdit={() => focus && setEditEntry(focus)}
            onSetDead={(toDead) => {
              if (!focus) return;
              onSetDead(focus, toDead);
              setHovered(null);
              setSelectedId(null);
            }}
            onDelete={() => {
              if (!focus) return;
              onDelete(focus);
              setHovered(null);
              setSelectedId(null);
            }}
          />
        </div>
      </div>

      {editEntry !== null && (
        <BoxEditor
          entry={editEntry === "new" ? null : editEntry}
          draft={
            editEntry === "new"
              ? makeBlank()
              : { ...editEntry, moves: [...editEntry.moves], ivs: { ...editEntry.ivs } }
          }
          pokemonData={pokemonData}
          onSave={(entry) => {
            onBoxChange(
              editEntry === "new"
                ? [...box, entry]
                : box.map((e) => (e.id === entry.id ? entry : e)),
            );
            if (editEntry !== "new") onEdited(editEntry, entry);
            setSelectedId(entry.id);
            setEditEntry(null);
          }}
          onCancel={() => setEditEntry(null)}
        />
      )}
    </aside>
  );
}
