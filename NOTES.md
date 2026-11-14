# Implementation notes

Findings from live calls that differ from, or add to, `SPHEREX_POINT_INSPECTION_PLAN.md`.

## Contract changes (proposed — please review)
- **`FrameRef.frame_id` added** (`f"{obs_id}D{detector}"`). `obs_id` is shared by the 6
  detectors of one exposure (Barnard's Star, DR1: 240 SIA rows, 121 unique `obs_id`s), so it
  cannot key frames or the cutout cache. The suffix matches IRSA's file naming
  (`..._0594_4D3_spx_...fits`). `FrameMeasurement` / `SpectrumSample` / `LightCurveSample`
  carry `frame_id` too, and `solar_system_by_frame` should be keyed by it.
- `FrameRef` also gained `collection`, `em_min_um`, `em_max_um`, `pixel_scale_arcsec`
  (Measurement needs the pixel scale for the Jy conversion; λ range is a sanity check).
- `Cutout` is a dataclass, not pydantic (it holds numpy arrays / headers and is never serialised).
- `PointSummary.spectrum_binned` added for the 102-bin version (brief §7).
- `FramesResponse` added for `/inspect/frames` (`n_found` before capping, `n_returned`, `collections`).

## Verified 2026-11-14
- `Irsa.list_collections(servicetype='SIA', filter='spherex')` → `spherex_dr1`,
  `spherex_dr1_cube`, `spherex_dr1_deep`, `spherex_qr3`, `spherex_qr3_deep`. `_cube` is
  excluded (not single-exposure frames).
- SIA column units: `t_min/t_max` d (MJD), `s_pixel_scale` **arcsec** (6.15), `em_min/em_max`
  **metres**, `s_region` `POLYGON ICRS ...` (closed, 5 vertices).
- DR1 and QR3 do not overlap in time (Barnard's: DR1 MJD 60902–61165, QR3 61268–61305), so
  querying both and deduping on `frame_id` is correct. `_deep` returned 0 rows here.
- **Cutout URL pattern works on the IBE path**: `access_url + "?center={ra},{dec}d&size={deg}"`
  returns the 7-HDU MEF (PRIMARY, IMAGE, FLAGS, VARIANCE, ZODI, EPSF, WCS-WAVE).
  `VERSION` = 7.0.5; `PSF_FWHM` ≈ 7.4″ (D3), 8.6″ (D5).

## Risks seen live (affect step 2)
- **Cutouts are ~4 MB each even at 0.02° (12×12 px)** — the EPSF table dominates. 363 frames ≈
  1.4 GB. The cache, `max_frames` and bounded concurrency matter more than planned.
- IRSA returned transient **503** on cutouts and **502** on SIA capabilities; one retry after
  10 s succeeded. Discovery retries 3× with 5 s × attempt backoff.
- `/inspect/frames` for Barnard's took ~22 s on the first live call (vs ~3 s for a single
  collection query in a probe) — likely slow/retried SIA responses. Watch this.
- **SIMBAD CDS main (`simbad.cds.unistra.fr`) returned 404** on its TAP capabilities;
  the Harvard mirror (`simbad.harvard.edu`) worked. Field Context (step 5) needs a mirror fallback.

## Step 2 — Cutout Retrieval (verified 2026-11-14)
- Done check passed live: **20/20 cutouts in 31.7 s cold** (concurrency 8, 0.02°), **0.5 s warm**
  (all from cache). That's ~1.6 s/cutout effective → 200 frames ≈ 5 min cold, all 363 ≈ 10 min.
  The default `max_frames=200` makes a cold `/inspect` slow; pre-warming the test targets matters.
- Cutout layout: 7 HDUs as the brief says, but **EPSF has 451 rows, not 441** (brief says a
  21×21 grid). Columns: `BINX, BINY, XCENTER, YCENTER, XWIDTH, YWIDTH, NSTAR, NEFF_MEAN, CWAVE,
  CBAND, EPSF(33×33 f8)`. EPSF is 3.95 MB of the ~4 MB file; zlib saves only ~6%, so the cache
  stores raw bytes uncompressed (default limit 10 GB, env `SPHEREX_CACHE_SIZE_GB`).
- `WCS-WAVE` columns: `X(9), Y(14), VALUES(14,9,2)`. Spectral WCS via `key='W'`, `sip=None` works
  (D3 centre pixel → 2.288 µm, Δλ 0.057 µm).
- **SIA `em_min/em_max` is not a hard per-pixel bound**: a D1 pixel gave λ = 0.7436 µm vs
  `em_min` = 0.7455 µm. Step 3's "λ inside that detector's range" check should allow ±Δλ/2.
- The alternate-WCS "Inconsistent SIP" INFO is filtered on `astropy.log`.
- Any per-frame error (5xx, transport, truncated/invalid FITS, WCS error) is retried 3× with
  10 s × attempt backoff; 4xx other than 429 fail at once. Invalid bytes are never cached;
  a corrupt cache entry is dropped and re-downloaded.
- Fixtures (`tests/fixtures/`, 11 MB total — each 0.02° cutout is ~4 MB because of EPSF):
  `barnard_first_d1` (MJD 60914.2), `barnard_latest_d1` (61285.3; same detector, Δt ≈ 371 d,
  Barnard's should move ≈ 10.5″ ≈ 1.7 px), `barnard_latest_d6` (61303.2, 4.4–5.0 µm).
  `manifest.json` holds each frame's `FrameRef`.
