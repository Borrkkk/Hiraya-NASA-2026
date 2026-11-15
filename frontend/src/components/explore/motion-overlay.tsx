"use client";

import { useState } from "react";
import type { Projection } from "@/lib/explore/projection";
import type { Mover } from "@/lib/explore/types";
import { useExplore } from "./use-explore";

/** Estimated position between observations (not a measured position). */
function positionAt(m: Mover, time: number) {
  const pts = m.points;
  const t = (i: number) => Date.parse(pts[i].date);
  if (time <= t(0)) return pts[0];
  if (time >= t(pts.length - 1)) return pts[pts.length - 1];
  for (let i = 0; i < pts.length - 1; i++) {
    if (time >= t(i) && time <= t(i + 1)) {
      const k = (time - t(i)) / (t(i + 1) - t(i));
      return { ra: pts[i].ra + (pts[i + 1].ra - pts[i].ra) * k, dec: pts[i].dec + (pts[i + 1].dec - pts[i].dec) * k };
    }
  }
  return pts[0];
}

function pathFor(points: [number, number][]) {
  return points.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
}

/**
 * Show ONE position per candidate: its current location at the chosen date.
 * The dashed trail is history, not another object. Do not place a fixed marker
 * at the first epoch; it looks like a second star when the playhead advances.
 */
export function MotionOverlay({ proj }: { proj: Projection }) {
  const ex = useExplore();
  const [hover, setHover] = useState<string | null>(null);
  if (ex.motion.status !== "done" || !ex.playheadEpoch) return null;
  const time = Date.parse(ex.playheadEpoch.date);

  return (
    <g style={{ opacity: ex.outdated ? 0.3 : 1, transition: "opacity 200ms" }}>
      {ex.movers.map((m) => {
        if (!m.points.length) return null;
        const selected = m.id === ex.moverId;
        const active = selected || hover === m.id;
        const color = selected ? "var(--color-ember)" : "var(--color-ink)";
        const now = positionAt(m, time);
        const [mx, my] = proj.toScreen(now.ra, now.dec);
        const history: [number, number][] = m.points
          .filter((p) => Date.parse(p.date) < time)
          .map((p) => proj.toScreen(p.ra, p.dec));
        const trail = history.length ? pathFor([...history, [mx, my]]) : null;
        const quiet = !active && ex.moverId !== null;
        const select = () => ex.selectMover(m.id);

        return (
          <g key={m.id} style={{ opacity: quiet ? 0.45 : 1 }}>
            {/* Only earlier positions make a trail; future points are not shown. */}
            {trail && (
              <>
                <path d={trail} fill="none" stroke="var(--color-ground)" strokeOpacity={0.7} strokeWidth={active ? 4 : 3} strokeLinejoin="round" />
                <path d={trail} fill="none" stroke={color} strokeWidth={active ? 2 : 1.5} strokeDasharray="4 4" strokeLinejoin="round" />
                <path d={trail} fill="none" stroke="transparent" strokeWidth={18}
                  style={{ pointerEvents: "stroke", cursor: "pointer" }}
                  onPointerEnter={() => setHover(m.id)}
                  onPointerLeave={() => setHover((h) => (h === m.id ? null : h))}
                  onPointerDown={(e) => e.stopPropagation()}
                  onClick={select}
                />
              </>
            )}
            {/* One numbered marker follows the timeline; no marker remains at the start. */}
            <g
              style={{
                transform: `translate(${mx}px, ${my}px)`,
                transition: ex.playing ? "transform 700ms cubic-bezier(0.2, 0.7, 0.2, 1)" : "none",
                pointerEvents: "all",
                cursor: "pointer",
              }}
              onPointerEnter={() => setHover(m.id)}
              onPointerLeave={() => setHover((h) => (h === m.id ? null : h))}
              onPointerDown={(e) => e.stopPropagation()}
              onClick={select}
            >
              <circle r={active ? 15 : 13} fill="none" stroke={color} strokeOpacity={0.55} strokeWidth={1} />
              <circle r={10} fill="var(--color-ground)" stroke={color} strokeWidth={1.5} />
              <text y={4} textAnchor="middle" className="font-mono" fill={color} fontSize={11} pointerEvents="none">
                {m.number}
              </text>
            </g>
          </g>
        );
      })}
    </g>
  );
}
