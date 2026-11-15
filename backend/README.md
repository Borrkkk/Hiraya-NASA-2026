# SPHEREx backend

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

The project-root `data/` folder is a copy of the sibling project's saved cache:
384 exposure records across eight targets, plus two detector-1 FITS cutouts for
Barnard's Star. The original sibling project is not needed at runtime.

Omit `source` or use `"source": "local"` to search this cache. Local time-lapse
requests select downloaded frames **before** applying `limit`; missing downloads
are skipped with a warning and never fetched remotely. Barnard's Star renders
two actual images, a median stack, and differences completely offline. The saved
cutouts are about 0.1 degrees wide; use `size_px: 48` at the default scale to
reduce transparent borders. Larger requested grids retain transparent missing pixels.

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

- [Reference visualization](https://github.com/ShivenKhurana1/spherex-timelapse)
- [IRSA SPHEREx access documentation](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-access/)
- [IRSA cutout parameters](https://irsa.ipac.caltech.edu/ibe/cutouts.html)

Uses current DR1/QR3 collections: QR2 is no longer searchable according to IRSA's
November 2026 documentation. Implementation is original Python; no reference-repository code is vendored.
Data credit: NASA/JPL-Caltech and NASA/IPAC Infrared Science Archive (IRSA).
