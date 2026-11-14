# Saved SPHEREx demo data

Copied from the sibling `NASA/Hiraya-NASA-2026/data` project, preserving its JSON
metadata and two downloaded FITS cutouts. Exposure caches were pulled on November
14, 2026; each file records its own `pulled_at`, coordinates, and source URLs.

Eight cached target fields contain 48 exposure records each (384 total).
Only Barnard's Star currently has downloaded image data: two detector-1 cutouts.
`targets.json` also lists curated targets that have not been cached.

The backend reads this directory directly; no path to the original project is
required. See `backend/README.md` for local API examples and coverage limitations.

Data credit: NASA/JPL-Caltech and NASA/IPAC Infrared Science Archive (IRSA).
