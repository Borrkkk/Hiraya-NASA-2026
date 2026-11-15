import type { ExploreApi } from "./api";
import { httpExploreApi } from "./http-client";
import { mockExploreApi } from "./mock/mock-client";

/**
 * The one backend handle for the Explore page.
 *
 * Default is the real backend (BACKEND_URL, proxied at /api). For the full
 * demo with invented data, set in .env.local:
 *   NEXT_PUBLIC_EXPLORE_API=mock
 */
export const exploreApi: ExploreApi =
  process.env.NEXT_PUBLIC_EXPLORE_API === "mock" ? mockExploreApi : httpExploreApi;

export const usingMockData = exploreApi === mockExploreApi;

export * from "./types";
export { NoDataError } from "./errors";
export type { ExploreApi } from "./api";
