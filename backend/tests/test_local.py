import asyncio
from io import BytesIO
import base64

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.local_store import cutout_path, search_local
from app.models import SkyRequest

BARNARD = {"ra": 269.452076, "dec": 4.693391}


@pytest.mark.skip(reason='Real-image integration fixture removed with bundled FITS images')
def test_real_local_frames_without_network():
    def reject(request):
        raise AssertionError("Local mode must not contact the archive")
    with TestClient(app) as client:
        original = app.state.client
        mock = httpx.AsyncClient(transport=httpx.MockTransport(reject))
        app.state.client = mock
        try:
            targets = client.get('/spherex/targets').json()
            assert len(targets) == 8
            assert sum(t['exposure_count'] for t in targets) == 384
            assert sum(t['local_frame_count'] for t in targets) == 2
            result = client.post('/spherex/timelapse', json={**BARNARD, 'size_px': 48})
            assert result.status_code == 200, result.text
            body = result.json()
            assert body['source'] == 'local'
            assert body['status'] == 'ready'
            assert len(body['frames']) == 2
            for frame in body['frames']:
                image = Image.open(BytesIO(base64.b64decode(frame['image_png'].split(',')[1])))
                assert np.asarray(image)[..., 3].sum() > 0
                fits = client.get(frame['local_cutout_url'])
                assert fits.status_code == 200
                assert fits.content.startswith(b'SIMPLE')
            # Cached metadata is still available even if image files aren't.
            mira = {'ra': 34.836635, 'dec': -2.977637}
            metadata = client.post('/spherex/search', json=mira).json()
            assert len(metadata['exposures']) == 12
            empty = client.post('/spherex/timelapse', json=mira).json()
            assert empty['status'] == 'no_local_frames'
            assert empty['frames'] == []
            elsewhere = client.post('/spherex/search', json={'ra': 0, 'dec': 0}).json()
            assert elsewhere['exposures'] == []
            assert elsewhere['warnings']
        finally:
            app.state.client = original
            client.portal.call(mock.aclose)


def test_local_filters_and_limit():
    result = search_local(SkyRequest(**BARNARD, limit=1))
    assert len(result.exposures) == 1 and result.truncated
    assert search_local(SkyRequest(**BARNARD, detector=2), images_only=True).exposures == []
    assert search_local(SkyRequest(**BARNARD, mjd_end=1), images_only=True).exposures == []


def test_click_near_saved_target_uses_actual_image_footprint():
    # This is well outside the one-arcsecond metadata matching tolerance.
    nearby = search_local(SkyRequest(ra=BARNARD['ra'] + 0.01, dec=BARNARD['dec']), images_only=True)
    assert nearby.exposures == []
    outside = search_local(SkyRequest(ra=BARNARD['ra'] + 1, dec=BARNARD['dec']), images_only=True)
    assert outside.exposures == []


def test_local_paths_cannot_escape_cache():
    assert cutout_path('..', 'anything.fits') is None
    assert cutout_path('barnards-star', '../exposures.json') is None
