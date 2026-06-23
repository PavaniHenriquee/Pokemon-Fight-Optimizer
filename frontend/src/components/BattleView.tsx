import type { TreeNode, PokemonState } from "../types";

const animFront = (id: number) =>
  `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/versions/generation-v/black-white/animated/${id}.gif`;
const animBack = (id: number) =>
  `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/versions/generation-v/black-white/animated/back/${id}.gif`;
const staticFront = (id: number) =>
  `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${id}.png`;
const staticBack = (id: number) =>
  `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/back/${id}.png`;

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

function WinRing({ win, size = 44 }: { win: number; size?: number }) {
  const strokeWidth = 3;
  const r = (size - strokeWidth * 2) / 2;
  const circ = 2 * Math.PI * r;
  const fill = win * circ;
  const color = win > 0.65 ? "#4ade80" : win > 0.4 ? "#fbbf24" : "#f87171";
  const cx = size / 2;
  const showPct = size >= 38;

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
          fontSize: size >= 44 ? "0.6rem" : size >= 38 ? "0.54rem" : "0.46rem",
          fontWeight: 800,
          color,
          lineHeight: 1,
          letterSpacing: "-0.02em",
        }}
      >
        {Math.round(win * 100)}
        {showPct ? "%" : ""}
      </span>
    </div>
  );
}

function HpBar({ pok }: { pok: PokemonState }) {
  const pct = pok.hp / pok.max_hp;
  const color = hpColor(pok.hp, pok.max_hp);
  const range = hpRange(pok.hp, pok.max_hp);
  return (
    <div
      style={{ display: "flex", alignItems: "center", gap: 5, width: "100%" }}
    >
      <span
        style={{
          fontSize: "0.58rem",
          fontWeight: 800,
          color: "var(--muted)",
          letterSpacing: "0.08em",
          flexShrink: 0,
          width: 16,
        }}
      >
        HP
      </span>
      <div
        style={{
          flex: 1,
          height: 5,
          background: "rgba(255,255,255,0.08)",
          borderRadius: 3,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${(pct * 100).toFixed(1)}%`,
            background: color,
            borderRadius: 3,
            transition: "width 0.4s ease",
          }}
        />
      </div>
      <span
        style={{
          fontSize: "0.62rem",
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
  );
}

function BattleSprite({
  pok,
  side,
}: {
  pok: PokemonState;
  side: "mine" | "opp";
}) {
  return (
    <img
      src={side === "opp" ? animFront(pok.id) : animBack(pok.id)}
      alt={pok.name}
      style={{
        imageRendering: "pixelated",
        height: 80,
        objectFit: "contain",
        display: "block",
      }}
      onError={(e) => {
        const img = e.currentTarget;
        if (!img.dataset.fallen) {
          img.dataset.fallen = "1";
          img.src = side === "opp" ? staticFront(pok.id) : staticBack(pok.id);
        }
      }}
    />
  );
}

function BattleSlot({
  pok,
  side,
}: {
  pok: PokemonState | null;
  side: "mine" | "opp";
}) {
  if (!pok) {
    return (
      <div
        style={{
          flex: 1,
          minHeight: 120,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--muted)",
          fontStyle: "italic",
          fontSize: "0.8rem",
        }}
      >
        fainted
      </div>
    );
  }

  const stages = Object.entries(pok.stages);

  const pokInfo = (
    <div style={{ width: "100%" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 5,
          flexWrap: "wrap",
          marginBottom: 4,
        }}
      >
        <span style={{ fontWeight: 700, fontSize: "0.9rem", color: "#f1f5f9" }}>
          {pok.name}
        </span>
        {pok.status && <span className="badge status-badge">{pok.status}</span>}
        {pok.vol_status.map((s) => (
          <span key={s} className="badge vol-badge">
            {s}
          </span>
        ))}
      </div>
      <HpBar pok={pok} />
      {stages.length > 0 && (
        <div
          style={{ display: "flex", flexWrap: "wrap", gap: 3, marginTop: 4 }}
        >
          {stages.map(([stat, val]) => (
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

  const spriteWrapper = (
    <div
      style={{
        display: "flex",
        justifyContent: side === "opp" ? "flex-end" : "flex-start",
      }}
    >
      <BattleSprite pok={pok} side={side} />
    </div>
  );

  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        gap: 6,
      }}
    >
      {side === "opp" ? (
        <>
          {pokInfo}
          {spriteWrapper}
        </>
      ) : (
        <>
          {spriteWrapper}
          {pokInfo}
        </>
      )}
    </div>
  );
}

export default function BattleView({ node }: { node: TreeNode }) {
  const { snapshot } = node;
  const isDeath = snapshot.phase === "DEATH";
  const bestAction =
    Object.values(node.actions).sort(
      (a, b) => b.total_visits - a.total_visits,
    )[0] ?? null;

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

      <div
        style={{
          display: "flex",
          gap: 12,
          alignItems: "stretch",
          minHeight: 128,
        }}
      >
        {isDeath ? (
          <div
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--muted)",
              fontSize: "0.82rem",
              fontStyle: "italic",
            }}
          >
            Choose a Pokémon ↓
          </div>
        ) : (
          <BattleSlot pok={snapshot.my} side="mine" />
        )}
        <span
          style={{
            alignSelf: "center",
            color: "var(--muted)",
            fontSize: "0.68rem",
            fontWeight: 700,
            flexShrink: 0,
          }}
        >
          VS
        </span>
        <BattleSlot pok={snapshot.opp} side="opp" />
      </div>

      <div className="node-stats">
        <span>
          <strong>{node.visits.toLocaleString()}</strong> visits
        </span>
        {bestAction ? (
          <>
            <WinRing win={bestAction.win_chance} size={44} />
            <span>
              <strong>{bestAction.dead_avg.toFixed(2)}</strong> exp. deaths
            </span>
            <span className="best-action-label">if {bestAction.label}</span>
          </>
        ) : (
          <span className="muted">no actions explored yet</span>
        )}
        {snapshot.terminal && (
          <span className="badge terminal-badge">TERMINAL</span>
        )}
      </div>
    </section>
  );
}
