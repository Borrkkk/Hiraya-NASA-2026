// Aladin Lite ships no TypeScript types; this is the slice of its API we use.
// Shared by the home screen's sky backdrop and the Explore view.

export type ClickEvent = { ra: number; dec: number; isDragging?: boolean };

export type AladinInstance = {
  getRaDec: () => [number, number];
  getFov: () => [number, number];
  gotoRaDec: (ra: number, dec: number) => void;
  setFoV: (fov: number) => void;
  zoomToFoV: (fov: number, seconds: number, done?: () => void) => void;
  stopAnimation: () => void;
  setBaseImageLayer: (survey: string) => unknown;
  /** Internal, but the public getViewDataURL ignores its options. */
  view: {
    getCanvasDataURL: (format: string, w?: number, h?: number, logo?: boolean) => Promise<string>;
  };
  on: (event: string, cb: (e: ClickEvent) => void) => void;
};

export type AladinModule = {
  init: Promise<void>;
  aladin: (el: HTMLElement, options: Record<string, unknown>) => AladinInstance;
};

/** Importing aladin-lite touches WebGL/WASM at module load: browser only. */
export async function loadAladin(): Promise<AladinModule> {
  const A = (await import("aladin-lite")).default as AladinModule;
  await A.init;
  return A;
}

/** Every Aladin control off, no usage ping. The logo stays (terms of use). */
export const BARE_ALADIN_OPTIONS = {
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
  log: false,
} as const;
