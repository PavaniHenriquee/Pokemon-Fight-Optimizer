import { Flag, Sparkle } from "lucide-react";
import { cn } from "@/lib/utils";
import { pokIcon } from "@/lib/sprites";
import {
  TIER_TEXT,
  displayName,
  fmtInt,
  switchTarget,
  typeColor,
  winTier,
} from "@/lib/format";
import { bestActionKey, orderActions } from "@/lib/tree";
import type { TreeNode, ActionData, BenchEntry } from "../types";
import { Sprite } from "./common/Sprite";
import { HpBar } from "./common/HpBar";
import { CategoryIcon, Kbd, StatusBadge, TypeBadge } from "./common/Badges";

interface Props {
  node: TreeNode;
  onActionClick: (key: string) => void;
  selectedKey: string | null;
}

function SectionTitle({ children, count }: { children: React.ReactNode; count?: number }) {
  return (
    <div className="mb-2 flex items-center gap-2">
      <span className="text-[11px] font-medium tracking-wider text-subtle-foreground uppercase">
        {children}
      </span>
      {count !== undefined && <span className="num text-[11px] text-subtle-foreground/70">{count}</span>}
      <div className="h-px flex-1 bg-border" />
    </div>
  );
}

// Win% is the headline, visits stay a faint bar at the bottom edge
function CardShell({
  action,
  isBest,
  isSelected,
  shortcut,
  maxVisits,
  onClick,
  stripe,
  footer,
  children,
}: {
  action: ActionData;
  isBest: boolean;
  isSelected: boolean;
  shortcut?: number;
  maxVisits: number;
  onClick: () => void;
  stripe?: string;
  footer?: React.ReactNode;
  children: React.ReactNode;
}) {
  const visitPct = (action.total_visits / maxVisits) * 100;
  return (
    <button
      onClick={onClick}
      className={cn(
        "group relative flex flex-col overflow-hidden rounded-xl border bg-card p-3 text-left transition-all cursor-pointer",
        "hover:-translate-y-px hover:border-foreground/20 hover:bg-elevated hover:shadow-lg hover:shadow-black/20",
        isSelected && "border-primary bg-elevated ring-2 ring-primary/40",
        !isSelected && isBest && "border-primary/45 shadow-[0_0_24px_-12px_var(--primary)]",
        stripe && "pl-4",
      )}
    >
      {stripe && (
        <span className="absolute inset-y-0 left-0 w-1" style={{ background: stripe }} />
      )}
      {children}
      <div className="mt-2 flex items-end justify-between gap-2">
        <span className={cn("num text-2xl leading-none font-semibold tracking-tight", TIER_TEXT[winTier(action.win_chance)])}>
          {Math.round(action.win_chance * 100)}
          <span className="text-base opacity-70">%</span>
        </span>
        <span className="num text-right text-[11px] leading-tight text-muted-foreground">
          {action.dead_avg.toFixed(2)} deaths
          <br />
          <span className="text-subtle-foreground">
            {action.nodes.length} outcome{action.nodes.length === 1 ? "" : "s"}
          </span>
        </span>
      </div>
      <div className="num mt-1.5 flex items-center justify-between gap-2 text-[10px] whitespace-nowrap text-subtle-foreground">
        <span>{footer}</span>
        <span>{fmtInt(action.total_visits)} visits</span>
      </div>
      {/* visit share relative to the most visited action */}
      <div className="absolute inset-x-0 bottom-0 h-0.5 bg-foreground/4">
        <div
          className={cn(
            "h-full transition-[width] duration-500",
            isBest ? "bg-primary" : "bg-foreground/20",
          )}
          style={{ width: `${visitPct}%` }}
        />
      </div>
      {shortcut !== undefined && shortcut <= 9 && (
        <Kbd className="absolute top-2 right-2 opacity-0 transition-opacity group-hover:opacity-100">
          {shortcut}
        </Kbd>
      )}
    </button>
  );
}

function BestPill() {
  return (
    <span className="inline-flex h-[18px] shrink-0 items-center gap-0.5 rounded-full bg-primary/18 px-1.5 text-[10px] font-semibold text-primary ring-1 ring-primary/35">
      <Sparkle className="size-2.5 fill-current" /> Best
    </span>
  );
}

