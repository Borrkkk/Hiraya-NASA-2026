"use client";

import { useEffect, useRef } from "react";
import { type Projection } from "@/lib/explore/projection";
import type { SkyBox } from "@/lib/explore/types";

const D2R = Math.PI / 180;
const R2D = 180 / Math.PI;
const MIN = 10;

type Rect = { x: number; y: number; w: number; h: number };
type Handle = "move" | "nw" | "ne" | "sw" | "se";

const rectOf = (box: SkyBox, proj: Projection): Rect => {
  const [cx, cy] = proj.toScreen(box.ra, box.dec);
  const w = box.width * D2R * proj.scale;
  const h = box.height * D2R * proj.scale;
  return { x: cx - w / 2, y: cy - h / 2, w, h };
};

const boxOf = (r: Rect, proj: Projection): SkyBox => {
  const [ra, dec] = proj.toSky(r.x + r.w / 2, r.y + r.h / 2);
  return { ra, dec, width: (r.w / proj.scale) * R2D, height: (r.h / proj.scale) * R2D };
};

/**
 * The selection box: ember outline, a faint ember wash, four corner handles.
 * Drag inside to move, drag a corner to resize. Edits are kept local while
 * dragging and committed on release, so the object panel doesn't recompute
 * on every pixel.
 */
export function SelectionBox({
  box,
  proj,
  onChange,
  clientToLocal,
  onDraft,
  bodyDraggable = true,
}: {
  box: SkyBox;
  proj: Projection;
  onChange: (b: SkyBox) => void;
  clientToLocal: (e: { clientX: number; clientY: number }) => { x: number; y: number };
  /** Reports the box mid-drag (null when done), so the parent can draw it. */
  onDraft: (b: SkyBox | null) => void;
  /** Whether the box body moves it. Off while selecting, so a drag there draws a new box. */
  bodyDraggable?: boolean;
}) {
  const r = rectOf(box, proj);
  const drag = useRef<{ handle: Handle; x: number; y: number; start: Rect; last: Rect } | null>(null);

  const down = (e: React.PointerEvent, handle: Handle) => {
    e.stopPropagation();
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
    const p = clientToLocal(e);
    drag.current = { handle, x: p.x, y: p.y, start: r, last: r };
    // Backstop: a release outside the handle is still heard by the window.
    window.addEventListener("pointerup", cancel, { once: true });
    window.addEventListener("pointercancel", cancel, { once: true });
  };
  // Same rule as the sky view: a drag always ends, even if the release is lost.
  const cancel = () => {
    if (!drag.current) return;
    drag.current = null;
    onDraft(null);
  };
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && cancel();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const move = (e: React.PointerEvent) => {
    const d = drag.current;
    if (!d) return;
    const p = clientToLocal(e);
    const dx = p.x - d.x;
    const dy = p.y - d.y;
    let { x, y, w, h } = d.start;
    if (d.handle === "move") {
      x += dx;
      y += dy;
    } else {
      const west = d.handle === "nw" || d.handle === "sw";
      const north = d.handle === "nw" || d.handle === "ne";
      if (west) {
        w = Math.max(MIN, d.start.w - dx);
        x = d.start.x + d.start.w - w;
      } else w = Math.max(MIN, d.start.w + dx);
      if (north) {
        h = Math.max(MIN, d.start.h - dy);
        y = d.start.y + d.start.h - h;
      } else h = Math.max(MIN, d.start.h + dy);
    }
    d.last = { x, y, w, h };
    onDraft(boxOf(d.last, proj));
  };
  const up = () => {
    const d = drag.current;
    drag.current = null;
    if (!d) return;
    onChange(boxOf(d.last, proj));
    onDraft(null);
  };

  const corners: [Handle, number, number, string][] = [
    ["nw", r.x, r.y, "nwse-resize"],
    ["ne", r.x + r.w, r.y, "nesw-resize"],
    ["sw", r.x, r.y + r.h, "nesw-resize"],
    ["se", r.x + r.w, r.y + r.h, "nwse-resize"],
  ];

  return (
    <g>
      <rect
        x={r.x}
        y={r.y}
        width={r.w}
        height={r.h}
        fill="var(--color-ember-band)"
        stroke="var(--color-ember)"
        strokeWidth={1.5}
        style={{ pointerEvents: bodyDraggable ? "all" : "none", cursor: "move" }}
        onPointerDown={(e) => down(e, "move")}
        onPointerMove={move}
        onPointerUp={up}
        onPointerCancel={cancel}
      />
      {corners.map(([h, x, y, cursor]) => (
        <rect
          key={h}
          x={x - 5}
          y={y - 5}
          width={10}
          height={10}
          rx={2}
          fill="var(--color-ground)"
          stroke="var(--color-ember)"
          strokeWidth={1.5}
          style={{ pointerEvents: "all", cursor }}
          onPointerDown={(e) => down(e, h)}
          onPointerMove={move}
          onPointerUp={up}
          onPointerCancel={cancel}
        />
      ))}
    </g>
  );
}
