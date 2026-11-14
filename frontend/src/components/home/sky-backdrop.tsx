"use client";

import { MousePointerClick } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Reticle } from "@/components/ui";
import { cn } from "@/lib/cn";
import { exploreHref } from "@/lib/explore";
import { getObject } from "@/lib/sky/catalog";
import { formatCoords } from "@/lib/sky/format";

// Aladin Lite ships no TypeScript types; this is the slice of its API we use.
type AladinInstance = {
  getRaDec: () => [number, number];
  getFov: () => [number, number];
  gotoRaDec: (ra: number, dec: number) => void;
  setFoV: (fov: number) => void;
  zoomToFoV: (fov: number, seconds: number, done?: () => void) => void;
  stopAnimation: () => void;
  /** Internal, but the public getViewDataURL ignores its options. */
  view: { getCanvasDataURL: (format: string, w?: number, h?: number, logo?: boolean) => Promise<string> };
  on: (event: string, cb: (e: ClickEvent) => void) => void;
};
type ClickEvent = { ra: number; dec: number; isDragging?: boolean };
type AladinModule = {
  init: Promise<void>;
  aladin: (el: HTMLElement, options: Record<string, unknown>) => AladinInstance;
};

// DSS2 colour, from NASA/IPAC IRSA's HiPS mirror. This is visible light, not
// infrared: for a decorative backdrop it's the cleanest, prettiest all-sky
// survey (AllWISE and 2MASS show tile seams and saturated cores at these fields).
// Passing a URL skips Aladin's mirror auto-selection, which can stall on a dead
// CDS mirror. To go back to infrared, point this at .../CDS/AllWISE/RGB-W4-W2-W1.
const SURVEY = "https://irsa.ipac.caltech.edu/data/hips/CDS/DSS2/color";

// Where the tour goes, in order: objects that look spectacular in DSS2 at a
// wide field. Names and positions come from the catalogue, so the label is true.
const TOUR = [
  { id: "orion-nebula", fov: 5 },
  { id: "carina", fov: 4 },
  { id: "m31", fov: 5 },
  { id: "rosette", fov: 4 },
  { id: "eagle", fov: 2.5 },
  { id: "pleiades", fov: 3 },
].map((t) => {
  const o = getObject(t.id);
  return { id: o.id, name: o.name, ra: o.ra!, dec: o.dec!, fov: t.fov };
});
type Stop = (typeof TOUR)[number];

const DWELL_MS = 10_000; // how long each target stays on screen
const IDLE_RESUME_MS = 30_000; // after the user lets go of the map
const LOAD_MS = 2_800; // the old frame holds while the next target's tiles stream in
const DISSOLVE_MS = 1_400; // then the old frame dissolves into the new view
const PUSH_FROM = 1.25; // and the new view slowly pushes in from this much wider.

/**
 * The home screen's sky. Mostly decoration: it slowly flies between
 * spectacular patches of real sky, and stops the moment someone
 * touches it. Dragging and zooming work as you'd expect; a plain click or tap
 * opens that spot in exploration mode.
 */
