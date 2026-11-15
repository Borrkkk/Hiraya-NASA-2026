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
- Fixtures: superseded in step 3 (see below).

## Step 3 — Frame Measurement (verified 2026-11-14)

### Contract changes (proposed — please review)
- **`FrameMeasurement.position_usable` added.** Barnard's Star saturates every SPHEREx detector:
  the core pixels carry `OVERFLOW` + `BLOOM` (+ `TRANSIENT`/`SUR_ERROR`), sometimes a NaN pixel.
  By the brief's §4 rules every Barnard frame is flux-unusable — correct for the flux — but its
  centroid is still good (30 live frames: median 1.08″, max 3.91″ from Gaia). Without a separate
  position flag, step 4 could never measure Barnard's proper motion.
  `usable` keeps the brief's meaning (flux). `position_usable` = detected, not a peak-pixel
  fallback, and none of `PERSIST, GHOST, GHOST_FPA, GHOST_EXT, STREAK, HALO, SNOWBALL` in the
  aperture (`config.FLAGS_POSITION_UNUSABLE`). Saturation flags are allowed for position.
- `FrameMeasurement.aperture_correction` and `.note` (why nothing was measured) added.

### Plan / brief corrections
- **Barnard's Star has moved ≈ 276″ since J2000, not ≈ 100″** (10.36″/yr × 26.7 yr). A cutout
  centred on SIMBAD's J2000 position does not contain the star at all. The step-2 fixtures were
  centred there, so they were replaced. The old D1 one is kept as `blank_badpix_d1.fits` (blank
  field with a TRANSIENT/SUR_ERROR/NONFUNC bad pixel → tests non-detection).
- **Design gap to decide (affects the UI + Intake):** for any fast mover, the coordinate a user
  clicks in Aladin depends on the epoch of the survey image shown (DSS ≈ 1950s, 2MASS ≈ 2000).
  Measurement only searches ±2 px (±12″) around the target, so a click on Barnard's Star in an
  old image finds nothing. Options: (a) the UI sends a Gaia-epoch position; (b) Intake resolves
  the nearest high-pm Gaia star and propagates it (but Intake must not talk to catalogs);
  (c) a wider search box, which picks up neighbours. Not changed yet.
- EPSF row count varies by file: 441 in one D1 file, 451 in another. Code picks the nearest
  `(XCENTER, YCENTER)` row and never assumes a grid size.
- Brief §3 says to rebin the ePSF to native pixels before the 2 px aperture; it is integrated
  on the ×5 grid instead (radius 10 oversampled px). Same result for a centred source.

### Measurement choices (beyond the brief)
- Detector coordinates for the ePSF lookup come from the `A` WCS (`WCSNAMEA = '0-based active
  pixel coordinates'`): `det = cutout_px + 1 − CRPIXnA`.
- **Detection = peak SNR ≥ 5 in the 5×5 box AND the brightest valid pixel is a local maximum**
  over its valid 8-neighbours. Without the local-max rule a faint neighbour's wing on the box
  edge counted as a detection (blank fixture). Masked pixels are skipped, so a NaN saturated core
  still counts. The source is located by the brightest *flux* pixel, not the SNR peak (for
  saturated stars the variance peaks at the core, so the SNR peak is off-centre).
- Pixels with `NONFUNC, MISSING_DATA, HOT, COLD` or non-finite values are masked from the
  background, the centroid fit and the aperture sum; any masked pixel in the aperture adds
  `MASKED_PIXELS` to `flag_names` and makes the flux unusable.
- Background annulus uses pixels with no flags except `FULLSAMPLE` (so `SOURCE` pixels, i.e.
  other stars, are excluded); falls back to sigma-clipped finite pixels.
- **Position error floor 1.5″ when `OVERFLOW/BLOOM/NONLINEAR` are in the aperture** (0.3″
  otherwise, per brief). The SNR formula gives 0.3″ for Barnard's but the real scatter is ~1–4″;
  without this, step 4's pm significance would be wildly overstated.
- Non-detections still get a forced-photometry flux at the target pixel and can be `usable`
  (a valid flux sample for faint sources like WISE 0855); `ra_meas/dec_meas` stay null.
