# Plan: SPHEREx Point Inspection — Feature API (Space Apps 2026 · Planet X and SPHEREx)

## Context
The challenge asks for a public tool that shows how a patch of sky changes in SPHEREx data, so people can spot movers and variables. It suggests overlaying Gaia/WISE and generating spectra on the fly.

**New workflow (after the pivot):** Aladin gives coordinates → find the SPHEREx exposure frames covering that point → pull information out of those frames: spectrum, position in earlier frames vs. now, brightness over time, quality flags. A separate component uses each frame's metadata (footprint and timestamp) to ask other catalogs **which known bodies are in or around that frame at that time**. That gives the measurements an identity.

**Scope:**
- **Feature API only.** The UI (Aladin Lite, flip-book, charts) comes later and only calls this API.
- Components are encapsulated, with **one responsibility each**. Only the orchestrator wires them together.

**Stack:** Python 3.11, FastAPI, pydantic, astropy, astroquery (`Irsa`, `Simbad`, `Gaia`), httpx (async), numpy/photutils (centroid/photometry), diskcache, pytest.

## Key facts from the IRSA SPHEREx docs (they shape the design)
- **Frame discovery:**
  - IRSA TAP: `spherex.plane` ⨝ `spherex.artifact`, `CONTAINS(POINT, p.poly)`, filter `energy_bandpassname` (`SPHEREx-D1..D6`), sort by `time_bounds_lower`. Data shows up right after the weekly ingest.
  - Or SIA collections `spherex_dr1`, `spherex_qr3` (+ `_deep`), which lag ~1 day.
  - Example result: 443 frames for one point. **Volume is the main performance risk.**
- **Cutouts:** `https://irsa.ipac.caltech.edu/{artifact.uri}?center={ra},{dec}d&size={deg}` returns a small MEF with `IMAGE` (MJy/sr), `FLAGS`, `VARIANCE`, `ZODI` (background, not subtracted), `EPSF` (PSF grid), `WCS-WAVE`.
- **Spectral WCS:**
  - `WCS(header, fobj=hdul, key="W")` with `sip=None` gives the **wavelength at that pixel**.
  - **Each frame gives one wavelength sample at the point.** A spectrum is built by combining many frames, over 6 detectors and 0.75–5 µm.
- Pixel ≈ 6.2″, `PSF_FWHM` in the header, flag counts in `L2 N_*` keywords. The processing `VERSION` sits in the primary header.

## Component map (no overlapping responsibilities)
```
request ─▶ [1 Intake] ─▶ Target
              ─▶ [2 Frame Discovery] ─▶ FrameRef[]
              ─▶ [3 Cutout Retrieval] ─▶ Cutout[]
              ─▶ [4 Frame Measurement] ─▶ FrameMeasurement[]
              ─▶ [5 Time-Series Aggregation] ─▶ PointSummary
              ─▶ [6 Field Context] (FrameRef[] + PointSummary) ─▶ FieldContext
              ─▶ [7 Reporting] ─▶ response
        all wiring in [0 Orchestrator]
```

