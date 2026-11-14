import pytest

from spherex_inspect.discovery import (
    DiscoveryError,
    FrameDiscovery,
    cap_frames,
    cutout_url,
    parse_detector,
    parse_polygon,
    release_from_collection,
    row_to_frame,
    select_collections,
)
from spherex_inspect.intake import to_target
from spherex_inspect.models import InspectRequest

UNITS = {"t_min": "d", "t_max": "d", "s_region": "deg", "s_pixel_scale": "arcsec", "em_min": "m", "em_max": "m"}


def make_row(obs_id="2026W33_2A_0594_4", det=3, t=61268.63, coll="spherex_qr3", **kw):
    row = {
        "obs_id": obs_id,
        "energy_bandpassname": f"SPHEREx-D{det}",
        "t_min": t,
        "t_max": t + 0.0013,
        "s_region": "POLYGON ICRS 268.47 8.17 271.97 7.89 271.83 4.40 268.32 4.69 268.47 8.17",
        "access_url": f"https://irsa.ipac.caltech.edu/ibe/data/spherex/x/{obs_id}D{det}.fits",
        "s_pixel_scale": 6.15,
        "em_min": 1.6301e-06,
        "em_max": 2.4346e-06,
        "obs_collection": coll,
        "dataproduct_subtype": "science",
        "_units": UNITS,
    }
    row.update(kw)
    return row


TARGET = to_target(InspectRequest(ra=269.452, dec=4.6933))


def test_select_collections_newest_only():
    avail = ["spherex_qr2", "spherex_qr3", "spherex_qr3_deep", "spherex_dr1", "spherex_dr1_cube", "spherex_dr1_deep", "other"]
    assert select_collections(avail) == ["spherex_dr1", "spherex_dr1_deep", "spherex_qr3", "spherex_qr3_deep"]
    assert select_collections(["spherex_qr10", "spherex_qr9"]) == ["spherex_qr10"]


def test_parsers():
    assert parse_detector("SPHEREx-D6") == 6 and parse_detector("x") is None
    poly = parse_polygon("POLYGON ICRS 1 2 3 4 5 6 1 2")
    assert poly == [(1, 2), (3, 4), (5, 6)]
    assert release_from_collection("spherex_dr1") == "DR1"
    assert release_from_collection("spherex_qr3_deep") == "QR3-deep"
    assert cutout_url("https://x/f.fits", 269.452, 4.6933, 0.05) == "https://x/f.fits?center=269.4520000,4.6933000d&size=0.05"


def test_row_to_frame_units_and_key():
    f = row_to_frame(make_row(), TARGET, "spherex_qr3")
    assert f.frame_id == "2026W33_2A_0594_4D3" and f.detector == 3
    assert f.t_mid == pytest.approx(61268.63065)
    assert f.em_min_um == pytest.approx(1.6301) and f.em_max_um == pytest.approx(2.4346)
    assert f.pixel_scale_arcsec == 6.15
    assert f.release == "QR3" and len(f.footprint) == 4
    assert f.cutout_url.startswith(f.full_url + "?center=269.4520000,4.6933000d&size=0.05")


def test_row_to_frame_rejects_incomplete():
    assert row_to_frame(make_row(energy_bandpassname="?"), TARGET, "c") is None
    assert row_to_frame(make_row(access_url=None), TARGET, "c") is None
    assert row_to_frame(make_row(dataproduct_subtype="calibration"), TARGET, "c") is None


def _frames(n_per_det=50, dets=(1, 2, 3, 4, 5, 6)):
    out = []
    for d in dets:
        for i in range(n_per_det):
            out.append(row_to_frame(make_row(obs_id=f"o{i}", det=d, t=61000 + i + d * 0.01), TARGET, "spherex_dr1"))
    return out


def test_cap_spreads_detectors_and_keeps_ends():
    frames = _frames()
    capped = cap_frames(frames, 30)
    assert len(capped) == 30
    by_det = {}
    for f in capped:
        by_det.setdefault(f.detector, []).append(f)
    assert sorted(by_det) == [1, 2, 3, 4, 5, 6] and all(len(v) == 5 for v in by_det.values())
    # first and last epochs kept for each detector
    for d, fs in by_det.items():
        assert fs[0].obs_id == "o0" and fs[-1].obs_id == "o49"
    assert [f.t_mid for f in capped] == sorted(f.t_mid for f in capped)


def test_cap_redistributes_when_detector_is_short():
    frames = _frames(n_per_det=50, dets=(1, 2)) + _frames(n_per_det=2, dets=(3,))
    capped = cap_frames(frames, 20)
    counts = {d: sum(f.detector == d for f in capped) for d in (1, 2, 3)}
    assert counts[3] == 2 and sum(counts.values()) == 20


def test_cap_noop_under_limit():
    frames = _frames(n_per_det=3)
    assert cap_frames(frames, 100) == frames


