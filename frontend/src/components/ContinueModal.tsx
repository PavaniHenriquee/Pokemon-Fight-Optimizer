import { useState, useEffect } from "react";
import type { PokemonEntry, NodeInfoData } from "../types";

const API_URL = "http://localhost:8000";

const gen7Icon = (id: number) =>
  `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/versions/generation-vii/icons/${id}.png`;

function hpColor(hp: number, max: number) {
  const pct = hp / Math.max(max, 1);
  return pct > 0.5 ? "#4ade80" : pct > 0.25 ? "#fbbf24" : "#f87171";
}

function HpRow({
  entry,
  hp,
  onChange,
}: {
  entry: PokemonEntry;
  hp: number;
  onChange: (hp: number) => void;
}) {
  const color = hpColor(hp, entry.max_hp);
  const pct = Math.min(hp / Math.max(entry.max_hp, 1), 1);

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "4px 0",
      }}
    >
      <img
        src={gen7Icon(entry.pok_id)}
        alt={entry.name}
        style={{
          width: 34,
          height: 26,
          imageRendering: "pixelated",
          objectFit: "contain",
          flexShrink: 0,
        }}
      />
      <span
        style={{
          fontWeight: 600,
          fontSize: "0.85rem",
          width: 90,
          flexShrink: 0,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {entry.name}
      </span>
      <input
        type="number"
        min={0}
        max={entry.max_hp}
        value={hp}
        onChange={(e) =>
          onChange(
            Math.max(0, Math.min(entry.max_hp, parseInt(e.target.value) || 0)),
          )
        }
        style={{
          width: 50,
          background: "var(--surface2)",
          border: `1px solid ${color}55`,
          borderRadius: 6,
          color,
          textAlign: "center",
          fontSize: "0.85rem",
          fontWeight: 700,
          padding: "2px 0",
          outline: "none",
        }}
      />
      <span
        style={{
          fontSize: "0.68rem",
          color: "var(--muted)",
          flexShrink: 0,
          width: 34,
        }}
      >
        / {entry.max_hp}
      </span>
      <div
        style={{
          flex: 1,
          height: 4,
          background: "rgba(255,255,255,0.06)",
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
            transition: "width 0.2s",
          }}
        />
      </div>
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p
      style={{
        fontSize: "0.6rem",
        textTransform: "uppercase",
        letterSpacing: "0.08em",
        color: "var(--muted)",
        margin: "10px 0 2px",
      }}
    >
      {children}
    </p>
  );
}

interface Props {
  nodeId: string;
  onClose: () => void;
  onStarted: () => void;
}

export default function ContinueModal({ nodeId, onClose, onStarted }: Props) {
  const [nodeInfo, setNodeInfo] = useState<NodeInfoData | null>(null);
  const [myActiveHp, setMyActiveHp] = useState(0);
  const [oppActiveHp, setOppActiveHp] = useState(0);
  const [benchHps, setBenchHps] = useState<Record<number, number>>({});
  const [iterations, setIterations] = useState(100_000);
  const [isFocused, setIsFocused] = useState(false);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/node_info/${nodeId}`)
      .then((r) => r.json())
      .then((info: NodeInfoData) => {
        setNodeInfo(info);
        if (info.my_active) setMyActiveHp(info.my_active.hp);
        setOppActiveHp(info.opp_active.hp);
        const bench: Record<number, number> = {};
        for (const p of info.my_bench) bench[p.slot] = p.hp;
        setBenchHps(bench);
        setLoading(false);
      })
      .catch(() => {
        setFailed(true);
        setLoading(false);
      });
  }, [nodeId]);

  function handleStart() {
    setStarting(true);
    fetch(`${API_URL}/continue_from_node`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        node_id: nodeId,
        iterations,
        my_active_hp: nodeInfo?.my_active ? myActiveHp : null,
        opp_active_hp: oppActiveHp,
        bench_hps: benchHps,
      }),
    })
      .then(() => {
        onStarted();
        onClose();
      })
      .catch(() => setStarting(false));
  }

  return (
    <div className="popup-overlay" onClick={onClose}>
      <div
        className="popup-panel"
        style={{ maxWidth: 460 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="popup-header">
          <h2>Continue MCTS from here</h2>
          <button className="close-btn" onClick={onClose}>
            ✕
          </button>
        </div>

        {loading && (
          <p
            style={{
              color: "var(--muted)",
              textAlign: "center",
              padding: "24px 0",
            }}
          >
            Loading…
          </p>
        )}

        {failed && (
          <p
            style={{
              color: "var(--red)",
              textAlign: "center",
              padding: "24px 0",
            }}
          >
            Failed to load node state.
          </p>
        )}

        {!loading && !failed && nodeInfo && (
          <>
            <p style={{ fontSize: "0.72rem", color: "var(--muted)" }}>
              Adjust HP to match your real game. Everything else is taken from
              the node.
            </p>

            <SectionLabel>Opponent</SectionLabel>
            <HpRow
              entry={nodeInfo.opp_active}
              hp={oppActiveHp}
              onChange={setOppActiveHp}
            />

            <SectionLabel>Your Pokémon</SectionLabel>
            {nodeInfo.my_active ? (
              <HpRow
                entry={nodeInfo.my_active}
                hp={myActiveHp}
                onChange={setMyActiveHp}
              />
            ) : (
              <p
                style={{
                  fontSize: "0.72rem",
                  color: "var(--muted)",
                  fontStyle: "italic",
                }}
              >
                Death phase — choosing replacement, no active Pokémon.
              </p>
            )}

            {nodeInfo.my_bench.length > 0 && (
              <>
                <SectionLabel>Your Bench</SectionLabel>
                {nodeInfo.my_bench.map((entry) => (
                  <HpRow
                    key={entry.slot}
                    entry={entry}
                    hp={benchHps[entry.slot] ?? entry.hp}
                    onChange={(hp) =>
                      setBenchHps((prev) => ({ ...prev, [entry.slot]: hp }))
                    }
                  />
                ))}
              </>
            )}

            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 4,
                marginTop: 14,
              }}
            >
              <SectionLabel>Iterations</SectionLabel>
              <input
                type="text"
                value={
                  isFocused
                    ? iterations === 0
                      ? ""
                      : iterations
                    : new Intl.NumberFormat("en-US").format(iterations)
                }
                onFocus={() => setIsFocused(true)}
                onBlur={() => {
                  setIsFocused(false);
                  setIterations((prev) => Math.max(1, prev));
                }}
                onChange={(e) => {
                  const raw = e.target.value.replace(/\D/g, "");
                  setIterations(raw === "" ? 0 : parseInt(raw, 10));
                }}
                style={{
                  width: 140,
                  background: "var(--surface2)",
                  border: "1px solid var(--border)",
                  borderRadius: 6,
                  color: "var(--text)",
                  textAlign: "center",
                  fontSize: "0.85rem",
                  padding: "4px 8px",
                  outline: "none",
                }}
              />
            </div>

            <div
              style={{
                display: "flex",
                justifyContent: "flex-end",
                gap: 8,
                marginTop: 16,
              }}
            >
              <button onClick={onClose} className="btn btn-secondary">
                Cancel
              </button>
              <button
                onClick={handleStart}
                disabled={starting}
                className="btn btn-primary"
                style={{ opacity: starting ? 0.6 : 1 }}
              >
                {starting ? "Starting…" : "▶ Start from here"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
