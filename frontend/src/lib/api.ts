// Thin fetch wrapper for the Python backend.
//
// - Browser: calls same-origin `/api/*`, which next.config.ts proxies to BACKEND_URL.
// - Server (RSC, route handlers): calls BACKEND_URL directly.
//
// Swap the `unknown` types for generated ones once the backend publishes an
// OpenAPI schema: `pnpm gen:api` writes src/lib/api-types.ts.

export class ApiError extends Error {
  constructor(
    public status: number,
    public body: unknown,
    message?: string,
  ) {
    super(message ?? `API request failed with ${status}`);
    this.name = "ApiError";
  }
}

export function baseUrl() {
  return typeof window === "undefined"
    ? (process.env.BACKEND_URL ?? "http://localhost:8000")
    : "/api";
}

export async function api<T = unknown>(
  path: string,
  init: Omit<RequestInit, "body"> & { json?: unknown } = {},
): Promise<T> {
  const { json, headers, ...rest } = init;
  const res = await fetch(`${baseUrl()}${path}`, {
    ...rest,
    headers: {
      Accept: "application/json",
      ...(json !== undefined && { "Content-Type": "application/json" }),
      ...headers,
    },
    body: json !== undefined ? JSON.stringify(json) : undefined,
  });

  const text = await res.text();
  const body = text ? safeJson(text) : null;
  if (!res.ok) throw new ApiError(res.status, body);
  return body as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

/** Like `api`, but returns the response body as a Blob (images). */
export async function apiBlob(path: string, init: RequestInit = {}): Promise<Blob> {
  const res = await fetch(`${baseUrl()}${path}`, init);
  if (!res.ok) throw new ApiError(res.status, await res.text().catch(() => null));
  return res.blob();
}
