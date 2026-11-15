"use client";

import { LoaderCircle, MousePointerClick } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Reticle } from "@/components/ui";
import { cn } from "@/lib/cn";
import { loadAladin, type AladinInstance } from "@/lib/sky/aladin";
import { exploreHref } from "@/lib/explore/href";
import { getObject } from "@/lib/sky/catalog";
import { formatCoords } from "@/lib/sky/format";

// DSS2 colour, from NASA/IPAC IRSA's HiPS mirror. This is visible light, not
// infrared: for a decorative backdrop it's the cleanest, prettiest all-sky
// survey (AllWISE and 2MASS show tile seams and saturated cores at these fields).
// Passing a URL skips Aladin's mirror auto-selection, which can stall on a dead
// CDS mirror. To go back to infrared, point this at .../CDS/AllWISE/RGB-W4-W2-W1.
const SURVEY = "https://irsa.ipac.caltech.edu/data/hips/CDS/DSS2/color";

// Where the tour goes, in order: objects that look spectacular in DSS2 at a
// wide field. Names and positions come from the catalogue, so the label is true.
// Demo build: open on something spectacular, then settle on Barnard's Star, the
// one place the Explore page has prefetched SPHEREx data for (public/demo).
// The tour stops at the last entry; add stops before it to make the intro longer.
const TOUR = [
  { id: "orion-nebula", fov: 5 },
  { id: "barnard", fov: 0.5 },
].map((t) => {
  const o = getObject(t.id);
  return { id: o.id, name: o.name, ra: o.ra!, dec: o.dec!, fov: t.fov };
});
type Stop = (typeof TOUR)[number];
type SavedView = { ra: number; dec: number; fov: number; tourIndex: number };
type Selection = { ra: number; dec: number; fov: number; left: number; top: number };

const DWELL_MS = 10_000; // how long each target stays on screen
const IDLE_RESUME_MS = 30_000; // after the user lets go of the map
const LOAD_MS = 2_800; // the old frame holds while the next target's tiles stream in
const DISSOLVE_MS = 1_400; // then the old frame dissolves into the new view
const PUSH_FROM = 1.25; // and the new view slowly pushes in from this much wider.

/**
 * The home screen's sky. Mostly decoration: it slowly flies between
 * spectacular patches of real sky, and stops the moment someone
 * touches it. Dragging and zooming work as you'd expect; a plain click or tap
 * asks before opening that spot in exploration mode.
 */
