// The demo backend for the Explore page: Barnard's Star, prefetched and
// simulated. NONE OF THIS IS SPHEREx DATA. It is shaped like the real thing
// (same contract as the Python API, see ../types.ts) so the page behaves the
// same, and it answers instantly from static files, so the demo cannot fail on
// a slow archive or a bad connection.
//
// What is real: Barnard's Star's position, proper motion (10.3 arcsec a year
// north) and brightness. What is simulated: the SPHEREx frames, the spectra,
// the cold object that moves ("the find"), and the catalogue look-ups.
//
// Switch to the real backend with NEXT_PUBLIC_EXPLORE_API=http.

import type { ExploreApi } from "../api";
import { NoDataError } from "../errors";
import { offsetDeg, separationDeg } from "../projection";
import type {
  Area,
  BandId,
  BandStatus,
  Epoch,
  Inspection,
  InspectRequest,
  Mover,
  ObjectType,
  SensorLayer,
  SkyBox,
  Spectrum,
  SpectrumFeature,
  TypeScore,
  VerifyOutcome,
} from "../types";
import { BANDS } from "../bands";
import { DEMO_AREA_ID, frameUrl, interp, loadDemo, positionAt, type Demo, type DemoEpoch, type DemoSource } from "./data";
import { gauss, hashString, mulberry32 } from "./rng";

const wait = (ms: number, signal?: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    if (signal?.aborted) return reject(new DOMException("Aborted", "AbortError"));
    const id = setTimeout(resolve, ms);
    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(id);
        reject(new DOMException("Aborted", "AbortError"));
      },
      { once: true },
    );
  });

// ---- sensors: the same IRSA HiPS surveys the real backend offers (Aladin loads them)

