"""Catalog adapter interface for Field Context.

Each catalog sits behind one adapter with its own timeout and raw-response cache. One failing
source shows up in ``status_by_source`` and never breaks the response.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any

import astropy.units as u
from astropy.coordinates import Distance, SkyCoord
from astropy.time import Time

from .. import config

log = logging.getLogger(__name__)


@dataclass
class CatalogSource:
    """One catalog row, normalised. Positions at ``epoch_jyear``; pm in mas/yr."""

    catalog: str  # "simbad" | "gaia_dr3" | "catwise2020"
    id: str
    ra: float
    dec: float
    epoch_jyear: float
    pm_ra_cosdec: float | None = None  # mas/yr
    pm_dec: float | None = None  # mas/yr
    parallax: float | None = None  # mas
    rv: float | None = None  # km/s
    name: str | None = None  # preferred display name (SIMBAD "NAME ..." or main_id)
    otype: str | None = None  # SIMBAD object type
    mags: dict[str, float] = field(default_factory=dict)

    def position_at(self, mjd: float) -> tuple[float, float]:
        """Propagate to ``mjd`` (astropy apply_space_motion). Without pm, returns as is.
        Without a positive parallax, propagates without distance."""
        if self.pm_ra_cosdec is None or self.pm_dec is None:
            return self.ra, self.dec
        if self.pm_ra_cosdec == 0 and self.pm_dec == 0:
            return self.ra, self.dec
        kw: dict[str, Any] = dict(
            ra=self.ra * u.deg, dec=self.dec * u.deg,
            pm_ra_cosdec=self.pm_ra_cosdec * u.mas / u.yr, pm_dec=self.pm_dec * u.mas / u.yr,
            obstime=Time(self.epoch_jyear, format="jyear"),
        )
        if self.parallax is not None and self.parallax > 0:
            kw["distance"] = Distance(parallax=self.parallax * u.mas)
            if self.rv is not None and math.isfinite(self.rv):
                kw["radial_velocity"] = self.rv * u.km / u.s
        c = SkyCoord(**kw)
        with _quiet():
            p = c.apply_space_motion(new_obstime=Time(mjd, format="mjd"))
        return float(p.ra.deg), float(p.dec.deg)


class _quiet:
    """apply_space_motion without distance warns (ErfaWarning / AstropyWarning); harmless."""

    def __enter__(self):
        import warnings

        self._cm = warnings.catch_warnings()
        self._cm.__enter__()
        warnings.simplefilter("ignore")

    def __exit__(self, *a):
        return self._cm.__exit__(*a)


@dataclass
class ConeQuery:
    """Cone at ``(ra, dec)`` of ``radius_arcsec`` around the target, valid at ``mjd``.

    Fast movers sit far from their catalog-epoch position, so adapters search a wider radius
    (radius + pm_max × |Δt|) and keep rows whose pm can bring them inside the cone."""

    ra: float
    dec: float
    radius_arcsec: float
    mjd: float


class CatalogAdapter:
    name: str = "catalog"
    epoch_jyear: float = 2000.0
    timeout_s: float = 30.0

    def __init__(self, cache=None):
        self._cache = cache

    def _get_cache(self):
        if self._cache is None:
            from ..cache import get_cache

            self._cache = get_cache()
        return self._cache

    # --- to implement -------------------------------------------------------
    def build_query(self, q: ConeQuery) -> str:  # ADQL
        raise NotImplementedError

    def run_query(self, adql: str) -> list[dict[str, Any]]:  # blocking; raw rows
        raise NotImplementedError

    def parse(self, rows: list[dict[str, Any]]) -> list[CatalogSource]:
        raise NotImplementedError

    # --- shared ---------------------------------------------------------------
    def wide_radius_deg(self, q: ConeQuery) -> tuple[float, float]:
        """→ (cone radius deg, extra search radius deg so fast movers from the catalog epoch fit)."""
        dt_yr = abs(Time(q.mjd, format="mjd").jyear - self.epoch_jyear)
        return q.radius_arcsec / 3600.0, config.CONTEXT_PM_MAX_ARCSEC_YR * dt_yr / 3600.0

    async def cone(self, q: ConeQuery) -> list[CatalogSource]:
        adql = self.build_query(q)
        key = f"catalog:v1:{self.name}:{adql}"
        cache = self._get_cache()
        rows = cache.get(key)
        if rows is None:
            down = cache.get(self._outage_key)
            if down is not None:
                raise CatalogUnavailable(f"skipped: unavailable since {down['since']} ({down['reason']})")
            try:
                rows = await asyncio.wait_for(asyncio.to_thread(self.run_query, adql), timeout=self.timeout_s)
            except Exception as exc:
                if is_outage(exc):
                    # Remember the outage (across requests and processes) so later requests
                    # skip this catalog instead of waiting out the timeout again.
                    cache.set(self._outage_key, {"since": time.strftime("%H:%M:%S"), "reason": _short(exc)},
                              expire=config.CONTEXT_OUTAGE_S)
                raise
            cache.set(key, json.loads(json.dumps(rows, default=_json_default)),
                      expire=config.CONTEXT_CACHE_TTL_S.get(self.name))
        return self.parse(rows)

    @property
    def _outage_key(self) -> str:
        return f"catalog:outage:{self.name}"


class CatalogUnavailable(RuntimeError):
    """The catalog timed out or 5xx'd recently; skipped without a network call."""


_OUTAGE_MARKERS = ("timeout", "timed out", "502", "503", "504", "connection", "proxy error")


def is_outage(exc: BaseException) -> bool:
    """Timeouts, 5xx and connection failures mean the service is down. Query errors (bad
    ADQL, 4xx) are bugs and must not be hidden behind the outage skip."""
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError, ConnectionError)):
        return True
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(m in text for m in _OUTAGE_MARKERS)


def _short(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:120]}"


class TimeoutSession:
    """requests.Session whose requests default to a timeout. pyvo passes none, so a stalled
    TAP server would otherwise keep the worker thread alive long after asyncio gave up."""

    def __new__(cls, timeout_s: float):
        import requests

        class _S(requests.Session):
            def request(self, *args, **kwargs):
                kwargs.setdefault("timeout", timeout_s)
                return super().request(*args, **kwargs)

        return _S()


def tap_rows(url: str, adql: str, timeout_s: float, maxrec: int = 5000) -> list[dict[str, Any]]:
    """Synchronous TAP query with a hard socket timeout → plain dict rows."""
    import pyvo

    svc = pyvo.dal.TAPService(url, session=TimeoutSession(timeout_s))
    return table_rows(svc.run_sync(adql, maxrec=maxrec).to_table())


def _json_default(v):
    if hasattr(v, "item"):
        return v.item()
    if isinstance(v, bytes):
        return v.decode()
    return str(v)


def table_rows(tbl) -> list[dict[str, Any]]:
    """astropy Table → list of plain dicts (masked → None)."""
    out = []
    names = tbl.colnames
    for r in tbl:
        d = {}
        for n in names:
            v = r[n]
            if v is None or getattr(v, "mask", False) is True or (hasattr(v, "mask") and bool(v.mask)):
                d[n] = None
                continue
            if hasattr(v, "item"):
                v = v.item()
            if isinstance(v, bytes):
                v = v.decode()
            if isinstance(v, float) and not math.isfinite(v):
                v = None
            d[n] = v
        out.append(d)
    return out
