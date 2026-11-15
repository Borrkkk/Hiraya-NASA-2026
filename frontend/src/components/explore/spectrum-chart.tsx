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
  // Always the whole SPHEREx range, so a spectrum with only a few wavelengths
  // shows plainly where the gaps are.
  const x0 = 0.75;
  const x1 = 5;
  const lo = Math.min(0, ...pts.map((p) => p.flux));
  const hi = Math.max(1e-6, ...pts.map((p) => p.flux));
  const pad = (hi - lo) * 0.12;
  const ymin = lo - (lo < 0 ? pad : 0);
  const ymax = hi + pad;
  const sx = (w: number) => PAD.l + ((w - x0) / (x1 - x0)) * (W - PAD.l - PAD.r);
  const sy = (f: number) => H - PAD.b - ((f - ymin) / (ymax - ymin)) * (H - PAD.b - PAD.t);
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
          {pts.map((p, index) => (
              <circle key={`${p.wavelengthUm}-${index}`} cx={sx(p.wavelengthUm)} cy={sy(p.flux)} r={3.5} fill="var(--color-ground)" stroke="var(--color-ink)" strokeWidth={1.5}>
                <title>{p.wavelengthUm.toFixed(3)} µm: {p.flux.toPrecision(4)}{p.err !== undefined ? ` ± ${p.err.toPrecision(3)}` : ''}</title>
              </circle>
            ))}
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
      {!compact && <p className="text-caption text-ink-secondary">{pts.length} measurements shown. Gaps are colours we have not measured; dots can come from different dates.</p>}
    </figure>
  );
}
