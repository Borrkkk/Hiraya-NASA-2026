"""Fixed-sky catalogs: SIMBAD, Gaia DR3, CatWISE2020 (positions propagated to frame time).

Each query is a cone around the target, widened so that a fast mover seen at the catalog
epoch can still fall in the cone at the frame time. The extra ring is filtered server-side:
a row is kept if it is already inside the cone, or if |pm| × |Δt| could bring it there.
"""
from __future__ import annotations

import logging
from typing import Any

from .. import config
from .base import CatalogAdapter, CatalogSource, ConeQuery, tap_rows, table_rows

log = logging.getLogger(__name__)


def _pm_aware_where(ra_col: str, dec_col: str, pm_expr: str, pm_to_deg_per_yr: float,
                    q: ConeQuery, r_deg: float, extra_deg: float, dt_yr: float,
                    index_cols: tuple[str, str] | None = None, index_slack_deg: float = 0.0) -> str:
    """``index_cols``: columns the service's spatial index is on, when they differ from the
    position columns (CatWISE indexes ra/dec, not ra_pm/dec_pm)."""
    big = r_deg + extra_deg
    ira, idec = index_cols or (ra_col, dec_col)
    dist = f"DISTANCE(POINT('ICRS', {ra_col}, {dec_col}), POINT('ICRS', {q.ra:.8f}, {q.dec:.8f}))"
    return (
        f"CONTAINS(POINT('ICRS', {ira}, {idec}), CIRCLE('ICRS', {q.ra:.8f}, {q.dec:.8f}, {big + index_slack_deg:.8f})) = 1 "
        f"AND ({dist} <= {r_deg:.8f} OR ({pm_expr}) * {pm_to_deg_per_yr * dt_yr:.10g} >= {dist} - {r_deg:.8f})"
    )


def _dt_years(epoch_jyear: float, mjd: float) -> float:
    from astropy.time import Time

    return abs(Time(mjd, format="mjd").jyear - epoch_jyear)


# --------------------------------------------------------------------------- #
# SIMBAD (positions at J2000)
# --------------------------------------------------------------------------- #


class SimbadAdapter(CatalogAdapter):
    name = "simbad"
    epoch_jyear = 2000.0
    timeout_s = config.CONTEXT_TIMEOUT_S

    def __init__(self, cache=None, servers: tuple[str, ...] | None = None):
        super().__init__(cache)
        self.servers = servers or config.SIMBAD_SERVERS
        self._working: str | None = None

    def build_query(self, q: ConeQuery) -> str:
        r, extra = self.wide_radius_deg(q)
        where = _pm_aware_where("b.ra", "b.dec", "SQRT(POWER(b.pmra, 2) + POWER(b.pmdec, 2))", 1 / 3.6e6,
                                q, r, extra, _dt_years(self.epoch_jyear, q.mjd))
        return (
            "SELECT b.main_id, b.otype, b.ra, b.dec, b.pmra, b.pmdec, b.plx_value, b.rvz_radvel, "
            "i.id AS name FROM basic AS b "
            "LEFT JOIN ident AS i ON i.oidref = b.oid AND i.id LIKE 'NAME %' "
            f"WHERE {where}"
        )

    def run_query(self, adql: str) -> list[dict[str, Any]]:
        last: Exception | None = None
        order = [self._working] + [s for s in self.servers if s != self._working] if self._working else list(self.servers)
        for server in order:
            try:
                rows = tap_rows(f"https://{server}/simbad/sim-tap", adql, self.timeout_s * 0.9)
                self._working = server
                return rows
            except Exception as exc:  # 404 capabilities, timeouts...
                log.info("SIMBAD server %s failed: %s", server, exc)
                last = exc
        raise last or RuntimeError("no SIMBAD server")

    def parse(self, rows: list[dict[str, Any]]) -> list[CatalogSource]:
        """One source per main_id (the NAME join gives one row per NAME identifier).
        Display name: main_id itself when it is a NAME identifier (SIMBAD's canonical spelling,
        e.g. "NAME Barnard's star"), else the alphabetically first NAME, else main_id."""
        first: dict[str, dict[str, Any]] = {}
        names: dict[str, list[str]] = {}
        for r in rows:
            mid = (r.get("main_id") or "").strip()
            if not mid or r.get("ra") is None:
                continue
            if (r.get("otype") or "").strip() in config.SIMBAD_SKIP_OTYPES:  # planets share the host's position
                continue
            first.setdefault(mid, r)
            n = r.get("name")
            if isinstance(n, str) and n.startswith("NAME "):
                names.setdefault(mid, []).append(n[5:].strip())
        out = []
        for mid, r in first.items():
            if mid.startswith("NAME "):
                display = mid[5:].strip()
            elif names.get(mid):
                display = sorted(names[mid])[0]
            else:
                display = mid
            out.append(CatalogSource(
                catalog=self.name, id=mid, ra=float(r["ra"]), dec=float(r["dec"]), epoch_jyear=self.epoch_jyear,
                pm_ra_cosdec=_f(r.get("pmra")), pm_dec=_f(r.get("pmdec")), parallax=_f(r.get("plx_value")),
                rv=_f(r.get("rvz_radvel")), name=display, otype=(r.get("otype") or "").strip() or None,
            ))
        return out


