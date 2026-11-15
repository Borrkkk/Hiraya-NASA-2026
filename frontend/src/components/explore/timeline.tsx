"use client";

import { Loader2, Pause, Play, Waves } from "lucide-react";
import { useRef, useState } from "react";
import { cn } from "@/lib/cn";
import { clamp } from "@/lib/explore/projection";
import { useExplore } from "./use-explore";

const fmtDate = (iso: string) => {
  const d = new Date(iso);
  const day = d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
  // Exposures can be minutes apart, so the time matters when it isn't midnight.
  const midnight = d.getUTCHours() === 0 && d.getUTCMinutes() === 0;
  return midnight ? day : `${day}, ${d.toISOString().slice(11, 16)} UTC`;
};

/**
 * Time runs left to right, spaced by real dates, so gaps show. A tick is
 * hollow until its frames have loaded. The playhead snaps to ticks; the two
 * handles set the period motion analysis covers.
 */
export function Timeline() {
  const ex = useExplore();
  const { epochs, playheadIdx, range, loadedEpochs, emptyEpochs } = ex;
  const trackRef = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const [dragging, setDragging] = useState<"head" | "start" | "end" | null>(null);

  const times = epochs.map((e) => Date.parse(e.date));
  const t0 = times[0] ?? 0;
  const span = Math.max(1, (times[times.length - 1] ?? 1) - t0);
  // Keep ticks off the very edges of the track.
  const pos = (i: number) => ((times[i] - t0) / span) * 100;

  const nearest = (clientX: number) => {
    const r = trackRef.current!.getBoundingClientRect();
    const pct = ((clientX - r.left) / r.width) * 100;
    let best = 0;
    epochs.forEach((_, i) => {
      if (Math.abs(pos(i) - pct) < Math.abs(pos(best) - pct)) best = i;
    });
    return best;
  };

  const drag = (kind: "head" | "start" | "end") => (e: React.PointerEvent) => {
    e.stopPropagation();
    e.currentTarget.setPointerCapture(e.pointerId);
    setDragging(kind);
  };
  const onMove = (e: React.PointerEvent) => {
    if (!dragging) return;
    const i = nearest(e.clientX);
    if (dragging === "head") ex.setPlayhead(i);
    if (dragging === "start") ex.setRange([clamp(i, 0, range[1]), range[1]]);
    if (dragging === "end") ex.setRange([range[0], clamp(i, range[0], epochs.length - 1)]);
  };
  const stopDrag = () => setDragging(null);

  const canAnalyze = ex.toolsEnabled && ex.rangeEpochCount >= 2 && ex.motion.status !== "running";
  const analyzing = ex.motion.status === "running";
  const upToDate = ex.motion.status === "done" && !ex.outdated;
  const hint = !ex.toolsEnabled
    ? "Available once the SPHEREx data has loaded"
    : ex.rangeEpochCount < 2
      ? "Pick a range with at least two observations"
      : null;

  return (
    <section aria-label="Timeline" className="flex h-[76px] shrink-0 items-center gap-5 rounded-xl border border-line-strong bg-surface px-5">
      <button
        type="button"
        aria-label={ex.playing ? "Stop" : "Play"}
        disabled={!ex.canPlay}
        title={!ex.canPlay ? "Playing needs at least two loaded observations in the range" : undefined}
        onClick={ex.playing ? ex.stop : ex.play}
        className="flex size-11 shrink-0 cursor-pointer items-center justify-center rounded-full border border-line-strong bg-raised text-ink transition-colors duration-(--dur-feedback) ease-standard hover:bg-overlay disabled:cursor-not-allowed disabled:opacity-50"
      >
        {ex.playing ? <Pause size={18} strokeWidth={1.5} aria-hidden="true" /> : <Play size={18} strokeWidth={1.5} aria-hidden="true" className="translate-x-px" />}
      </button>

      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        <p className="text-small text-ink">
          {ex.playheadEpoch ? fmtDate(ex.playheadEpoch.date) : "Waiting for observations"}
          {epochs.length > 0 && <span className="text-ink-secondary"> · {playheadIdx + 1} of {epochs.length}</span>}
        </p>

        <div ref={trackRef} className="relative mx-3 h-6 touch-none select-none" onPointerMove={onMove} onPointerUp={stopDrag} onPointerCancel={stopDrag}>
          <div className="absolute inset-x-0 top-1/2 h-0.5 -translate-y-1/2 rounded-full bg-line-strong" />
          {epochs.length > 0 && (
            <div
              className="absolute top-1/2 h-1 -translate-y-1/2 rounded-full bg-ink-secondary"
              style={{ left: `${pos(range[0])}%`, width: `${pos(range[1]) - pos(range[0])}%` }}
            />
          )}

          {epochs.map((e, i) => {
            const loaded = loadedEpochs[i];
            const empty = emptyEpochs[i];
            const inRange = i >= range[0] && i <= range[1];
            return (
              <button
                key={e.id}
                type="button"
                aria-label={`${fmtDate(e.date)}${empty ? ", nothing at the selected wavelengths" : loaded ? "" : ", still loading"}`}
                disabled={!ex.toolsEnabled && !loaded}
                onClick={() => ex.setPlayhead(i)}
                onPointerEnter={() => setHover(i)}
                onPointerLeave={() => setHover((h) => (h === i ? null : h))}
                onFocus={() => setHover(i)}
                onBlur={() => setHover((h) => (h === i ? null : h))}
                className="absolute top-1/2 flex size-6 -translate-x-1/2 -translate-y-1/2 cursor-pointer items-center justify-center rounded-full"
                style={{ left: `${pos(i)}%` }}
              >
                <span
                  className={cn(
                    "size-2.5 rounded-full border-2",
                    empty
                      ? "size-1.5 border-ink-muted bg-ink-muted opacity-60"
                      : loaded
                        ? inRange ? "border-ink bg-ink" : "border-ink-muted bg-ink-muted"
                        : "border-ink-secondary bg-surface",
                  )}
                />
                {hover === i && (
                  <span className="pointer-events-none absolute bottom-[calc(100%+6px)] z-20 whitespace-nowrap rounded-xs border border-line-strong bg-overlay px-2 py-1 text-small text-ink">
                    {fmtDate(e.date)}
                    {empty ? <span className="text-ink-secondary"> · nothing at these wavelengths</span> : !loaded && <span className="text-ink-secondary"> · loading</span>}
                  </span>
                )}
              </button>
            );
          })}

          {epochs.length > 0 && (
            <>
              <RangeHandle left={pos(range[0])} label="Start of the analysis range" onDown={drag("start")} />
              <RangeHandle left={pos(range[1])} label="End of the analysis range" onDown={drag("end")} />
              <div
                role="slider"
                tabIndex={0}
                aria-label="Playhead"
                aria-valuemin={range[0] + 1}
                aria-valuemax={range[1] + 1}
                aria-valuenow={playheadIdx + 1}
                aria-valuetext={ex.playheadEpoch ? fmtDate(ex.playheadEpoch.date) : undefined}
                onKeyDown={(e) => {
                  if (e.key === "ArrowLeft") ex.setPlayhead(playheadIdx - 1);
                  if (e.key === "ArrowRight") ex.setPlayhead(playheadIdx + 1);
                }}
                onPointerDown={drag("head")}
                className={cn(
                  "absolute top-1/2 z-10 size-5 -translate-x-1/2 -translate-y-1/2 cursor-grab touch-none rounded-full border-2 border-ground bg-ember active:cursor-grabbing",
                  dragging !== "head" && "transition-[left] duration-(--dur-move) ease-standard",
                )}
                style={{ left: `${pos(playheadIdx)}%` }}
              />
            </>
          )}
        </div>
      </div>

      <div className="flex shrink-0 flex-col items-end gap-1">
        <button
          type="button"
          disabled={!canAnalyze}
          onClick={ex.analyze}
          className="inline-flex h-11 w-[176px] cursor-pointer items-center justify-center gap-2 rounded-md bg-primary px-4 text-body-sm font-medium text-on-primary transition-colors duration-(--dur-feedback) ease-standard hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-60"
        >
          {analyzing ? <Loader2 size={16} strokeWidth={1.5} className="animate-spin" aria-hidden="true" /> : <Waves size={16} strokeWidth={1.5} aria-hidden="true" />}
          {analyzing ? "Analyzing…" : upToDate || ex.outdated ? "Analyze again" : "Analyze motion"}
        </button>
        {hint && <p className="max-w-[176px] text-right text-caption text-ink-secondary">{hint}</p>}
      </div>
    </section>
  );
}

/** The two grips that set the analysis period: small bars at the ends of the bright segment. */
function RangeHandle({ left, label, onDown }: { left: number; label: string; onDown: (e: React.PointerEvent) => void }) {
  return (
    <div
      role="presentation"
      title={label}
      onPointerDown={onDown}
      className="absolute top-1/2 z-[5] flex h-6 w-4 -translate-x-1/2 -translate-y-1/2 cursor-ew-resize touch-none items-center justify-center"
      style={{ left: `${left}%` }}
    >
      <span className="h-6 w-1 rounded-full bg-ink" />
    </div>
  );
}
