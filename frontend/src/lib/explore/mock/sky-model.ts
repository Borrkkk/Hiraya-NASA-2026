// A made-up patch of sky, deterministic per area. MOCK ONLY: none of this is
// SPHEREx data. It exists so every part of the Explore UI has something
// plausible to show. The shapes it produces are the ones the real API returns.

import { CATALOG, type ObjectKind } from "@/lib/sky/catalog";
import { BANDS } from "../bands";
import { frameProjection, offsetDeg, separationDeg, shiftPoint } from "../projection";
import type { Area, BandId, Epoch, SkyBox, SkyPoint } from "../types";
import { gauss, hashString, mulberry32 } from "./rng";

export type Flux = Record<BandId, number>;
const zero = (): Flux => Object.fromEntries(BANDS.map((b) => [b.id, 0])) as Flux;

export type Star = SkyPoint & { flux: Flux; size: number };
export type Cloud = SkyPoint & {
  kind: "emission" | "dark" | "galaxy";
  /** Radius in degrees. */
  r: number;
  strength: number;
};
export type MoverTruth = {
  id: string;
  /** Position at the first epoch. */
  start: SkyPoint;
  /** Degrees per year, east and north. */
  east: number;
  north: number;
  flux: Flux;
  /** What the verify mock will say about it. */
  fate: "explained" | "artifact" | "unexplained";
  kind: "asteroid" | "comet" | "brown-dwarf";
};

export type SkyModel = {
  area: Pick<Area, "center" | "extentDeg" | "sizePx" | "pixelScaleArcsec">;
  epochs: (Epoch & { years: number })[];
  stars: Star[];
  blobs: Cloud[];
  movers: MoverTruth[];
  nearest: { name: string; kind: ObjectKind } | null;
  seed: number;
};

/** Epochs are months apart and uneven, like a real revisit pattern. */
const EPOCH_DATES = ["2025-07-02", "2025-12-18", "2026-01-09", "2026-06-21", "2026-10-30"];
const T0 = Date.parse(EPOCH_DATES[0]);

export const mockAreaId = (ra: number, dec: number, fov: number) =>
  `mock-${ra.toFixed(4)}_${dec.toFixed(4)}_${fov.toFixed(3)}`;

export function parseMockAreaId(id: string) {
  const m = /^mock-([\d.]+)_(-?[\d.]+)_([\d.]+)$/.exec(id);
  if (!m) throw new Error(`Unknown mock area ${id}`);
  return { ra: Number(m[1]), dec: Number(m[2]), fov: Number(m[3]) };
}

const cache = new Map<string, SkyModel>();

export function getSkyModel(ra: number, dec: number, fov: number): SkyModel {
  const id = mockAreaId(ra, dec, fov);
  const hit = cache.get(id);
  if (hit) return hit;
  const model = build(ra, dec, fov, id);
  cache.set(id, model);
  return model;
}