| # | Component | Owns (only this) | Does NOT do | Network? |
|---|---|---|---|---|
| 0 | **Orchestrator** `inspect_point()` | Order of calls, passing data, partial-failure policy | Any science, I/O details, formatting | no |
| 1 | **Intake** | Parse/validate RA/Dec (deg or sexagesimal → ICRS), optional time range, detector bands, cutout size (default 0.05°, max ~0.2°), frame cap | Knowing about IRSA or catalogs | no |
| 2 | **Frame Discovery** | IRSA TAP/SIA query → list of frames: `obs_id`, detector, `t_min/t_max`, footprint polygon, release (DR1/QR3), cutout URL | Downloading pixels, measuring | **IRSA metadata** |
| 3 | **Cutout Retrieval** | Downloading cutout MEFs in parallel with retries, timeouts, disk cache, per-frame status | Interpreting pixels | **IRSA data** |
| 4 | **Frame Measurement** | **Per single cutout:** find the source near the target (centroid with EPSF/2D Gaussian), measured RA/Dec ± error, wavelength/bandwidth at that pixel, zodi-subtracted forced-photometry flux ± error (from VARIANCE), FLAGS bits at the source, SNR | Combining frames, catalogs | no (pure) |
| 5 | **Time-Series Aggregation** | **Across frames:** spectrum (flux vs λ, with bad-flag samples dropped), position track → proper-motion fit, "first seen" vs "latest" position, light curve + variability metric, quality summary | Per-pixel work, catalogs | no (pure) |
| 6 | **Field Context** | Uses **frame metadata** (footprint, mid-time) and the measured position to ask other services which **known bodies** are around: SIMBAD/Gaia DR3/CatWISE (propagated to frame time) and JPL Small-Body ID API (asteroids/comets at frame time). Cross-matches the measured source to the best one | Reading pixels, building spectra | **catalogs** |
| 7 | **Reporting** | Public JSON shape, units, links (SIMBAD, Gaia, JPL, IRSA frame/cutout URLs for a future flip-book), status passthrough | Any decision or re-ranking | no |

Boundaries in one line:
- 2 and 3 are the only components that talk to IRSA, and 6 is the only one that talks to other catalogs.
- 4 looks at one frame at a time, and 5 is the only one that looks across frames.
- 7 is the only one that knows the public JSON.

## Data contracts (`spherex_inspect/models.py`, agree these first)
- `InspectRequest`: `ra`, `dec`, `time_start?`, `time_end?`, `bands?: list[1..6]`, `cutout_size_deg?`, `max_frames?` (default 200), `include_context?: bool = true`
- `Target`: `coord`, `time_range`, `bands`, `cutout_size_deg`, `max_frames`
- `FrameRef`: `obs_id`, `detector`, `t_mid` (MJD), `t_min`, `t_max`, `footprint` (polygon), `release`, `cutout_url`, `full_url`
- `Cutout`: `frame: FrameRef`, `image`, `flags`, `variance`, `zodi`, `epsf`, `header`, `wave_wcs`, `version` — or `status=failed`
- `FrameMeasurement`: `obs_id`, `t_mid`, `wavelength_um`, `bandwidth_um`, `detected: bool`, `ra_meas`, `dec_meas`, `pos_err_arcsec`, `offset_from_target_arcsec`, `flux_jy`, `flux_err_jy`, `snr`, `flag_bits`, `flag_names: list[str]`, `usable: bool` (flux is in **Jansky**, never MJy/sr; see Implementer brief §3)
- `PointSummary`:
  - `spectrum[]`: `wavelength_um`, `flux`, `err`, `obs_id`
  - `positions[]`: `t_mid`, `ra`, `dec`, `err`
  - `first_position`, `latest_position`
  - `proper_motion?`: `pm_ra_cosdec`, `pm_dec`, `err`, `significance`
  - `light_curve[]`, `variability` (chi² / amplitude, per band)
  - `quality`: `n_frames`, `n_usable`, `flag_summary`
- `KnownBody`: `name`, `object_class` (star, brown_dwarf, variable_star, galaxy, qso, asteroid, comet, unknown), `source_catalogs`, `ra_at_t`, `dec_at_t`, `t_ref`, `separation_arcsec`, `pm?`, `mags`, `is_solar_system`, `ids`
- `FieldContext`: `best_match?: KnownBody + match_score`, `nearby: list[KnownBody]`, `solar_system_by_frame: {obs_id: [KnownBody]}`, `verdict` (`matched` | `ambiguous` | `no_known_match`), `status_by_source`
- `InspectResponse`: `query`, `frames` (lightweight refs), `summary`, `context`, `warnings`, `status`

## Component details

**2 · Frame Discovery** (`discovery.py`)
- **SIA query first** (its columns are verified; see Implementer brief §1). Use the TAP query from the IRSA cutout tutorial only as an optional "freshest data" path, after its columns have been checked.
- Filter by time range and bands; order by time; cap at `max_frames`. When capping, spread the picks evenly across time and detectors, not just the first N.
- Returns per-frame metadata that 6 needs (footprint + time). Downloads nothing.

