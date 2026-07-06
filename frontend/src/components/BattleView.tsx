import { HoverCard, HoverCardTrigger, HoverCardContent } from "./ui/hover-card";
import type { TreeNode, PokemonState, BenchEntry } from "../types";

// ── Sprite URLs ───────────────────────────────────────────────────────────────
const animFront = (id: number) =>
  `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/versions/generation-v/black-white/animated/${id}.gif`;
const animBack = (id: number) =>
  `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/versions/generation-v/black-white/animated/back/${id}.gif`;
const staticFront = (id: number) =>
  `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${id}.png`;
const staticBack = (id: number) =>
  `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/back/${id}.png`;
const gen7Icon = (id: number) =>
  `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/versions/generation-vii/icons/${id}.png`;
const itemIcon = (name: string) =>
  `https://play.pokemonshowdown.com/sprites/itemicons/${name.toLowerCase().replace(/[\s_]+/g, "-")}.png`;

// ── Helpers ───────────────────────────────────────────────────────────────────
function hpColor(hp: number, max: number) {
  const pct = hp / Math.max(max, 1);
  return pct > 0.5 ? "#4ade80" : pct > 0.25 ? "#fbbf24" : "#f87171";
}

function hpRange(hp: number, max: number): string {
  const pct = hp / Math.max(max, 1);
  if (pct <= 0) return "Fainted";
  if (pct === 1) return "100%";
  if (pct >= 0.75) return "75%–100%";
  if (pct >= 0.5) return "50%–74%";
  if (pct >= 0.25) return "25%–49%";
  return "1%–24%";
}

// ── Win Ring ──────────────────────────────────────────────────────────────────
function WinRing({ win, size = 44 }: { win: number; size?: number }) {
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
          fontSize: size >= 44 ? "0.6rem" : "0.54rem",
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

// ── HP Bar ────────────────────────────────────────────────────────────────────
function HpBar({ pok }: { pok: PokemonState }) {
  const pct = pok.hp / Math.max(pok.max_hp, 1);
  const color = hpColor(pok.hp, pok.max_hp);
  return (
    <div
      style={{ display: "flex", alignItems: "center", gap: 6, width: "100%" }}
    >
      <span
        style={{
          fontSize: "0.56rem",
          fontWeight: 800,
          color: "var(--muted)",
          letterSpacing: "0.1em",
          flexShrink: 0,
          width: 16,
        }}
      >
        HP
      </span>
      <div
        style={{
          flex: 1,
          height: 6,
          background: "rgba(255,255,255,0.07)",
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
            boxShadow: `0 0 8px ${color}55`,
          }}
        />
      </div>
      <span
        style={{
          fontSize: "0.62rem",
          color,
          fontWeight: 700,
          width: 62,
          textAlign: "right",
          flexShrink: 0,
        }}
      >
        {hpRange(pok.hp, pok.max_hp)}
      </span>
    </div>
  );
}

// ── Active Pokémon info block ──────────────────────────────────────────────────
function PokInfo({ pok, label }: { pok: PokemonState; label: string }) {
  const stages = Object.entries(pok.stages);
  return (
    <div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 5,
          marginBottom: 6,
          flexWrap: "wrap",
        }}
      >
        <span
          style={{
            fontSize: "0.56rem",
            color: "var(--muted)",
            textTransform: "uppercase",
            letterSpacing: "0.1em",
          }}
        >
          {label}
        </span>
        <span
          style={{
            fontWeight: 700,
            fontSize: "1rem",
            color: "#f1f5f9",
            lineHeight: 1,
          }}
        >
          {pok.name}
        </span>
        {pok.status && <span className="badge status-badge">{pok.status}</span>}
        {pok.vol_status.map((s) => (
          <span key={s} className="badge vol-badge">
            {s}
          </span>
        ))}
      </div>
      {pok.item && (
        <img
          src={itemIcon(pok.item)}
          alt={pok.item}
          title={pok.item}
          width={16}
          height={16}
          style={{ imageRendering: "pixelated", flexShrink: 0 }}
          onError={(e) => {
            e.currentTarget.style.display = "none";
          }}
        />
      )}
      <HpBar pok={pok} />
      {stages.length > 0 && (
        <div
          style={{ display: "flex", flexWrap: "wrap", gap: 3, marginTop: 5 }}
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
}

// ── Battle sprite ─────────────────────────────────────────────────────────────
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
        height: 84,
        filter: "drop-shadow(0 4px 10px rgba(0,0,0,0.5))",
      }}
      className="object-contain block mx-auto mw-100 item-center"
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

