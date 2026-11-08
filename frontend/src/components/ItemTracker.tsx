import { Fragment, useState, type ReactNode } from "react";
import { Check, Package, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { itemIcon, tmIcon } from "@/lib/sprites";
import type { ItemLocationDB, ItemPickup, NuzlockeRun, PickupKind } from "../types";
import { Button } from "./ui/button";
import { Sprite } from "./common/Sprite";

const KINDS: { kind: PickupKind; label: string }[] = [
  { kind: "item", label: "Items" },
  { kind: "key", label: "Rods" },
  { kind: "tm", label: "TMs" },
];

const pickupName = (p: ItemPickup) => (p.move ? `${p.item} ${p.move}` : p.item);

function pickupIcon(p: ItemPickup): string[] {
  if (p.kind === "tm" && p.type) return tmIcon(p.item.startsWith("HM") ? "HM" : "TM", p.type);
  return itemIcon(p.item);
}

// A location's rows by area, the unnamed one first
function byArea(pickups: ItemPickup[]): { area: string; rows: ItemPickup[] }[] {
  const groups = new Map<string, ItemPickup[]>([["", []]]);
  for (const p of pickups) {
    if (!groups.has(p.area)) groups.set(p.area, []);
    groups.get(p.area)!.push(p);
  }
  return [...groups]
    .map(([area, rows]) => ({ area, rows }))
    .filter((g) => g.rows.length);
}

function PickupRow({
  pickup,
  picked,
  onToggle,
}: {
  pickup: ItemPickup;
  picked: boolean;
  onToggle: () => void;
}) {
  const detail = pickup.how;
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={picked}
      title={picked ? "Picked up. Click to undo" : "Mark as picked up"}
      className="flex min-h-9 w-full min-w-0 cursor-pointer items-center gap-2 rounded-lg px-1.5 py-1 text-left transition-colors hover:bg-foreground/10"
    >
      <span
        className={cn(
          "flex size-4 shrink-0 items-center justify-center rounded-full ring-1 transition-colors",
          picked ? "bg-good text-background ring-good" : "ring-foreground/25",
        )}
      >
        {picked && <Check className="size-3" strokeWidth={3} />}
      </span>
      <span className="flex size-6 shrink-0 items-center justify-center">
        <Sprite
          srcs={pickupIcon(pickup)}
          alt=""
          width={24}
          height={24}
          className={cn("transition-opacity", picked && "opacity-40")}
          fallback={<Package className="size-4 text-subtle-foreground" />}
        />
      </span>
      <span className="flex min-w-0 flex-col">
        <span
          className={cn(
            "truncate text-xs font-medium",
            picked && "text-subtle-foreground",
          )}
        >
          {pickup.kind === "tm" ? (
            <>
              <span className="num text-muted-foreground">{pickup.item}</span>{" "}
              {pickup.move}
            </>
          ) : (
            pickup.item
          )}
        </span>
        {detail && (
          <span className="truncate text-[11px] text-subtle-foreground" title={detail}>
            {detail}
          </span>
        )}
      </span>
    </button>
  );
}

// One location: its name on the left, its pickups in as many columns as fit
function LocationSection({
  name,
  pickups,
  total,
  picked,
  onToggle,
}: {
  name: string;
  pickups: ItemPickup[]; // the rows shown
  total: ItemPickup[]; // every row of the kinds shown, for the count
  picked: Set<string>;
  onToggle: (id: string) => void;
}) {
  const done = total.filter((p) => picked.has(p.id)).length;
  const complete = done === total.length;
  return (
    <section className="grid gap-x-4 px-3 py-2.5 sm:grid-cols-[170px_minmax(0,1fr)]">
      <div className="flex items-baseline gap-2 px-1.5 py-1.5 sm:flex-col sm:gap-0.5">
        <span
          className={cn(
            "truncate text-[13px] font-semibold",
            complete && "text-muted-foreground",
          )}
          title={name}
        >
          {name}
        </span>
        <span
          className={cn(
            "num text-[11px]",
            complete ? "text-good" : "text-subtle-foreground",
          )}
        >
          {done}/{total.length}
        </span>
      </div>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(250px,1fr))] gap-x-2">
        {byArea(pickups).map(({ area, rows }, g) => (
          <Fragment key={g}>
            {area && (
              <div className="col-span-full px-1.5 pt-1.5 pb-0.5 text-[11px] font-medium text-subtle-foreground">
                {area}
              </div>
            )}
            {rows.map((p) => (
              <PickupRow
                key={p.id}
                pickup={p}
                picked={picked.has(p.id)}
                onToggle={() => onToggle(p.id)}
              />
            ))}
          </Fragment>
        ))}
      </div>
    </section>
  );
}

