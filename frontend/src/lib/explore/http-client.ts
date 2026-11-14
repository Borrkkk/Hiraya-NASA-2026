import { api, apiBlob } from "@/lib/api";
import type { ExploreApi } from "./api";
import type {
  Area,
  CallOptions,
  Inspection,
  MotionResult,
  VerifyOutcome,
} from "./types";

/**
 * The real backend client. Written against the endpoints proposed in
 * frontend/docs/explore-backend-integration.md. If the Python API picks
 * different paths or field names, this file is the only place to change
 * (plus types.ts if the shapes differ). Not exercised against a live server
 * yet: it was written blind, so expect small fixes on first contact.
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
  getArea: (req, opts) =>
    api<Area>(`/explore/area?ra=${req.ra}&dec=${req.dec}&fov=${req.fov}`, { signal: opts?.signal }),

  fetchFrame: ({ areaId, epochId, band }, opts) =>
    apiBlob(
      `/explore/areas/${encodeURIComponent(areaId)}/frames/${encodeURIComponent(epochId)}/${band}`,
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