// ── Pokéball placeholder for empty party slots ─────────────────────────────────
function EmptyBenchSlot() {
  return (
    <div
      style={{
        width: 44,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 4,
        flexShrink: 0,
      }}
    >
      <div
        style={{
          width: 34,
          height: 26,
          borderRadius: 4,
          border: "1.5px dashed rgba(255,255,255,0.1)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 22 22"
          opacity={0.18}
          color="white"
        >
          <circle
            cx="11"
            cy="11"
            r="9.5"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          />
          <line
            x1="1.5"
            y1="11"
            x2="20.5"
            y2="11"
            stroke="currentColor"
            strokeWidth="1.5"
          />
          <circle
            cx="11"
            cy="11"
            r="3"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          />
        </svg>
      </div>
      <div style={{ height: 3, width: 28 }} />
    </div>
  );
}

// ── Bench Pokémon card with hover ──────────────────────────────────────────────
function BenchCard({ entry }: { entry: BenchEntry }) {
  const isFainted = entry.hp <= 0;
  const color = hpColor(entry.hp, entry.max_hp);
  const pct = isFainted ? 0 : entry.hp / Math.max(entry.max_hp, 1);

  return (
    <HoverCard openDelay={180} closeDelay={80}>
      <HoverCardTrigger asChild>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 3,
            padding: "4px 5px 5px",
            borderRadius: 8,
            background: "rgba(255,255,255,0.03)",
            border: "1px solid rgba(255,255,255,0.07)",
            cursor: "default",
            opacity: isFainted ? 0.4 : 1,
            flexShrink: 0,
            minWidth: 44,
          }}
        >
          <img
            src={gen7Icon(entry.id)}
            alt={entry.name}
            style={{
              width: 34,
              height: 26,
              imageRendering: "pixelated",
              objectFit: "contain",
              filter: isFainted ? "grayscale(100%)" : undefined,
            }}
          />
          <div
            style={{
              height: 3,
              width: 28,
              background: "rgba(255,255,255,0.07)",
              borderRadius: 2,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                height: "100%",
                width: `${pct * 100}%`,
                background: color,
                borderRadius: 2,
              }}
            />
          </div>
          {entry.status && (
            <span
              style={{
                fontSize: "0.48rem",
                fontWeight: 800,
                color: "#fbbf24",
                letterSpacing: "0.04em",
                lineHeight: 1,
              }}
            >
              {entry.status}
            </span>
          )}
        </div>
      </HoverCardTrigger>
      <HoverCardContent
        side="top"
        className="bg-slate-800 border border-slate-600 rounded-lg shadow-xl z-50 animate-in fade-in-0 zoom-in-95 w-auto"
      >
        <div style={{ minWidth: 155 }}>
          <div
            style={{
              display: "flex",
              alignItems: "baseline",
              gap: 5,
              marginBottom: 7,
            }}
          >
            <span
              style={{ fontWeight: 700, color: "#f1f5f9", fontSize: "0.9rem" }}
            >
              {entry.name}
            </span>
            <span style={{ fontSize: "0.7rem", color: "var(--muted)" }}>
              Lv.{entry.level}
            </span>
          </div>
          {entry.status && (
            <span
              className="badge status-badge"
              style={{ display: "inline-block", marginBottom: 7 }}
            >
              {entry.status}
            </span>
          )}
          {entry.item && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 4,
                marginBottom: 7,
              }}
            >
              <img
                src={itemIcon(entry.item)}
                alt={entry.item}
                width={16}
                height={16}
                style={{ imageRendering: "pixelated" }}
                onError={(e) => {
                  e.currentTarget.style.display = "none";
                }}
              />
              <span style={{ fontSize: "0.65rem", color: "var(--muted)" }}>
                {entry.item}
              </span>
            </div>
          )}
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span
              style={{
                fontSize: "0.56rem",
                fontWeight: 800,
                color: "var(--muted)",
                letterSpacing: "0.1em",
                width: 14,
                flexShrink: 0,
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
                  width: `${pct * 100}%`,
                  background: color,
                  borderRadius: 3,
                }}
              />
            </div>
            <span
              style={{
                fontSize: "0.62rem",
                color,
                fontWeight: 700,
                width: 62,
                textAlign: "right",
                flexShrink: 0,
              }}
            >
              {isFainted ? "Fainted" : hpRange(entry.hp, entry.max_hp)}
            </span>
          </div>
        </div>
      </HoverCardContent>
    </HoverCard>
  );
}