- Pixel-phase error: an exact 2 px aperture on the undersampled PSF (FWHM ≈ 1.2 px) loses a few
  % for off-centre sources (2.4% in the synthetic test). The planned ePSF fit fixes this.

### Live results
- 30 Barnard frames (all 6 detectors, MJD 60902–61305): 30/30 cutouts, **30/30 detected**,
  separation from Gaia-propagated position median 1.08″, max 3.91″ (< 1 px = 6.15″). 29/30
  position-usable (one `PERSIST`). 0/30 flux-usable (saturated). Fluxes 2–7 Jy, the right order
  for a J ≈ 5.2 M dwarf (saturated, so lower bounds).
- Fixtures now (`tests/fixtures/`, 15 MB): `barnard_first_d1` (MJD 60914.2), `barnard_latest_d1`
  (61285.3, Δt ≈ 371 d), `barnard_latest_d6` (61272.9), all 0.05° centred on Barnard's Gaia
  position propagated to 2026.0; `blank_badpix_d1` (old J2000-centred one). `manifest.json`
  holds each `FrameRef` and the Gaia DR3 astrometry (`_gaia_dr3_barnard`).

### For step 4
- Gaia propagation with `apply_space_motion` gives a **barycentric** position. Barnard's
  parallax is 0.547″, comparable to the per-frame scatter, so the pm fit (and the step-5
  comparison) should either fit parallax or compare against a parallax-corrected prediction.
- IRSA TAP (`list_collections`) failed 3× in a row once; Discovery now falls back to the last
  successful collections list stored in the disk cache.

## Step 4 — Time-Series Aggregation

### Contract changes (proposed — please review)
- `PointSummary.spectrum_flagged`: detected samples whose flux was rejected (e.g. saturated),
  each with its `flags`, for display only. Without it Barnard's Star (saturated in every frame)
  has no spectrum to plot at all. `spectrum` and `spectrum_binned` use usable samples only.
- `PointSummary.proper_motion_fit` + `proper_motion_note`: the fit is always returned; `proper_motion`
  is set only when it passes the brief's thresholds, and the note says why it didn't.
- `ProperMotion` gained per-component errors, `pm_total`, `position_angle_deg`, `baseline_days`,
  `n_used`, `n_rejected`, `reduced_chi2`, `ref_epoch_mjd`.
- `PositionSample` gained `frame_id`, `detector`, `used_in_fit`. `SpectrumSample` gained
  `bandwidth_um`, `detector`, `flags`. `QualitySummary` gained `n_detected`, `n_position_usable`,
  `n_failed`.

### Choices
- PM fit: weighted LSQ of tangent-plane offsets (RA·cosδ, δ) vs time, per axis. Errors scaled by
  √(reduced χ²) when > 1, so underestimated per-frame errors don't inflate the significance.
  Iterative 4σ outlier rejection, capped at 20% of points. Reported only if baseline ≥ 150 d,
  ≥ 6 detections used, and |pm|/σ ≥ 3 (brief §7).
