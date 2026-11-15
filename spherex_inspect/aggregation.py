"""[5] Time-Series Aggregation: the only component that looks ACROSS frames.

Pure: list[FrameMeasurement] → PointSummary (spectrum, position track + proper motion,
light curve, quality). No pixels, no catalogs.
"""
from __future__ import annotations

import math
from collections import Counter

import numpy as np

from . import config
from .models import (
    BandVariability,
    BinnedSpectrumSample,
    FrameMeasurement,
    LightCurveSample,
    PointSummary,
    PositionSample,
    ProperMotion,
    QualitySummary,
    SpectrumSample,
)

_DAYS_PER_YEAR = 365.25


# --------------------------------------------------------------------------- #
# Spectrum
# --------------------------------------------------------------------------- #


def _spectrum_sample(m: FrameMeasurement, flags: bool = False) -> SpectrumSample:
    return SpectrumSample(
        wavelength_um=m.wavelength_um, flux=m.flux_jy, err=m.flux_err_jy, frame_id=m.frame_id,
        bandwidth_um=m.bandwidth_um, detector=m.detector, flags=list(m.flag_names) if flags else [],
    )


def build_spectrum(ms: list[FrameMeasurement]) -> tuple[list[SpectrumSample], list[SpectrumSample]]:
    """→ (usable samples, flagged detected samples), each sorted by wavelength.

    Usable includes forced-photometry non-detections: for a faint source they are real
    flux samples. Flagged = detected but flux rejected (e.g. saturated), for display only."""
    good, flagged = [], []
    for m in ms:
        if m.wavelength_um is None or m.flux_jy is None or not m.flux_err_jy:
            continue
        if m.usable:
            good.append(_spectrum_sample(m))
        elif m.detected:
            flagged.append(_spectrum_sample(m, flags=True))
    key = lambda s: s.wavelength_um  # noqa: E731
    return sorted(good, key=key), sorted(flagged, key=key)


def bin_spectrum(samples: list[SpectrumSample], n_bins: int | None = None,
                 lam_range: tuple[float, float] | None = None) -> list[BinnedSpectrumSample]:
    """Equal-width bins in log λ; inverse-variance weighted mean. Empty bins → null
    (gaps are never interpolated)."""
    n_bins = n_bins or config.SPECTRUM_BINS
    lo, hi = lam_range or config.SPECTRUM_RANGE_UM
    edges = np.geomspace(lo, hi, n_bins + 1)
    centres = np.sqrt(edges[:-1] * edges[1:])
    sw = np.zeros(n_bins)
    swf = np.zeros(n_bins)
    n = np.zeros(n_bins, int)
    for s in samples:
        if not (lo <= s.wavelength_um < hi) or s.err <= 0:
            continue
        i = int(np.searchsorted(edges, s.wavelength_um, side="right") - 1)
        w = 1.0 / s.err**2
        sw[i] += w
        swf[i] += w * s.flux
        n[i] += 1
    out = []
    for i in range(n_bins):
        if n[i]:
            out.append(BinnedSpectrumSample(wavelength_um=float(centres[i]), flux=float(swf[i] / sw[i]),
                                            err=float(1 / math.sqrt(sw[i])), n=int(n[i])))
        else:
            out.append(BinnedSpectrumSample(wavelength_um=float(centres[i])))
    return out


# --------------------------------------------------------------------------- #
# Positions / proper motion
# --------------------------------------------------------------------------- #


def _wls_line(t: np.ndarray, y: np.ndarray, w: np.ndarray):
    """Weighted least squares y = a + b t → (a, b, cov 2×2)."""
    A = np.vstack([np.ones_like(t), t]).T
    AtW = A.T * w
    cov = np.linalg.inv(AtW @ A)
    a, b = cov @ (AtW @ y)
    return float(a), float(b), cov


