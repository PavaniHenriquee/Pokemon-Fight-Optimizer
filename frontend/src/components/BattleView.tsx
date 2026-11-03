import {
  ArrowRightLeft,
  CloudHail,
  CloudRain,
  CornerDownRight,
  GitBranchPlus,
  Orbit,
  RotateCcw,
  Skull,
  Sun,
  TriangleAlert,
  Trophy,
  Wind,
} from "lucide-react";
import { HoverCard, HoverCardTrigger, HoverCardContent } from "./ui/hover-card";
import { Button } from "./ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "./ui/tooltip";
import { cn } from "@/lib/utils";
import { battleSprite, pokIcon } from "@/lib/sprites";
import { displayName, fmtInt, statusColor, switchTarget } from "@/lib/format";
import { bestActionKey } from "@/lib/tree";
import type { TreeNode, PokemonState, BenchEntry, SnapshotData, SideEffect } from "../types";
import { Sprite } from "./common/Sprite";
import { HpBar } from "./common/HpBar";
import { WinRing } from "./common/WinRing";
import { ItemIcon } from "./common/ItemIcon";
import { MoveList } from "./common/MoveList";
import {
  Chip,
  SideChips,
  StageChips,
  StatusBadge,
  TypeBadges,
  TypeDot,
  VolatileChips,
} from "./common/Badges";

const WEATHER_ICON: Record<string, typeof Sun> = {
  Sun,
  Rain: CloudRain,
  Hail: CloudHail,
  Sandstorm: Wind,
};

