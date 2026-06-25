import type { TreeNode, ActionData } from "../types";

const gen7Icon = (id: number) =>
  `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/versions/generation-vii/icons/${id}.png`;

function WinRing({ win, size = 30 }: { win: number; size?: number }) {
  const strokeWidth = 2.5;
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
          fontWeight: 800,
          color,
          lineHeight: 1,
        }}
        className="text-sm"
      >
        {Math.round(win * 100)}
      </span>
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

  const maxVisits = Math.max(
    ...Object.values(node.actions).map((a) => a.total_visits),
    1,
  );
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
    const switchPokId =
      action.action_type === 2 ? action.nodes[0]?.snapshot.my?.id : undefined;
    const visitFillPct = (action.total_visits / maxVisits) * 100;

    return (
      <button
        onClick={() => onActionClick(actionKey)}
        style={{ position: "relative", overflow: "hidden" }}
        className={[
          "flex flex-col gap-1.5 p-2.5 pb-3 rounded-lg border text-left cursor-pointer transition-colors",
          "bg-[var(--surface)] text-[var(--text)]",
          isSelected
            ? "border-[var(--accent)] bg-[var(--surface2)]"
            : isBest
              ? "border-purple-500/40 hover:border-[var(--accent)] hover:bg-[var(--surface2)]"
              : "border-[var(--border)] hover:border-[var(--accent)] hover:bg-[var(--surface2)]",
        ].join(" ")}
      >
        {/* Switch: pokemon icon */}
        {switchPokId !== undefined && (
          <div style={{ display: "flex", justifyContent: "center" }}>
            <img
              src={gen7Icon(switchPokId)}
              alt=""
              style={{
                width: 70,
                height: 50,
                imageRendering: "pixelated",
                objectFit: "contain",
              }}
            />
          </div>
        )}

        {/* Label */}
        <div className="flex flex-row justify-center items-center gap-1">
          <span className="overflow-hidden text-ellipsis whitespace-nowrap font-bold text-lg">
            {isBest && (
              <span style={{ color: "var(--accent)", marginRight: 2 }}>★</span>
            )}
            {action.label}
          </span>
        </div>

        {/* Win ring + secondary stats */}
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <WinRing win={action.win_chance} size={50} />
          <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
            <span className="text-xs text-[var(--muted)]">
              {action.dead_avg.toFixed(2)} deaths
            </span>
            <span className="text-xs text-[rgba(120,128,160,0.55)]">
              {action.nodes.length} outcomes
            </span>
          </div>
          <span className="text-[var(--muted)] rounded-md max-w-sm mx-auto text-center font-semibold text-sm">
            {action.total_visits.toLocaleString()} visits
          </span>
        </div>

        {/* Visit bar — 2px strip at bottom edge, fills relative to most-visited action */}
        <div
          style={{
            position: "absolute",
            bottom: 0,
            left: 0,
            right: 0,
            height: 2,
            background: "rgba(255,255,255,0.04)",
          }}
        >
          <div
            style={{
              height: "100%",
              width: `${visitFillPct}%`,
              background: isBest ? "var(--accent)" : "rgba(120,128,160,0.3)",
              transition: "width 0.4s ease",
            }}
          />
        </div>
      </button>
    );
  }

  return (
    <section className="flex-1 p-4 overflow-y-auto space-y-4 min-h-0">
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
                className="rounded-lg border border-dashed border-slate-700/40"
                style={{ minHeight: 80 }}
              />
            ))}
          </div>
        </div>
      )}

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
                className="rounded-lg border border-dashed border-slate-700/40"
                style={{ minHeight: 100 }}
              />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