function build(ra: number, dec: number, fov: number, id: string): SkyModel {
  const rand = mulberry32(hashString(id));
  const center = { ra, dec };
  const extentDeg = Math.max(1.5, fov * 3);
  const sizePx = Math.min(1536, Math.round((extentDeg * 3600) / 6));
  const pixelScaleArcsec = (extentDeg * 3600) / sizePx;
  const area = { center, extentDeg, sizePx, pixelScaleArcsec };
  const fp = frameProjection(area);

  const near = CATALOG.filter((o) => o.ra !== undefined && o.dec !== undefined)
    .map((o) => ({ o, d: separationDeg(center, { ra: o.ra!, dec: o.dec! }) }))
    .sort((a, b) => a.d - b.d)[0];
  const nearest = near && near.d <= Math.max(0.3, fov) ? { name: near.o.name, kind: near.o.kind } : null;
  const kind = nearest?.kind;

  const at = (ox: number, oy: number): SkyPoint => {
    const [r, d] = fp.toSky(sizePx / 2 + ox * sizePx, sizePx / 2 + oy * sizePx);
    return { ra: r, dec: d };
  };

  // Stars: mostly faint, a few bright. Denser in a cluster.
  const stars: Star[] = [];
  const count = kind === "cluster" ? 520 : 380;
  for (let i = 0; i < count; i++) {
    const clustered = kind === "cluster" && rand() < 0.6;
    const ox = clustered ? gauss(rand) * 0.12 : rand() - 0.5;
    const oy = clustered ? gauss(rand) * 0.12 : rand() - 0.5;
    if (Math.abs(ox) > 0.5 || Math.abs(oy) > 0.5) continue;
    const b = Math.pow(rand(), 3.2);
    const cool = rand();
    const flux = zero();
    flux.starlight = 0.12 + b * 0.88;
    flux["warm-glow"] = flux.starlight * 0.15 * (0.3 + cool);
    stars.push({ ...at(ox, oy), flux, size: 1.1 + b * 3.4 });
  }

  // Clouds and glow, shaped by what the area is.
  const blobs: Cloud[] = [];
  const R = extentDeg;
  if (kind === "nebula") {
    blobs.push({ ...at(0.02, 0), kind: "emission", r: R * 0.17, strength: 1 });
    blobs.push({ ...at(-0.16, 0.08), kind: "dark", r: R * 0.1, strength: 0.9 });
    blobs.push({ ...at(0.17, -0.1), kind: "emission", r: R * 0.09, strength: 0.6 });
  } else if (kind === "galaxy") {
    blobs.push({ ...at(0, 0), kind: "galaxy", r: R * 0.12, strength: 1 });
  } else if (kind === "brown-dwarf" || kind === "star" || kind === "cluster") {
    if (rand() < 0.4) blobs.push({ ...at(0.2, 0.15), kind: "dark", r: R * 0.1, strength: 0.7 });
  } else {
    if (rand() < 0.6) blobs.push({ ...at(rand() - 0.5, rand() - 0.5), kind: "emission", r: R * 0.1, strength: 0.7 });
    if (rand() < 0.6) blobs.push({ ...at(rand() - 0.5, rand() - 0.5), kind: "dark", r: R * 0.09, strength: 0.8 });
  }

  // A cold object at the centre when the area is about one.
  if (kind === "brown-dwarf") {
    const flux = zero();
    flux.starlight = 0.18;
    flux.methane = 0.85;
    flux["warm-glow"] = 0.5;
    stars.push({ ...center, flux, size: 4.2 });
  }

  const epochs = EPOCH_DATES.map((date, i) => ({
    id: `e${i + 1}`,
    date: `${date}T00:00:00Z`,
    years: (Date.parse(date) - T0) / (365.25 * 864e5),
  }));

  // Three things that move. Speeds scale with the area so tracks stay in frame.
  const kinds: MoverTruth["kind"][] = ["asteroid", "comet", "brown-dwarf"];
  const fates: MoverTruth["fate"][] = ["explained", "artifact", "unexplained"];
  const spanYears = epochs[epochs.length - 1].years;
  const movers: MoverTruth[] = kinds.map((k, i) => {
    const heading = rand() * Math.PI * 2;
    const speed = (0.035 + rand() * 0.03 + i * 0.012) * extentDeg / spanYears;
    const flux = zero();
    if (k === "asteroid") {
      flux["warm-glow"] = 0.8;
      flux.starlight = 0.35;
    } else if (k === "comet") {
      flux["warm-glow"] = 0.7;
      flux.starlight = 0.3;
      flux.hydrogen = 0.35;
    } else {
      flux.methane = 0.8;
      flux["warm-glow"] = 0.45;
      flux.starlight = 0.15;
    }
    const sx = (rand() - 0.5) * 0.26;
    const sy = (rand() - 0.5) * 0.26;
    return {
      id: `m${i + 1}`,
      start: at(sx, sy),
      east: Math.sin(heading) * speed,
      north: Math.cos(heading) * speed,
      flux,
      fate: fates[i],
      kind: k,
    };
  });

  // Demo-only visual safety: background stars near a mover's path can look
  // like a second copy of that moving object in a still screenshot. Keep the
  // static sky populated, but clear a small corridor around each fake track.
  // This never changes real SPHEREx imagery or motion analysis.
  const samplePositions = movers.flatMap((m) =>
    Array.from({ length: 13 }, (_, i) => {
      const p = moverPosition(m, (spanYears * i) / 12);
      return fp.toScreen(p.ra, p.dec);
    }),
  );
  const clearStars = stars.filter((s) => {
    const [x, y] = fp.toScreen(s.ra, s.dec);
    // Mock star sprites have a width of size * 8 pixels. Leave room for the
    // mover's own sprite too, so two bright sources never blend together.
    const minSeparationPx = 18 + s.size * 4 + 14;
    return samplePositions.every(([mx, my]) => Math.hypot(x - mx, y - my) > minSeparationPx);
  });

  return { area, epochs, stars: clearStars, blobs, movers, nearest, seed: hashString(id) };
}

