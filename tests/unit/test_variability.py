import math

import numpy as np
import pytest

from spherex_inspect import config
from spherex_inspect.aggregation import aggregate, detector_variability
from spherex_inspect.context.match import assess_candidate
from spherex_inspect.models import (
    FrameMeasurement,
    LightCurveSample,
    PointSummary,
    PositionSample,
    ProperMotion,
    QualitySummary,
)


def lc(n=20, det=1, slope=3.0, var_amp=0.0, snr=200, seed=0, lam=(0.75, 1.1)):
    """Light curve in one detector: each epoch samples a random λ in the band; the spectrum
    slopes steeply (flux ∝ λ^slope) and the star optionally varies sinusoidally in time."""
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        t = 60900 + i * 20.0
        l = rng.uniform(*lam)
        f0 = 1.0 * (l / lam[0]) ** slope * (1 + var_amp * math.sin(2 * math.pi * t / 150))
        err = f0 / snr
        out.append(LightCurveSample(t_mid=t, detector=det, wavelength_um=l, flux=f0 + rng.normal(0, err), err=err,
                                    frame_id=f"f{i}"))
    return out


@pytest.mark.parametrize("seed", range(5))
def test_constant_star_with_steep_spectrum_not_variable(seed):
    v = detector_variability(1, lc(slope=3.0, seed=seed))
    assert not v.variable and v.reduced_chi2 < 3 and v.basis == "usable"
    assert v.amplitude < 1.1


def test_constant_model_would_flag_spectral_slope():
    """Why the model is a spectrum in λ: with degree 0 (the brief's constant), a non-variable
    star with a sloped spectrum looks wildly variable."""
    old = config.VAR_POLY_DEGREE
    try:
        config.VAR_POLY_DEGREE = 0
        assert detector_variability(1, lc(slope=3.0)).variable
    finally:
        config.VAR_POLY_DEGREE = old


def test_variable_star_flagged():
    v = detector_variability(1, lc(var_amp=0.3))
    assert v.variable and v.reduced_chi2 > 20 and v.amplitude > 1.5


def test_too_few_samples():
    v = detector_variability(1, lc(n=4))
    assert v.reduced_chi2 is None and not v.variable and v.n == 4


def _meas(samples, usable=True, flags=(), detected=True):
    return [FrameMeasurement(frame_id=s.frame_id, obs_id=s.frame_id, detector=s.detector, t_mid=s.t_mid,
                             wavelength_um=s.wavelength_um, bandwidth_um=0.02, flux_jy=s.flux, flux_err_jy=s.err,
                             detected=detected, usable=usable, flag_names=list(flags)) for s in samples]


def test_saturated_fallback_and_masked_core_note():
    ms = (_meas(lc(det=5, var_amp=0.4, seed=1), usable=False, flags=["OVERFLOW", "BLOOM"])
          + _meas(lc(det=6, seed=2), usable=False, flags=["OVERFLOW", "MASKED_PIXELS"])
          + _meas(lc(det=4, var_amp=0.4, seed=3), usable=False, flags=["OVERFLOW", "GHOST"]))
    s = aggregate(ms)
    by = {v.detector: v for v in s.variability}
    assert by[5].basis == "saturated" and by[5].variable
    assert by[6].reduced_chi2 is None and "masked (NaN) saturated core" in by[6].note  # no wing fit
    assert by[4].reduced_chi2 is None and "artifacts" in by[4].note  # ghosted samples are never used
    assert s.light_curve == []  # the light curve stays clean-only


def test_usable_preferred_over_saturated():
    ms = _meas(lc(det=2, seed=4)) + _meas(lc(det=2, var_amp=0.5, seed=5), usable=False, flags=["OVERFLOW"])
    [v] = aggregate(ms).variability
    assert v.basis == "usable" and not v.variable


def test_saturated_floor_keeps_constant_star_quiet():
    # constant star, saturated, photometry scattered ~5% (worse than its formal errors)
    samples = lc(det=5, seed=6, snr=400)
    rng = np.random.default_rng(7)
    for s in samples:
        s.flux *= 1 + rng.normal(0, 0.05)
    [v] = aggregate(_meas(samples, usable=False, flags=["OVERFLOW"])).variability
    assert v.basis == "saturated" and not v.variable


# ---- candidate discovery gate ------------------------------------------------


def _summary(flag_sets, pm=None):
    ps = [PositionSample(t_mid=61000 + i, ra=10, dec=20, err=0.5, frame_id=f"f{i}", flags=list(f))
          for i, f in enumerate(flag_sets)]
    return PointSummary(positions=ps, first_position=ps[0], latest_position=ps[-1], proper_motion=pm,
                        quality=QualitySummary(n_frames=len(ps), n_usable=len(ps)))


def test_candidate_needs_two_clean_detections():
    cand, n, note = assess_candidate("no_known_match", _summary([[], ["DICHROIC"]]))
    assert cand and n == 2 and "stationary source in 2 artifact-free frames" in note
    pm = ProperMotion(pm_ra_cosdec=500, pm_dec=0, err=50, significance=10)
    assert "moving source" in assess_candidate("no_known_match", _summary([[], [], []], pm=pm))[2]


def test_artifact_flags_block_candidate():
    cand, n, note = assess_candidate("no_known_match", _summary([["TRANSIENT"], [], ["GHOST"]]))
    assert not cand and n == 1 and "only 1 artifact-free frame" in note
    cand, n, note = assess_candidate("no_known_match", _summary([["OUTLIER"], ["PERSIST"]]))
    assert not cand and n == 0 and "likely an artifact" in note


def test_no_candidate_when_matched_or_nothing_detected():
    assert assess_candidate("matched", _summary([[], []])) == (False, None, None)
    empty = PointSummary(quality=QualitySummary(n_frames=3, n_usable=0))
    assert assess_candidate("no_known_match", empty) == (False, None, None)


def test_masked_core_wing_fluxes_feed_variability():
    samples = lc(det=3, var_amp=0.4, seed=8)
    ms = _meas(samples, usable=False, flags=["OVERFLOW", "MASKED_PIXELS"])
    for m in ms:
        m.flux_method = "psf_wings"
    [v] = aggregate(ms).variability
    assert v.basis == "saturated" and v.variable
    # same samples from a truncated aperture (no wing fit) are not used
    for m in ms:
        m.flux_method = "aperture"
    [v2] = aggregate(ms).variability
    assert v2.reduced_chi2 is None and "wing fit failed" in v2.note
