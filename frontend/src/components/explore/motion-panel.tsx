"use client";

import { ArrowUp } from "lucide-react";
import { cn } from "@/lib/cn";
import { directionLabel, screenAngle, speedPlain, speedReal, speedShort, suggestion } from "@/lib/explore/motion-language";
import { Reveal } from "./panel-parts";
import { useExplore } from "./use-explore";

/** Mover list, then how the selected one moves, in everyday words. */
export function MotionPanel() {
  const ex = useExplore();
  const m = ex.selectedMover;

  return (
    <div className="flex flex-col gap-4">
      <p className="text-small text-ink-secondary">
        The numbered circle is the object at the selected date. Its dashed trail
        shows earlier positions, not another object. Press Play on the timeline
        to watch the position change.
      </p>
      <ol className="flex flex-col" aria-label="Motion candidates">
        {ex.movers.map((x) => {
          const selected = x.id === ex.moverId;
          return (
            <li key={x.id}>
              <button
                type="button"
                aria-pressed={selected}
                onClick={() => ex.selectMover(x.id)}
                className={cn(
                  "grid w-full cursor-pointer grid-cols-[24px_1fr] items-center gap-3 rounded-lg border px-2 py-1.5 text-left transition-colors duration-(--dur-feedback) ease-standard",
                  selected ? "border-ember-line bg-ember-wash" : "border-transparent hover:bg-raised",
                )}
              >
                <span className="flex size-6 items-center justify-center rounded-full border border-line-strong font-mono text-mono-sm tabular-nums text-ink">
                  {x.number}
                </span>
                <span className="text-body-sm text-ink">{speedShort(x.speedArcsecPerHour)}</span>
              </button>
            </li>
          );
        })}
      </ol>

      {!m && <p className="text-small text-ink-secondary">Pick one, here or on the image.</p>}

      {m && (
        <div className="flex flex-col gap-4">
          <p className="text-small text-ink-secondary">Candidate only: this track has not been independently verified against known objects at every observation date.</p>
          <div className="flex flex-col gap-1">
            <p className="text-small text-ink-secondary">Speed</p>
            <p className="text-body text-ink">It moves {speedPlain(m.speedArcsecPerHour)}.</p>
            <Reveal label="Show the real value" mono>{speedReal(m.speedArcsecPerHour)}</Reveal>
          </div>

          <div className="flex items-center gap-4">
            <span className="flex size-14 shrink-0 items-center justify-center rounded-full border border-line-strong bg-raised" aria-hidden="true">
              <ArrowUp
                size={24}
                strokeWidth={1.5}
                className="text-ink transition-transform duration-(--dur-enter) ease-standard"
                style={{ transform: `rotate(${screenAngle(m.positionAngleDeg)}deg)` }}
              />
            </span>
            <div className="flex flex-col gap-1">
              <p className="text-small text-ink-secondary">Direction on the image</p>
              <p className="text-body-sm text-ink">{directionLabel(m.positionAngleDeg)}</p>
              <Reveal label="Show the real value" mono>{`Position angle ${m.positionAngleDeg.toFixed(0)}° (measured from north, through east)`}</Reveal>
            </div>
          </div>

          <div className="flex flex-col gap-1">
            <p className="text-small text-ink-secondary">What this suggests</p>
            <p className="text-body-sm text-ink">{suggestion(m)}</p>
            <p className="text-small text-ink-secondary">
              A clue, not a confirmed result. Based on {m.points.length} comparable observations.
            </p>
          </div>
        </div>
      )}

      <button type="button" onClick={ex.clearMotion} className="w-fit cursor-pointer rounded-xs text-small text-ink-secondary underline underline-offset-4 transition-colors duration-(--dur-feedback) ease-standard hover:text-ink">
        Clear the analysis
      </button>
    </div>
  );
}