- The fit does not model parallax (0.55″ for Barnard's). Over a ~1.1 yr baseline this biases the
  pm by at most a few %; fitting parallax is a later refinement.
- `first_position` / `latest_position` = earliest / latest position used in the fit.
- Spectrum and light curve include forced-photometry non-detections that are flux-usable.
- Variability is left empty until build step 7.
- `GET /inspect` now runs the whole pipeline up to aggregation; `context` is null with a warning
  until step 5.
- Live tests now use the real `.cache/` (offline tests stay isolated), so the demo targets stay warm.

### Live results (2026-11-14) — done check passed
- `inspect_point` on Barnard's Star (Gaia position at 2026.0, default `max_frames=200` of 358):
  199/200 cutouts, 199 detected, 187 position-usable, **0 flux-usable** (saturated everywhere).
  ~2.5 min cold.
- **|pm| = 10363 ± 268 mas/yr (38.7σ) vs Gaia 10393 → 0.3% off.** PA 349.5° vs Gaia 355.6°.
  pm_dec 10190 ± 268 (Gaia 10362); **pm_ra −1886 ± 268 (Gaia −802), a 4σ bias in RA.**
  Baseline 403 d, 0 rejected, reduced χ² 0.38 (the 1.5″ saturated floor is conservative in Dec).
- RA bias diagnosis: **not parallax** (removing the 0.55″ parallax changes pm by ~0.1″/yr).
  Not the NaN-masked cores (same bias with and without). Residuals vs Gaia: RA rms 1.25″, Dec
  0.6″; frames at some detector rotation angles (MJD ≈ 61110–61165) sit ~+0.5″ off in RA. Likely
  an orientation-dependent centroid systematic for saturated stars (bloom/readout direction
  rotating on the sky), or a WCS systematic. Needs an unsaturated high-pm star to separate the
  two. The planned ePSF fit (masking saturated pixels) is the natural fix.
- `spectrum` empty, `spectrum_flagged` 199 samples (all saturated) — the warning says so.
- IRSA SIA returned 502 for one collection (DR1 or a `_deep`) in 2 of 4 runs after retries.
  When DR1 drops out, the baseline shrinks to QR3's ~40 days and the pm is (correctly) withheld
  by the baseline gate; the response is `partial` with a warning. This happens often enough
  that a short SIA-result cache (raw rows, a few hours) is worth adding.

## Step 5 — Field Context: fixed catalogs + match (verified 2026-11-14)

### Done check passed (live)
- `inspect_point` on Barnard's Star (Gaia position at 2026.0): **verdict `matched`, best match
  "Barnard's star"** (Gaia DR3 4472832130942575872 + SIMBAD), 1.39″ from the measured position,
  score 0.82, class `variable_star` (SIMBAD otype `BY*`, a BY Draconis variable — not plain
  `star` as the brief's table expected). Next nearest known body 9.5″ away. ~49 s warm, of which
  ~41 s is the CatWISE timeout (catalogs run concurrently with retrieval + measurement).

### Contract changes (proposed — please review)
- `FieldContext.note` (why the verdict is what it is) and `FieldContext.t_ref` (MJD catalog
  positions were propagated to = the latest measured position's time).
- `KnownBody.ids` also carries `simbad_otype` when known.

### Verified
- **CatWISE2020** (IRSA `catwise_2020`): positions `ra_pm/dec_pm` at **MJD 57170 = 2015.405**
  (brief's value confirmed); `pmra/pmdec` in **arcsec/yr** ("apparent motion"); W1/W2 from
  `w1mpro_pm/w2mpro_pm`. The spatial index is on `ra/dec`, not `ra_pm/dec_pm`.
- **SIMBAD**: CDS main still 404 on TAP capabilities; the Harvard mirror works and is used as
  fallback (adapter remembers the working server). `basic` has no `coo_epoch` column on the
  mirror; positions are J2000. The mirror's ADQL parser rejects qualified names in `ORDER BY`.
  SIMBAD's main identifier for the star is `NAME Barnard's star` (lowercase "star"), so that is
  the name returned; the done check compares case-insensitively.
- **Gaia DR3** (ESA archive via astroquery): 165 rows for the widened Barnard cone in ~7 s.

### Plan / brief corrections
- **Cone + propagation alone misses fast movers.** The brief's cone (radius = cutout half-size,
  90″) is centred on the target at frame time, but catalogs store positions at their epoch:
  Barnard's Star is ~110″ from its Gaia J2016 position and ~280″ from its SIMBAD J2000 position.
  Adapters therefore search radius + 11″/yr × |Δt| and keep only rows already inside the cone
  or with |pm| × |Δt| large enough to reach it (filtered server-side in ADQL); the exact cone
  cut is applied after propagation.
- **SIMBAD returns exoplanets** (Barnard's Star b/c/d/e, otype `Pl`) with the host's
  coordinates. Left in, every planet host would come out `ambiguous`. They are dropped.
- With the brief's weights (position 0.6, pm 0.25), two catalog stars < 1″ apart can't reach the
  0.2 margin even when the measured pm clearly favours one → `ambiguous` with the right one
  ranked first. Honest at 6″ pixels; left as is.

### Choices
- Two-phase component: `fetch()` (network, runs concurrently with retrieval + measurement)
  and `build()` (pure: propagate → group → score → decide).
- Grouping across catalogs within 1.5″ after propagation; never merges two rows of one catalog.
  Astrometry priority Gaia > SIMBAD > CatWISE; name from SIMBAD when present.
- Scoring renormalises over the terms actually available (position always; pm only when the
  measured pm is ≥ 3σ; IR only with a usable SPHEREx sample within 0.3 µm of Ks/W1/W2), so a
  position-only match can still reach 0.6. The pm term is deliberately tolerant
  (σ = hypot(err, 10 % of |pm|, 50 mas/yr)) because of the step-4 RA systematic.
- Ks is not queried yet (no 2MASS adapter); IR scoring uses CatWISE W1/W2 only.
- Raw catalog rows are cached (SIMBAD 7 days, Gaia/CatWISE forever), keyed by the exact ADQL.
- `GET /context?ra=&dec=&t=` lists known bodies at time `t` (no pixels → no best match).

### Reliability
- **IRSA TAP hung on `catwise_2020` all session** — even `SELECT TOP 3` on a tiny cone
  elsewhere did not return within 280 s. CatWISE is reported as a timeout in
  `status_by_source` and the response is `partial`.
- `asyncio.wait_for` cannot stop a blocking worker thread: the abandoned TAP call kept the
  process alive ~5 min after the request returned. SIMBAD and CatWISE now go through pyvo with
  a `requests` session that has a default socket timeout (0.9 × adapter timeout), so threads
  end too. Gaia still uses astroquery's own client (no socket timeout) — fine so far, but worth
  the same treatment.

## Faster checks (2026-11-14)
Measured before: offline suite 32 s; live suite several minutes (one run hung ~6 min).

- **Offline: 32 s → 2 s.** 30 s was a test bug: the fake SIA backend lists `spherex_qr2` with
  no rows, so discovery waited out the real 5 s + 10 s retry backoff in two tests. Offline tests
  now run with zero retry backoff (`tests/conftest.py`).
- **Live: ~6 min → 50 s first run, 10 s warm.**
  - Steps 3–5 share one `inspect_point` run of Barnard's Star (`barnard_run` session fixture)
    instead of three full pipeline runs, with `max_frames=60` (spread across time and detectors;
    pm still 20.8σ, |pm| 10012 ± 480 vs Gaia 10393, verdict `matched`).
  - All live tests use the shared `.cache/`. The cold-download timing check (step 2) only runs
    with `SPHEREX_LIVE_COLD=1`.
- **Catalog outage memory (API too, not just tests).** A timeout / 5xx / connection failure
  is stored in the disk cache for 15 min (`CONTEXT_OUTAGE_S`); during that window the catalog
  is skipped at once with `status_by_source = "skipped: unavailable since HH:MM:SS (...)"`.
  This removed the ~41 s CatWISE wait from every request while IRSA TAP hangs. Query errors
  (bad ADQL, 4xx) never trip it, so bugs stay visible.
- **SIA frame lists cached** (raw rows, fresh for 6 h — `SIA_CACHE_TTL_S`; new data only
  arrives at the weekly ingest). When IRSA's SIA fails, an older cached list is used with a
  warning instead of losing that collection (and the DR1 baseline).
- How to run:
  - `pytest` — offline, ~2 s
  - `pytest -m live` — live, ~10 s warm
  - `SPHEREX_LIVE_COLD=1 pytest -m live` — adds the cold-download timing check

## Step 6 — Field Context: solar system (verified 2026-11-14)

### Plan change (please review): SkyBoT primary, JPL sb_ident fallback
The brief has JPL `sb_ident` as primary and SkyBoT as fallback. Live timings make that
impractical: **one two-pass `sb_ident` call took 91 s** (first pass alone 49 s, 18 s with
`xobs=0,0,0`), and a request covers ~one exposure per 2 frames (100 calls at the default 200
frames). **SkyBoT answered in 2.2 s.** So:
- **Primary: IMCCE SkyBoT** cone search per exposure (geocentric observer `-loc=500`), positions
  then **corrected to SPHEREx's own position** with an exact parallax shift (object distance
  `dg` from SkyBoT, SPHEREx geocentric ICRF state from Horizons). On the Vesta test case the
  geocentric position was 4.9″ off the Horizons-from-SPHEREx position; corrected, < 1.5″.
- **Fallback: JPL sb_ident** (two-pass, `xobs` = SPHEREx state) for exposures where SkyBoT fails,
  capped at 2 calls per request (`SB_IDENT_MAX_CALLS`).
- One query per exposure (`obs_id`): the 6 detectors share time and target; results are listed
  under every `frame_id` of that exposure. `solar_system_by_frame` holds non-empty frames only,
  keyed by `frame_id` (the brief said `obs_id`; see step 1's `frame_id` note).
- FOV = the cutout (cone radius = half-size × √2, then cut to the square); bodies fainter than
  V = 22 are dropped (`SOLAR_MAX_V`).
- SkyBoT outages are remembered for 15 min like the fixed catalogs.

### VERIFY items resolved
- **Horizons has SPHEREx**: `-163182` ("SPHEREx (spacecraft)", 2025-047E). Geocentric
  distance ≈ 7030 km, speed ≈ 7.6 km/s. One batched call returns states for many times
  (`TLIST`, chunks of 100); `TIME_TYPE='UT'` matters (default TDB moved the state ~600 km).
- **`sb_ident` accepts `xobs=0,0,0`** (without velocity the rate columns are omitted).
  `mpc-code=500` stays unused.
- **sb_ident rate units are ″/h** — the response field names say `RA rate ("/h)`.
- sb_ident `signature.version` = "1.1". Two-pass with the SPHEREx state put Vesta 0.47″ from
  Horizons; the first pass returns ~6000 coarse rows over the whole sky (ignore it).
- **SkyBoT returns HTTP 204 with an empty body when the field is empty.**
- Apparent rates from SPHEREx are dominated by its own orbital motion (Vesta: SkyBoT geocentric
  (−4.7, −11.4) ″/h vs Horizons-from-SPHEREx (−2.6, +9.9) ″/h). SkyBoT rates are geocentric
  and are reported as such (`ids.observer`).

### Done check passed (live)
- Asteroid case found by search (Horizons ephemeris of Vesta from SPHEREx, days at 80–100° solar
  elongation, SIA footprint check at the exact mid-time): **(4) Vesta, V = 7.3, in frame
  `2025W32_1A_0105_1D3` at MJD 60891.461818, RA 222.86623, Dec −11.90754.**
- `inspect_point` at that point for that day: `solar_system_by_frame` lists **4 Vesta for both
  detectors of the exposure (D3, D6), 0.2″ from the Horizons position** (SkyBoT + SPHEREx
  parallax correction), V 7.5 (SkyBoT). 6.7 s.

### Contract / plan change (please review)
- **A solar-system body in the frame of the latest measured position is now a match
  candidate.** Before, the Vesta run said `no_known_match … candidate discovery` although the
  detection *was* Vesta, because matching only used fixed-sky catalogs. Now it says
  `matched → 4 Vesta`. `nearby` stays the fixed-sky list; asteroids in other frames don't count.

### Timing
- Full live suite: ~28 s with cold SkyBoT/Horizons lookups, **~6 s warm**. Offline: ~2.4 s.

## Step 7 — Variability, candidate discovery, blank field (verified 2026-11-14)

### Done check (live)
| target | result |
|---|---|
| RW Aur (T Tauri) | **variable** in D1 (clean), D2, D5, D6 (saturated basis), amplitude ×1.6–2.7. Context `ambiguous`, top body RW Aur B — RW Aur is a 1.4″ binary, so that is correct |
| R Dra (Mira) | **not measurable**: NaN-masked saturated core in every frame (all 6 detectors say so). Context `matched` → V* R Dra (`variable_star`) |
| Barnard's Star (control) | not variable (reduced χ² 0.09, 0.31 on saturated D5/D6) |
| Blank field (Barnard's J2000 spot) | nothing detected; forced photometry reduced χ² 0.2–2.5, nothing flagged |

So the brief's "R Dra flagged variable" is **not met**, honestly: SPHEREx saturates at roughly
0.1–0.2 Jy, both brief targets are far brighter, and R Dra's cores are NaN. Measuring it needs the
ePSF fit to the unsaturated wings (the plan's "add the ePSF fit later").

### Plan / brief corrections (please review)
- **Variability model is a smooth spectrum per detector, not a constant.** Every frame samples a
  different λ even within one detector (D1 spans 0.75–1.1 µm), so the brief's constant model
  flags any star with a sloped spectrum (unit test shows it). Per detector: weighted polynomial
  in λ (degree ≤ 2, ≥ 3 dof), reduced χ² of the residuals with a 3% fractional floor; brief's
  threshold kept (≥ 5 with ≥ 5 samples). Amplitude = max/min of flux / model (only when the
  model is clearly > 0).
- **Saturated fallback** (`BandVariability.basis = "saturated"`): when a detector has < 5 clean
  samples, detected samples whose only problem is saturation (no masked core, no
  ghost/persistence/streak) are used with a 10% floor. Live margin: constant Barnard 0.1–0.2,
  RW Aur 5–12. Otherwise `note` says why nothing was measured.
- **Candidate discovery is flag-gated** (`FieldContext.candidate_discovery`, `n_clean_detections`):
  only `no_known_match` with ≥ 2 position-usable detections free of TRANSIENT, OUTLIER,
  PERSIST, GHOST*, STREAK, HALO, SNOWBALL, SUR_ERROR, MASKED_PIXELS. One clean frame → "an
  artifact or untracked mover is more likely". A warning is added when it fires. Never fires
  when all catalogs failed. (`PositionSample.flags` added to carry the aperture flags.)
- **Detection radius**: a detection must lie within 2 px of the target (the 5×5 box let a
  neighbour 2.8 px ≈ 17″ away through). The blank field's 19″ neighbour, mixed with forced
  photometry, had produced fake variability with amplitudes ×15–92.
- **Brightness plausibility veto in matching**: a candidate whose catalog flux, at a wavelength
  within 0.3 µm of a SPHEREx sample, is > 100× fainter than SPHEREx measured (saturated samples
  as lower bounds) is ruled out and does not count toward "ambiguous". Without it, R Dra's
  centroid (4″ off, wings only) matched a G = 19.4 Gaia star at 0.1″. Same-λ only: Gaia mags
  never veto a red object measured at 4.5 µm.
- Position-error floor 3″ for saturated detections with a masked core (R Dra's centroid was 4″
  off). Barnard's pm is now 14.6σ (was 20.8σ), |pm| 10060 ± 688 vs Gaia 10393.

### Reliability
- Horizons returned 502 once; the solar-system lookup fell back to geocentric SkyBoT positions
  and said so in `status_by_source`.
- Full live suite: 9 passed, 1 skipped (cold timing, opt-in), 18 s warm. Offline: 137 in 2.3 s.

### ePSF wing fit for masked-core saturated stars (added after step 7 review)
- When a detection has NaN-masked pixels in its aperture (a saturated core), measurement fits the
  SPHEREx ePSF (amplitude + position) to the pixels within 4 px that carry none of
  `FLAGS_WING_EXCLUDE` (saturation, bloom, transient, bad pixels, artifacts).
  The amplitude is the total flux, so no aperture correction is needed. Errors are scaled by
  √(reduced χ²). The position comes from the same fit. `FrameMeasurement.flux_method` =
  `aperture` | `forced` | `psf_wings`, plus `psf_fit_rchi2` (proposed fields).
- Only for masked cores. On saturated-but-unmasked frames the wing fit scattered more than the
  aperture (Barnard's: 17–50% vs aperture χ² 0.1–0.3), because the SPHEREx ePSF does not match
  bright wings well (reduced χ² of the fit ~50–800).
- Variability's saturated fallback now accepts masked-core samples whose flux came from the wing
  fit. Live at the 10% floor: Barnard's (constant) D1 0.5, D5 0.1, D6 1.9 → none flagged;
  RW Aur still flagged (D1 clean, D5 8.6, D6 12.1).
- Barnard's fixtures: aperture 4.24 / 2.54 Jy → wing fit 4.14 / 4.06 Jy at 0.75 µm (D1, a year
  apart), 3.92 Jy at 4.87 µm (≈ WISE W2 4.3 Jy).
- **R Dra stays unmeasurable — a data limit, not a bug.** Its flagged saturation region reaches
  ~6 px, but the SPHEREx ePSF stamp is only ±3.3 native px, so **zero usable pixels fall inside
  the model** (median 0 within 4 px over 98 frames). Measuring it needs an extended PSF-wing
  model, which IRSA does not provide. The variability note now says "masked (NaN) saturated
  core and the ePSF wing fit failed".
