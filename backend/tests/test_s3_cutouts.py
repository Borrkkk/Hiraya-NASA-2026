from io import BytesIO

import httpx
import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS

from app.archive import ArchiveError
from app.explore.s3_cutouts import RangeFile, extract
from app.explore import s3_cutouts
import asyncio
from app.imaging import align
from app.models import TimelapseRequest


def test_range_cutout_preserves_compressed_flags_alignment_and_spectral_origin(monkeypatch):
    # Smaller synthetic images use proportionally smaller range blocks.
    monkeypatch.setattr(RangeFile, 'BLOCK', 64 * 1024)
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ['RA---TAN', 'DEC--TAN']
    wcs.wcs.crval = [269.4521, 4.6934]
    wcs.wcs.crpix = [257, 257]
    wcs.wcs.cdelt = [-6.15 / 3600, 6.15 / 3600]
    header = wcs.to_header()
    for axis in (1, 2):
        header[f'CRPIX{axis}W'] = 257.
        header[f'CRVAL{axis}W'] = 1.
        header[f'CDELT{axis}W'] = .001
        header[f'CTYPE{axis}W'] = 'LINEAR'
    image = np.arange(512**2, dtype=np.float32).reshape(512, 512)
    flags = np.zeros((512, 512), dtype=np.int32)
    flags[256, 256] = 1
    stream = BytesIO()
    fits.HDUList([fits.PrimaryHDU(), fits.ImageHDU(image, header, name='IMAGE'),
                  fits.CompImageHDU(flags, name='FLAGS', compression_type='RICE_1', tile_shape=(1, 512)),
                  fits.BinTableHDU.from_columns([], name='WCS-WAVE')]).writeto(stream)
    raw = stream.getvalue()
    requested = []
    def respond(request):
        start, end = map(int, request.headers['Range'].removeprefix('bytes=').split('-'))
        end = min(end, len(raw)-1)
        requested.append((start, end))
        return httpx.Response(206, headers={'Content-Range': f'bytes {start}-{end}/{len(raw)}'},
                              content=raw[start:end+1])
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        reader = RangeFile(client, 'https://example.test/image.fits')
        with extract(reader, 269.4521, 4.6934, .08) as hdus:
            assert hdus['IMAGE'].shape[0] < 60
            assert np.count_nonzero(hdus['FLAGS'].data) == 1
            cropped = BytesIO()
            hdus.writeto(cropped)
            old = WCS(header, key='W')
            new = WCS(hdus['IMAGE'].header, key='W')
            x, y = WCS(hdus['IMAGE'].header).all_world2pix(269.4521, 4.6934, 0)
            assert np.allclose(new.all_pix2world(x, y, 0), old.all_pix2world(256, 256, 0))
        req = TimelapseRequest(ra=269.4521, dec=4.6934, size_px=16)
        assert np.allclose(align(raw, req), align(cropped.getvalue(), req), equal_nan=True)
        assert reader.transferred < len(raw) / 2
        assert len(requested) == len(set(requested))


def test_range_reader_rejects_server_ignoring_range():
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b'wrong'))) as client:
        with pytest.raises(ArchiveError, match='byte range'):
            RangeFile(client, 'https://example.test/image.fits').read(80)


def test_rejected_footprint_metadata_is_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(s3_cutouts, 'CACHE', tmp_path)
    calls = []
    def reject(*args):
        calls.append(args)
        raise ValueError('Indexed exposure does not cover target')
    monkeypatch.setattr(s3_cutouts, '_metadata', reject)
    async def check():
        for _ in range(2):
            with pytest.raises(ValueError, match='does not cover'):
                await s3_cutouts.metadata('test-url', 10, 20)
    asyncio.run(check())
    assert len(calls) == 1
