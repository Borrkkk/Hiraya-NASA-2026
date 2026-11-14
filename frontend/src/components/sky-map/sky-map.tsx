"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";

// Aladin Lite ships no TypeScript types; this is the slice of its API we use.
type AladinInstance = {
  setImageSurvey: (id: string) => void;
  getRaDec: () => [number, number];
  getFov: () => [number, number];
  setFoV: (deg: number) => void;
  increaseZoom: () => void;
  decreaseZoom: () => void;
  on: (event: string, cb: (...args: unknown[]) => void) => void;
};

type AladinModule = {
  init: Promise<void>;
  aladin: (el: HTMLElement, options: Record<string, unknown>) => AladinInstance;
};

// Surveys are loaded straight from NASA/IPAC IRSA's HiPS mirror. Passing a URL
// skips Aladin's mirror auto-selection, which can stall on a dead CDS mirror.
const IRSA_HIPS = "https://irsa.ipac.caltech.edu/data/hips/CDS";

export const SURVEYS = [
  {
    id: "allwise",
    url: `${IRSA_HIPS}/AllWISE/RGB-W4-W2-W1`,
    label: "Infrared",
    hint: "AllWISE · 3.4–22 μm",
  },
  {
    id: "2mass",
    url: `${IRSA_HIPS}/2MASS/Color`,
    label: "Near-IR",
    hint: "2MASS · J H K",
  },
  {
    id: "dss2",
    url: `${IRSA_HIPS}/DSS2/color`,
    label: "Visible",
    hint: "DSS2 · optical",
  },
] as const;

const surveyUrl = (id: SurveyId) => SURVEYS.find((s) => s.id === id)!.url;

type SurveyId = (typeof SURVEYS)[number]["id"];

type View = { ra: number; dec: number; fov: number };

export type SkyMapProps = {
  className?: string;
  /**
   * Initial center as "ra dec" in degrees, or an object name ("M42").
   * Names need a network lookup (Sesame), so prefer coordinates.
   */
  target?: string;
  /** Initial field of view in degrees. */
  fov?: number;
  survey?: SurveyId;
};

