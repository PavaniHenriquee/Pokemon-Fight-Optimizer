import {
  ArrowRightLeft,
  CloudHail,
  CloudRain,
  CornerDownRight,
  FlipHorizontal2,
  Orbit,
  Skull,
  Sun,
  TriangleAlert,
  Wind,
} from "lucide-react";
import { HoverCard, HoverCardTrigger, HoverCardContent } from "./ui/hover-card";
import { cn } from "@/lib/utils";
import { battleSprite, pokIcon } from "@/lib/sprites";
import { OPP_DID, displayName, statusColor } from "@/lib/format";
import type { TreeNode, PokemonState, BenchEntry, SnapshotData, SideEffect } from "../types";
import { Sprite } from "./common/Sprite";
import { HpBar } from "./common/HpBar";
import { ItemIcon } from "./common/ItemIcon";
import { MoveList } from "./common/MoveList";
import {
  Chip,
  GenderMark,
  SideChips,
  StageChips,
  StatusBadge,
  TypeBadges,
  VolatileChips,
} from "./common/Badges";

const WEATHER_ICON: Record<string, typeof Sun> = {
  Sun,
  Rain: CloudRain,
  Hail: CloudHail,
  Sandstorm: Wind,
};

// ── Field strip: turn, weather, Gravity, Trick Room, trainer items ────────────
function FieldStrip({ snapshot }: { snapshot: SnapshotData }) {
  const field = snapshot.field;
  const WeatherIcon = field?.weather ? WEATHER_ICON[field.weather] : undefined;
  const items = snapshot.trainer_items?.filter(Boolean) ?? [];
  return (
    <div className="flex items-center gap-2 short:contents">
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
      {!!field?.trick_room_turns && (
        <Chip tone="primary" title={`${field.trick_room_turns} turn(s) left`}>
          <FlipHorizontal2 className="size-3" />
          Trick Room <span className="opacity-70">· {field.trick_room_turns}</span>
        </Chip>
      )}
      {snapshot.terminal && <Chip tone="warn">Terminal</Chip>}
      {items.length > 0 && (
        <div className="ml-auto flex items-center gap-1.5 short:order-1">
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
function EventLines({ snapshot, oppMove }: { snapshot: SnapshotData; oppMove?: string | null }) {
  const isDeath = snapshot.phase === "DEATH" && !snapshot.terminal;
  const isBatonPass = snapshot.phase === "BATON_PASS" && !snapshot.terminal;
  if (!isDeath && !isBatonPass && !oppMove) return null;
  return (
    <div className="flex flex-wrap items-center gap-2">
      {isDeath && (
        <div className="flex items-center gap-2 rounded-lg bg-bad/10 px-3 py-1.5 text-xs text-bad ring-1 ring-bad/25 ring-inset">
          <TriangleAlert className="size-3.5" />
          Your Pokémon fainted. Choose a replacement below.
        </div>
      )}
      {isBatonPass && (
        <div className="flex items-center gap-2 rounded-lg bg-primary/10 px-3 py-1.5 text-xs text-primary ring-1 ring-primary/25 ring-inset">
          <ArrowRightLeft className="size-3.5" />
          Baton Pass: choose who receives it below.
        </div>
      )}
      {oppMove && (
        <div className="flex items-center gap-2 rounded-lg bg-foreground/5 px-3 py-1.5 text-xs text-muted-foreground ring-1 ring-foreground/10 ring-inset">
          <CornerDownRight className="size-3.5" />
          Opponent {!OPP_DID[oppMove] && "used "}
          <span className="font-semibold text-foreground">{OPP_DID[oppMove] ?? oppMove}</span>
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
    <div className="w-full max-w-[340px] rounded-xl border bg-card/85 p-3 shadow-xl shadow-black/25 backdrop-blur-sm short:p-2 roomy-tall:max-w-[400px]">
      <div className="flex items-center gap-2">
        <span className="rounded bg-foreground/8 px-1.5 py-0.5 text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">
          {label}
        </span>
        <span className="truncate text-[15px] font-semibold tracking-tight roomy-tall:text-lg">
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
      <TypeBadges types={pok.types} className="mt-1.5 short:mt-1" />
      <HpBar hp={pok.hp} max={pok.max_hp} className="mt-2.5 short:mt-1.5" />
      {hasChips && (
        <div className="mt-2 flex flex-wrap gap-1 short:mt-1">
          <StageChips stages={pok.stages} />
          <VolatileChips names={pok.vol_status} />
          <SideChips effects={side} />
        </div>
      )}
    </div>
  );
}

// The ability on its own line in a hover card
function AbilityLine({ ability, className }: { ability?: string; className?: string }) {
  if (!ability) return null;
  return (
    <div className={cn("text-xs text-muted-foreground", className)}>
      <span className="text-subtle-foreground">Ability</span> {ability}
    </div>
  );
}

// Set steps rather than a stage that fills the window: it would resize on every node with other cards
const STAGE_ROW = "h-[148px] roomy-tall:h-[230px] roomy-full:h-[270px]";
const SPRITE_SCALE = {
  mine: "scale-[1.75] roomy-tall:scale-[2.25] roomy-full:scale-[2.5]",
  opp: "scale-[1.5] roomy-tall:scale-[2] roomy-full:scale-[2.25]",
};

// ── Battle sprite on its platform; hover lists ability, gender and moves ──────
function BattleSprite({
  pok,
  side,
}: {
  pok: PokemonState | null;
  side: "mine" | "opp";
}) {
  const platform = (
    <div
      className="pointer-events-none absolute bottom-1 left-1/2 h-9 w-48 -translate-x-1/2 rounded-[50%] roomy-tall:h-12 roomy-tall:w-64 roomy-full:h-14 roomy-full:w-72"
      style={{
        background:
          "radial-gradient(closest-side, oklch(1 0 0 / 11%), oklch(1 0 0 / 4%) 65%, transparent)",
      }}
    />
  );

  if (!pok || pok.hp <= 0) {
    return (
      <div className={cn("relative flex items-end justify-center pb-5", STAGE_ROW)}>
        {platform}
        <span className="flex items-center gap-1.5 text-xs text-subtle-foreground italic">
          <Skull className="size-3.5" /> Fainted
        </span>
      </div>
    );
  }

  const img = (
    <div className={cn("relative flex items-end justify-center pb-4", STAGE_ROW)}>
      {platform}
      <Sprite
        srcs={battleSprite(pok.id, side === "opp" ? "front" : "back")}
        alt={pok.name}
        className={cn(
          "relative block origin-bottom drop-shadow-[0_6px_10px_rgb(0_0_0/45%)]",
          SPRITE_SCALE[side],
        )}
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
        <div className="mb-2 border-b pb-1.5">
          <div className="flex items-baseline gap-1.5">
            <span className="font-semibold">{displayName(pok.name)}</span>
            <GenderMark gender={pok.gender ?? null} />
            <span className="ml-auto text-[10px] tracking-wider text-subtle-foreground uppercase">
              Moves
            </span>
          </div>
          <AbilityLine ability={pok.ability} className="mt-0.5" />
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
            "relative flex h-[52px] w-12 flex-col items-center justify-between rounded-lg bg-foreground/4 px-1 pt-1 pb-1.5 ring-1 ring-foreground/8 transition-colors ring-inset hover:bg-foreground/8 short:h-[44px] roomy-tall:h-[70px] roomy-tall:w-[68px]",
            fainted && "opacity-40 grayscale",
          )}
        >
          <Sprite
            srcs={pokIcon(entry.id)}
            alt={entry.name}
            width={40}
            height={30}
            className="max-w-none shrink-0 object-contain roomy-tall:h-[45px] roomy-tall:w-[60px]"
          />
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
          <span className="flex items-baseline gap-1.5">
            <span className="font-semibold">{displayName(entry.name)}</span>
            <GenderMark gender={entry.gender ?? null} />
          </span>
          <span className="num text-xs text-subtle-foreground">Lv {entry.level}</span>
          <StatusBadge status={entry.status} className="ml-auto" />
        </div>
        <TypeBadges types={entry.types} className="mt-1.5" />
        <AbilityLine ability={entry.ability} className="mt-2" />
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

// ── Main component ────────────────────────────────────────────────────────────
export default function BattleView({
  node,
  oppMove,
}: {
  node: TreeNode;
  oppMove?: string | null;
}) {
  const { snapshot } = node;
  const isDeath = snapshot.phase === "DEATH";

  return (
    <section className="space-y-3 p-4 pb-3 short:space-y-2 short:pt-2 short:pb-2">
      {/* One row on a short window, with the trainer's items last */}
      <div className="space-y-3 short:flex short:flex-wrap short:items-center short:gap-2 short:space-y-0">
        <FieldStrip snapshot={snapshot} />
        <EventLines snapshot={snapshot} oppMove={oppMove} />
      </div>

      {/* Stage */}
      <div
        className="relative overflow-hidden rounded-2xl border"
        style={{
          background: [
            "radial-gradient(ellipse 55% 60% at 78% 28%, oklch(0.32 0.06 250 / 55%), transparent 70%)",
            "radial-gradient(ellipse 55% 60% at 22% 82%, oklch(0.32 0.08 230 / 45%), transparent 70%)",
            "linear-gradient(180deg, oklch(0.205 0.016 265), oklch(0.17 0.01 265))",
          ].join(", "),
        }}
      >
        {/* faint horizon */}
        <div className="pointer-events-none absolute inset-x-0 top-1/2 h-px bg-gradient-to-r from-transparent via-foreground/8 to-transparent" />

        <div className="relative grid grid-cols-2 gap-x-6 px-5 pt-3 pb-2 short:pt-2 short:pb-1">
          {/* Opponent: plate + party (left), sprite (right) */}
          <div className="flex flex-col justify-center gap-2 pb-2 short:gap-1.5 short:pb-1">
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
          <div className="flex flex-col items-end justify-center gap-2 pt-2 short:gap-1.5 short:pt-1">
            {isDeath ? (
              <div className="w-full max-w-[340px] rounded-xl border border-bad/25 bg-bad/8 p-3 roomy-tall:max-w-[400px]">
                <div className="mb-2 text-xs text-bad">
                  {snapshot.terminal ? "Fainted" : "Fainted. Pick a replacement:"}
                </div>
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
    </section>
  );
}
