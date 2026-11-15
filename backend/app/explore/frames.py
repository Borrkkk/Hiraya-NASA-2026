"""The Area description and the per-band frame images."""
from functools import lru_cache
from io import BytesIO

import numpy as np
from astropy import units as u
from astropy.coordinates import SkyCoord
from PIL import Image

from ..local_store import list_targets
from .common import (BAND_LABELS, BAND_WINDOWS, EXTENT_DEG, LEVELS, PIXEL_SCALE, SIZE_PX, aligned, area_id,
                     epochs_at, has_usable_pixels, in_band, mjd_to_iso, shot_for, shots_at)

IRSA = "https://irsa.ipac.caltech.edu/data/hips/CDS"


def _layers():
    def layer(id, name, blurb, path):
        return {"id": id, "name": name, "blurb": blurb, "hips": f"{IRSA}/{path}",
                "thumbnail": f"{IRSA}/{path}/Norder0/Dir0/Npix7.jpg", "coverage": {"ok": True}}
    return [
        layer("wise", "WISE", "Mid-infrared heat from dust and cool stars, the closest cousin to SPHEREx.", "AllWISE/RGB-W4-W2-W1"),
        layer("2mass", "2MASS", "Near-infrared starlight, good for seeing through thin dust.", "2MASS/Color"),
        layer("dss2", "Visible light", "What a camera would see, the digitised sky survey.", "DSS2/color"),
        layer("iris", "IRAS dust", "Far-infrared glow of cold dust across the whole sky, blurry but wide.", "IRIS/color"),
    ]


def nearest_target(ra: float, dec: float, within_deg: float = 0.05):
    here = SkyCoord(ra * u.deg, dec * u.deg)
    best = None
    for t in list_targets():
        d = here.separation(SkyCoord(t["ra"] * u.deg, t["dec"] * u.deg)).deg
        if d <= within_deg and (best is None or d < best[0]):
            best = (d, t)
    return best[1] if best else None


def sample_suggestion():
    """Somewhere that does have images, to offer when a spot has none."""
    for t in list_targets():
        if t["local_frame_count"] > 0:
            return {"name": t["name"], "ra": t["ra"], "dec": t["dec"], "fov": 0.25}
    return None


def build_area(ra: float, dec: float):
    """None when nothing is saved for this position."""
    shots = shots_at(ra, dec)
    # Archive searches can list cutouts whose entire requested region is
    # masked. They are real exposure records but NOT usable images. Showing
    # them in the timeline (or claiming their band exists) is misleading.
    usable = [s for s in shots if has_usable_pixels(s, ra, dec)]
    if not usable:
        return None
    ids = {s.epoch_id for s in usable}
    epochs = [(e, mjd) for e, mjd in epochs_at(ra, dec) if e in ids]
    target = nearest_target(ra, dec)
    bands = []
    for band in BAND_WINDOWS:
        frames = [s for s in usable if in_band(band, s.wavelength)]
        if not frames:
            seen = ", ".join(f"{w:.1f}" for w in sorted({round(s.wavelength, 1) for s in shots}))
            bands.append({"id": band, "state": "no-coverage",
                          "reason": f"No observation at {BAND_LABELS[band]} for this spot. We have {seen} µm."})
        else:
            bands.append({"id": band, "state": "ok", "empty": _is_empty(ra, dec, band)})
    return {
        "id": area_id(ra, dec),
        "name": target["name"] if target else None,
        "center": {"ra": ra, "dec": dec},
        "extentDeg": EXTENT_DEG,
        "sizePx": SIZE_PX,
        "pixelScaleArcsec": PIXEL_SCALE,
        # `bands`: which rows have an image for this observation, so the page can skip empty ones.
        "epochs": [{"id": e, "date": mjd_to_iso(m), "bands": [
                        b for b in BAND_WINDOWS if any(s.epoch_id == e and in_band(b, s.wavelength) for s in usable)],
                    "coverage": _coverage(ra, dec, e)} for e, m in epochs],
        "bands": bands,
        # The frames are a small tile; let people zoom out to the sky around it.
        "levels": [{k: l[k] for k in ("level", "extentDeg", "sizePx", "pixelScaleArcsec")} for l in LEVELS],
        "minFovDeg": EXTENT_DEG * 0.3,
        "maxFovDeg": LEVELS[-1]["extentDeg"] * 0.98,  # the widest frame fills the view
        "layers": _layers(),
    }


def _coverage(ra: float, dec: float, epoch_id: str) -> float:
    """How much of the smallest frame has data in this observation (the best of its exposures)."""
    best = 0.0
    for s in shots_at(ra, dec):
        if s.epoch_id == epoch_id:
            a = aligned(str(s.path), ra, dec)
            best = max(best, float(np.isfinite(a).mean()))
    return round(best, 3)


def _is_empty(ra, dec, band) -> bool:
    """True if nothing stands out of the noise in any frame of this band."""
    for e, _ in epochs_at(ra, dec):
        s = shot_for(ra, dec, e, band)
        if s is None:
            continue
        a = aligned(str(s.path), ra, dec)
        finite = a[np.isfinite(a)]
        if finite.size and (np.nanmax(finite) - np.median(finite)) > 8 * max(_noise(finite), 1e-9):
            return False
    return True


def _noise(finite: np.ndarray) -> float:
    return float(1.4826 * np.median(np.abs(finite - np.median(finite))))


@lru_cache(maxsize=32)
def _stretch(ra: float, dec: float, band: str) -> tuple[float, float]:
    """One stretch per band across all its frames, so brightness compares between epochs."""
    values = []
    for e, _ in epochs_at(ra, dec):
        s = shot_for(ra, dec, e, band)
        if s is not None:
            a = aligned(str(s.path), ra, dec)
            finite = a[np.isfinite(a)]
            if finite.size:
                values.append(finite)
    if not values:
        return 0.0, 1.0
    # Background (the median, after subtraction) maps to black so stars stand out.
    low, high = np.percentile(np.concatenate(values), [50, 99.8])
    return float(low), float(max(high, low + 1e-9))


def frame_png(ra: float, dec: float, epoch_id: str, band: str, level: int = 0, path=None) -> bytes:
    """North up, east left, transparent where there is no data (see the page's contract)."""
    s = shot_for(ra, dec, epoch_id, band)
    size = LEVELS[level]["sizePx"]
    if s is None:
        return _encode(np.zeros((size, size, 4), dtype=np.uint8))
    a = aligned(str(path or s.path), ra, dec, level)
    low, high = _stretch(ra, dec, band)
    norm = np.clip((np.nan_to_num(a) - low) / (high - low), 0, 1)
    gray = 255 * np.arcsinh(10 * norm) / np.arcsinh(10)
    rgba = np.stack([gray, gray, gray, np.isfinite(a) * 255], axis=-1).astype(np.uint8)
    return _encode(np.flipud(rgba))  # array row 0 is south; image row 0 must be north


def _encode(rgba: np.ndarray) -> bytes:
    out = BytesIO()
    Image.fromarray(rgba).save(out, format="PNG")
    return out.getvalue()
