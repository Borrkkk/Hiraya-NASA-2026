"use client";

import { useState } from "react";
import { cn } from "@/lib/cn";
import { TYPE_LABELS } from "@/lib/explore/labels";
import { formatCoords } from "@/lib/sky/format";
import { Notice, Reveal, Skeleton, buttonSecondary } from "./panel-parts";
import { SpectrumChart } from "./spectrum-chart";
import { useExplore } from "./use-explore";

const fmtSize = (d: number) => (d >= 1 ? `${d.toFixed(2)}°` : d >= 1 / 60 ? `${(d * 60).toFixed(1)}′` : `${(d * 3600).toFixed(0)}″`);

/** What's selected, a type guess with its reason, other possibilities, the spectrum. */
export function ObjectPanel() {
  const ex = useExplore();
  const { box, inspectQuery: q } = ex;
  const [more, setMore] = useState(false);

  if (!box) return <NoSelection />;

  const header = ex.selectedMover ? `Mover ${ex.selectedMover.number}` : "Your box";
  const waiting = q.isPending || q.isFetching;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-0.5">
        <p className="text-body-sm font-medium text-ink">{header}</p>
        <p className="font-mono text-mono tabular-nums text-ink-secondary">
          {formatCoords(box.ra, box.dec)} · {fmtSize(box.width)} × {fmtSize(box.height)}
        </p>
      </div>

      {q.isError && (
        <Notice tone="error">
          <p>We couldn&apos;t read this box.</p>
          <button type="button" className={cn(buttonSecondary, "w-fit")} onClick={() => q.refetch()}>
            Try again
          </button>
        </Notice>
      )}

      {!q.isError && waiting && !q.data && (
        <div className="flex flex-col gap-4" aria-busy="true">
          <p role="status" className="text-small text-ink-secondary">Reading the infrared light in your box…</p>
          <Skeleton className="h-20" />
          <Skeleton className="h-10" />
          <Skeleton className="h-40" />
        </div>
      )}

      {q.data && (
        <div className={cn("flex flex-col gap-4 transition-opacity duration-(--dur-feedback) ease-standard", waiting && "opacity-60")}>
          <div className="flex flex-col gap-1">
            <p className="text-small text-ink-secondary">Best guess</p>
            <p className="text-h3 text-ink">{TYPE_LABELS[q.data.guess.type]}</p>
            <p className="text-body-sm text-ink-secondary">{q.data.guess.reason}</p>
          </div>

          {q.data.evidence && <section className="rounded-md border border-line bg-surface p-3" aria-label="Measurement quality">
            <p className="text-small font-medium text-ink">Measurement quality</p>
            <p className="mt-1 text-caption text-ink-secondary">{q.data.evidence.measurement}</p>
            <p className="mt-2 font-mono text-mono-sm text-ink-secondary">{q.data.evidence.nUsable} usable / {q.data.evidence.nFrames} frames · {q.data.evidence.nDetected} detections</p>
            {q.data.evidence.nFailed > 0 && <p className="mt-1 text-caption text-ember">{q.data.evidence.nFailed} frames could not be measured.</p>}
            {Object.keys(q.data.evidence.flags).length > 0 && <p className="mt-1 break-words text-caption text-ink-secondary">Flags: {Object.keys(q.data.evidence.flags).join(", ")}</p>}
            {q.data.evidence.warnings.map((warning, i) => <p key={i} className="mt-2 text-caption text-ink-secondary">{warning}</p>)}
          </section>}

          {q.data.candidates.length > 0 && <div className="flex flex-col gap-2">
            <button
              type="button"
              aria-expanded={more}
              onClick={() => setMore((v) => !v)}
              className="w-fit cursor-pointer rounded-xs text-small text-ink-secondary underline underline-offset-4 transition-colors duration-(--dur-feedback) ease-standard hover:text-ink"
            >
              {more ? "Hide other possibilities" : "Other possibilities"}
            </button>
            {more && (
              <ul className="flex flex-col gap-2">
                {q.data.candidates.map((c) => (
                  <li key={c.type} className="grid grid-cols-[132px_1fr_40px] items-center gap-3 text-small">
                    <span className="text-ink">{TYPE_LABELS[c.type]}</span>
                    <span className="h-1.5 overflow-hidden rounded-full bg-raised" aria-hidden="true">
                      <span className="block h-full rounded-full bg-ink-secondary" style={{ width: `${Math.round(c.confidence * 100)}%` }} />
                    </span>
                    <span className="text-right font-mono text-mono-sm tabular-nums text-ink-secondary">
                      {Math.round(c.confidence * 100)}%
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>}

          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-body-sm font-medium text-ink">Infrared spectrum</p>
              <div role="radiogroup" aria-label="Which observation" className="flex gap-1 rounded-md border border-line bg-surface p-0.5">
                {[
                  { v: false, l: "This one" },
                  { v: true, l: "All combined" },
                ].map((o) => (
                  <button
                    key={o.l}
                    type="button"
                    role="radio"
                    aria-checked={ex.allEpochs === o.v}
                    onClick={() => ex.setAllEpochs(o.v)}
                    className={cn(
                      "h-7 cursor-pointer rounded-sm px-2 text-caption transition-colors duration-(--dur-feedback) ease-standard",
                      ex.allEpochs === o.v ? "bg-overlay text-ink" : "text-ink-secondary hover:text-ink",
                    )}
                  >
                    {o.l}
                  </button>
                ))}
              </div>
            </div>
            {q.data.lowSignal ? (
              <p className="text-small text-ink-secondary">Not enough signal to draw a useful chart.</p>
            ) : (
              <SpectrumChart spectrum={q.data.spectrum} />
            )}
            <Reveal label="What am I looking at?">
              {q.data.evidence
                ? "Each point measures a source near the centre of your selection at a wavelength, in Jy. Flagged flux measurements are excluded from this chart. A wavelength sample alone does not confirm a gas or ice feature."
                : "Each point is how bright your box is at one colour of infrared light, from short wavelengths on the left to long on the right. Dips and bumps are fingerprints: gases and ices take light in or give it out at set wavelengths."}
            </Reveal>
          </div>
        </div>
      )}
    </div>
  );
}

export function NoSelection() {
  const steps = [
    ["Pick what to look for", "Use the list on the left. Start with the defaults."],
    ["Draw a box", "Choose Select box above the image, then drag around something that catches your eye."],
    ["Read the answer", "Here you'll see what it probably is. Then check if it's already known."],
  ];
  return (
    <ol className="flex flex-col gap-4">
      {steps.map(([title, body], i) => (
        <li key={title} className="grid grid-cols-[28px_1fr] gap-3">
          <span className="flex size-7 items-center justify-center rounded-full border border-line-strong font-mono text-mono-sm text-ink">{i + 1}</span>
          <span className="flex flex-col gap-0.5">
            <span className="text-body-sm font-medium text-ink">{title}</span>
            <span className="text-small text-ink-secondary">{body}</span>
          </span>
        </li>
      ))}
    </ol>
  );
}
