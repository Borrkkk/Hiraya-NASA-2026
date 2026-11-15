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
        <p className="text-ink-secondary">Looking for anything that moved between observations. This takes a moment.</p>
      </Notice>
    );
  if (motion.status === "failed")
    return (
      <Notice tone="error">
        <p>We couldn&apos;t finish looking for movement. Nothing was changed.</p>
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
  if (motion.status === "done" && motion.result.movers.length === 0)
    return (
      <Notice>
        <p className="text-body-sm font-medium">No movement found in this period</p>
        <p className="text-ink-secondary">Try a longer range, or switch on other bands.</p>
      </Notice>
    );
  return null;
}
