# Explore page and its backend

The Explore page talks to the unified Python API (`api.app:app`), reusing the
renderer in `backend/app/explore/` and the analysis in `spherex_inspect/`. The
contract is `frontend/src/lib/explore/types.ts`; the only file that knows URLs is
`frontend/src/lib/explore/http-client.ts`. A mock (`lib/explore/mock/`) stays
for demos with invented data: set `NEXT_PUBLIC_EXPLORE_API=mock`.

## Running it

```sh
# From the repository root, in one terminal:
source backend/.venv/bin/activate
pip install -e '.[dev]'
uvicorn api.app:app --port 8000
# In a separate terminal, from the repository root:
cd frontend
pnpm dev          # /api/* is proxied to BACKEND_URL (default localhost:8000)
```

Open `/explore?q=Barnard%27s%20Star&ra=269.452076&dec=4.693391&fov=0.25`.
`cd backend && python -m pytest` runs the tests (`tests/test_explore.py`).

## Endpoints

| | Path | Notes |
| --- | --- | --- |
| GET | `/explore/area?ra&dec&fov` | Area, epochs, per-band coverage, sensor layers. 404 `{detail:{message,suggestion}}` when SPHEREx hasn't observed the spot; 502 if IRSA is unreachable. |
| GET | `/explore/areas/{id}/frames/{epoch}/{band}?level=0..2` | Greyscale PNG, north up, east left, transparent where there is no data. Level 0 is 0.22 degrees, 1 is 0.44, 2 is 1.0 (`Area.levels`). The page asks for the smallest level that covers the zoom and draws the nearest loaded one meanwhile. |
| POST | `/explore/areas/{id}/inspect` | Morphology-based guess, point-source spectrum in Jy, quality evidence, and full `science` response. No invented confidence percentages. |
| POST | `/explore/areas/{id}/motion` | `{jobId}`. Screens for motion candidates from 3+ comparable exposures (same detector and near-matching wavelength), requires a time baseline, consistent linear shift and conservative pixel-space significance. Not calibrated astrometric confirmation. |
| POST | `/explore/areas/{id}/verify` | `{jobId}`. `spherex_inspect` measurements and epoch-aware catalog matching. Inconclusive / unavailable checks remain unexplained. |
| GET | `/explore/jobs/{id}` | `{status, step?, result?, message?}`; `step` is shown to the user. |
| GET | `/explore/search?q=` | Saved SPHEREx targets (images first), plus SIMBAD names when online. Used by the home search. |

## What is real

- **Epochs**: each exposure is an epoch (id = observation id, date from MJD).
- **Bands**: the page's nine rows are wavelength windows (`BAND_WINDOWS` in
  `explore/common.py`). A row has data only if a saved exposure's wavelength at
  that spot falls in its window. The wavelength comes from each FITS file's
  `WCS-WAVE` table. Barnard's Star has two exposures at 0.757 and 0.7745 micrometres,
  so only Starlight is enabled; the rest are disabled with a reason that lists
  the wavelengths we do have. Live spots get up to 10 observations and more rows.
- **Spectrum**: clean point-source measurements near the box centre, from
  `spherex_inspect`, in Jy with uncertainties in the response. Flagged samples
  are excluded from the chart and retained in `science.summary.spectrum_flagged`.
  A spot with two usable exposures has a
  two-point spectrum, and the chart shows the full 0.75 to 5 micrometre range so the
  gaps are visible. Feature labels are empty until there are enough wavelengths.
- **Motion**: real source detection and tracking on the aligned frames. Two exposures
  two minutes apart correctly find nothing.
- **Artifact check**: share of the box with valid data (the pipeline flags and the
  frame edge both mask pixels).

## What is a rule or a placeholder

- The type guess is rule-based on computed facts (signal to noise, compactness,
  valid fraction, mover speed). Thresholds are placeholders: top of `analysis.py`.
- Point-source measurement quality and catalog matching come from `spherex_inspect`;
  they do not turn a morphology guess into a calibrated classification.
- Speed wording thresholds ("What this suggests") are placeholders: `motion-language.ts`.
- Band windows and wavelengths need science-team validation.
- Points table: `points.ts`.

## Frames follow the zoom, bands follow the observations

- The page is the SPHEREx image: black where there is no data, with the Aladin sky only as
  the loading placeholder and the curtain's other sensor. The widest frame is about 1 degree,
  which is also the widest zoom.
- Bigger levels need bigger cutouts (up to about 12 MB each), downloaded on first use and cached.
- Observations (timeline points) are those that have **every** band that is on. A band that is
  never seen in the same observation as the bands already on is disabled, with the reason.
- The page opens on the observation with the most data (`Epoch.coverage`).
- Observations are spread over the survey, not the earliest ones, because each exposure only sees
  a few wavelengths: for Orion this takes the page from 2 usable bands to all 9.

## Where the data comes from