**3 · Cutout Retrieval** (`retrieval.py`)
- `async fetch(frames) -> list[Cutout]`
- Bounded concurrency (~8), retry with backoff (the docs warn about transient `IncompleteRead`/timeouts), `remote_timeout=120`.
- Cache keyed on `(obs_id, ra, dec, size)`.
- A failed frame is marked failed and the rest carry on.

**4 · Frame Measurement** (`measurement.py`)
- Spatial WCS → target pixel. Subtract `ZODI`.
- Centroid inside a ~2 px window (EPSF-weighted fit, falling back to a 2D Gaussian), then convert back to RA/Dec.
- Spectral WCS (`key="W"`, `sip=None`) at the centroid pixel gives λ and Δλ.
- Forced aperture/PSF photometry with error from `VARIANCE`. Read the `FLAGS` bits at the source and set `usable`.
- Pure function of one `Cutout`, so it is easy to unit-test with saved fixtures.

**5 · Time-Series Aggregation** (`aggregation.py`)
- **Spectrum:** usable measurements sorted by λ. Optionally bin to the 102 SPHEREx channels.
- **Motion:** weighted linear fit of RA/Dec vs time. Report pm only if it is significant (> 3σ) and the time baseline is ≥ 1 survey pass (~6 months). `first_position` / `latest_position` are the earliest and latest usable centroids.
- **Variability:** per-detector light curve. Compare against a constant model (χ²) **within the same wavelength band only**, because each frame samples a different λ.

**6 · Field Context** (`context/`), uses frame metadata, not pixels
- `fixed.py`: SIMBAD + Gaia DR3 + CatWISE2020 cone search around the target (radius = cutout half-size). **Propagate proper motion to each frame's `t_mid`** (astropy `apply_space_motion`). Needed for Barnard's Star (~10″/yr) and WISE 0855.
- `solar_system.py`: for each frame (or one per distinct day), call JPL `sb_ident.api` with the frame center, its time and FOV. Fall back to IMCCE SkyBoT. **The observer must be given as a state vector (`xobs`).** The API rejects the geocentric code `mpc-code=500`. See Implementer brief §5.
- `match.py`: cross-match the measured source (latest position and its pm, if any) against the known bodies at matching times.
  - Score = positional likelihood + pm agreement + infrared brightness agreement (W1/W2/Ks vs the SPHEREx flux at a similar λ).
  - Verdict: `ambiguous` when 2 or more bodies fall within one PSF (common at 6″). `no_known_match` means a moving or stationary source no catalog explains: **a candidate discovery**.
- Each catalog is behind one adapter interface with its own timeout. One failing source shows up in `status_by_source` and does not break the response.

**0 · Orchestrator + HTTP** (`__init__.py`, `api/app.py`)
- `async inspect_point(req) -> InspectResponse`
- 6 runs concurrently with 3–5 when possible: it only needs `FrameRef[]` plus the target, and the final match step waits for `PointSummary`.
- HTTP:
  - `GET /inspect?ra=&dec=&start=&end=&bands=&size=`
  - `GET /inspect/frames?ra=&dec=…`: discovery only, fast, for a future flip-book
  - `GET /context?ra=&dec=&t=`: context only
- The HTTP layer contains no logic.

## Layout
```
spherex_inspect/
  __init__.py  models.py  config.py
  intake.py  discovery.py  retrieval.py  measurement.py  aggregation.py  reporting.py
  context/  base.py  fixed.py  solar_system.py  match.py
  cache.py
api/app.py
tests/ unit/ (one per component, using saved cutout FITS + catalog fixtures)   integration/test_targets.py
```
Once `models.py` is agreed, teammates can each own one component.

