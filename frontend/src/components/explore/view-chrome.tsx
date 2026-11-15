"use client";

import { Database, Move, RefreshCw, SquareDashed } from "lucide-react";
import Link from "next/link";
import { exploreHref } from "@/lib/explore/href";
import { cn } from "@/lib/cn";
import { useExplore } from "./use-explore";

/** Move / Select box. Shift+drag also draws a box, from either mode. */
export function ViewControls() {
  const { mode, setMode, toolsEnabled } = useExplore();
  const options = [
    { value: "move", label: "Move", Icon: Move, hint: "Drag to move the view" },
    { value: "select", label: "Select box", Icon: SquareDashed, hint: "Drag to draw a box. Shift+drag does this from either mode." },
  ] as const;
  return (
    <div
      role="radiogroup"
      aria-label="What dragging does"
      className="absolute left-3 top-3 z-[5] flex gap-1 rounded-lg border border-line-strong bg-ground/90 p-1"
    >
      {options.map(({ value, label, Icon, hint }) => {
        const selected = mode === value;
        const disabled = value === "select" && !toolsEnabled;
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={selected}
            disabled={disabled}
            title={disabled ? "Available once the SPHEREx data has loaded" : hint}
            onClick={() => setMode(value)}
            className={cn(
              "flex h-9 cursor-pointer items-center gap-2 rounded-md px-3 text-small transition-colors duration-(--dur-feedback) ease-standard",
              "disabled:cursor-not-allowed disabled:opacity-50",
              selected ? "bg-overlay text-ink shadow-[inset_0_0_0_1px_var(--color-line-strong)]" : "text-ink-secondary hover:text-ink",
            )}
          >
            <Icon size={16} strokeWidth={1.5} aria-hidden="true" />
            {label}
          </button>
        );
      })}
    </div>
  );
}

/** Loading, error, and "range changed" notes at the top of the view. */
export function ViewStatus() {
  const { dataStatus, noData, retryData, outdated, motion, usingMock } = useExplore();
  return (
    <>
      <div className="pointer-events-none absolute inset-x-0 top-[68px] z-[5] flex flex-col items-center gap-2 px-4">
        {dataStatus === "loading" && (
          <p
            role="status"
            className="inline-flex items-center gap-2.5 rounded-lg border border-line-strong bg-ground/90 px-3 py-2 text-small text-ink"
          >
            <span aria-hidden="true" className="size-2 animate-pulse rounded-full bg-ink-secondary" />
            {usingMock ? "Loading simulated sky data…" : "Loading real SPHEREx data…"}
          </p>
        )}
        {noData && (
          <div
            role="status"
            className="pointer-events-auto flex max-w-[520px] flex-col gap-2 rounded-lg border border-line-strong bg-ground/90 px-4 py-3 text-small text-ink"
          >
            <p>{noData.message} The sky behind is a visible-light stand-in.</p>
            {noData.suggestion && (
              <Link
                href={exploreHref({ q: noData.suggestion.name, ra: noData.suggestion.ra, dec: noData.suggestion.dec, fov: noData.suggestion.fov })}
                className="w-fit rounded-xs underline underline-offset-4 hover:text-ink-secondary"
              >
                Try {noData.suggestion.name}, which has images
              </Link>
            )}
          </div>
        )}
        {dataStatus === "error" && !noData && (
          <p
            role="alert"
            className="pointer-events-auto inline-flex items-center gap-3 rounded-lg border border-line-strong bg-ground/90 py-1.5 pl-3 pr-1.5 text-small text-ink"
          >
            We couldn&apos;t load the SPHEREx data. The sky you see is a stand-in.
            <button
              type="button"
              onClick={retryData}
              className="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-md bg-primary px-3 text-small font-medium text-on-primary transition-colors duration-(--dur-feedback) ease-standard hover:bg-primary-hover"
            >
              <RefreshCw size={14} strokeWidth={1.5} aria-hidden="true" />
              Retry
            </button>
          </p>
        )}
        {outdated && motion.status === "done" && (
          <p className="inline-flex items-center gap-2 rounded-lg border border-line-strong bg-ground/90 px-3 py-2 text-small text-ink">
            Range changed, analyze again
          </p>
        )}
      </div>
      <p className="pointer-events-none absolute bottom-3 left-3 z-[5] inline-flex items-center gap-2 rounded-xs bg-scrim px-2 py-1 text-caption text-ink-secondary">
        <Database size={12} strokeWidth={1.5} aria-hidden="true" />
        {usingMock ? "Mock SPHEREx data" : "SPHEREx · NASA/JPL-Caltech, IRSA"}
      </p>
    </>
  );
}