const IRSA = "https://irsa.ipac.caltech.edu/data/hips/CDS";
const LAYERS: SensorLayer[] = [
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

// Nothing in a star field glows at these wavelengths, so the page says so.
const QUIET: BandId[] = ["hydrogen", "helium", "water-ice", "co2-ice", "co-ice", "organic-dust", "methane"];

const FIND = "find";
const BARNARD = "barnard";

// ---------------------------------------------------------------- the five calls

export const demoExploreApi: ExploreApi = {
  async getArea(req, opts) {
    const d = await loadDemo(opts?.signal);
    await wait(120, opts?.signal);
    if (separationDeg(req, d.area.center) > 1.2)
      throw new NoDataError(
        "This demo only has SPHEREx images for Barnard's Star.",
        { name: "Barnard's Star", ra: d.area.center.ra, dec: d.area.center.dec, fov: 0.2 },
      );
    const bands: BandStatus[] = BANDS.map((b) => ({ id: b.id, state: "ok", empty: QUIET.includes(b.id) }));
    const epochs: Epoch[] = d.epochs.map((e) => ({ id: e.id, date: e.date, bands: e.bands, coverage: e.coverage }));
    const area: Area = {
      id: DEMO_AREA_ID,
      name: d.area.name,
      center: d.area.center,
      extentDeg: d.area.extentDeg,
      sizePx: d.area.sizePx,
      pixelScaleArcsec: d.area.pixelScaleArcsec,
      minFovDeg: d.area.minFovDeg,
      maxFovDeg: d.area.maxFovDeg,
      levels: d.area.levels,
      epochs,
      bands,
      layers: LAYERS,
    };
    return area;
  },

  async fetchFrame({ epochId, band, level = 0 }, opts) {
    const r = await fetch(frameUrl(level, epochId, band), { signal: opts?.signal });
    if (!r.ok) throw new Error(`No ${band} frame for ${epochId}`);
    return r.blob();
  },

  async inspect(req, opts) {
    const d = await loadDemo(opts?.signal);
    await wait(260, opts?.signal);
    return inspectBox(d, req);
  },

  async analyzeMotion(req, opts) {
    const d = await loadDemo(opts?.signal);
    const steps = [
      "Lining up the frames…",
      "Matching stars between frames…",
      "Looking for things that shifted…",
      "Joining the dots into tracks…",
    ];
    for (const s of steps) {
      opts?.onStep?.(s);
      await wait(620, opts?.signal);
    }
    const eps = d.epochs.filter((e) => req.epochs.includes(e.id)).sort((a, b) => a.year - b.year);
    const movers: Mover[] = [];
    if (eps.length >= 2) {
      const pxDeg = d.area.pixelScaleArcsec / 3600;
      for (const s of d.sources.filter((x) => x.kind === "mover" || x.id === BARNARD)) {
        // The cold object is faint: it only shows when a warm-glow or starlight frame is in use.
        if (s.id === FIND && !req.bands.some((b) => b === "warm-glow" || b === "starlight")) continue;
        const rand = mulberry32(hashString(`${s.id}|track`));
        const points = eps.map((e) => {
          const p = positionAt(s, e.year);
          // Centroid error: a fraction of a pixel, bigger for the faint one.
          const err = (s.id === FIND ? 0.08 : 0.002) * pxDeg;
          const q = { ra: p.ra + (gauss(rand) * err) / Math.cos((p.dec * Math.PI) / 180), dec: p.dec + gauss(rand) * err };
          return { epochId: e.id, date: e.date, ra: q.ra, dec: q.dec };
        });
        const a = points[0];
        const b = points[points.length - 1];
        const o = offsetDeg(a, b);
        const shiftPx = Math.hypot(o.east, o.north) / pxDeg;
        if (shiftPx < 1.0) continue; // not enough movement to be sure it isn't noise
        const hours = (Date.parse(b.date) - Date.parse(a.date)) / 36e5;
        movers.push({
          id: s.id,
          number: 0,
          points,
          speedArcsecPerHour: (Math.hypot(o.east, o.north) * 3600) / hours,
          positionAngleDeg: ((Math.atan2(o.east, o.north) * 180) / Math.PI + 360) % 360,
        });
      }
    }
    movers.sort((a, b) => b.speedArcsecPerHour - a.speedArcsecPerHour);
    movers.forEach((m, i) => (m.number = i + 1));
    return { movers, epochs: req.epochs };
  },

  async verify(req, opts) {
    const d = await loadDemo(opts?.signal);
    const steps = [
      "Checking known stars…",
      "Checking known asteroids…",
      "Checking catalogs…",
      "Checking for instrument glitches…",
    ];
    for (const s of steps) {
      opts?.onStep?.(s);
      await wait(560, opts?.signal);
    }
    return verifyBox(d, req);
  },
};

// ---------------------------------------------------------------- what is in a box

type Hit = { source: DemoSource; fraction: number };

const epochsFor = (d: Demo, id: string | "all"): DemoEpoch[] =>
  id === "all" ? d.epochs : d.epochs.filter((e) => e.id === id);

/** Sources inside the box at one epoch, with how much of each the box holds. */
function sourcesIn(d: Demo, box: SkyBox, year: number): Hit[] {
  const out: Hit[] = [];
  const halfW = box.width / 2;
  const halfH = box.height / 2;
  for (const s of d.sources) {
    const p = s.kind === "hotpixel" ? { ra: s.ra, dec: s.dec } : positionAt(s, year);
    const o = offsetDeg(box, p);
    if (Math.abs(o.east) > halfW || Math.abs(o.north) > halfH) continue;
    let fraction = 1;
    if (s.kind === "galaxy") fraction = Math.min(1, (Math.min(box.width, box.height) * 3600) / (6 * (s.reff ?? 8)));
    out.push({ source: s, fraction });
  }
  return out;
}

const totalFlux = (d: Demo, s: DemoSource, lam: number) =>
  d.flux0 * 10 ** (-0.4 * s.j) * interp(d.grid, d.spectra[s.cls], lam);

/** 2MASS-style designation from a position. Looks like the catalogue name because it is built the same way. */
function designation(prefix: string, ra: number, dec: number) {
  const h = ra / 15;
  const hh = Math.floor(h);
  const mm = Math.floor((h - hh) * 60);
  const ss = ((h - hh) * 60 - mm) * 60;
  const sign = dec < 0 ? "-" : "+";
  const a = Math.abs(dec);
  const dd = Math.floor(a);
  const dm = Math.floor((a - dd) * 60);
  const ds = ((a - dd) * 60 - dm) * 60;
  const p2 = (n: number) => String(n).padStart(2, "0");
  return `${prefix} J${p2(hh)}${p2(mm)}${p2(Math.floor(ss))}${(ss % 1).toFixed(2).slice(1)}${sign}${p2(dd)}${p2(dm)}${p2(Math.floor(ds))}${(ds % 1).toFixed(1).slice(1)}`;
}

const nameOf = (s: DemoSource) =>
  s.name ?? designation(s.kind === "galaxy" ? "2MASX" : "2MASS", s.ra, s.dec);

/** The brightest thing in the box over the epochs asked about, or null. */
function dominant(d: Demo, box: SkyBox, eps: DemoEpoch[]) {
  const weight = new Map<string, { s: DemoSource; w: number }>();
  for (const e of eps) {
    for (const h of sourcesIn(d, box, e.year)) {
      const w = (h.source.kind === "hotpixel" ? 3e3 : totalFlux(d, h.source, 1.25)) * h.fraction;
      const hit = weight.get(h.source.id);
      weight.set(h.source.id, { s: h.source, w: (hit?.w ?? 0) + w });
    }
  }
  return [...weight.values()].sort((a, b) => b.w - a.w)[0]?.s ?? null;
}

// ---------------------------------------------------------------- inspect

const FEATURES: Record<DemoSource["cls"], SpectrumFeature[]> = {
  M: [
    { label: "Water vapour", realName: "Water vapour absorption (cool star atmosphere, 1.4 µm)", wavelengthUm: 1.4 },
    { label: "Water vapour", realName: "Water vapour absorption (cool star atmosphere, 1.9 µm)", wavelengthUm: 1.9 },
    { label: "Carbon monoxide", realName: "CO absorption (4.65 µm)", wavelengthUm: 4.65 },
  ],
  K: [{ label: "Carbon monoxide", realName: "CO absorption (4.65 µm)", wavelengthUm: 4.65 }],
  G: [],
  A: [
    { label: "Hydrogen", realName: "Hydrogen line (Paschen β, 1.28 µm)", wavelengthUm: 1.28 },
    { label: "Hydrogen", realName: "Hydrogen line (Paschen α, 1.88 µm)", wavelengthUm: 1.88 },
  ],
  T: [
    { label: "Methane", realName: "Methane absorption (1.7 µm)", wavelengthUm: 1.7 },
    { label: "Methane", realName: "Methane absorption (3.3 µm)", wavelengthUm: 3.3 },
  ],
  galaxy: [{ label: "Organic dust", realName: "PAH emission (3.3 µm)", wavelengthUm: 3.3 }],
};

function inspectBox(d: Demo, req: InspectRequest): Inspection {
  const box = req.target.box;
  const eps = epochsFor(d, req.epoch);
  const pxArcsec = d.area.pixelScaleArcsec;
  // Optimal extraction: noise grows with the aperture around the object, not the whole box.
  const npix = Math.min(25, Math.max(4, ((box.width * 3600) / pxArcsec) * ((box.height * 3600) / pxArcsec)));
  const sigma = d.sigma * Math.sqrt(npix) * 1.1;

  const rand = mulberry32(hashString(`${box.ra.toFixed(5)}|${box.dec.toFixed(5)}|${req.epoch}`));
  const raw: { wavelengthUm: number; flux: number; snr: number }[] = [];
  const main = dominant(d, box, eps);
  for (const e of eps) {
    const hits = sourcesIn(d, box, e.year).filter((h) => h.source.kind !== "hotpixel");
    for (const b of e.bands) {
      const lam = e.wavelengths[b];
      if (lam === undefined) continue;
      let flux = 0;
      for (const h of hits) flux += totalFlux(d, h.source, lam) * h.fraction;
      // Brightest sources are limited by calibration (~1.5 %), faint ones by noise.
      const noise = Math.hypot(sigma, flux * 0.015);
      const measured = flux + gauss(rand) * noise;
      raw.push({ wavelengthUm: lam, flux: measured, snr: Math.abs(flux) / noise });
    }
  }
  raw.sort((a, b) => a.wavelengthUm - b.wavelengthUm);
  const peak = Math.max(1e-9, ...raw.map((p) => p.flux));
  const spectrum: Spectrum = {
    points: raw.map((p) => ({ wavelengthUm: p.wavelengthUm, flux: p.flux / peak })),
    fluxLabel: "Brightness (relative)",
    features: main ? FEATURES[main.cls] : [],
  };

  const bestSnr = Math.max(0, ...raw.map((p) => p.snr));
  const lowSignal = !main || bestSnr < 4;
  const n = raw.length;
  const few = n < 8 ? ` With only ${n} wavelength${n === 1 ? "" : "s"} for this spot, treat it as a rough guess.` : "";

  const colour = warmToStar(raw);
  const methane = methaneDip(raw);

  let type: ObjectType = "empty";
  let reason = "Not enough signal to say. Try a bigger box, or look at more bands.";
  let scores: Partial<Record<ObjectType, number>> = {};
  if (!lowSignal && main) {
    if (main.kind === "hotpixel") {
      type = "artifact";
      reason = "One detector pixel that glows the same way in every frame. Real objects don't stay put when the telescope moves.";
      scores = { artifact: 0.86, star: 0.08, "brown-dwarf": 0.03, galaxy: 0.02, asteroid: 0.01 };
    } else if (main.cls === "T") {
      type = "brown-dwarf";
      reason =
        `Faint in starlight but bright at 4 to 5 µm${methane ? `, with a methane dip (${Math.round(methane * 100)}% lower) around 1.7 µm` : ""}: ` +
        `that is what a cold brown dwarf looks like. It also shifts between observations.${few}`;
      scores = { "brown-dwarf": 0.76, star: 0.11, planet: 0.06, asteroid: 0.04, galaxy: 0.03 };
    } else if (main.cls === "galaxy") {
      type = "galaxy";
      reason = `Soft and spread out over about ${Math.round((main.reff ?? 9) * 2)} arcseconds with no sharp centre, and a bump of organic dust at 3.3 µm: that looks like a galaxy.${few}`;
      scores = { galaxy: 0.84, star: 0.09, comet: 0.03, "brown-dwarf": 0.03, artifact: 0.01 };
    } else if (main.cls === "M") {
      type = "star";
      reason =
        `A cool, red star: very bright in starlight${colour ? ` and ${colour}` : ""}, fading smoothly toward 5 µm with dips from water vapour in its atmosphere.${few}`;
      scores = { star: 0.93, "brown-dwarf": 0.04, galaxy: 0.01, asteroid: 0.01, comet: 0.01 };
    } else if (main.cls === "A") {
      type = "star";
      reason = `A hot, blue-white star: bright and smooth, with small hydrogen dips near 1.28 and 1.88 µm.${few}`;
      scores = { star: 0.95, galaxy: 0.02, "brown-dwarf": 0.01, asteroid: 0.01, comet: 0.01 };
    } else {
      type = "star";
      reason = `A star like the Sun: a bright, smooth glow that fades steadily toward longer wavelengths.${few}`;
      scores = { star: 0.94, galaxy: 0.03, "brown-dwarf": 0.01, asteroid: 0.01, comet: 0.01 };
    }
  } else {
    scores = { empty: 0.9 };
  }
  const all: ObjectType[] = ["star", "brown-dwarf", "planet", "comet", "asteroid", "galaxy", "empty", "artifact"];
  const rest = Math.max(0, 1 - Object.values(scores).reduce((a, b) => a + (b ?? 0), 0));
  const missing = all.filter((t) => scores[t] === undefined);
  const candidates: TypeScore[] = all
    .map((t) => ({ type: t, confidence: scores[t] ?? rest / Math.max(1, missing.length) }))
    .sort((a, b) => b.confidence - a.confidence);

  return { lowSignal, guess: { type, reason }, candidates, spectrum };
}

/** Mean brightness at 4 to 5 µm over mean brightness below 1.3 µm, in plain words. */
function warmToStar(points: { wavelengthUm: number; flux: number }[]) {
  const warm = points.filter((p) => p.wavelengthUm >= 3.8);
  const near = points.filter((p) => p.wavelengthUm <= 1.3);
  if (!warm.length || !near.length) return null;
  const ratio = mean(warm.map((p) => p.flux)) / mean(near.map((p) => p.flux));
  if (!(ratio > 0)) return null;
  return `about ${Math.round(ratio * 100)}% as bright at 4 to 5 µm`;
}

/** How far the 1.7 µm sample sits below the 1.25 µm one, 0..1. Null if either is missing. */
function methaneDip(points: { wavelengthUm: number; flux: number }[]) {
  const a = points.filter((p) => Math.abs(p.wavelengthUm - 1.7) < 0.1);
  const b = points.filter((p) => p.wavelengthUm >= 1.0 && p.wavelengthUm <= 1.3);
  if (!a.length || !b.length) return null;
  const dip = 1 - mean(a.map((p) => p.flux)) / mean(b.map((p) => p.flux));
  return dip > 0.2 ? Math.min(0.95, dip) : null;
}

const mean = (xs: number[]) => xs.reduce((a, b) => a + b, 0) / xs.length;

// ---------------------------------------------------------------- verify

function verifyBox(d: Demo, req: InspectRequest & { moverId?: string }): VerifyOutcome {
  const box = req.target.box;
  const eps = epochsFor(d, req.epoch);
  const byId = req.moverId ? d.sources.find((s) => s.id === req.moverId) : null;
  const main = byId ?? dominant(d, box, eps);

  if (!main) return { outcome: "artifact", headline: "Nothing here to check", reason: "There is no signal in this box, so there is nothing to match.", flag: "No detection" };

  if (main.kind === "hotpixel")
    return {
      outcome: "artifact",
      headline: "Not a real object",
      reason: "It is one detector pixel that glows in every frame. Real objects don't stay in the same pixel when the telescope moves.",
      flag: "Instrument flag: hot pixel",
    };

  if (main.id === BARNARD)
    return {
      outcome: "explained",
      headline: "Known star",
      name: "Barnard's Star (GJ 699)",
      fact: req.moverId
        ? "A red dwarf 6 light-years away. Its path across these dates matches its known motion of 10.3 arcseconds a year, north."
        : "A red dwarf 6 light-years away, and the star that moves fastest across our sky: 10.3 arcseconds a year.",
      source: "SIMBAD",
      objectType: "star",
    };

  if (main.id === FIND) {
    // The closest steady catalogue star, as a near miss.
    const here = positionAt(main, d.epochs[d.epochs.length - 1].year);
    const near = d.sources
      .filter((s) => s.kind === "star" && s.id !== BARNARD)
      .map((s) => ({ s, sep: separationDeg(s, here) * 3600 }))
      .sort((a, b) => a.sep - b.sep)[0];
    return {
      outcome: "unexplained",
      headline: "We can't match this to anything known",
      nearMatch: near
        ? {
            name: nameOf(near.s),
            source: "2MASS",
            note: `${Math.round(near.sep)} arcseconds away. It's a steady star, and this one moves.`,
          }
        : undefined,
    };
  }

  if (main.kind === "galaxy")
    return {
      outcome: "explained",
      headline: "Known galaxy",
      name: nameOf(main),
      fact: `Listed in the catalog as an extended source about ${Math.round((main.reff ?? 9) * 2)} arcseconds across.`,
      source: "SIMBAD",
      objectType: "galaxy",
    };

  return {
    outcome: "explained",
    headline: "Known star",
    name: nameOf(main),
    fact: `Listed in the catalog at this position (J = ${main.j.toFixed(1)}). It doesn't move noticeably.`,
    source: "SIMBAD",
    objectType: "star",
  };
}

export type { SkyBox };