## Build order (each step is demoable)
1. `models.py`, Intake, Frame Discovery. `/inspect/frames` lists real frames for Barnard's Star.
2. Cutout Retrieval + cache.
3. Frame Measurement (centroid, λ, flux, flags).
4. Aggregation: spectrum + position track. **Milestone:** Barnard's Star shows motion between first and latest frames, and the spectrum plots.
5. Field Context (fixed catalogs + propagation) + match. Barnard's Star → matched.
6. Field Context (solar system), plus a "frame contains asteroid X" list.
7. Variability metric (RW Aur, R Dra) and the candidate-discovery warning.
8. Stretch: co-add per detector to boost signal-to-noise (suggested in the brief); difference-image metric for movers.

## Gaps and risks
- **SPHEREx gives pixels, not positions.** "Previous/current position" is *our* centroid measurement. Precision is about 1″ at best (6.2″ pixels), so only fast movers (≳ 1″/yr) show real motion over the ~1.5-year archive. Report pm only when it is significant.
- **A fixed point does not follow a fast mover.**
  - Asteroids cross a cutout within hours, so a stack at one RA/Dec will show them once, then nothing.
  - The asteroid list from Field Context explains those one-off detections.
  - Tracking a mover across frames needs ephemeris-guided cutouts. That is a possible later feature.
- **One wavelength per frame.** A full 0.75–5 µm spectrum needs frames from all 6 detectors across a survey pass. Partial coverage must show as gaps, not be interpolated.
- **Volume and latency.** Hundreds of frames per point and ~20 s TAP queries. Mitigate with `max_frames`, time and band filters, concurrency, caching, and pre-warming the 5 test targets before judging.
- **Artifacts.** Persistence, cosmic rays and ghosts look like transients. Gate everything on FLAGS before calling something a discovery.
- **Data releases.** Never hard-code DR1/QR3; read the collections list. QR3/DR1 supersede QR2.

## Verification
- **Unit (offline):**
  - Measurement on a saved cutout: centroid within 1 px of a known Gaia star, λ matches the tutorial's spectral-WCS value.
  - Aggregation on synthetic tracks: recovers an injected pm; no false pm on a constant track.
  - Context propagation: Barnard's Star moved J2016 → frame time ≈ published pm × Δt.
  - Reporting schema snapshot.
- **Integration (live or recorded), `tests/integration/test_targets.py`:**
  - Barnard's Star → significant pm toward the known direction; context `matched` = Barnard's Star
  - WISE 0855 (08h55m10.831s, −07°14′42.53″) → faint, red spectrum rising toward 4.5 µm; matched brown_dwarf via CatWISE
  - Eps Indi B → `ambiguous` (blended pair)
  - RW Aur, R Dra → high variability metric; matched variable_star
  - A frame on the ecliptic → the solar-system list is non-empty
- **Resilience:** mock IRSA failing on 30% of cutouts, and SIMBAD timing out. The response still returns, with per-frame and per-source status filled in.
- **Manual:** `uvicorn api.app:app`, then
  ```bash
  curl "localhost:8000/inspect?ra=269.452&dec=4.6933&bands=1,4,6"
  ```

---

# Implementer brief (read before writing code)

You are implementing the plan above. These are the facts, numbers and rules it leaves open. Items marked **VERIFIED** were checked against the official docs on 2026-11-14. Items marked **VERIFY** must be confirmed with a live call before you build on them, and any difference must be reported back.

## 0. Rules of engagement
- Build **one step of the Build order at a time**. After each step, run the tests, summarize what works and what doesn't, and **stop for review** before starting the next one.
- Treat `models.py` as the contract. If a component needs a field changed, propose the change and explain why. Do not change it silently.
- **Out of scope:** any UI or frontend code, plotting, Aladin, a database, authentication, deployment. Only components 2 and 3 contact IRSA, and only component 6 contacts SIMBAD, Gaia, CatWISE and JPL.
- **Never invent an API column, parameter or flag name.** If something here doesn't match what a live service returns, trust the service, note it in `NOTES.md`, and carry on.
- Units everywhere: positions in ICRS degrees, times in MJD (float), proper motion in mas/yr, wavelength in µm, flux in Jy, separations in arcsec.

