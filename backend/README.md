# SPHEREx backend

For setup on another computer, see [QUICKSTART.md](QUICKSTART.md). Run
`setup.cmd` once, keep settings in the private `.env` file, and use `run.cmd`
thereafter. The launcher loads `.env` automatically; no repeated environment
commands are needed.

## Community findings and identified markers

Explore can submit suspected motion to a shared discussion through `/explore/findings`.
Posts preserve the selected region, original view, bands, observation IDs, and
any recorded motion track. `/findings/{id}` in the frontend is the shareable post
page, with comments saved through the backend. Links are accessible to people who
can reach the same running frontend/backend; localhost links are local to this machine.

The database is `backend/.data/community.sqlite3` (not committed). Back up that
directory to retain posts. Set `PULSR_COMMUNITY_DB` to use another SQLite path.
These threads are shared server data, unlike the fictional sample feed discussions
which remain separate. Posts and comments use the active account returned by
`/explore/session`; client-supplied author names are rejected. The existing app
currently uses Alex Rivera as a demo account, not an authenticated login session.

Before composition, the app looks for an existing regional thread. The server
also checks inside an atomic transaction when submitting: overlapping boxes with
centres within 60 arcseconds share a thread, and crops within one native pixel
(6.15 arcseconds) are treated as the same region. This also handles RA wraparound.
The existing post is returned instead of inserting a duplicate. Suspected motion
requires at least two distinct observation IDs and stays labelled unconfirmed.

Completed catalog verifications persist markers via `/explore/markers`.
Cyan markers indicate matches; dashed markers identify a match within the selected
box when the verifier did not return an exact catalog position. Markers tied to a
particular epoch are shown only at that epoch. Orange discussion markers open the
existing finding. This is not a full catalog overlay: known-object markers appear
after a verification returns a match.

Wavelength windows with available observations can always be selected. A window
which cannot combine with the current selection replaces it and resets the time
range, while the final active window cannot be switched off.

Discussion pins open a preview card before navigating. Saved posts attach the
best available cached SPHEREx frame, with the submitted selection outlined,
plus its detector, wavelength, date, field size, and an evidence-based summary.
When enough cached frames are available, posts also include a date-labelled GIF
blink on a common sky grid and a brightness-versus-wavelength plot calculated
from usable pixels in the selected region. Blink frames can differ in wavelength;
the per-frame label preserves that context. Plot samples are regional averages
above the frame background, not whole-object integrated fluxes.
The image is real observational data, not generated imagery. If no cached frame
is available, the post explicitly says so instead of fabricating an image.

To populate three clearly labelled sample discussions, from `backend/` run:

```powershell
.\.venv\Scripts\python.exe -m app.explore.seed_discussions
```

This uses the prewarmed Barnard, Orion and Andromeda observations and creates two
sample comments per thread. It is repeatable and does not replace existing user
discussions in overlapping regions.
The post heading uses ordinary field-note styling; a small provenance note below
the evidence identifies the prepared demo conversation separately from real data.

Optional AI explanations use the [Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create).
Set `OPENAI_API_KEY` and `PULSR_AI_MODEL` in `backend/.env` to enable
“Explain with AI.” No credentials are committed or sent to the browser.
Only observation facts, not post bodies or account details, are sent to the model.
Model-generated text is labelled AI and never substitutes for scientific verification.
Without configuration or when the service is unavailable, the saved data summary
remains available and is not labelled AI.

Start only the backend with the newest installed exposure index and S3 downloads:

```powershell
.\run.cmd
```

Run this from `backend/`, or run `.\backend\run.cmd` from the project root.
It starts Uvicorn on port 8000 in the current terminal; Ctrl+C stops it.
Use `-IndexDir "path\to\snapshot"` to select a specific index.

## Prepare a fast-loading demo

From the project root, run:

```powershell
.\backend\warm-demo.cmd
```

This prepares the eight stationary suggested/feed regions, including Barnard's
Star, at all three supported viewer sizes. It downloads the widest cutout for
each sampled exposure, derives smaller previews locally, and renders the PNGs
for each available wavelength window. Metadata, cutouts, rendered PNGs, and
shared brightness scales persist under `backend/.cache/` across server restarts.
The widest SPHEREx view is currently about 1 degree across; larger feed fields
are still constrained by the viewer's supported sizes.

The initial preparation requires internet access and may take time and disk space.
Run it before the demo. Re-running reuses completed cache entries and retries
missing entries. Use `--target barnard` to prepare one region, or `--list` to list
the configured targets without downloading. A completion/failure report is
saved to `backend/.cache/demo-warm-report.json`.