For any position the backend first looks in the saved cache (`data/`, Barnard's
Star only), and otherwise fetches **live from NASA/IPAC (IRSA)**
(`backend/app/explore/sources.py`): one SIA search per collection, 18 observations spread over time, and a small native cutout per detector. Cutouts are cached in
`backend/.cache/cutouts/`, so the first visit to a spot takes about 10 to 40 seconds
and every later one is instant. Needs internet (IRSA); TLS uses the system trust
store (`truststore`), because some Python installs reject IRSA's certificate.

Each SPHEREx exposure sees a spot at one wavelength per detector, so an observation
only has images for some of the page's band rows. `Epoch.bands` lists them, the page
opens on the latest observation that has data for the bands that are on, skips empty
ones when playing, and marks them on the timeline.

## Known limits

- Live catalog behavior has not been validated by the offline integration tests.
  When a catalog is unavailable, Verify reports incomplete checks instead of a confirmed match.
- Saturated regions (the Orion core) are masked by the SPHEREx pipeline, so the tile has
  holes there. The unified API reports missing or flagged measurements; absence of
  a reliable detection alone does not establish an artifact.
- The tile is 0.22 degrees wide (128 px at 6.15"/px); the page lets you zoom out to
  1.5 degrees, where it sits on the Aladin sky around it (`minFovDeg` / `maxFovDeg`).
- Barnard's Star has moved about 265 arcseconds since J2000, which is what the saved cutouts
  are centred on, so the star is outside them. Source-centred inspection is needed
  to measure the star. The science pipeline compares measured positions with catalog
  positions propagated to the observation epoch. Live areas are centred where you ask.
- The first load of a new spot is slow; there is no job queue yet (the area call just waits).
- Fixed along the way: `archive.parse_results` read IRSA's table by column ID, which IRSA
  does not set, so every live search failed. It now reads by name.

## Share this find

Entry point only: the draft is stored in `sessionStorage` (`lib/explore/share.ts`)
and the page goes to a placeholder `/share`.

## Motion candidate safety

- Three or more detections at distinct times are required. The current detector uses
  a 0.75-pixel assumed centroid-error floor, a >=3.5-pixel fitted displacement,
  a >=4-sigma *screening* threshold and <=1-pixel maximum fit residual. These
  are conservative engineering filters, not calibrated scientific uncertainties.
- Frames must come from the same detector and within 0.025 micrometres of an
  anchor wavelength. Not enough comparable observations means no candidate.
- Tracks are still not independently confirmed by sky ephemerides. Inspect/Verify
  checks the selected point; it explicitly withholds motion-track verification.
- Animated markers between recorded dates show **interpolation**, not additional
  observations. Do not call candidates discoveries.
- Robust field-wide astrometry, crowded-field matching, uncertainty propagation,
  ephemeris-based validation and per-target cross-epoch source association remain
  future scientific work.

## Diagnosing zero real motion candidates

When the motion job finishes, the response includes `result.diagnostics`:
`comparableObservations`, `requiredObservations`, `detectedSources`,
`reason`. The UI distinguishes:

- `insufficient_comparable_observations`: fewer than 3 images from a matching
  detector and wavelength. A long timeline does **not** guarantee these exist.
- `no_sources_detected`: matching images exist, but no bright enough sources
  were detected to follow.
- `no_consistent_tracks`: sources were detected, but no track passed motion
  consistency tests. This is a legitimate outcome, not a backend failure.
- `candidates_found`: one or more screening candidates; not scientifically
  verified trajectories.

The job endpoint returns HTTP 200 for both running and completed jobs.
Check the **JSON** of `GET /explore/jobs/{jobId}` for `status` and `result`;
HTTP 200 alone does not mean motion was found. The frame endpoint may
independently fail when requesting a larger cutout from the archive; a failed
zoom-level frame is not a motion finding.


## Exploring different sky locations

The Explore page separates the location of the **loaded SPHEREx data**
(`ra`, `dec`, `fov`) from the **current camera view**
(`viewRa`, `viewDec`, `viewFov` in the URL).

- Navigating to another known target resets the Explore controller and loads
  that target's own area. Previously, URL coordinates were read only on first
  mount, so client-side navigation could leave the old area loaded.
- Panning/zooming within a loaded area does not instantly download a new
  sky region. After panning far enough, **Load this sky area** appears in the
  header; select it to request SPHEREx observations at the new centre.
- Copy Link preserves camera coordinates separately from data coordinates.
- Plain `/explore` intentionally starts at Orion, but a free-text search
  without resolved RA/Dec is no longer offered as a target. Old links that
  contain a name without coordinates explicitly say they display default Orion.
- After choosing a new target, the browser Network tab should show
  `GET /explore/area?ra=<new RA>&dec=<new Dec>`, and the heading should show
  the new sky position. If not, the target did not change.

Backend cutouts only cover a small field around their requested centre. Moving
a view without requesting another area cannot produce new SPHEREx imagery.
