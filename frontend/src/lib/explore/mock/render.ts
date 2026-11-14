// Draws the mock frames: one greyscale canvas per band and epoch. MOCK ONLY.

import { frameProjection } from "../projection";
import type { BandId } from "../types";
import { moverPosition, type Cloud, type SkyModel } from "./sky-model";
import { gauss, mulberry32 } from "./rng";

let sprite: HTMLCanvasElement | null = null;
function starSprite() {
  if (sprite) return sprite;
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const g = c.getContext("2d")!;
  const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  grad.addColorStop(0, "rgba(255,255,255,1)");
  grad.addColorStop(0.18, "rgba(255,255,255,0.75)");
  grad.addColorStop(0.5, "rgba(255,255,255,0.14)");
  grad.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = grad;
  g.fillRect(0, 0, 64, 64);
  return (sprite = c);
}

const layerCache = new Map<string, HTMLCanvasElement>();

/** Clouds don't change between epochs, so draw them once per band. */
function cloudLayer(model: SkyModel, band: BandId, id: string) {
  const key = `${id}|${band}`;
  const hit = layerCache.get(key);
  if (hit) return hit;
  const { sizePx, extentDeg } = model.area;
  const c = document.createElement("canvas");
  c.width = c.height = sizePx;
  const g = c.getContext("2d")!;
  g.fillStyle = "#000";
  g.fillRect(0, 0, sizePx, sizePx);
  g.globalCompositeOperation = "lighter";
  const fp = frameProjection(model.area);
  const pxPerDeg = sizePx / extentDeg;
  const rand = mulberry32(model.seed ^ band.length * 7919);

  const puffs = (b: Cloud, radiusScale: number, alpha: number, ring = false) => {
    const [cx, cy] = fp.toScreen(b.ra, b.dec);
    const r = b.r * pxPerDeg * radiusScale;
    for (let i = 0; i < 34; i++) {
      const a = rand() * Math.PI * 2;
      const dist = ring ? r * (0.7 + rand() * 0.25) : Math.abs(gauss(rand)) * r * 0.5;
      const x = cx + Math.cos(a) * dist;
      const y = cy + Math.sin(a) * dist;
      const pr = r * (ring ? 0.22 : 0.3 + rand() * 0.4);
      const grad = g.createRadialGradient(x, y, 0, x, y, pr);
      const k = alpha * b.strength * (0.5 + rand() * 0.5);
      grad.addColorStop(0, `rgba(255,255,255,${k})`);
      grad.addColorStop(1, "rgba(255,255,255,0)");
      g.fillStyle = grad;
      g.fillRect(x - pr, y - pr, pr * 2, pr * 2);
    }
  };

  for (const b of model.blobs) {
    if (b.kind === "emission") {
      if (band === "hydrogen") puffs(b, 1, 0.1);
      if (band === "helium") puffs(b, 0.5, 0.1);
      if (band === "warm-glow") puffs(b, 1.4, 0.05);
      if (band === "organic-dust") puffs(b, 1.2, 0.08, true);
    } else if (b.kind === "dark") {
      if (band === "water-ice") puffs(b, 1, 0.11);
      if (band === "co2-ice") puffs(b, 0.8, 0.1);
      if (band === "co-ice") puffs(b, 0.55, 0.12);
      if (band === "warm-glow") puffs(b, 1, 0.025);
    } else {
      if (band === "starlight") puffs(b, 1, 0.1);
      if (band === "warm-glow") puffs(b, 0.8, 0.04);
    }
  }
  layerCache.set(key, c);
  return c;
}

/** Render one frame to a JPEG blob. */
export async function renderFrame(
  model: SkyModel,
  id: string,
  epochId: string,
  band: BandId,
): Promise<Blob> {
  const { sizePx } = model.area;
  const c = document.createElement("canvas");
  c.width = c.height = sizePx;
  const g = c.getContext("2d")!;
  g.fillStyle = "#000";
  g.fillRect(0, 0, sizePx, sizePx);
  g.drawImage(cloudLayer(model, band, id), 0, 0);
  g.globalCompositeOperation = "lighter";

  const fp = frameProjection(model.area);
  const spr = starSprite();
  const epoch = model.epochs.find((e) => e.id === epochId)!;
  const jitter = mulberry32(model.seed ^ epoch.years.toString().length * 31 ^ band.length);

  const stamp = (ra: number, dec: number, size: number, intensity: number) => {
    const [x, y] = fp.toScreen(ra, dec);
    if (x < -40 || y < -40 || x > sizePx + 40 || y > sizePx + 40) return;
    const d = size * 8;
    g.globalAlpha = Math.min(1, intensity * 1.5);
    g.drawImage(spr, x - d / 2, y - d / 2, d, d);
  };

  for (const s of model.stars) {
    const f = s.flux[band];
    if (f > 0.01) stamp(s.ra, s.dec, s.size, f * (0.96 + jitter() * 0.08));
  }
  for (const m of model.movers) {
    const f = m.flux[band];
    if (f <= 0.01) continue;
    const p = moverPosition(m, epoch.years);
    stamp(p.ra, p.dec, 3.6, f);
  }
  g.globalAlpha = 1;

  return new Promise((resolve, reject) =>
    c.toBlob((b) => (b ? resolve(b) : reject(new Error("Could not encode frame"))), "image/jpeg", 0.88),
  );
}
