"""Read the bundled, curated cache without contacting IRSA."""
import json
from pathlib import Path
from urllib.parse import quote

import numpy as np
from astropy.coordinates import SkyCoord
from astropy import units as u
from astropy.io import fits
from astropy.wcs import WCS, NoConvergence

from .models import Exposure, SearchResult

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def target_records():
    return [json.loads(p.read_text()) for p in sorted((DATA_DIR / "targets").glob("*/exposures.json"))]


def cutout_path(target_id: str, filename: str) -> Path | None:
    if Path(target_id).name != target_id or Path(filename).name != filename:
        return None
    root = (DATA_DIR / "targets").resolve()
    path = (root / target_id / "cutouts" / filename).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        return None
    return path


def local_path(exposure: Exposure) -> Path | None:
    if not exposure.local_cutout_url:
        return None
    parts = exposure.local_cutout_url.split("/")
    from urllib.parse import unquote
    return cutout_path(unquote(parts[-3]), unquote(parts[-1]))


def list_targets():
    targets = []
    for record in target_records():
        target = record["target"]
        local_count = sum(bool(row.get("local_cutout")) and
                          cutout_path(target["id"], Path(row["local_cutout"]).name) is not None
                          for row in record["exposures"])
        targets.append({**target, "exposure_count": len(record["exposures"]),
                        "local_frame_count": local_count, "pulled_at": record.get("pulled_at")})
    return targets


def covers_position(path, request):
    """Only reuse a downloaded cutout where its actual WCS covers the click."""
    if path is None:
        return False
    try:
        with fits.open(path, memmap=False) as hdus:
            image = hdus['IMAGE']
            x, y = WCS(image.header, hdus, naxis=2).celestial.all_world2pix(request.ra, request.dec, 0)
            return bool(np.isfinite(x) and np.isfinite(y) and
                        0 <= x <= image.header['NAXIS1'] - 1 and
                        0 <= y <= image.header['NAXIS2'] - 1)
    except (OSError, ValueError, KeyError, NoConvergence):
        return False


def search_local(request, images_only=False):
    # Metadata candidates can only be reused at the saved target. Downloaded
    # images can also answer nearby clicks after checking their actual footprints.
    position = SkyCoord(request.ra * u.deg, request.dec * u.deg)
    records = target_records()
    matches = []
    for record in records:
        separation = position.separation(SkyCoord(
            record['target']['ra'] * u.deg, record['target']['dec'] * u.deg))
        at_target = separation.arcsec <= 1
        # Native cutouts are tiny. Avoid inverting SIP far outside the field,
        # where the polynomial can diverge rather than report an off-image pixel.
        if separation.deg > float(record.get('search', {}).get('cutout_size_deg', 0.1)):
            continue
        candidates = []
        for row in record['exposures']:
            filename = Path(row['local_cutout']).name if row.get('local_cutout') else None
            path = cutout_path(record['target']['id'], filename) if filename else None
            if at_target or covers_position(path, request):
                candidates.append(row)
        if candidates:
            matches.append({**record, 'exposures': candidates})
    warnings = ["Local cache is a saved subset of exposure candidates, not a complete sky search."]
    if not matches:
        return SearchResult(exposures=[], truncated=False, source="local", warnings=[
            "No cached target at these coordinates. Use /spherex/targets or explicitly set source=remote."])
    unique = {}
    skipped = 0
    for record in matches:
        target_id = record["target"]["id"]
        for row in record["exposures"]:
            if row["detector"] != request.detector or row["collection"] not in request.collections:
                continue
            mjd = float(row["mjd_start"])
            if not np.isfinite(mjd):
                continue
            if request.mjd_start is not None and mjd < request.mjd_start:
                continue
            if request.mjd_end is not None and mjd > request.mjd_end:
                continue
            filename = Path(row["local_cutout"]).name if row.get("local_cutout") else None
            path = cutout_path(target_id, filename) if filename else None
            if images_only and path is None:
                skipped += 1
                continue
            exposure = Exposure(id=row["obs_id"], detector=row["detector"], collection=row["collection"],
                                mjd=mjd, fits_url=row["access_url"],
                                local_cutout_url=f"/spherex/targets/{quote(target_id)}/cutouts/{quote(filename)}" if path else None)
            key = (exposure.id, exposure.detector)
            if key not in unique or exposure.local_cutout_url:
                unique[key] = exposure
    if skipped:
        warnings.append(f"{skipped} matching metadata records have no downloaded FITS cutout; skipped without network access.")
    rows = sorted(unique.values(), key=lambda row: (row.mjd, row.id))
    return SearchResult(exposures=rows[:request.limit], truncated=len(rows) > request.limit,
                        warnings=warnings, source="local")