## 1. Frame discovery (IRSA)
- **VERIFIED:** SIA via `Irsa.query_sia(pos=(SkyCoord, radius), collection=[...])`. Collections: `spherex_dr1`, `spherex_qr3`, `spherex_dr1_deep`, `spherex_qr3_deep`. Build the list at startup with `Irsa.list_collections(servicetype='SIA', filter='spherex')` and keep the newest DR and QR. Don't hard-code it. QR2 is superseded; skip it.
- **VERIFIED** SIA columns to use:
  - `obs_id`
  - `energy_bandpassname`: `'SPHEREx-D1'`..`'SPHEREx-D6'`; parse the detector number from it
  - `t_min`, `t_max`: MJD
  - `s_region`: footprint polygon
  - `access_url`: full MEF URL under `https://irsa.ipac.caltech.edu/ibe/data/spherex/...`
  - `s_pixel_scale`, `em_min`, `em_max`, `obs_collection`
- Search radius: 1″. You want frames that *contain* the point.
- **VERIFY:** cutout URL = `access_url + f"?center={ra},{dec}d&size={size_deg}"`. The tutorial builds the same pattern from the TAP `artifact.uri`. Confirm on the first live run that the IBE path accepts it and returns a 7-HDU MEF.
- **VERIFY:** TAP path (`spherex.plane` ⨝ `spherex.artifact`, `CONTAINS(POINT('ICRS',ra,dec), p.poly)`, `p.energy_bandpassname`, `p.time_bounds_lower`, `a.uri`). Before relying on other columns, list them with `SELECT * FROM TAP_SCHEMA.columns WHERE table_name IN ('spherex.plane','spherex.artifact')`. TAP is optional. Use it only for data newer than SIA's ~1-day lag.
- Expect several hundred frames per point. TAP queries take ~20 s, so set generous timeouts.

## 2. Cutout files: structure (VERIFIED)
HDUs in order:
0. PRIMARY: contains `VERSION`
1. `IMAGE`: MJy/sr, zodi **not** subtracted
2. `FLAGS`: int32 bitmap
3. `VARIANCE`: (MJy/sr)²
4. `ZODI`: MJy/sr
5. `EPSF`: 441 rows (a 21×21 grid of detector regions), each a 33×33 ePSF oversampled ×5 (`OVSMPX`/`OVSMPY`), with columns `XCENTER`, `YCENTER`, `CWAVE`, `CBAND`
6. `WCS-WAVE`: lookup table

Useful keywords:
- Spatial WCS: `WCS(hdul['IMAGE'].header)`. It is TAN-SIP.
- Spectral WCS: `w = WCS(hdul['IMAGE'].header, fobj=hdul, key='W'); w.sip = None`, then `w.pixel_to_world(x, y)` → (wavelength, bandwidth).
- Header keywords: `DETECTOR`, `OBSID`, `PSF_FWHM`, `L2 N_*` flag counts.
- Set `astropy.utils.data.conf.remote_timeout = 120`. Wrap reads with `(TimeoutError, urllib.error.HTTPError, http.client.IncompleteRead, http.client.RemoteDisconnected)` and retry 3× with 10 s × attempt backoff.
- Suppress astropy's alternate-WCS SIP INFO messages with the logging filter used in the tutorial.

## 3. Measurement numbers
- Background: `IMAGE − ZODI`, then subtract the median of an annulus with radius 4–6 px, using unflagged pixels only. The zodi model is not perfect.
- Centroid: search a 5×5 px box around the target pixel. Use `photutils.centroids.centroid_2dg` (in `photutils>=1.13`) to start. Add the ePSF fit later.
  - `detected = True` when the peak SNR is ≥ 5.
  - `pos_err_arcsec ≈ FWHM_arcsec / (2.35 × SNR)`, with a floor of 0.3″.
- Photometry: circular aperture with radius **2 px** at the centroid, from `photutils.aperture`.
  - Apply an aperture correction from the nearest ePSF row (closest `XCENTER, YCENTER`): fraction of ePSF flux inside 2 px, after rebinning the ×5 oversampled ePSF to native pixels.