export function moverPosition(m: MoverTruth, years: number): SkyPoint {
  return shiftPoint(m.start, m.east * years, m.north * years);
}

/** Profile of a blob at `d` degrees from its centre, 0..1. */
export function blobProfile(b: Cloud, d: number) {
  const x = d / b.r;
  return b.strength * Math.exp(-x * x);
}

/**
 * Mean brightness per band inside a box at one epoch, 0..~1. The same model
 * drawn into the frames, so the spectrum and the type guess agree with what
 * the user can see.
 */
export function fluxInBox(model: SkyModel, box: SkyBox, epochId: string | "all"): Flux {
  const out = zero();
  const half = { w: box.width / 2, h: box.height / 2 };
  const inside = (p: SkyPoint) => {
    const o = offsetDeg(box, p);
    return Math.abs(o.east) <= half.w && Math.abs(o.north) <= half.h;
  };
  for (const s of model.stars) {
    if (!inside(s)) continue;
    for (const b of BANDS) out[b.id] += s.flux[b.id];
  }
  const epochs = epochId === "all" ? model.epochs : model.epochs.filter((e) => e.id === epochId);
  for (const e of epochs) {
    for (const m of model.movers) {
      if (!inside(moverPosition(m, e.years))) continue;
      for (const b of BANDS) out[b.id] += m.flux[b.id] / epochs.length;
    }
  }
  // Clouds: average the profile over a small grid of points in the box.
  const n = 5;
  for (const blob of model.blobs) {
    let sum = 0;
    for (let i = 0; i < n; i++)
      for (let j = 0; j < n; j++) {
        const p = shiftPoint(box, ((i + 0.5) / n - 0.5) * box.width, ((j + 0.5) / n - 0.5) * box.height);
        sum += blobProfile(blob, separationDeg(p, blob));
      }
    const v = sum / (n * n);
    if (blob.kind === "emission") {
      out.hydrogen += v;
      out.helium += v * 0.5;
      out["warm-glow"] += v * 0.5;
      out["organic-dust"] += v * 0.35;
    } else if (blob.kind === "dark") {
      out["water-ice"] += v;
      out["co2-ice"] += v * 0.8;
      out["co-ice"] += v * 0.6;
      out["warm-glow"] += v * 0.15;
    } else {
      out.starlight += v;
      out["warm-glow"] += v * 0.3;
    }
  }
  // Stars add up with the box size; normalise to something comparable.
  const area = Math.max(1e-6, box.width * box.height);
  const ref = model.area.extentDeg * model.area.extentDeg * 0.01;
  const scale = Math.min(1, ref / area);
  out.starlight *= scale;
  out["warm-glow"] *= Math.max(scale, 0.35);
  out.methane *= Math.max(scale, 0.35);
  return out;
}

/** Whether a band shows anything in the whole area. Drives the "nothing bright" note. */
export function bandIsEmpty(model: SkyModel, band: BandId): boolean {
  const e = model.area.extentDeg;
  const whole = fluxInBox(model, { ...model.area.center, width: e, height: e }, "all");
  return whole[band] < 0.35 && !(band === "starlight" || band === "warm-glow");
}
