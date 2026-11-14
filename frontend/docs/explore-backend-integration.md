# Explore page: backend integration guide

For whoever wires the Explore page (`/explore`) to the real API. The page is
finished against a **mock**. Swapping the mock for the real backend is meant to
be one file of glue plus fixing whatever the real shapes turn out to be.

## TL;DR

1. Implement the 5 endpoints in the table below (or tell us the real paths and
   edit `src/lib/explore/http-client.ts`, the only file that knows URLs).
2. Set `NEXT_PUBLIC_EXPLORE_API=http` and `BACKEND_URL=...` in `frontend/.env.local`.
3. Open `/explore?ra=83.82&dec=-5.39&fov=2`. Done. Everything else is UI.

If a real response differs from `src/lib/explore/types.ts`, **change the types
and let TypeScript (`pnpm typecheck`) point at every place that needs updating**.
Don't reshape data in components.

## Where things are

| Path | What it is |
| --- | --- |
| `src/lib/explore/types.ts` | The whole data contract. Read this first. |
| `src/lib/explore/api.ts` | `ExploreApi` interface: 5 methods, documented. |
| `src/lib/explore/http-client.ts` | Real client. Written blind against the table below. |
| `src/lib/explore/mock/` | Mock client + procedural sky. Delete once the real API is solid. |
| `src/lib/explore/index.ts` | Picks mock vs http from `NEXT_PUBLIC_EXPLORE_API`. |
| `src/lib/explore/bands.ts` | The 9 "things to look for": names, copy, colours. Frontend-owned. |
| `src/lib/explore/frame-store.ts` | Frame cache and loader (concurrency 3). |
| `src/lib/explore/motion-language.ts` | Speed and direction wording. **Suggestion thresholds are placeholders.** |
| `src/lib/explore/points.ts` | Rarity table for points (localStorage). Placeholder numbers. |
| `src/lib/explore/share.ts` | "Share this find" hand-off (see below). |
| `src/components/explore/use-explore.tsx` | The page controller: all state, the async flows, URL sync. |
| `src/components/explore/*` | The UI. Components only talk to `useExplore()`. |

`src/lib/explore/href.ts` (`exploreHref`) is what the **home** screen uses to
link in. It defines the URL contract: `ra`, `dec` (degrees), `fov` (degrees, horizontal), optional `q` (name).

## Endpoints the http client expects

Paths are relative to the backend root. The browser calls `/api/...` and
`next.config.ts` rewrites it to `BACKEND_URL`, so there is no CORS.

| Method | Path | Returns |
| --- | --- | --- |
| GET | `/explore/area?ra&dec&fov` | `Area` (JSON). Quick, no pixels. |
| GET | `/explore/areas/{areaId}/frames/{epochId}/{band}` | An image (PNG/WebP/JPEG, greyscale). |
| POST | `/explore/areas/{areaId}/inspect` body `InspectRequest` | `Inspection` |
| POST | `/explore/areas/{areaId}/motion` body `MotionRequest` | `MotionResult`, or `{ jobId }` |
| POST | `/explore/areas/{areaId}/verify` body `VerifyRequest` | `VerifyOutcome`, or `{ jobId }` |
| GET | `/explore/jobs/{jobId}` | `{status:"running",step?}` / `{status:"done",result}` / `{status:"failed",message?}` |

`motion` and `verify` are slow. The client handles both styles: return the
result straight from the POST, **or** return `{ jobId }` and let the client poll
`/explore/jobs/{id}` every 700 ms. The `step` string is shown to the user as
the progress message, so make it plain language ("Checking known asteroids…").
All shapes are in `types.ts`. Aborts are passed through as `AbortSignal`.

## The one thing to get right: frames and alignment

The page blends bands itself on a canvas, so toggling a band is instant and
needs no request. So the backend serves **one monochrome image per (epoch, band)**,
not a pre-coloured composite.

Each frame must satisfy:

