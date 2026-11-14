from io import BytesIO
import base64
import httpx
import numpy as np
import pytest
from astropy.io import fits
from astropy.table import Table
from astropy.io.votable import from_table, writeto
from fastapi.testclient import TestClient
from PIL import Image
from app.archive import ArchiveError, parse_results, validate_url
from app.imaging import align, png, render, target_wcs
from app.main import app
from app.models import TimelapseRequest

URL = 'https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/level2/test/level2_test_1D1_spx_v1.fits'

def votable(url=URL, empty=False):
    table = Table({'access_url': [url], 'obs_id': ['test'], 't_min': [61000.]})
    if empty:
        table = table[:0]
    stream = BytesIO()
    writeto(from_table(table), stream)
    return stream.getvalue()

def synthetic(request, flags=None, rotated=False):
    data = np.zeros((request.size_px, request.size_px))
    wcs = target_wcs(request)
    if rotated:
        wcs.wcs.pc = [[0, -1], [1, 0]]
    ra, dec = target_wcs(request).all_pix2world(8, 9, 0)
    x, y = wcs.all_world2pix(ra, dec, 0)
    data[int(round(float(y))), int(round(float(x)))] = 100
    hdus = fits.HDUList([fits.PrimaryHDU(), fits.ImageHDU(data, wcs.to_header(), name='IMAGE'),
                        fits.ImageHDU(np.zeros_like(data, dtype=np.uint32) if flags is None else flags, name='FLAGS')])
    stream = BytesIO()
    hdus.writeto(stream)
    return stream.getvalue()

@pytest.mark.parametrize('rotated', [False, True])
def test_alignment(rotated):
    request = TimelapseRequest(ra=359.999, dec=80, size_px=16)
    result = align(synthetic(request, rotated=rotated), request)
    assert result[9, 8] == pytest.approx(100, abs=1e-6)

def test_flags():
    request = TimelapseRequest(ra=0, dec=0, size_px=16)
    flags = np.zeros((16, 16), dtype=np.uint32)
    flags[9, 8] = 1
    assert np.isnan(align(synthetic(request, flags), request)[9, 8])

def test_shared_stretch_and_median_difference():
    a = np.arange(256, dtype=float).reshape(16, 16)
    output = render([a, a + 10])
    assert output['images'][0] != output['images'][1]
    assert output['stretch']['difference_abs_max'] == pytest.approx(5)

def test_png_orientation_and_transparency():
    url = png(np.array([[0., np.nan], [10., 10.]]), 0, 10)
    pixels = np.asarray(Image.open(BytesIO(base64.b64decode(url.split(',')[1]))))
    assert pixels[0, 0, 0] == 255
    assert pixels[1, 1, 3] == 0

def test_votable_and_detector_filter():
    request = TimelapseRequest(ra=0, dec=0)
    rows, overflow = parse_results(votable(), 'spherex_dr1', request)
    assert len(rows) == 1 and not overflow
    assert parse_results(votable(), 'spherex_dr1', request.model_copy(update={'detector': 2}))[0] == []

@pytest.mark.parametrize('url', ['http://localhost/a.fits', 'https://evil.com/a.fits', URL + '?url=x'])
def test_untrusted_urls(url):
    with pytest.raises(ArchiveError):
        validate_url(url)

@pytest.mark.parametrize('empty', [False, True])
def test_api_end_to_end(empty):
    request = TimelapseRequest(ra=0, dec=0, size_px=16, collections=['spherex_dr1'], source='remote')
    def handler(incoming):
        if incoming.url.path == '/SIA':
            return httpx.Response(200, content=votable(empty=empty))
        assert 'center' in incoming.url.params
        return httpx.Response(200, content=synthetic(request))
    with TestClient(app) as client:
        original = app.state.client
        app.state.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        response = client.post('/spherex/timelapse', json=request.model_dump())
        app.state.client = original
        assert response.status_code == 200, response.text
        result = response.json()
        assert result['status'] == ('no_coverage' if empty else 'ready')
        assert len(result['frames']) == (0 if empty else 1)
        if not empty:
            assert result['median_png'].startswith('data:image/png;base64,')

def test_validation():
    with TestClient(app) as client:
        for body in [{'ra':360,'dec':0}, {'ra':0,'dec':-91}, {'ra':0,'dec':0,'mjd_start':2,'mjd_end':1}, {'ra':0,'dec':0,'size_px':10000}]:
            assert client.post('/spherex/timelapse', json=body).status_code == 422

def test_archive_failure_is_not_no_coverage():
    with TestClient(app) as client:
        original = app.state.client
        app.state.client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
        response = client.post('/spherex/search', json={'ra':0,'dec':0,'source':'remote'})
        app.state.client = original
        assert response.status_code == 502
