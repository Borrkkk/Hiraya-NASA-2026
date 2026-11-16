"use client";

import { Info } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/cn";
import { BANDS, EMPTY_BAND_NOTE } from "@/lib/explore/bands";
import { useExplore } from "./use-explore";

/**
 * "Things to look for", not wavelengths. Rows are independent toggles; at
 * least one stays on. Each has a fixed colour, so the blended picture can be
 * read from the swatches.
 */
export function BandPicker() {
  const { area, bandsOn, toggleBand, bandBlocked, bandCounts } = useExplore();
  const [open, setOpen] = useState<string | null>(null);

  return (
    <section aria-labelledby="bands-title" className="flex min-h-0 w-[280px] shrink-0 flex-col rounded-xl border border-line-strong bg-surface">
      <header className="px-4 pb-2 pt-4">
        <h2 id="bands-title" className="text-body-sm font-medium text-ink">
          Wavelength windows
        </h2>
        <p className="text-small text-ink-secondary">Selected / available observations</p>
        <p className="mt-1 text-caption text-ink-secondary">Counts cover this area&apos;s observation sample. Windows show light near a feature, not a confirmed detection.</p>
      </header>
      <ul className="scroll-pulsr flex min-h-0 flex-1 flex-col overflow-y-auto px-2 pb-2">
        {BANDS.map((b) => {
          const status = area?.bands.find((x) => x.id === b.id);
          const on = bandsOn.includes(b.id);
          const noCoverage = status?.state === "no-coverage";
          const empty = status?.state === "ok" && status.empty && on;
          const lastOn = on && bandsOn.length === 1;
          const blocked = !on && !!bandBlocked[b.id];
          const expanded = open === b.id;
          // One line under the name: the most useful thing for this row right now.
          const sub = noCoverage && status.state === "no-coverage" ? status.reason : blocked ? 'Switch to this window' : empty ? EMPTY_BAND_NOTE : b.looksFor;
          return (
            <li key={b.id} className="flex flex-col">
              <div className="flex items-center rounded-lg transition-colors duration-(--dur-feedback) ease-standard hover:bg-raised">
                <button
                  type="button"
                  role="switch"
                  aria-checked={on}
                  disabled={noCoverage || (!area && !on) || lastOn}
                  title={lastOn ? "At least one has to stay on" : blocked ? 'Replaces the current windows because no observation contains both' : undefined}
                  onClick={() => toggleBand(b.id)}
                  className={cn("flex min-w-0 flex-1 cursor-pointer items-center gap-3 rounded-lg px-2.5 py-2 text-left disabled:cursor-not-allowed", noCoverage && "opacity-60")}
                >
                  <span
                    aria-hidden="true"
                    className={cn("size-4 shrink-0 rounded-full border-2", on ? "border-transparent" : "border-line-strong bg-transparent")}
                    style={on ? { backgroundColor: b.color } : undefined}
                  />
                  <span className="flex min-w-0 flex-col">
                    <span className={cn("flex min-w-0 items-center gap-2 text-body-sm", on ? "font-medium text-ink" : "text-ink-secondary")}>
                      <span className="truncate">{b.name}</span>
                      {area && <span className="shrink-0 font-mono text-caption tabular-nums text-ink-secondary"
                        title={`${bandCounts[b.id]?.selected ?? 0} observations match the selected bands and time range; ${bandCounts[b.id]?.total ?? 0} available in this area's sample`}
                        aria-label={`${bandCounts[b.id]?.selected ?? 0} selected of ${bandCounts[b.id]?.total ?? 0} available observations`}>
                        {bandCounts[b.id]?.selected ?? 0}/{bandCounts[b.id]?.total ?? 0}
                      </span>}
                    </span>
                    <span className="truncate text-caption text-ink-secondary">{sub}</span>
                  </span>
                </button>
                <button
                  type="button"
                  aria-label={`More about ${b.name}`}
                  aria-expanded={expanded}
                  onClick={() => setOpen(expanded ? null : b.id)}
                  className="mr-1 flex size-8 shrink-0 cursor-pointer items-center justify-center rounded-md text-ink-secondary transition-colors duration-(--dur-feedback) ease-standard hover:bg-overlay hover:text-ink"
                >
                  <Info size={16} strokeWidth={1.5} aria-hidden="true" />
                </button>
              </div>
              {expanded && (
                <div className="mx-2 mb-1 flex flex-col gap-1 rounded-md bg-ground px-3 py-2 text-small text-ink-secondary">
                  <p>
                    <span className="text-ink">Shows up in:</span> {b.whereItShows.toLowerCase()}
                  </p>
                  <p className="font-mono text-mono">
                    {b.realName}, {b.wavelength}
                  </p>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
