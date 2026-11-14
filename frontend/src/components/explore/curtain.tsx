"use client";

import { ChevronsLeftRight } from "lucide-react";
import { useRef } from "react";
import { clamp } from "@/lib/explore/projection";
import { useExplore } from "./use-explore";

/**
 * The comparison divider. SPHEREx on the left, the chosen sensor on the
 * right. The container ignores pointers so panning still works everywhere
 * but on the divider itself.
 */
export function Curtain({ layerName }: { layerName: string }) {
  const { curtain, setCurtain } = useExplore();
  const ref = useRef<HTMLDivElement>(null);

  const move = (e: React.PointerEvent) => {
    if (!(e.buttons & 1)) return;
    const r = ref.current!.getBoundingClientRect();
    setCurtain(clamp((e.clientX - r.left) / r.width, 0.06, 0.94));
  };

  return (
    <div ref={ref} className="pointer-events-none absolute inset-0 z-[4]">
      <span
        className="absolute bottom-3 -translate-x-[calc(100%+12px)] rounded-xs bg-scrim px-2 py-1 text-small text-ink"
        style={{ left: `${curtain * 100}%` }}
      >
        SPHEREx
      </span>
      <span
        className="absolute bottom-3 translate-x-3 rounded-xs bg-scrim px-2 py-1 text-small text-ink"
        style={{ left: `${curtain * 100}%` }}
      >
        {layerName}
      </span>
      <div
        role="slider"
        tabIndex={0}
        aria-label="Compare SPHEREx and the other sensor. Drag the divider, or use the arrow keys."
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(curtain * 100)}
        className="pointer-events-auto absolute inset-y-0 flex w-8 -translate-x-1/2 cursor-ew-resize touch-none items-center justify-center rounded-xs"
        style={{ left: `${curtain * 100}%` }}
        onPointerDown={(e) => {
          e.stopPropagation();
          e.currentTarget.setPointerCapture(e.pointerId);
          move(e);
        }}
        onPointerMove={move}
        onKeyDown={(e) => {
          if (e.key === "ArrowLeft") setCurtain(clamp(curtain - 0.03, 0.06, 0.94));
          if (e.key === "ArrowRight") setCurtain(clamp(curtain + 0.03, 0.06, 0.94));
        }}
      >
        <span className="absolute inset-y-0 left-1/2 w-0.5 -translate-x-1/2 bg-ink" />
        <span className="relative flex size-9 items-center justify-center rounded-full border border-line-strong bg-ground text-ink">
          <ChevronsLeftRight size={18} strokeWidth={1.5} aria-hidden="true" />
        </span>
      </div>
    </div>
  );
}
