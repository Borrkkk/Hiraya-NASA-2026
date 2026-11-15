// MOCK backend for the Explore page. Everything here is invented, procedural
// and deterministic per area. Nothing is SPHEREx data. Replace by setting
// NEXT_PUBLIC_EXPLORE_API=http once the real API exists.
//
// Test the unhappy paths by adding ?mock=<flag> to the Explore URL:
//   fail-data     frames fail to load (placeholder stays, Retry shown)
//   fail-motion   Analyze motion fails
//   fail-verify   Verify fails
//   no-movers     Analyze finds nothing
//   slow          everything takes 3x longer

import type { ExploreApi } from "../api";
import { BANDS } from "../bands";
import { separationDeg, offsetDeg } from "../projection";
import type {
  Area,
  BandStatus,
  CallOptions,
  Inspection,
  InspectRequest,
  ObjectType,
  SensorLayer,
  SkyBox,
  Spectrum,
  SpectrumFeature,
  TypeScore,
  VerifyOutcome,
} from "../types";
import { gauss, mulberry32 } from "./rng";
import { renderFrame } from "./render";
import {
  bandIsEmpty,
  fluxInBox,
  getSkyModel,
  mockAreaId,
  moverPosition,
  parseMockAreaId,
  type Flux,
  type SkyModel,
} from "./sky-model";

function flag(name: string) {
  if (typeof window === "undefined") return false;
  return new URLSearchParams(window.location.search).get("mock")?.split(",").includes(name) ?? false;
}

function wait(ms: number, signal?: AbortSignal) {
  const t = flag("slow") ? ms * 3 : ms;
  return new Promise<void>((resolve, reject) => {
    if (signal?.aborted) return reject(new DOMException("Aborted", "AbortError"));
    const id = setTimeout(resolve, t);
    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(id);
        reject(new DOMException("Aborted", "AbortError"));
      },
      { once: true },
    );
  });
}

const modelFor = (areaId: string) => {
  const p = parseMockAreaId(areaId);
  return getSkyModel(p.ra, p.dec, p.fov);
};

// ---- sensors: real IRSA HiPS surveys. The same URLs the real backend can return.

const IRSA = "https://irsa.ipac.caltech.edu/data/hips/CDS";
const layers = (): SensorLayer[] => [
  {
    id: "wise",
    name: "WISE",
    blurb: "Mid-infrared heat from dust and cool stars, the closest cousin to SPHEREx.",
    hips: `${IRSA}/AllWISE/RGB-W4-W2-W1`,
    thumbnail: `${IRSA}/AllWISE/RGB-W4-W2-W1/Norder0/Dir0/Npix7.jpg`,
    coverage: { ok: true },
  },
  {
    id: "2mass",
    name: "2MASS",
    blurb: "Near-infrared starlight, good for seeing through thin dust.",
    hips: `${IRSA}/2MASS/Color`,
    thumbnail: `${IRSA}/2MASS/Color/Norder0/Dir0/Npix7.jpg`,
    coverage: { ok: true },
  },
  {
    id: "dss2",
    name: "Visible light",
    blurb: "What a camera would see, the digitised sky survey.",
    hips: `${IRSA}/DSS2/color`,
    thumbnail: `${IRSA}/DSS2/color/Norder0/Dir0/Npix7.jpg`,
    coverage: { ok: true },
  },
  {
    id: "iris",
    name: "IRAS dust",
    blurb: "Far-infrared glow of cold dust across the whole sky, blurry but wide.",
    hips: `${IRSA}/IRIS/color`,
    thumbnail: `${IRSA}/IRIS/color/Norder0/Dir0/Npix7.jpg`,
    coverage: { ok: true },
  },
];

// ---- the five calls