// ── Bench row (up to 5 slots, pokéballs fill gaps) ────────────────────────────
function BenchRow({
  entries,
  maxSlots = 5,
  showEmpty = true,
  justify = "flex-start",
}: {
  entries: BenchEntry[];
  maxSlots?: number;
  showEmpty?: boolean;
  justify?: "flex-start" | "flex-end";
}) {
  const sorted = [...entries].sort((a, b) => a.slot - b.slot);
  const emptyCount = showEmpty ? Math.max(0, maxSlots - sorted.length) : 0;
  if (sorted.length === 0 && emptyCount === 0) return null;
  return (
    <div
      style={{
        display: "flex",
        gap: 4,
        flexWrap: "wrap",
        justifyContent: justify,
      }}
    >
      {sorted.map((e) => (
        <BenchCard key={e.slot} entry={e} />
      ))}
      {Array.from({ length: emptyCount }).map((_, i) => (
        <EmptyBenchSlot key={`ep-${i}`} />
      ))}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function BattleView({
  node,
  onContinue,
}: {
  node: TreeNode;
  onContinue: (id: string) => void;
}) {
  const { snapshot } = node;
  const isDeath = snapshot.phase === "DEATH";
  const bestAction =
    Object.values(node.actions).sort(
      (a, b) => b.total_visits - a.total_visits,
    )[0] ?? null;

  return (
    <section
      style={{
        padding: "12px 16px 10px",
        background:
          "linear-gradient(165deg, #11141d 0%, #1a1d27 50%, #141720 100%)",
        borderBottom: "1px solid var(--border)",
        flexShrink: 0,
      }}
    >
      {/* Banners */}
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

      {/* Battle field */}
      <div
        style={{
          display: "flex",
          gap: 10,
          alignItems: "stretch",
          minHeight: 160,
        }}
      >
        {/* ── MY SIDE ────────────────────────────────────────────────── */}
        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            gap: 8,
            minWidth: 0,
          }}
        >
          {isDeath ? (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 8,
                paddingTop: 8,
              }}
            >
              <span
                style={{
                  fontSize: "0.78rem",
                  color: "var(--muted)",
                  fontStyle: "italic",
                }}
              >
                Choose a Pokémon ↓
              </span>
              {/* In death phase show all party mons to pick from, no pokéball padding */}
              <BenchRow entries={snapshot.my_bench} showEmpty={false} />
            </div>
          ) : (
            <>
              {snapshot.my ? (
                <BattleSprite pok={snapshot.my} side="mine" />
              ) : (
                <div
                  style={{
                    height: 84,
                    display: "flex",
                    alignItems: "center",
                    color: "var(--muted)",
                    fontSize: "0.78rem",
                    fontStyle: "italic",
                  }}
                >
                  fainted
                </div>
              )}
              {snapshot.my && (
                <div
                  style={{
                    background: "rgba(255,255,255,0.025)",
                    border: "1px solid rgba(255,255,255,0.07)",
                    borderLeft: `2px solid ${hpColor(snapshot.my.hp, snapshot.my.max_hp)}55`,
                    borderRadius: 8,
                    padding: "8px 10px",
                  }}
                >
                  <PokInfo pok={snapshot.my} label="YOU" />
                </div>
              )}
              <BenchRow entries={snapshot.my_bench} />
            </>
          )}
        </div>

        {/* ── VS ─────────────────────────────────────────────────────── */}
        <div
          style={{
            alignSelf: "center",
            color: "rgba(120,128,160,0.3)",
            fontSize: "0.58rem",
            fontWeight: 700,
            letterSpacing: "0.12em",
            flexShrink: 0,
            userSelect: "none",
            padding: "0 2px",
          }}
        >
          VS
        </div>

        {/* ── OPP SIDE ───────────────────────────────────────────────── */}
        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            gap: 8,
            minWidth: 0,
          }}
        >
          {/* Trainer remaining items */}
          {snapshot.trainer_items?.some(Boolean) && (
            <div
              style={{
                display: "flex",
                gap: 4,
                justifyContent: "flex-end",
                alignItems: "center",
              }}
            >
              <span
                style={{
                  fontSize: "0.48rem",
                  color: "var(--muted)",
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                }}
              >
                Items
              </span>
              {snapshot.trainer_items.map((item, i) =>
                item ? (
                  <img
                    key={i}
                    src={itemIcon(item)}
                    alt={item}
                    title={item}
                    width={20}
                    height={20}
                    style={{ imageRendering: "pixelated" }}
                    onError={(e) => {
                      e.currentTarget.style.display = "none";
                    }}
                  />
                ) : null,
              )}
            </div>
          )}
          {/* Bench above info */}
          <BenchRow entries={snapshot.opp_bench} justify="flex-end" />
          {snapshot.opp && (
            <div
              style={{
                background: "rgba(255,255,255,0.025)",
                border: "1px solid rgba(255,255,255,0.07)",
                borderRight: `2px solid ${hpColor(snapshot.opp.hp, snapshot.opp.max_hp)}55`,
                borderRadius: 8,
                padding: "8px 10px",
              }}
            >
              <PokInfo pok={snapshot.opp} label="OPP" />
            </div>
          )}
          {/* Sprite below info */}
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            {snapshot.opp ? (
              <BattleSprite pok={snapshot.opp} side="opp" />
            ) : (
              <div
                style={{
                  height: 84,
                  display: "flex",
                  alignItems: "center",
                  color: "var(--muted)",
                  fontSize: "0.78rem",
                  fontStyle: "italic",
                }}
              >
                fainted
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Node stats ─────────────────────────────────────────────────── */}
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
        <button
          onClick={() => onContinue(node.id)}
          style={{
            marginLeft: "auto",
            padding: "3px 10px",
            background: "transparent",
            border: "1px solid var(--border)",
            borderRadius: 6,
            color: "var(--muted)",
            fontSize: "0.7rem",
            cursor: "pointer",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "var(--text)")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "var(--muted)")}
        >
          Continue from here
        </button>
      </div>
    </section>
  );
}
