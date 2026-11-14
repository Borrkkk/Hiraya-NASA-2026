import io

import diskcache
import httpx
import numpy as np
import pytest
import respx
from astropy.io import fits
from astropy.table import Table

from spherex_inspect.cache import cutout_key
from spherex_inspect.intake import to_target
from spherex_inspect.models import InspectRequest
from spherex_inspect.retrieval import CutoutRetrieval, parse_cutout

from .test_discovery import make_row
from spherex_inspect.discovery import row_to_frame

TARGET = to_target(InspectRequest(ra=269.452, dec=4.6933, cutout_size_deg=0.02))


def synthetic_mef(n=12) -> bytes:
    """Minimal MEF with the SPHEREx HDU layout (not real data)."""
    hdr = fits.Header()
    hdr.update({
        "CTYPE1": "RA---TAN", "CTYPE2": "DEC--TAN", "CRVAL1": 269.452, "CRVAL2": 4.6933,
        "CRPIX1": n / 2, "CRPIX2": n / 2, "CDELT1": -6.15 / 3600, "CDELT2": 6.15 / 3600,
        "CUNIT1": "deg", "CUNIT2": "deg",
        "CTYPE1W": "WAVE", "CTYPE2W": "LINEAR", "CRVAL1W": 2.0, "CRVAL2W": 0.05,
        "CRPIX1W": 1, "CRPIX2W": 1, "CDELT1W": 0.01, "CDELT2W": 0.001, "CUNIT1W": "um",
        "DETECTOR": 3, "PSF_FWHM": 7.4,
    })
    prim = fits.PrimaryHDU()
    prim.header["VERSION"] = "7.0.5"
    epsf = Table({"XCENTER": [100.0], "YCENTER": [100.0], "EPSF": [np.ones((33, 33))]})
    hdus = [
        prim,
        fits.ImageHDU(np.ones((n, n), np.float32), header=hdr, name="IMAGE"),
        fits.ImageHDU(np.zeros((n, n), np.int32), name="FLAGS"),
        fits.ImageHDU(np.full((n, n), 0.01, np.float32), name="VARIANCE"),
        fits.ImageHDU(np.full((n, n), 0.2, np.float32), name="ZODI"),
        fits.BinTableHDU(epsf, name="EPSF"),
        fits.BinTableHDU(Table({"X": [np.arange(3)]}), name="WCS-WAVE"),
    ]
    buf = io.BytesIO()
    fits.HDUList(hdus).writeto(buf)
    return buf.getvalue()


MEF = synthetic_mef()


def frame(i=0, det=3):
    return row_to_frame(make_row(obs_id=f"o{i}", det=det, t=61000 + i), TARGET, "spherex_dr1")


@pytest.fixture
def cache(tmp_path):
    c = diskcache.Cache(str(tmp_path / "c"))
    yield c
    c.close()


def retr(cache, **kw):
    return CutoutRetrieval(cache=cache, backoff_s=0, **kw)


def test_parse_cutout():
    c = parse_cutout(frame(), MEF)
    assert c.status == "ok" and c.version == "7.0.5"
    assert c.image.shape == (12, 12) and c.flags.dtype == np.int64
    assert c.header["DETECTOR"] == 3 and c.wave_wcs is not None and c.wave_wcs.sip is None


def test_parse_rejects_non_fits():
    with pytest.raises(ValueError):
        parse_cutout(frame(), b"<html>503 Service Unavailable</html>")


@respx.mock
async def test_fetch_ok_then_cache_hit(cache):
    frames = [frame(i) for i in range(5)]
    route = respx.get(url__startswith="https://irsa.ipac.caltech.edu/").mock(return_value=httpx.Response(200, content=MEF))
    out = await retr(cache).fetch(frames, TARGET)
    assert [c.status for c in out] == ["ok"] * 5 and route.call_count == 5
    assert [c.frame.frame_id for c in out] == [f.frame_id for f in frames]  # order preserved
    assert not any(c.from_cache for c in out)
    assert cutout_key(frames[0].frame_id, 269.452, 4.6933, 0.02) in cache

    out2 = await retr(cache).fetch(frames, TARGET)
    assert all(c.from_cache for c in out2) and route.call_count == 5  # no new requests


