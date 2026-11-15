import type { ObjectKind } from "@/lib/sky/catalog";

export type ExploreTarget = {
  /** Free-text name, shown in the explore page's search box. */
  q?: string;
  ra?: number;
  dec?: number;
  /** Field of view in degrees. */
  fov?: number;
  types?: ObjectKind[];
};

/**
 * The one place that builds links into exploration mode. Everything on the
 * home screen (search, feed cards, a click on the map) goes through here, so
 * wiring up the real page later is a one-file change.
 */
export function exploreHref({ q, ra, dec, fov, types }: ExploreTarget = {}) {
  const p = new URLSearchParams();
  if (q?.trim()) p.set("q", q.trim());
  if (ra !== undefined && dec !== undefined) {
    p.set("ra", ra.toFixed(4));
    p.set("dec", dec.toFixed(4));
  }
  if (fov !== undefined) p.set("fov", String(Number(fov.toFixed(3))));
  if (types?.length) p.set("types", types.join(","));
  const qs = p.toString();
  return qs ? `/explore?${qs}` : "/explore";
}
