import { useState, useEffect, useMemo, useCallback } from "react";
import type { TreeNode, ActionData, WSMessage } from "./types";
import BattleView from "./components/BattleView";
import ActionPanel from "./components/ActionPanel";
import NodePopup from "./components/NodePopup";
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
  const [iterations, setIterations] = useState(0);
  const [running, setRunning] = useState(false);
  const [connected, setConnected] = useState(false);

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
      setIterations(msg.iterations);
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

  // ── MCTS controls ───────────────────────────────────────────────────────────
  const start = () => {
    fetch(`${API_URL}/start`, { method: "POST" }).catch(console.error);
    setPathIds([]); // reset navigation for the new run
    setSelectedKey(null);
  };

  const stop = () =>
    fetch(`${API_URL}/stop`, { method: "POST" }).catch(console.error);

  // ── render ──────────────────────────────────────────────────────────────────
  // JSX looks like HTML but it's actually JavaScript.
  // className instead of class (class is a reserved word in JS).
  // onClick, onChange etc. are camelCase event handlers.
  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title">MCTS Explorer</h1>

        <div className="header-status">
          <span className={`dot ${connected ? "dot-on" : ""}`} />
          <span>
            {running
              ? `${iterations.toLocaleString()} iterations…`
              : iterations > 0
                ? `Done — ${iterations.toLocaleString()}`
                : "Not started"}
          </span>
        </div>

        <div className="header-controls">
          <button className="btn btn-primary" onClick={start}>
            ▶ Start
          </button>
          <button className="btn btn-secondary" onClick={stop}>
            ■ Stop
          </button>
          {pathIds.length > 0 && (
            <button className="btn btn-back" onClick={goBack}>
              ← Back
            </button>
          )}
          {pathIds.length > 0 && (
            <span className="depth-badge">Depth {pathIds.length}</span>
          )}
        </div>
      </header>

      {!currentNode ? (
        <div className="empty-state">
          <p>Press Start to run MCTS</p>
          <p className="muted">
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
      )}

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
