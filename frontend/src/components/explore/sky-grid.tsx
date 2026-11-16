"use client";

import { useMemo } from "react";
import type { Projection } from "@/lib/explore/projection";
import { useStore } from "@/lib/explore/store";
import { useExplore } from "./use-explore";

/** Grid spacings in arcseconds, plain numbers a person can read off. */
const STEPS = [2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600];

const label = (arcsec: number) =>
  arcsec >= 3600 ? `${arcsec / 3600}°` : arcsec >= 60 ? `${arcsec / 60}′` : `${arcsec}″`;

/**
 * A grid fixed to the sky (lines of equal RA and Dec), so when something moves
 * between observations it visibly crosses squares while the stars stay put.
 * Spacing follows the zoom; the legend says how big one square is.
 */
export function SkyGrid({ proj }: { proj: Projection }) {
  const ex = useExplore();
  const size = useStore(ex.sizeStore);
  const view = useStore(ex.viewStore);

  const grid = useMemo(() => {
    const { w, h } = size;
    if (!w || !h) return null;
    // About fourteen squares across the view, fine enough to see a few arcseconds of movement.
    const wantArcsec = (view.fov * 3600) / 14;
    const step = STEPS.find((s) => s >= wantArcsec) ?? STEPS[STEPS.length - 1];
    const d = step / 3600; // degrees
    const cosd = Math.max(0.05, Math.cos((view.dec * Math.PI) / 180));
    // The sky area on screen, with a margin so lines run off the edges.
    const corners = [proj.toSky(0, 0), proj.toSky(w, 0), proj.toSky(0, h), proj.toSky(w, h)];
    const decs = corners.map((c) => c[1]);
    const dec0 = Math.min(...decs) - d;
    const dec1 = Math.max(...decs) + d;
    const unwrapped = corners.map(([ra]) => ((ra - view.ra + 540) % 360) - 180 + view.ra);
    const ra0 = Math.min(...unwrapped) - d / cosd;
    const ra1 = Math.max(...unwrapped) + d / cosd;
    const dRa = d / cosd;

    const lines: { key: string; pts: string; strong: boolean }[] = [];
    const path = (f: (t: number) => [number, number], n = 16) => {
      const pts: string[] = [];
      for (let i = 0; i <= n; i++) {
        const [ra, dec] = f(i / n);
        const [x, y] = proj.toScreen(ra, dec);
        pts.push(`${x.toFixed(1)},${y.toFixed(1)}`);
      }
      return pts.join(" ");
    };
    for (let k = Math.ceil(dec0 / d); k * d <= dec1 && lines.length < 80; k++) {
      lines.push({ key: `d${k}`, strong: k % 5 === 0, pts: path((t) => [ra0 + (ra1 - ra0) * t, k * d]) });
    }
    for (let k = Math.ceil(ra0 / dRa); k * dRa <= ra1 && lines.length < 160; k++) {
      lines.push({ key: `r${k}`, strong: k % 5 === 0, pts: path((t) => [k * dRa, dec0 + (dec1 - dec0) * t]) });
    }
    return { lines, step };
  }, [proj, size, view]);

  if (!grid) return null;
  return (
    <g aria-hidden="true">
      {grid.lines.map((l) => (
        <polyline key={l.key} points={l.pts} fill="none" stroke="var(--color-ink)" strokeOpacity={l.strong ? 0.3 : 0.14} strokeWidth={1} vectorEffect="non-scaling-stroke" />
      ))}
      <g transform={`translate(12, ${size.h - 48})`}>
        <text fontSize={11} className="font-mono" fill="var(--color-ink)" stroke="var(--color-ground)" strokeWidth={3} paintOrder="stroke" opacity={0.85}>
          Grid · one square = {label(grid.step)}
        </text>
      </g>
    </g>
  );
}