This preloads real observations, not placeholder images. It prepares the same
sample of up to 18 observation IDs per region as the viewer, rather than the
entire archive. Moving objects require time-dependent coordinates and are not
included. Other sky surveys shown as context still load from their own servers.

## Optional static-index and S3 mode for Explore

An installed local snapshot is now detected automatically through
`backend/.cache/exposure-index/active.json`. The pinned snapshot and reproduction
steps are documented in [data/INDEX.md](../data/INDEX.md), with saved metadata
coverage for the recommended fields in [indexed-targets.json](../data/indexed-targets.json).
Restart the API after installing it. The archive importer validates all tiles
before activating a snapshot, and defaults to direct S3 access for image data.
Explicit environment settings still take precedence.

The `/explore/*` routes can discover exposures without live IRSA SIA searches.
From `backend/`, install an exposure index from a configured HTTPS snapshot:

```powershell
.\.venv\Scripts\python.exe -m app.explore.install_index --source https://your-index-host/snapshots/version/data
```

The installer prints two PowerShell environment assignments. Run both in the
terminal where you start the server, then start it normally. `SPHEREX_INDEX_DIR`
points at the completed snapshot and `SPHEREX_IMAGE_SOURCE=s3` selects direct
public-bucket downloads. Without those settings or an active installed snapshot, Explore automatically
uses the combined index committed under `data/exposure-index/`. No separate index
download is needed for a fresh clone. See `data/INDEX.md` for provenance.
When an index is configured, it takes precedence over partial bundled target data.
Without an index, saved local target data still takes precedence over live searches.

The index includes all six detectors; Explore still selects up to 18 observation
IDs spread over time. Coverage in the index is approximate and FITS WCS is the
final check. An empty configured index result does not silently query IRSA.
The source must contain `index.json` and `tiles/*.bin` in an immutable snapshot
directory. Installations are identified by a hash of the index metadata.
Run the installer periodically with a new snapshot URL to refresh metadata.
Release coverage and freshness depend on the installed snapshot. This command
installs metadata; it does not generate an all-sky index.

Explore first reads only FITS headers and the wavelength lookup table to return
accurate observation/band metadata. It does not download pixels to build the area.
The visible frame is requested first, then the timeline loads in the background.
Display cutouts retrieve only IMAGE, compressed FLAGS, and the wavelength table
using HTTP ranges; variance and background images are not fetched for display.
Cropped celestial and spectral coordinate origins are adjusted together.
Analysis requests load separate science cutouts with variance, background, and
the PSF table on demand.
Cutouts are cached under `backend/.cache/s3-cutouts`; wider zoom levels request
their own cutout once. The spatial PSF grid is not included in viewer cutouts.
Display brightness uses a fixed scale from the first displayed frame in each
band, shared by subsequent frames; it no longer scans the full timeline upfront.
Band emptiness and pixel coverage remain unknown until pixels are read.
The cache has no automatic eviction. Older whole-image cache files are no longer
used by Explore. This mode currently applies
to Explore only, not the legacy `/spherex/*` endpoints or `/inspect` pipeline.

Python 3.11+ API for the Aladin Lite → ICRS coordinates → SPHEREx time-series flow.
No NASA account or API key is required. Local mode is the default and makes no
external requests. Internet access is required only for explicit `source: "remote"` requests.

