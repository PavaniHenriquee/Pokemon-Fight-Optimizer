import { cn } from "@/lib/utils";
import { TIER_BG, TIER_TEXT, hpRange, hpTier } from "@/lib/format";

// HP bar with the bracket text ("50%–74%"), never the exact value
export function HpBar({
  hp,
  max,
  size = "md",
  showText = true,
  showLabel = size !== "xs",
  className,
}: {
  hp: number;
  max: number;
  size?: "xs" | "sm" | "md";
  showText?: boolean;
  showLabel?: boolean;
  className?: string;
}) {
  const pct = Math.max(0, Math.min(1, hp / Math.max(max, 1)));
  const tier = hpTier(hp, max);
  const height = size === "md" ? "h-2" : size === "sm" ? "h-1.5" : "h-1";
  return (
    <div className={cn("flex w-full items-center gap-2", className)}>
      {showLabel && (
        <span className="text-[10px] font-bold tracking-wider text-subtle-foreground">HP</span>
      )}
      <div className={cn("flex-1 overflow-hidden rounded-full bg-foreground/8", height)}>
        <div
          className={cn("h-full rounded-full transition-[width] duration-500", TIER_BG[tier])}
          style={{ width: `${pct * 100}%` }}
        />
      </div>
      {showText && (
        <span
          className={cn(
            "num shrink-0 text-right font-semibold whitespace-nowrap",
            size === "md" ? "min-w-[4.5rem] text-xs" : "min-w-16 text-[11px]",
            TIER_TEXT[tier],
          )}
        >
          {hpRange(hp, max)}
        </span>
      )}
    </div>
  );
}
