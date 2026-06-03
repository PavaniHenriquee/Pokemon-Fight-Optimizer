// Shows the current battle state: both active Pokemon + node statistics.

import type { TreeNode, PokemonState } from "../types";

// ─── helpers ─────────────────────────────────────────────────────────────────

function hpColor(hp: number, max: number) {
  const pct = hp / max;
  if (pct > 0.5) return "#4ade80"; // green
  if (pct > 0.25) return "#fbbf24"; // yellow
  return "#f87171"; // red
}

function winColor(w: number) {
  if (w > 0.65) return "#4ade80";
  if (w > 0.4) return "#fbbf24";
  return "#f87171";
}

// ─── one Pokemon card ─────────────────────────────────────────────────────────

function PokCard({ pok, label }: { pok: PokemonState | null; label: string }) {
  if (!pok) {
    return (
      <div className="pok-card empty">
        <span>{label}: fainted</span>
      </div>
    );
  }

  const nonZeroStages = Object.entries(pok.stages);
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
    <div className="pok-card">
      <div className="pok-header">
        <span className="pok-label">{label}</span>
        <span className="pok-name">{pok.name}</span>
        {pok.status && <span className="badge status-badge">{pok.status}</span>}
      </div>

      {/* HP bar */}
      <div className="hp-row">
        <div className="bar-track">
          <div
            className="bar-fill"
            style={{
              width: `${((pok.hp / pok.max_hp) * 100).toFixed(1)}%`,
              background: hpColor(pok.hp, pok.max_hp),
            }}
          />
        </div>
        <span className="hp-text">{pctLabel}</span>
      </div>

      {/* Volatile statuses */}
      {pok.vol_status.length > 0 && (
        <div className="badge-row">
          {pok.vol_status.map((s) => (
            <span key={s} className="badge vol-badge">
              {s}
            </span>
          ))}
        </div>
      )}

      {/* Stat stages — only show non-zero ones */}
      {nonZeroStages.length > 0 && (
        <div className="badge-row">
          {nonZeroStages.map(([stat, val]) => (
            <span
              key={stat}
              className={`badge stage-badge ${val > 0 ? "up" : "down"}`}
            >
              {stat} {val > 0 ? "+" : ""}
              {val}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── main component ───────────────────────────────────────────────────────────

export default function BattleView({ node }: { node: TreeNode }) {
  const { snapshot, visits, win_chance, dead_avg } = node;
  const isDeath = snapshot.phase === "DEATH";
  const bestAction = Object.values(node.actions).sort(
    (a, b) => b.total_visits - a.total_visits
  )[0] ?? null

  return (
    <section className="battle-view">
      {isDeath && (
        <div className="death-banner">
          ⚠ Your Pokémon fainted — choose a replacement below
        </div>
      )}

      {snapshot.opp_move && (
        <div className="opp-move-banner">
          Opp used: <strong>{snapshot.opp_move}</strong>
        </div>
      )}

      <div className="battle-field">
        <PokCard pok={isDeath ? null : snapshot.my} label="Yours" />
        <span className="versus">VS</span>
        <PokCard pok={snapshot.opp} label="Opponent" />
      </div>

      <div className="node-stats">
        <span><strong>{node.visits.toLocaleString()}</strong> visits</span>
        {bestAction ? (
          <>
            <span style={{ color: winColor(bestAction.win_chance) }}>
              <strong>{(bestAction.win_chance * 100).toFixed(1)}%</strong> win
            </span>
            <span><strong>{bestAction.dead_avg.toFixed(2)}</strong> avg deaths</span>
            <span className="best-action-label">if {bestAction.label}</span>
          </>
        ) : (
          <span className="muted">no actions explored yet</span>
        )}
        {snapshot.terminal && <span className="badge terminal-badge">TERMINAL</span>}
      </div>
    </section>
  );
}
