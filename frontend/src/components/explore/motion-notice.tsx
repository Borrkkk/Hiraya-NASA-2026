"use client";

import { Loader2 } from "lucide-react";
import { Notice, buttonPrimary, buttonSecondary } from "./panel-parts";
import { cn } from "@/lib/cn";
import { useExplore } from "./use-explore";

/**
 * The states of motion analysis that aren't a result: running, failed,
 * nothing found, and out of date. Results themselves live in the motion panel.
 */
export function MotionNotice() {
  const ex = useExplore();
  const { motion } = ex;

  if (motion.status === "running")
    return (
      <Notice>
        <p className="flex items-center gap-2.5 text-ink" role="status">
          <Loader2 size={16} strokeWidth={1.5} className="animate-spin" aria-hidden="true" />
          {motion.step}
        </p>
        <p className="text-ink-secondary">Screening comparable observations for possible motion. Candidate paths need independent verification.</p>
      </Notice>
    );
  if (motion.status === "failed")
    return (
      <Notice tone="error">
        <p>We couldn&apos;t finish looking for movement. Nothing was changed.</p>
        <p className="text-ink-secondary">{motion.error}</p>
        <button type="button" className={cn(buttonSecondary, "w-fit")} onClick={ex.analyze}>
          Retry
        </button>
      </Notice>
    );
  if (motion.status === "done" && ex.outdated)
    return (
      <Notice>
        <p>Range changed, analyze again.</p>
        <p className="text-ink-secondary">The tracks on the image are from the earlier range.</p>
        <button type="button" className={cn(buttonPrimary, "w-fit")} onClick={ex.analyze} disabled={ex.rangeEpochCount < 2}>
          Analyze motion
        </button>
      </Notice>
    );
  if (motion.status === "done" && motion.result.movers.length === 0) {
    const diagnostics = motion.result.diagnostics;
    const explanation = diagnostics?.reason === "insufficient_comparable_observations"
      ? `Only ${diagnostics.comparableObservations} of the available observations can be compared (same detector and nearly the same wavelength). At least ${diagnostics.requiredObservations} are required. Switching to a longer date range or another band might help.`
      : diagnostics?.reason === "no_sources_detected"
        ? `The ${diagnostics.comparableObservations} comparable images had no bright enough sources to track. Try another sky area or band.`
        : diagnostics?.reason === "no_consistent_tracks"
          ? `Checked ${diagnostics.detectedSources} source detections across ${diagnostics.comparableObservations} comparable images, but none showed steady enough motion. This is a valid result, not an error.`
          : "At least three comparable observations are needed. Try a longer date range or a different band.";
    return (
      <Notice>
        <p className="text-body-sm font-medium">No reliable motion candidates in this period</p>
        <p className="text-ink-secondary">{explanation}</p>
      </Notice>
    );
  }
  return null;
}