function MoveCard(props: {
  action: ActionData;
  isBest: boolean;
  isSelected: boolean;
  shortcut: number;
  maxVisits: number;
  onClick: () => void;
}) {
  const { action, isBest } = props;
  const outOfPp = action.current_pp != null && action.current_pp <= 0;
  return (
    <CardShell
      {...props}
      stripe={action.move_type ? typeColor(action.move_type) : undefined}
      footer={
        action.max_pp != null && (
          <span className={cn("text-[11px]", outOfPp ? "font-semibold text-bad" : "text-muted-foreground")}>
            PP {action.current_pp ?? 0}
            <span className="opacity-60">/{action.max_pp}</span>
          </span>
        )
      }
    >
      <div className="flex items-center gap-2 pr-5">
        <span className="truncate text-[15px] font-semibold tracking-tight">{action.label}</span>
        {isBest && <BestPill />}
      </div>
      <div className="mt-1.5 flex items-center gap-1.5 text-[11px] whitespace-nowrap text-muted-foreground">
        {action.move_type && <TypeBadge type={action.move_type} height={14} />}
        <CategoryIcon category={action.category} />
        {!!action.power && <span className="num">{action.power} BP</span>}
      </div>
    </CardShell>
  );
}

function SwitchCard(props: {
  action: ActionData;
  bench?: BenchEntry;
  isBest: boolean;
  isSelected: boolean;
  shortcut: number;
  maxVisits: number;
  onClick: () => void;
}) {
  const { action, bench, isBest } = props;
  const pokId = bench?.id ?? action.nodes[0]?.snapshot.my?.id;
  const name = bench ? displayName(bench.name) : switchTarget(action.label);
  return (
    <CardShell {...props}>
      <div className="flex items-center gap-2 pr-5">
        {pokId !== undefined && (
          <Sprite srcs={pokIcon(pokId)} alt="" width={40} height={30} className="-my-1 -ml-1 object-contain" />
        )}
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-1.5">
            <span className="truncate text-sm font-semibold">{name}</span>
            {isBest && <BestPill />}
          </span>
          {bench && (
            <span className="mt-1 flex items-center gap-1.5">
              <HpBar hp={bench.hp} max={bench.max_hp} size="xs" showLabel={false} showText={false} />
              <StatusBadge status={bench.status} />
            </span>
          )}
        </span>
      </div>
    </CardShell>
  );
}

function Placeholder({ className }: { className?: string }) {
  return <div className={cn("rounded-xl border border-dashed border-foreground/8", className)} />;
}

export default function ActionPanel({ node, onActionClick, selectedKey }: Props) {
  const { snapshot } = node;

  if (snapshot.terminal) {
    return (
      <section className="px-4 pb-4">
        <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed py-8 text-muted-foreground">
          <Flag className="size-5" />
          <p className="text-sm">Battle over: this is a terminal state.</p>
        </div>
      </section>
    );
  }

  const ordered = orderActions(node);
  if (ordered.length === 0) {
    return (
      <section className="px-4 pb-4">
        <div className="rounded-xl border border-dashed px-6 py-7 text-center">
          <p className="text-sm text-muted-foreground">Not explored enough below this point yet.</p>
          <p className="mt-1 text-xs text-subtle-foreground">
            Actions show up once they pass 100 visits. Let the search run longer, or use
            Continue from here to focus the search on this position.
          </p>
        </div>
      </section>
    );
  }

  const maxVisits = Math.max(...ordered.map(([, a]) => a.total_visits), 1);
  const bestKey = bestActionKey(node) ?? "";
  const isDeath = snapshot.phase === "DEATH";
  const isBatonPass = snapshot.phase === "BATON_PASS";
  const moves = ordered.filter(([, a]) => a.action_type === 1);
  const switches = ordered.filter(([, a]) => a.action_type === 2);
  const benchBySlot = new Map(snapshot.my_bench.map((b) => [b.slot, b]));
  const shortcutOf = (key: string) => ordered.findIndex(([k]) => k === key) + 1;

  return (
    <section className="space-y-4 px-4 pb-5">
      {!isDeath && moves.length > 0 && (
        <div>
          <SectionTitle count={moves.length}>Moves</SectionTitle>
          <div className="grid grid-cols-4 gap-3">
            {moves.map(([key, action]) => (
              <MoveCard
                key={key}
                action={action}
                isBest={key === bestKey}
                isSelected={key === selectedKey}
                shortcut={shortcutOf(key)}
                maxVisits={maxVisits}
                onClick={() => onActionClick(key)}
              />
            ))}
            {Array.from({ length: Math.max(0, 4 - moves.length) }).map((_, i) => (
              <Placeholder key={`mp-${i}`} className="min-h-[118px]" />
            ))}
          </div>
        </div>
      )}

      {switches.length > 0 && (
        <div>
          <SectionTitle count={switches.length}>
            {isDeath ? "Switch to" : isBatonPass ? "Baton Pass to" : "Switches"}
          </SectionTitle>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(160px,1fr))] gap-3">
            {switches.map(([key, action]) => (
              <SwitchCard
                key={key}
                action={action}
                bench={benchBySlot.get(action.action_idx)}
                isBest={key === bestKey}
                isSelected={key === selectedKey}
                shortcut={shortcutOf(key)}
                maxVisits={maxVisits}
                onClick={() => onActionClick(key)}
              />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

