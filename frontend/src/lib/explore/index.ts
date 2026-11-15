import type { ExploreApi } from "./api";
import { demoExploreApi } from "./demo/demo-client";
import { httpExploreApi } from "./http-client";

/**
 * The one backend handle for the Explore page.
 *
 * Default is the DEMO: prefetched, simulated Barnard's Star data served from
 * public/demo, no backend needed (docs/demo.md). For the real SPHEREx backend
 * (BACKEND_URL, proxied at /api), set in .env.local:
 *   NEXT_PUBLIC_EXPLORE_API=http
 */
export const exploreApi: ExploreApi =
  process.env.NEXT_PUBLIC_EXPLORE_API === "http" ? httpExploreApi : demoExploreApi;

export const usingMockData = exploreApi === demoExploreApi;

export * from "./types";
export { NoDataError } from "./errors";
export type { ExploreApi } from "./api";