def fit_proper_motion(positions: list[PositionSample]) -> tuple[ProperMotion | None, list[bool]]:
    """Weighted linear fit of tangent-plane offsets vs time, with iterative outlier
    rejection. Errors are scaled by sqrt(reduced χ²) when it exceeds 1.

    Returns (fit or None if < 3 points, used-mask aligned with ``positions``)."""
    n_all = len(positions)
    used = [True] * n_all
    if n_all < 3:
        return None, used
    ra = np.array([p.ra for p in positions])
    dec = np.array([p.dec for p in positions])
    t_mjd = np.array([p.t_mid for p in positions])
    err = np.array([p.err for p in positions])  # arcsec

    ra0, dec0 = float(np.median(ra)), float(np.median(dec))
    cosd = math.cos(math.radians(dec0))
    x = ((ra - ra0 + 180.0) % 360.0 - 180.0) * cosd * 3600.0  # arcsec, east
    y = (dec - dec0) * 3600.0  # arcsec, north
    w_all = 1.0 / err**2
    mask = np.ones(n_all, bool)
    max_reject = int(config.PM_MAX_CLIP_FRACTION * n_all)

    while True:
        t_ref = float(np.average(t_mjd[mask], weights=w_all[mask]))
        t = (t_mjd - t_ref) / _DAYS_PER_YEAR
        ax, bx, covx = _wls_line(t[mask], x[mask], w_all[mask])
        ay, by, covy = _wls_line(t[mask], y[mask], w_all[mask])
        rx, ry = x - (ax + bx * t), y - (ay + by * t)
        chi2 = float(np.sum((rx[mask] ** 2 + ry[mask] ** 2) * w_all[mask]))
        dof = max(2 * int(mask.sum()) - 4, 1)
        rchi2 = chi2 / dof
        scale = math.sqrt(max(rchi2, 1.0))
        norm = np.hypot(rx, ry) / (err * scale)
        norm[~mask] = -np.inf
        worst = int(np.argmax(norm))
        if norm[worst] > config.PM_CLIP_SIGMA and (n_all - mask.sum()) < max_reject and mask.sum() > 3:
            mask[worst] = False
            continue
        break

    pmx, pmy = bx * 1000.0, by * 1000.0  # mas/yr
    sx, sy = math.sqrt(covx[1, 1]) * scale * 1000.0, math.sqrt(covy[1, 1]) * scale * 1000.0
    total = math.hypot(pmx, pmy)
    err_total = math.sqrt((pmx * sx) ** 2 + (pmy * sy) ** 2) / total if total > 0 else math.hypot(sx, sy)
    tm = t_mjd[mask]
    pm = ProperMotion(
        pm_ra_cosdec=pmx, pm_dec=pmy, err=err_total, significance=total / err_total if err_total > 0 else 0.0,
        pm_ra_cosdec_err=sx, pm_dec_err=sy, pm_total=total,
        position_angle_deg=math.degrees(math.atan2(pmx, pmy)) % 360.0,
        baseline_days=float(tm.max() - tm.min()), n_used=int(mask.sum()), n_rejected=int(n_all - mask.sum()),
        reduced_chi2=rchi2, ref_epoch_mjd=t_ref,
    )
    return pm, mask.tolist()


def pm_report_decision(pm: ProperMotion | None) -> str | None:
    """None when the pm passes the brief's thresholds; otherwise the reason it is withheld."""
    if pm is None:
        return "fewer than 3 usable positions"
    if pm.baseline_days < config.PM_MIN_BASELINE_DAYS:
        return f"baseline {pm.baseline_days:.0f} d < {config.PM_MIN_BASELINE_DAYS:.0f} d"
    if pm.n_used < config.PM_MIN_DETECTIONS:
        return f"{pm.n_used} usable detections < {config.PM_MIN_DETECTIONS}"
    if pm.significance < config.PM_MIN_SIGNIFICANCE:
        return f"not significant ({pm.significance:.1f}σ < {config.PM_MIN_SIGNIFICANCE:.0f}σ)"
    return None


# --------------------------------------------------------------------------- #
# Variability
# --------------------------------------------------------------------------- #


def detector_variability(det: int, samples: list[LightCurveSample], floor: float | None = None,
                         basis: str = "usable") -> BandVariability:
    """Within one detector: fit a smooth spectrum (polynomial in λ) to all epochs, then the
    reduced χ² of the residuals measures variability in time. A constant-flux model would
    flag any star whose spectrum slopes across the detector band."""
    floor = config.VAR_FLUX_ERR_FLOOR if floor is None else floor
    pts = [s for s in samples if s.wavelength_um is not None and s.err and s.err > 0]
    n = len(pts)
    if n < config.VAR_MIN_SAMPLES:
        return BandVariability(detector=det, n=n)
    lam = np.array([s.wavelength_um for s in pts])
    f = np.array([s.flux for s in pts])
    e = np.array([s.err for s in pts])
    deg = min(config.VAR_POLY_DEGREE, max(n - 4, 0))  # keep ≥ 3 degrees of freedom
    x = lam - lam.mean()
    model = np.full(n, float(np.average(f, weights=1 / e**2)))
    for _ in range(2):  # refit once with the floor based on the model flux
        sig = np.sqrt(e**2 + (floor * np.abs(model)) ** 2)
        coef = np.polyfit(x, f, deg, w=1 / sig) if deg > 0 else [np.average(f, weights=1 / sig**2)]
        model = np.polyval(coef, x)
    sig = np.sqrt(e**2 + (floor * np.abs(model)) ** 2)
    rchi2 = float(np.sum(((f - model) / sig) ** 2) / (n - deg - 1))
    # Amplitude only means something when the source is clearly above zero everywhere.
    amp = None
    if np.all(model > 3 * e):
        ratio = f / model
        ratio = ratio[np.isfinite(ratio) & (ratio > 0)]
        amp = float(np.max(ratio) / np.min(ratio)) if len(ratio) >= 2 else None
    return BandVariability(detector=det, n=n, reduced_chi2=rchi2, amplitude=amp,
                           variable=bool(rchi2 >= config.VAR_CHI2_THRESHOLD), basis=basis)