@respx.mock
async def test_retry_on_503_then_success(cache):
    route = respx.get(url__startswith="https://irsa").mock(
        side_effect=[httpx.Response(503, text="busy"), httpx.ConnectError("reset"), httpx.Response(200, content=MEF)]
    )
    [c] = await retr(cache).fetch([frame()], TARGET)
    assert c.status == "ok" and c.extra["attempts"] == 3 and route.call_count == 3


@respx.mock
async def test_retry_on_truncated_body(cache):
    respx.get(url__startswith="https://irsa").mock(
        side_effect=[httpx.Response(200, content=MEF[:5000]), httpx.Response(200, content=MEF)]
    )
    [c] = await retr(cache).fetch([frame()], TARGET)
    assert c.status == "ok" and c.extra["attempts"] == 2


@respx.mock
async def test_fatal_404_no_retry(cache):
    route = respx.get(url__startswith="https://irsa").mock(return_value=httpx.Response(404, text="nope"))
    [c] = await retr(cache).fetch([frame()], TARGET)
    assert c.status == "failed" and "404" in c.error and route.call_count == 1
    assert len(cache) == 0


@respx.mock
async def test_partial_failure_carries_on(cache):
    frames = [frame(i) for i in range(10)]
    bad = {frames[i].cutout_url for i in (1, 4, 7)}

    def handler(request):
        if str(request.url) in bad:
            return httpx.Response(503)
        return httpx.Response(200, content=MEF)

    respx.get(url__startswith="https://irsa").mock(side_effect=handler)
    out = await retr(cache, retries=2).fetch(frames, TARGET)
    statuses = [c.status for c in out]
    assert statuses.count("failed") == 3 and statuses.count("ok") == 7
    assert out[1].status == "failed" and "503" in out[1].error


@respx.mock
async def test_corrupt_cache_entry_redownloads(cache):
    f = frame()
    cache.set(cutout_key(f.frame_id, 269.452, 4.6933, 0.02), b"garbage")
    route = respx.get(url__startswith="https://irsa").mock(return_value=httpx.Response(200, content=MEF))
    [c] = await retr(cache).fetch([f], TARGET)
    assert c.status == "ok" and not c.from_cache and route.call_count == 1


@respx.mock
async def test_concurrency_bounded(cache):
    import asyncio

    active = peak = 0

    async def handler(request):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return httpx.Response(200, content=MEF)

    respx.get(url__startswith="https://irsa").mock(side_effect=handler)
    out = await retr(cache, concurrency=3).fetch([frame(i) for i in range(12)], TARGET)
    assert all(c.status == "ok" for c in out) and peak <= 3


# ---- real fixtures (captured live 2026-11-14, Barnard's Star, 0.02 deg) ----
import json
from pathlib import Path

from spherex_inspect.models import FrameRef

FIXTURES = Path(__file__).parent.parent / "fixtures"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text())


@pytest.mark.parametrize("name", sorted(MANIFEST))
def test_parse_real_fixture(name):
    m = MANIFEST[name]
    f = FrameRef(**m["frame"])
    c = parse_cutout(f, (FIXTURES / m["file"]).read_bytes())
    assert c.status == "ok" and c.version
    assert int(c.header["DETECTOR"]) == f.detector
    assert c.image.shape == c.flags.shape == c.variance.shape == c.zodi.shape
    assert {"XCENTER", "YCENTER", "EPSF"} <= set(c.epsf.names)
    assert any(k.startswith("MSKN") for k in c.flags_header)
    ny, nx = c.image.shape
    lam, bw = c.wave_wcs.pixel_to_world(nx / 2, ny / 2)
    lam, bw = lam.to_value("um"), bw.to_value("um")
    assert 0 < bw < 0.2
    # SIA em_min/em_max is not a hard per-pixel bound (D1 edge pixel: 0.7436 vs em_min 0.7455),
    # so require the pixel's band [lam - bw/2, lam + bw/2] to overlap the frame's range.
    assert lam + bw / 2 >= f.em_min_um and lam - bw / 2 <= f.em_max_um
