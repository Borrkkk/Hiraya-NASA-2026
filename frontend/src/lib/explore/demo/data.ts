// The prefetched demo dataset: frontend/public/demo/barnard (made by
// scripts/make-demo-data.py). Static files only, no backend, no network.

import type { BandId } from "../types";

export const DEMO_BASE = "/demo/barnard";
export const DEMO_AREA_ID = "demo-barnard";

export type DemoSource = {
  id: string;
  kind: "star" | "mover" | "galaxy" | "hotpixel";
  /** Spectrum template: M, K, G, A, T (brown dwarf) or galaxy. */
  cls: "M" | "K" | "G" | "A" | "T" | "galaxy";
  /** J magnitude. Total brightness is flux0 * 10^(-0.4 j). */
  j: number;
  ra: number;
  dec: number;
  /** Proper motion, mas/yr, and the year `ra`/`dec` are for (default 2000.0 for Barnard's Star). */
  pmRa?: number;
  pmDec?: number;
  ref?: number;
  name?: string;
  /** Galaxies: effective radius in arcseconds. */
  reff?: number;
};

export type DemoEpoch = {
  id: string;
  date: string;
  bands: BandId[];
  coverage: number;
  /** The one wavelength (µm) this observation sampled in each band. */
  wavelengths: Partial<Record<BandId, number>>;
  /** Decimal year, for proper motion. */
  year: number;
};

export type Demo = {
  area: {
    id: string;
    name: string;
    center: { ra: number; dec: number };
    extentDeg: number;
    sizePx: number;
    pixelScaleArcsec: number;
    minFovDeg: number;
    maxFovDeg: number;
    levels: { level: number; extentDeg: number; sizePx: number; pixelScaleArcsec: number }[];
  };
  epochs: DemoEpoch[];
  grid: number[];
  spectra: Record<DemoSource["cls"], number[]>;
  sources: DemoSource[];
  hotPixels: { x: number; y: number }[];
  flux0: number;
  sigma: number;
  fwhmArcsec: number;
};

let loading: Promise<Demo> | null = null;

export function loadDemo(signal?: AbortSignal): Promise<Demo> {
  loading ??= fetch(`${DEMO_BASE}/manifest.json`, { signal })
    .then((r) => {
      if (!r.ok) throw new Error("The demo data is missing. Run scripts/make-demo-data.py.");
      return r.json() as Promise<Demo>;
    })
    .then((d) => {
      prefetchFrames(d);
      return d;
    })
    .catch((e) => {
      loading = null; // allow a retry
      throw e;
    });
  return loading;
}

export const frameUrl = (level: number, epochId: string, band: BandId) =>
  `${DEMO_BASE}/frames/L${level}/${epochId}/${band}.png`;

/** Warm the browser cache with the closest zoom level of every frame, a few at a time. */
function prefetchFrames(d: Demo) {
  if (typeof window === "undefined") return;
  const urls: string[] = [];
  for (const level of [0, 1, 2])
    for (const e of d.epochs) for (const b of e.bands) urls.push(frameUrl(level, e.id, b));
  let next = 0;
  const worker = async () => {
    while (next < urls.length) {
      const url = urls[next++];
      try {
        await fetch(url);
      } catch {
        // Offline or aborted: the frame store will retry when it needs the frame.
      }
    }
  };
  for (let i = 0; i < 4; i++) void worker();
}

export function interp(xs: number[], ys: number[], x: number) {
  if (x <= xs[0]) return ys[0];
  if (x >= xs[xs.length - 1]) return ys[ys.length - 1];
  let lo = 0;
  let hi = xs.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (xs[mid] <= x) lo = mid;
    else hi = mid;
  }
  const t = (x - xs[lo]) / (xs[hi] - xs[lo]);
  return ys[lo] + t * (ys[hi] - ys[lo]);
}

/** Where a source is at a given decimal year. */
export function positionAt(s: DemoSource, year: number) {
  if (s.pmRa === undefined || s.pmDec === undefined) return { ra: s.ra, dec: s.dec };
  const dt = year - (s.ref ?? 2000);
  return {
    ra: s.ra + (s.pmRa / 3.6e6) * dt / Math.cos((s.dec * Math.PI) / 180),
    dec: s.dec + (s.pmDec / 3.6e6) * dt,
  };
}

/** Observation year as a decimal, from an ISO date. */
export const yearOf = (iso: string) => {
  const t = Date.parse(iso);
  return 1970 + t / (365.25 * 864e5);
};