class FakeBackend:
    def __init__(self, rows_by_coll, fail=()):
        self.rows_by_coll, self.fail, self.calls = rows_by_coll, set(fail), 0

    def list_collections(self):
        return list(self.rows_by_coll) + ["spherex_qr2", "spherex_dr1_cube"]

    def query(self, ra, dec, radius, coll):
        self.calls += 1
        if coll in self.fail:
            raise ConnectionError("503")
        return self.rows_by_coll[coll]


async def test_discover_filters_dedupes_sorts():
    rows = {
        "spherex_dr1": [make_row("a", 1, 61000.0, "spherex_dr1"), make_row("a", 4, 61000.0, "spherex_dr1"), make_row("b", 2, 60990.0, "spherex_dr1")],
        "spherex_qr3": [make_row("c", 1, 61300.0), make_row("c", 1, 61300.0)],  # duplicate row
    }
    d = FrameDiscovery(FakeBackend(rows))
    t = to_target(InspectRequest(ra=269.452, dec=4.6933, bands=[1, 2], time_start=60995))
    res, warnings = await d.discover(t)
    assert [f.frame_id for f in res.frames] == ["aD1", "cD1"]
    assert res.collections == ["spherex_dr1", "spherex_qr3"]
    assert warnings == []


async def test_discover_partial_failure(monkeypatch):
    monkeypatch.setattr("spherex_inspect.config.SIA_BACKOFF_S", 0)
    rows = {"spherex_dr1": [make_row("a", 1, 61000.0, "spherex_dr1")], "spherex_qr3": []}
    d = FrameDiscovery(FakeBackend(rows, fail={"spherex_qr3"}))
    res, warnings = await d.discover(TARGET)
    assert len(res.frames) == 1 and any("spherex_qr3 failed" in w for w in warnings)


async def test_discover_all_fail_raises(monkeypatch):
    monkeypatch.setattr("spherex_inspect.config.SIA_BACKOFF_S", 0)
    d = FrameDiscovery(FakeBackend({"spherex_dr1": []}, fail={"spherex_dr1"}))
    with pytest.raises(DiscoveryError):
        await d.discover(TARGET)


async def test_cap_warning():
    rows = {"spherex_dr1": [make_row(f"o{i}", (i % 6) + 1, 61000.0 + i, "spherex_dr1") for i in range(60)]}
    d = FrameDiscovery(FakeBackend(rows))
    t = to_target(InspectRequest(ra=1, dec=2, max_frames=12))
    res, warnings = await d.discover(t)
    assert len(res.frames) == 12 and res.n_found == 60 and any("capped" in w for w in warnings)


async def test_collections_fall_back_to_cached_list(monkeypatch, tmp_path):
    import diskcache

    monkeypatch.setattr("spherex_inspect.config.SIA_BACKOFF_S", 0)
    cache = diskcache.Cache(str(tmp_path / "dc"))
    rows = {"spherex_dr1": [make_row("a", 1, 61000.0, "spherex_dr1")], "spherex_qr2": []}  # fake also lists qr2
    assert await FrameDiscovery(FakeBackend(rows), cache=cache).collections() == ["spherex_dr1", "spherex_qr2"]

    class Down(FakeBackend):
        def list_collections(self):
            raise ConnectionError("502 Proxy Error")

    # A fresh instance (e.g. after a restart) with IRSA's listing down uses the cached list.
    d = FrameDiscovery(Down(rows), cache=cache)
    res, _ = await d.discover(TARGET)
    assert res.collections == ["spherex_dr1", "spherex_qr2"] and len(res.frames) == 1

    with pytest.raises(DiscoveryError):
        await FrameDiscovery(Down(rows), cache=diskcache.Cache(str(tmp_path / "empty"))).collections()


async def test_sia_rows_cached_and_stale_fallback(monkeypatch, tmp_path):
    import diskcache

    import spherex_inspect.discovery as disc

    cache = diskcache.Cache(str(tmp_path / "sia"))
    rows = {"spherex_dr1": [make_row("a", 1, 61000.0, "spherex_dr1")], "spherex_qr2": []}
    be = FakeBackend(rows)
    res, w = await FrameDiscovery(be, cache=cache).discover(TARGET)
    n_calls = be.calls
    res2, w2 = await FrameDiscovery(be, cache=cache).discover(TARGET)
    assert be.calls == n_calls and [f.frame_id for f in res2.frames] == ["aD1"]  # served from cache
    assert w2 == []

    # Past the TTL with IRSA down: the stale list is used, with a warning.
    monkeypatch.setattr(disc.time, "time", lambda: 1e12)
    down = FakeBackend(rows, fail={"spherex_dr1", "spherex_qr2"})
    res3, w3 = await FrameDiscovery(down, cache=cache).discover(TARGET)
    assert [f.frame_id for f in res3.frames] == ["aD1"]
    assert any("using the cached frame list" in x for x in w3)
