"""Shared pieces for the Explore API: area ids, the frame grid, band windows,
and cached access to the saved SPHEREx cutouts.

Everything here reads the local cache (data/). Nothing contacts the network.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
import warnings

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS

from ..imaging import align, target_wcs
from ..local_store import local_path, search_local
from ..models import Exposure, TimelapseRequest

# Frames come in three sizes, so the picture can follow the zoom. Native SPHEREx
# pixels are 6.15"; the widest level is coarser. `cutout_deg` is how much sky
# we ask IRSA for, a bit more than the tile so its edges are filled.
LEVELS = [
    {"level": 0, "sizePx": 128, "pixelScaleArcsec": 6.15, "cutout_deg": 0.35},
    {"level": 1, "sizePx": 256, "pixelScaleArcsec": 6.15, "cutout_deg": 0.55},
    {"level": 2, "sizePx": 256, "pixelScaleArcsec": 14.0, "cutout_deg": 1.25},
]
for _l in LEVELS:
    _l["extentDeg"] = _l["sizePx"] * _l["pixelScaleArcsec"] / 3600
SIZE_PX = LEVELS[0]["sizePx"]            # level 0, used by the analysis code
PIXEL_SCALE = LEVELS[0]["pixelScaleArcsec"]
EXTENT_DEG = LEVELS[0]["extentDeg"]
DETECTORS = range(1, 7)

# SPHEREx wavelength windows (micrometres) for the page's "things to look for".
# Line rows get +-4% around the line; the two broad rows use fixed ranges.
# Approximate: to be validated by the science team (spec).
def _line(*centres: float):
    return [(c * 0.96, c * 1.04) for c in centres]

BAND_WINDOWS: dict[str, list[tuple[float, float]]] = {
    "starlight": [(0.75, 1.30)],
    "hydrogen": _line(1.28, 1.88, 4.05),
    "helium": _line(1.08),
    "water-ice": _line(3.0),
    "co2-ice": _line(4.27),
    "co-ice": _line(4.67),
    "organic-dust": _line(3.3),
    "methane": _line(1.7, 3.3),
    "warm-glow": [(3.8, 5.0)],
}
BAND_LABELS = {
    "starlight": "1 µm", "hydrogen": "1.28, 1.88 or 4.05 µm", "helium": "1.08 µm",
    "water-ice": "3.0 µm", "co2-ice": "4.27 µm", "co-ice": "4.67 µm",
    "organic-dust": "3.3 µm", "methane": "1.7 or 3.3 µm", "warm-glow": "4 to 5 µm",
}


def in_band(band: str, wavelength: float) -> bool:
    return any(lo <= wavelength <= hi for lo, hi in BAND_WINDOWS[band])


def area_id(ra: float, dec: float) -> str:
    return f"{key(ra, dec)[0]:.5f}_{key(ra, dec)[1]:.5f}"


def parse_area_id(value: str) -> tuple[float, float]:
    try:
        ra, dec = value.split("_")
        return float(ra), float(dec)
    except ValueError as exc:
        raise KeyError(f"Unknown area {value}") from exc


def grid_request(ra: float, dec: float, level: int = 0):
    """What `align` and `target_wcs` need for a level's grid (duck-typed: no validation limits)."""
    from types import SimpleNamespace
    l = LEVELS[level]
    return SimpleNamespace(ra=ra % 360, dec=dec, size_px=l["sizePx"], pixel_scale_arcsec=l["pixelScaleArcsec"],
                           bad_bits=0xFFFFFFFF ^ (1 << 21), subtract_background=True)


def request_for(ra: float, dec: float, detector: int) -> TimelapseRequest:
    return TimelapseRequest(ra=ra % 360, dec=dec, detector=detector, limit=24,
                            size_px=SIZE_PX, pixel_scale_arcsec=PIXEL_SCALE)


def mjd_to_iso(mjd: float) -> str:
    return (datetime(1858, 11, 17, tzinfo=timezone.utc) + timedelta(days=mjd)).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class Shot:
    """One saved exposure that covers the area: when, which detector, where on disk."""
    epoch_id: str
    detector: int
    mjd: float
    path: Path
    wavelength: float  # micrometres at the area centre
    fits_url: str = ""  # the archive's file, to ask for bigger cutouts later


@lru_cache(maxsize=32)
def _read_wavelength(path: str, ra: float, dec: float) -> float:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with fits.open(path, memmap=False) as hdus:
            image = hdus["IMAGE"]
            x, y = WCS(image.header, hdus, naxis=2).celestial.all_world2pix(ra, dec, 0)
            wave, _ = WCS(image.header, hdus, key="W").all_pix2world([x], [y], 0)
    return float(wave[0])


# Shots per position, filled by sources.ensure_shots (the saved cache first, then IRSA live).
SHOTS: dict[tuple[float, float], tuple[Shot, ...]] = {}


def key(ra: float, dec: float) -> tuple[float, float]:
    return round(ra % 360, 5), round(dec, 5)


def shots_at(ra: float, dec: float) -> tuple[Shot, ...]:
    """Exposures covering this position, oldest first. Call sources.ensure_shots first."""
    return SHOTS.get(key(ra, dec), ())


def local_shots(ra: float, dec: float) -> tuple[Shot, ...]:
    """Saved exposures covering this position, oldest first."""
    shots: dict[tuple[str, int], Shot] = {}
    for detector in DETECTORS:
        found = search_local(request_for(ra, dec, detector), True)
        for e in found.exposures:
            path = local_path(e)
            if path is None:
                continue
            try:
                wavelength = _read_wavelength(str(path), ra, dec)
            except (OSError, KeyError, ValueError):
                continue
            if not np.isfinite(wavelength):
                continue
            shots[(e.id, e.detector)] = Shot(e.id, e.detector, e.mjd, path, wavelength, e.fits_url)
    return tuple(sorted(shots.values(), key=lambda s: (s.mjd, s.detector)))


def epochs_at(ra: float, dec: float) -> list[tuple[str, float]]:
    """(epoch id, mjd) for each exposure, oldest first. One exposure is one epoch."""
    seen: dict[str, float] = {}
    for s in shots_at(ra, dec):
        seen.setdefault(s.epoch_id, s.mjd)
    return sorted(seen.items(), key=lambda kv: kv[1])


def shot_for(ra: float, dec: float, epoch_id: str, band: str) -> Shot | None:
    for s in shots_at(ra, dec):
        if s.epoch_id == epoch_id and in_band(band, s.wavelength):
            return s
    return None


@lru_cache(maxsize=160)
def aligned(path: str, ra: float, dec: float, level: int = 0) -> np.ndarray:
    """The exposure on a level's grid: background removed, NaN where there is no data."""
    return align(Path(path).read_bytes(), grid_request(ra, dec, level))


def grid_wcs(ra: float, dec: float, level: int = 0):
    return target_wcs(grid_request(ra, dec, level))
