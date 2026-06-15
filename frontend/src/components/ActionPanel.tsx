// The list of action cards at the bottom. Sorted by visits, best first.
import type { TreeNode, ActionData } from "../types";

function WinBar({ win }: { win: number }) {
  const color = win > 0.65 ? "#4ade80" : win > 0.4 ? "#fbbf24" : "#f87171";
  return (
    <div className="w-full h-1.5 bg-slate-700 rounded-full overflow-hidden">
      <div
        className="h-full rounded-full transition-all duration-300"
        style={{ width: `${(win * 100).toFixed(1)}%`, background: color }}
      />
    </div>
  );
}

interface Props {
  node: TreeNode;
  onActionClick: (key: string) => void;
  selectedKey: string | null;
}

export default function ActionPanel({
  node,
  onActionClick,
  selectedKey,
}: Props) {
  const { snapshot } = node;

  if (snapshot.terminal) {
    return (
      <section className="flex-1 p-4 overflow-y-auto">
        <p className="text-slate-500 italic text-center py-8">
          Battle over — this is a terminal state.
        </p>
      </section>
    );
  }

  const sorted = Object.entries(node.actions).sort(([, a], [, b]) => {
    if (a.action_type !== b.action_type) return a.action_type - b.action_type;
    return b.total_visits - a.total_visits;
  });

  if (sorted.length === 0) {
    return (
      <section className="flex-1 p-4 overflow-y-auto">
        <p className="text-slate-500 italic text-center py-8">
          No explored actions yet…
        </p>
      </section>
    );
  }

  const bestKey =
    Object.entries(node.actions).sort(
      ([, a], [, b]) => b.total_visits - a.total_visits,
    )[0]?.[0] ?? "";

  const moves = sorted.filter(([, a]) => a.action_type === 1);
  const switches = sorted.filter(([, a]) => a.action_type === 2);

  const isDeath = snapshot.phase === "DEATH";

  function ActionCard({
    actionKey,
    action,
  }: {
    actionKey: string;
    action: ActionData;
  }) {
    const isBest = actionKey === bestKey;
    const isSelected = actionKey === selectedKey;
    return (
      <button
        onClick={() => onActionClick(actionKey)}
        className={[
          "flex flex-col gap-1.5 p-2.5 rounded-lg border text-left cursor-pointer transition-colors",
          "bg-[var(--surface)] text-[var(--text)]",
          isSelected
            ? "border-[var(--accent)] bg-[var(--surface2)]"
            : isBest
              ? "border-purple-500/40 hover:border-[var(--accent)] hover:bg-[var(--surface2)]"
              : "border-[var(--border)] hover:border-[var(--accent)] hover:bg-[var(--surface2)]",
        ].join(" ")}
      >
        <div className="flex justify-between items-baseline gap-1">
          <span className="font-semibold text-sm truncate">
            {isBest && <span className="text-[var(--accent)] mr-0.5">★</span>}
            {action.label}
          </span>
          <span className="text-[10px] text-slate-500 shrink-0">
            {action.total_visits.toLocaleString()}v
          </span>
        </div>

        <WinBar win={action.win_chance} />

        <div className="flex gap-2 text-[10px] text-slate-500">
          <span>{(action.win_chance * 100).toFixed(1)}%</span>
          <span>{action.dead_avg.toFixed(2)} Exp. Deaths</span>
          <span>{action.nodes.length} Outcomes</span>
        </div>
      </button>
    );
  }

  return (
    <section className="flex-1 p-4 overflow-y-auto space-y-4 min-h-0">
      {/* Moves row — always 4 columns, placeholders fill empty slots */}
      {!isDeath && moves.length > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-widest text-slate-500 mb-2">
            Moves
          </p>
          <div className="grid grid-cols-4 gap-2">
            {moves.map(([key, action]) => (
              <ActionCard key={key} actionKey={key} action={action} />
            ))}
            {Array.from({ length: 4 - moves.length }).map((_, i) => (
              <div
                key={`mp-${i}`}
                className="rounded-lg border border-dashed border-slate-700/40 h-20"
              />
            ))}
          </div>
        </div>
      )}

      {/* Switches row — up to 5 columns (6 pokemon minus 1 active) */}
      {switches.length > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-widest text-slate-500 mb-2">
            {isDeath ? "Switch to:" : "Switches"}
          </p>
          <div className="grid grid-cols-5 gap-2">
            {switches.map(([key, action]) => (
              <ActionCard key={key} actionKey={key} action={action} />
            ))}
            {Array.from({ length: 5 - switches.length }).map((_, i) => (
              <div
                key={`sp-${i}`}
                className="rounded-lg border border-dashed border-slate-700/40 h-20"
              />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
