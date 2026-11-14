"""[2] Frame Discovery: which SPHEREx frames contain the target point?

Talks to IRSA *metadata* only (SIA). Downloads no pixels and measures nothing.
"""
from __future__ import annotations

import asyncio
import logging
import re
from collections import defaultdict
from typing import Any, Iterable, Protocol

from . import config
from .models import DiscoveryResult, FrameRef, Target

log = logging.getLogger(__name__)

_COLLECTION_RE = re.compile(r"^spherex_(dr|qr)(\d+)(_deep)?$")
_BAND_RE = re.compile(r"SPHEREx-D(\d)")


class DiscoveryError(RuntimeError):
    """IRSA could not be queried at all (every collection failed)."""


# --------------------------------------------------------------------------- #
# IRSA backend (the only part that does I/O); swappable in tests
# --------------------------------------------------------------------------- #


class SiaBackend(Protocol):
    def list_collections(self) -> list[str]: ...

    def query(self, ra: float, dec: float, radius_arcsec: float, collection: str) -> list[dict[str, Any]]: ...


class IrsaSiaBackend:
    """Blocking astroquery calls; Discovery runs them in a thread."""

    def list_collections(self) -> list[str]:
        from astroquery.ipac.irsa import Irsa

        tbl = Irsa.list_collections(servicetype="SIA", filter=config.COLLECTION_FILTER)
        return [str(c) for c in tbl["collection"]]

    def query(self, ra: float, dec: float, radius_arcsec: float, collection: str) -> list[dict[str, Any]]:
        import astropy.units as u
        from astropy.coordinates import SkyCoord
        from astroquery.ipac.irsa import Irsa

        tbl = Irsa.query_sia(
            pos=(SkyCoord(ra * u.deg, dec * u.deg, frame="icrs"), radius_arcsec * u.arcsec),
            collection=collection,
        )
        cols = [
            "obs_id", "energy_bandpassname", "t_min", "t_max", "s_region", "access_url",
            "s_pixel_scale", "em_min", "em_max", "obs_collection", "dataproduct_subtype",
        ]
        units = {c: (str(tbl[c].unit) if c in tbl.colnames and tbl[c].unit is not None else None) for c in cols}
        rows = []
        for r in tbl:
            d = {c: _plain(r[c]) for c in cols if c in tbl.colnames}
            d["_units"] = units
            rows.append(d)
        return rows


def _plain(v: Any) -> Any:
    """numpy / masked scalar → plain Python (None when masked)."""
    if v is None or getattr(v, "mask", False) is True:
        return None
    if hasattr(v, "item"):
        v = v.item()
    if isinstance(v, bytes):
        v = v.decode()
    return v


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #


def select_collections(available: Iterable[str]) -> list[str]:
    """Newest DR and newest QR, plus their ``_deep`` variants when present.

    Never hard-codes a release; superseded releases (e.g. QR2) drop out
    automatically. Cubes and other products are ignored.
    """
    avail = set(available)
    newest: dict[str, int] = {}
    for name in avail:
        m = _COLLECTION_RE.match(name)
        if m:
            kind, num = m.group(1), int(m.group(2))
            newest[kind] = max(newest.get(kind, -1), num)
    out: list[str] = []
    for kind in ("dr", "qr"):
        if kind in newest:
            base = f"spherex_{kind}{newest[kind]}"
            out += [c for c in (base, f"{base}_deep") if c in avail]
    return out


def parse_detector(bandpassname: str | None) -> int | None:
    m = _BAND_RE.search(bandpassname or "")
    return int(m.group(1)) if m else None


def parse_polygon(s_region: str | None) -> list[tuple[float, float]]:
    """'POLYGON ICRS ra1 dec1 ra2 dec2 ...' → [(ra, dec), ...] (closing vertex dropped)."""
    if not s_region:
        return []
    nums = [float(t) for t in s_region.split() if _is_float(t)]
    pts = list(zip(nums[0::2], nums[1::2]))
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    return pts