# --------------------------------------------------------------------------- #
# Gaia DR3 (positions at J2016.0)
# --------------------------------------------------------------------------- #


class GaiaAdapter(CatalogAdapter):
    name = "gaia_dr3"
    epoch_jyear = 2016.0
    timeout_s = config.CONTEXT_TIMEOUT_S

    def build_query(self, q: ConeQuery) -> str:
        r, extra = self.wide_radius_deg(q)
        where = _pm_aware_where("ra", "dec", "SQRT(POWER(pmra, 2) + POWER(pmdec, 2))", 1 / 3.6e6,
                                q, r, extra, _dt_years(self.epoch_jyear, q.mjd))
        return (
            "SELECT source_id, ra, dec, pmra, pmdec, parallax, radial_velocity, ref_epoch, "
            "phot_g_mean_mag, phot_bp_mean_mag, phot_rp_mean_mag "
            f"FROM gaiadr3.gaia_source WHERE {where}"
        )

    def run_query(self, adql: str) -> list[dict[str, Any]]:
        from astroquery.gaia import Gaia

        Gaia.ROW_LIMIT = -1
        return table_rows(Gaia.launch_job(adql).get_results())

    def parse(self, rows: list[dict[str, Any]]) -> list[CatalogSource]:
        out = []
        for r in rows:
            if r.get("ra") is None:
                continue
            mags = {k: float(r[c]) for k, c in (("G", "phot_g_mean_mag"), ("BP", "phot_bp_mean_mag"),
                                                  ("RP", "phot_rp_mean_mag")) if r.get(c) is not None}
            sid = str(r["source_id"])
            out.append(CatalogSource(
                catalog=self.name, id=sid, ra=float(r["ra"]), dec=float(r["dec"]),
                epoch_jyear=float(r.get("ref_epoch") or self.epoch_jyear),
                pm_ra_cosdec=_f(r.get("pmra")), pm_dec=_f(r.get("pmdec")), parallax=_f(r.get("parallax")),
                rv=_f(r.get("radial_velocity")), name=f"Gaia DR3 {sid}", mags=mags,
            ))
        return out


# --------------------------------------------------------------------------- #
# CatWISE2020 (IRSA; ra_pm/dec_pm at MJD 57170 = 2015.405; pm in arcsec/yr)
# --------------------------------------------------------------------------- #


class CatWiseAdapter(CatalogAdapter):
    name = "catwise2020"
    epoch_jyear = 2015.405  # VERIFIED: ra_pm/dec_pm "at epoch MJD=57170 (2015.405)"
    timeout_s = config.CONTEXT_TIMEOUT_S

    def build_query(self, q: ConeQuery) -> str:
        r, extra = self.wide_radius_deg(q)
        # Spatial index is on ra/dec (stationary fit); a plain cone on ra_pm/dec_pm timed out
        # (> 90 s). ra/dec differ from ra_pm/dec_pm by at most |pm| × a few years, covered by
        # the fast-mover widening plus 10" slack.
        where = _pm_aware_where("ra_pm", "dec_pm", "SQRT(POWER(pmra, 2) + POWER(pmdec, 2))", 1 / 3600.0,
                                q, r, extra, _dt_years(self.epoch_jyear, q.mjd),
                                index_cols=("ra", "dec"), index_slack_deg=10 / 3600)
        return (
            "SELECT source_name, ra_pm, dec_pm, pmra, pmdec, sigpmra, sigpmdec, par_pm, "
            "w1mpro_pm, w2mpro_pm, w1sigmpro_pm, w2sigmpro_pm, ab_flags, cc_flags "
            f"FROM catwise_2020 WHERE {where}"
        )

    def run_query(self, adql: str) -> list[dict[str, Any]]:
        return tap_rows(config.IRSA_TAP_URL, adql, self.timeout_s * 0.9)

    def parse(self, rows: list[dict[str, Any]]) -> list[CatalogSource]:
        out = []
        for r in rows:
            if r.get("ra_pm") is None:
                continue
            mags = {k: float(r[c]) for k, c in (("W1", "w1mpro_pm"), ("W2", "w2mpro_pm")) if r.get(c) is not None}
            pmra, pmdec = _f(r.get("pmra")), _f(r.get("pmdec"))
            out.append(CatalogSource(
                catalog=self.name, id=str(r["source_name"]).strip(), ra=float(r["ra_pm"]), dec=float(r["dec_pm"]),
                epoch_jyear=self.epoch_jyear,
                # arcsec/yr → mas/yr. CatWISE motions are relative and noisy for faint sources;
                # parallax is not used for propagation (par_pm is a rough estimate).
                pm_ra_cosdec=pmra * 1000 if pmra is not None else None,
                pm_dec=pmdec * 1000 if pmdec is not None else None,
                name=f"CWISE {str(r['source_name']).strip()}", mags=mags,
            ))
        return out


def _f(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None


def default_adapters(cache=None) -> list[CatalogAdapter]:
    return [SimbadAdapter(cache), GaiaAdapter(cache), CatWiseAdapter(cache)]
