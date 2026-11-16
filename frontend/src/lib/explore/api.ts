import type {
  Area,
  AreaRequest,
  CallOptions,
  FrameRequest,
  Inspection,
  InspectRequest,
  MotionRequest,
  MotionResult,
  VerifyOutcome,
  VerifyRequest,
} from "./types";

/**
 * Everything the Explore page asks of the backend. Two implementations:
 *
 *   demo/demo-client.ts  prefetched, simulated Barnard's Star data, no network (default)
 *   http-client.ts       calls the Python API (set NEXT_PUBLIC_EXPLORE_API=http)
 *
 * The UI imports `exploreApi` from "@/lib/explore" and nothing else about the
 * backend. If a method's real shape needs to change, change it here and in
 * types.ts, and TypeScript will point at every place that needs updating.
 *
 * Every method accepts an AbortSignal. The UI aborts when the user moves on
 * (new area, new selection, leaves the page), so implementations should pass it
 * to fetch().
 */
export interface ExploreApi {
  /**
   * The area, its epochs, per-band coverage and the other sensors. Called once
   * on page load. The page shows the Aladin placeholder until this and the first
   * frames arrive, so keep it quick (no pixels here).
   */
  getArea(req: AreaRequest, opts?: CallOptions): Promise<Area>;

  /**
   * One monochrome frame, as an image Blob (PNG, WebP or JPEG, greyscale).
   * The image is `area.sizePx` square and covers `area.extentDeg` degrees,
   * tangent (gnomonic) projection centred on `area.center`, north up, east LEFT
   * (the way sky maps are drawn), so pixel (0,0) is the north-east corner.
   * Brightness is already stretched for display (0 = no signal, 255 = bright);
   * stretch consistently across epochs so the same star looks the same.
   */
  fetchFrame(req: FrameRequest, opts?: CallOptions): Promise<Blob>;

  /**
   * Type guess, spectrum and confidence list for a box or a mover.
   * Fast enough to call as the user drags a box (the UI debounces).
   */
  inspect(req: InspectRequest, opts?: CallOptions): Promise<Inspection>;

  /**
   * Detect everything that moved across the area over the epochs given.
   * Slow. Call `opts.onStep` with short plain-language messages as the job
   * progresses ("Matching stars between frames…"). Movers seen in only one
   * frame must not be returned.
   */
  analyzeMotion(req: MotionRequest, opts?: CallOptions): Promise<MotionResult>;

  /**
   * Cross-reference against Gaia, SkyBoT, SIMBAD and instrument flags. Slow.
   * Report each check through `opts.onStep` ("Checking known stars…").
   */
  verify(req: VerifyRequest, opts?: CallOptions): Promise<VerifyOutcome>;
}
