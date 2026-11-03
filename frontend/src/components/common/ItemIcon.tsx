import { itemIcon } from "@/lib/sprites";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Sprite } from "./Sprite";

// Item sprite with its name as a tooltip; the name shows as text when there's no sprite
export function ItemIcon({
  name,
  size = 20,
  className,
}: {
  name: string;
  size?: number;
  className?: string;
}) {
  if (!name) return null;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          className={cn("inline-flex shrink-0 items-center justify-center", className)}
          style={{ minWidth: size, height: size }}
        >
          <Sprite
            srcs={itemIcon(name)}
            alt={name}
            width={size}
            height={size}
            fallback={<span className="text-[10px] text-muted-foreground">{name}</span>}
          />
        </span>
      </TooltipTrigger>
      <TooltipContent>{name}</TooltipContent>
    </Tooltip>
  );
}
