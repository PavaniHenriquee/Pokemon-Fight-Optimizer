import { useState, useEffect, useMemo, useCallback, useRef } from "react";
import type {
  TreeNode,
  ActionData,
  WSMessage,
  PokemonData,
  PokemonConfig,
  TrainerDB,
} from "./types";
import BattleView from "./components/BattleView";
import ActionPanel from "./components/ActionPanel";
import NodePopup from "./components/NodePopup";
import ConfigureView from "./components/ConfigureView";
import "./App.css";

const WS_URL = "ws://localhost:8000/ws";
const API_URL = "http://localhost:8000";

// Build a flat id→node map so we can look up any node in O(1).
// This runs whenever the tree updates (once per second).
function buildNodeMap(node: TreeNode, map = new Map<string, TreeNode>()) {
  map.set(node.id, node);
  for (const action of Object.values(node.actions)) {
    for (const child of action.nodes) buildNodeMap(child, map);
  }
  return map;
}

export default function App() {
  // ── state ──────────────────────────────────────────────────────────────────
  // useState(initialValue) declares a piece of state.
  // Re-renders happen whenever you call the setter (setTree, setPathIds, etc.)

  const [tree, setTree] = useState<TreeNode | null>(null);
  const [running, setRunning] = useState(false);
  const [connected, setConnected] = useState(false);
  const [actualIterations, setActualIterations] = useState(0);
  const [displayIterations, setDisplayIterations] = useState(0);
  const prevDisplayRef = useRef(0); // tracks where animation is currently at
  const [view, setView] = useState<"configure" | "explore">("configure");
  const [pokemonData, setPokemonData] = useState<PokemonData | null>(null);
  const [trainerDB, setTrainerDB] = useState<TrainerDB>({});

  useEffect(() => {
    fetch(`${API_URL}/trainers`)
      .then((r) => r.json())
      .then(setTrainerDB)
      .catch(console.error);
  }, []);

  useEffect(() => {
    const from = prevDisplayRef.current;
    const to = actualIterations;
    if (from === to) return;

    const duration = 1850;
    const startTime = performance.now();

    const animate = (now: number) => {
      const t = Math.min((now - startTime) / duration, 1);
      const eased = Math.sqrt(t); // ease-out: fast start, slows near target
      const current = Math.round(from + (to - from) * eased);
      prevDisplayRef.current = current;
      setDisplayIterations(current);
      if (t < 1) requestAnimationFrame(animate);
      else {
        prevDisplayRef.current = to;
        setDisplayIterations(to);
      }
    };

    const rafId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(rafId);
  }, [actualIterations]);

  // pathIds is our navigation: an array of node IDs from root → current.
  // [] = we're at the root.  ["42", "108"] = two levels deep.
  const [pathIds, setPathIds] = useState<string[]>([]);

  // Which action card is selected (drives the popup). null = popup closed.
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  // ── derived values ─────────────────────────────────────────────────────────
  // useMemo runs the function and caches the result until a dependency changes.
  // This one rebuilds the flat node map whenever the tree snapshot changes.
  const nodeMap = useMemo(
    () => (tree ? buildNodeMap(tree) : new Map<string, TreeNode>()),
    [tree], // dependency: only rebuild when `tree` changes
  );

  // The node the user is currently looking at.
  // Falls back to root if a node was pruned from the latest snapshot.
  const currentNode = useMemo((): TreeNode | null => {
    if (!tree) return null;
    if (pathIds.length === 0) return tree;
    return nodeMap.get(pathIds[pathIds.length - 1]) ?? tree;
  }, [tree, pathIds, nodeMap]);

  const selectedAction: ActionData | null =
    currentNode && selectedKey
      ? (currentNode.actions[selectedKey] ?? null)
      : null;

  // ── WebSocket ───────────────────────────────────────────────────────────────
  // useEffect runs after the component mounts (appears on screen).
  // The empty [] dependency array means "run once, never again".
  // The return value is a cleanup function: runs when the component unmounts.
  useEffect(() => {
    const ws = new WebSocket(WS_URL);
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);
    ws.onmessage = (e) => {
      const msg: WSMessage = JSON.parse(e.data);
      setActualIterations(msg.iterations);
      setRunning(msg.running);
      if (msg.type === "tree_update" && msg.tree) setTree(msg.tree);
    };
    return () => ws.close(); // cleanup: close WebSocket when app unmounts
  }, []);

  // ── navigation ─────────────────────────────────────────────────────────────
  // useCallback memoises a function so child components don't re-render
  // unnecessarily just because App re-rendered.

  const navigateTo = useCallback((nodeId: string) => {
    setPathIds((prev) => [...prev, nodeId]);
    setSelectedKey(null);
  }, []);

  const goBack = useCallback(() => {
    setPathIds((prev) => prev.slice(0, -1));
    setSelectedKey(null);
  }, []);

  // ── action click handler ───────────────────────────────────────────────────
  // If there's exactly 1 outcome we skip the popup and navigate directly.
  const handleActionClick = (key: string) => {
    const action = currentNode?.actions[key];
    if (!action) return;
    if (action.nodes.length === 1) {
      navigateTo(action.nodes[0].id);
    } else {
      setSelectedKey(key);
    }
  };

  // ──Timer───────────────────────────────────────────────────────────
  const [startTime, setStartTime] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);

  // tick every second while running
  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => {
      setElapsed(Date.now() - (startTime ?? Date.now()));
    }, 1000);
    return () => clearInterval(id);
  }, [running, startTime]);

  // Fetch pokemon data once on mount (add to the existing useEffect block or separate)
  useEffect(() => {
    fetch(`${API_URL}/pokemon-data`)
      .then((r) => r.json())
      .then(setPokemonData)
      .catch(console.error);
  }, []);

  // ── MCTS controls ───────────────────────────────────────────────────────────
  const start = (myTeam: PokemonConfig[], oppTeam: PokemonConfig[]) => {
    fetch(`${API_URL}/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ my_team: myTeam, opp_team: oppTeam }),
    }).catch(console.error);
    setPathIds([]);
    setSelectedKey(null);
    setStartTime(Date.now());
    setElapsed(0);
    setView("explore"); // auto-switch to explore tab
  };

  const stop = () => {
    fetch(`${API_URL}/stop`, { method: "POST" }).catch(console.error);
  };

  // format as m:ss
  const formatTime = (ms: number) => {
    const s = Math.floor(ms / 1000);
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  };

  // ── render ──────────────────────────────────────────────────────────────────
  // JSX looks like HTML but it's actually JavaScript.
  // className instead of class (class is a reserved word in JS).
  // onClick, onChange etc. are camelCase event handlers.
  return (
    <div className="flex flex-col bg-slate-900 text-slate-200">
      <header className="flex flex-wrap items-center h-30 gap-1 px-4 py-2 bg-slate-800 border-b border-slate-700 shrink-0 sticky top-0 z-10 justify-center">
        <h1 className="text-yellow-400 font-bold text-4xl w-full text-shadow-lg/20 font-sans">
          MCTS
        </h1>

        {/* Tabs */}
        <div className="flex gap-1 bg-slate-900 rounded-lg p-1">
          {(["configure", "explore"] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`px-3 py-1 rounded text-xs font-medium capitalize transition-colors cursor-pointer
          ${
            view === v
              ? "bg-(--accent) text-black"
              : "text-slate-400 hover:text-slate-200"
          }`}
            >
              {v}
            </button>
          ))}
        </div>

        <div className="basis-full h-0"></div>

        {/* Status */}
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <span
            className={`w-2 h-2 rounded-full ${connected ? "bg-green-400" : "bg-red-500"}`}
          />
          {running
            ? `${displayIterations.toLocaleString()} iters — ${formatTime(elapsed)}`
            : actualIterations > 0
              ? `Done — ${actualIterations.toLocaleString()} in ${formatTime(elapsed)}`
              : "Not started"}
        </div>

        {/* Controls */}
        <div className="flex gap-2">
          {running && (
            <button
              onClick={stop}
              className="px-3 py-1 bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs rounded-lg border border-slate-600 transition-colors"
            >
              ■ Stop
            </button>
          )}
          {view === "explore" && pathIds.length > 0 && (
            <button
              onClick={goBack}
              className="px-3 py-1 text-slate-400 hover:text-slate-200 text-xs border border-slate-700 rounded-lg transition-colors"
            >
              ← Back
            </button>
          )}
          {view === "explore" && pathIds.length > 0 && (
            <span className="text-xs text-slate-500 self-center">
              Depth {pathIds.length}
            </span>
          )}
        </div>
      </header>

      {/* Always mounted — CSS hide/show preserves team state between tab switches */}
      <div
        className={
          view === "configure"
            ? "flex flex-1 flex-col overflow-hidden"
            : "hidden"
        }
      >
        <ConfigureView
          pokemonData={pokemonData}
          onStart={start}
          running={running}
          trainerDB={trainerDB}
        />
      </div>

      {view !== "configure" &&
        (!currentNode ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-2 text-slate-500">
            <p>Start MCTS from the Configure tab</p>
            <p className="text-xs">
              {connected ? "✓ Backend connected" : "Waiting for backend…"}
            </p>
          </div>
        ) : (
          <>
            <BattleView node={currentNode} />
            <ActionPanel
              node={currentNode}
              onActionClick={handleActionClick}
              selectedKey={selectedKey}
            />
          </>
        ))}
      {selectedAction && (
        <NodePopup
          action={selectedAction}
          onSelect={navigateTo}
          onClose={() => setSelectedKey(null)}
        />
      )}
    </div>
  );
}
