import math

import numpy as np
import pytest

from spherex_inspect.aggregation import aggregate, bin_spectrum, fit_proper_motion
from spherex_inspect.models import FrameMeasurement, PositionSample, SpectrumSample

RA0, DEC0 = 269.446, 4.768
COSD = math.cos(math.radians(DEC0))


def track(pm_ra=0.0, pm_dec=0.0, n=40, days=400.0, err=1.0, seed=1, t0=60900.0):
    """Synthetic positions: pm in mas/yr, Gaussian noise `err` arcsec per axis."""
    rng = np.random.default_rng(seed)
    t = np.sort(rng.uniform(t0, t0 + days, n))
    out = []
    for i, ti in enumerate(t):
        yr = (ti - t0) / 365.25
        dx = pm_ra / 1000 * yr + rng.normal(0, err)
        dy = pm_dec / 1000 * yr + rng.normal(0, err)
        out.append(PositionSample(t_mid=float(ti), ra=RA0 + dx / 3600 / COSD, dec=DEC0 + dy / 3600, err=err,
                                  frame_id=f"f{i}", detector=i % 6 + 1))
    return out


def meas_from_positions(ps, **kw):
    return [FrameMeasurement(frame_id=p.frame_id, obs_id=p.frame_id, detector=p.detector, t_mid=p.t_mid,
                             detected=True, position_usable=True, ra_meas=p.ra, dec_meas=p.dec,
                             pos_err_arcsec=p.err, **kw) for p in ps]


def test_recovers_barnard_like_pm():
    pm, used = fit_proper_motion(track(-801.6, 10362.4, err=1.5))
    assert pm.pm_ra_cosdec == pytest.approx(-801.6, abs=4 * pm.pm_ra_cosdec_err)
    assert pm.pm_dec == pytest.approx(10362.4, abs=4 * pm.pm_dec_err)
    assert pm.significance > 8 and all(used)  # ~13σ expected: 1.5″ errors, 40 pts, 0.3 yr rms span
    pa_tol = 3 * math.degrees(pm.pm_ra_cosdec_err / pm.pm_total)
    assert pm.position_angle_deg == pytest.approx(math.degrees(math.atan2(-801.6, 10362.4)) % 360, abs=pa_tol)
    assert 0.5 < pm.reduced_chi2 < 1.6


def test_ra_wrap_near_zero():
    ps = track(500, 0, err=0.3)
    for p in ps:
        p.ra = (p.ra - RA0 + 359.9999) % 360  # straddle RA = 0
    pm, _ = fit_proper_motion(ps)
    assert pm.pm_ra_cosdec * COSD / math.cos(math.radians(DEC0)) == pytest.approx(500, abs=4 * pm.pm_ra_cosdec_err)


@pytest.mark.parametrize("seed", range(10))
def test_no_false_pm_on_constant_track(seed):
    s = aggregate(meas_from_positions(track(0, 0, err=1.5, seed=seed)))
    assert s.proper_motion is None
    assert "not significant" in s.proper_motion_note
    assert s.proper_motion_fit is not None


def test_outlier_rejected():
    ps = track(0, 3000, err=0.5, n=30)
    ps[10].dec += 30 / 3600  # a 30" glitch (e.g. a neighbour picked up)
    pm, used = fit_proper_motion(ps)
    assert not used[10] and sum(used) == 29
    assert pm.pm_dec == pytest.approx(3000, abs=4 * pm.pm_dec_err)


def test_clip_fraction_capped():
    ps = track(0, 0, err=0.5, n=10)
    for p in ps[:6]:
        p.dec += 50 / 3600
    _, used = fit_proper_motion(ps)
    assert used.count(False) <= 2  # at most 20%


def test_errors_inflated_when_underestimated():
    honest, _ = fit_proper_motion(track(0, 5000, err=2.0, seed=3))
    ps = track(0, 5000, err=2.0, seed=3)
    for p in ps:
        p.err = 0.3  # claim 0.3" while true scatter is 2"
    over, _ = fit_proper_motion(ps)
    assert over.reduced_chi2 > 20
    assert over.pm_dec_err == pytest.approx(honest.pm_dec_err, rel=0.3)


