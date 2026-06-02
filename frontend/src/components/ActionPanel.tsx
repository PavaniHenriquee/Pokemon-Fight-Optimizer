// The list of action cards at the bottom. Sorted by visits, best first.

import type { TreeNode } from "../types";

function WinBar({ win }: { win: number }) {
  const color = win > 0.65 ? "#4ade80" : win > 0.4 ? "#fbbf24" : "#f87171";
  return (
    <div className="bar-track">
      <div
        className="bar-fill"
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
  const isDeath = snapshot.phase === "DEATH";

  // Sort by total_visits descending so the MCTS recommendation is always first
  const sorted = Object.entries(node.actions).sort(
    ([, a], [, b]) => b.total_visits - a.total_visits,
  );

  if (snapshot.terminal) {
    return (
      <section className="action-panel">
        <p className="panel-empty">Battle over — this is a terminal state.</p>
      </section>
    );
  }

  if (sorted.length === 0) {
    return (
      <section className="action-panel">
        <p className="panel-empty">No explored actions yet…</p>
      </section>
    );
  }

  return (
    <section className="action-panel">
      <h2 className="panel-title">
        {isDeath ? "Switch to:" : "Available Actions"}
      </h2>

      <div className="action-list">
        {sorted.map(([key, action], idx) => (
          <button
            key={key}
            className={[
              "action-card",
              idx === 0 ? "best" : "",
              key === selectedKey ? "selected" : "",
            ].join(" ")}
            onClick={() => onActionClick(key)}
          >
            <div className="action-top">
              <span className="action-label">
                {idx === 0 && <span className="star">★ </span>}
                {action.label}
              </span>
              <span className="action-meta">
                {action.total_visits.toLocaleString()} v
              </span>
            </div>

            <WinBar win={action.win_chance} />

            <div className="action-stats">
              <span>{(action.win_chance * 100).toFixed(1)}% win</span>
              <span>{action.dead_avg.toFixed(2)} dead</span>
              <span>
                {action.nodes.length} outcome
                {action.nodes.length !== 1 ? "s" : ""}
              </span>
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}