export const mockExploreApi: ExploreApi = {
  async getArea(req, opts) {
    await wait(350, opts?.signal);
    const model = getSkyModel(req.ra, req.dec, req.fov);
    const bands: BandStatus[] = BANDS.map((b) => {
      // One band without coverage, to show the disabled state, only for a
      // few areas so the default experience isn't a mystery.
      if (b.id === "co-ice" && model.seed % 5 === 0)
        return { id: b.id, state: "no-coverage", reason: "SPHEREx hasn't covered this band here yet." };
      return { id: b.id, state: "ok", empty: bandIsEmpty(model, b.id) };
    });
    const area: Area = {
      id: mockAreaId(req.ra, req.dec, req.fov),
      name: model.nearest?.name ?? null,
      center: model.area.center,
      extentDeg: model.area.extentDeg,
      sizePx: model.area.sizePx,
      pixelScaleArcsec: model.area.pixelScaleArcsec,
      epochs: model.epochs.map(({ id, date }) => ({ id, date })),
      bands,
      layers: layers(),
    };
    return area;
  },

  async fetchFrame({ areaId, epochId, band }, opts) {
    if (flag("fail-data")) {
      await wait(900, opts?.signal);
      throw new Error("Mock failure: frames unavailable");
    }
    await wait(500 + Math.random() * 900, opts?.signal);
    const model = modelFor(areaId);
    return renderFrame(model, areaId, epochId, band);
  },

  async inspect(req, opts) {
    await wait(450, opts?.signal);
    return inspectModel(modelFor(req.areaId), req);
  },

  async analyzeMotion(req, opts) {
    const steps = [
      "Lining up the frames…",
      "Matching stars between frames…",
      "Looking for things that shifted…",
      "Joining the dots into tracks…",
    ];
    for (const s of steps) {
      opts?.onStep?.(s);
      await wait(700, opts?.signal);
    }
    if (flag("fail-motion")) throw new Error("Mock failure: motion analysis");
    const model = modelFor(req.areaId);
    const epochs = model.epochs.filter((e) => req.epochs.includes(e.id));
    if (flag("no-movers") || epochs.length < 2) return { movers: [], epochs: req.epochs };
    const movers = model.movers.map((m, i) => {
      const points = epochs.map((e) => ({
        epochId: e.id,
        date: e.date,
        ...moverPosition(m, e.years),
      }));
      const a = points[0];
      const b = points[points.length - 1];
      const hours = (Date.parse(b.date) - Date.parse(a.date)) / 36e5;
      const o = offsetDeg(a, b);
      const arcsec = Math.hypot(o.east, o.north) * 3600;
      const pa = ((Math.atan2(o.east, o.north) * 180) / Math.PI + 360) % 360;
      return {
        id: m.id,
        number: i + 1,
        points,
        speedArcsecPerHour: arcsec / hours,
        positionAngleDeg: pa,
      };
    });
    return { movers, epochs: req.epochs };
  },

  async verify(req, opts) {
    const steps = [
      "Checking known stars…",
      "Checking known asteroids…",
      "Checking catalogs…",
      "Checking for instrument glitches…",
    ];
    for (const s of steps) {
      opts?.onStep?.(s);
      await wait(650, opts?.signal);
    }
    if (flag("fail-verify")) throw new Error("Mock failure: cross-reference");
    return verifyModel(modelFor(req.areaId), req);
  },
};

// ---------------------------------------------------------------- inspect

const WAVELENGTHS = Array.from({ length: 96 }, (_, i) => 0.75 + (i * (5 - 0.75)) / 95);

const bump = (x: number, c: number, w: number) => Math.exp(-(((x - c) / w) ** 2));

function makeSpectrum(f: Flux, seed: number): Spectrum {
  const rand = mulberry32(seed);
  const points = WAVELENGTHS.map((w) => {
    // A warm star falls with wavelength; dust and cool objects rise past 3.5 µm.
    let flux = f.starlight * 1.1 * Math.pow(1.1 / w, 1.6);
    flux += f["warm-glow"] * 0.9 * bump(w, 4.6, 1.1);
    flux += f.hydrogen * 0.7 * (bump(w, 1.28, 0.03) + bump(w, 1.88, 0.04) + bump(w, 4.05, 0.05));
    flux += f.helium * 0.6 * bump(w, 1.08, 0.03);
    flux += f["organic-dust"] * 0.55 * bump(w, 3.3, 0.06);
    flux -= f["water-ice"] * 0.35 * bump(w, 3.0, 0.18);
    flux -= f["co2-ice"] * 0.3 * bump(w, 4.27, 0.06);
    flux -= f["co-ice"] * 0.25 * bump(w, 4.67, 0.05);
    flux -= f.methane * 0.3 * (bump(w, 1.7, 0.1) + bump(w, 3.3, 0.12));
    flux += f.methane * 0.5 * bump(w, 1.28, 0.12); // methane objects peak in the gaps
    return { wavelengthUm: w, flux: Math.max(0, flux + gauss(rand) * 0.012) };
  });

  const features: SpectrumFeature[] = [];
  const add = (on: boolean, label: string, realName: string, wavelengthUm: number) =>
    on && features.push({ label, realName, wavelengthUm });
  add(f.hydrogen > 0.12, "Hydrogen", "Hydrogen line (Paschen β, 1.28 µm)", 1.28);
  add(f.hydrogen > 0.12, "Hydrogen", "Hydrogen line (Paschen α, 1.88 µm)", 1.88);
  add(f.helium > 0.1, "Helium", "Helium line (1.08 µm)", 1.08);
  add(f.methane > 0.12, "Methane", "Methane absorption (1.7 µm)", 1.7);
  add(f["organic-dust"] > 0.1, "Organic dust", "PAH emission (3.3 µm)", 3.3);
  add(f["water-ice"] > 0.12, "Water ice", "Water ice absorption (3.0 µm)", 3.0);
  add(f["co2-ice"] > 0.12, "CO₂ ice", "CO₂ ice absorption (4.27 µm)", 4.27);
  add(f["co-ice"] > 0.12, "CO ice", "CO ice absorption (4.67 µm)", 4.67);
  return { points, fluxLabel: "Brightness (relative)", features };
}

