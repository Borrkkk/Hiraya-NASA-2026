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

from ..archive import SIA_URL, ArchiveError, cutout_url, download, parse_results
from .common import DETECTORS, SHOTS, Shot, _read_wavelength, key, local_shots, request_for

import numpy as np

CACHE = Path(__file__).resolve().parents[2] / ".cache" / "cutouts"
EPOCHS = 10           # earliest observations kept per spot: more of them cover more wavelengths
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
        saved = await asyncio.to_thread(local_shots, *k)
        if saved:
            SHOTS[k] = saved
            return
        SHOTS[k] = await live_shots(client, *k)


async def live_shots(client, ra: float, dec: float) -> tuple[Shot, ...]:
    bodies = await asyncio.gather(*(
        download(client, SIA_URL, {"COLLECTION": c, "POS": f"CIRCLE {ra} {dec} 0.000001", "MAXREC": "10000"})
        for c in COLLECTIONS))
    exposures = {}
    for detector in DETECTORS:
        req = request_for(ra, dec, detector)
        for collection, body in zip(COLLECTIONS, bodies):
            rows, _ = parse_results(body, collection, req)
            for e in rows:
                exposures.setdefault((e.id, e.detector), e)
    # The earliest few observations (one observation = the same id on every detector).
    first_seen: dict[str, float] = {}
    for e in exposures.values():
        first_seen[e.id] = min(first_seen.get(e.id, e.mjd), e.mjd)
    chosen = set(sorted(first_seen, key=first_seen.get)[:EPOCHS])
    wanted = [e for e in exposures.values() if e.id in chosen]

    async def fetch(e):
        req = request_for(ra, dec, e.detector)
        url = cutout_url(e, req)
        path = CACHE / f"{hashlib.sha1(url.encode()).hexdigest()}.fits"
        try:
            if not path.exists():
                async with _downloads:
                    body = await download(client, url)
                CACHE.mkdir(parents=True, exist_ok=True)
                path.write_bytes(body)
            wavelength = await asyncio.to_thread(_read_wavelength, str(path), ra, dec)
        except (ArchiveError, OSError, KeyError, ValueError):
            return None  # one bad cutout shouldn't sink the area
        return Shot(e.id, e.detector, e.mjd, path, wavelength) if np.isfinite(wavelength) else None

    shots = [s for s in await asyncio.gather(*(fetch(e) for e in wanted)) if s]
    return tuple(sorted(shots, key=lambda s: (s.mjd, s.detector)))
