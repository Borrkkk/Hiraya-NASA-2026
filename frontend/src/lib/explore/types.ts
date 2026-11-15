// The data contract between the Explore page and the backend.
//
// Every shape the UI needs from the server is here. The mock client
// (mock/mock-client.ts) and the HTTP client (http-client.ts) both implement
// `ExploreApi` (api.ts) against these types. Integration guide:
// frontend/docs/explore-backend-integration.md
//
// Conventions
// - Sky positions: ICRS/J2000 degrees. `ra` 0..360, `dec` -90..90.
// - Sizes on the sky: degrees. Wavelengths: micrometres. Dates: ISO 8601 UTC.
// - Ids are opaque strings. The UI never parses them.

export type SkyPoint = { ra: number; dec: number };

/** The area the user picked on the home page (the page's URL params). */
export type AreaRequest = SkyPoint & {
  /** Field of view in degrees, horizontal. */
  fov: number;
};

/** A box on the sky, centred on `ra`/`dec`. Sizes in degrees on the sky. */
export type SkyBox = SkyPoint & { width: number; height: number };

// ---------------------------------------------------------------- bands

/** The ten "things to look for". Static, see bands.ts. Ids are the API's band ids. */
export type BandId =
  | "starlight"
  | "hydrogen"
  | "helium"
  | "water-ice"
  | "co2-ice"
  | "co-ice"
  | "organic-dust"
  | "methane"
  | "warm-glow";

export type BandStatus =
  /** Has data for this area and epoch. */
  | { id: BandId; state: "ok"; empty: boolean }
  /** No coverage: the row is disabled and shows `reason`. */
  | { id: BandId; state: "no-coverage"; reason: string };

// ---------------------------------------------------------------- area

export type Epoch = {
  id: string;
  /** When SPHEREx observed this area. Spacing on the timeline is by this date. */
  date: string;
  /**
   * The bands this observation has an image for. Each SPHEREx exposure sees a
   * spot at only a few wavelengths, so some observations have nothing in a given
   * band. Omit if every band is available at every epoch.
   */
  bands?: BandId[];
  /** 0..1: how much of the picture has data. The page opens on the fullest observation. */
  coverage?: number;
};

export type SensorLayer = {
  id: string;
  name: string;
  /** One line on what the sensor is good at. */
  blurb: string;
  /** Aladin HiPS base URL. The page hands it straight to Aladin Lite. */
  hips: string;
  /** Small preview image for the layer picker. */
  thumbnail: string;
  coverage: { ok: true } | { ok: false; reason: string };
  /**
   * Only set if the sensor has its own epochs. Not used yet (spec open
   * question 4): the layer stays fixed.
   */
  epochs?: Epoch[];
};

/**
 * What the backend knows about the chosen area. Everything else is requested
 * lazily using `area.id`.
 */
export type Area = {
  id: string;
  /** Display name, e.g. "Orion Nebula". Falls back to coordinates in the UI. */
  name: string | null;
  center: SkyPoint;
  /**
   * The patch of sky the server can serve frames for: a square tangent-plane
   * image of this many degrees on a side, centred on `center`. The user can
   * pan and zoom inside it, but not outside it.
   */
  extentDeg: number;
  /** Frame image size in pixels (square). */
  sizePx: number;
  /** Arcseconds per pixel of the frames. Sets the zoom limit. */
  pixelScaleArcsec: number;
  /** One per SPHEREx observation of this area, any order. */
  epochs: Epoch[];
  /** One entry per band id, in any order. */
  bands: BandStatus[];
  /**
   * Zoom limits in degrees, if the defaults (derived from the pixel scale and
   * the extent) don't fit, e.g. when frames cover only a small tile and the
   * user should still be able to zoom out to the surrounding sky.
   */
  minFovDeg?: number;
  maxFovDeg?: number;
  /**
   * Frame sizes, smallest first, so the picture can follow the zoom. Level 0 is
   * the one described by extentDeg/sizePx/pixelScaleArcsec above. The page asks for
   * the smallest level that covers the view. Omit for a single size.
   */
  levels?: FrameLevel[];
  layers: SensorLayer[];
};

// ---------------------------------------------------------------- frames

/**
 * A monochrome frame: brightness for one band at one epoch, as an image.
 * The page colours and blends these itself, so toggling a band is instant.
 * See `ExploreApi.fetchFrame` for the image format.
 */
