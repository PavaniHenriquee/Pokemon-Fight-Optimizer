import { useState, type CSSProperties } from "react";
import { cn } from "@/lib/utils";

// <img> that walks its URL list on error (local copy → remote → static fallback)
export function Sprite({
  srcs,
  alt = "",
  title,
  className,
  style,
  width,
  height,
  fallback = null,
  pixelated = true,
}: {
  srcs: string[];
  alt?: string;
  title?: string;
  className?: string;
  style?: CSSProperties;
  width?: number;
  height?: number;
  fallback?: React.ReactNode;
  pixelated?: boolean; // false for smooth art scaled down (type badges)
}) {
  const key = srcs.join("|");
  const [state, setState] = useState({ key, idx: 0 });
  // A new source list starts again from its first URL
  const idx = state.key === key ? state.idx : 0;
  if (state.key !== key) setState({ key, idx: 0 });

  if (idx >= srcs.length) return <>{fallback}</>;
  return (
    <img
      src={srcs[idx]}
      alt={alt}
      title={title}
      width={width}
      height={height}
      draggable={false}
      className={cn(pixelated && "pixelated", "select-none", className)}
      style={style}
      onError={() => setState({ key, idx: idx + 1 })}
    />
  );
}
