import { ChevronLeft, Flag, Skull } from "lucide-react";
import { cn } from "@/lib/utils";
import { OPP_DID, TIER_TEXT, fmtCompact, fmtPct, switchTarget, winTier } from "@/lib/format";
import { pathSteps } from "@/lib/tree";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { TreeNode } from "../types";
import { Kbd, TypeIcon } from "./common/Badges";

// Decision path from root to the node on screen; click a step to jump back to it
export default function PathRail({
  tree,
  pathIds,
  pathMoves,
  nodeMap,
  onJump,
  onBack,
}: {
  tree: TreeNode;
  pathIds: string[];
  pathMoves: (string | null)[];
  nodeMap: Map<string, TreeNode>;
  onJump: (depth: number) => void;
  onBack: () => void;
}) {
  const steps = pathSteps(tree, pathIds, nodeMap);
  const current = steps.length - 1;

  return (
    <aside className="flex min-h-0 flex-col border-r bg-card/40">
      <div className="flex h-11 shrink-0 items-center justify-between border-b px-3">
        <span className="text-[11px] font-medium tracking-wider text-subtle-foreground uppercase">
          Decision path
        </span>
        <Tooltip>
          <TooltipTrigger asChild>
            <span>
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={onBack}
                disabled={pathIds.length === 0}
                aria-label="Back one step"
              >
                <ChevronLeft />
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent>
            Back <Kbd>Backspace</Kbd>
          </TooltipContent>
        </Tooltip>
      </div>

      <ol className="min-h-0 flex-1 overflow-y-auto px-2 py-3">
        {steps.map((step, i) => {
          const snap = step.node.snapshot;
          const isCurrent = i === current;
          const isSwitch = step.action?.action_type === 2;
          const label =
            step.action === null
              ? "Battle start"
              : isSwitch
                ? `Switch to ${switchTarget(step.action.label)}`
                : step.action.label;
          const win = step.node.win_chance;
          const oppMove = i > 0 ? pathMoves[i - 1] : null;
          return (
            <li key={step.node.id} className="relative">
              {/* timeline line */}
              {i < current && (
                <span className="absolute top-6 bottom-[-6px] left-[15px] w-px bg-border" />
              )}
              <button
                onClick={() => onJump(i)}
                className={cn(
                  "group relative flex w-full gap-2.5 rounded-lg px-2 py-1.5 text-left transition-colors cursor-pointer",
                  isCurrent ? "bg-primary/12 ring-1 ring-primary/30" : "hover:bg-foreground/5",
                )}
              >
                <span
                  className={cn(
                    "relative z-10 mt-1 flex size-3.5 shrink-0 items-center justify-center rounded-full ring-2",
                    isCurrent
                      ? "bg-primary ring-primary/30"
                      : "bg-background ring-foreground/20 group-hover:ring-foreground/40",
                  )}
                >
                  {i === 0 && !isCurrent && <Flag className="size-2 text-muted-foreground" />}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-1.5">
                    {step.action?.move_type && <TypeIcon type={step.action.move_type} size={14} />}
                    <span
                      className={cn(
                        "truncate text-[13px]",
                        isCurrent ? "font-semibold text-foreground" : "font-medium text-foreground/90",
                      )}
                    >
                      {label}
                    </span>
                  </span>
                  <span className="mt-0.5 flex items-center gap-1.5 text-[11px] text-subtle-foreground">
                    <span className="num">T{snap.turn}</span>
                    {oppMove && (
                      <>
                        <span>·</span>
                        <span className="truncate" title={oppMove}>
                          Opp {OPP_DID[oppMove] ?? oppMove}
                        </span>
                      </>
                    )}
                    {snap.phase === "DEATH" && (
                      <Skull className="size-3 shrink-0 text-bad" aria-label="Fainted" />
                    )}
                  </span>
                </span>
                <span className="flex flex-col items-end">
                  <span className={cn("num text-xs font-semibold", TIER_TEXT[winTier(win)])}>
                    {fmtPct(win)}
                  </span>
                  <span className="num text-[10px] text-subtle-foreground">
                    {fmtCompact(step.node.visits)}
                  </span>
                </span>
              </button>
            </li>
          );
        })}
      </ol>

      <div className="flex h-9 shrink-0 items-center justify-between border-t px-3 text-[11px] text-subtle-foreground">
        <span>Depth {current}</span>
        <span>
          <Kbd>1</Kbd>–<Kbd>9</Kbd> pick · <Kbd>Esc</Kbd> clear
        </span>
      </div>
    </aside>
  );
}
