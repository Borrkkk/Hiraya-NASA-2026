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
