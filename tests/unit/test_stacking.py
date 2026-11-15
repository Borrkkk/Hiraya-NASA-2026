import math

import numpy as np
import pytest
from astropy.wcs import WCS

from spherex_inspect import config
from spherex_inspect.context.match import explain_transients
from spherex_inspect.measurement import measure
from spherex_inspect.models import (
    DifferenceFrame,
    FrameMeasurement,
    KnownBody,
    PointSummary,
    QualitySummary,
)
from spherex_inspect.stacking import stack_and_difference

from .test_measurement import C, DEC0, N, OMEGA_SR, RA0, SCALE, frame, synthetic, target


def shifted(i, stars=(), dx=0.0, dy=0.0, noise=0.01, det=2, extra=()):
    """A frame whose pointing differs by (dx, dy) px: stars given in SKY-fixed pixel coords
    of the reference frame are moved accordingly, and CRPIX is moved with them."""
    cut = synthetic(stars=[(x + dx, y + dy, f) for x, y, f in list(stars) + list(extra)], noise=noise, seed=i)
    cut.header["CRPIX1"] += dx
    cut.header["CRPIX2"] += dy
    f = frame()
    cut.frame = f.model_copy(update={"frame_id": f"o{i}D{det}", "obs_id": f"o{i}", "detector": det, "t_mid": 61000.0 + i})
    return cut


def test_stack_aligns_shifted_frames_and_gains_snr():
    star = [(C, C, 0.6)]  # faint: per-frame SNR ~ a few
    offsets = [(0, 0), (1.3, -0.7), (-0.9, 1.6), (2.2, 0.4), (-1.5, -1.8), (0.6, 2.1), (1.8, 1.1), (-2.0, 0.3), (0.2, -1.2)]
    cuts = [shifted(i, star, dx, dy) for i, (dx, dy) in enumerate(offsets)]
    ms = [measure(c, target()) for c in cuts]
    stacked, _ = stack_and_difference(cuts, target(), ms)
    [s] = stacked
    assert s.n_frames == 9 and s.detected and s.note is None
    assert s.offset_from_target_arcsec < 0.5 * SCALE  # aligned on the sky
    frame_snr = np.median([m.snr for m in ms])
    assert s.snr > 2.0 * frame_snr  # ~√9 = 3× ideally; interpolation smooths a little
    assert s.flux_jy == pytest.approx(0.6 * OMEGA_SR * 1e6, rel=0.15)
    assert s.median_frame_snr == pytest.approx(frame_snr)


def test_difference_flags_the_frame_with_a_mover():
    star = [(C, C, 5.0)]
    cuts = [shifted(i, star, *(0.5 * (i % 3), -0.4 * (i % 2))) for i in range(8)]
    # an asteroid crossing the cutout in frame 5 only, 5 px from the target
    cuts[5] = shifted(5, star, 1.0, 0.0, extra=[(C + 5, C - 3, 20.0)])
    _, diffs = stack_and_difference(cuts, target(), [measure(c, target()) for c in cuts])
    flagged = [d for d in diffs if d.transient]
    assert [d.frame_id for d in flagged] == ["o5D2"]
    d = flagged[0]
    assert d.peak_sep_from_target_arcsec == pytest.approx(math.hypot(5, 3) * SCALE, abs=1.5 * SCALE)
    # the static star (with λ-dependent residuals) is not a transient anywhere else
    assert all(x.peak_snr < config.DIFF_SNR for x in diffs if x.frame_id != "o5D2")


def test_saturated_detector_not_stacked():
    cuts = [shifted(i, [(C, C, 50.0)]) for i in range(4)]
    ms = [FrameMeasurement(frame_id=c.frame.frame_id, obs_id=c.frame.obs_id, detector=2, t_mid=c.frame.t_mid,
                           detected=True, flag_names=["OVERFLOW"]) for c in cuts]
    stacked, _ = stack_and_difference(cuts, target(), ms)
    assert stacked[0].flux_jy is None and "saturated" in stacked[0].note


def test_too_few_frames():
    cuts = [shifted(i, [(C, C, 1.0)]) for i in range(2)]
    stacked, diffs = stack_and_difference(cuts, target(), None)
    assert stacked == [] and diffs == []


def test_explain_transients():
    def tr(fid, ra, dec):
        return DifferenceFrame(frame_id=fid, detector=3, t_mid=61000.0, peak_snr=20.0, peak_ra=ra, peak_dec=dec, transient=True)

    s = PointSummary(quality=QualitySummary(n_frames=3, n_usable=0), difference=[
        tr("F1", RA0, DEC0 + 15 / 3600),  # 15″ from an asteroid (saturated: wing peak)
        tr("F2", RA0 + 20 / 3600, DEC0),  # 20″ from a bright star
        tr("F3", RA0 - 40 / 3600, DEC0),  # nothing near
        DifferenceFrame(frame_id="F4", detector=3, t_mid=61000.0, peak_snr=3.0, peak_ra=RA0, peak_dec=DEC0),
    ])
    vesta = KnownBody(name="4 Vesta", object_class="asteroid", ra_at_t=RA0, dec_at_t=DEC0, t_ref=61000, is_solar_system=True)
    bright = KnownBody(name="HD 1", ra_at_t=RA0 + 25 / 3600 / math.cos(math.radians(DEC0)), dec_at_t=DEC0, t_ref=61000,
                       mags={"G": 7.0})
    faint = KnownBody(name="faint", ra_at_t=RA0 - 30 / 3600, dec_at_t=DEC0, t_ref=61000, mags={"G": 18.0})
    out = {m.frame_id: m for m in explain_transients(s, [bright, faint], {"F1": [vesta]})}
    assert set(out) == {"F1", "F2", "F3"}  # F4 is not a transient
    assert out["F1"].kind == "solar_system" and out["F1"].explained_by == "4 Vesta"
    assert out["F2"].kind == "known_star" and out["F2"].explained_by == "HD 1"
    assert out["F3"].kind == "unexplained"  # the faint star is 10″+ away: outside its 9″ radius
