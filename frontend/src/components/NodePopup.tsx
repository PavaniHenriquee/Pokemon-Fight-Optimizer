// Overlay that shows the possible outcomes for a clicked action.
// The user picks which outcome/node to navigate into.

import type { ActionData, TreeNode } from "../types";

// Summarises one outcome node so the user can distinguish them
function OutcomeCard({
  node,
  onSelect,
}: {
  node: TreeNode;
  onSelect: (id: string) => void;
}) {
  const { opp, my } = node.snapshot;

  function PokLine({ pok, label }: { pok: typeof opp; label: string }) {
    if (!pok) return <span className="outcome-pok">{label}: fainted</span>;
    const pct = Math.round((pok.hp / pok.max_hp) * 100);
    const pctLabel =
      pct === 0
        ? "Dead"
        : pct >= 75
          ? "75%-100%"
          : pct >= 50
            ? "50%-74%"
            : pct >= 25
              ? "25%-49%"
              : "1%-24%";
    return (
      <span className="outcome-pok">
        <strong>
          {label}: {pok.name}
        </strong>{" "}
        {pctLabel}
        {pok.status && <span className="badge status-badge">{pok.status}</span>}
        {pok.vol_status.map((s) => (
          <span key={s} className="badge vol-badge">
            {s}
          </span>
        ))}
      </span>
    );
  }

  return (
    <div className="outcome-card">
      <div className="outcome-snapshot">
        {node.snapshot.phase === "DEATH" && (
          <span className="badge terminal-badge">Fainted</span>
        )}
        <PokLine pok={opp} label="Opp" />
        <PokLine pok={my} label="Yours" />
      </div>

      <div className="outcome-footer">
        <span className="action-stats">
          <span>{node.visits.toLocaleString()} v</span>
          <span>{(node.win_chance * 100).toFixed(1)}% win</span>
          <span>{node.dead_avg.toFixed(2)} dead</span>
        </span>
        <button className="btn btn-primary" onClick={() => onSelect(node.id)}>
          Explore →
        </button>
      </div>
    </div>
  );
}

interface Props {
  action: ActionData;
  onSelect: (nodeId: string) => void;
  onClose: () => void;
}

export default function NodePopup({ action, onSelect, onClose }: Props) {
  // Sorted highest-visits first
  const sorted = [...action.nodes].sort((a, b) => b.visits - a.visits);

  return (
    // Clicking the dark overlay closes the popup
    <div className="popup-overlay" onClick={onClose}>
      {/* stopPropagation prevents the panel click from also closing */}
      <div className="popup-panel" onClick={(e) => e.stopPropagation()}>
        <div className="popup-header">
          <h2>
            After: <em>{action.label}</em>
          </h2>
          <button className="close-btn" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="popup-aggregate">
          {action.total_visits.toLocaleString()} visits total &nbsp;·&nbsp;
          {(action.win_chance * 100).toFixed(1)}% win &nbsp;·&nbsp;
          {action.dead_avg.toFixed(2)} avg deaths
        </div>

        {sorted.length === 0 ? (
          <p className="panel-empty">
            No outcomes above visit threshold yet — check back after more
            iterations.
          </p>
        ) : (
          <div className="outcome-list">
            {sorted.map((node) => (
              <OutcomeCard key={node.id} node={node} onSelect={onSelect} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
