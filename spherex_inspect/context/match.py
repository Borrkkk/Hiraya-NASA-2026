"""Group catalog sources into known bodies, score them against the measured source, decide.

Pure: no network. Catalog rows come from the adapters; the measured source from PointSummary.
"""
from __future__ import annotations

import math
from statistics import median

from .. import config
from ..models import BestMatch, KnownBody, PointSummary
from .base import CatalogSource

_CATALOG_PRIORITY = {"gaia_dr3": 0, "simbad": 1, "catwise2020": 2}  # astrometry quality

_VARIABLE = {
    "V*", "V*?", "Mi*", "Mi?", "LP*", "LP?", "RR*", "RR?", "Ce*", "Ce?", "cC*", "EB*", "EB?", "Pu*", "Ir*",
    "Or*", "TT*", "TT?", "RS*", "RS?", "BY*", "BY?", "Er*", "Ro*", "gD*", "dS*", "SX*", "a2*", "El*", "RV*",
    "WV*", "bC*", "sv*", "Fl*", "No*", "No?", "CV*", "CV?", "DN*", "NL*", "Ae*", "Ae?", "BE*", "WR*", "LXB",
    "HXB", "XB*", "S*?", "Y*O", "Y*?",
}
_BROWN_DWARF = {"BD*", "BD?"}
_GALAXY = {
    "G", "G?", "GiC", "GiG", "GiP", "BiC", "IG", "PaG", "SBG", "SyG", "Sy1", "Sy2", "AGN", "AG?", "LIN",
    "EmG", "rG", "H2G", "LSB", "bCG", "GrG", "CGG", "ClG", "PCG", "LeG", "LeI",
}
_QSO = {"QSO", "Q?", "Bla", "Bz?", "BLL", "BL?", "OVV"}


def object_class(otype: str | None, mags: dict[str, float], pm_total: float | None) -> str:
    """SIMBAD otype → object_class. Without a SIMBAD type: brown_dwarf if W1−W2 ≥ 1.0 and
    |pm| ≥ 200 mas/yr (brief §6), else unknown."""
    if otype:
        if otype in _BROWN_DWARF:
            return "brown_dwarf"
        if otype in _VARIABLE:
            return "variable_star"
        if otype in _GALAXY:
            return "galaxy"
        if otype in _QSO:
            return "qso"
        if otype.endswith("*") or otype.endswith("*?") or otype in {"*", "**", "PM*", "HS*", "LM*", "MS*"}:
            return "star"
        return "unknown"
    if "W1" in mags and "W2" in mags and mags["W1"] - mags["W2"] >= 1.0 and (pm_total or 0) >= 200:
        return "brown_dwarf"
    return "unknown"