// ── Field strip: turn, weather, Gravity, trainer items ────────────────────────
function FieldStrip({ snapshot }: { snapshot: SnapshotData }) {
  const field = snapshot.field;
  const WeatherIcon = field?.weather ? WEATHER_ICON[field.weather] : undefined;
  const items = snapshot.trainer_items?.filter(Boolean) ?? [];
  return (
    <div className="flex items-center gap-2">
      <span className="num rounded-md bg-foreground/6 px-2 py-0.5 text-xs font-semibold text-foreground ring-1 ring-foreground/10 ring-inset">
        Turn {snapshot.turn}
      </span>
      {field?.weather && (
        <Chip
          tone="info"
          title={field.weather_turns > 0 ? `${field.weather_turns} turn(s) left` : "Permanent"}
        >
          {WeatherIcon && <WeatherIcon className="size-3" />}
          {field.weather}
          {field.weather_turns > 0 && <span className="opacity-70">· {field.weather_turns}</span>}
        </Chip>
      )}
      {!!field?.gravity_turns && (
        <Chip tone="primary" title={`${field.gravity_turns} turn(s) left`}>
          <Orbit className="size-3" />
          Gravity <span className="opacity-70">· {field.gravity_turns}</span>
        </Chip>
      )}
      {snapshot.terminal && <Chip tone="warn">Terminal</Chip>}
      {items.length > 0 && (
        <div className="ml-auto flex items-center gap-1.5">
          <span className="text-[10px] font-medium tracking-wider text-subtle-foreground uppercase">
            Trainer items
          </span>
          {items.map((item, i) => (
            <ItemIcon key={i} name={item} size={22} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── What just happened ─────────────────────────────────────────────────────────
function EventLines({ snapshot }: { snapshot: SnapshotData }) {
  const isDeath = snapshot.phase === "DEATH";
  if (!isDeath && snapshot.phase !== "BATON_PASS" && !snapshot.opp_move) return null;
  return (
    <div className="flex flex-wrap items-center gap-2">
      {isDeath && (
        <div className="flex items-center gap-2 rounded-lg bg-bad/10 px-3 py-1.5 text-xs text-bad ring-1 ring-bad/25 ring-inset">
          <TriangleAlert className="size-3.5" />
          Your Pokémon fainted. Choose a replacement below.
        </div>
      )}
      {snapshot.phase === "BATON_PASS" && (
        <div className="flex items-center gap-2 rounded-lg bg-primary/10 px-3 py-1.5 text-xs text-primary ring-1 ring-primary/25 ring-inset">
          <ArrowRightLeft className="size-3.5" />
          Baton Pass: choose who receives it below.
        </div>
      )}
      {snapshot.opp_move && (
        <div className="flex items-center gap-2 rounded-lg bg-foreground/5 px-3 py-1.5 text-xs text-muted-foreground ring-1 ring-foreground/10 ring-inset">
          <CornerDownRight className="size-3.5" />
          Opponent used <span className="font-semibold text-foreground">{snapshot.opp_move}</span>
        </div>
      )}
    </div>
  );
}

// ── Info plate for an active Pokémon ───────────────────────────────────────────
function PokPlate({
  pok,
  label,
  side,
}: {
  pok: PokemonState;
  label: string;
  side?: SideEffect[];
}) {
  const hasChips =
    Object.keys(pok.stages).length > 0 || pok.vol_status.length > 0 || (side?.length ?? 0) > 0;
  return (
    <div className="w-full max-w-[340px] rounded-xl border bg-card/85 p-3 shadow-xl shadow-black/25 backdrop-blur-sm">
      <div className="flex items-center gap-2">
        <span className="rounded bg-foreground/8 px-1.5 py-0.5 text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">
          {label}
        </span>
        <span className="truncate text-[15px] font-semibold tracking-tight">
          {displayName(pok.name)}
        </span>
        {!!pok.level && (
          <span className="num text-xs text-subtle-foreground">Lv {pok.level}</span>
        )}
        <span className="ml-auto flex items-center gap-1.5">
          <StatusBadge status={pok.status} />
          {pok.item && <ItemIcon name={pok.item} size={22} />}
        </span>
      </div>
      <TypeBadges types={pok.types} className="mt-1.5" />
      <HpBar hp={pok.hp} max={pok.max_hp} className="mt-2.5" />
      {hasChips && (
        <div className="mt-2 flex flex-wrap gap-1">
          <StageChips stages={pok.stages} />
          <VolatileChips names={pok.vol_status} />
          <SideChips effects={side} />
        </div>
      )}
    </div>
  );
}

// ── Battle sprite on its platform; hover lists the moves ──────────────────────
function BattleSprite({
  pok,
  side,
}: {
  pok: PokemonState | null;
  side: "mine" | "opp";
}) {
  const scale = side === "mine" ? 1.75 : 1.5;
  const platform = (
    <div
      className="pointer-events-none absolute bottom-1 left-1/2 h-9 w-48 -translate-x-1/2 rounded-[50%]"
      style={{
        background:
          "radial-gradient(closest-side, oklch(1 0 0 / 11%), oklch(1 0 0 / 4%) 65%, transparent)",
      }}
    />
  );

  if (!pok) {
    return (
      <div className="relative flex h-[148px] items-end justify-center pb-5">
        {platform}
        <span className="flex items-center gap-1.5 text-xs text-subtle-foreground italic">
          <Skull className="size-3.5" /> Fainted
        </span>
      </div>
    );
  }

  const img = (
    <div className="relative flex h-[148px] items-end justify-center pb-4">
      {platform}
      <Sprite
        srcs={battleSprite(pok.id, side === "opp" ? "front" : "back")}
        alt={pok.name}
        className="relative block drop-shadow-[0_6px_10px_rgb(0_0_0/45%)]"
        style={{ transform: `scale(${scale})`, transformOrigin: "bottom center" }}
      />
    </div>
  );

  if (!pok.moves || pok.moves.length === 0) return img;

  return (
    <HoverCard openDelay={150} closeDelay={80}>
      <HoverCardTrigger asChild>
        <div className="cursor-help">{img}</div>
      </HoverCardTrigger>
      <HoverCardContent side="top" className="w-60">
        <div className="mb-2 flex items-baseline justify-between border-b pb-1.5">
          <span className="font-semibold">{displayName(pok.name)}</span>
          <span className="text-[10px] tracking-wider text-subtle-foreground uppercase">Moves</span>
        </div>
        <MoveList moves={pok.moves} />
      </HoverCardContent>
    </HoverCard>
  );
}

// ── Party strip ────────────────────────────────────────────────────────────────
function PartySlot({ entry }: { entry: BenchEntry }) {
  const fainted = entry.hp <= 0;
  return (
    <HoverCard openDelay={180} closeDelay={80}>
      <HoverCardTrigger asChild>
        <div
          className={cn(
            "relative flex h-[52px] w-12 flex-col items-center justify-between rounded-lg bg-foreground/4 px-1 pt-1 pb-1.5 ring-1 ring-foreground/8 transition-colors ring-inset hover:bg-foreground/8",
            fainted && "opacity-40 grayscale",
          )}
        >
          <Sprite srcs={pokIcon(entry.id)} alt={entry.name} width={40} height={30} className="object-contain" />
          <HpBar hp={entry.hp} max={entry.max_hp} size="xs" showText={false} showLabel={false} className="px-0.5" />
          {entry.status && (
            <span
              className="absolute top-1 right-1 size-1.5 rounded-full"
              style={{ background: statusColor(entry.status) }}
            />
          )}
        </div>
      </HoverCardTrigger>
      <HoverCardContent side="top" className="w-60">
        <div className="flex items-baseline gap-2">
          <span className="font-semibold">{displayName(entry.name)}</span>
          <span className="num text-xs text-subtle-foreground">Lv {entry.level}</span>
          <StatusBadge status={entry.status} className="ml-auto" />
        </div>
        <TypeBadges types={entry.types} className="mt-1.5" />
        {entry.item && (
          <div className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
            <ItemIcon name={entry.item} size={18} />
            {entry.item}
          </div>
        )}
        <HpBar hp={entry.hp} max={entry.max_hp} size="sm" className="mt-2" />
        {entry.moves && entry.moves.length > 0 && (
          <div className="mt-2.5 border-t pt-2">
            <MoveList moves={entry.moves} />
          </div>
        )}
      </HoverCardContent>
    </HoverCard>
  );
}

// Bench in slot order; only real party members (no empty-slot padding)
function PartyStrip({ entries, className }: { entries: BenchEntry[]; className?: string }) {
  if (entries.length === 0) return null;
  const sorted = [...entries].sort((a, b) => a.slot - b.slot);
  return (
    <div className={cn("flex flex-wrap gap-1.5", className)}>
      {sorted.map((e) => (
        <PartySlot key={e.slot} entry={e} />
      ))}
    </div>
  );
}

// ── Recommendation / result bar ───────────────────────────────────────────────
function Recommendation({
  node,
  onContinue,
  onStartNew,
  running,
  starting,
}: {
  node: TreeNode;
  onContinue: (id: string) => void;
  onStartNew?: () => void;
  running?: boolean;
  starting?: boolean;
}) {
  const bestKey = bestActionKey(node);
  const best = bestKey ? node.actions[bestKey] : null;
  const terminal = node.snapshot.terminal;
  const won = node.win_chance >= 0.5;

  return (
    <div className="flex items-center gap-4 rounded-xl border bg-card px-4 py-2.5">
      {terminal ? (
        <>
          <div
            className={cn(
              "flex size-12 items-center justify-center rounded-full ring-1",
              won ? "bg-good/12 text-good ring-good/30" : "bg-bad/12 text-bad ring-bad/30",
            )}
          >
            {won ? <Trophy className="size-5" /> : <Skull className="size-5" />}
          </div>
          <div>
            <div className="text-[11px] font-medium tracking-wider text-subtle-foreground uppercase">
              Battle over
            </div>
            <div className="text-lg font-semibold">{won ? "Victory" : "Defeat"}</div>
            <div className="num text-xs text-muted-foreground">
              {node.dead_avg.toFixed(2)} expected deaths ·{" "}
              <span className="text-subtle-foreground">{fmtInt(node.visits)} visits</span>
            </div>
          </div>
        </>
      ) : best ? (
        <>
          <WinRing win={best.win_chance} size={50} />
          <div className="min-w-0">
            <div className="text-[11px] font-medium tracking-wider text-subtle-foreground uppercase">
              Recommended
            </div>
            <div className="flex items-center gap-2">
              <TypeDot type={best.move_type} className="size-2.5" />
              <span className="truncate text-lg font-semibold tracking-tight">
                {best.action_type === 2 ? `Switch to ${switchTarget(best.label)}` : best.label}
              </span>
            </div>
            <div className="num text-xs text-muted-foreground">
              {best.dead_avg.toFixed(2)} expected deaths ·{" "}
              <span className="text-subtle-foreground">{fmtInt(node.visits)} visits here</span>
            </div>
          </div>
        </>
      ) : (
        <span className="text-sm text-muted-foreground italic">No recommendation yet</span>
      )}

      <div className="ml-auto flex items-center gap-2">
        {onStartNew && (
          <Tooltip>
            <TooltipTrigger asChild>
              <span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onStartNew}
                  disabled={running || starting}
                >
                  <RotateCcw />
                  {starting ? "Starting…" : "Start brand new"}
                </Button>
              </span>
            </TooltipTrigger>
            <TooltipContent>Start a brand new search from the root</TooltipContent>
          </Tooltip>
        )}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="outline" size="sm" onClick={() => onContinue(node.id)}>
              <GitBranchPlus />
              Continue from here
            </Button>
          </TooltipTrigger>
          <TooltipContent>Search again from this position, with your real HP</TooltipContent>
        </Tooltip>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function BattleView({
  node,
  onContinue,
  onStartNew,
  running,
  starting,
}: {
  node: TreeNode;
  onContinue: (id: string) => void;
  onStartNew?: () => void;
  running?: boolean;
  starting?: boolean;
}) {
  const { snapshot } = node;
  const isDeath = snapshot.phase === "DEATH";

  return (
    <section className="space-y-3 p-4 pb-3">
      <FieldStrip snapshot={snapshot} />
      <EventLines snapshot={snapshot} />

      {/* Stage */}
      <div
        className="relative overflow-hidden rounded-2xl border"
        style={{
          background: [
            "radial-gradient(ellipse 55% 60% at 78% 28%, oklch(0.32 0.06 250 / 55%), transparent 70%)",
            "radial-gradient(ellipse 55% 60% at 22% 82%, oklch(0.32 0.08 290 / 45%), transparent 70%)",
            "linear-gradient(180deg, oklch(0.205 0.016 265), oklch(0.17 0.01 265))",
          ].join(", "),
        }}
      >
        {/* faint horizon */}
        <div className="pointer-events-none absolute inset-x-0 top-1/2 h-px bg-gradient-to-r from-transparent via-foreground/8 to-transparent" />

        <div className="relative grid grid-cols-2 gap-x-6 px-5 pt-3 pb-2">
          {/* Opponent: plate + party (left), sprite (right) */}
          <div className="flex flex-col justify-center gap-2 pb-2">
            <PartyStrip entries={snapshot.opp_bench} />
            {snapshot.opp ? (
              <PokPlate pok={snapshot.opp} label="Opp" side={snapshot.field?.opp_side} />
            ) : (
              <div className="text-xs text-subtle-foreground italic">Opponent fainted</div>
            )}
          </div>
          <BattleSprite pok={snapshot.opp} side="opp" />

          {/* Me: sprite (left), plate + party (right) */}
          <BattleSprite pok={isDeath ? null : snapshot.my} side="mine" />
          <div className="flex flex-col items-end justify-center gap-2 pt-2">
            {isDeath ? (
              <div className="w-full max-w-[340px] rounded-xl border border-bad/25 bg-bad/8 p-3">
                <div className="mb-2 text-xs text-bad">Fainted. Pick a replacement:</div>
                <PartyStrip entries={snapshot.my_bench} />
                {(snapshot.field?.my_side?.length ?? 0) > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    <SideChips effects={snapshot.field?.my_side} />
                  </div>
                )}
              </div>
            ) : (
              <>
                {snapshot.my ? (
                  <PokPlate pok={snapshot.my} label="You" side={snapshot.field?.my_side} />
                ) : (
                  <div className="text-xs text-subtle-foreground italic">Fainted</div>
                )}
                <PartyStrip entries={snapshot.my_bench} className="justify-end" />
              </>
            )}
          </div>
        </div>
      </div>

      <Recommendation
        node={node}
        onContinue={onContinue}
        onStartNew={onStartNew}
        running={running}
        starting={starting}
      />
    </section>
  );
}
