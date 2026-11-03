import { ArrowRight, CornerDownRight, MousePointerClick, Skull, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { pokIcon } from "@/lib/sprites";
import {
  TIER_TEXT,
  displayName,
  fmtInt,
  fmtPct,
  switchTarget,
  winTier,
} from "@/lib/format";
import { Button } from "./ui/button";
import type { ActionData, PokemonState, TreeNode } from "../types";
import { Sprite } from "./common/Sprite";
import { HpBar } from "./common/HpBar";
import { WinRing } from "./common/WinRing";
import {
  CategoryIcon,
  Kbd,
  StageChips,
  StatusBadge,
  TypeBadge,
  VolatileChips,
} from "./common/Badges";

function PokRow({ pok, label }: { pok: PokemonState; label: string }) {
  const hasChips = Object.keys(pok.stages).length > 0 || pok.vol_status.length > 0;
  return (
    <div className="flex items-start gap-2">
      <Sprite srcs={pokIcon(pok.id)} alt={pok.name} width={40} height={30} className="-mt-0.5 shrink-0 object-contain" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-semibold tracking-wider text-subtle-foreground uppercase">
            {label}
          </span>
          <span className="truncate text-[13px] font-medium">{displayName(pok.name)}</span>
          <StatusBadge status={pok.status} className="ml-auto" />
        </div>
        <HpBar hp={pok.hp} max={pok.max_hp} size="sm" className="mt-1" />
        {hasChips && (
          <div className="mt-1.5 flex flex-wrap gap-1">
            <StageChips stages={pok.stages} />
            <VolatileChips names={pok.vol_status} limit={2} />
          </div>
        )}
      </div>
    </div>
  );
}

function OutcomeCard({
  node,
  action,
  onSelect,
}: {
  node: TreeNode;
  action: ActionData;
  onSelect: (id: string) => void;
}) {
  const { opp, my, opp_move } = node.snapshot;
  const isDeath = node.snapshot.phase === "DEATH";
  const share = node.visits / Math.max(action.total_visits, 1);

  return (
    <button
      onClick={() => onSelect(node.id)}
      className="group w-full rounded-xl border bg-card p-3 text-left transition-all hover:border-foreground/20 hover:bg-elevated cursor-pointer"
    >
      {/* how often this branch happened + its win chance */}
      <div className="flex items-center gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-1.5">
            <span className="num text-base font-semibold">{fmtPct(share, 1)}</span>
            <span className="text-[11px] text-subtle-foreground">of rollouts</span>
          </div>
          <div className="mt-1 h-1 overflow-hidden rounded-full bg-foreground/8">
            <div className="h-full rounded-full bg-primary/70" style={{ width: `${share * 100}%` }} />
          </div>
        </div>
        <WinRing win={node.win_chance} size={40} />
      </div>

      {opp_move && (
        <div className="mt-2.5 flex items-center gap-1.5 text-xs text-muted-foreground">
          <CornerDownRight className="size-3" />
          Opp used <span className="font-medium text-foreground">{opp_move}</span>
        </div>
      )}

      <div className="mt-2.5 space-y-2 rounded-lg bg-background/50 p-2 ring-1 ring-foreground/5">
        {opp ? (
          <PokRow pok={opp} label="Opp" />
        ) : (
          <div className="text-xs text-muted-foreground italic">Opponent fainted</div>
        )}
        <div className="h-px bg-foreground/6" />
        {isDeath ? (
          <div className="flex items-center gap-1.5 text-xs text-bad">
            <Skull className="size-3.5" /> Your Pokémon fainted
          </div>
        ) : my ? (
          <PokRow pok={my} label="You" />
        ) : (
          <div className="text-xs text-bad italic">Yours fainted</div>
        )}
      </div>

      <div className="mt-2.5 flex items-center justify-between">
        <span className="num text-[11px] text-subtle-foreground">
          {fmtInt(node.visits)} visits · {node.dead_avg.toFixed(2)} deaths
        </span>
        <span className="flex items-center gap-1 text-xs font-medium text-primary opacity-80 transition-opacity group-hover:opacity-100">
          Explore <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" />
        </span>
      </div>
    </button>
  );
}

interface Props {
  action: ActionData | null;
  onSelect: (nodeId: string) => void;
  onClose: () => void;
}

// Right pane: the outcomes of the selected action, most visited first
export default function OutcomeInspector({ action, onSelect, onClose }: Props) {
  return (
    <aside className="flex min-h-0 flex-col border-l bg-card/40">
      <div className="flex h-11 shrink-0 items-center justify-between border-b px-3">
        <span className="text-[11px] font-medium tracking-wider text-subtle-foreground uppercase">
          Outcomes
        </span>
        {action && (
          <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="Clear selection">
            <X />
          </Button>
        )}
      </div>

      {!action ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 px-8 text-center">
          <div className="flex size-10 items-center justify-center rounded-full bg-foreground/5 ring-1 ring-foreground/10">
            <MousePointerClick className="size-4 text-muted-foreground" />
          </div>
          <p className="text-sm text-muted-foreground">
            Select a move or switch to see what can happen next.
          </p>
          <p className="text-[11px] text-subtle-foreground">
            Actions with a single outcome open directly. Shortcut: <Kbd>1</Kbd>–<Kbd>9</Kbd>
          </p>
        </div>
      ) : (
        <>
          {/* aggregate for the action */}
          <div className="shrink-0 border-b p-3">
            <div className="flex items-center gap-3">
              <WinRing win={action.win_chance} size={52} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <span className="truncate text-base font-semibold tracking-tight">
                    {action.action_type === 2
                      ? `Switch to ${switchTarget(action.label)}`
                      : action.label}
                  </span>
                </div>
                <div className="mt-1 flex items-center gap-1.5">
                  {action.move_type && <TypeBadge type={action.move_type} />}
                  <CategoryIcon category={action.category} />
                  {!!action.power && (
                    <span className="num text-[11px] text-muted-foreground">{action.power} BP</span>
                  )}
                </div>
              </div>
            </div>
            <div className="mt-3 grid grid-cols-3 gap-2 text-center">
              {[
                ["Win", fmtPct(action.win_chance, 1), TIER_TEXT[winTier(action.win_chance)]],
                ["Deaths", action.dead_avg.toFixed(2), "text-foreground"],
                ["Visits", fmtInt(action.total_visits), "text-muted-foreground"],
              ].map(([label, value, color]) => (
                <div key={label} className="rounded-lg bg-background/50 py-1.5 ring-1 ring-foreground/5">
                  <div className={cn("num text-sm font-semibold", color)}>{value}</div>
                  <div className="text-[10px] tracking-wider text-subtle-foreground uppercase">
                    {label}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3">
            {action.nodes.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground italic">
                No outcomes above the visit threshold yet.
              </p>
            ) : (
              [...action.nodes]
                .sort((a, b) => b.visits - a.visits)
                .map((node) => (
                  <OutcomeCard key={node.id} node={node} action={action} onSelect={onSelect} />
                ))
            )}
          </div>
        </>
      )}
    </aside>
  );
}
