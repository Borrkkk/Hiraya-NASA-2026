"""Solar-system bodies in each frame's cutout at that frame's time.

- Observer: SPHEREx itself. Its geocentric ICRF state comes from JPL Horizons (spacecraft
  -163182), one batched call for all frame times.
- Primary: IMCCE SkyBoT cone search (~2 s/call, geocentric observer), corrected to SPHEREx's
  position (≈7000 km from Earth's centre → up to ~5″ for main-belt asteroids, far more for NEOs).
- Fallback: JPL sb_ident (two-pass, ``xobs`` = SPHEREx state). Accurate but ~90 s per call,
  so it is capped per request.

One query per exposure (obs_id): the 6 detectors of an exposure share the time and the target.
"""
from __future__ import annotations

import asyncio
import logging
import math
import time
from collections import defaultdict
from typing import Any

import httpx
import numpy as np
from astropy.coordinates import Angle
from astropy.time import Time
import astropy.units as u

from .. import config
from ..models import FrameRef, KnownBody, Target
from .base import is_outage

log = logging.getLogger(__name__)

_AU_KM = 149_597_870.7


# --------------------------------------------------------------------------- #
# Geometry helpers (pure)
# --------------------------------------------------------------------------- #


def topocentric(ra_deg: float, dec_deg: float, dist_au: float, obs_km: tuple[float, float, float]) -> tuple[float, float]:
    """Geocentric direction + distance → direction seen from an observer at ``obs_km``
    (geocentric ICRF, km). Exact parallax shift; light-time difference ignored."""
    ra, dec = math.radians(ra_deg), math.radians(dec_deg)
    d = dist_au * _AU_KM
    p = np.array([d * math.cos(dec) * math.cos(ra), d * math.cos(dec) * math.sin(ra), d * math.sin(dec)])
    q = p - np.asarray(obs_km, float)
    ra2 = math.degrees(math.atan2(q[1], q[0])) % 360.0
    dec2 = math.degrees(math.asin(q[2] / np.linalg.norm(q)))
    return ra2, dec2


def sep_arcsec(ra1, dec1, ra2, dec2) -> float:
    r1, d1, r2, d2 = map(math.radians, (ra1, dec1, ra2, dec2))
    s = math.sin((d2 - d1) / 2) ** 2 + math.cos(d1) * math.cos(d2) * math.sin((r2 - r1) / 2) ** 2
    return math.degrees(2 * math.asin(min(1.0, math.sqrt(s)))) * 3600.0


def object_class_from_skybot(cls: str | None, name: str) -> str:
    c = (cls or "").lower()
    if "comet" in c or name.startswith(("C/", "P/")) or (name[:-1].isdigit() and name.endswith("P")):
        return "comet"
    return "asteroid"


def _sexa_ra(s: str) -> float:
    return float(Angle(s.replace(" ", ":"), unit=u.hourangle).deg)


def _sexa_dec(s: str) -> float:
    s = s.replace("'", " ").replace('"', " ").replace(":", " ").strip()
    return float(Angle(s, unit=u.deg).deg)


def jpl_fov(ra: float, dec: float) -> tuple[str, str]:
    """sb_ident FOV centre format: hh-mm-ss.ss and [M]dd-mm-ss.s (M = negative)."""
    hms = Angle(ra * u.deg).to_string(unit=u.hour, sep="-", precision=2, pad=True)
    dms = Angle(abs(dec) * u.deg).to_string(unit=u.deg, sep="-", precision=1, pad=True)
    return hms, ("M" if dec < 0 else "") + dms


# --------------------------------------------------------------------------- #
# Parsers (pure)
# --------------------------------------------------------------------------- #