- **Flux unit conversion (do not skip):** `flux_Jy = Σ(pixel MJy/sr) × Ω_pix × 1e6`, where `Ω_pix = (s_pixel_scale_arcsec × π/(180×3600))²` sr.
  - Error: `sqrt(Σ VARIANCE) × Ω_pix × 1e6`.
  - Get `s_pixel_scale` from the SIA row (check its unit), or derive it from the WCS with `proj_plane_pixel_scales`. They must agree within 2%.
- `wavelength_um` / `bandwidth_um`: spectral WCS evaluated at the centroid pixel.

## 4. Flags (VERIFIED names; bit numbers can change)
Read the bit meanings from the FLAGS header at runtime: `MSKNnnnn` = name and `MSKDnnnn` = description for bit `n`. **Map by name, never by hard-coded bit number.** Classify any OR'd bits inside the 2 px aperture as follows:
- **Unusable** (`usable=False`): `TRANSIENT, OVERFLOW, SUR_ERROR, NONFUNC, MISSING_DATA, HOT, COLD, NONLINEAR, PERSIST, OUTLIER, GHOST, GHOST_FPA, GHOST_EXT, STREAK, BLOOM, SNOWBALL, HALO`
- **Warning only** (keep the sample, but list the flag): `DICHROIC, PHANMISS, CROSSTALK`
- **Ignore:** `SOURCE` (it means "a known source is here", which is expected) and `FULLSAMPLE`
- An unknown flag name counts as a warning, and gets logged once.

## 5. JPL Small-Body Identification API (VERIFIED, docs v1.1)
- `GET https://ssd-api.jpl.nasa.gov/sb_ident.api`
- **Observer:** `mpc-code=500` (geocentric) is **rejected**. Use `xobs=<x,y,z[,vx,vy,vz]>`, the geocentric ICRF position in km and velocity in km/s.
  - Ideally use SPHEREx's own state at the frame time, from JPL Horizons. **VERIFY** whether Horizons has a SPHEREx spacecraft ID.
  - Otherwise, **VERIFY** whether `xobs=0,0,0` is accepted. If it is not, use a fixed ~7000 km geocentric vector, and add a `warnings` note that rates and very-near-Earth objects are approximate.
  - Without the velocity part, the API returns no rates.
