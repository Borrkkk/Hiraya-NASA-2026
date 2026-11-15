import asyncio
import time

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.explore import analysis, sources, verify as verify_mod
from app.explore.analysis import detect_sources
from app.main import app

REAL_LIVE_SHOTS = sources.live_shots  # the autouse fixture replaces it on the module
RA, DEC = 269.452076, 4.693391
AREA = "269.45208_4.69339"


@pytest.fixture(autouse=True)
def offline(monkeypatch, request):
    """Tests use only the saved cache; the live IRSA path is tested with a fake archive below."""
    async def nothing(client, ra, dec):
        return ()
    monkeypatch.setattr(sources, "live_shots", nothing)
    sources.SHOTS.clear()
    from app.explore.common import local_shots
    needs_images = ('client' in request.fixturenames and request.node.name not in {
        'test_area_without_images_is_a_404_with_a_suggestion', 'test_search_finds_saved_targets_first'})
    needs_images |= request.node.name == 'test_live_path_builds_shots_from_an_irsa_style_table_and_cutouts'
    if needs_images and not local_shots(RA, DEC):
        pytest.skip('Optional real-image integration fixture is no longer shipped')


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def wait(client, job_id):
    for _ in range(60):
        job = client.get(f"/explore/jobs/{job_id}").json()
        if job["status"] != "running":
            return job
        time.sleep(0.1)
    raise AssertionError("job did not finish")


def test_area_has_real_epochs_and_honest_band_coverage(client):
    area = client.get("/explore/area", params={"ra": RA, "dec": DEC, "fov": 0.25}).json()
    assert area["name"] == "Barnard's Star"
    assert len(area["epochs"]) == 2
    bands = {b["id"]: b for b in area["bands"]}
    assert bands["starlight"]["state"] == "ok"
    # Both saved exposures sit near 0.8 um, so every other row has no data.
    assert bands["hydrogen"]["state"] == "no-coverage" and "0.8 µm" in bands["hydrogen"]["reason"]
    assert area["sizePx"] == 128 and area["pixelScaleArcsec"] == 6.15


def test_area_without_images_is_a_404_with_a_suggestion(client):
    r = client.get("/explore/area", params={"ra": 10.0, "dec": 40.0})
    assert r.status_code == 404
    detail = r.json()["detail"]
    assert "hasn't observed" in detail["message"] and detail["suggestion"] is None


def test_frame_is_a_png_with_transparency_where_there_is_no_data(client):
    from io import BytesIO
    from PIL import Image
    r = client.get(f"/explore/areas/{AREA}/frames/2025W35_1A_0658_1/starlight")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    img = np.array(Image.open(BytesIO(r.content)).convert("RGBA"))
    assert img.shape == (128, 128, 4) and 0 < (img[..., 3] > 0).mean() < 1
    blank = client.get(f"/explore/areas/{AREA}/frames/2025W35_1A_0658_1/hydrogen")
    assert (np.array(Image.open(BytesIO(blank.content)).convert("RGBA"))[..., 3] == 0).all()


def box(ra, dec, size=0.006):
    return {"ra": ra, "dec": dec, "width": size, "height": size}


def inspect(client, b):
    return client.post(f"/explore/areas/{AREA}/inspect", json={
        "areaId": AREA, "target": {"kind": "box", "box": b}, "epoch": "all", "bands": ["starlight"]}).json()


def test_inspect_returns_the_wavelengths_we_really_have(client):
    out = inspect(client, box(269.47, 4.71))
    waves = [p["wavelengthUm"] for p in out["spectrum"]["points"]]
    assert waves == pytest.approx([0.757, 0.7745], abs=0.002)
    assert out["guess"]["type"] in {"star", "galaxy", "empty"}
    assert abs(sum(c["confidence"] for c in out["candidates"]) - 1) < 1e-6


def test_inspect_flags_a_box_outside_the_frame_as_an_artifact(client):
    out = inspect(client, box(RA + 0.2, DEC))
    assert out["guess"]["type"] == "artifact"


def test_motion_finds_nothing_in_two_exposures_two_minutes_apart(client):
    r = client.post(f"/explore/areas/{AREA}/motion", json={
        "areaId": AREA, "epochs": ["2025W35_1A_0658_1", "2025W35_1A_0658_2"], "bands": ["starlight"]})
    job = wait(client, r.json()["jobId"])
    assert job["status"] == "done" and job["result"]["movers"] == []


def test_motion_needs_two_epochs(client):
    r = client.post(f"/explore/areas/{AREA}/motion", json={"areaId": AREA, "epochs": ["x"], "bands": []})
    assert r.status_code == 422


def test_source_detection_and_tracking_finds_a_shifted_source():
    base = np.random.default_rng(1).normal(0, 0.05, (64, 64))
    def frame(x, y):
        yy, xx = np.indices(base.shape)
        return base + 4 * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / 2)
    a, b = detect_sources(frame(20, 30)), detect_sources(frame(25, 30))
    assert len(a) == 1 and len(b) == 1
    assert abs(b[0][0] - a[0][0] - 5) < 0.3


