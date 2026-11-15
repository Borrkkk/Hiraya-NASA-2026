import { BANDS, DEFAULT_BANDS } from "./bands";
import type { AreaRequest, BandId } from "./types";

// The page's shareable state lives in the URL, so "Copy link" is just the
// current address. The home screen builds the first version of this URL
// (lib/explore.ts), and the page keeps it up to date as the user moves.

export type ExploreParams = {
  target: AreaRequest;
  /** Current camera position; distinct from the centre of the loaded data. */
  view: AreaRequest;
  /** Name from the search box or feed card, if any. */
  q: string | null;
  bands: BandId[];
  epoch: string | null;
  layer: string | null;
  /** True when the URL had no position and we fell back to a default. */
  fallback: boolean;
};

// Orion Nebula: where we start when someone opens /explore with nothing.
const FALLBACK: AreaRequest = { ra: 83.82, dec: -5.39, fov: 2 };

export function readParams(p: URLSearchParams): ExploreParams {
  const ra = Number(p.get("ra"));
  const dec = Number(p.get("dec"));
  const fov = Number(p.get("fov"));
  const hasPos = p.has("ra") && p.has("dec") && Number.isFinite(ra) && Number.isFinite(dec);
  const target = hasPos
    ? { ra, dec, fov: Number.isFinite(fov) && fov > 0 ? fov : 1 }
    : FALLBACK;
  const viewRa = Number(p.get("viewRa"));
  const viewDec = Number(p.get("viewDec"));
  const viewFov = Number(p.get("viewFov"));
  const hasView = p.has("viewRa") && p.has("viewDec") &&
    Number.isFinite(viewRa) && Number.isFinite(viewDec);
  const view = hasView
    ? { ra: viewRa, dec: viewDec, fov: Number.isFinite(viewFov) && viewFov > 0 ? viewFov : target.fov }
    : target;
  const ids = new Set(BANDS.map((b) => b.id));
  const bands = (p.get("bands") ?? "").split(",").filter((b): b is BandId => ids.has(b as BandId));
  return {
    target,
    view,
    q: p.get("q"),
    bands: bands.length ? bands : DEFAULT_BANDS,
    epoch: p.get("epoch"),
    layer: p.get("layer"),
    fallback: !hasPos,
  };
}

export function writeParams(
  base: URLSearchParams,
  s: { ra: number; dec: number; fov: number; bands: BandId[]; epoch: string | null; layer: string | null },
) {
  const p = new URLSearchParams(base);
  // Keep ra/dec/fov identifying the requested DATA location. Updating them
  // whenever the user pans made the URL point to a different target while
  // the old images were still on screen, and could reset the Explore page.
  // Persist camera movement separately for copy-link and page refresh.
  p.set("viewRa", s.ra.toFixed(5));
  p.set("viewDec", s.dec.toFixed(5));
  p.set("viewFov", String(Number(s.fov.toFixed(3))));
  p.set("bands", s.bands.join(","));
  if (s.epoch) p.set("epoch", s.epoch);
  else p.delete("epoch");
  if (s.layer) p.set("layer", s.layer);
  else p.delete("layer");
  return p;
}