def parse_skybot(rows: list[dict[str, Any]], t_mjd: float, target: Target,
                 obs_km: tuple[float, float, float] | None) -> list[KnownBody]:
    out = []
    for r in rows:
        name = " ".join(str(x) for x in (r.get("Num"), r.get("Name")) if x not in (None, "")).strip()
        try:
            ra, dec = _sexa_ra(r["RA (hms)"]), _sexa_dec(r["DEC (dms)"])
        except Exception:
            continue
        dg = r.get("dg (ua)")
        if obs_km is not None and dg:
            ra, dec = topocentric(ra, dec, float(dg), obs_km)
        v = r.get("VMag (mag)")
        if v is not None and float(v) > config.SOLAR_MAX_V:
            continue
        mags = {"V": float(v)} if v is not None else {}
        out.append(KnownBody(
            name=name or "unknown", object_class=object_class_from_skybot(r.get("Class"), str(r.get("Name") or "")),
            source_catalogs=["skybot"], ra_at_t=ra, dec_at_t=dec, t_ref=t_mjd,
            separation_arcsec=sep_arcsec(ra, dec, target.coord.ra, target.coord.dec), mags=mags,
            is_solar_system=True,
            ids={k: str(v) for k, v in (("skybot_class", r.get("Class")), ("observer", "spherex" if obs_km else "geocentre"),
                                         ("rate_ra_arcsec_h", r.get("dRA (arcsec/h)")), ("rate_dec_arcsec_h", r.get("dDEC (arcsec/h)")))
                 if v is not None},
        ))
    return sorted(out, key=lambda b: b.separation_arcsec)


def parse_sb_ident(j: dict[str, Any], t_mjd: float, target: Target) -> list[KnownBody]:
    fields = j.get("fields_second") or j.get("fields_first") or []
    data = j.get("data_second_pass") or j.get("data_first_pass") or []
    idx = {f: i for i, f in enumerate(fields)}

    def col(row, prefix):
        for f, i in idx.items():
            if f.startswith(prefix):
                return row[i]
        return None

    out = []
    for row in data:
        try:
            ra, dec = _sexa_ra(col(row, "Astrometric RA")), _sexa_dec(col(row, "Astrometric Dec"))
        except Exception:
            continue
        v = col(row, "Visual magnitude")
        try:
            vmag = float(v)
        except (TypeError, ValueError):
            vmag = None
        if vmag is not None and vmag > config.SOLAR_MAX_V:
            continue
        name = str(col(row, "Object name") or "unknown").strip()
        out.append(KnownBody(
            name=name, object_class=object_class_from_skybot(None, name), source_catalogs=["jpl_sb_ident"],
            ra_at_t=ra, dec_at_t=dec, t_ref=t_mjd,
            separation_arcsec=sep_arcsec(ra, dec, target.coord.ra, target.coord.dec),
            mags={"V": vmag} if vmag is not None else {}, is_solar_system=True,
            ids={k: str(v) for k, v in (("rate_ra_arcsec_h", col(row, "RA rate")), ("rate_dec_arcsec_h", col(row, "Dec rate")),
                                         ("observer", "spherex")) if v is not None},
        ))
    return sorted(out, key=lambda b: b.separation_arcsec)


def parse_horizons_vectors(result: str) -> dict[float, tuple[float, float, float]]:
    """Horizons CSV VECTORS (table 2) → {JD: (x, y, z) km}."""
    if "$$SOE" not in result:
        raise ValueError(f"no ephemeris in Horizons reply: {result[-300:]}")
    out = {}
    for line in result.split("$$SOE")[1].split("$$EOE")[0].strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        out[round(float(parts[0]), 6)] = (float(parts[2]), float(parts[3]), float(parts[4]))
    return out


# --------------------------------------------------------------------------- #
# Service
# --------------------------------------------------------------------------- #


def _jd(mjd: float) -> float:
    return round(mjd + 2400000.5, 6)