function inspectModel(model: SkyModel, req: InspectRequest): Inspection {
  const { box } = req.target;
  const f = fluxInBox(model, box, req.epoch);
  const total = Object.values(f).reduce((a, b) => a + b, 0);
  const spectrum = makeSpectrum(f, model.seed ^ Math.round(box.ra * 1000));
  const mover = req.target.kind === "mover" ? model.movers.find((m) => m.id === (req.target as { moverId: string }).moverId) : undefined;

  const edge = (() => {
    const o = offsetDeg(model.area.center, box);
    const limit = model.area.extentDeg / 2;
    return Math.max(Math.abs(o.east), Math.abs(o.north)) > limit * 0.93;
  })();

  const scores: Record<ObjectType, number> = {
    star: 0.1 + f.starlight * 0.6,
    "brown-dwarf": f.methane * 1.2,
    planet: f.methane * 0.15 + (mover ? 0.05 : 0),
    comet: mover?.kind === "comet" ? 0.9 : f.hydrogen * 0.15 + (mover ? 0.1 : 0),
    asteroid: mover?.kind === "asteroid" ? 0.9 : mover ? 0.1 : 0,
    galaxy: model.nearest?.kind === "galaxy" ? f.starlight * 0.5 : 0.02,
    empty: total < 0.2 ? 0.9 : 0.03,
    artifact: edge ? 0.7 : 0.02,
  };

  const low = total < 0.2 && !mover;
  let type: ObjectType = (Object.entries(scores).sort((a, b) => b[1] - a[1])[0][0]) as ObjectType;
  if (low) type = "empty";

  const reasons: Record<ObjectType, string> = {
    star: f.hydrogen > 0.2
      ? "Likely young stars in glowing gas: bright starlight and hydrogen lines"
      : "Likely a star: bright and smooth, with no strong features",
    "brown-dwarf": "Likely a brown dwarf: very cold, methane detected",
    planet: "Possibly a planet: faint, cold and moving against the stars",
    comet: "Likely a comet: moves, glows warm, and gives off hydrogen",
    asteroid: "Likely an asteroid: moves across the stars and glows warm at 4–5 µm",
    galaxy: "Likely a galaxy: soft, extended starlight with no sharp edge",
    empty: "Not enough signal to say. Try a bigger box or other bands.",
    artifact: "Likely an artifact: it sits right at the edge of the frame",
  };

  const sum = Object.values(scores).reduce((a, b) => a + b, 0) || 1;
  const candidates: TypeScore[] = (Object.entries(scores) as [ObjectType, number][])
    .map(([t, s]) => ({ type: t, confidence: low ? (t === "empty" ? 0.9 : 0.1 / 7) : s / sum }))
    .sort((a, b) => b.confidence - a.confidence);

  return { lowSignal: low, guess: { type, reason: reasons[type] }, candidates, spectrum };
}

// ---------------------------------------------------------------- verify

function verifyModel(model: SkyModel, req: InspectRequest & { moverId?: string }): VerifyOutcome {
  const mover = req.moverId ? model.movers.find((m) => m.id === req.moverId) : undefined;
  if (mover) {
    if (mover.fate === "explained")
      return {
        outcome: "explained",
        headline: mover.kind === "asteroid" ? "Known asteroid" : "Known comet",
        name: mover.kind === "asteroid" ? "(4179) Mock-1" : "C/2025 M1 (Mock)",
        fact: "Its predicted path for these dates passes within a few arcseconds of the track.",
        source: "SkyBoT",
        objectType: mover.kind === "asteroid" ? "asteroid" : "comet",
      };
    if (mover.fate === "artifact")
      return {
        outcome: "artifact",
        headline: "Not a real object",
        reason: "It matches a detector glitch flagged in one of the frames.",
        flag: "Instrument flag: hot pixel cluster",
      };
    return {
      outcome: "unexplained",
      headline: "We can't match this to anything known",
      nearMatch: { name: "Mock Star 12", source: "Gaia", note: "Close by, but it doesn't move the way this does." },
    };
  }

  const box = req.target.box;
  const near = model.nearest;
  if (near && separationDeg(box, model.area.center) < Math.max(box.width, box.height)) {
    return {
      outcome: "explained",
      headline: `Known ${near.kind === "brown-dwarf" ? "brown dwarf" : near.kind.replace("-", " ")}`,
      name: near.name,
      fact: "Listed in the catalog at this position.",
      source: "SIMBAD",
      objectType: near.kind === "brown-dwarf" ? "brown-dwarf" : near.kind === "galaxy" ? "galaxy" : "star",
    };
  }
  const o = offsetDeg(model.area.center, box);
  if (Math.max(Math.abs(o.east), Math.abs(o.north)) > model.area.extentDeg * 0.46)
    return {
      outcome: "artifact",
      headline: "Not a real object",
      reason: "It sits on the very edge of the frame, where the detector often produces false signals.",
      flag: "Instrument flag: frame edge",
    };
  return { outcome: "unexplained", headline: "We can't match this to anything known" };
}

export type { CallOptions, SkyBox };
