"""Where the exposures for a position come from: the saved cache first, and if
it has nothing there, NASA/IPAC (IRSA) live.

Live path: one SIA search per collection lists every exposure covering the spot
(all six detectors), we keep the earliest few observations, and download a small
native cutout of each detector's image. Cutouts are cached on disk, so a spot
loads once and is instant afterwards.
"""
import asyncio
import hashlib
from pathlib import Path

from urllib.parse import urlencode

from ..archive import SIA_URL, ArchiveError, download, parse_results, validate_url
from ..local_store import DATA_DIR
from .common import DETECTORS, LEVELS, SHOTS, Shot, _read_wavelength, key, local_shots, request_for

import numpy as np
from .static_index import indexed_exposures
from .s3_cutouts import cutout as s3_cutout
from .s3_cutouts import metadata as s3_metadata
import os

CACHE = Path(__file__).resolve().parents[2] / ".cache" / "cutouts"
EPOCHS = 18           # observations kept per spot, spread over the survey: each sees other wavelengths
COLLECTIONS = ("spherex_dr1", "spherex_qr3")
_locks: dict[tuple[float, float], asyncio.Lock] = {}
_downloads = asyncio.Semaphore(6)


async def ensure_shots(client, ra: float, dec: float) -> None:
    """Fill SHOTS for this position. Idempotent. Raises ArchiveError if IRSA can't be reached."""
    k = key(ra, dec)
    if k in SHOTS:
        return
    lock = _locks.setdefault(k, asyncio.Lock())
    async with lock:
        if k in SHOTS:
            return
        # Explicit index mode must not be short-circuited by a partial bundled
        # target (Barnard's offline sample contains only detector 1).
        if not os.environ.get('SPHEREX_INDEX_DIR'):
            saved = await asyncio.to_thread(local_shots, *k)
            if saved:
                SHOTS[k] = saved
                return
        SHOTS[k] = await live_shots(client, *k)


async def live_shots(client, ra: float, dec: float) -> tuple[Shot, ...]:
    try:
        indexed = await asyncio.to_thread(indexed_exposures, ra, dec)
    except (OSError, ValueError, KeyError, IndexError) as exc:
        raise ArchiveError(f'Cannot read configured SPHEREx index: {exc}') from exc
    bodies = [] if indexed is not None else await asyncio.gather(*(
        download(client, SIA_URL, {"COLLECTION": c, "POS": f"CIRCLE {ra} {dec} 0.000001", "MAXREC": "10000"})
        for c in COLLECTIONS))
    exposures = {(e.id, e.detector): e for e in indexed or []}
    for detector in DETECTORS:
        req = request_for(ra, dec, detector)
        for collection, body in zip(COLLECTIONS, bodies):
            rows, _ = parse_results(body, collection, req)
            for e in rows:
                exposures.setdefault((e.id, e.detector), e)
    # Observations spread evenly over time (one observation = the same id on every
    # detector). The earliest ones alone are all from one week and see the same wavelengths.
    first_seen: dict[str, float] = {}
    for e in exposures.values():
        first_seen[e.id] = min(first_seen.get(e.id, e.mjd), e.mjd)
    ordered = sorted(first_seen, key=first_seen.get)
    if len(ordered) > EPOCHS:
        ordered = [ordered[round(i * (len(ordered) - 1) / (EPOCHS - 1))] for i in range(EPOCHS)]
    chosen = set(ordered)
    wanted = [e for e in exposures.values() if e.id in chosen]

    async def fetch(e):
        url = cutout_url_for(e.fits_url, ra, dec, LEVELS[0]["cutout_deg"])
        path = CACHE / f"{hashlib.sha1(url.encode()).hexdigest()}.fits"
        try:
            if os.environ.get('SPHEREX_IMAGE_SOURCE') == 's3':
                async with _downloads:
                    info = await s3_metadata(e.fits_url, ra, dec)
                # Reserve the path now; pixels are fetched only by a frame or
                # analysis request after the area metadata has been returned.
                wavelength = info['wavelength']
                return Shot(e.id, e.detector, e.mjd, path, wavelength, e.fits_url)
            elif not path.exists():
                async with _downloads:
                    body = await download(client, url)
                CACHE.mkdir(parents=True, exist_ok=True)
                path.write_bytes(body)
            wavelength = await asyncio.to_thread(_read_wavelength, str(path), ra, dec)
        except (ArchiveError, OSError, KeyError, ValueError):
            return None  # one bad cutout shouldn't sink the area
        return Shot(e.id, e.detector, e.mjd, path, wavelength, e.fits_url) if np.isfinite(wavelength) else None

    shots = [s for s in await asyncio.gather(*(fetch(e) for e in wanted)) if s]
    if wanted and not shots:
        raise ArchiveError('Exposures were found, but no usable image could be downloaded or read; retry the request')
    return tuple(sorted(shots, key=lambda s: (s.mjd, s.detector)))


def cutout_url_for(fits_url: str, ra: float, dec: float, size_deg: float) -> str:
    return validate_url(fits_url) + "?" + urlencode({"center": f"{ra},{dec}", "size": size_deg, "gzip": "false"})


def cutout_path(shot: Shot, ra: float, dec: float, level: int, science: bool = True) -> Path:
    """Where this exposure's file for a level lives (it may not be downloaded yet).
    Level 0 is already on disk, and the saved cache has one small file per exposure."""
    if not shot.fits_url or DATA_DIR in shot.path.parents:
        return shot.path
    if level == 0:
        return shot.path.with_suffix('.science.fits') if science else shot.path
    url = cutout_url_for(shot.fits_url, ra, dec, LEVELS[level]["cutout_deg"])
    suffix = '.science.fits' if science else '.fits'
    return CACHE / f"{hashlib.sha1(url.encode()).hexdigest()}{suffix}"


async def ensure_cutouts(client, shots, ra: float, dec: float, level: int) -> None:
    await asyncio.gather(*(ensure_cutout(client, s, ra, dec, level, science=True) for s in shots))


async def ensure_cutout(client, shot: Shot, ra: float, dec: float, level: int, science: bool = False) -> Path:
    """The file to render this exposure at a level, downloading a larger cutout once if needed."""
    path = cutout_path(shot, ra, dec, level, science=science)
    if os.environ.get('SPHEREX_IMAGE_SOURCE') == 's3' and shot.fits_url and DATA_DIR not in shot.path.parents:
        async with _downloads:
            source = await s3_cutout(shot.fits_url, ra, dec, LEVELS[level]['cutout_deg'], science=science)
        # Higher-level renderers resolve cutout_path, so install the same original
        # at the expected level path without another network request.
        if path != source and not path.exists():
            CACHE.mkdir(parents=True, exist_ok=True)
            try:
                await asyncio.to_thread(os.link, source, path)
            except FileExistsError:
                pass  # another frame request installed the same cached file
        return path
    if path == shot.path and path.exists():
        return path
    url = cutout_url_for(shot.fits_url, ra, dec, LEVELS[level]["cutout_deg"])
    if not path.exists():
        async with _downloads:
            body = await download(client, url)
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    return path