- Required: `obs-time` as `YYYY-MM-DD_hh:mm:ss` or JD (use the frame's `t_mid` converted to JD).
- FOV: `fov-ra-center=hh-mm-ss.ss`, `fov-dec-center=dd-mm-ss.ss` (negative declinations start with `M`, e.g. `M07-14-42.5`), `fov-ra-hwidth`, `fov-dec-hwidth` in degrees (use the cutout half-size).
- Use `two-pass=true&suppress-first-pass=true` for accurate positions, and `mag-required=false` so faint objects still appear.
- Response: check `signature.version == "1.1"`. Read rows from `data_second_pass`, with column names in `fields_second`: name, RA, Dec, distances from center (″), V mag, RA/Dec rate. **VERIFY** the rate units against a known asteroid; the docs label them "deg/s", but the example values look like ″/h.
- Cache one call per (cutout center, day) for frames within the same day.

## 6. Field Context numbers (starting values in `config.py`)
- Cone radius = cutout half-size, capped at 120″.
- Propagation: in astropy, `SkyCoord(ra, dec, pm_ra_cosdec, pm_dec, distance=Distance(parallax=…), obstime=Time(ref_epoch, format='jyear'))` then `.apply_space_motion(new_obstime=Time(t_mid, format='mjd'))`. If parallax is missing or ≤ 0, propagate without distance. Reference epochs: Gaia DR3 = 2016.0, CatWISE2020 = 2015.4. **VERIFY** CatWISE's reference epoch from the IRSA table description. SIMBAD is already J2000 and has PMs, so propagate it too.
- Cross-match group radius: 1.5″. σ_psf = 3″.
- Scoring weights: position 0.6, pm agreement 0.25, infrared brightness 0.15.
  - pm agreement is only used when the measured pm is significant at > 3σ.
  - IR brightness is only used when there is a SPHEREx sample within 0.3 µm of Ks (2.16), W1 (3.4) or W2 (4.6).
- `matched` if the top score is ≥ 0.6 **and** beats the runner-up by 0.2. `ambiguous` if ≥ 2 bodies lie within 6″. Otherwise `no_known_match`.
- Taxonomy: map SIMBAD `otype` to `object_class`. If there is no SIMBAD type, mark the object `brown_dwarf` when CatWISE W1−W2 ≥ 1.0 and total pm ≥ 200 mas/yr. Otherwise `unknown`.

## 7. Aggregation numbers
- Proper motion: weighted least squares on RA·cos(Dec) and Dec offsets vs time.
  - Report it only if the baseline is ≥ 150 days, there are ≥ 6 usable detections, and |pm|/σ_pm ≥ 3.
- Variability: per detector, compute reduced χ² of flux against a weighted-mean constant. Flag `variable` if it is ≥ 5 with ≥ 5 samples. Report the amplitude as max/min of the per-detector medians.
- Spectrum: keep raw samples. Also provide a binned version with 102 equal-width bins in log-λ (0.75–5.0 µm), using inverse-variance weighted means. Empty bins are `null`, not interpolated.

## 8. Test targets
Coordinates below are approximate J2000. **In tests, resolve them by name** through SIMBAD (`Simbad.query_object`) and keep the values here only as a sanity check.
| Target | Approx RA, Dec (deg) | Expectation |
|---|---|---|
| Barnard's Star | 269.452, +4.693 | pm ≈ (−0.80, +10.36) ″/yr; matched star |
| WISE 0855−0714 | 133.795, −7.245 (given in the challenge brief) | faint, red; matched brown_dwarf (CatWISE) |
| Epsilon Indi B (Ba/Bb) | ≈ 331.0, −56.8 | `ambiguous` or matched BD pair |
| RW Aurigae | ≈ 76.96, +30.40 | variable |
| R Draconis | ≈ 248.17, +66.75 | variable |
| Asteroid case | choose one: run the sb_ident API on any real SPHEREx frame with ecliptic latitude below 5° and pick a V < 17 object | appears in `solar_system_by_frame` |

Remember that the archive starts in 2025, so Barnard's Star should be about 100″ away from its J2000 position.

## 9. Project setup
- Python ≥ 3.11. `pyproject.toml` with:
  - `astropy>=6.1`, `astroquery>=0.4.10`, `photutils>=1.13`, `numpy`, `fastapi`, `uvicorn`, `pydantic>=2`, `httpx`, `diskcache`
  - dev: `pytest`, `pytest-asyncio`, `pytest-recording` (vcrpy), `respx`
- astroquery calls block, so wrap them in `await asyncio.to_thread(...)`. Use `httpx.AsyncClient` for JPL and for cutout downloads (open the FITS from bytes with `fits.open(io.BytesIO(...))`).
- Cache directory comes from env `SPHEREX_CACHE_DIR` (default `.cache/`). The cache must store raw cutout bytes and raw catalog responses, never derived results.
- Tests:
  - `pytest` runs offline by default.
  - Live tests use `@pytest.mark.live` and run with `pytest -m live`.
  - Commit 2–3 real cutout FITS files under `tests/fixtures/` (keep them small: 0.02° cutouts) for measurement unit tests. Capture them on the first live run.
- Per-step "done" checks:
  1. `/inspect/frames` for Barnard's Star returns ≥ 50 frames with all 6 detectors, sorted by time.
  2. 20 cutouts download in < 60 s, and a second run hits the cache.
  3. A fixture cutout gives a detection within 1 px of the Gaia-propagated Barnard's Star position, with λ inside that detector's range.
  4. The Barnard's Star summary reports a significant pm within 20% of the published value.
  5. Barnard's Star context → `matched`, best match "Barnard's Star".
  6. The asteroid case passes.
  7. RW Aur and R Dra are flagged variable. A blank field returns `no_known_match` or nothing detected.
