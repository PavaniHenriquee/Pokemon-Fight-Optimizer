import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import type { BoxEntry } from "../types";
import { getJSON, postJSON } from "./api";

// The PC box and the death box (one file, BoxEntry.dead tells them apart). box stays null until the real
// box has loaded: nothing can be edited or saved before that, so a malfunction can't wipe the file.
export function useBox(enabled: boolean) {
  const [box, setBox] = useState<BoxEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loads, setLoads] = useState(0); // Try again counts up to load it once more
  const [dirty, setDirty] = useState(false);
  const [saved, setSaved] = useState(false);
  const saves = useRef<Promise<unknown>>(Promise.resolve()); // one at a time, in order

  useEffect(() => {
    if (!enabled) return;
    getJSON<BoxEntry[]>("/box")
      .then((data) => setBox(data))
      .catch((e: Error) => setError(e.message));
  }, [enabled, loads]);

  function save(entries: BoxEntry[] | null = box) {
    if (entries === null) return;
    saves.current = saves.current
      .then(() => postJSON("/box", entries))
      .then(() => {
        setDirty(false);
        setSaved(true);
        setTimeout(() => setSaved(false), 1500);
      })
      .catch((e: Error) =>
        toast.error("Couldn't save the box", { description: e.message }),
      );
  }

  return {
    box,
    error,
    dirty,
    saved,
    save,
    retry() {
      setError(null);
      setLoads((n) => n + 1);
    },
    // An edit waits for the Save button
    edit(entries: BoxEntry[]) {
      setBox(entries);
      setDirty(true);
    },
    // Stored right away: it stays marked until the save lands
    commit(entries: BoxEntry[]) {
      setBox(entries);
      setDirty(true);
      save(entries);
    },
  };
}

export type BoxState = ReturnType<typeof useBox>;