def _is_float(t: str) -> bool:
    try:
        float(t)
        return True
    except ValueError:
        return False


def release_from_collection(collection: str) -> str:
    m = _COLLECTION_RE.match(collection)
    if not m:
        return collection
    return f"{m.group(1).upper()}{m.group(2)}" + ("-deep" if m.group(3) else "")


def cutout_url(access_url: str, ra: float, dec: float, size_deg: float) -> str:
    # Pattern from the IRSA SPHEREx cutout tutorial (IBE cutout service).
    return f"{access_url}?center={ra:.7f},{dec:.7f}d&size={size_deg:g}"


def _to_um(value: float | None, unit: str | None) -> float | None:
    if value is None:
        return None
    factor = {"m": 1e6, "um": 1.0, "micron": 1.0, "nm": 1e-3}.get((unit or "m").strip(), 1e6)
    return float(value) * factor


def _to_arcsec(value: float | None, unit: str | None) -> float | None:
    if value is None:
        return None
    factor = {"arcsec": 1.0, "deg": 3600.0, "arcmin": 60.0}.get((unit or "arcsec").strip(), 1.0)
    return float(value) * factor


def row_to_frame(row: dict[str, Any], target: Target, collection: str) -> FrameRef | None:
    det = parse_detector(row.get("energy_bandpassname"))
    obs_id, url = row.get("obs_id"), row.get("access_url")
    t_min, t_max = row.get("t_min"), row.get("t_max")
    if det is None or not obs_id or not url or t_min is None or t_max is None:
        return None
    if row.get("dataproduct_subtype") not in (None, "science"):
        return None
    units = row.get("_units") or {}
    coll = row.get("obs_collection") or collection
    return FrameRef(
        frame_id=f"{obs_id}D{det}",
        obs_id=str(obs_id),
        detector=det,
        t_min=float(t_min),
        t_max=float(t_max),
        t_mid=0.5 * (float(t_min) + float(t_max)),
        footprint=parse_polygon(row.get("s_region")),
        release=release_from_collection(coll),
        collection=coll,
        em_min_um=_to_um(row.get("em_min"), units.get("em_min")),
        em_max_um=_to_um(row.get("em_max"), units.get("em_max")),
        pixel_scale_arcsec=_to_arcsec(row.get("s_pixel_scale"), units.get("s_pixel_scale")),
        cutout_url=cutout_url(str(url), target.coord.ra, target.coord.dec, target.cutout_size_deg),
        full_url=str(url),
    )


def filter_frames(frames: Iterable[FrameRef], target: Target) -> list[FrameRef]:
    """Band + time filter, dedupe on frame_id, sort by time."""
    tr = target.time_range
    seen: dict[str, FrameRef] = {}
    for f in frames:
        if f.detector not in target.bands:
            continue
        if tr.start is not None and f.t_max < tr.start:
            continue
        if tr.end is not None and f.t_min > tr.end:
            continue
        seen.setdefault(f.frame_id, f)
    return sorted(seen.values(), key=lambda f: (f.t_mid, f.detector))


