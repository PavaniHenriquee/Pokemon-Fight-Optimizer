import { useState, useEffect } from "react";
import { Loader2, Play } from "lucide-react";
import { toast } from "sonner";
import { getJSON, postJSON } from "@/lib/api";
import { pokIcon } from "@/lib/sprites";
import { TIER_TEXT, displayName, hpTier } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { PathClick, PokemonEntry, NodeInfoData } from "../types";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog";
import { Button } from "./ui/button";
import { Sprite } from "./common/Sprite";
import { IterationsInput } from "./common/IterationsInput";

function HpRow({
  entry,
  hp,
  onChange,
}: {
  entry: PokemonEntry;
  hp: number;
  onChange: (hp: number) => void;
}) {
  const tier = hpTier(hp, entry.max_hp);
  const clamp = (v: number) => Math.max(0, Math.min(entry.max_hp, v));
  return (
    <div className="flex items-center gap-3 py-1">
      <Sprite srcs={pokIcon(entry.pok_id)} alt={entry.name} width={40} height={30} className="shrink-0 object-contain" />
      <span className="w-24 shrink-0 truncate text-sm font-medium">{displayName(entry.name)}</span>
      <input
        type="range"
        min={0}
        max={entry.max_hp}
        value={hp}
        onChange={(e) => onChange(clamp(parseInt(e.target.value) || 0))}
        className="h-1.5 flex-1 cursor-pointer accent-(--primary)"
        aria-label={`${entry.name} HP`}
      />
      <div className="flex shrink-0 items-center gap-1">
        <input
          type="number"
          min={0}
          max={entry.max_hp}
          value={hp}
          onChange={(e) => onChange(clamp(parseInt(e.target.value) || 0))}
          className={cn(
            "num h-7 w-14 rounded-md border border-input bg-input/30 text-center text-sm font-semibold outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50",
            TIER_TEXT[tier],
          )}
        />
        <span className="num w-10 text-xs text-subtle-foreground">/ {entry.max_hp}</span>
      </div>
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="mt-3 mb-1 text-[11px] font-medium tracking-wider text-subtle-foreground uppercase">
      {children}
    </p>
  );
}

interface Props {
  nodeId: string;
  path: PathClick[];
  onClose: () => void;
  onStarted: (iterations: number) => void;
  defaultIterations: number; // the top bar's
}

export default function ContinueModal({ nodeId, path, onClose, onStarted, defaultIterations }: Props) {
  const [nodeInfo, setNodeInfo] = useState<NodeInfoData | null>(null);
  const [myActiveHp, setMyActiveHp] = useState(0);
  const [oppActiveHp, setOppActiveHp] = useState(0);
  const [benchHps, setBenchHps] = useState<Record<number, number>>({});
  const [iterations, setIterations] = useState(defaultIterations);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    getJSON<NodeInfoData & { error?: string }>(`/node_info/${nodeId}`)
      .then((info) => {
        if (info.error) throw new Error(info.error);
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
    postJSON("/continue_from_node", {
      node_id: nodeId,
      iterations,
      my_active_hp: nodeInfo?.my_active ? myActiveHp : null,
      opp_active_hp: oppActiveHp,
      bench_hps: benchHps,
      path,
    })
      .then(() => {
        onStarted(iterations);
        onClose();
      })
      .catch((e: Error) => {
        toast.error("Couldn't continue from this node", { description: e.message });
        setStarting(false);
      });
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>Continue the search from here</DialogTitle>
          <DialogDescription>
            Adjust HP to match your real game. Everything else is taken from the node.
          </DialogDescription>
        </DialogHeader>

        {loading && (
          <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" /> Loading node…
          </div>
        )}

        {failed && (
          <p className="py-8 text-center text-sm text-bad">Failed to load the node state.</p>
        )}

        {!loading && !failed && nodeInfo && (
          <div className="-mt-2">
            <SectionLabel>Opponent</SectionLabel>
            <HpRow entry={nodeInfo.opp_active} hp={oppActiveHp} onChange={setOppActiveHp} />

            <SectionLabel>Your Pokémon</SectionLabel>
            {nodeInfo.my_active ? (
              <HpRow entry={nodeInfo.my_active} hp={myActiveHp} onChange={setMyActiveHp} />
            ) : (
              <p className="text-xs text-muted-foreground italic">
                Death phase: choosing a replacement, no active Pokémon.
              </p>
            )}

            {nodeInfo.my_bench.length > 0 && (
              <>
                <SectionLabel>Your bench</SectionLabel>
                {nodeInfo.my_bench.map((entry) => (
                  <HpRow
                    key={entry.slot}
                    entry={entry}
                    hp={benchHps[entry.slot] ?? entry.hp}
                    onChange={(hp) => setBenchHps((prev) => ({ ...prev, [entry.slot]: hp }))}
                  />
                ))}
              </>
            )}

            <SectionLabel>Iterations</SectionLabel>
            <IterationsInput value={iterations} onChange={setIterations} className="w-36" />
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleStart} disabled={starting || loading || failed}>
            {starting ? <Loader2 className="animate-spin" /> : <Play className="fill-current" />}
            {starting ? "Starting…" : "Start from here"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
