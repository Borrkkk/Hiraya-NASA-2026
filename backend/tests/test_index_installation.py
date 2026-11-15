from io import BytesIO
import json
import struct
import tarfile

import pytest

from app.explore import static_index
from app.explore.import_index_archive import install


def archive_at(tmp_path, truncate=False):
    metadata = dict(rowBytes=24, tileDeg=5, mjd0=60000, total=6, updated='2026-11-10T00:00:00Z',
                    tiles={'18_71': 6}, folders=['qr3/2026W01_1A'], versions=['v1'])
    rows = b''.join(struct.pack('<fffhBBHHHH', 359.9, 0, 100, 0, d, 1, 0, 42, 0, 0) for d in range(1, 7))
    if truncate:
        rows = rows[:-24]
    path = tmp_path / 'snapshot.tar.gz'
    with tarfile.open(path, 'w:gz') as bundle:
        for name, data in [('index.json', json.dumps(metadata).encode()), ('tiles/18_71.bin', rows)]:
            member = tarfile.TarInfo('project-commit/data/' + name)
            member.size = len(data)
            bundle.addfile(member, BytesIO(data))
    return path


def test_valid_archive_activates_all_sky_index(tmp_path, monkeypatch):
    root = tmp_path / 'installed'
    directory, source = install(archive_at(tmp_path), 'https://example.com/pinned-commit', root)
    monkeypatch.setattr(static_index, 'INDEX_ROOT', root)
    monkeypatch.delenv('SPHEREX_INDEX_DIR', raising=False)
    monkeypatch.delenv('SPHEREX_IMAGE_SOURCE', raising=False)
    assert static_index.index_directory() == directory
    assert static_index.image_source() == 's3'
    assert [e.detector for e in static_index.indexed_exposures(.1, 0)] == list(range(1, 7))
    assert source['total_records'] == 6
    monkeypatch.setenv('SPHEREX_IMAGE_SOURCE', 'irsa')
    assert static_index.image_source() == 'irsa'
    monkeypatch.setenv('SPHEREX_INDEX_DIR', str(tmp_path / 'override'))
    assert static_index.index_directory() == tmp_path / 'override'


def test_invalid_archive_does_not_replace_active_snapshot(tmp_path):
    root = tmp_path / 'installed'
    install(archive_at(tmp_path), 'first', root)
    original = (root / 'active.json').read_bytes()
    with pytest.raises(ValueError, match='Invalid index tile'):
        install(archive_at(tmp_path, truncate=True), 'broken', root)
    assert (root / 'active.json').read_bytes() == original


def test_active_snapshot_cannot_escape_index_root(tmp_path, monkeypatch):
    monkeypatch.setattr(static_index, 'INDEX_ROOT', tmp_path)
    monkeypatch.delenv('SPHEREX_INDEX_DIR', raising=False)
    (tmp_path / 'active.json').write_text(json.dumps({'snapshot': '../../escape'}))
    with pytest.raises(ValueError, match='Invalid active'):
        static_index.index_directory()


def test_bundled_index_works_without_local_cache(tmp_path, monkeypatch):
    bundled, _ = install(archive_at(tmp_path), 'bundled', tmp_path / 'bundle')
    monkeypatch.setattr(static_index, 'BUNDLED_INDEX', bundled)
    monkeypatch.delenv('SPHEREX_INDEX_DIR', raising=False)
    monkeypatch.delenv('SPHEREX_IMAGE_SOURCE', raising=False)
    assert static_index.index_directory() == bundled
    assert static_index.image_source() == 's3'
    assert len(static_index.indexed_exposures(.1, 0)) == 6
    installed, _ = install(archive_at(tmp_path), 'local', static_index.INDEX_ROOT)
    assert static_index.index_directory() == installed
