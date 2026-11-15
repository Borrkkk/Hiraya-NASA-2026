import pytest
from fastapi.testclient import TestClient

import spherex_inspect
from api.app import app
from spherex_inspect.discovery import FrameDiscovery

from .test_discovery import FakeBackend, make_row


@pytest.fixture
def client():
    rows = {
        "spherex_dr1": [make_row("a", 1, 61000.0, "spherex_dr1"), make_row("a", 4, 61000.0, "spherex_dr1")],
        "spherex_qr3": [make_row("c", 6, 61300.0)],
    }
    spherex_inspect.set_discovery(FrameDiscovery(FakeBackend(rows)))
    yield TestClient(app)
    spherex_inspect.set_discovery(None)


def test_frames_endpoint(client):
    r = client.get("/inspect/frames", params={"ra": "269.452", "dec": "4.6933", "bands": "1,6"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["n_returned"] == 2
    assert [f["frame_id"] for f in body["frames"]] == ["aD1", "cD6"]
    assert body["query"]["bands"] == [1, 6]
    f = body["frames"][0]
    for k in ("obs_id", "detector", "t_mid", "t_min", "t_max", "footprint", "release", "cutout_url", "full_url"):
        assert k in f


def test_frames_endpoint_bad_input(client):
    assert client.get("/inspect/frames", params={"ra": "x", "dec": "1"}).status_code == 422
    assert client.get("/inspect/frames", params={"ra": "1", "dec": "1", "bands": "9"}).status_code == 422
    assert client.get("/inspect/frames", params={"ra": "1", "dec": "1", "bands": "a"}).status_code == 422


def test_inspect_endpoint_end_to_end(monkeypatch):
    """Discovery (fake) → retrieval (mocked HTTP) → measurement → aggregation → JSON."""
    import httpx
    import respx

    from spherex_inspect.context import FieldContextService
    from spherex_inspect.retrieval import CutoutRetrieval

    from .test_context import FakeAdapter
    from .test_retrieval import MEF

    rows = {"spherex_dr1": [make_row(f"o{i}", (i % 6) + 1, 61000.0 + 10 * i, "spherex_dr1") for i in range(6)]}
    spherex_inspect.set_discovery(FrameDiscovery(FakeBackend(rows)))
    spherex_inspect.set_retrieval(CutoutRetrieval(backoff_s=0, retries=1))
    spherex_inspect.set_context(FieldContextService([FakeAdapter("gaia_dr3"), FakeAdapter("simbad", exc=ConnectionError("down"))]))
    try:
        with respx.mock:
            ok = MEF
            def handler(request):
                return httpx.Response(503) if "o2D3" in str(request.url) else httpx.Response(200, content=ok)
            respx.get(url__startswith="https://irsa").mock(side_effect=handler)
            r = TestClient(app).get("/inspect", params={"ra": "269.452", "dec": "4.6933", "size": "0.02"})
    finally:
        spherex_inspect.set_discovery(None)
        spherex_inspect.set_retrieval(None)
        spherex_inspect.set_context(None)
    assert r.status_code == 200
    b = r.json()
    assert b["status"] == "partial" and len(b["frames"]) == 6
    assert [f["status"] for f in b["frames"]].count("failed") == 1
    assert b["summary"]["quality"]["n_frames"] == 6 and b["summary"]["quality"]["n_failed"] == 1
    assert len(b["summary"]["spectrum_binned"]) == 102
    assert any("cutouts failed" in w for w in b["warnings"])
    assert any("catalog(s) failed: simbad" in w for w in b["warnings"])
    ctx = b["context"]
    assert ctx["verdict"] == "no_known_match" and ctx["status_by_source"]["gaia_dr3"] == "ok (0 rows)"
    assert ctx["status_by_source"]["simbad"].startswith("error")


def test_context_endpoint():
    from spherex_inspect.context import FieldContextService

    from .test_context import FakeAdapter, T_FRAME, barnard_gaia

    spherex_inspect.set_context(FieldContextService([FakeAdapter("gaia_dr3", [barnard_gaia()])]))
    try:
        ra, dec = barnard_gaia().position_at(T_FRAME)
        r = TestClient(app).get("/context", params={"ra": ra, "dec": dec, "t": str(T_FRAME)})
    finally:
        spherex_inspect.set_context(None)
    assert r.status_code == 200
    b = r.json()
    assert b["t_ref"] == T_FRAME and b["best_match"] is None and b["verdict"] == "no_known_match"
    assert b["nearby"][0]["source_catalogs"] == ["gaia_dr3"] and b["nearby"][0]["separation_arcsec"] < 0.01
    assert "nothing detected" in b["note"]
