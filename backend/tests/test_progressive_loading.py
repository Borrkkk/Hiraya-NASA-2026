import asyncio
from pathlib import Path

import numpy as np

from app.explore import frames, sources
from app.explore.common import Shot
from app.models import Exposure


def test_area_metadata_never_downloads_or_aligns_pixels(monkeypatch, tmp_path):
    monkeypatch.setenv('SPHEREX_IMAGE_SOURCE', 's3')
    monkeypatch.setattr(sources, 'CACHE', tmp_path)
    exposure = Exposure(id='epoch1', collection='spherex_qr3', detector=1, mjd=61000,
                        fits_url='https://irsa.ipac.caltech.edu/ibe/data/spherex/qr3/level2/test.fits')
    monkeypatch.setattr(sources, 'indexed_exposures', lambda *args: [exposure])
    async def metadata(*args):
        return {'wavelength': 1.0}
    async def forbidden(*args):
        raise AssertionError('Area discovery must not fetch pixels')
    def no_alignment(*args):
        raise AssertionError('Area metadata must not align image pixels')
    monkeypatch.setattr(sources, 's3_metadata', metadata)
    monkeypatch.setattr(sources, 's3_cutout', forbidden)
    monkeypatch.setattr(sources, 'download', forbidden)
    monkeypatch.setattr(frames, 'aligned', no_alignment)
    shots = asyncio.run(sources.live_shots(None, 269.4521, 4.6934))
    assert len(shots) == 1
    assert not shots[0].path.exists()
    monkeypatch.setattr(frames, 'shots_at', lambda *args: shots)
    monkeypatch.setattr(frames, 'epochs_at', lambda *args: [('epoch1', 61000)])
    monkeypatch.setattr(frames, 'shot_for', lambda ra, dec, epoch, band: shots[0] if band == 'starlight' else None)
    area = frames.build_area(269.4521, 4.6934)
    assert area['epochs'][0]['bands'] == ['starlight']
    assert 'coverage' not in area['epochs'][0]
    assert area['bands'][0]['empty'] is None


def test_first_frame_does_not_read_other_epochs(monkeypatch, tmp_path):
    first = Shot('first', 1, 61000, tmp_path / 'first.fits', 1.0)
    first.path.touch()
    monkeypatch.setattr(frames, 'FRAME_CACHE', tmp_path / 'frames')
    second = Shot('second', 1, 61001, tmp_path / 'missing.fits', 1.0)
    calls = []
    monkeypatch.setattr(frames, 'shot_for', lambda *args: first)
    monkeypatch.setattr(frames, 'shots_at', lambda *args: (first, second))
    monkeypatch.setattr(frames, '_stretches', {})
    def aligned(path, *args):
        calls.append(path)
        assert path == str(first.path)
        return np.arange(128**2).reshape(128, 128).astype(float)
    monkeypatch.setattr(frames, 'aligned', aligned)
    png = frames.frame_png(10, 20, 'first', 'starlight')
    assert png.startswith(b'\x89PNG')
    assert calls == [str(first.path)]
    # Subsequent frames share the first frame's scale, not a per-frame normalization.
    assert frames._stretch(10, 20, 'starlight', np.ones((128, 128))*1e9) == frames._stretches[(10, 20, 'starlight')]
    # Persistent PNGs work after a server restart without another alignment.
    monkeypatch.setattr(frames, '_stretches', {})
    monkeypatch.setattr(frames, 'aligned', lambda *args: (_ for _ in ()).throw(AssertionError('Unexpected re-render')))
    assert frames.frame_png(10, 20, 'first', 'starlight') == png


def test_frame_downloads_only_the_requested_exposure(monkeypatch, tmp_path):
    monkeypatch.setenv('SPHEREX_IMAGE_SOURCE', 's3')
    monkeypatch.setattr(sources, 'CACHE', tmp_path)
    shot = Shot('first', 1, 61000, tmp_path / 'first.fits', 1.0,
                'https://irsa.ipac.caltech.edu/ibe/data/spherex/qr3/level2/test.fits')
    calls = []
    async def download(url, ra, dec, size, science=False):
        calls.append(url)
        path = tmp_path / 'download.fits'
        path.write_bytes(b'test')
        return path
    monkeypatch.setattr(sources, 's3_cutout', download)
    result = asyncio.run(sources.ensure_cutout(None, shot, 10, 20, 0))
    assert result == shot.path and result.read_bytes() == b'test'
    assert calls == [shot.fits_url]
