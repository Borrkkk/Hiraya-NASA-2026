import type { ExploreApi } from "./api";
import { httpExploreApi } from "./http-client";
import { mockExploreApi } from "./mock/mock-client";

/**
 * The one backend handle for the Explore page.
 *
 * Default is the mock. To use the real API set, in .env.local:
 *   NEXT_PUBLIC_EXPLORE_API=http
 * (and BACKEND_URL for the proxy). See docs/explore-backend-integration.md.
 */
export const exploreApi: ExploreApi =
  process.env.NEXT_PUBLIC_EXPLORE_API === "http" ? httpExploreApi : mockExploreApi;

export const usingMockData = exploreApi === mockExploreApi;

export * from "./types";
export type { ExploreApi } from "./api";
