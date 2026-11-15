"use client";

import { Minus, Plus } from "lucide-react";
import { IconButton } from "@/components/ui";
import { fovToT, tToFov } from "@/lib/explore/fov";
import { useStore } from "@/lib/explore/store";
import { useExplore } from "./use-explore";

/** Zoom: minus, a slider, plus, and the size in degrees. Nothing else. */
export function FovControl() {
  const { viewStore, limits, setView } = useExplore();
  const view = useStore(viewStore);
  if (!limits) return <div className="h-9" />;
  const { min, max } = limits;
  const closest = view.fov <= min * 1.001;
  const widest = view.fov >= max * 0.999;
  const zoom = (k: number) => setView({ ...view, fov: view.fov * k });
  const deg = view.fov >= 10 ? view.fov.toFixed(0) : view.fov.toFixed(view.fov >= 1 ? 1 : 2);

  return (
    <div className="flex items-center gap-2">
      <IconButton label="Zoom out" onClick={() => zoom(1.4)} disabled={widest} className="size-9">
        <Minus size={16} strokeWidth={1.5} aria-hidden="true" />
      </IconButton>
      <input
        type="range"
        min={0}
        max={1}
        step={0.001}
        value={fovToT(view.fov, min, max)}
        aria-label="Zoom"
        aria-valuetext={`${deg} degrees wide`}
        onChange={(e) => setView({ ...view, fov: tToFov(Number(e.target.value), min, max) })}
        className="h-5 w-[180px] cursor-pointer accent-[var(--color-ink)]"
      />
      <IconButton label="Zoom in" onClick={() => zoom(1 / 1.4)} disabled={closest} className="size-9">
        <Plus size={16} strokeWidth={1.5} aria-hidden="true" />
      </IconButton>
      <span className="w-[84px] font-mono text-mono tabular-nums text-ink-secondary">{closest ? "Closest" : `${deg}° wide`}</span>
    </div>
  );
}