```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Interactive API docs: http://localhost:8000/docs. Tests: `python -m pytest`.
The existing Next.js proxy forwards `/api/*` to this server via `BACKEND_URL`.

## Frontend contract

When Aladin emits a sky click, send its ICRS RA/Dec **in degrees**:

```ts
const result = await api('/spherex/timelapse', {
  method: 'POST',
  json: { ra: 269.452076, dec: 4.693391, detector: 1, size_px: 48, limit: 12 },
});
```

Or call it directly:

```sh
curl http://localhost:8000/spherex/timelapse \
  -H 'Content-Type: application/json' \
  -d '{"ra":269.452076,"dec":4.693391,"detector":1,"size_px":48}'
```

- `POST /spherex/search`: observation metadata and original FITS URLs, without downloading pixels.
- `POST /spherex/timelapse`: metadata plus north-up, east-left PNG data URLs on a common tangent-plane grid. Play `frames[].image_png` in order, blink any two frames, show `frames[].difference_png`, or display `median_png`.
- `GET /health`: process liveness; does not check IRSA.
- `GET /spherex/targets`: cached target coordinates, metadata counts, and downloaded frame counts.
- `GET /spherex/targets/{id}/cutouts/{filename}`: downloaded FITS file.

## Explore page API

`/explore/*` serves the Explore page (area, frames, inspect, motion, verify, search) from the saved cache. See `frontend/docs/explore-backend-integration.md` and `app/explore/router.py`.

## Bundled local data

The project-root `data/` folder contains 384 saved exposure metadata records
across eight targets. No bundled FITS images are shipped.

Omit `source` or use `"source": "local"` to search this cache. Local time-lapse
requests select downloaded frames **before** applying `limit`; missing downloads
are skipped with a warning and never fetched remotely. Use indexed Explore for
image retrieval; local mode provides metadata only unless you add cutouts yourself.

Local metadata lookup matches saved target coordinates within one arcsecond.
Downloaded cutouts also support nearby map clicks when their actual FITS WCS
footprints contain the position. It is not an all-sky index. Cached cone-search rows are exposure candidates, not
guaranteed footprint matches. Actual FITS coverage is checked when rendering.
Other targets have metadata but no images yet. These requests return
`status: "no_local_frames"` and warnings. Use `/spherex/targets` to discover
supported target coordinates. To query arbitrary sky positions live, explicitly
send `"source": "remote"`; there is no automatic network fallback.

Search accepts `ra` [0,360), `dec` [-90,90], `detector` 1–6, `collections`,
`mjd_start`, `mjd_end`, `source` (`local` or `remote`), and `limit` 1–24.
Defaults filter wide-survey DR1 and QR3.
Add `spherex_dr1_deep` / `spherex_qr3_deep` to include deep-field visits.
Timelapse also accepts `size_px` 16–256, `pixel_scale_arcsec` 6.15–12.3,
`subtract_background` (default true), and a `bad_bits` bit mask.

Frames are sorted by MJD and limited to the earliest requested observations.
`truncated` means more exposures exist or the archive's 10,000-row search cap was reached.
Narrow the date interval to explore later epochs or resolve archive overflow.
Exposures shared by multiple queried collections are deduplicated by observation ID and detector.

Response fields include `source`, `status` (`ready`, `partial`, `no_coverage`, `no_local_frames`), `frames`,
`median_png`, `stretch`, `failures`, `warnings`, and the underlying FITS WCS header.
No coverage returns HTTP 200 with empty frames. Upstream errors return 502;
invalid requests return 422. Individual frame failures produce `partial` results;
if all selected frames fail, the request returns 502. PNGs have transparent missing pixels.
The WCS describes numerical arrays with increasing y pointing north; PNG rows are flipped
for display. Each frame retains source and cutout FITS URLs for scientific use.

## Processing and limits

Remote search uses IRSA SIA2, then requests native cutouts from IRSA IBE. Local mode
reads saved JSON metadata and FITS files. Astropy handles
celestial WCS and SIP distortion. Bilinear interpolation places images on a common
grid (default 6.15 arcsec/pixel); flagged pixels are excluded before interpolation.
The conservative default rejects every flag except SOURCE (bit 21), which
identifies pixels mapped to a known source. This follows the
[IRSA flag definitions](https://irsa.ipac.caltech.edu/onlinehelp/spherex/spherex/sp.html).
Choose a scientifically appropriate mask for your analysis.

The background option subtracts each frame's median, not a physical zodiacal-light
model. All frames share a 1–99.5 percentile asinh stretch. Differences are each
frame minus the per-pixel median stack, with a shared symmetric linear scale.
Detector selection is not monochromatic wavelength selection: SPHEREx wavelength
varies across each detector. These are visualization products, not calibrated
photometry, spectra, moving-object tracking, or flux-conserving science mosaics.

This initial service runs requests synchronously, with two concurrent jobs and
four cutout downloads per process, bounded response sizes, and upstream timeouts.
It has no persistent cache or job queue. Start with small batches; long requests
may need a larger reverse-proxy timeout. A public deployment should add rate limits,
job storage, and caching. CORS is unnecessary through the existing Next.js proxy.

## Sources

- [IRSA SPHEREx access documentation](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-access/)
- [IRSA cutout parameters](https://irsa.ipac.caltech.edu/ibe/cutouts.html)

Uses current DR1/QR3 collections: QR2 is no longer searchable according to IRSA's
November 2026 documentation.
Data credit: NASA/JPL-Caltech and NASA/IPAC Infrared Science Archive (IRSA).