- `area.sizePx` pixels square, covering `area.extentDeg` degrees on a side.
- **Gnomonic (TAN) projection centred on `area.center`**, north up, **east to the left**.
  Pixel (0,0) is the north-east corner.
- 0 = no signal, 255 = bright, already stretched for display, **stretched the same
  way across epochs and bands** so brightness is comparable.
- `area.pixelScaleArcsec` is the real arcseconds per pixel. It sets the zoom limit
  (we stop at about 4 screen pixels per frame pixel).

The user can pan and zoom inside the extent only. The view is drawn with a
small affine fit around the view centre (`frameTransform` in `projection.ts`),
which is accurate for fields up to a few degrees. For very large extents
(10 degrees or more) expect a few pixels of drift at the edges. If that bites,
reproject on the server or tile the frames.

SPHEREx caveat from the spec: one exposure holds a range of wavelengths, so "band X at
epoch Y" may be assembled from several exposures. That is the backend's job.
The frontend only ever sees the assembled frame.

## Sensors and the curtain

`Area.layers` lists the other sensors. `hips` is an **Aladin Lite HiPS base URL**
handed straight to Aladin, which draws it on the right of the curtain. The mock
returns real IRSA mirrors (WISE, 2MASS, DSS2, IRAS), which work today. Set
`coverage: { ok: false, reason }` for sensors with no coverage here; they show
disabled with the reason. The Aladin cutout that shows while SPHEREx loads
(and when it fails) is DSS2 from the same mirror: `PLACEHOLDER` in `sky-view.tsx`.

Aladin is the placeholder only; the page owns the view and pushes it into Aladin
each frame, so everything stays aligned. Aladin's logo is kept visible (its terms
of use); see `.explore-view .aladin-logo-container` in `globals.css`.

## What is mock today (and how to tell)

Everything behind `ExploreApi`: frames (procedural stars, clouds and three moving
things), the spectrum, the type guess, motion tracks, verify outcomes, epochs
(5, uneven dates). The page shows a "Mock SPHEREx data" tag while the mock is on.
The mock stars do **not** match the real sky, so dragging the curtain over a real
layer shows two different skies. That goes away with real frames.

Mock-only test switches, as `?mock=` on the Explore URL (comma separated):
`fail-data`, `fail-motion`, `fail-verify`, `no-movers`, `slow`.

## Spec items that are placeholders until decided

- **Suggestion thresholds** (`SUGGESTION_THRESHOLDS` in `motion-language.ts`): need the science team (spec Q10).
- **Band wavelengths and copy** (`bands.ts`): to be validated by the science team.
- **Points table** (`points.ts`): numbers are made up.
- **Zoom limit**: 4 screen px per sensor pixel (`fov.ts`), to be tuned.
- **Default bands**: Starlight + Warm glow. **Spectrum epoch**: the one under the playhead, with an "All combined" toggle (spec Q3).
- **Secondary sensor epochs**: not used; layers stay fixed (spec Q4).
- **Verify partial matches** (spec Q7): the contract has `unexplained.nearMatch`; the backend decides the threshold.
- **Move / Select toggle** plus Shift+drag (spec Q1) is in.

## Share this find

Only the entry point exists. The button (unexplained results only) stores a
`ShareDraft` (box, bands, epochs, spectrum, track, view URL) in `sessionStorage`
under `SHARE_KEY` and goes to the placeholder route `/share`. The Share flow can
read the draft from there.

## URL state

The page keeps the URL current (`ra`, `dec`, `fov`, `bands`, `epoch`, `layer`), so
"Copy link" is just the address bar. The selection box and analysis results are
not in the URL yet.

## Things I'd check first on first contact

1. Frame orientation and alignment (flipped east/west is the classic one). Put
   a real star on the page and compare with the WISE layer through the curtain.
2. `Area.epochs` order does not matter (the page sorts by date), but ids must be stable.
3. Response times of `inspect`: the page calls it ~220 ms after a box stops changing.
4. Frame size: the page decodes with `createImageBitmap`, so a few MB per frame is fine, 100 MB is not.