def cap_frames(frames: list[FrameRef], max_frames: int) -> list[FrameRef]:
    """Keep at most ``max_frames``, spread evenly across detectors and time.

    Each detector gets an equal share (leftover share goes to detectors that
    have more frames); within a detector, picks are evenly spaced in the
    time-sorted list so the first and last epochs are always kept.
    """
    if len(frames) <= max_frames:
        return list(frames)
    by_det: dict[int, list[FrameRef]] = defaultdict(list)
    for f in frames:
        by_det[f.detector].append(f)

    quota = {d: 0 for d in by_det}
    remaining = max_frames
    open_dets = sorted(by_det)
    while remaining > 0 and open_dets:
        share = max(1, remaining // len(open_dets))
        for d in list(open_dets):
            if remaining == 0:
                break
            give = min(share, len(by_det[d]) - quota[d], remaining)
            quota[d] += give
            remaining -= give
            if quota[d] >= len(by_det[d]):
                open_dets.remove(d)

    picked: list[FrameRef] = []
    for d, fs in by_det.items():
        picked += _evenly_spaced(fs, quota[d])
    return sorted(picked, key=lambda f: (f.t_mid, f.detector))


def _evenly_spaced(items: list, k: int) -> list:
    n = len(items)
    if k <= 0:
        return []
    if k >= n:
        return list(items)
    if k == 1:
        return [items[0]]
    idx = sorted({round(i * (n - 1) / (k - 1)) for i in range(k)})
    return [items[i] for i in idx]


# --------------------------------------------------------------------------- #
# Component entry point
# --------------------------------------------------------------------------- #


_COLLECTIONS_CACHE_KEY = "sia:collections:v1"


class FrameDiscovery:
    def __init__(self, backend: SiaBackend | None = None, cache=None):
        self.backend = backend or IrsaSiaBackend()
        self._cache = cache
        self._collections: list[str] | None = None

    def _get_cache(self):
        if self._cache is None:
            from .cache import get_cache

            self._cache = get_cache()
        return self._cache

    async def collections(self) -> list[str]:
        if self._collections is None:
            try:
                avail = await _retry(self.backend.list_collections)
                self._get_cache().set(_COLLECTIONS_CACHE_KEY, list(avail))
            except Exception as exc:
                # IRSA's TAP listing 502s at times; fall back to the last list we saw.
                avail = self._get_cache().get(_COLLECTIONS_CACHE_KEY)
                if not avail:
                    raise DiscoveryError(f"could not list SIA collections: {exc}") from exc
                log.warning("SIA collection listing failed (%s); using cached list %s", exc, avail)
            chosen = select_collections(avail)
            if not chosen:
                raise DiscoveryError(f"no SPHEREx frame collections found among {avail}")
            self._collections = chosen
        return self._collections

    async def discover(self, target: Target) -> tuple[DiscoveryResult, list[str]]:
        """Returns the result plus a list of warnings (e.g. a collection failed)."""
        warnings: list[str] = []
        collections = await self.collections()

        async def one(coll: str):
            rows = await _retry(
                self.backend.query, target.coord.ra, target.coord.dec,
                config.SIA_SEARCH_RADIUS_ARCSEC, coll,
            )
            return coll, rows

        results = await asyncio.gather(*(one(c) for c in collections), return_exceptions=True)
        frames: list[FrameRef] = []
        n_ok = 0
        for coll, res in zip(collections, results):
            if isinstance(res, BaseException):
                warnings.append(f"discovery: collection {coll} failed: {res}")
                log.warning("SIA query failed for %s: %s", coll, res)
                continue
            n_ok += 1
            for row in res[1]:
                f = row_to_frame(row, target, coll)
                if f is not None:
                    frames.append(f)
        if n_ok == 0:
            raise DiscoveryError("; ".join(warnings) or "all SIA queries failed")

        filtered = filter_frames(frames, target)
        capped = cap_frames(filtered, target.max_frames)
        if len(capped) < len(filtered):
            warnings.append(
                f"discovery: {len(filtered)} frames found, capped to {len(capped)} "
                f"(spread across detectors and time); raise max_frames or narrow the time range"
            )
        return DiscoveryResult(frames=capped, n_found=len(filtered), collections=collections), warnings


async def _retry(fn, *args, retries: int | None = None, backoff: float | None = None):
    """Run a blocking call in a thread, retrying transient failures."""
    retries = config.SIA_RETRIES if retries is None else retries
    backoff = config.SIA_BACKOFF_S if backoff is None else backoff
    last: BaseException | None = None
    for attempt in range(1, retries + 1):
        try:
            return await asyncio.to_thread(fn, *args)
        except Exception as exc:  # pyvo DALServiceError, ConnectionError, timeouts...
            last = exc
            log.info("IRSA call %s failed (attempt %d/%d): %s", getattr(fn, "__name__", fn), attempt, retries, exc)
            if attempt < retries:
                await asyncio.sleep(backoff * attempt)
    assert last is not None
    raise last