export function SkyMap({
  className,
  // Orion: M42 and the surrounding molecular cloud glow in WISE infrared.
  target = "83.82 -5.39",
  fov = 24,
  survey: initialSurvey = "allwise",
}: SkyMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const aladinRef = useRef<AladinInstance | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [survey, setSurvey] = useState<SurveyId>(initialSurvey);
  const [view, setView] = useState<View | null>(null);

  useEffect(() => {
    let cancelled = false;
    const el = containerRef.current;
    if (!el) return;

    (async () => {
      try {
        // Importing aladin-lite touches WebGL/WASM at module load, so it can
        // only happen in the browser.
        const A = (await import("aladin-lite")).default as AladinModule;
        await A.init;
        if (cancelled) return;

        const aladin = A.aladin(el, {
          survey: surveyUrl(initialSurvey),
          target,
          fov,
          projection: "SIN",
          cooFrame: "ICRS",
          backgroundColor: "rgb(5, 6, 8)",
          showReticle: true,
          reticleColor: "rgb(255, 107, 61)",
          reticleSize: 18,
          // We draw our own controls; the Aladin logo stays (terms of use).
          showZoomControl: false,
          showLayersControl: false,
          showFullscreenControl: false,
          showGotoControl: false,
          showProjectionControl: false,
          showFrame: false,
          showFov: false,
          showCooLocation: false,
          showStatusBar: false,
          showContextMenu: false,
          showSimbadPointerControl: false,
          showCooGridControl: false,
          showSettingsControl: false,
          showShareControl: false,
          // Skip Aladin's startup usage ping to CDS (sends our page URL).
          log: false,
        });
        aladinRef.current = aladin;

        const sync = () => {
          const [ra, dec] = aladin.getRaDec();
          const [fovX] = aladin.getFov();
          setView({ ra, dec, fov: fovX });
        };
        aladin.on("positionChanged", sync);
        aladin.on("zoomChanged", sync);
        sync();
        setReady(true);
      } catch (e) {
        if (!cancelled) setError(String(e));
      }
    })();

    return () => {
      cancelled = true;
      aladinRef.current = null;
      el.replaceChildren();
    };
    // Initial props only: later changes go through the instance.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const pickSurvey = (id: SurveyId) => {
    setSurvey(id);
    aladinRef.current?.setImageSurvey(surveyUrl(id));
  };

  return (
    <div className={cn("sky-map relative overflow-hidden bg-[#050608]", className)}>
      <div
        ref={containerRef}
        className={cn(
          "absolute inset-0 transition-opacity duration-1000",
          ready ? "opacity-100" : "opacity-0",
        )}
      />

      {/* Vignette keeps overlays legible over bright regions. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_55%,rgba(5,6,8,0.75)_100%)]"
      />

      {!ready && !error && (
        <div className="absolute inset-0 grid place-items-center">
          <p className="font-mono text-xs uppercase tracking-[0.3em] text-[#7C838E] animate-pulse">
            Loading sky
          </p>
        </div>
      )}

      {error && (
        <div className="absolute inset-0 grid place-items-center p-6 text-center">
          <p className="max-w-sm font-mono text-sm text-[#A3A9B3]">
            The sky map needs WebGL2, which this browser didn&apos;t provide.
          </p>
        </div>
      )}

      {ready && (
        <>
          {view && <Readout view={view} />}

          <div className="absolute right-4 top-1/2 flex -translate-y-1/2 flex-col gap-2">
            <IconButton label="Zoom in" onClick={() => aladinRef.current?.increaseZoom()}>
              <path d="M12 5v14M5 12h14" />
            </IconButton>
            <IconButton label="Zoom out" onClick={() => aladinRef.current?.decreaseZoom()}>
              <path d="M5 12h14" />
            </IconButton>
          </div>

          <div
            role="radiogroup"
            aria-label="Sky survey"
            className="absolute bottom-6 left-1/2 flex -translate-x-1/2 gap-1 rounded-full border border-white/10 bg-[#0E1013]/70 p-1 backdrop-blur-md"
          >
            {SURVEYS.map((s) => {
              const active = s.id === survey;
              return (
                <button
                  key={s.id}
                  type="button"
                  role="radio"
                  aria-checked={active}
                  title={s.hint}
                  onClick={() => pickSurvey(s.id)}
                  className={cn(
                    "h-11 whitespace-nowrap rounded-full px-3.5 font-mono text-xs uppercase tracking-[0.12em] transition-colors sm:px-5 sm:tracking-[0.15em]",
                    active
                      ? "bg-[#FF6B3D] text-[#0E1013]"
                      : "text-[#A3A9B3] hover:bg-white/5 hover:text-[#E8EAED]",
                  )}
                >
                  {s.label}
                </button>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

function Readout({ view }: { view: View }) {
  return (
    <dl className="pointer-events-none absolute left-4 top-4 grid grid-cols-[auto_auto] gap-x-3 gap-y-1 rounded-lg border border-white/10 bg-[#0E1013]/60 px-3 py-2 font-mono text-[11px] tabular-nums backdrop-blur-md">
      <dt className="text-[#7C838E]">RA</dt>
      <dd className="text-[#E8EAED]">{formatRa(view.ra)}</dd>
      <dt className="text-[#7C838E]">DEC</dt>
      <dd className="text-[#E8EAED]">{formatDec(view.dec)}</dd>
      <dt className="text-[#7C838E]">FOV</dt>
      <dd className="text-[#E8EAED]">{formatFov(view.fov)}</dd>
    </dl>
  );
}

function IconButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      className="grid size-11 place-items-center rounded-full border border-white/10 bg-[#0E1013]/70 text-[#E8EAED] backdrop-blur-md transition-colors hover:border-[#FF6B3D]/60 hover:text-[#FF6B3D]"
    >
      <svg
        aria-hidden="true"
        viewBox="0 0 24 24"
        className="size-4"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.75}
        strokeLinecap="round"
      >
        {children}
      </svg>
    </button>
  );
}

function formatRa(deg: number) {
  const h = (((deg % 360) + 360) % 360) / 15;
  const hh = Math.floor(h);
  const mm = Math.floor((h - hh) * 60);
  const ss = ((h - hh) * 60 - mm) * 60;
  return `${pad(hh)}h ${pad(mm)}m ${ss.toFixed(1).padStart(4, "0")}s`;
}

function formatDec(deg: number) {
  const sign = deg < 0 ? "−" : "+";
  const a = Math.abs(deg);
  const dd = Math.floor(a);
  const mm = Math.floor((a - dd) * 60);
  const ss = Math.round(((a - dd) * 60 - mm) * 60);
  return `${sign}${pad(dd)}° ${pad(mm)}′ ${pad(ss)}″`;
}

function formatFov(deg: number) {
  if (deg >= 1) return `${deg.toFixed(deg >= 10 ? 0 : 1)}°`;
  const arcmin = deg * 60;
  if (arcmin >= 1) return `${arcmin.toFixed(1)}′`;
  return `${(arcmin * 60).toFixed(0)}″`;
}

function pad(n: number) {
  return String(n).padStart(2, "0");
}
