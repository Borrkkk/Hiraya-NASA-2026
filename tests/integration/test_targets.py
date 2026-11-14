"""Live integration tests (run with `pytest -m live`). They hit IRSA/SIMBAD."""
import pytest

from spherex_inspect.discovery import FrameDiscovery
from spherex_inspect.intake import to_target
from spherex_inspect.models import InspectRequest

pytestmark = pytest.mark.live


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


async def test_step2_cutouts_download_and_cache(tmp_path):
    import time

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