def test_verify_offline_uses_the_saved_list_and_respects_proper_motion(client):
    # The cutout centre is the J2000 position; Barnard's Star has since moved ~265".
    r = client.post(f"/explore/areas/{AREA}/verify", json={
        "areaId": AREA, "target": {"kind": "box", "box": box(RA, DEC, 0.004)}, "epoch": "all", "bands": []})
    job = wait(client, r.json()["jobId"])
    assert job["result"]["outcome"] in {"unexplained", "artifact"}
    moved = verify_mod.check_local(box(269.4463, 4.7672, 0.004), 60915.4)
    assert moved and moved["name"] == "Barnard's Star"


def test_simbad_answer_becomes_an_explained_result():
    def handler(request):
        return httpx.Response(200, json={"data": [["* Test Star", "BD*", 1.0, 2.0]]})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await verify_mod.check_simbad(c, box(1.0, 2.0))
    out = asyncio.run(run())
    assert out["outcome"] == "explained" and out["objectType"] == "brown-dwarf" and out["source"] == "SIMBAD"


def test_search_finds_saved_targets_first(client):
    out = client.get("/explore/search", params={"q": "barnard"}).json()["results"]
    assert out[0]["name"] == "Barnard's Star" and out[0]["images"] is False
    assert all(not r['images'] for r in client.get("/explore/search", params={"q": ""}).json()["results"])


def test_live_path_builds_shots_from_an_irsa_style_table_and_cutouts(monkeypatch, tmp_path):
    """The IRSA path, against a fake archive: a VOTable with named columns and FITS cutouts."""
    from pathlib import Path
    fits_bytes = next(Path("../data/targets/barnards-star/cutouts").glob("*_1_D1.fits")).read_bytes()

    def row(n, mjd):
        return (f"<TR><TD>2025W35_1A_0658_{n}</TD><TD>{mjd}</TD><TD>https://irsa.ipac.caltech.edu/ibe/data/spherex/"
                f"dr1/level2/x/{n}/level2_2025W35_1A_0658_{n}D1_spx_l2b.fits</TD></TR>")

    table = ("<?xml version='1.0'?><VOTABLE version='1.3' xmlns='http://www.ivoa.net/xml/VOTable/v1.3'><RESOURCE><TABLE>"
             "<FIELD name='obs_id' datatype='char' arraysize='*'/><FIELD name='t_min' datatype='double'/>"
             "<FIELD name='access_url' datatype='char' arraysize='*'/><DATA><TABLEDATA>"
             + row(1, 60915.4311) + row(2, 60915.4326) + "</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>").encode()

    async def fake_download(client, url, params=None):
        return table if params else fits_bytes

    monkeypatch.setattr(sources, "download", fake_download)
    monkeypatch.setattr(sources, "CACHE", tmp_path)
    shots = asyncio.run(REAL_LIVE_SHOTS(None, RA, DEC))
    assert [s.epoch_id for s in shots] == ["2025W35_1A_0658_1", "2025W35_1A_0658_2"]
    assert {s.detector for s in shots} == {1}
    assert shots[0].wavelength == pytest.approx(0.757, abs=0.002)
    assert len(list(tmp_path.glob("*.fits"))) == 2  # cutouts are cached on disk


def test_frames_come_in_three_sizes_and_the_widest_is_wider(client):
    from io import BytesIO
    from PIL import Image
    A_ = AREA
    area = client.get("/explore/area", params={"ra": RA, "dec": DEC}).json()
    assert [l["sizePx"] for l in area["levels"]] == [128, 256, 256]
    assert area["levels"][2]["extentDeg"] > 2 * area["levels"][0]["extentDeg"]
    for lv, size in enumerate((128, 256, 256)):
        r = client.get(f"/explore/areas/{A_}/frames/2025W35_1A_0658_1/starlight", params={"level": lv})
        assert Image.open(BytesIO(r.content)).size == (size, size)
    assert client.get(f"/explore/areas/{A_}/frames/2025W35_1A_0658_1/starlight", params={"level": 9}).status_code == 404


def test_epochs_say_which_bands_they_have_and_how_full_they_are(client):
    area = client.get("/explore/area", params={"ra": RA, "dec": DEC}).json()
    for e in area["epochs"]:
        assert e["bands"] == ["starlight"] and 0 < e["coverage"] <= 1


def test_the_box_picks_the_smallest_frame_that_holds_it():
    from app.explore.analysis import pick_level
    assert pick_level(RA, DEC, box(RA, DEC, 0.01)) == 0
    assert pick_level(RA, DEC, box(RA + 0.15, DEC, 0.01)) == 1
    assert pick_level(RA, DEC, box(RA + 0.4, DEC, 0.01)) == 2
