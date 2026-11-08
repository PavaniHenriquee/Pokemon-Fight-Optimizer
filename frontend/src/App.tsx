import { useState, useEffect, useMemo, useCallback, useRef } from "react";
import { Loader2, Search, Settings2, Unplug } from "lucide-react";
import { toast } from "sonner";
import type {
  TreeNode,
  ActionData,
  WSMessage,
  PokemonData,
  PokemonConfig,
  TrainerDB,
  EncounterDB,
  ItemLocationDB,
  NuzlockeRun,
  BoxEntry,
} from "./types";
import { WS_URL, API_URL, getJSON, postJSON } from "./lib/api";
import {
  EMPTY_RUN,
  deathChanges,
  makeLineOf,
  partyAfterEdit,
  setDeadInBox,
  setDeadInRun,
} from "./lib/nuzlocke";
import { useBox } from "./lib/useBox";
import TopBar, { type View } from "./components/TopBar";
import PathRail from "./components/PathRail";
import BattleView from "./components/BattleView";
import ActionPanel from "./components/ActionPanel";
import OutcomeInspector from "./components/OutcomeInspector";
import ConfigureView from "./components/ConfigureView";
import ContinueModal from "./components/ContinueModal";
import TrackerView from "./components/TrackerView";
import { Button } from "./components/ui/button";
import { Toaster } from "./components/ui/sonner";
import { TooltipProvider } from "./components/ui/tooltip";

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
  const [everConnected, setEverConnected] = useState(false);
  const [compiling, setCompiling] = useState(false); // backend warm-up still compiling
  const [actualIterations, setActualIterations] = useState(0);
  const [displayIterations, setDisplayIterations] = useState(0);
  const prevDisplayRef = useRef(0); // tracks where animation is currently at
  const lastErrorRef = useRef<string | null>(null); // last search crash already shown
  const [view, setView] = useState<View>("configure");
  const [pokemonData, setPokemonData] = useState<PokemonData | null>(null);
  const [trainerDB, setTrainerDB] = useState<TrainerDB>({});
  const [myTeam, setMyTeam] = useState<PokemonConfig[]>([]);
  const [oppTeam, setOppTeam] = useState<PokemonConfig[]>([]);
  const [iterations, setIterations] = useState(500_000);
  const [runMax, setRunMax] = useState(0); // max iterations of the current run (progress bar)
  const [continueNodeId, setContinueNodeId] = useState<string | null>(null);
  const [sessionActive, setSessionActive] = useState(false);
  const [starting, setStarting] = useState(false);
  const [trainerItems, setTrainerItems] = useState<string[]>(["", "", "", ""]);
  const [terrain, setTerrain] = useState("plain");
  const [encounterDB, setEncounterDB] = useState<EncounterDB | null>(null);
  const [itemDB, setItemDB] = useState<ItemLocationDB | null>(null);
  const [run, setRun] = useState<NuzlockeRun | null>(null); // null until loaded: see TrackerView
  const [trackerError, setTrackerError] = useState<string | null>(null);
  const runSaves = useRef<Promise<unknown>>(Promise.resolve()); // one at a time, in order

  const loadTracker = useCallback(() => {
    const onError = (e: Error) => setTrackerError(e.message);
    getJSON<EncounterDB>("/encounters").then(setEncounterDB).catch(onError);
    getJSON<ItemLocationDB>("/item-locations").then(setItemDB).catch(onError);
    getJSON<NuzlockeRun>("/nuzlocke").then(setRun).catch(onError);
  }, []);

  const boxState = useBox(everConnected);
  const lineOf = useMemo(() => makeLineOf(encounterDB), [encounterDB]);

  function saveRun(next: NuzlockeRun) {
    setRun(next);
    runSaves.current = runSaves.current
      .then(() => postJSON("/nuzlocke", next))
      .catch((e: Error) =>
        toast.error("Couldn't save the Nuzlocke run", { description: e.message }),
      );
  }

  // A death on the tracker moves its evolution line in the box too, and takes it out of the party
  function changeRun(next: NuzlockeRun) {
    const changes = run ? deathChanges(run, next) : [];
    saveRun(next);
    const { box } = boxState;
    if (box) {
      const nextBox = changes.reduce(
        (entries, { species, dead }) => setDeadInBox(entries, lineOf, species, dead),
        box,
      );
      if (nextBox !== box) boxState.commit(nextBox);
    }
    const died = new Set(changes.filter((c) => c.dead).map((c) => lineOf(c.species)));
    if (myTeam.some((member) => died.has(lineOf(member.name)))) {
      setMyTeam(myTeam.filter((member) => !died.has(lineOf(member.name))));
    }
  }

  // The same thing from the box's side
  function setBoxEntryDead(entry: BoxEntry, dead: boolean) {
    if (!boxState.box) return;
    boxState.commit(setDeadInBox(boxState.box, lineOf, entry.name, dead));
    if (run) {
      const nextRun = setDeadInRun(run, lineOf, entry.name, dead);
      if (nextRun !== run) saveRun(nextRun);
    }
    if (dead) setMyTeam(myTeam.filter((member) => lineOf(member.name) !== lineOf(entry.name)));
  }

  // A box Pokémon stored or edited from the Tracker, with the run change that goes with it. The Tracker
  // has no Save button, so it saves right away. An edit reaches its copy in the party too.
  function storeFromTracker(entry: BoxEntry, nextRun?: NuzlockeRun) {
    const { box } = boxState;
    if (!box) return;
    const before = box.find((e) => e.id === entry.id);
    boxState.commit(before ? box.map((e) => (e.id === entry.id ? entry : e)) : [...box, entry]);
    if (before) setMyTeam(partyAfterEdit(myTeam, before.name, entry));
    if (nextRun) saveRun(nextRun);
  }

  // Clearing a tracker row takes its Pokémon out of the box and the party too
  function clearTrackerRow(nextRun: NuzlockeRun, entry?: BoxEntry) {
    saveRun(nextRun);
    if (entry && boxState.box) {
      boxState.commit(boxState.box.filter((e) => e.id !== entry.id));
      setMyTeam(myTeam.filter((member) => member.name !== entry.name));
    }
  }

  // A new run is the tracker and the box: what's left in the box would block its lines
  function startNewRun() {
    saveRun(EMPTY_RUN);
    boxState.commit([]);
    setMyTeam([]);
  }

  // Data loads once the backend is reachable (in Electron the window can open first)
  useEffect(() => {
    if (!everConnected) return;
    getJSON<TrainerDB>("/trainers").then(setTrainerDB).catch(console.error);
    loadTracker();
  }, [everConnected, loadTracker]);

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
  // Same length as pathIds: what the foe did on each step, the outcome dropdown it was picked under
  const [pathMoves, setPathMoves] = useState<(string | null)[]>([]);

  // Which action card is selected (drives the outcome inspector). null = nothing selected.
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
  // A dropped connection retries with backoff (1s, 2s, 4s, then every 5s).
  useEffect(() => {
    let ws: WebSocket | null = null;
    let retryId: number | undefined;
    let delay = 1000;
    let disposed = false;

    // Events from a socket this effect already disposed are ignored: in dev, StrictMode mounts
    // the effect twice and the first socket's late "close" would mark the live one offline.
    const connect = () => {
      const socket = new WebSocket(WS_URL);
      ws = socket;
      socket.onopen = () => {
        if (disposed) return;
        delay = 1000;
        setConnected(true);
        setEverConnected(true);
      };
      socket.onclose = () => {
        if (disposed) return;
        setConnected(false);
        retryId = window.setTimeout(connect, delay);
        delay = Math.min(delay * 2, 5000);
      };
      socket.onerror = () => socket.close(); // onclose schedules the retry
      socket.onmessage = (e) => {
        if (disposed) return;
        setConnected(true);
        const msg: WSMessage = JSON.parse(e.data);
        setActualIterations(msg.iterations);
        setRunning(msg.running);
        setCompiling(!!msg.compiling);
        if (msg.type === "tree_update" && msg.tree) setTree(msg.tree);
        if (msg.error && msg.error !== lastErrorRef.current) {
          lastErrorRef.current = msg.error;
          const lines = msg.error.trim().split("\n");
          toast.error("The search stopped with an error", {
            description: lines[lines.length - 1],
          });
        }
      };
    };

    connect();
    return () => {
      // cleanup: stop retrying and close the WebSocket when the app unmounts
      disposed = true;
      window.clearTimeout(retryId);
      ws?.close();
    };
  }, []);

  // ── navigation ─────────────────────────────────────────────────────────────
  // useCallback memoises a function so child components don't re-render
  // unnecessarily just because App re-rendered.

  const navigateTo = useCallback((nodeId: string, oppMove: string | null) => {
    setPathIds((prev) => [...prev, nodeId]);
    setPathMoves((prev) => [...prev, oppMove]);
    setSelectedKey(null);
  }, []);

  const goBack = useCallback(() => {
    setPathIds((prev) => prev.slice(0, -1));
    setPathMoves((prev) => prev.slice(0, -1));
    setSelectedKey(null);
  }, []);

  // Path rail: depth 0 = root, depth n = the n-th step
  const jumpTo = useCallback((depth: number) => {
    setPathIds((prev) => prev.slice(0, depth));
    setPathMoves((prev) => prev.slice(0, depth));
    setSelectedKey(null);
  }, []);

  // ── action click handler ───────────────────────────────────────────────────
  // If there's exactly 1 outcome and 1 thing the foe could have done, there's nothing to pick in the
  // inspector and we navigate directly.
  const handleActionClick = (key: string) => {
    const action = currentNode?.actions[key];
    if (!action) return;
    if (action.nodes.length === 1 && action.opp_moves.length <= 1) {
      navigateTo(action.nodes[0].id, action.opp_moves[0]?.label ?? null);
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

  // Fetch pokemon data once the backend is up (add to the existing useEffect block or separate)
  useEffect(() => {
    if (!everConnected) return;
    getJSON<PokemonData>("/pokemon-data")
      .then(setPokemonData)
      .catch(console.error);
  }, [everConnected]);

  // ── MCTS controls ───────────────────────────────────────────────────────────
  const start = async (myTeam: PokemonConfig[], oppTeam: PokemonConfig[]) => {
    if (starting || running) return;
    setStarting(true);
    try {
      await postJSON("/start", {
        my_team: myTeam,
        opp_team: oppTeam,
        iterations,
        trainer_items: trainerItems.filter(Boolean),
        terrain,
      });
      if (boxState.dirty) boxState.save(); // the party's edits are in the box, a search saves them
      setSessionActive(true);
      setTree(null);
      setPathIds([]);
      setPathMoves([]);
      setSelectedKey(null);
      setStartTime(Date.now());
      setElapsed(0);
      setRunMax(iterations);
      setView("explore");
    } catch (e) {
      console.error(e);
      const message = e instanceof Error ? e.message : String(e);
      toast.error("Could not start the search", {
        description:
          message === "Failed to fetch" ? `Can't reach ${API_URL}` : message,
      });
    } finally {
      setStarting(false);
    }
  };

  const stop = () => {
    postJSON("/stop").catch(console.error);
  };

  const canStart = myTeam.length > 0 && oppTeam.length > 0;

  // ── render ──────────────────────────────────────────────────────────────────
  // JSX looks like HTML but it's actually JavaScript.
  // className instead of class (class is a reserved word in JS).
  // onClick, onChange etc. are camelCase event handlers.
  return (
    <TooltipProvider delayDuration={300}>
      <div className="flex h-screen flex-col overflow-hidden bg-background text-foreground">
        <TopBar
          view={view}
          onView={setView}
          connected={connected}
          compiling={compiling}
          running={running}
          starting={starting}
          sessionActive={sessionActive}
          displayIterations={displayIterations}
          actualIterations={actualIterations}
          maxIterations={runMax || iterations}
          elapsed={elapsed}
          iterations={iterations}
          onIterations={setIterations}
          canStart={canStart}
          onStart={() => start(myTeam, oppTeam)}
          onStop={stop}
          canContinue={!!currentNode && !currentNode.snapshot.terminal}
          battleOver={!!currentNode?.snapshot.terminal}
          onContinue={() => currentNode && setContinueNodeId(currentNode.id)}
        />

        {!everConnected ? (
          <WaitingForBackend />
        ) : (
          <main className="min-h-0 flex-1">
            {/* Always mounted — CSS hide/show preserves team state between tab switches */}
            <div
              className={
                view === "configure" ? "flex h-full flex-col" : "hidden"
              }
            >
              <ConfigureView
                pokemonData={pokemonData}
                trainerDB={trainerDB}
                myTeam={myTeam}
                setMyTeam={setMyTeam}
                oppTeam={oppTeam}
                setOppTeam={setOppTeam}
                trainerItems={trainerItems}
                setTrainerItems={setTrainerItems}
                terrain={terrain}
                setTerrain={setTerrain}
                run={run}
                onRunChange={saveRun}
                boxState={boxState}
                onSetDead={setBoxEntryDead}
                evolutions={encounterDB?.evolutions}
              />
            </div>

            {view === "tracker" && (
              <TrackerView
                run={run}
                encounterDB={encounterDB}
                itemDB={itemDB}
                pokemonData={pokemonData}
                box={boxState.box}
                lineOf={lineOf}
                error={trackerError ?? boxState.error}
                onRetry={() => {
                  if (trackerError) {
                    setTrackerError(null);
                    loadTracker();
                  }
                  if (boxState.error) boxState.retry();
                }}
                onChange={changeRun}
                onStore={storeFromTracker}
                onClearRow={clearTrackerRow}
                onNewRun={startNewRun}
              />
            )}

            {view === "explore" &&
              (!sessionActive || !tree || !currentNode ? (
                <ExploreEmpty
                  sessionActive={sessionActive}
                  onSetup={() => setView("configure")}
                />
              ) : (
                <div className="grid h-full grid-cols-[180px_minmax(0,1fr)_270px] min-[1400px]:grid-cols-[220px_minmax(0,1fr)_340px] 2xl:grid-cols-[260px_minmax(0,1fr)_400px]">
                  <PathRail
                    tree={tree}
                    pathIds={pathIds}
                    pathMoves={pathMoves}
                    nodeMap={nodeMap}
                    onJump={jumpTo}
                    onBack={goBack}
                  />
                  <div className="min-h-0 overflow-y-auto">
                    <div className="mx-auto max-w-[1080px]">
                      <BattleView
                        node={currentNode}
                        oppMove={
                          currentNode.id === pathIds[pathIds.length - 1]
                            ? pathMoves[pathMoves.length - 1]
                            : null
                        }
                      />
                      <ActionPanel
                        node={currentNode}
                        onActionClick={handleActionClick}
                        selectedKey={selectedKey}
                      />
                    </div>
                  </div>
                  <OutcomeInspector
                    action={selectedAction}
                    onSelect={navigateTo}
                    onClose={() => setSelectedKey(null)}
                  />
                </div>
              ))}
          </main>
        )}

        {continueNodeId && (
          <ContinueModal
            nodeId={continueNodeId}
            path={pathIds.map((id, i) => ({ node_id: id, opp_move: pathMoves[i] }))}
            onClose={() => setContinueNodeId(null)}
            defaultIterations={iterations}
            onStarted={(n) => {
              setSessionActive(true);
              setTree(null);
              setPathIds([]);
              setPathMoves([]);
              setSelectedKey(null);
              setStartTime(Date.now());
              setElapsed(0);
              setRunMax(n);
            }}
          />
        )}
        <Toaster position="bottom-right" />
      </div>
    </TooltipProvider>
  );
}

function WaitingForBackend() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4">
      <div className="relative flex size-14 items-center justify-center rounded-2xl bg-card ring-1 ring-border">
        <Unplug className="size-6 text-muted-foreground" />
        <Loader2 className="absolute -right-1.5 -bottom-1.5 size-5 animate-spin text-primary" />
      </div>
      <div className="text-center">
        <p className="text-sm font-medium">Waiting for the backend…</p>
        <p className="mt-1 text-xs text-muted-foreground">
          Trying <span className="num">{API_URL}</span>. Start it with{" "}
          <code className="rounded bg-foreground/8 px-1 py-0.5">dev.bat</code>{" "}
          if it isn't running.
        </p>
      </div>
    </div>
  );
}

function ExploreEmpty({
  sessionActive,
  onSetup,
}: {
  sessionActive: boolean;
  onSetup: () => void;
}) {
  if (sessionActive) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-muted-foreground">
        <Loader2 className="size-6 animate-spin text-primary" />
        <p className="text-sm">Building the search tree…</p>
      </div>
    );
  }
  return (
    <div className="flex h-full items-center justify-center p-8">
      <div className="w-full max-w-md rounded-2xl border bg-card p-8 text-center shadow-2xl shadow-black/30">
        <div className="mx-auto flex size-12 items-center justify-center rounded-xl bg-primary/12 ring-1 ring-primary/30">
          <Search className="size-5 text-primary" />
        </div>
        <h2 className="mt-4 text-base font-semibold">No search yet</h2>
        <p className="mt-1.5 text-sm text-muted-foreground">
          Pick your team and a trainer in Setup, then start the search. Results
          show up here while it runs.
        </p>
        <div className="mt-6 flex justify-center gap-2">
          <Button onClick={onSetup}>
            <Settings2 /> Go to Setup
          </Button>
        </div>
      </div>
    </div>
  );
}
