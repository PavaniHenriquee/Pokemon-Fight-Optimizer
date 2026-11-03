import { useState } from "react";
import { cn } from "@/lib/utils";
import { fmtInt } from "@/lib/format";

// Digits only; shows 100,000 while blurred, raw digits while editing, never below 1
export function IterationsInput({
  value,
  onChange,
  disabled,
  className,
  title = "Max iterations",
}: {
  value: number;
  onChange: (n: number) => void;
  disabled?: boolean;
  className?: string;
  title?: string;
}) {
  const [focused, setFocused] = useState(false);
  return (
    <input
      type="text"
      inputMode="numeric"
      title={title}
      value={focused ? (value === 0 ? "" : value) : fmtInt(value)}
      onFocus={() => setFocused(true)}
      onBlur={() => {
        setFocused(false);
        onChange(Math.max(1, value));
      }}
      onChange={(e) => {
        const raw = e.target.value.replace(/\D/g, "");
        onChange(raw === "" ? 0 : parseInt(raw, 10));
      }}
      disabled={disabled}
      className={cn(
        "num h-8 rounded-lg border border-input bg-input/30 px-2 text-center text-sm text-foreground outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50",
        className,
      )}
    />
  );
}
