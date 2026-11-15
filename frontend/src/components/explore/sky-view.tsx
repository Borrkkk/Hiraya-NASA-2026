"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import { BANDS } from "@/lib/explore/bands";
import {
  clamp,
  frameTransform,
  makeProjection,
  type Projection,
  type View,
} from "@/lib/explore/projection";
import { useStore } from "@/lib/explore/store";
import type { BandId, SkyBox } from "@/lib/explore/types";
import { BARE_ALADIN_OPTIONS, loadAladin, type AladinInstance } from "@/lib/sky/aladin";
import { Curtain } from "./curtain";
import { LayerPicker } from "./layer-picker";
import { MotionOverlay } from "./motion-overlay";
import { SelectionBox } from "./selection-box";
import { ViewControls, ViewStatus } from "./view-chrome";
import { useExplore } from "./use-explore";
import { ObjectMarkers } from './object-markers';

const R2D = 180 / Math.PI;

// The placeholder under the SPHEREx image: DSS2 colour from IRSA's HiPS mirror.
const PLACEHOLDER = "https://irsa.ipac.caltech.edu/data/hips/CDS/DSS2/color";

type Drag =
  | { kind: "pan"; x: number; y: number; proj: Projection; view: View; moved: boolean }
  | { kind: "box"; x: number; y: number; moved: boolean };

/**
 * The one sky image. Layers, bottom to top:
 *   1. Aladin Lite: the instant cutout, and the other sensor behind the curtain
 *   2. SPHEREx frames, blended on a canvas (clipped by the curtain)
 *   3. pointer layer: pan, wheel zoom, drag-a-box
 *   4. overlays: selection box, tracks, marker (never clipped)
 *   5. controls
 *
 * We own the view (centre and field of view) and push it into Aladin each
 * frame, rather than letting Aladin drive, so the SPHEREx canvas, the overlays
 * and the placeholder can never disagree about where they are.
 */