export type FrameRequest = { areaId: string; epochId: string; band: BandId; level?: number };

export type FrameLevel = { level: number; extentDeg: number; sizePx: number; pixelScaleArcsec: number };

// ---------------------------------------------------------------- inspect

export type ObjectType =
  | "star"
  | "brown-dwarf"
  | "planet"
  | "comet"
  | "asteroid"
  | "galaxy"
  | "empty"
  | "artifact";

/** What to inspect: a box on the sky, or a detected mover. */
export type InspectTarget =
  | { kind: "box"; box: SkyBox }
  | { kind: "mover"; moverId: string; box: SkyBox };

export type InspectRequest = {
  areaId: string;
  target: InspectTarget;
  /** The epoch under the playhead, or "all" for all epochs combined. */
  epoch: string | "all";
  /** Bands switched on, so the reason text can talk about what the user sees. */
  bands: BandId[];
};

export type SpectrumFeature = {
  /** Plain label, e.g. "Methane". */
  label: string;
  /** The real name, shown on hover, e.g. "Methane absorption". */
  realName: string;
  wavelengthUm: number;
};

export type Spectrum = {
  /** Sorted by wavelength. SPHEREx covers roughly 0.75 to 5 µm. */
  points: { wavelengthUm: number; flux: number }[];
  /** Unit label for the y axis, plain: e.g. "Brightness (relative)". */
  fluxLabel: string;
  features: SpectrumFeature[];
};

export type TypeScore = { type: ObjectType; confidence: number };

export type Inspection = {
  /** Present when the unified API uses spherex_inspect point-source measurements. */
  evidence?: {
    engine: string;
    measurement: string;
    nFrames: number;
    nDetected: number;
    nUsable: number;
    nFailed: number;
    warnings: string[];
    flags: Record<string, number>;
  };
  /** True if there isn't enough signal to say anything. The guess is then "empty". */
  lowSignal: boolean;
  /** Best guess. `reason` must come from computed facts, not from a model score. */
  guess: { type: ObjectType; reason: string };
  /** Ranked, best first, confidence 0..1. Includes the guess. */
  candidates: TypeScore[];
  spectrum: Spectrum;
};

// ---------------------------------------------------------------- motion

export type MotionRequest = {
  areaId: string;
  /** Inclusive range of epoch ids. At least two epochs. */
  epochs: string[];
  bands: BandId[];
};

export type Mover = {
  id: string;
  /** 1-based number shown in the list and on the tracks. */
  number: number;
  /** One point per epoch the mover was seen in (at least two), time order. */
  points: { epochId: string; date: string; ra: number; dec: number }[];
  /** Apparent speed, arcseconds per hour. */
  speedArcsecPerHour: number;
  /** Direction on the sky, degrees east of north (0 = north, 90 = east). */
  positionAngleDeg: number;
};

export type MotionResult = {
  movers: Mover[];
  /** The epochs the analysis covered, so the page can tell if the range changed. */
  epochs: string[];
  /** Why real-data analysis returned no candidates. Absent from mock results. */
  diagnostics?: {
    reason: "insufficient_comparable_observations" | "no_sources_detected" | "no_consistent_tracks" | "candidates_found";
    comparableObservations: number;
    requiredObservations: number;
    /** Number of source detections across the comparable frames (not unique stars). */
    detectedSources: number;
  };
};

// ---------------------------------------------------------------- verify

export type VerifyRequest = InspectRequest & {
  /** Motion track, when verifying a mover. */
  moverId?: string;
};

export type VerifyOutcome =
  | {
      outcome: "explained";
      /** e.g. "Known asteroid" */
      headline: string;
      /** The name, e.g. "(433) Eros" */
      name: string;
      /** One-line fact. */
      fact: string;
      /** Which source matched: "SkyBoT", "Gaia", "SIMBAD". */
      source: string;
      /** Used to look up points in the rarity table. */
      objectType: ObjectType;
    }
  | {
      outcome: "artifact";
      headline: string;
      reason: string;
      /** Which flag caught it. */
      flag: string;
    }
  | {
      outcome: "unexplained";
      headline: string;
      /** Nearest catalog object that did not fit well, if any (spec Q7). */
      nearMatch?: { name: string; source: string; note: string };
    };

/** Short plain-language step messages shown while a long call runs. */
export type StepReporter = (message: string) => void;

export type CallOptions = { signal?: AbortSignal; onStep?: StepReporter };
