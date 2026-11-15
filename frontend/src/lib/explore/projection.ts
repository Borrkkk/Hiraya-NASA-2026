// Sky <-> screen maths for the Explore view. Gnomonic (tangent-plane), north
// up, east LEFT, like a printed sky map. Pure functions, no DOM.

import type { Area, SkyBox, SkyPoint } from "./types";

const D2R = Math.PI / 180;
const R2D = 180 / Math.PI;

export type View = SkyPoint & {
  /** Horizontal field of view in degrees. */
  fov: number;
};

export type Projection = {
  /** px per tangent-plane unit. */
  scale: number;
  toScreen: (ra: number, dec: number) => [number, number];
  toSky: (x: number, y: number) => [number, number];
};

export function makeProjection(view: View, width: number, height: number): Projection {
  const scale = width / 2 / Math.tan((view.fov * D2R) / 2);
  const ra0 = view.ra * D2R;
  const dec0 = view.dec * D2R;
  const sin0 = Math.sin(dec0);
  const cos0 = Math.cos(dec0);

  return {
    scale,
    toScreen(ra, dec) {
      const a = ra * D2R - ra0;
      const d = dec * D2R;
      const cosc = sin0 * Math.sin(d) + cos0 * Math.cos(d) * Math.cos(a);
      const xi = (Math.cos(d) * Math.sin(a)) / cosc;
      const eta = (cos0 * Math.sin(d) - sin0 * Math.cos(d) * Math.cos(a)) / cosc;
      return [width / 2 - scale * xi, height / 2 - scale * eta];
    },
    toSky(x, y) {
      const xi = (width / 2 - x) / scale;
      const eta = (height / 2 - y) / scale;
      const rho = Math.hypot(xi, eta);
      if (rho === 0) return [view.ra, view.dec];
      const c = Math.atan(rho);
      const dec = Math.asin(Math.cos(c) * sin0 + (eta * Math.sin(c) * cos0) / rho);
      const ra = ra0 + Math.atan2(xi * Math.sin(c), rho * cos0 * Math.cos(c) - eta * sin0 * Math.sin(c));
      return [(((ra * R2D) % 360) + 360) % 360, dec * R2D];
    },
  };
}

/** The projection of a server frame: it covers `extentDeg`, `sizePx` square. */
export function frameProjection(area: Pick<Area, "center" | "extentDeg" | "sizePx">) {
  return makeProjection({ ...area.center, fov: area.extentDeg }, area.sizePx, area.sizePx);
}

/**
 * The canvas transform that draws a frame (in its own pixels) onto the screen.
 * Frame projection and view projection are both tangent planes, just with
 * different centres, so they differ slightly. We fit an exact affine at the
 * view centre, where the user is looking, so errors only grow at the screen
 * edges and stay small for fields up to a few degrees.
 */
export function frameTransform(
  area: Pick<Area, "center" | "extentDeg" | "sizePx">,
  view: View,
  width: number,
  height: number,
): [number, number, number, number, number, number] {
  const fp = frameProjection(area);
  const vp = makeProjection(view, width, height);
  // Where the view centre falls in the frame.
  const [u0, v0] = fp.toScreen(view.ra, view.dec);
  const step = 100;
  const at = (u: number, v: number) => {
    const [ra, dec] = fp.toSky(u, v);
    return vp.toScreen(ra, dec);
  };
  const s0 = at(u0, v0);
  const s1 = at(u0 + step, v0);
  const s2 = at(u0, v0 + step);
  const a = (s1[0] - s0[0]) / step;
  const b = (s1[1] - s0[1]) / step;
  const c = (s2[0] - s0[0]) / step;
  const d = (s2[1] - s0[1]) / step;
  return [a, b, c, d, s0[0] - a * u0 - c * v0, s0[1] - b * u0 - d * v0];
}

/** Angular separation in degrees. */
export function separationDeg(a: SkyPoint, b: SkyPoint) {
  const d1 = a.dec * D2R;
  const d2 = b.dec * D2R;
  const dra = (a.ra - b.ra) * D2R;
  const x = Math.sin(d1) * Math.sin(d2) + Math.cos(d1) * Math.cos(d2) * Math.cos(dra);
  return Math.acos(Math.min(1, Math.max(-1, x))) * R2D;
}

/** Offset (degrees, on the sky) of `p` from `origin`, east positive. Small-field. */
export function offsetDeg(origin: SkyPoint, p: SkyPoint) {
  let dra = p.ra - origin.ra;
  if (dra > 180) dra -= 360;
  if (dra < -180) dra += 360;
  return { east: dra * Math.cos(origin.dec * D2R), north: p.dec - origin.dec };
}

/** Move a point by (east, north) degrees on the sky. Small-field. */
export function shiftPoint(origin: SkyPoint, east: number, north: number): SkyPoint {
  const dec = Math.max(-89.999, Math.min(89.999, origin.dec + north));
  const ra = origin.ra + east / Math.max(0.01, Math.cos(origin.dec * D2R));
  return { ra: ((ra % 360) + 360) % 360, dec };
}

export function clamp(v: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, v));
}

/** Keep the view's centre inside the area so the user can't pan off the data. */
export function clampView(view: View, area: Pick<Area, "center" | "extentDeg">): View {
  const limit = Math.max(0, area.extentDeg / 2 - view.fov / 2) + view.fov * 0.15;
  const o = offsetDeg(area.center, view);
  const east = clamp(o.east, -limit, limit);
  const north = clamp(o.north, -limit, limit);
  if (east === o.east && north === o.north) return view;
  return { ...shiftPoint(area.center, east, north), fov: view.fov };
}

export function boxContains(box: SkyBox, p: SkyPoint) {
  const o = offsetDeg(box, p);
  return Math.abs(o.east) <= box.width / 2 && Math.abs(o.north) <= box.height / 2;
}
