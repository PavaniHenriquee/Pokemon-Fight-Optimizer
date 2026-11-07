import { cn } from "@/lib/utils";
import type { MoveEntry } from "../../types";
import { CategoryIcon, TypeIcon } from "./Badges";

// Move list for hover cards: type symbol, name, category, PP
export function MoveList({ moves, className }: { moves: MoveEntry[]; className?: string }) {
  if (moves.length === 0) return null;
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      {moves.map((m, idx) => (
        <div key={idx} className="flex items-center gap-2 text-xs">
          <TypeIcon type={m.type} size={14} />
          <span className="flex-1 truncate text-foreground">{m.name}</span>
          <CategoryIcon category={m.category} />
          <span
            className={cn(
              "num w-12 text-right text-[11px]",
              m.pp <= 0 ? "font-semibold text-bad" : "text-muted-foreground",
            )}
          >
            {m.pp}/{m.max_pp}
          </span>
        </div>
      ))}
    </div>
  );
}
