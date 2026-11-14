"use client";

import { useState } from "react";
import type { Spectrum } from "@/lib/explore/types";

const W = 360;
const H = 150;
const PAD = { l: 8, r: 8, t: 8, b: 22 };

/**
 * Brightness against wavelength, with plain-language feature labels you can
 * hover for the real name. Labels stagger vertically so close ones don't
 * overlap.
 */
export function SpectrumChart({ spectrum, compact = false }: { spectrum: Spectrum; compact?: boolean }) {
  const [hover, setHover] = useState<number | null>(null);
  const pts = spectrum.points;
  const xs = pts.map((p) => p.wavelengthUm);
  const x0 = Math.min(...xs);
  const x1 = Math.max(...xs);
  const ymax = Math.max(0.001, ...pts.map((p) => p.flux)) * 1.15;
  const sx = (w: number) => PAD.l + ((w - x0) / (x1 - x0)) * (W - PAD.l - PAD.r);
  const sy = (f: number) => H - PAD.b - (f / ymax) * (H - PAD.b - PAD.t);
  const d = pts.map((p, i) => `${i ? "L" : "M"}${sx(p.wavelengthUm).toFixed(1)} ${sy(p.flux).toFixed(1)}`).join(" ");
  const features = [...spectrum.features].sort((a, b) => a.wavelengthUm - b.wavelengthUm);
  // One label chip per kind of feature, even if it shows at several wavelengths.
  const chips = features
    .map((f, i) => ({ f, i }))
    .filter(({ f }, idx, all) => all.findIndex((x) => x.f.label === f.label) === idx);
  const sameKind = (i: number) => features.filter((f) => f.label === features[i].label);

  return (
    <figure className="flex flex-col gap-2">
      <div className="relative">
        {!compact && (
          <div className="relative h-[52px]">
            {chips.map(({ f, i }, n) => (
              <button
                key={f.realName}
                type="button"
                aria-label={`${f.label}: ${sameKind(i).map((x) => x.realName).join(", ")}`}
                onPointerEnter={() => setHover(i)}
                onPointerLeave={() => setHover((h) => (h === i ? null : h))}
                onFocus={() => setHover(i)}
                onBlur={() => setHover((h) => (h === i ? null : h))}
                className="absolute -translate-x-1/2 cursor-default whitespace-nowrap rounded-xs bg-raised px-1.5 py-0.5 text-caption text-ink"
                style={{ left: `${(sx(f.wavelengthUm) / W) * 100}%`, top: (n % 3) * 18 }}
              >
                {f.label}
              </button>
            ))}
          </div>
        )}
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Infrared spectrum: brightness against wavelength" className="block w-full">
          {[1, 2, 3, 4, 5].map((t) => (
            <g key={t}>
              <line x1={sx(t)} x2={sx(t)} y1={PAD.t} y2={H - PAD.b} stroke="var(--color-line)" />
              <text x={sx(t)} y={H - 6} textAnchor="middle" className="fill-ink-secondary font-mono" fontSize={10}>
                {t}
              </text>
            </g>
          ))}
          <line x1={PAD.l} x2={W - PAD.r} y1={H - PAD.b} y2={H - PAD.b} stroke="var(--color-line-strong)" />
          {!compact &&
            features.map((f) => (
              <line
                key={f.realName}
                x1={sx(f.wavelengthUm)}
                x2={sx(f.wavelengthUm)}
                y1={PAD.t}
                y2={H - PAD.b}
                stroke={hover !== null && features[hover].label === f.label ? "var(--color-ink)" : "var(--color-line-strong)"}
                strokeDasharray="3 3"
              />
            ))}
          <path d={d} fill="none" stroke="var(--color-ink)" strokeWidth={1.5} strokeLinejoin="round" />
        </svg>
        {hover !== null && features[hover] && (
          <p className="pointer-events-none absolute inset-x-0 -bottom-1 translate-y-full rounded-xs border border-line-strong bg-overlay px-2 py-1 text-small text-ink">
            {sameKind(hover).map((x) => x.realName).join(" · ")}
          </p>
        )}
      </div>
      <figcaption className="flex justify-between text-caption text-ink-secondary">
        <span>{spectrum.fluxLabel}</span>
        <span>Wavelength (µm)</span>
      </figcaption>
    </figure>
  );
}
