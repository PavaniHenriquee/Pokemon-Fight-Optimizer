import { GitBranch, Loader2, Play, Square } from "lucide-react";
import { cn } from "@/lib/utils";
import { fmtInt, formatTime } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { IterationsInput } from "./common/IterationsInput";

export type View = "configure" | "explore";

const TABS: { id: View; label: string }[] = [
  { id: "configure", label: "Setup" },
  { id: "explore", label: "Analyze" },
];

export default function TopBar({
  view,
  onView,
  connected,
  compiling,
  running,
  starting,
  sessionActive,
  displayIterations,
  actualIterations,
  maxIterations,
  elapsed,
  iterations,
  onIterations,
  canStart,
  onStart,
  onStop,
}: {
  view: View;
  onView: (v: View) => void;
  connected: boolean;
  compiling: boolean;
  running: boolean;
  starting: boolean;
  sessionActive: boolean;
  displayIterations: number;
  actualIterations: number;
  maxIterations: number;
  elapsed: number;
  iterations: number;
  onIterations: (n: number) => void;
  canStart: boolean;
  onStart: () => void;
  onStop: () => void;
}) {
  const progress = maxIterations > 0 ? Math.min(1, actualIterations / maxIterations) : 0;

  return (
    <header className="relative z-20 flex h-12 shrink-0 items-center gap-5 border-b bg-card/70 px-4 backdrop-blur select-none">
      {/* Brand */}
      <div className="flex items-center gap-2.5">
        <div className="flex size-7 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-[oklch(0.55_0.2_250)] shadow-[0_0_16px_-4px_var(--primary)]">
          <GitBranch className="size-4 text-primary-foreground" />
        </div>
        <div className="leading-tight">
          <div className="text-[13px] font-semibold tracking-tight">Nuzlocke Optimizer</div>
          <div className="text-[10px] text-subtle-foreground">Renegade Platinum · Gen IV</div>
        </div>
      </div>

      {/* View switch */}
      <nav className="flex rounded-lg bg-background/60 p-0.5 ring-1 ring-border">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => onView(t.id)}
            className={cn(
              "h-7 rounded-md px-3.5 text-xs font-medium transition-colors cursor-pointer",
              view === t.id
                ? "bg-elevated text-foreground shadow-sm ring-1 ring-foreground/10"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {/* Run status + controls */}
      <div className="ml-auto flex items-center gap-4">
        <Tooltip>
          <TooltipTrigger asChild>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span className="relative flex size-2">
                {connected && running && (
                  <span className="absolute inline-flex size-full animate-ping rounded-full bg-good opacity-60" />
                )}
                <span
                  className={cn(
                    "relative inline-flex size-2 rounded-full",
                    connected ? "bg-good" : "bg-bad",
                  )}
                />
              </span>
              <span className="num">
                {running ? (
                  <>
                    <span className="text-foreground">{fmtInt(displayIterations)}</span>
                    <span className="text-subtle-foreground"> / {fmtInt(maxIterations)}</span>
                  </>
                ) : connected && compiling ? (
                  <span className="flex items-center gap-1.5 text-warn">
                    <Loader2 className="size-3 animate-spin" /> Compiling engine…
                  </span>
                ) : actualIterations > 0 ? (
                  <>
                    Done ·{" "}
                    <span className="text-foreground">{fmtInt(actualIterations)}</span> iterations
                  </>
                ) : connected ? (
                  "Idle"
                ) : (
                  "Backend offline"
                )}
              </span>
              {(running || actualIterations > 0) && (
                <span className="num rounded bg-foreground/6 px-1.5 py-0.5 text-[11px] text-muted-foreground">
                  {formatTime(elapsed)}
                </span>
              )}
            </div>
          </TooltipTrigger>
          <TooltipContent>
            {!connected
              ? "Can't reach the backend, retrying…"
              : compiling
                ? "First start after a code change: compiling the engine (a minute or two). A search started now waits for it."
                : "Connected to the backend"}
          </TooltipContent>
        </Tooltip>

        <div className="h-5 w-px bg-border" />

        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          Iterations
          <IterationsInput
            value={iterations}
            onChange={onIterations}
            disabled={running || starting}
            className="w-28"
          />
        </label>

        {running ? (
          <Button variant="outline" size="sm" onClick={onStop} className="w-28">
            <Square className="fill-current" />
            Stop
          </Button>
        ) : (
          <Tooltip>
            <TooltipTrigger asChild>
              {/* span wrapper: a disabled button doesn't fire hover events */}
              <span>
                <Button
                  size="sm"
                  onClick={onStart}
                  disabled={!canStart || starting || !connected}
                  className="w-28 shadow-[0_0_20px_-6px_var(--primary)]"
                >
                  {starting ? <Loader2 className="animate-spin" /> : <Play className="fill-current" />}
                  {starting ? "Starting…" : sessionActive ? "Start new" : "Start search"}
                </Button>
              </span>
            </TooltipTrigger>
            <TooltipContent>
              {!connected
                ? "Waiting for the backend"
                : !canStart
                  ? "Configure both teams to start"
                  : "Start a new search from the battle's first turn"}
            </TooltipContent>
          </Tooltip>
        )}
      </div>

      {/* Search progress */}
      {(running || actualIterations > 0) && (
        <div className="absolute inset-x-0 -bottom-px h-0.5 bg-transparent">
          <div
            className={cn(
              "h-full transition-[width] duration-700 ease-out",
              running ? "bg-primary shadow-[0_0_8px_var(--primary)]" : "bg-primary/40",
            )}
            style={{ width: `${(running ? progress : 1) * 100}%` }}
          />
        </div>
      )}
    </header>
  );
}