def _saturated_only(m: FrameMeasurement) -> bool:
    """Detected, flux rejected only because of saturation, and none of the flags that also
    spoil the position (ghosts, persistence, streaks...). A masked (NaN) core is acceptable
    only when the flux came from the ePSF wing fit, not from the (truncated) aperture."""
    names = set(m.flag_names)
    masked_ok = "MASKED_PIXELS" not in names or m.flux_method == "psf_wings"
    return (m.detected and not m.usable and m.flux_jy is not None and m.flux_jy > 0 and bool(m.flux_err_jy)
            and bool(names & config.FLAGS_SATURATION) and masked_ok
            and not (names & config.FLAGS_POSITION_UNUSABLE))


def variability(ms: list[FrameMeasurement], light_curve: list[LightCurveSample]) -> list[BandVariability]:
    """Per detector: clean (usable) photometry when there are enough samples, else saturated
    photometry with a larger error floor; otherwise say why nothing could be measured."""
    usable: dict[int, list[LightCurveSample]] = {}
    for s in light_curve:
        usable.setdefault(s.detector, []).append(s)
    saturated: dict[int, list[LightCurveSample]] = {}
    masked: dict[int, int] = {}
    for m in ms:
        if _saturated_only(m):
            saturated.setdefault(m.detector, []).append(LightCurveSample(
                t_mid=m.t_mid, detector=m.detector, wavelength_um=m.wavelength_um, flux=m.flux_jy,
                err=m.flux_err_jy, frame_id=m.frame_id))
        elif m.detected and "MASKED_PIXELS" in m.flag_names and m.flux_method != "psf_wings":
            masked[m.detector] = masked.get(m.detector, 0) + 1
    detected = {m.detector for m in ms if m.detected}
    out = []
    for d in sorted(set(usable) | set(saturated) | set(masked) | detected):
        if len(usable.get(d, [])) >= config.VAR_MIN_SAMPLES:
            out.append(detector_variability(d, usable[d]))
        elif len(saturated.get(d, [])) >= config.VAR_MIN_SAMPLES:
            out.append(detector_variability(d, saturated[d], floor=config.VAR_SATURATED_ERR_FLOOR, basis="saturated"))
        else:
            n_u, n_s, n_m = len(usable.get(d, [])), len(saturated.get(d, [])), masked.get(d, 0)
            why = f"too few samples ({n_u} clean, {n_s} saturated; need {config.VAR_MIN_SAMPLES})"
            if n_m:
                why += f"; {n_m} detections have a masked (NaN) saturated core and the ePSF wing fit failed"
            elif not n_u and not n_s:
                why += "; detections are flagged by artifacts (ghost, persistence, streak...)"
            out.append(BandVariability(detector=d, n=n_u + n_s, note=why))
    return out


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def aggregate(ms: list[FrameMeasurement]) -> PointSummary:
    spectrum, flagged = build_spectrum(ms)

    positions = [
        PositionSample(t_mid=m.t_mid, ra=m.ra_meas, dec=m.dec_meas, err=m.pos_err_arcsec,
                       frame_id=m.frame_id, detector=m.detector, flags=list(m.flag_names))
        for m in sorted(ms, key=lambda m: m.t_mid)
        if m.position_usable and m.ra_meas is not None and m.pos_err_arcsec
    ]
    fit, used = fit_proper_motion(positions)
    for p, u in zip(positions, used):
        p.used_in_fit = u
    note = pm_report_decision(fit)
    in_fit = [p for p in positions if p.used_in_fit]

    light_curve = [
        LightCurveSample(t_mid=m.t_mid, detector=m.detector, wavelength_um=m.wavelength_um,
                         flux=m.flux_jy, err=m.flux_err_jy, frame_id=m.frame_id)
        for m in sorted(ms, key=lambda m: m.t_mid)
        if m.usable and m.flux_jy is not None and m.flux_err_jy
    ]

    flag_counts = Counter(n for m in ms for n in m.flag_names)
    quality = QualitySummary(
        n_frames=len(ms),
        n_usable=sum(m.usable for m in ms),
        n_detected=sum(m.detected for m in ms),
        n_position_usable=len(positions),
        n_failed=sum(1 for m in ms if m.note and m.note.startswith("cutout failed")),
        flag_summary=dict(sorted(flag_counts.items())),
    )

    return PointSummary(
        spectrum=spectrum,
        spectrum_flagged=flagged,
        spectrum_binned=bin_spectrum(spectrum),
        positions=positions,
        first_position=in_fit[0] if in_fit else None,
        latest_position=in_fit[-1] if in_fit else None,
        proper_motion=fit if note is None else None,
        proper_motion_fit=fit,
        proper_motion_note=note,
        light_curve=light_curve,
        variability=variability(ms, light_curve),
        quality=quality,
    )
