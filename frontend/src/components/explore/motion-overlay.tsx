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

/**
 * Motion results: for each mover a point per epoch, a path joining them, and
 * a marker that sits where the mover is at the playhead's date. One colour for
 * all tracks, ember for the selected one. Drawn above everything.
 */
export function MotionOverlay({ proj }: { proj: Projection }) {
  const ex = useExplore();
  const [hover, setHover] = useState<string | null>(null);
  if (ex.motion.status !== "done" || !ex.playheadEpoch) return null;
  const time = Date.parse(ex.playheadEpoch.date);

  return (
    <g style={{ opacity: ex.outdated ? 0.3 : 1, transition: "opacity 200ms" }}>
      {ex.movers.map((m) => {
        const pts = m.points.map((p) => proj.toScreen(p.ra, p.dec));
        const d = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
        const selected = m.id === ex.moverId;
        const active = selected || hover === m.id;
        const color = selected ? "var(--color-ember)" : "var(--color-ink)";
        const now = positionAt(m, time);
        const [mx, my] = proj.toScreen(now.ra, now.dec);
        const first = pts[0];
        const quiet = !active && ex.moverId !== null; // something else is picked
        return (
          <g key={m.id} style={{ opacity: quiet ? 0.45 : 1 }}>
            {/* One thin line. Dots only at the two ends, so a track reads as a path. */}
            <path d={d} fill="none" stroke="var(--color-ground)" strokeOpacity={0.6} strokeWidth={active ? 4 : 3} strokeLinejoin="round" />
            <path d={d} fill="none" stroke={color} strokeWidth={active ? 2 : 1.25} strokeLinejoin="round" strokeDasharray={active ? undefined : "4 3"} />
            {/* The number sits at the start, always, so the list and the picture match. */}
            <g transform={`translate(${first[0]}, ${first[1]})`}>
              <circle r={10} fill="var(--color-ground)" stroke={color} strokeWidth={1.5} />
              <text y={4} textAnchor="middle" className="font-mono" fill={color} fontSize={11}>
                {m.number}
              </text>
            </g>
            {/* This animated position is interpolated; only dots at measured epochs are observations. */}
            <g
              style={{
                transform: `translate(${mx}px, ${my}px)`,
                transition: ex.playing ? "transform 700ms cubic-bezier(0.2, 0.7, 0.2, 1)" : "none",
              }}
            >
              <circle r={6} fill="none" stroke={color} strokeWidth={1.5} />
              <circle r={2} fill={color} />
            </g>
            <path
              d={d}
              fill="none"
              stroke="transparent"
              strokeWidth={18}
              style={{ pointerEvents: "stroke", cursor: "pointer" }}
              onPointerEnter={() => setHover(m.id)}
              onPointerLeave={() => setHover((h) => (h === m.id ? null : h))}
              onPointerDown={(e) => e.stopPropagation()}
              onClick={() => ex.selectMover(m.id)}
            />
            <circle
              cx={first[0]}
              cy={first[1]}
              r={14}
              fill="transparent"
              style={{ pointerEvents: "all", cursor: "pointer" }}
              onPointerEnter={() => setHover(m.id)}
              onPointerLeave={() => setHover((h) => (h === m.id ? null : h))}
              onPointerDown={(e) => e.stopPropagation()}
              onClick={() => ex.selectMover(m.id)}
            />
          </g>
        );
      })}
    </g>
  );
}
