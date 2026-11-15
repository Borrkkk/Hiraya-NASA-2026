"use client";

import { useId, useMemo, useState } from "react";
import { BANDS } from "@/lib/explore/bands";
import type { Spectrum } from "@/lib/explore/types";

const W = 360;
const H = 170;
const PAD = { l: 8, r: 8, t: 10, b: 30 };
const X0 = 0.75;
const X1 = 5;

/** Infrared colours: warm white at the near end, through amber and rose, to violet and blue at 5 µm. */
const RAMP: [number, string][] = [
  [0.75, "#ffe9c8"],
  [1.5, "#ffb54d"],
  [2.4, "#ff7a59"],
  [3.3, "#ee4f8f"],
  [4.2, "#a15cff"],
  [5.0, "#4f9bff"],
];

function mix(a: string, b: string, t: number) {
  const p = (c: string, i: number) => parseInt(c.slice(1 + i * 2, 3 + i * 2), 16);
  const ch = (i: number) => Math.round(p(a, i) + (p(b, i) - p(a, i)) * t);
  return `rgb(${ch(0)}, ${ch(1)}, ${ch(2)})`;
}

export function colourAt(um: number) {
  if (um <= RAMP[0][0]) return RAMP[0][1];
  for (let i = 1; i < RAMP.length; i++) {
    if (um <= RAMP[i][0]) return mix(RAMP[i - 1][1], RAMP[i][1], (um - RAMP[i - 1][0]) / (RAMP[i][0] - RAMP[i - 1][0]));
  }
  return RAMP[RAMP.length - 1][1];
}

/** The page's wavelength windows, so the chart can show which "thing to look for" each part of the spectrum is. */
const WINDOWS: { band: string; from: number; to: number; broad: boolean }[] = [
  { band: "starlight", from: 0.75, to: 1.3, broad: true },
  { band: "warm-glow", from: 3.8, to: 5.0, broad: true },
  ...[
    ["helium", [1.083]],
    ["hydrogen", [1.282, 1.875, 4.05]],
    ["methane", [1.7, 3.3]],
    ["organic-dust", [3.3]],
    ["water-ice", [3.0]],
    ["co2-ice", [4.27]],
    ["co-ice", [4.67]],
  ].flatMap(([band, centres]) => (centres as number[]).map((c) => ({ band: band as string, from: c * 0.97, to: c * 1.03, broad: false }))),
];
const bandColour = (id: string) => BANDS.find((b) => b.id === id)?.color ?? "#999";

/** Which window a spectral feature belongs to, by its plain label. */
const FEATURE_BAND: Record<string, string> = {
  Hydrogen: "hydrogen",
  Helium: "helium",
  Methane: "methane",
  "Water vapour": "water-ice",
  "Water ice": "water-ice",
  "Carbon monoxide": "co-ice",
  "CO ice": "co-ice",
  "CO₂ ice": "co2-ice",
  "Organic dust": "organic-dust",
};

