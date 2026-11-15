"use client";

import { ArrowLeft, Loader2, Share2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { Verdict } from "@/components/ui";
import { getBand } from "@/lib/explore/bands";
import { TYPE_LABELS } from "@/lib/explore/labels";
import { Notice, buttonPrimary, buttonSecondary } from "./panel-parts";
import { SpectrumChart } from "./spectrum-chart";
import { useExplore } from "./use-explore";

/** Replaces the sidebar while Verify runs and shows what it found. */
export function VerifyPanel() {
  const ex = useRouterExplore();
  const { verifyState: v } = ex.ex;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="flex h-14 shrink-0 items-center border-b border-line px-2">
        <button
          type="button"
          onClick={ex.ex.closeVerify}
          className="inline-flex h-10 cursor-pointer items-center gap-2 rounded-md px-3 text-small text-ink-secondary transition-colors duration-(--dur-feedback) ease-standard hover:bg-raised hover:text-ink"
        >
          <ArrowLeft size={16} strokeWidth={1.5} aria-hidden="true" />
          Back
        </button>
        <p className="ml-1 text-body-sm font-medium text-ink">Is it already known?</p>
      </header>

      <div className="scroll-pulsr flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto p-4">
        {v.status === "running" && (
          <div className="flex flex-col gap-4" aria-busy="true">
            <p role="status" className="flex items-center gap-2.5 text-body-sm text-ink">
              <Loader2 size={16} strokeWidth={1.5} className="animate-spin" aria-hidden="true" />
              {v.step}
            </p>
            <p className="text-small text-ink-secondary">
              We compare your selection with known stars, asteroids, catalogs and instrument problems.
            </p>
          </div>
        )}

        {v.status === "failed" && (
          <Notice tone="error">
            <p>We couldn&apos;t finish the check. Nothing was changed.</p>
            <button type="button" className={buttonSecondary + " w-fit"} onClick={ex.ex.verify}>
              Retry
            </button>
          </Notice>
        )}

        {v.status === "done" && v.result.outcome === "explained" && (
          <>
            <Outcome kind="explained" headline={v.result.headline} />
            <div className="flex flex-col gap-1 rounded-lg bg-raised p-4">
              <p className="text-h3 text-ink">{v.result.name}</p>
              <p className="text-body-sm text-ink-secondary">{v.result.fact}</p>
              <p className="text-small text-ink-secondary">Matched in {v.result.source}</p>
            </div>
            <p className="text-small text-ink">
              {v.points > 0 ? `+${v.points} points, counted as a ${TYPE_LABELS[v.result.objectType].toLowerCase()}.` : "No points for this one."}
            </p>
          </>
        )}

        {v.status === "done" && v.result.outcome === "artifact" && (
          <>
            <Outcome kind="artifact" headline={v.result.headline} />
            <div className="flex flex-col gap-1 rounded-lg bg-raised p-4">
              <p className="text-body-sm text-ink">{v.result.reason}</p>
              <p className="text-small text-ink-secondary">{v.result.flag}</p>
            </div>
            <p className="text-small text-ink-secondary">No points for this one.</p>
          </>
        )}

        {v.status === "done" && v.result.outcome === "unexplained" && (
          <>
            <Outcome kind="unexplained" headline={v.result.headline} />
            <p className="text-body-sm text-ink-secondary">
              Our checks found no match. That is not a discovery: it only means these sources don&apos;t list it. Someone may still know what it is.
            </p>
            {v.result.nearMatch && (
              <div className="flex flex-col gap-1 rounded-lg bg-raised p-4">
                <p className="text-small text-ink-secondary">Closest match, but it doesn&apos;t fit</p>
                <p className="text-body-sm text-ink">{v.result.nearMatch.name}</p>
                <p className="text-small text-ink-secondary">
                  {v.result.nearMatch.source}. {v.result.nearMatch.note}
                </p>
              </div>
            )}
            <div className="flex flex-col gap-3">
              <p className="text-body-sm font-medium text-ink">What we collected</p>
              <dl className="grid grid-cols-[88px_1fr] gap-x-4 gap-y-2 text-small">
                <dt className="text-ink-secondary">Bands</dt>
                <dd className="text-ink">{ex.ex.bandsOn.map((b) => getBand(b).name).join(", ")}</dd>
                <dt className="text-ink-secondary">Epochs</dt>
                <dd className="text-ink">
                  {ex.ex.rangeEpochCount} {ex.ex.rangeEpochCount === 1 ? "observation" : "observations"} in range
                </dd>
                {ex.ex.selectedMover && (
                  <>
                    <dt className="text-ink-secondary">Track</dt>
                    <dd className="text-ink">
                      Mover {ex.ex.selectedMover.number}, seen in {ex.ex.selectedMover.points.length} observations
                    </dd>
                  </>
                )}
              </dl>
              {ex.ex.inspectQuery.data && !ex.ex.inspectQuery.data.lowSignal && (
                <SpectrumChart spectrum={ex.ex.inspectQuery.data.spectrum} compact />
              )}
            </div>
          </>
        )}
      </div>

      {v.status === "done" && v.result.outcome === "unexplained" && (
        <footer className="flex shrink-0 gap-2 border-t border-line p-4">
          <button type="button" className={buttonSecondary + " flex-1"} onClick={ex.ex.closeVerify}>
            Back
          </button>
          <button
            type="button"
            className={buttonPrimary + " flex-1"}
            onClick={() => {
              const href = ex.ex.share(ex.ex.inspectQuery.data?.spectrum ?? null);
              if (href) ex.router.push(href);
            }}
          >
            <Share2 size={16} strokeWidth={1.5} aria-hidden="true" />
            Discuss suspected motion
          </button>
        </footer>
      )}
    </div>
  );
}

function Outcome({ kind, headline }: { kind: "explained" | "artifact" | "unexplained"; headline: string }) {
  return (
    <div className="flex flex-col gap-2">
      <Verdict kind={kind} />
      <h2 className="text-h2 text-ink">{headline}</h2>
    </div>
  );
}

function useRouterExplore() {
  return { ex: useExplore(), router: useRouter() };
}
