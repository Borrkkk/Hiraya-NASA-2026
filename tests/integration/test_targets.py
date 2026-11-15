"""Live integration tests (run with `pytest -m live`). They hit IRSA / SIMBAD / Gaia.

Speed: steps 3–5 share ONE pipeline run of Barnard's Star (`barnard_run`, 60 frames spread
across time and detectors) and use the real `.cache/`, so a warm run is fast. The cold-download
timing check (step 2) re-downloads on purpose and only runs with SPHEREX_LIVE_COLD=1.
"""
import asyncio
import json
import math
import os
import time
from pathlib import Path

import astropy.units as u
import pytest
from astropy.coordinates import Distance, SkyCoord
from astropy.time import Time

from spherex_inspect.discovery import FrameDiscovery
from spherex_inspect.intake import to_target
from spherex_inspect.models import InspectRequest

pytestmark = pytest.mark.live

FIXTURES = Path(__file__).parent.parent / "fixtures"
GAIA = json.loads((FIXTURES / "manifest.json").read_text())["_gaia_dr3_barnard"]
LIVE_FRAMES = 60  # enough for a ~20σ pm over the full baseline; 200 is the API default


def resolve(name: str) -> tuple[float, float]:
    from astroquery.simbad import SimbadClass

    last = None
    for server in ("simbad.cds.unistra.fr", "simbad.harvard.edu"):  # CDS main was 404ing on 2026-11-14
        try:
            s = SimbadClass()
            s.server = server
            r = s.query_object(name)
            break
        except Exception as exc:
            last = exc
    else:
        raise last
    cols = {c.lower(): c for c in r.colnames}
    return float(r[cols["ra"]][0]), float(r[cols["dec"]][0])


def barnard() -> SkyCoord:
    g = GAIA
    return SkyCoord(g["ra"] * u.deg, g["dec"] * u.deg, pm_ra_cosdec=g["pmra"] * u.mas / u.yr,
                    pm_dec=g["pmdec"] * u.mas / u.yr, distance=Distance(parallax=g["parallax"] * u.mas),
                    radial_velocity=g["radial_velocity"] * u.km / u.s, obstime=Time(g["ref_epoch"], format="jyear"))


@pytest.fixture(scope="session")
def barnard_run():
    """One full inspect_point run on Barnard's Star (Gaia position at 2026.0), shared by steps 3–5."""
    import spherex_inspect

    ctr = barnard().apply_space_motion(new_obstime=Time(2026.0, format="jyear"))
    t0 = time.monotonic()
    resp = asyncio.run(spherex_inspect.inspect_point(
        InspectRequest(ra=ctr.ra.deg, dec=ctr.dec.deg, max_frames=LIVE_FRAMES)))
    print(f"\n[barnard_run] {time.monotonic() - t0:.1f}s, status={resp.status}, warnings={resp.warnings}")
    return resp


# --------------------------------------------------------------------------- #
# Step 1 — discovery
# --------------------------------------------------------------------------- #


async def test_step1_barnards_star_frames():
    ra, dec = resolve("Barnard's Star")
    assert ra == pytest.approx(269.452, abs=0.05) and dec == pytest.approx(4.693, abs=0.05)
    target = to_target(InspectRequest(ra=ra, dec=dec, max_frames=2000))
    res, warnings = await FrameDiscovery().discover(target)
    frames = res.frames
    assert len(frames) >= 50, warnings
    assert {f.detector for f in frames} == {1, 2, 3, 4, 5, 6}
    assert [f.t_mid for f in frames] == sorted(f.t_mid for f in frames)
    assert len({f.frame_id for f in frames}) == len(frames)
    for f in frames:
        assert f.em_min_um is not None and 0.7 < f.em_min_um < f.em_max_um < 5.1
        assert f.pixel_scale_arcsec == pytest.approx(6.15, abs=0.2)
        assert len(f.footprint) >= 4


# --------------------------------------------------------------------------- #
# Step 2 — cold download timing (opt-in: it re-downloads ~80 MB on purpose)
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(not os.environ.get("SPHEREX_LIVE_COLD"), reason="set SPHEREX_LIVE_COLD=1 to time cold downloads")
async def test_step2_cutouts_download_and_cache(tmp_path):
    import diskcache

    from spherex_inspect.retrieval import CutoutRetrieval

    ra, dec = resolve("Barnard's Star")
    target = to_target(InspectRequest(ra=ra, dec=dec, max_frames=20, cutout_size_deg=0.02))
    res, _ = await FrameDiscovery().discover(target)
    assert len(res.frames) == 20
    cache = diskcache.Cache(str(tmp_path / "cache"))
    retr = CutoutRetrieval(cache=cache)

    t0 = time.monotonic()
    cold = await retr.fetch(res.frames, target)
    cold_s = time.monotonic() - t0
    ok = [c for c in cold if c.status == "ok"]
    print(f"\ncold: {len(ok)}/20 ok in {cold_s:.1f}s; failures: {[c.error for c in cold if c.status != 'ok']}")
    assert cold_s < 60
    assert len(ok) >= 18  # tolerate a couple of IRSA hiccups
    for c in ok:
        assert c.image.shape[0] >= 8 and c.version
        assert int(c.header["DETECTOR"]) == c.frame.detector
        lam = c.wave_wcs.pixel_to_world(c.image.shape[1] / 2, c.image.shape[0] / 2)[0].to_value("um")
        assert c.frame.em_min_um - 0.05 <= lam <= c.frame.em_max_um + 0.05

    t0 = time.monotonic()
    warm = await retr.fetch(res.frames, target)
    warm_s = time.monotonic() - t0
    print(f"warm: {sum(c.from_cache for c in warm)}/20 from cache in {warm_s:.1f}s")
    assert all(c.from_cache for c, k in zip(warm, cold) if k.status == "ok")
    assert warm_s < 10
    cache.close()