// ─── Exported: the Tracker's Items tab ────────────────────────────────────────

export default function ItemTracker({
  itemDB,
  run,
  error,
  tabs,
  onRetry,
  onChange,
}: {
  itemDB: ItemLocationDB | null;
  run: NuzlockeRun;
  error: string | null;
  tabs: ReactNode; // the Pokémon / Items switch, at the start of the search bar
  onRetry: () => void;
  onChange: (run: NuzlockeRun) => void;
}) {
  const [query, setQuery] = useState("");
  const [kinds, setKinds] = useState<Set<PickupKind>>(
    () => new Set(KINDS.map((k) => k.kind)),
  );
  const [todoOnly, setTodoOnly] = useState(false);

  const picked = new Set(run.items);
  const locations = Object.entries(itemDB?.locations ?? {});
  const all = locations.flatMap(([, pickups]) => pickups);
  const q = query.trim().toLowerCase();

  function toggle(id: string) {
    onChange({
      ...run,
      items: picked.has(id) ? run.items.filter((i) => i !== id) : [...run.items, id],
    });
  }

  function toggleKind(kind: PickupKind) {
    const next = new Set(kinds);
    if (next.has(kind)) next.delete(kind);
    else next.add(kind);
    setKinds(next);
  }

  // A search finds a location by name, or the rows whose item or move matches
  const shown = locations
    .map(([name, pickups]) => {
      const total = pickups.filter((p) => kinds.has(p.kind));
      const nameHit = !q || name.toLowerCase().includes(q);
      const rows = total.filter(
        (p) =>
          (!todoOnly || !picked.has(p.id)) &&
          (nameHit || pickupName(p).toLowerCase().includes(q)),
      );
      return { name, total, rows };
    })
    .filter((l) => l.rows.length);

  return (
    <div className="mx-auto max-w-6xl px-4 pb-6">
      <div className="sticky top-0 z-20 flex flex-wrap items-center gap-2 bg-background py-3">
        {tabs}
        <div className="flex h-8 min-w-48 flex-1 items-center gap-2 rounded-lg border border-input bg-input/30 px-2 focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50">
          <Search className="size-3.5 text-subtle-foreground" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search a location, an item or a TM's move"
            className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-subtle-foreground"
          />
        </div>
        {KINDS.map(({ kind, label }) => {
          const ofKind = all.filter((p) => p.kind === kind);
          const done = ofKind.filter((p) => picked.has(p.id)).length;
          return (
            <Button
              key={kind}
              variant={kinds.has(kind) ? "secondary" : "ghost"}
              size="sm"
              aria-pressed={kinds.has(kind)}
              title={`${kinds.has(kind) ? "Hide" : "Show"} ${label.toLowerCase()}`}
              onClick={() => toggleKind(kind)}
            >
              {label}
              <span className="num text-[11px] text-subtle-foreground">
                {done}/{ofKind.length}
              </span>
            </Button>
          );
        })}
        <Button
          variant={todoOnly ? "secondary" : "ghost"}
          size="sm"
          aria-pressed={todoOnly}
          title="Hide what you already picked up"
          onClick={() => setTodoOnly(!todoOnly)}
        >
          Still to pick up
        </Button>
      </div>

      {!itemDB ? (
        <div className="flex flex-col items-center gap-3 py-8 text-center">
          <p className="text-sm text-muted-foreground">
            {error ? `Couldn't load the item locations: ${error}` : "Loading the item locations…"}
          </p>
          {error && (
            <Button variant="outline" size="sm" onClick={onRetry}>
              Try again
            </Button>
          )}
        </div>
      ) : (
        <>
          <div className={cn("divide-y rounded-xl border bg-card", !shown.length && "hidden")}>
            {shown.map(({ name, total, rows }) => (
              <LocationSection
                key={name}
                name={name}
                pickups={rows}
                total={total}
                picked={picked}
                onToggle={toggle}
              />
            ))}
          </div>
          {shown.length === 0 && (
            <p className="py-8 text-center text-sm text-subtle-foreground">
              {todoOnly && !q ? "Everything shown is picked up." : "Nothing matches."}
            </p>
          )}
        </>
      )}
    </div>
  );
}
