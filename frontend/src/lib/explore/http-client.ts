import { ApiError, api, apiBlob } from "@/lib/api";
import { NoDataError } from "./errors";
import type { ExploreApi } from "./api";
import type {
  Area,
  CallOptions,
  Inspection,
  MotionResult,
  VerifyOutcome,
} from "./types";

/**
 * The real unified API client (api.app:app). It is the only file that knows
 * the URLs; the shapes are in types.ts.
 *
 * Browser calls go to same-origin /api/*, which next.config.ts proxies to
 * BACKEND_URL, so the paths below are relative to the backend root.
 */

const POLL_MS = 700;

type JobStatus<T> =
  | { status: "running"; step?: string }
  | { status: "done"; result: T }
  | { status: "failed"; message?: string };

/**
 * Slow endpoints can be either synchronous (the POST returns the result) or
 * jobs (the POST returns { jobId } and we poll). Handles both, so the backend
 * team can start synchronous and move to jobs without a frontend change.
 */
async function runJob<T>(path: string, json: unknown, opts: CallOptions = {}): Promise<T> {
  const first = await api<{ jobId?: string } & Record<string, unknown>>(path, {
    method: "POST",
    json,
    signal: opts.signal,
  });
  if (!first || typeof first.jobId !== "string") return first as T;

  for (;;) {
    await sleep(POLL_MS, opts.signal);
    const job = await api<JobStatus<T>>(`/explore/jobs/${first.jobId}`, { signal: opts.signal });
    if (job.status === "done") return job.result;
    if (job.status === "failed") throw new Error(job.message ?? "The analysis failed.");
    if (job.step) opts.onStep?.(job.step);
  }
}

function sleep(ms: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    if (signal?.aborted) return reject(new DOMException("Aborted", "AbortError"));
    const t = setTimeout(resolve, ms);
    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(t);
        reject(new DOMException("Aborted", "AbortError"));
      },
      { once: true },
    );
  });
}

export const httpExploreApi: ExploreApi = {
  getArea: async (req, opts) => {
    try {
      return await api<Area>(`/explore/area?ra=${req.ra}&dec=${req.dec}&fov=${req.fov}`, { signal: opts?.signal });
    } catch (e) {
      // 404 with { detail: { message, suggestion } } means "nothing saved here", not "broken".
      const detail = e instanceof ApiError && e.status === 404 ? (e.body as { detail?: { message?: string; suggestion?: NoDataError["suggestion"] } })?.detail : null;
      if (detail?.message) throw new NoDataError(detail.message, detail.suggestion);
      throw e;
    }
  },

  fetchFrame: ({ areaId, epochId, band, level = 0 }, opts) =>
    apiBlob(
      `/explore/areas/${encodeURIComponent(areaId)}/frames/${encodeURIComponent(epochId)}/${band}?level=${level}`,
      { signal: opts?.signal },
    ),

  inspect: (req, opts) =>
    api<Inspection>(`/explore/areas/${encodeURIComponent(req.areaId)}/inspect`, {
      method: "POST",
      json: req,
      signal: opts?.signal,
    }),

  analyzeMotion: (req, opts) =>
    runJob<MotionResult>(`/explore/areas/${encodeURIComponent(req.areaId)}/motion`, req, opts),

  verify: (req, opts) =>
    runJob<VerifyOutcome>(`/explore/areas/${encodeURIComponent(req.areaId)}/verify`, req, opts),
};
