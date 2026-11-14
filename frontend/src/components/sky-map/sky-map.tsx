"use client";

import { Minus, Plus } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { IconButton, Logo, Reticle, Segmented } from "@/components/ui";
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
    value: "allwise",
    url: `${IRSA_HIPS}/AllWISE/RGB-W4-W2-W1`,
    label: "Infrared",
    hint: "AllWISE, 3.4–22 µm",
  },
  {
    value: "2mass",
    url: `${IRSA_HIPS}/2MASS/Color`,
    label: "Near-infrared",
    hint: "2MASS, 1.2–2.2 µm",
  },
  {
    value: "dss2",
    url: `${IRSA_HIPS}/DSS2/color`,
    label: "Visible",
    hint: "DSS2 optical",
  },
] as const;

type SurveyId = (typeof SURVEYS)[number]["value"];

const surveyUrl = (id: SurveyId) => SURVEYS.find((s) => s.value === id)!.url;

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
          backgroundColor: "rgb(5, 6, 8)", // sky
          // We draw the Pulsr reticle and controls ourselves. The Aladin logo
          // stays (terms of use).
          showReticle: false,
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
    <div className={cn("relative overflow-hidden bg-sky", className)}>
      <div
        ref={containerRef}
        className={cn(
          "absolute inset-0 transition-opacity duration-(--dur-enter) ease-standard",
          ready ? "opacity-100" : "opacity-0",
        )}
      />

      {/* Ground-to-transparent scrims: the one gradient Pulsr allows, so the
          header and controls stay readable over bright sky. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-32 bg-linear-to-b from-ground/90 to-transparent"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 bottom-0 h-40 bg-linear-to-t from-ground/90 to-transparent"
      />

      <header className="absolute inset-x-0 top-0 flex items-center justify-between px-4 py-4 sm:px-6">
        <Logo size={22} />
      </header>

      {!ready && !error && (
        <div className="absolute inset-0 grid place-items-center">
          <p className="text-small text-ink-secondary">Loading the sky</p>
        </div>
      )}

      {error && (
        <div className="absolute inset-0 grid place-items-center p-6 text-center">
          <p className="max-w-sm text-body-sm text-ink-secondary">
            This browser can&apos;t draw the sky map. It needs WebGL2, which most
            up-to-date browsers have.
          </p>
        </div>
      )}

      {ready && (
        <>
          {/* The reticle frames the centre of view: what search and verify
              will act on. */}
          <div className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
            {view && (
              <Reticle
                size={56}
                name={`Field ${formatFov(view.fov)}`}
                coords={`${formatRa(view.ra)} ${formatDec(view.dec)}`}
              />
            )}
          </div>

          {/* Mobile: bottom-right above the survey switch, clear of the
              reticle label. Desktop: vertically centred on the right edge. */}
          <div className="absolute bottom-24 right-4 flex flex-col gap-2 sm:bottom-auto sm:right-6 sm:top-1/2 sm:-translate-y-1/2">
            <IconButton
              label="Zoom in"
              className="max-sm:size-11"
              onClick={() => aladinRef.current?.increaseZoom()}
            >
              <Plus size={16} strokeWidth={1.5} aria-hidden="true" />
            </IconButton>
            <IconButton
              label="Zoom out"
              className="max-sm:size-11"
              onClick={() => aladinRef.current?.decreaseZoom()}
            >
              <Minus size={16} strokeWidth={1.5} aria-hidden="true" />
            </IconButton>
          </div>

          <div className="absolute inset-x-4 bottom-6 flex justify-center sm:bottom-8">
            <Segmented
              label="Sky survey"
              options={SURVEYS}
              value={survey}
              onChange={pickSurvey}
              className="w-full max-w-sm"
            />
          </div>
        </>
      )}
    </div>
  );
}

// Pulsr number formats: 08h55m10.8s −07°14′42″, 4.4 µm.
function formatRa(deg: number) {
  const h = (((deg % 360) + 360) % 360) / 15;
  const hh = Math.floor(h);
  const mm = Math.floor((h - hh) * 60);
  const ss = ((h - hh) * 60 - mm) * 60;
  return `${pad(hh)}h${pad(mm)}m${ss.toFixed(1).padStart(4, "0")}s`;
}

function formatDec(deg: number) {
  const sign = deg < 0 ? "−" : "+";
  const a = Math.abs(deg);
  const dd = Math.floor(a);
  const mm = Math.floor((a - dd) * 60);
  const ss = Math.round(((a - dd) * 60 - mm) * 60);
  return `${sign}${pad(dd)}°${pad(mm)}′${pad(ss)}″`;
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