@pytest.mark.parametrize(
    "kw,reason",
    [({"days": 100}, "baseline"), ({"n": 5}, "usable detections")],
)
def test_pm_withheld_below_thresholds(kw, reason):
    s = aggregate(meas_from_positions(track(0, 10000, err=0.5, **kw)))
    assert s.proper_motion is None and reason in s.proper_motion_note


def test_first_latest_and_positions():
    ps = track(0, 10000, err=0.5, n=12)
    ms = meas_from_positions(ps)
    ms.append(FrameMeasurement(frame_id="x", obs_id="x", detector=1, t_mid=60000.0, detected=True,
                               position_usable=False, ra_meas=RA0, dec_meas=DEC0, pos_err_arcsec=1))
    s = aggregate(ms)
    assert len(s.positions) == 12  # position-unusable excluded
    assert s.first_position.t_mid == min(p.t_mid for p in ps)
    assert s.latest_position.t_mid == max(p.t_mid for p in ps)
    assert s.latest_position.dec > s.first_position.dec  # moved north
    assert s.proper_motion is not None and s.proper_motion.significance > 3


def _m(i, lam, flux, err=0.1, usable=True, detected=True, flags=()):
    return FrameMeasurement(frame_id=f"f{i}", obs_id=f"f{i}", detector=1, t_mid=61000.0 + i,
                            wavelength_um=lam, bandwidth_um=0.02, flux_jy=flux, flux_err_jy=err,
                            usable=usable, detected=detected, flag_names=list(flags))


def test_spectrum_split_and_sorted():
    ms = [_m(0, 2.0, 1.0), _m(1, 1.0, 2.0), _m(2, 3.0, 9.0, usable=False, flags=["OVERFLOW"]),
          _m(3, 4.0, 0.01, detected=False),  # forced photometry non-detection, still usable
          _m(4, 4.5, 5.0, usable=False, detected=False)]  # undetected AND unusable: dropped
    s = aggregate(ms)
    assert [x.wavelength_um for x in s.spectrum] == [1.0, 2.0, 4.0]
    assert [x.frame_id for x in s.spectrum_flagged] == ["f2"] and s.spectrum_flagged[0].flags == ["OVERFLOW"]
    assert s.spectrum[0].flags == []
    assert s.quality.n_frames == 5 and s.quality.n_usable == 3 and s.quality.flag_summary == {"OVERFLOW": 1}
    assert [lc.frame_id for lc in s.light_curve] == ["f0", "f1", "f3"]


def test_binning_inverse_variance_and_gaps():
    samples = [SpectrumSample(wavelength_um=1.0, flux=1.0, err=1.0, frame_id="a"),
               SpectrumSample(wavelength_um=1.0001, flux=4.0, err=0.5, frame_id="b"),
               SpectrumSample(wavelength_um=6.0, flux=1.0, err=1.0, frame_id="out_of_range")]
    b = bin_spectrum(samples)
    assert len(b) == 102
    full = [x for x in b if x.n]
    assert len(full) == 1
    assert full[0].flux == pytest.approx((1 * 1 + 4 * 4) / (1 + 4))  # weights 1/err²
    assert full[0].err == pytest.approx(1 / math.sqrt(5))
    assert all(x.flux is None and x.err is None for x in b if not x.n)  # gaps stay null
    lams = [x.wavelength_um for x in b]
    assert lams == sorted(lams) and 0.75 < lams[0] < lams[-1] < 5.0
    ratios = np.diff(np.log(lams))
    assert np.allclose(ratios, ratios[0])  # equal width in log λ


def test_empty_input():
    s = aggregate([])
    assert s.spectrum == [] and s.positions == [] and s.proper_motion is None
    assert s.quality.n_frames == 0 and len(s.spectrum_binned) == 102
