// Field-of-view language and limits.

/** Everyday objects held at arm's length, with their apparent size in degrees. */
const MOON = 0.5;
const THUMB = 2;
const FIST = 10;

/** Stop at about this many screen pixels per SPHEREx pixel (spec Q9, to be tuned). */
export const MIN_SCREEN_PX_PER_SKY_PX = 4;

export function fovLabel(fov: number): { main: string; real: string } {
  const real = `${fov >= 10 ? fov.toFixed(0) : fov.toFixed(fov >= 1 ? 1 : 2)}° × ${
    fov >= 10 ? fov.toFixed(0) : fov.toFixed(fov >= 1 ? 1 : 2)
  }°`;
  const moons = fov / MOON;
  if (moons >= 1 && moons <= 20) return { main: `about ${plural(moons, "full moon")} wide`, real };
  if (moons > 20) {
    const t = fov / THUMB;
    if (t <= 20) return { main: `about ${plural(t, "thumb")} wide at arm's length`, real };
    return { main: `about ${plural(fov / FIST, "fist")} wide at arm's length`, real };
  }
  return { main: `${fraction(moons)} of a full moon wide`, real };
}

function plural(n: number, noun: string) {
  const r = n < 3 ? Math.round(n * 2) / 2 : Math.round(n);
  const word = r === 1 ? `1 ${noun}` : `${r % 1 ? r.toFixed(1) : r} ${noun}s`;
  return word.replace("thumbs", "thumbs");
}

function fraction(x: number) {
  if (x >= 0.8) return "nearly the width";
  if (x >= 0.6) return "about two thirds";
  if (x >= 0.4) return "about half";
  if (x >= 0.28) return "about a third";
  if (x >= 0.2) return "about a quarter";
  return `about 1/${Math.round(1 / x)}`;
}

/** The zoom range for an area and a view this wide on screen. */
export function fovLimits(
  area: { extentDeg: number; pixelScaleArcsec: number },
  viewWidthPx: number,
) {
  const closest = ((viewWidthPx / MIN_SCREEN_PX_PER_SKY_PX) * area.pixelScaleArcsec) / 3600;
  const widest = area.extentDeg;
  return { min: Math.min(closest, widest), max: widest };
}

/** Slider position (0 = widest, 1 = closest) from a field of view, on a log scale. */
export const fovToT = (fov: number, min: number, max: number) =>
  max <= min ? 1 : Math.log(max / fov) / Math.log(max / min);

export const tToFov = (t: number, min: number, max: number) => max * Math.pow(min / max, t);