def sep_arcsec(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    r1, d1, r2, d2 = map(math.radians, (ra1, dec1, ra2, dec2))
    s = math.sin((d2 - d1) / 2) ** 2 + math.cos(d1) * math.cos(d2) * math.sin((r2 - r1) / 2) ** 2
    return math.degrees(2 * math.asin(min(1.0, math.sqrt(s)))) * 3600.0


# --------------------------------------------------------------------------- #
# Grouping
# --------------------------------------------------------------------------- #


def group_sources(sources: list[CatalogSource], t_mjd: float, centre: tuple[float, float],
                  radius_arcsec: float) -> list[KnownBody]:
    """Propagate every source to ``t_mjd``, merge sources within the group radius (same
    object in several catalogs), keep bodies inside ``radius_arcsec`` of ``centre``."""
    pos = [s.position_at(t_mjd) for s in sources]
    parent = list(range(len(sources)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    # O(n²) is fine: a few hundred rows at most per cone.
    for i in range(len(sources)):
        for j in range(i + 1, len(sources)):
            if sources[i].catalog == sources[j].catalog:
                continue  # never merge two rows of the same catalog
            if sep_arcsec(*pos[i], *pos[j]) <= config.MATCH_GROUP_RADIUS_ARCSEC:
                parent[find(i)] = find(j)

    groups: dict[int, list[int]] = {}
    for i in range(len(sources)):
        groups.setdefault(find(i), []).append(i)

    bodies = []
    for idx in groups.values():
        members = sorted(idx, key=lambda i: _CATALOG_PRIORITY.get(sources[i].catalog, 9))
        astro = sources[members[0]]
        ra_t, dec_t = pos[members[0]]
        simbad = next((sources[i] for i in members if sources[i].catalog == "simbad"), None)
        name = simbad.name if simbad and simbad.name else astro.name or astro.id
        pm_src = next((sources[i] for i in members if sources[i].pm_ra_cosdec is not None), None)
        pm = (pm_src.pm_ra_cosdec, pm_src.pm_dec) if pm_src else None
        mags: dict[str, float] = {}
        for i in members:
            for k, v in sources[i].mags.items():
                mags.setdefault(k, v)
        sep_c = sep_arcsec(ra_t, dec_t, *centre)
        if sep_c > radius_arcsec:
            continue
        bodies.append(KnownBody(
            name=name,
            object_class=object_class(simbad.otype if simbad else None, mags, math.hypot(*pm) if pm else None),
            source_catalogs=sorted({sources[i].catalog for i in members}, key=lambda c: _CATALOG_PRIORITY.get(c, 9)),
            ra_at_t=ra_t, dec_at_t=dec_t, t_ref=t_mjd, separation_arcsec=sep_c, pm=pm, mags=mags,
            is_solar_system=False,
            ids={sources[i].catalog: sources[i].id for i in members} | ({"simbad_otype": simbad.otype} if simbad and simbad.otype else {}),
        ))
    return sorted(bodies, key=lambda b: b.separation_arcsec)


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #


def score_body(body: KnownBody, summary: PointSummary) -> tuple[float, dict[str, float]]:
    """Weighted mean of the available terms (position always; pm and IR only when usable),
    renormalised over the weights actually used."""
    lp = summary.latest_position
    terms: dict[str, float] = {}
    sigma = math.hypot(config.MATCH_SIGMA_PSF_ARCSEC, lp.err)
    terms["position"] = math.exp(-0.5 * (body.separation_arcsec / sigma) ** 2)

    pm = summary.proper_motion
    if pm is not None and pm.significance >= config.MATCH_PM_MIN_SIGNIFICANCE:
        bpm = body.pm or (0.0, 0.0)
        d = math.hypot(pm.pm_ra_cosdec - bpm[0], pm.pm_dec - bpm[1])
        # Tolerant on purpose: SPHEREx pm has ~10% systematics on saturated stars (NOTES step 4).
        s = math.hypot(pm.err, 0.1 * (pm.pm_total or 0.0), 50.0)
        terms["pm"] = math.exp(-0.5 * (d / s) ** 2)

    ir = []
    for band, (lam0, zp) in config.IR_BANDS.items():
        if band not in body.mags:
            continue
        near = [s.flux for s in summary.spectrum
                if abs(s.wavelength_um - lam0) <= config.MATCH_IR_WINDOW_UM and s.flux > 0]
        if not near:
            continue
        cat_jy = zp * 10 ** (-0.4 * body.mags[band])
        dm = -2.5 * math.log10(median(near) / cat_jy)
        ir.append(math.exp(-0.5 * (dm / config.MATCH_IR_SIGMA_MAG) ** 2))
    if ir:
        terms["ir"] = sum(ir) / len(ir)

    w = config.MATCH_WEIGHTS
    total_w = sum(w[k] for k in terms)
    return sum(w[k] * v for k, v in terms.items()) / total_w, terms


def brightness_veto(body: KnownBody, summary: PointSummary) -> str | None:
    """Return a reason when the body is far too faint (same-λ comparison) to be the measured
    source; None otherwise. Saturated (flagged) samples count as lower bounds."""
    samples = [(s.wavelength_um, s.flux) for s in summary.spectrum if s.flux > 0]
    samples += [(s.wavelength_um, s.flux) for s in summary.spectrum_flagged
                if s.flux > 0 and set(s.flags) & config.FLAGS_SATURATION]
    if not samples:
        return None
    for band, (lam0, zp) in config.VETO_BANDS.items():
        if band not in body.mags:
            continue
        near = [f for lam, f in samples if abs(lam - lam0) <= config.MATCH_IR_WINDOW_UM]
        if not near:
            continue
        cat = zp * 10 ** (-0.4 * body.mags[band])
        meas = median(near)
        if meas / cat > config.MATCH_BRIGHTNESS_VETO_RATIO:
            return f"{band}={body.mags[band]:.1f} gives {cat:.2g} Jy, SPHEREx measured ≥ {meas:.2g} Jy"
    return None


def decide(bodies: list[KnownBody], summary: PointSummary | None):
    """→ (best_match | None, verdict, note). Bodies must already be propagated to the
    latest position's time and carry separations from the measured source."""
    if summary is None or summary.latest_position is None:
        return None, "no_known_match", "no measured source to identify (nothing detected, or a context-only lookup)"
    if not bodies:
        return None, "no_known_match", "no catalog source near the measured position: candidate discovery"
    scored = sorted(((0.0 if brightness_veto(b, summary) else score_body(b, summary)[0], b) for b in bodies),
                    key=lambda x: -x[0])
    top, best = scored[0]
    runner = scored[1][0] if len(scored) > 1 else 0.0
    # Bodies vetoed on brightness cannot blend with the source either.
    close = [b for b in bodies if b.separation_arcsec <= config.MATCH_AMBIGUOUS_RADIUS_ARCSEC
             and not brightness_veto(b, summary)]
    if top >= config.MATCH_MIN_SCORE and top - runner >= config.MATCH_MIN_MARGIN:
        return BestMatch(**best.model_dump(), match_score=round(top, 4)), "matched", None
    if len(close) >= 2:
        return (BestMatch(**best.model_dump(), match_score=round(top, 4)), "ambiguous",
                f"{len(close)} known bodies within {config.MATCH_AMBIGUOUS_RADIUS_ARCSEC:g}\" (one SPHEREx PSF)")
    return None, "no_known_match", (f"best candidate {best.name} scored {top:.2f}; "
                                    "no catalog source explains the measured source: candidate discovery")


def assess_candidate(verdict: str, summary: PointSummary | None) -> tuple[bool, int | None, str | None]:
    """→ (candidate_discovery, n_clean_detections, note suffix). Only for no_known_match with a
    measured source; 'clean' = position-usable detection without artifact flags."""
    if verdict != "no_known_match" or summary is None or summary.latest_position is None:
        return False, None, None
    clean = [p for p in summary.positions
             if p.used_in_fit and not (set(p.flags) & config.CANDIDATE_BLOCKING_FLAGS)]
    n = len(clean)
    if n >= config.CANDIDATE_MIN_CLEAN_DETECTIONS:
        moving = summary.proper_motion is not None
        kind = "moving" if moving else "stationary"
        return True, n, f"{kind} source in {n} artifact-free frames with no known counterpart: candidate discovery"
    if n == 1:
        return False, n, ("seen in only 1 artifact-free frame: an artifact (cosmic ray, ghost) or an "
                          "untracked mover is more likely than a new object")
    return False, n, "no artifact-free detection: likely an artifact, not a discovery"
