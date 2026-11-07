// Display helpers shared by every screen.

export type Tier = "good" | "warn" | "bad";

export function hpTier(hp: number, max: number): Tier {
  const pct = hp / Math.max(max, 1);
  return pct > 0.5 ? "good" : pct > 0.25 ? "warn" : "bad";
}

export function winTier(win: number): Tier {
  return win > 0.65 ? "good" : win > 0.4 ? "warn" : "bad";
}

// Literal class names so Tailwind sees them
export const TIER_TEXT: Record<Tier, string> = {
  good: "text-good",
  warn: "text-warn",
  bad: "text-bad",
};
export const TIER_BG: Record<Tier, string> = {
  good: "bg-good",
  warn: "bg-warn",
  bad: "bg-bad",
};
export const TIER_VAR: Record<Tier, string> = {
  good: "var(--good)",
  warn: "var(--warn)",
  bad: "var(--bad)",
};

// HP is shown as a bracket, not an exact value: outcomes are grouped by bracket
export function hpRange(hp: number, max: number): string {
  const pct = hp / Math.max(max, 1);
  if (pct <= 0) return "Fainted";
  if (pct === 1) return "100%";
  if (pct >= 0.75) return "75%–100%";
  if (pct >= 0.5) return "50%–74%";
  if (pct >= 0.25) return "25%–49%";
  return "1%–24%";
}

// An outcome row's label when it isn't a move, as a sentence about the opponent goes on
export const OPP_DID: Record<string, string> = {
  "Didn't move": "didn't move",
  Switched: "switched",
  "Used item": "used an item",
};

// m:ss
export function formatTime(ms: number): string {
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

const intFormat = new Intl.NumberFormat("en-US");
export const fmtInt = (n: number) => intFormat.format(n);

export const fmtPct = (x: number, digits = 0) => `${(x * 100).toFixed(digits)}%`;

export function fmtCompact(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(n >= 10_000_000 ? 0 : 1)}M`;
  if (n >= 10_000) return `${Math.round(n / 1000)}k`;
  return fmtInt(n);
}

// DB names (Mr_mime, Nidoran_f, Deoxys_attack) → display names. Keys stay raw everywhere else.
const NAME_OVERRIDES: Record<string, string> = {
  Nidoran_f: "Nidoran♀",
  Nidoran_m: "Nidoran♂",
  Mr_mime: "Mr. Mime",
  Mime_jr: "Mime Jr.",
  Ho_oh: "Ho-Oh",
  Porygon_z: "Porygon-Z",
  Farfetchd: "Farfetch'd",
};

export function displayName(raw: string): string {
  if (!raw) return raw;
  const known = NAME_OVERRIDES[raw];
  if (known) return known;
  return raw
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join("-");
}

// Switch actions are labelled "→ Name" by the backend
export const switchTarget = (label: string) => label.replace(/^→\s*/, "");

export function typeColor(type: string | null | undefined): string {
  return `var(--type-${(type || "typeless").toLowerCase()})`;
}

export const STATUS_NAMES: Record<string, string> = {
  BRN: "Burned",
  PAR: "Paralyzed",
  SLP: "Asleep",
  FRZ: "Frozen",
  PSN: "Poisoned",
  TOX: "Badly poisoned",
};

export function statusColor(status: string): string {
  return `var(--status-${status.toLowerCase()})`;
}