export function SkyView() {
  const ex = useExplore();
  const { area, viewStore, sizeStore, frames, frameVersion, bandsOn, playheadEpoch, layerId, curtain, mode, level, levels } = ex;

  const wrapRef = useRef<HTMLDivElement>(null);
  const aladinEl = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const aladinRef = useRef<AladinInstance | null>(null);
  const drag = useRef<Drag | null>(null);

  const view = useStore(viewStore);
  const size = useStore(sizeStore);
  const [draft, setDraft] = useState<SkyBox | null>(null);
  const [shown, setShown] = useState(false);

  const layer = area?.layers.find((l) => l.id === layerId && l.coverage.ok) ?? null;
  const curtainX = layer ? curtain * size.w : size.w;
  const proj = useMemo(() => makeProjection(view, size.w, size.h), [view, size.w, size.h]);

  // ---- size
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      if (width > 0 && height > 0) sizeStore.set({ w: Math.round(width), h: Math.round(height) });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [sizeStore]);

  // Keep the view inside the new limits when the area arrives or the window changes.
  useEffect(() => {
    ex.setView(viewStore.get());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [area, size.w]);

  // ---- Aladin
  useEffect(() => {
    const el = aladinEl.current;
    if (!el) return;
    let cancelled = false;
    (async () => {
      try {
        const A = await loadAladin();
        if (cancelled) return;
        const v = viewStore.get();
        const a = A.aladin(el, {
          ...BARE_ALADIN_OPTIONS,
          survey: PLACEHOLDER,
          target: `${v.ra} ${v.dec}`,
          fov: v.fov,
          projection: "TAN",
          cooFrame: "ICRS",
          backgroundColor: "rgb(5, 6, 8)",
        });
        aladinRef.current = a;
        // Handy for checking alignment from the devtools console.
        if (process.env.NODE_ENV !== "production") (window as unknown as { __aladin?: unknown }).__aladin = a;
        invalidate();
      } catch {
        // No WebGL2: the SPHEREx canvas still works once frames arrive.
      }
    })();
    return () => {
      cancelled = true;
      aladinRef.current?.stopAnimation();
      aladinRef.current = null;
      el.replaceChildren();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // The other sensor shows through on the far side of the curtain.
  useEffect(() => {
    aladinRef.current?.setBaseImageLayer(layer?.hips ?? PLACEHOLDER);
  }, [layer?.hips, area]);

  // ---- drawing, one frame at a time, only when something changed
  const raf = useRef(0);
  const latest = useRef({ view, size, curtainX, layer: !!layer, level, levels });
  latest.current = { view, size, curtainX, layer: !!layer, level, levels };

  function invalidate() {
    if (raf.current) return;
    raf.current = requestAnimationFrame(() => {
      raf.current = 0;
      drawNow();
    });
  }

  function drawNow() {
    const { view: v, size: s, curtainX: cx, level, levels } = latest.current;

    // Aladin follows our view.
    const a = aladinRef.current;
    if (a) {
      try {
        a.gotoRaDec(v.ra, v.dec);
        a.setFoV(v.fov);
      } catch {
        // Aladin can throw while it is still starting.
      }
    }

    const canvas = canvasRef.current;
    if (!canvas || !area || !frames || !playheadEpoch) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    if (canvas.width !== Math.round(s.w * dpr) || canvas.height !== Math.round(s.h * dpr)) {
      canvas.width = Math.round(s.w * dpr);
      canvas.height = Math.round(s.h * dpr);
    }
    const g = canvas.getContext("2d")!;
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.clearRect(0, 0, canvas.width, canvas.height);

    g.save();
    g.beginPath();
    g.rect(0, 0, Math.max(0, cx) * dpr, canvas.height);
    g.clip();
    g.imageSmoothingQuality = "high";
    // Each band is drawn from the frame size that suits the zoom, or the nearest one
    // that has loaded, so zooming never shows a gap while the sharper frame arrives.
    const order = [...levels].sort((x, y) => Math.abs(x.level - level) - Math.abs(y.level - level)).map((l) => l.level);
    const chosen: { id: BandId; lv: number }[] = [];
    for (const id of bandsOn) {
      const lv = order.find((l) => frames.isReady(l, playheadEpoch.id, id));
      if (lv !== undefined) chosen.push({ id, lv });
    }
    // SPHEREx is the image: black where it has no data, not the placeholder sky.
    if (chosen.length) {
      g.fillStyle = "#000";
      g.fillRect(0, 0, canvas.width, canvas.height);
    }
    g.globalCompositeOperation = "lighter";
    let any = false;
    for (const { id, lv } of chosen) {
      const tinted = frames.tintedFrame(lv, playheadEpoch.id, id, bandColor(id));
      const l = levels.find((x) => x.level === lv);
      if (!tinted || !l) continue;
      const [ta, tb, tc, td, te, tf] = frameTransform({ center: area.center, extentDeg: l.extentDeg, sizePx: l.sizePx }, v, s.w, s.h);
      g.setTransform(ta * dpr, tb * dpr, tc * dpr, td * dpr, te * dpr, tf * dpr);
      g.drawImage(tinted, 0, 0);
      any = true;
    }
    g.restore();
    setShown(any);
  }

  // Redraw on any input that changes the picture.
  useEffect(() => {
    invalidate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, size, curtainX, frameVersion, bandsOn, playheadEpoch?.id, area, frames, level]);

  // ---- pointer: pan, select, zoom
  const local = (e: { clientX: number; clientY: number }) => {
    const r = wrapRef.current!.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  };

  const onPointerDown = (e: React.PointerEvent) => {
    if (e.button !== 0) return;
    const { x, y } = local(e);
    const selecting = ex.toolsEnabled && (mode === "select" || e.shiftKey);
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    drag.current = selecting
      ? { kind: "box", x, y, moved: false }
      : { kind: "pan", x, y, proj, view: viewStore.get(), moved: false };
  };

  const onPointerMove = (e: React.PointerEvent) => {
    const d = drag.current;
    if (!d) return;
    const { x, y } = local(e);
    if (!d.moved && Math.hypot(x - d.x, y - d.y) < 4) return;
    d.moved = true;
    if (d.kind === "pan") {
      const [ra, dec] = d.proj.toSky(size.w / 2 - (x - d.x), size.h / 2 - (y - d.y));
      ex.setView({ ...d.view, ra, dec });
    } else {
      setDraft(boxFromCorners(proj, d.x, d.y, x, y));
    }
  };

  const onPointerUp = (e: React.PointerEvent) => {
    const d = drag.current;
    drag.current = null;
    if (!d) return;
    if (!d.moved) {
      // A plain click outside the box clears it.
      if (ex.box) ex.setBox(null);
      return;
    }
    if (d.kind === "box") {
      const { x, y } = local(e);
      if (Math.abs(x - d.x) > 6 || Math.abs(y - d.y) > 6) ex.setBox(boxFromCorners(proj, d.x, d.y, x, y));
      setDraft(null);
    }
  };

  // Wheel needs a non-passive listener so the page doesn't scroll.
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const r = el.getBoundingClientRect();
      const x = e.clientX - r.left;
      const y = e.clientY - r.top;
      const v = viewStore.get();
      const p = makeProjection(v, sizeStore.get().w, sizeStore.get().h);
      const [ra, dec] = p.toSky(x, y);
      const k = Math.exp(clamp(e.deltaY, -120, 120) * (e.ctrlKey ? 0.01 : 0.0016));
      const next = ex.normalizeView({ ...v, fov: v.fov * k });
      // Keep the sky under the cursor where it was.
      const p2 = makeProjection(next, sizeStore.get().w, sizeStore.get().h);
      const [ra2, dec2] = p2.toSky(x, y);
      ex.setView({
        ...next,
        ra: next.ra + (ra - ra2),
        dec: next.dec + (dec - dec2),
      });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [ex, viewStore, sizeStore]);

  const boxShown = draft ?? ex.box;

  return (
    <div
      ref={wrapRef}
      className="explore-view relative min-h-0 flex-1 overflow-hidden rounded-xl border border-line-strong bg-sky"
    >
      {/* 1. Aladin (no z-index, so its logo can sit above the canvas) */}
      <div className="absolute inset-0" aria-hidden="true">
        {/* Aladin makes its own container position:relative, so it needs a sized parent. */}
        <div ref={aladinEl} className="size-full" />
      </div>

      {/* 2. SPHEREx */}
      <canvas
        ref={canvasRef}
        aria-hidden="true"
        className={cn(
          "pointer-events-none absolute inset-0 z-[1] size-full transition-opacity duration-(--dur-enter) ease-standard",
          shown ? "opacity-100" : "opacity-0",
        )}
      />

      {/* 3. pointer layer */}
      <div
        role="application"
        aria-label="Sky view. Drag to move, scroll to zoom."
        className={cn("absolute inset-0 z-[2] touch-none", mode === "select" ? "cursor-crosshair" : "cursor-grab active:cursor-grabbing")}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={() => {
          drag.current = null;
          setDraft(null);
        }}
      />

      {/* 4. overlays */}
      <svg className="pointer-events-none absolute inset-0 z-[3] size-full" width={size.w} height={size.h}>
        <MotionOverlay proj={proj} />
        <ObjectMarkers key={ex.showDiscussionPosts ? 'discussions-shown' : 'discussions-hidden'} proj={proj} />
        {boxShown && (
          <SelectionBox
            box={boxShown}
            proj={proj}
            onChange={(b) => ex.setBox(b)}
            clientToLocal={local}
            onDraft={setDraft}
          />
        )}
      </svg>

      {/* 5. controls */}
      {layer && <Curtain layerName={layer.name} />}
      <ViewControls />
      <LayerPicker />
      <ViewStatus />
    </div>
  );
}

const bandColor = (id: BandId) => BANDS.find((b) => b.id === id)?.color ?? "#ffffff";

function boxFromCorners(proj: Projection, x0: number, y0: number, x1: number, y1: number): SkyBox {
  const [ra, dec] = proj.toSky((x0 + x1) / 2, (y0 + y1) / 2);
  return {
    ra,
    dec,
    width: (Math.abs(x1 - x0) / proj.scale) * R2D,
    height: (Math.abs(y1 - y0) / proj.scale) * R2D,
  };
}
