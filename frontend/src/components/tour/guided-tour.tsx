"use client";

import { ArrowLeft, ArrowRight, Play, RotateCcw, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import { STEPS } from "./steps";
import { markSeen, tour, useTourSeen, useTourStep } from "./tour-store";

type Rect = { x: number; y: number; w: number; h: number };

/**
 * The guided demo. A small card walks someone through the app, a pulsing ring
 * points at what to click, and the card moves on by itself when they do it.
 * Desktop only: the explorer it walks through needs room.
 */
export function GuidedTour() {
  const step = useTourStep();
  const seen = useTourSeen();
  const pathname = usePathname();
  if (step === null) {
    // First visit to the home page: a quiet invitation, never a modal.
    return pathname === "/" && !seen ? <Invite /> : null;
  }
  return <Running index={Math.min(step, STEPS.length - 1)} pathname={pathname} />;
}

function Invite() {
  return (
    <div className="fixed left-10 top-[96px] z-20 hidden w-[300px] flex-col gap-3 rounded-xl border border-line-strong bg-surface p-4 shadow-xl lg:flex" role="region" aria-label="Guided demo invitation">
      <p className="text-body-sm font-medium text-ink">New here?</p>
      <p className="text-small text-ink-secondary">Take the two-minute guided demo: it shows you exactly what to click.</p>
      <div className="flex items-center gap-2">
        <button type="button" onClick={tour.start} className="inline-flex h-10 items-center gap-2 rounded-md bg-primary px-4 text-small font-medium text-on-primary">
          <Play size={14} strokeWidth={1.75} aria-hidden="true" /> Start the demo
        </button>
        <button type="button" onClick={markSeen} className="h-10 rounded-md px-3 text-small text-ink-secondary hover:text-ink">
          Not now
        </button>
      </div>
    </div>
  );
}

function Running({ index, pathname }: { index: number; pathname: string }) {
  const step = STEPS[index];
  const onPage = step.path.test(pathname);
  const last = index === STEPS.length - 1;
  // If they wandered ahead (e.g. clicked a link early), offer to pick the demo up from here.
  const later = onPage ? -1 : STEPS.findIndex((x, i) => i > index && x.path.test(pathname));
  const [rect, setRect] = useState<Rect | null>(null);
  const [missing, setMissing] = useState(false);
  const advanced = useRef(-1);
  const unmetSince = useRef<number | null>(null);

  // Watch the page: find the target, notice when the step is done. The "done" check also
  // runs on other pages (a step is often finished by navigating away from its page).
  useEffect(() => {
    const tick = () => {
      if (onPage) {
        const needed = step.requires ? step.requires() : true;
        if (needed) unmetSince.current = null;
        else unmetSince.current ??= Date.now();
        // Give the page a moment to mount before saying something is missing.
        setMissing(!needed && Date.now() - (unmetSince.current ?? Date.now()) > 1800);

        const el = needed ? (step.target?.() ?? null) : null;
        const r = el?.getBoundingClientRect();
        if (r && r.width > 0 && r.height > 0)
          setRect((p) => (p && p.x === r.left && p.y === r.top && p.w === r.width && p.h === r.height ? p : { x: r.left, y: r.top, w: r.width, h: r.height }));
        else setRect(null);
      }
      if (step.done && advanced.current !== index && step.done()) {
        advanced.current = index;
        // A beat, so the visitor sees their click land before the card changes.
        setTimeout(() => tour.go(Math.min(index + 1, STEPS.length - 1)), 650);
      }
    };
    tick();
    const timer = setInterval(tick, 250);
    return () => clearInterval(timer);
  }, [onPage, step, index]);

  const onExplore = pathname.startsWith("/explore");
  const place = onExplore ? "left-4 top-[84px] w-[272px]" : "bottom-6 left-6 w-[320px]";

  return (
    <>
      {onPage && rect && !missing && <Ring rect={rect} />}
      <div
        role="dialog"
        aria-label="Guided demo"
        className={cn("fixed z-50 hidden flex-col gap-3 rounded-xl border border-line-strong bg-surface p-4 shadow-xl lg:flex", place)}
      >
        <div className="flex items-center justify-between gap-2">
          <p className="font-mono text-mono-sm uppercase tracking-widest text-ink-secondary">
            Guided demo · {index + 1}/{STEPS.length}
          </p>
          <button type="button" aria-label="Close the guided demo" onClick={tour.stop} className="-mr-1 inline-flex size-7 items-center justify-center rounded-md text-ink-secondary hover:bg-raised hover:text-ink">
            <X size={16} strokeWidth={1.5} aria-hidden="true" />
          </button>
        </div>
        <div className="h-1 overflow-hidden rounded-full bg-raised" aria-hidden="true">
          <div className="h-full rounded-full bg-primary transition-[width] duration-300" style={{ width: `${((index + 1) / STEPS.length) * 100}%` }} />
        </div>

        {!onPage ? (
          <>
            <p className="text-body-sm text-ink">
              {later >= 0 ? "You’ve moved ahead of the demo." : "Continue the demo: this step is on a different page."}
            </p>
            {later >= 0 ? (
              <button type="button" onClick={() => tour.go(later)} className="inline-flex h-10 w-fit items-center rounded-md bg-primary px-4 text-small font-medium text-on-primary">
                Continue from here
              </button>
            ) : (
              <Link href={fallbackFor(index)} className="inline-flex h-10 w-fit items-center rounded-md bg-primary px-4 text-small font-medium text-on-primary">
                Take me there
              </Link>
            )}
          </>
        ) : missing ? (
          <>
            <p className="text-body-sm text-ink">This step needs the Barnard’s Star region.</p>
            <Link href={step.fallbackHref ?? "/"} className="inline-flex h-10 w-fit items-center rounded-md bg-primary px-4 text-small font-medium text-on-primary">
              {step.fallbackLabel ?? "Open it"}
            </Link>
          </>
        ) : (
          <>
            <h2 className="text-body font-medium text-ink">{step.title}</h2>
            <p className="text-small leading-relaxed text-ink-secondary">{step.text}</p>
            {step.action && (
              <p className="rounded-md border border-ember bg-ember-wash px-3 py-2 text-small font-medium text-ink">{step.action}</p>
            )}
          </>
        )}

        <div className="flex items-center justify-between gap-2 pt-1">
          <button type="button" disabled={index === 0} onClick={() => tour.go(index - 1)} className="inline-flex h-9 items-center gap-1.5 rounded-md px-2 text-small text-ink-secondary hover:text-ink disabled:opacity-40">
            <ArrowLeft size={14} strokeWidth={1.5} aria-hidden="true" /> Back
          </button>
          {last ? (
            <div className="flex gap-2">
              <button type="button" onClick={() => tour.go(0)} className="inline-flex h-9 items-center gap-1.5 rounded-md px-3 text-small text-ink-secondary hover:text-ink">
                <RotateCcw size={14} strokeWidth={1.5} aria-hidden="true" /> Again
              </button>
              <button type="button" onClick={tour.stop} className="inline-flex h-9 items-center rounded-md bg-primary px-4 text-small font-medium text-on-primary">
                Finish
              </button>
            </div>
          ) : (
            <button type="button" onClick={() => tour.go(index + 1)} className={cn("inline-flex h-9 items-center gap-1.5 rounded-md px-3 text-small font-medium", step.done ? "text-ink-secondary hover:text-ink" : "bg-primary text-on-primary")}>
              {step.done ? "Skip this step" : index === 0 ? "Let’s go" : "Next"} <ArrowRight size={14} strokeWidth={1.5} aria-hidden="true" />
            </button>
          )}
        </div>
      </div>
    </>
  );
}

/** The route a step belongs on, for someone who wandered off. */
function fallbackFor(index: number) {
  const id = STEPS[index].id;
  if (STEPS[index].path.source.includes("share")) return "/explore";
  if (id === "end") return "/discussions";
  if (STEPS[index].path.test("/")) return "/";
  if (STEPS[index].path.source.includes("findings")) return "/discussions";
  return STEPS[index].fallbackHref ?? "/explore?q=Barnard%27s%20Star&ra=269.4463&dec=4.7682&fov=0.2";
}

function Ring({ rect }: { rect: Rect }) {
  const pad = 6;
  return (
    <div
      aria-hidden="true"
      className="tour-ring pointer-events-none fixed z-40 rounded-lg border-2 border-ember"
      style={{ left: rect.x - pad, top: rect.y - pad, width: rect.w + pad * 2, height: rect.h + pad * 2 }}
    />
  );
}