class SolarSystemLookup:
    def __init__(self, cache=None, client: httpx.AsyncClient | None = None):
        self._cache = cache
        self._client = client

    def _get_cache(self):
        if self._cache is None:
            from ..cache import get_cache

            self._cache = get_cache()
        return self._cache

    # -- network pieces (each cached; raw responses only) ----------------------
    async def spherex_positions(self, client, mjds: list[float]) -> dict[float, tuple[float, float, float]]:
        cache = self._get_cache()
        out, missing = {}, []
        for m in mjds:
            hit = cache.get(f"horizons:spherex:v1:{_jd(m)}")
            if hit is not None:
                out[_jd(m)] = tuple(hit)
            else:
                missing.append(m)
        for i in range(0, len(missing), 100):  # keep the GET URL short
            chunk = missing[i:i + 100]
            p = {"format": "json", "COMMAND": f"'{config.SPHEREX_HORIZONS_ID}'", "OBJ_DATA": "'NO'",
                 "MAKE_EPHEM": "'YES'", "EPHEM_TYPE": "'VECTORS'", "CENTER": "'500@399'", "REF_PLANE": "'FRAME'",
                 "REF_SYSTEM": "'ICRF'", "OUT_UNITS": "'KM-S'", "VEC_TABLE": "'2'", "CSV_FORMAT": "'YES'",
                 "TIME_TYPE": "'UT'", "TLIST": "'" + "' '".join(f"{_jd(m):.6f}" for m in chunk) + "'"}
            r = await client.get(config.HORIZONS_URL, params=p, timeout=config.SOLAR_TIMEOUT_S)
            r.raise_for_status()
            vecs = parse_horizons_vectors(r.json()["result"])
            # Match each requested time to the nearest returned row (within ~1 s) rather than
            # relying on Horizons echoing the JD with identical float formatting.
            jds = np.array(sorted(vecs))
            for m in chunk:
                i = int(np.argmin(np.abs(jds - _jd(m))))
                if abs(jds[i] - _jd(m)) <= 1.2e-5:
                    xyz = vecs[float(jds[i])]
                    cache.set(f"horizons:spherex:v1:{_jd(m)}", list(xyz))
                    out[_jd(m)] = xyz
        return out

    async def skybot(self, client, t_mjd: float, target: Target, radius_deg: float) -> list[dict[str, Any]]:
        key = f"skybot:v1:{_jd(t_mjd)}:{target.coord.ra:.6f}:{target.coord.dec:.6f}:{radius_deg:.5f}"
        cache = self._get_cache()
        hit = cache.get(key)
        if hit is not None:
            return hit
        p = {"-ep": Time(t_mjd, format="mjd", scale="utc").isot, "-ra": f"{target.coord.ra:.6f}",
             "-dec": f"{target.coord.dec:.6f}", "-rd": f"{radius_deg:.5f}", "-mime": "json", "-output": "all",
             "-loc": "500", "-from": "SPHERExInspect"}
        r = await client.get(config.SKYBOT_URL, params=p, timeout=config.SOLAR_TIMEOUT_S)
        if r.status_code == 204:  # VERIFIED: no object in the field → 204, empty body
            rows: list[dict[str, Any]] = []
        else:
            r.raise_for_status()
            j = r.json()
            rows = j if isinstance(j, list) else []
        cache.set(key, rows)
        return rows

    async def sb_ident(self, client, t_mjd: float, target: Target, half_deg: float,
                       obs_km: tuple[float, float, float] | None) -> dict[str, Any]:
        key = f"sbident:v1:{_jd(t_mjd)}:{target.coord.ra:.6f}:{target.coord.dec:.6f}:{half_deg:.5f}"
        cache = self._get_cache()
        hit = cache.get(key)
        if hit is not None:
            return hit
        ra_s, dec_s = jpl_fov(target.coord.ra, target.coord.dec)
        # VERIFIED: mpc-code=500 is rejected; xobs=0,0,0 is accepted (no rates without velocity).
        xobs = ",".join(f"{v:.6f}" for v in obs_km) if obs_km else "0,0,0"
        p = {"xobs": xobs, "obs-time": f"{_jd(t_mjd):.6f}", "fov-ra-center": ra_s, "fov-dec-center": dec_s,
             "fov-ra-hwidth": f"{half_deg:.5f}", "fov-dec-hwidth": f"{half_deg:.5f}", "two-pass": "true",
             "suppress-first-pass": "true", "mag-required": "false"}
        r = await client.get(config.SB_IDENT_URL, params=p, timeout=config.SB_IDENT_TIMEOUT_S)
        r.raise_for_status()
        j = r.json()
        if (j.get("signature") or {}).get("version") != "1.1":
            log.warning("sb_ident signature version %s (expected 1.1)", (j.get("signature") or {}).get("version"))
        cache.set(key, j)
        return j

    # -- entry point ------------------------------------------------------------
    async def lookup(self, target: Target, frames: list[FrameRef]) -> tuple[dict[str, list[KnownBody]], dict[str, str]]:
        """→ ({frame_id: bodies in the cutout at that frame's time}, status). Never raises."""
        status: dict[str, str] = {}
        if not frames:
            return {}, status
        by_obs: dict[str, list[FrameRef]] = defaultdict(list)
        for f in frames:
            by_obs[f.obs_id].append(f)
        t_by_obs = {o: float(np.mean([f.t_mid for f in fs])) for o, fs in by_obs.items()}
        half = target.cutout_size_deg / 2
        radius = half * math.sqrt(2)  # cone covering the square cutout

        own = self._client is None
        client = self._client or httpx.AsyncClient(follow_redirects=True)
        try:
            try:
                obs_pos = await self.spherex_positions(client, list(t_by_obs.values()))
                status["horizons"] = f"ok ({len(obs_pos)} SPHEREx states)"
            except Exception as exc:
                obs_pos = {}
                status["horizons"] = f"error: {type(exc).__name__}: {str(exc)[:150]} (positions are geocentric)"

            cache = self._get_cache()
            sem = asyncio.Semaphore(config.SOLAR_CONCURRENCY)
            outage = cache.get("solar:outage:skybot")

            async def one(obs_id: str, t: float):
                obs_km = obs_pos.get(_jd(t))
                if outage is None:
                    try:
                        async with sem:
                            rows = await self.skybot(client, t, target, radius)
                        return obs_id, parse_skybot(rows, t, target, obs_km), "skybot"
                    except Exception as exc:
                        if is_outage(exc):
                            cache.set("solar:outage:skybot", {"since": time.strftime("%H:%M:%S")},
                                      expire=config.CONTEXT_OUTAGE_S)
                        return obs_id, None, f"skybot error: {type(exc).__name__}: {str(exc)[:120]}"
                return obs_id, None, "skybot skipped: unavailable"

            results = await asyncio.gather(*(one(o, t) for o, t in t_by_obs.items()))

            failed = [(o, err) for o, bodies, err in results if bodies is None]
            n_jpl = 0
            jpl_results = {}
            for obs_id, _ in failed[: config.SB_IDENT_MAX_CALLS]:
                t = t_by_obs[obs_id]
                try:
                    j = await self.sb_ident(client, t, target, half, obs_pos.get(_jd(t)))
                    jpl_results[obs_id] = parse_sb_ident(j, t, target)
                    n_jpl += 1
                except Exception as exc:
                    log.info("sb_ident failed for %s: %s", obs_id, exc)
        finally:
            if own:
                await client.aclose()

        out: dict[str, list[KnownBody]] = {}
        n_sky = 0
        for obs_id, bodies, _ in results:
            if bodies is None:
                bodies = jpl_results.get(obs_id)
            else:
                n_sky += 1
            if bodies is None:
                continue
            # Keep bodies inside the square cutout.
            bodies = [b for b in bodies if _in_square(b, target, half)]
            if bodies:
                for f in by_obs[obs_id]:
                    out[f.frame_id] = bodies
        status["skybot"] = (f"ok ({n_sky}/{len(t_by_obs)} exposures)" if not failed
                            else f"partial: {len(failed)}/{len(t_by_obs)} exposures failed ({failed[0][1]})")
        if failed:
            status["jpl_sb_ident"] = (f"fallback for {n_jpl} of {len(failed)} failed exposures "
                                      f"(capped at {config.SB_IDENT_MAX_CALLS})")
        return out, status


def _in_square(b: KnownBody, target: Target, half_deg: float) -> bool:
    ddec = abs(b.dec_at_t - target.coord.dec)
    dra = abs(((b.ra_at_t - target.coord.ra + 180) % 360) - 180) * math.cos(math.radians(target.coord.dec))
    return dra <= half_deg and ddec <= half_deg
