# Bundled SPHEREx exposure index

`data/exposure-index/index.json` and `tiles/*.bin` contain the actual combined
index, included in Git. A fresh clone can query it immediately, without rebuilding
or downloading an index. `sha256.json` lists file checksums.

- 1,290,044 detector-exposure records in 1,738 tiles (about 31 MB).
- Base: ShivenKhurana1/spherex-timelapse at commit
  `cca8e6dc69a07632f4cee4b85330237ed7fa212f` (QR2 and QR3).
- Recommended fields: 6,893 NASA FITS headers read, including 4,721 DR1 headers.
  Physical observation/detector duplicates are merged, preferring DR1 processing.
- Combined snapshot: `55178b4ab02d7c2f529b32cfc9637a58111083372575abb901149dbefdcfb570`.
- Provenance and per-field refresh counts: `exposure-index/source.json`.

Explore resolves the index in this order: explicit `SPHEREX_INDEX_DIR`, a local
active snapshot in `backend/.cache/exposure-index/active.json`, then this bundled
index. Direct NASA S3 image access is the default when an index is available.
The `/inspect` endpoint retains its own discovery behavior.

These records locate candidate exposures. FITS WCS remains the final coverage
check. Full FITS images, local caches, and the community discussion database are
not included with this index. Images download as needed.

To reproduce the upstream import, use `backend.app.explore.import_index_archive`.
To refresh and merge recommended fields, use `backend.app.explore.combine_index`.
Those commands write local snapshots; publishing an updated bundled index requires
copying the chosen snapshot's metadata and tiles here and regenerating checksums.

Data credit: NASA/JPL-Caltech and NASA/IPAC IRSA. Original index preparation:
https://github.com/ShivenKhurana1/spherex-timelapse . No executable upstream
application code is vendored.