/** A smooth path through points (Catmull-Rom as cubic Béziers). */
function smooth(pts: [number, number][]) {
  if (pts.length < 2) return "";
  let d = `M${pts[0][0]},${pts[0][1]}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] ?? pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] ?? p2;
    d += ` C${p1[0] + (p2[0] - p0[0]) / 6},${p1[1] + (p2[1] - p0[1]) / 6} ${p2[0] - (p3[0] - p1[0]) / 6},${p2[1] - (p3[1] - p1[1]) / 6} ${p2[0]},${p2[1]}`;
  }
  return d;
}

/**
 * Brightness against wavelength. Dots take the colour of their wavelength, a
 * glowing curve follows the typical value, the coloured strips mark the page's
 * wavelength windows, and feature chips take the colour of the thing they point at.
 */
export function SpectrumChart({ spectrum, compact = false }: { spectrum: Spectrum; compact?: boolean }) {
  const uid = useId().replace(/:/g, "");
  const [hover, setHover] = useState<number | null>(null);
  const [point, setPoint] = useState<number | null>(null);
  const pts = spectrum.points;
  const lo = Math.min(0, ...pts.map((p) => p.flux));
  const hi = Math.max(1e-6, ...pts.map((p) => p.flux));
  const pad = (hi - lo) * 0.12;
  const ymin = lo - (lo < 0 ? pad : 0);
  const ymax = hi + pad;
  const sx = (w: number) => PAD.l + ((w - X0) / (X1 - X0)) * (W - PAD.l - PAD.r);
  const sy = (f: number) => H - PAD.b - ((f - ymin) / (ymax - ymin)) * (H - PAD.b - PAD.t);
  const base = sy(Math.max(0, ymin));

  // The typical value in each slice of wavelength, joined into one smooth curve.
  const curve = useMemo(() => {
    const bins = 16;
    const out: [number, number][] = [];
    for (let i = 0; i < bins; i++) {
      const a = X0 + ((X1 - X0) * i) / bins;
      const b = X0 + ((X1 - X0) * (i + 1)) / bins;
      const inBin = pts.filter((p) => p.wavelengthUm >= a && p.wavelengthUm < b).map((p) => p.flux).sort((x, y) => x - y);
      if (inBin.length) out.push([sx((a + b) / 2), sy(inBin[Math.floor(inBin.length / 2)])]);
    }
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pts, ymin, ymax]);
  const path = smooth(curve);
  const area = curve.length > 1 ? `${path} L${curve[curve.length - 1][0]},${base} L${curve[0][0]},${base} Z` : "";

  const features = [...spectrum.features].sort((a, b) => a.wavelengthUm - b.wavelengthUm);
  const chips = features.map((f, i) => ({ f, i })).filter(({ f }, idx, all) => all.findIndex((x) => x.f.label === f.label) === idx);
  const sameKind = (i: number) => features.filter((f) => f.label === features[i].label);
  const featureColour = (label: string) => bandColour(FEATURE_BAND[label] ?? "");
  const active = point !== null ? pts[point] : null;

  return (
    <figure className="flex flex-col gap-2">
      <div className="relative">
        {!compact && chips.length > 0 && (
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
                className="absolute inline-flex -translate-x-1/2 cursor-default items-center gap-1.5 whitespace-nowrap rounded-full border bg-raised px-2 py-0.5 text-caption text-ink"
                style={{ left: `${Math.min(88, Math.max(12, (sx(f.wavelengthUm) / W) * 100))}%`, top: (n % 3) * 18, borderColor: featureColour(f.label) }}
              >
                <span className="size-1.5 rounded-full" style={{ background: featureColour(f.label) }} aria-hidden="true" />
                {f.label}
              </button>
            ))}
          </div>
        )}
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Infrared spectrum: brightness against wavelength" className="block w-full overflow-visible">
          <defs>
            <linearGradient id={`${uid}-ramp`} gradientUnits="userSpaceOnUse" x1={sx(X0)} x2={sx(X1)} y1="0" y2="0">
              {RAMP.map(([w, c]) => (
                <stop key={w} offset={`${((w - X0) / (X1 - X0)) * 100}%`} stopColor={c} />
              ))}
            </linearGradient>
            <linearGradient id={`${uid}-fade`} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="white" stopOpacity="0.5" />
              <stop offset="100%" stopColor="white" stopOpacity="0" />
            </linearGradient>
            <mask id={`${uid}-mask`}>
              <rect x="0" y="0" width={W} height={H} fill={`url(#${uid}-fade)`} />
            </mask>
            <filter id={`${uid}-glow`} x="-10%" y="-30%" width="120%" height="160%">
              <feGaussianBlur stdDeviation="3" />
            </filter>
          </defs>

          {/* the page's wavelength windows, coloured like the band picker */}
          {WINDOWS.map((w, i) => (
            <rect
              key={i}
              x={sx(w.from)}
              width={sx(w.to) - sx(w.from)}
              y={PAD.t}
              height={H - PAD.b - PAD.t}
              fill={bandColour(w.band)}
              opacity={w.broad ? 0.1 : 0.32}
              rx={w.broad ? 0 : 1}
            />
          ))}
          {[1, 2, 3, 4, 5].map((t) => (
            <line key={t} x1={sx(t)} x2={sx(t)} y1={PAD.t} y2={H - PAD.b} stroke="var(--color-line)" />
          ))}
          {!compact &&
            features.map((f) => (
              <line
                key={f.realName}
                x1={sx(f.wavelengthUm)}
                x2={sx(f.wavelengthUm)}
                y1={PAD.t}
                y2={H - PAD.b}
                stroke={featureColour(f.label)}
                strokeWidth={hover !== null && features[hover].label === f.label ? 2.5 : 1.25}
                strokeDasharray="3 3"
                opacity={hover !== null && features[hover].label !== f.label ? 0.35 : 1}
              />
            ))}

          {/* the glowing curve */}
          {area && <path d={area} fill={`url(#${uid}-ramp)`} mask={`url(#${uid}-mask)`} opacity="0.9" />}
          {path && <path d={path} fill="none" stroke={`url(#${uid}-ramp)`} strokeWidth="5" opacity="0.4" filter={`url(#${uid}-glow)`} />}
          {path && <path d={path} fill="none" stroke={`url(#${uid}-ramp)`} strokeWidth="2.25" strokeLinecap="round" pathLength={1} className="spectrum-draw" />}

          {/* axis, with a colour bar so wavelength reads as colour */}
          <rect x={sx(X0)} y={H - PAD.b + 3} width={sx(X1) - sx(X0)} height="4" rx="2" fill={`url(#${uid}-ramp)`} />
          {[1, 2, 3, 4, 5].map((t) => (
            <text key={t} x={sx(t)} y={H - 6} textAnchor="middle" className="fill-ink-secondary font-mono" fontSize={10}>
              {t}
            </text>
          ))}

          {pts.map((p, index) => (
            <circle
              key={`${p.wavelengthUm}-${index}`}
              cx={sx(p.wavelengthUm)}
              cy={sy(p.flux)}
              r={point === index ? 6 : 4}
              fill={colourAt(p.wavelengthUm)}
              stroke="var(--color-ground)"
              strokeWidth={1.5}
              className="spectrum-dot"
              style={{ animationDelay: `${Math.min(index, 60) * 12}ms` }}
              onPointerEnter={() => setPoint(index)}
              onPointerLeave={() => setPoint((v) => (v === index ? null : v))}
            >
              <title>
                {p.wavelengthUm.toFixed(3)} µm: {p.flux.toPrecision(4)}
                {p.err !== undefined ? ` ± ${p.err.toPrecision(3)}` : ""}
              </title>
            </circle>
          ))}
        </svg>
        {active && (
          <p
            className="pointer-events-none absolute top-0 z-10 -translate-x-1/2 whitespace-nowrap rounded-xs border border-line-strong bg-overlay px-2 py-1 font-mono text-caption text-ink"
            style={{ left: `${(sx(active.wavelengthUm) / W) * 100}%`, top: !compact && chips.length > 0 ? 56 : 0 }}
          >
            {active.wavelengthUm.toFixed(2)} µm · {active.flux.toPrecision(3)}
          </p>
        )}
        {hover !== null && features[hover] && (
          <p className="pointer-events-none absolute inset-x-0 -bottom-1 translate-y-full rounded-xs border border-line-strong bg-overlay px-2 py-1 text-small text-ink">
            {sameKind(hover).map((x) => x.realName).join(" · ")}
          </p>
        )}
      </div>
      <figcaption className="flex justify-between text-caption text-ink-secondary">
        <span>{spectrum.fluxLabel}</span>
        <span>Wavelength (µm), shorter to longer</span>
      </figcaption>
      {!compact && (
        <>
          <ul className="flex flex-wrap gap-x-3 gap-y-1 text-caption text-ink-secondary" aria-label="Wavelength windows">
            {BANDS.filter((b) => ["starlight", "warm-glow", ...features.map((f) => FEATURE_BAND[f.label])].includes(b.id)).map((b) => (
              <li key={b.id} className="inline-flex items-center gap-1.5">
                <span className="size-2 rounded-xs" style={{ background: b.color }} aria-hidden="true" />
                {b.name}
              </li>
            ))}
          </ul>
          <p className="text-caption text-ink-secondary">{pts.length} measurements shown. Gaps are colours we have not measured; dots can come from different dates.</p>
        </>
      )}
    </figure>
  );
}
