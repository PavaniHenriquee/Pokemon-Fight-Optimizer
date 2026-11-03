import { cn } from "@/lib/utils";
import { TIER_BG, TIER_TEXT, TIER_VAR, winTier } from "@/lib/format";

export function WinRing({
  win,
  size = 44,
  stroke,
  label = true,
  className,
}: {
  win: number;
  size?: number;
  stroke?: number;
  label?: boolean;
  className?: string;
}) {
  const strokeWidth = stroke ?? Math.max(2.5, size / 14);
  const r = (size - strokeWidth) / 2;
  const circ = 2 * Math.PI * r;
  const fill = Math.max(0, Math.min(1, win)) * circ;
  const tier = winTier(win);
  return (
    <div
      className={cn("relative shrink-0", className)}
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="oklch(1 0 0 / 8%)"
          strokeWidth={strokeWidth}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={TIER_VAR[tier]}
          strokeWidth={strokeWidth}
          strokeDasharray={`${fill} ${circ - fill}`}
          strokeLinecap="round"
          className="transition-[stroke-dasharray,stroke] duration-500"
        />
      </svg>
      {label && (
        <span
          className={cn(
            "num absolute inset-0 flex items-center justify-center font-semibold leading-none",
            TIER_TEXT[tier],
          )}
          style={{ fontSize: Math.max(10, size * 0.27) }}
        >
          {Math.round(win * 100)}
          <span style={{ fontSize: "0.62em" }} className="opacity-70">
            %
          </span>
        </span>
      )}
    </div>
  );
}

export function WinBar({ win, className }: { win: number; className?: string }) {
  const tier = winTier(win);
  return (
    <div className={cn("h-1 w-full overflow-hidden rounded-full bg-foreground/8", className)}>
      <div
        className={cn("h-full rounded-full transition-[width] duration-500", TIER_BG[tier])}
        style={{ width: `${Math.max(0, Math.min(1, win)) * 100}%` }}
      />
    </div>
  );
}