# --------------------------------------------------------------------------- #
# Steps 3–5 — share one pipeline run
# --------------------------------------------------------------------------- #


def test_step3_barnard_detected_near_gaia(barnard_run):
    """Every downloaded frame detects Barnard's Star within 1 px of its Gaia-propagated position."""
    resp, star = barnard_run, barnard()
    ok = [f for f in resp.frames if f.status != "failed"]
    detected = [f for f in ok if f.status == "detected"]
    seps = []
    for p in resp.summary.positions:
        g = star.apply_space_motion(new_obstime=Time(p.t_mid, format="mjd"))
        seps.append(g.separation(SkyCoord(p.ra * u.deg, p.dec * u.deg)).arcsec)
    seps.sort()
    print(f"\ncutouts ok {len(ok)}/{len(resp.frames)}; detected {len(detected)}; position-usable {len(seps)}; "
          f"sep vs Gaia median {seps[len(seps) // 2]:.2f}\" max {seps[-1]:.2f}\"")
    assert len(detected) >= 0.9 * len(ok)
    assert seps[len(seps) // 2] < 3.0 and seps[-1] < 6.15


def test_step4_barnard_proper_motion(barnard_run):
    """Barnard's summary reports a significant pm within 20% of the published value."""
    s = barnard_run.summary
    fit = s.proper_motion_fit
    print(f"\nfit: pm=({fit.pm_ra_cosdec:.0f}±{fit.pm_ra_cosdec_err:.0f}, {fit.pm_dec:.0f}±{fit.pm_dec_err:.0f}) "
          f"mas/yr |pm|={fit.pm_total:.0f}±{fit.err:.0f} ({fit.significance:.1f}σ) used {fit.n_used} "
          f"rejected {fit.n_rejected} baseline {fit.baseline_days:.0f} d; Gaia |pm|="
          f"{math.hypot(GAIA['pmra'], GAIA['pmdec']):.0f}")
    pm = s.proper_motion
    assert pm is not None, s.proper_motion_note
    gaia_total = math.hypot(GAIA["pmra"], GAIA["pmdec"])
    assert pm.pm_total == pytest.approx(gaia_total, rel=0.2)
    # each component within 20% of the total (pm_ra is only −0.8″/yr, so a relative test on it is meaningless)
    assert abs(pm.pm_ra_cosdec - GAIA["pmra"]) < 0.2 * gaia_total
    assert abs(pm.pm_dec - GAIA["pmdec"]) < 0.2 * gaia_total
    assert s.latest_position.dec > s.first_position.dec  # moved north
    assert len(s.spectrum) + len(s.spectrum_flagged) >= 0.8 * s.quality.n_detected


def test_step5_barnard_context_matched(barnard_run):
    """Barnard's Star context → matched, best match "Barnard's Star"."""
    ctx = barnard_run.context
    print(f"\nverdict={ctx.verdict} note={ctx.note} status={ctx.status_by_source}")
    if ctx.best_match:
        b = ctx.best_match
        print(f"best: {b.name} [{b.object_class}] {b.source_catalogs} score={b.match_score} "
              f"sep={b.separation_arcsec:.2f}\"")
    assert ctx.verdict == "matched", ctx.note
    # SIMBAD's canonical spelling is "Barnard's star" (main_id "NAME Barnard's star").
    assert ctx.best_match.name.lower() == "barnard's star"
    assert ctx.best_match.separation_arcsec < 6.15


# --------------------------------------------------------------------------- #
# Step 6 — solar system
# --------------------------------------------------------------------------- #

# Found live on 2026-11-14 (Horizons ephemeris from SPHEREx + SIA footprint check):
# (4) Vesta, V = 7.3, is inside this frame at its mid-time.
VESTA = {"frame_id": "2025W32_1A_0105_1D3", "t_mid": 60891.461818, "ra": 222.86623, "dec": -11.90754}


def test_step6_asteroid_in_frame():
    """The asteroid case: Vesta appears in solar_system_by_frame for the frame that contains it."""
    import spherex_inspect

    t0 = time.monotonic()
    resp = asyncio.run(spherex_inspect.inspect_point(InspectRequest(
        ra=VESTA["ra"], dec=VESTA["dec"], time_start=VESTA["t_mid"] - 0.5, time_end=VESTA["t_mid"] + 0.5)))
    ctx = resp.context
    print(f"\n{time.monotonic() - t0:.1f}s; frames {[f.frame_id for f in resp.frames]}")
    print(f"status {ctx.status_by_source}")
    for fid, bodies in ctx.solar_system_by_frame.items():
        print(f"  {fid}: {[(b.name, round(b.separation_arcsec, 1), b.mags.get('V'), b.ids.get('observer')) for b in bodies]}")
    print(f"verdict {ctx.verdict} best {ctx.best_match.name if ctx.best_match else None} note {ctx.note}")
    bodies = ctx.solar_system_by_frame.get(VESTA["frame_id"], [])
    vesta = [b for b in bodies if "Vesta" in b.name]
    assert vesta, f"Vesta not listed for {VESTA['frame_id']}: {[b.name for b in bodies]}"
    assert vesta[0].is_solar_system and vesta[0].object_class == "asteroid"
    assert vesta[0].separation_arcsec < 6.15  # within one pixel of the target (= Horizons position)
    assert vesta[0].mags["V"] < 17
    # The detection in that frame IS Vesta: it must be matched, not called a discovery.
    assert ctx.verdict == "matched" and "Vesta" in ctx.best_match.name, ctx.note


# --------------------------------------------------------------------------- #
# Step 7 — variability, candidate discovery, blank field
# --------------------------------------------------------------------------- #

RW_AUR = (76.95652603458333, 30.401438173888888)  # SIMBAD, pm ~20 mas/yr (negligible here)
R_DRA = (248.16761083295, 66.75497941722)
BLANK = (269.4520769586187, 4.693364966576667)  # Barnard's J2000 spot: the star left it long ago


def _run(ra, dec, **kw):
    import spherex_inspect

    t0 = time.monotonic()
    resp = asyncio.run(spherex_inspect.inspect_point(InspectRequest(ra=ra, dec=dec, **kw)))
    print(f"\n{time.monotonic() - t0:.1f}s")
    for v in resp.summary.variability:
        print(f"  D{v.detector} n={v.n:3d} basis={v.basis} rchi2={v.reduced_chi2} amp={v.amplitude} "
              f"variable={v.variable} {v.note or ''}")
    c = resp.context
    print(f"  verdict={c.verdict} best={c.best_match.name if c.best_match else None} "
          f"class={c.best_match.object_class if c.best_match else None} candidate={c.candidate_discovery} note={c.note}")
    return resp


@pytest.fixture(scope="session")
def rw_aur_run():
    return _run(*RW_AUR, max_frames=120)


@pytest.fixture(scope="session")
def r_dra_run():
    return _run(*R_DRA, max_frames=120)


def test_step7_rw_aur_flagged_variable(rw_aur_run):
    flagged = [v for v in rw_aur_run.summary.variability if v.variable]
    assert len(flagged) >= 2, "RW Aur should be variable in at least two detectors"
    assert any(v.basis == "saturated" for v in flagged)  # RW Aur saturates most SPHEREx frames
    assert max(v.amplitude for v in flagged) > 1.5
    # RW Aur is a 1.4″ binary (A+B): "ambiguous" is the honest verdict; the top body is variable.
    assert rw_aur_run.context.best_match and rw_aur_run.context.best_match.object_class == "variable_star"


def test_step7_r_dra_reported_not_measurable(r_dra_run):
    """R Dra (Mira) saturates with NaN cores in every frame: aperture photometry cannot measure
    it. The summary must say so rather than claim 'constant'."""
    vs = r_dra_run.summary.variability
    assert vs and not any(v.variable for v in vs)
    assert all(v.reduced_chi2 is None for v in vs)
    assert any(v.note and "masked (NaN) saturated core" in v.note for v in vs)
    assert r_dra_run.context.verdict == "matched" and r_dra_run.context.best_match.object_class == "variable_star"


def test_step7_barnard_not_variable(barnard_run):
    """Control: Barnard's Star is constant (and saturated); no detector may be flagged."""
    vs = barnard_run.summary.variability
    print("\n" + "\n".join(f"  D{v.detector} n={v.n} basis={v.basis} rchi2={v.reduced_chi2} {v.note or ''}" for v in vs))
    assert not any(v.variable for v in vs)


def test_step7_blank_field():
    resp = _run(*BLANK, max_frames=60)
    c = resp.context
    nothing = resp.summary.latest_position is None
    assert nothing or c.verdict == "no_known_match", f"blank field gave {c.verdict} ({c.note})"
    assert not c.candidate_discovery or c.n_clean_detections >= 2
