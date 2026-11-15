"""[1] Intake: validate and normalise a request into a Target.

Knows nothing about IRSA or catalogs.
"""
from __future__ import annotations

import re

import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.time import Time

from . import config
from .models import InspectRequest, SkyPosition, Target, TimeRange


class IntakeError(ValueError):
    """Raised for invalid user input (maps to HTTP 422)."""


_NUMERIC = re.compile(r"^\s*[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?\s*$")


def _is_numeric(v: float | str) -> bool:
    return isinstance(v, (int, float)) or bool(_NUMERIC.match(str(v)))


def parse_coord(ra: float | str, dec: float | str) -> SkyPosition:
    """Degrees (numbers or numeric strings) or sexagesimal strings → ICRS deg.

    Sexagesimal RA is read as hours (``08h55m10.8s`` or ``08:55:10.8``),
    sexagesimal Dec as degrees.
    """
    try:
        if _is_numeric(ra) and _is_numeric(dec):
            c = SkyCoord(float(ra) * u.deg, float(dec) * u.deg, frame="icrs")
        else:
            ra_unit = u.deg if _is_numeric(ra) else u.hourangle
            c = SkyCoord(str(ra), str(dec), unit=(ra_unit, u.deg), frame="icrs")
    except Exception as exc:  # astropy raises a variety of types
        raise IntakeError(f"could not parse coordinates ra={ra!r} dec={dec!r}: {exc}") from exc
    ra_deg, dec_deg = float(c.ra.deg), float(c.dec.deg)
    if not -90.0 <= dec_deg <= 90.0:
        raise IntakeError(f"dec out of range: {dec_deg}")
    return SkyPosition(ra=ra_deg % 360.0, dec=dec_deg)


def parse_time(v: float | str | None) -> float | None:
    """MJD float/numeric string, or any ISO/ISOT string → MJD."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if _is_numeric(v):
        return float(v)
    try:
        return float(Time(str(v).strip()).mjd)
    except Exception as exc:
        raise IntakeError(f"could not parse time {v!r}: {exc}") from exc


def parse_bands(bands: list[int] | None) -> list[int]:
    if not bands:
        return list(config.ALL_BANDS)
    out = sorted({int(b) for b in bands})
    bad = [b for b in out if b not in config.ALL_BANDS]
    if bad:
        raise IntakeError(f"bands must be in 1..6, got {bad}")
    return out


def to_target(req: InspectRequest) -> Target:
    coord = parse_coord(req.ra, req.dec)

    start, end = parse_time(req.time_start), parse_time(req.time_end)
    if start is not None and end is not None and start > end:
        raise IntakeError(f"time_start ({start}) is after time_end ({end})")

    size = config.DEFAULT_CUTOUT_SIZE_DEG if req.cutout_size_deg is None else float(req.cutout_size_deg)
    if not config.MIN_CUTOUT_SIZE_DEG <= size <= config.MAX_CUTOUT_SIZE_DEG:
        raise IntakeError(
            f"cutout_size_deg must be within "
            f"{config.MIN_CUTOUT_SIZE_DEG}..{config.MAX_CUTOUT_SIZE_DEG}, got {size}"
        )

    max_frames = config.DEFAULT_MAX_FRAMES if req.max_frames is None else int(req.max_frames)
    if not 1 <= max_frames <= config.HARD_MAX_FRAMES:
        raise IntakeError(f"max_frames must be within 1..{config.HARD_MAX_FRAMES}, got {max_frames}")

    return Target(
        coord=coord,
        time_range=TimeRange(start=start, end=end),
        bands=parse_bands(req.bands),
        cutout_size_deg=size,
        max_frames=max_frames,
        include_context=req.include_context,
    )
