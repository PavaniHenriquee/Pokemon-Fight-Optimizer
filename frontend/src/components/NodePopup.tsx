import type { ActionData, TreeNode } from "../types";

const gen7Icon = (id: number) =>
  `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/versions/generation-vii/icons/${id}.png`;

function hpColor(hp: number, max: number) {
  const pct = hp / max;
  return pct > 0.5 ? "#4ade80" : pct > 0.25 ? "#fbbf24" : "#f87171";
}

function hpRange(hp: number, max: number): string {
  const pct = hp / max;
  if (pct <= 0) return "Fainted";
  if (pct >= 0.75) return "75%–100%";
  if (pct >= 0.5) return "50%–74%";
  if (pct >= 0.25) return "25%–49%";
  return "1%–24%";
}

function WinRing({ win, size = 38 }: { win: number; size?: number }) {
  const strokeWidth = 3;
  const r = (size - strokeWidth * 2) / 2;
  const circ = 2 * Math.PI * r;
  const fill = win * circ;
  const color = win > 0.65 ? "#4ade80" : win > 0.4 ? "#fbbf24" : "#f87171";
  const cx = size / 2;

  return (
    <div
      style={{ position: "relative", width: size, height: size, flexShrink: 0 }}
    >
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle
          cx={cx}
          cy={cx}
          r={r}
          fill="none"
          stroke="rgba(255,255,255,0.08)"
          strokeWidth={strokeWidth}
        />
        <circle
          cx={cx}
          cy={cx}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeDasharray={`${fill} ${circ - fill}`}
          strokeLinecap="round"
          style={{ transition: "stroke-dasharray 0.4s ease, stroke 0.3s" }}
        />
      </svg>
      <span
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: "0.54rem",
          fontWeight: 800,
          color,
          lineHeight: 1,
          letterSpacing: "-0.02em",
        }}
      >
        {Math.round(win * 100)}%
      </span>
    </div>
  );
}

function PokRow({
  pok,
  label,
}: {
  pok: NonNullable<TreeNode["snapshot"]["my"]>;
  label: string;
}) {
  const pct = pok.hp / pok.max_hp;
  const color = hpColor(pok.hp, pok.max_hp);
  const range = hpRange(pok.hp, pok.max_hp);

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
      <img
        src={gen7Icon(pok.id)}
        alt={pok.name}
        style={{
          width: 34,
          height: 26,
          imageRendering: "pixelated",
          objectFit: "contain",
          flexShrink: 0,
        }}
      />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 4,
            marginBottom: 3,
            flexWrap: "wrap",
          }}
        >
          <span
            style={{
              fontSize: "0.6rem",
              color: "var(--muted)",
              textTransform: "uppercase",
              letterSpacing: "0.06em",
            }}
          >
            {label}
          </span>
          <span style={{ fontWeight: 600, fontSize: "0.85rem" }}>
            {pok.name}
          </span>
          {pok.status && (
            <span className="badge status-badge">{pok.status}</span>
          )}
          {pok.vol_status.slice(0, 2).map((s) => (
            <span key={s} className="badge vol-badge">
              {s}
            </span>
          ))}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span
            style={{
              fontSize: "0.56rem",
              fontWeight: 800,
              color: "var(--muted)",
              letterSpacing: "0.08em",
              width: 14,
              flexShrink: 0,
            }}
          >
            HP
          </span>
          <div
            style={{
              flex: 1,
              height: 4,
              background: "rgba(255,255,255,0.08)",
              borderRadius: 2,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                height: "100%",
                width: `${(pct * 100).toFixed(1)}%`,
                background: color,
                borderRadius: 2,
              }}
            />
          </div>
          <span
            style={{
              fontSize: "0.6rem",
              color,
              fontWeight: 600,
              width: 62,
              textAlign: "right",
              flexShrink: 0,
            }}
          >
            {range}
          </span>
        </div>
        {Object.keys(pok.stages).length > 0 && (
          <div className="flex flex-row flex-wrap gap-3 mt-1">
            {Object.entries(pok.stages).map(([stat, val]) => (
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
    </div>
  );
}

function OutcomeCard({
  node,
  onSelect,
  action,
}: {
  node: TreeNode;
  onSelect: (id: string) => void;
  action: ActionData;
}) {
  const { opp, my, opp_move } = node.snapshot;
  const isDeath = node.snapshot.phase === "DEATH";
  const rolloutPct = ((node.visits / action.total_visits) * 100).toFixed(1);

  return (
    <div className="outcome-card">
      {opp_move && (
        <div className="opp-move-banner" style={{ marginBottom: 8 }}>
          Opp used: <strong>{opp_move}</strong>
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
        {opp ? (
          <PokRow pok={opp} label="Opp" />
        ) : (
          <span
            style={{
              fontSize: "0.8rem",
              color: "var(--muted)",
              fontStyle: "italic",
            }}
          >
            Opponent fainted
          </span>
        )}

        <div style={{ height: 1, background: "rgba(255,255,255,0.06)" }} />

        {isDeath ? (
          <div
            style={{
              fontSize: "0.78rem",
              color: "var(--red)",
              display: "flex",
              alignItems: "center",
              gap: 5,
            }}
          >
            ⚠ Your Pokémon fainted
          </div>
        ) : my ? (
          <PokRow pok={my} label="You" />
        ) : (
          <span
            style={{
              fontSize: "0.8rem",
              color: "var(--red)",
              fontStyle: "italic",
            }}
          >
            Yours fainted
          </span>
        )}
      </div>

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginTop: 10,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
          <WinRing win={node.win_chance} size={38} />
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            <span style={{ fontSize: "0.72rem" }}>
              <strong>{rolloutPct}%</strong>
              <span style={{ color: "var(--muted)" }}> of rollouts</span>
            </span>
            <span
              style={{ fontSize: "0.62rem", color: "rgba(120,128,160,0.6)" }}
            >
              {node.visits.toLocaleString()} visits · {node.dead_avg.toFixed(2)}{" "}
              deaths
            </span>
          </div>
        </div>
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
  const sorted = [...action.nodes].sort((a, b) => b.visits - a.visits);

  return (
    <div className="popup-overlay" onClick={onClose}>
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
          {action.total_visits.toLocaleString()} visits ·{" "}
          {(action.win_chance * 100).toFixed(1)}% win ·{" "}
          {action.dead_avg.toFixed(2)} avg deaths
        </div>

        {sorted.length === 0 ? (
          <p className="panel-empty">No outcomes above visit threshold yet.</p>
        ) : (
          <div className="outcome-list">
            {sorted.map((node) => (
              <OutcomeCard
                key={node.id}
                node={node}
                onSelect={onSelect}
                action={action}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
