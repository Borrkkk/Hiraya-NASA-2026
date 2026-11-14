import { cn } from "@/lib/cn";

/**
 * Pulsr's signature: four ember corners and two mono lines (name in ink,
 * coordinates in ink-secondary). One per view. Labels go right, or left near
 * an edge, never on top of the object. Not decoration.
 */
export function Reticle({
  size = 56,
  name,
  coords,
  labelSide = "right",
  className,
}: {
  size?: number;
  name?: string;
  coords?: string;
  labelSide?: "right" | "left";
  className?: string;
}) {
  const corner = size < 40 ? "size-3" : "size-3.5";
  return (
    <div className={cn("relative", className)} style={{ width: size, height: size }}>
      <span className={cn("absolute left-0 top-0 border-l-[1.5px] border-t-[1.5px] border-ember", corner)} />
      <span className={cn("absolute right-0 top-0 border-r-[1.5px] border-t-[1.5px] border-ember", corner)} />
      <span className={cn("absolute bottom-0 left-0 border-b-[1.5px] border-l-[1.5px] border-ember", corner)} />
      <span className={cn("absolute bottom-0 right-0 border-b-[1.5px] border-r-[1.5px] border-ember", corner)} />
      {(name || coords) && (
        <div
          className={cn(
            // A scrim keeps the label readable over bright sky.
            "absolute top-0 flex flex-col gap-0.5 whitespace-nowrap rounded-xs bg-scrim px-2 py-1 font-mono text-mono-sm tabular-nums",
            labelSide === "right" ? "left-[calc(100%+12px)]" : "right-[calc(100%+12px)] text-right",
          )}
        >
          {name && <span className="text-ink">{name}</span>}
          {coords && <span className="text-ink-secondary">{coords}</span>}
        </div>
      )}
    </div>
  );
}
