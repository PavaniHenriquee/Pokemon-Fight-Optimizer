import { CircleDot, Mars, Sparkles, Swords, Venus } from "lucide-react";
import { cn } from "@/lib/utils";
import { STATUS_NAMES, statusColor, typeColor } from "@/lib/format";
import { typeIcon, typeSprite } from "@/lib/sprites";
import { Sprite } from "./Sprite";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { SideEffect } from "../../types";

// Small rounded label; tone picks the color family
export function Chip({
  children,
  tone = "neutral",
  className,
  title,
}: {
  children: React.ReactNode;
  tone?: "neutral" | "good" | "bad" | "info" | "primary" | "warn";
  className?: string;
  title?: string;
}) {
  const tones = {
    neutral: "bg-foreground/6 text-muted-foreground ring-foreground/10",
    good: "bg-good/12 text-good ring-good/25",
    bad: "bg-bad/12 text-bad ring-bad/25",
    warn: "bg-warn/12 text-warn ring-warn/25",
    info: "bg-info/12 text-info ring-info/25",
    primary: "bg-primary/15 text-primary ring-primary/30",
  };
  return (
    <span
      title={title}
      className={cn(
        "num inline-flex h-5 items-center gap-1 rounded-md px-1.5 text-[11px] font-medium whitespace-nowrap ring-1 ring-inset",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

// PokeAPI type badge; the colored text badge when there's no sprite (Typeless, offline)
export function TypeBadge({
  type,
  className,
  height = 16,
}: {
  type: string;
  className?: string;
  height?: number;
}) {
  return (
    <Sprite
      srcs={typeSprite(type)}
      alt={type}
      title={type}
      pixelated={false}
      className={cn("shrink-0", className)}
      style={{ height, width: "auto" }}
      fallback={<TypeTextBadge type={type} className={className} />}
    />
  );
}

function TypeTextBadge({ type, className }: { type: string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex h-[18px] items-center rounded px-1.5 text-[10px] font-semibold tracking-wide text-white uppercase",
        className,
      )}
      style={{
        background: `color-mix(in oklab, ${typeColor(type)} 78%, black)`,
        textShadow: "0 1px 1px rgb(0 0 0 / 35%)",
      }}
    >
      {type}
    </span>
  );
}

export function TypeBadges({
  types,
  className,
  height,
}: {
  types?: string[];
  className?: string;
  height?: number;
}) {
  if (!types || types.length === 0) return null;
  return (
    <span className={cn("inline-flex gap-1", className)}>
      {types.map((t) => (
        <TypeBadge key={t} type={t} height={height} />
      ))}
    </span>
  );
}

export function TypeDot({ type, className }: { type?: string | null; className?: string }) {
  if (!type) return null;
  return (
    <span
      className={cn("inline-block size-2 shrink-0 rounded-full", className)}
      style={{ background: typeColor(type) }}
      title={type}
    />
  );
}

// The type's round symbol; the colored dot, in the same space, when there's no sprite (Typeless, offline)
export function TypeIcon({
  type,
  size = 16,
  className,
}: {
  type?: string | null;
  size?: number;
  className?: string;
}) {
  if (!type) return null;
  return (
    <Sprite
      srcs={typeIcon(type)}
      alt={type}
      title={type}
      pixelated={false}
      width={size}
      height={size}
      className={cn("shrink-0", className)}
      fallback={
        <span
          className={cn("flex shrink-0 items-center justify-center", className)}
          style={{ width: size, height: size }}
        >
          <TypeDot type={type} />
        </span>
      }
    />
  );
}

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  if (!status) return null;
  return (
    <span
      title={STATUS_NAMES[status] ?? status}
      className={cn(
        "inline-flex h-[18px] items-center rounded px-1.5 text-[10px] font-bold tracking-wide",
        className,
      )}
      style={{
        color: statusColor(status),
        background: `color-mix(in oklab, ${statusColor(status)} 16%, transparent)`,
        boxShadow: `inset 0 0 0 1px color-mix(in oklab, ${statusColor(status)} 35%, transparent)`,
      }}
    >
      {status}
    </span>
  );
}

const CATEGORY_ICON = {
  Physical: Swords,
  Special: Sparkles,
  Status: CircleDot,
} as const;

export function CategoryIcon({
  category,
  className,
}: {
  category?: string | null;
  className?: string;
}) {
  if (!category) return null;
  const Icon = CATEGORY_ICON[category as keyof typeof CATEGORY_ICON];
  if (!Icon) return null;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className={cn("inline-flex text-muted-foreground", className)}>
          <Icon className="size-3.5" />
        </span>
      </TooltipTrigger>
      <TooltipContent>{category}</TooltipContent>
    </Tooltip>
  );
}

export function StageChips({ stages }: { stages: Record<string, number> }) {
  const entries = Object.entries(stages);
  if (entries.length === 0) return null;
  return (
    <>
      {entries.map(([stat, val]) => (
        <Chip key={stat} tone={val > 0 ? "good" : "bad"}>
          {stat} {val > 0 ? "+" : ""}
          {val}
        </Chip>
      ))}
    </>
  );
}

export function VolatileChips({ names, limit }: { names: string[]; limit?: number }) {
  if (names.length === 0) return null;
  const shown = limit ? names.slice(0, limit) : names;
  const hidden = names.length - shown.length;
  return (
    <>
      {shown.map((n) => (
        <Chip key={n} tone="primary">
          {n}
        </Chip>
      ))}
      {hidden > 0 && <Chip title={names.slice(shown.length).join(", ")}>+{hidden}</Chip>}
    </>
  );
}

function effectLabel(e: SideEffect): string {
  if (e.layers !== undefined) return `${e.name} ×${e.layers}`;
  if (e.turns !== undefined) return `${e.name} ${e.turns}`;
  return e.name;
}

export function SideChips({ effects }: { effects?: SideEffect[] }) {
  if (!effects || effects.length === 0) return null;
  return (
    <>
      {effects.map((e) => (
        <Chip
          key={e.name}
          tone="info"
          title={e.turns !== undefined ? `${e.turns} turn(s) left` : undefined}
        >
          {effectLabel(e)}
        </Chip>
      ))}
    </>
  );
}

// ♂ / ♀ in the game's blue / pink; nothing for genderless. An icon, so it reads apart from the text symbol in
// Nidoran♀'s name beside it. 1em, so it follows the text size around it
export function GenderMark({ gender, className }: { gender: string | null; className?: string }) {
  if (gender !== "Male" && gender !== "Female") return null;
  const Icon = gender === "Male" ? Mars : Venus;
  return (
    <Icon
      aria-label={gender}
      strokeWidth={3}
      className={cn(
        "size-[1em] shrink-0 self-center",
        gender === "Male" ? "text-[oklch(0.7_0.14_245)]" : "text-[oklch(0.72_0.16_350)]",
        className,
      )}
    />
  );
}

// Small Poké Ball drawn inline (no sprite needed offline)
export function PokeballIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={cn("size-3.5", className)} aria-hidden>
      <circle cx="12" cy="12" r="10.5" fill="#f4f4f5" stroke="#18181b" strokeWidth="1.8" />
      <path d="M1.5 12a10.5 10.5 0 0 1 21 0z" fill="#ef4444" stroke="#18181b" strokeWidth="1.8" />
      <circle cx="12" cy="12" r="3.2" fill="#f4f4f5" stroke="#18181b" strokeWidth="1.8" />
    </svg>
  );
}
