"""Regression tests: an exposure with no unmasked pixels must not crash Explore."""
from io import BytesIO

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.explore import common, frames
from app.explore.common import Shot
from app.main import app


@pytest.fixture
def fake_cutouts(monkeypatch, tmp_path):
    """Two real-looking exposure entries, one entirely masked and one usable."""
    ra, dec = 123.45678, -21.34567
    bad_path = tmp_path / "masked.fits"
    good_path = tmp_path / "usable.fits"
    bad_path.write_bytes(b"masked")
    good_path.write_bytes(b"usable")
    bad = Shot("bad_epoch", 1, 61000.0, bad_path, 1.08)
    good = Shot("good_epoch", 1, 61001.0, good_path, 0.80)

    def fake_align(raw, request):
        if raw == b"masked":
            raise ValueError("No usable pixels cover this position after masking")
        return np.ones((request.size_px, request.size_px), dtype=float)

    monkeypatch.setattr(common, "align", fake_align)
    common.SHOTS[common.key(ra, dec)] = (bad, good)
    common.aligned.cache_clear()
    frames._stretch.cache_clear()
    yield ra, dec, bad, good
    common.SHOTS.pop(common.key(ra, dec), None)
    common.aligned.cache_clear()
    frames._stretch.cache_clear()


def test_explore_aligned_converts_only_fully_masked_exposures_to_nan(fake_cutouts):
    ra, dec, bad, good = fake_cutouts
    masked = common.aligned(str(bad.path), ra, dec)
    assert masked.shape == (common.SIZE_PX, common.SIZE_PX)
    assert np.isnan(masked).all()
    assert np.isfinite(common.aligned(str(good.path), ra, dec)).all()


def test_area_skips_masked_dates_and_wavelength_bands(fake_cutouts):
    ra, dec, _, good = fake_cutouts
    with TestClient(app) as client:
        response = client.get("/explore/area", params={"ra": ra, "dec": dec, "fov": 0.25})
    assert response.status_code == 200
    area = response.json()
    assert [e["id"] for e in area["epochs"]] == [good.epoch_id]
    assert area["epochs"][0]["coverage"] == 1.0
    bands = {b["id"]: b for b in area["bands"]}
    assert bands["starlight"]["state"] == "ok"
    assert bands["helium"]["state"] == "no-coverage"


def test_masked_frame_returns_transparent_png_instead_of_500(fake_cutouts):
    ra, dec, bad, _ = fake_cutouts
    area_id = common.area_id(ra, dec)
    with TestClient(app) as client:
        response = client.get(f"/explore/areas/{area_id}/frames/{bad.epoch_id}/helium")
    assert response.status_code == 200
    rgba = np.asarray(Image.open(BytesIO(response.content)).convert("RGBA"))
    assert rgba.shape == (common.SIZE_PX, common.SIZE_PX, 4)
    assert np.all(rgba[..., 3] == 0)


def test_all_masked_exposures_yield_honest_404_not_server_error(fake_cutouts):
    ra, dec, bad, _ = fake_cutouts
    common.SHOTS[common.key(ra, dec)] = (bad,)
    with TestClient(app) as client:
        response = client.get("/explore/area", params={"ra": ra, "dec": dec})
    assert response.status_code == 404
    assert "hasn't observed" in response.json()["detail"]["message"]


def test_shot_for_prefers_usable_detector_when_other_is_masked(fake_cutouts):
    ra, dec, bad, good = fake_cutouts
    common.SHOTS[common.key(ra, dec)] = (
        Shot("same_epoch", 1, bad.mjd, bad.path, 0.80),
        Shot("same_epoch", 2, good.mjd, good.path, 0.80),
    )
    preferred = common.shot_for(ra, dec, "same_epoch", "starlight")
    assert preferred is not None and preferred.path == good.path


def test_all_masked_band_stretch_uses_safe_defaults(fake_cutouts):
    ra, dec, bad, _ = fake_cutouts
    common.SHOTS[common.key(ra, dec)] = (bad,)
    assert frames._stretch(ra, dec, "helium") == (0.0, 1.0)


def test_unrelated_alignment_errors_are_not_hidden(monkeypatch, tmp_path):
    file = tmp_path / "invalid.fits"
    file.write_bytes(b"broken")

    def bad_wcs(*args):
        raise ValueError("Invalid FITS WCS header")

    monkeypatch.setattr(common, "align", bad_wcs)
    common.aligned.cache_clear()
    try:
        with pytest.raises(ValueError, match="Invalid FITS WCS header"):
            common.aligned(str(file), 50.0, 10.0)
    finally:
        common.aligned.cache_clear()