export function SkyBackdrop({ className }: { className?: string }) {
  const router = useRouter();
  const containerRef = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState(false);
  const [stop, setStop] = useState<Stop>(TOUR[0]);
  const [labelVisible, setLabelVisible] = useState(true);
  // A frozen copy of the previous view, laid over the map while it jumps.
  const [ghost, setGhost] = useState<string | null>(null);
  const [ghostVisible, setGhostVisible] = useState(false);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let index = 0;
    let flight = 0; // bumped to cancel an in-progress flight
    let userHolding = false;
    let aladin: AladinInstance | null = null;
    const removeListeners: (() => void)[] = [];
    const listen = <K extends keyof HTMLElementEventMap>(
      type: K,
      fn: (e: HTMLElementEventMap[K]) => void,
    ) => {
      el.addEventListener(type, fn, { capture: true, passive: true });
      removeListeners.push(() => el.removeEventListener(type, fn, { capture: true }));
    };

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const schedule = (ms: number) => {
      clearTimeout(timer);
      timer = setTimeout(next, ms);
    };

    // Cross-fade to the next target. We deliberately don't fly across the sky:
    // that makes Aladin ask IRSA for hundreds of tiles at once, the server
    // resets the connections (ERR_HTTP2_PROTOCOL_ERROR), and Aladin never
    // retries, leaving permanent blocky holes. Instead: freeze the current
    // frame as an overlay, jump underneath it (one patch of tiles, tops), let
    // those load, then dissolve the old frame away. Never black, never blocky.
    const next = async () => {
      if (cancelled || !aladin) return;
      if (userHolding || document.hidden) return schedule(2_000);

      index = (index + 1) % TOUR.length;
      const target = TOUR[index];
      const id = ++flight;
      const live = () => !cancelled && id === flight;
      const a = aladin;

      setLabelVisible(false);
      try {
        const frame = await a.view.getCanvasDataURL("image/jpeg", undefined, undefined, false);
        if (!live()) return;
        setGhost(frame);
        setGhostVisible(true);
      } catch {
        // No snapshot: the jump just happens, which is still fine.
      }

      a.gotoRaDec(target.ra, target.dec);
      a.setFoV(target.fov * PUSH_FROM);
      setStop(target);

      timer = setTimeout(() => {
        if (!live()) return;
        setGhostVisible(false);
        a.zoomToFoV(target.fov, DWELL_MS / 1000);
        timer = setTimeout(() => live() && setLabelVisible(true), DISSOLVE_MS - 400);
        timer = setTimeout(() => live() && setGhost(null), DISSOLVE_MS + 100);
        timer = setTimeout(() => live() && next(), DWELL_MS);
      }, LOAD_MS);
    };

    // Someone took the controls: stop flying and hide the (now stale) label.
    const takeOver = () => {
      userHolding = true;
      flight++;
      aladin?.stopAnimation();
      clearTimeout(timer);
      setGhostVisible(false);
      setLabelVisible(false);
    };
    // They let go: wait a while, then carry on touring from wherever they are.
    const release = () => {
      userHolding = false;
      if (!reduceMotion) schedule(IDLE_RESUME_MS);
    };

    (async () => {
      try {
        // Importing aladin-lite touches WebGL/WASM at module load, so it can
        // only happen in the browser.
        const A = (await import("aladin-lite")).default as AladinModule;
        await A.init;
        if (cancelled) return;

        const first = TOUR[0];
        aladin = A.aladin(el, {
          survey: SURVEY,
          target: `${first.ra} ${first.dec}`,
          fov: first.fov,
          projection: "SIN",
          cooFrame: "ICRS",
          backgroundColor: "rgb(5, 6, 8)", // sky
          // We draw the Pulsr reticle ourselves. All of Aladin's own controls
          // are off; its logo stays (terms of use).
          showReticle: false,
          showZoomControl: false,
          showLayersControl: false,
          showFullscreenControl: false,
          showGotoControl: false,
          showProjectionControl: false,
          showFrame: false,
          showFov: false,
          showCooLocation: false,
          showStatusBar: false,
          showContextMenu: false,
          showSimbadPointerControl: false,
          showCooGridControl: false,
          showSettingsControl: false,
          showShareControl: false,
          // Skip Aladin's startup usage ping to CDS (sends our page URL).
          log: false,
        });

        // A click that isn't the end of a drag opens exploration mode there.
        aladin.on("click", (e) => {
          if (e.isDragging) return;
          router.push(exploreHref({ ra: e.ra, dec: e.dec, fov: aladin!.getFov()[0] }));
        });

        listen("pointerdown", takeOver);
        listen("wheel", takeOver);
        listen("pointerup", release);
        listen("pointercancel", release);
        // Wheel has no "up": treat a pause in scrolling as letting go.
        let wheelTimer: ReturnType<typeof setTimeout> | undefined;
        listen("wheel", () => {
          clearTimeout(wheelTimer);
          wheelTimer = setTimeout(release, 600);
        });
        removeListeners.push(() => clearTimeout(wheelTimer));

        // Let the first tiles stream in before revealing, so the opening frame
        // isn't a blocky low-resolution preview.
        timer = setTimeout(() => {
          if (cancelled) return;
          setReady(true);
          if (!reduceMotion) schedule(DWELL_MS);
        }, LOAD_MS);
      } catch {
        if (!cancelled) setError(true);
      }
    })();

    return () => {
      cancelled = true;
      clearTimeout(timer);
      removeListeners.forEach((off) => off());
      aladin?.stopAnimation();
      aladin = null;
      el.replaceChildren();
    };
    // Runs once: the tour reads everything it needs from module constants.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className={cn("overflow-hidden bg-sky", className)}>
      <div
        ref={containerRef}
        className={cn(
          "absolute inset-0 cursor-crosshair transition-opacity duration-1000 ease-standard",
          ready ? "opacity-100" : "opacity-0",
        )}
      />
      {ghost && (
        // eslint-disable-next-line @next/next/no-img-element -- a one-off canvas snapshot
        <img
          src={ghost}
          alt=""
          aria-hidden="true"
          className={cn(
            "pointer-events-none absolute inset-0 size-full ease-standard",
            ghostVisible
              ? "opacity-100"
              : "opacity-0 transition-opacity duration-[1400ms]",
          )}
        />
      )}

      {/* Ground-to-transparent scrim so the header stays readable over bright
          sky. The one gradient Pulsr allows. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-28 bg-linear-to-b from-ground/90 to-transparent"
      />

      {ready && (
        <>
          {/* The reticle sits on the centre of the stage, which is the middle
              of the free part of the screen, not under the feed. */}
          <div className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
            <Reticle
              size={56}
              name={stop.name}
              coords={formatCoords(stop.ra, stop.dec)}
              labelVisible={labelVisible}
              labelBelowOnPhones
            />
          </div>
        </>
      )}

      {!ready && !error && (
        <p className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 text-small text-ink-secondary">
          Loading the sky
        </p>
      )}
      {error && (
        <p className="absolute left-1/2 top-1/2 max-w-xs -translate-x-1/2 -translate-y-1/2 px-6 text-center text-body-sm text-ink-secondary">
          This browser can&apos;t draw the sky map. It needs WebGL2, which most up-to-date
          browsers have. The feed still works.
        </p>
      )}
    </div>
  );
}

/** The hint under the map. Separate so it can sit in the free part of the screen. */
export function SkyHint({ className }: { className?: string }) {
  return (
    <p
      className={cn(
        "pointer-events-none inline-flex items-center gap-2 rounded-md bg-scrim px-3 py-2 text-small text-ink-secondary",
        className,
      )}
    >
      <MousePointerClick size={16} strokeWidth={1.5} aria-hidden="true" />
      Click or tap the sky to explore it
    </p>
  );
}
