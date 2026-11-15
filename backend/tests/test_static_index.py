import json
import struct

import pytest

from app.explore.static_index import indexed_exposures
from app.explore.s3_store import s3_url
from app.archive import ArchiveError
import asyncio
from io import BytesIO
import httpx
import numpy as np
from astropy.io import fits
from app.explore import s3_store
from app.explore import sources


def test_index_selects_all_detectors_and_handles_ra_wrap(tmp_path, monkeypatch):
    (tmp_path / 'tiles').mkdir()
    rows = b''.join(struct.pack('<fffhBBHHHH', 359.9, 0, 100, 0, d, 1, 0, 42, 0, 0)
                    for d in range(1, 7))
    (tmp_path / 'tiles' / '18_71.bin').write_bytes(rows)
    (tmp_path / 'index.json').write_text(json.dumps(dict(
        rowBytes=24, tileDeg=5, mjd0=60000, tiles={'18_71': 6},
        folders=['qr3/2026W01_1A'], versions=['v1'])))
    monkeypatch.setenv('SPHEREX_INDEX_DIR', str(tmp_path))
    result = indexed_exposures(.1, 0)
    assert [e.detector for e in result] == list(range(1, 7))
    assert result[0].mjd == 60100
    assert result[0].id == '2026W01_1A_0042_1'
    assert indexed_exposures(180, 0) == []


def test_s3_mapping_rejects_untrusted_urls():
    url = 'https://irsa.ipac.caltech.edu/ibe/data/spherex/qr3/level2/test.fits'
    assert s3_url(url) == 'https://nasa-irsa-spherex.s3.amazonaws.com/qr3/level2/test.fits'
    with pytest.raises(ArchiveError):
        s3_url('https://example.com/test.fits')


def test_s3_original_is_validated_and_cached(tmp_path, monkeypatch):
    stream = BytesIO()
    fits.HDUList([fits.PrimaryHDU(), *[
        fits.ImageHDU(np.zeros((2, 2)), name=name)
        for name in ('IMAGE', 'FLAGS', 'WCS-WAVE')]]).writeto(stream)
    calls = []
    def respond(request):
        calls.append(request.url)
        return httpx.Response(200, content=stream.getvalue())
    monkeypatch.setattr(s3_store, 'CACHE', tmp_path)
    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            url = 'https://irsa.ipac.caltech.edu/ibe/data/spherex/qr3/level2/test.fits'
            first = await s3_store.original(client, url)
            assert await s3_store.original(client, url) == first
            assert first.read_bytes() == stream.getvalue()
    asyncio.run(check())
    assert len(calls) == 1
    assert calls[0].host == 'nasa-irsa-spherex.s3.amazonaws.com'


def test_bad_s3_response_is_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(s3_store, 'CACHE', tmp_path)
    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda request: httpx.Response(404))) as client:
            with pytest.raises(ArchiveError, match='404'):
                await s3_store.original(client, 'https://irsa.ipac.caltech.edu/ibe/data/spherex/qr3/level2/missing.fits')
    asyncio.run(check())
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('indexed', [True, False])
def test_index_mode_does_not_use_partial_bundled_target(monkeypatch, indexed):
    monkeypatch.setattr(sources, 'SHOTS', {})
    monkeypatch.setattr(sources, '_locks', {})
    if indexed:
        monkeypatch.setenv('SPHEREX_INDEX_DIR', 'installed-index')
    else:
        monkeypatch.delenv('SPHEREX_INDEX_DIR', raising=False)
    bundled = ('detector-1-only',)
    complete = tuple(range(1, 7))
    monkeypatch.setattr(sources, 'local_shots', lambda *args: bundled)
    async def discover(*args):
        assert indexed, 'Offline mode should retain the bundled data'
        return complete
    monkeypatch.setattr(sources, 'live_shots', discover)
    asyncio.run(sources.ensure_shots(None, 269.4521, 4.6934))
    assert next(iter(sources.SHOTS.values())) == (complete if indexed else bundled)
