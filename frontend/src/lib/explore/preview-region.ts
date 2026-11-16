// The preview opens one patch of sky: Barnard's Star and what is around it.
// Everything else (search results, feed cards, pasted links, coordinates) lands
// on a short explanation with a button into that region.

import { exploreHref } from "./href";

export const PREVIEW_NAME = "Barnard's Star";
export const PREVIEW_CENTRE = { ra: 269.4463, dec: 4.7682 };
/** Anything this close to the centre is inside the data we ship. */
const PREVIEW_RADIUS_DEG = 0.6;

export const previewHref = () =>
  exploreHref({ q: PREVIEW_NAME, ra: PREVIEW_CENTRE.ra, dec: PREVIEW_CENTRE.dec, fov: 0.2 });

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();

function separationDeg(ra1: number, dec1: number, ra2: number, dec2: number) {
  const d = ((((ra2 - ra1 + 180) % 360) + 360) % 360) - 180;
  const a = (dec1 * Math.PI) / 180;
  const b = (dec2 * Math.PI) / 180;
  const h = Math.sin((b - a) / 2) ** 2 + Math.cos(a) * Math.cos(b) * Math.sin((d * Math.PI) / 360) ** 2;
  return (2 * Math.asin(Math.sqrt(Math.min(1, Math.max(0, h)))) * 180) / Math.PI;
}

/** True when a requested target (from the URL) is inside the preview region. */
export function inPreviewRegion(p: { q?: string | null; ra?: string | null; dec?: string | null }) {
  const ra = Number(p.ra);
  const dec = Number(p.dec);
  if (p.ra != null && p.dec != null && Number.isFinite(ra) && Number.isFinite(dec))
    return separationDeg(ra, dec, PREVIEW_CENTRE.ra, PREVIEW_CENTRE.dec) <= PREVIEW_RADIUS_DEG;
  if (p.q && p.q.trim()) {
    const q = norm(p.q);
    return q.includes("barnard") || q === "gj 699" || q === "gj699";
  }
  return true; // nothing asked for: start at Barnard's Star
}