export function SkyBackdrop({ className }: { className?: string }) {
  const router = useRouter();
  const containerRef = useRef<HTMLDivElement>(null);
  const savedView = useRef<SavedView | null>(null);
  const popupRef = useRef<HTMLDivElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const confirming = useRef(false);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  const [stop, setStop] = useState<Stop>(TOUR[0]);
  const [labelVisible, setLabelVisible] = useState(true);
  // A frozen copy of the previous view, laid over the map while it jumps.
  const [ghost, setGhost] = useState<string | null>(null);
  const [ghostVisible, setGhostVisible] = useState(false);

  const dismissSelection = useCallback((restoreFocus = true) => {
    confirming.current = false;
    setSelection(null);
    if (restoreFocus) containerRef.current?.focus({ preventScroll: true });
  }, []);

  useEffect(() => {
    if (!selection) return;
    confirmRef.current?.focus({ preventScroll: true });
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        dismissSelection();
      }
    };
    const onOutside = (event: PointerEvent) => {
      if (event.target instanceof Node && !popupRef.current?.contains(event.target)) dismissSelection(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onOutside, true);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onOutside, true);
    };
  }, [selection, dismissSelection]);

  useEffect(() => {
    const host = containerRef.current;
    if (!host) return;
    const previousView = savedView.current;
    confirming.current = false;
    setSelection(null);
    // Activity preserves React's DOM and state while restarting Effects. Aladin
    // mutates its mount's classes/styles, so give each instance a fresh mount.
    const el = document.createElement("div");
    Object.assign(el.style, { position: "absolute", inset: "0", width: "100%", height: "100%" });
    host.appendChild(el);
    setReady(false);
    setError(false);
    setGhost(null);
    setGhostVisible(false);
    setStop(TOUR[previousView?.tourIndex ?? 0]);
    // A restored camera may have been panned away from the named tour target.
    setLabelVisible(!previousView);
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const pendingTimers = new Set<ReturnType<typeof setTimeout>>();
    const later = (callback: () => void, ms: number) => {
      const id = setTimeout(() => {
        pendingTimers.delete(id);
        if (!cancelled) callback();
      }, ms);
      pendingTimers.add(id);
      return id;
    };
    let index = previousView?.tourIndex ?? 0;
    let flight = 0; // bumped to cancel an in-progress flight
    let userHolding = false;
    let pointer = { x: 0, y: 0 };
    let aladin: AladinInstance | null = null;
    const rememberView = () => {
      if (!aladin) return;
      aladin.stopAnimation();
      const [ra, dec] = aladin.getRaDec();
      const [fov] = aladin.getFov();
      if (Number.isFinite(ra) && Number.isFinite(dec) && Number.isFinite(fov) && fov > 0) {
        savedView.current = { ra, dec, fov, tourIndex: index };
      }
    };
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
      timer = later(next, ms);
    };

    // Cross-fade to the next target. We deliberately don't fly across the sky:
    // that makes Aladin ask IRSA for hundreds of tiles at once, the server
    // resets the connections (ERR_HTTP2_PROTOCOL_ERROR), and Aladin never
    // retries, leaving permanent blocky holes. Instead: freeze the current
    // frame as an overlay, jump underneath it (one patch of tiles, tops), let
    // those load, then dissolve the old frame away. Never black, never blocky.
    const next = async () => {
      if (cancelled || !aladin || index >= TOUR.length - 1) return; // rests on the last stop
      if (confirming.current || userHolding || document.hidden) return schedule(2_000);

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
      if (!live()) return;

      a.gotoRaDec(target.ra, target.dec);
      a.setFoV(target.fov * PUSH_FROM);
      setStop(target);

      timer = later(() => {
        if (!live()) return;
        setGhostVisible(false);
        a.zoomToFoV(target.fov, DWELL_MS / 1000);
        later(() => { if (live()) setLabelVisible(true); }, DISSOLVE_MS - 400);
        later(() => { if (live()) setGhost(null); }, DISSOLVE_MS + 100);
        timer = later(() => { if (live()) void next(); }, DWELL_MS);
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
        const A = await loadAladin();
        if (cancelled) return;

        const first = previousView ?? TOUR[0];
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
        if (previousView) {
          aladin.gotoRaDec(previousView.ra, previousView.dec);
          aladin.setFoV(previousView.fov);
        }

        // Freeze the camera and ask before leaving the sky.
        aladin.on("click", (e) => {
          if (cancelled || e.isDragging || !Number.isFinite(e.ra) || !Number.isFinite(e.dec)) return;
          rememberView();
          const bounds = host.getBoundingClientRect();
          confirming.current = true;
          setSelection({ ra: e.ra, dec: e.dec, fov: aladin!.getFov()[0],
            left: Math.max(12, Math.min(pointer.x - bounds.left + 12, bounds.width - 292)),
            top: Math.max(12, Math.min(pointer.y - bounds.top + 12, bounds.height - 208)),
          });
        });

        listen("pointerdown", (event) => {
          pointer = { x: event.clientX, y: event.clientY };
          takeOver();
        });
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
        timer = later(() => {
          if (cancelled) return;
          setReady(true);
          if (!reduceMotion) schedule(previousView ? IDLE_RESUME_MS : DWELL_MS);
        }, LOAD_MS);
      } catch {
        if (!cancelled) setError(true);
      }
    })();

    return () => {
      cancelled = true;
      flight++;
      clearTimeout(timer);
      pendingTimers.forEach(clearTimeout);
      removeListeners.forEach((off) => off());
      rememberView();
      aladin = null;
      el.remove();
    };
  }, [retry, router]);

  return (
    <div className={cn("overflow-hidden bg-sky", className)}>
      <div
        ref={containerRef}
        style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
        aria-label="Aladin sky viewer"
        tabIndex={0}
        aria-busy={!ready && !error}
        className={cn(
          "absolute inset-0 cursor-crosshair transition-opacity duration-1000 ease-standard",
          ready ? "opacity-100" : "opacity-0",
        )}
      />
      {selection && <div ref={popupRef} role="dialog" aria-label="Explore this sky position" className="absolute z-20 w-[280px] max-w-[calc(100%-24px)] rounded-lg border border-line-strong bg-surface p-4" style={{ left: selection.left, top: selection.top }}>
        <p className="text-body-sm font-medium text-ink">Explore this spot?</p>
        <p className="mt-1 text-caption text-ink-secondary">Open the observation view at these coordinates.</p>
        <p className="mt-3 font-mono text-mono-sm tabular-nums text-ink-secondary">RA {selection.ra.toFixed(5)}° · Dec {selection.dec.toFixed(5)}°</p>
        <div className="mt-4 flex justify-end gap-2">
          <button type="button" onClick={() => dismissSelection()} className="min-h-9 cursor-pointer rounded-md border border-line-strong px-3 text-small text-ink-secondary hover:bg-raised">Cancel</button>
          <button ref={confirmRef} type="button" onClick={() => {
            const target = selection;
            dismissSelection(false);
            router.push(exploreHref(target));
          }} className="min-h-9 cursor-pointer rounded-md bg-primary px-3 text-small font-medium text-on-primary hover:bg-primary-hover">Go there</button>
        </div>
      </div>}
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


      {ready && (
        <>
          {/* The reticle sits on the centre of the sky window. */}
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
        <p role="status" className="pointer-events-none absolute left-1/2 top-1/2 flex -translate-x-1/2 -translate-y-1/2 items-center gap-2 rounded-md bg-scrim px-3 py-2 text-small text-ink-secondary">
          <LoaderCircle size={16} className="animate-spin" aria-hidden="true" /> Loading Aladin sky viewer…
        </p>
      )}
      {ready && !error && <p role="status" className="pointer-events-none absolute bottom-4 right-4 rounded-md bg-scrim px-2 py-1 text-caption text-ink-secondary">Aladin ready · DSS2 tiles stream online</p>}
      {error && (
        <div role="alert" className="absolute left-1/2 top-1/2 w-full max-w-xs -translate-x-1/2 -translate-y-1/2 rounded-lg border border-line-strong bg-surface p-6 text-center text-body-sm text-ink-secondary">
          <p>Aladin couldn&apos;t load. The sky viewer needs WebGL2 and internet access. The feed still works.</p>
          <button type="button" onClick={() => setRetry((value) => value + 1)} className="mt-3 cursor-pointer rounded-md border border-line-strong bg-raised px-3 py-2 text-small text-ink hover:bg-overlay">Retry sky viewer</button>
        </div>
      )}
    </div>
  );
}

/** The hint under the map. Separate so it can sit in the free part of the screen. */
export function SkyHint({ className }: { className?: string }) {
  return (
    <p
      className={cn(
        "pointer-events-none inline-flex items-center gap-2 rounded-md border border-line-strong bg-ground/90 px-3 py-2 text-small text-ink-secondary",
        className,
      )}
    >
      <MousePointerClick size={16} strokeWidth={1.5} aria-hidden="true" />
      Click or tap the sky to choose a spot
    </p>
  );
}
