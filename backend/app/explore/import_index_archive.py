"""Install just the metadata index from a pinned GitHub repository tarball.

Every tile is validated before activating the snapshot. No archive paths are
extracted directly, and no upstream executable source is installed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tarfile

from .static_index import INDEX_ROOT, ROW


def install(archive: Path, origin: str, root: Path = INDEX_ROOT):
    with tarfile.open(archive, 'r:gz') as bundle:
        indexes = [m for m in bundle.getmembers() if m.name.endswith('/data/index.json') and m.isfile()]
        if len(indexes) != 1 or indexes[0].size > 2_000_000:
            raise ValueError('Expected exactly one bounded data/index.json')
        raw = bundle.extractfile(indexes[0]).read()
        meta = json.loads(raw)
        if meta['rowBytes'] != ROW.size or sum(meta['tiles'].values()) != meta['total']:
            raise ValueError('Unsupported or inconsistent index metadata')
        snapshot = hashlib.sha256(raw).hexdigest()
        destination = root / snapshot
        tiles = destination / 'tiles'
        tiles.mkdir(parents=True, exist_ok=True)
        prefix = indexes[0].name.removesuffix('index.json')
        for name, count in meta['tiles'].items():
            if not re.fullmatch(r'\d+_\d+', name) or not isinstance(count, int) or count < 0:
                raise ValueError('Invalid tile metadata')
            member = bundle.getmember(f'{prefix}tiles/{name}.bin')
            if not member.isfile() or member.size != count * ROW.size:
                raise ValueError(f'Invalid index tile: {name}')
            content = bundle.extractfile(member).read()
            if len(content) != member.size:
                raise ValueError(f'Truncated index tile: {name}')
            pending = tiles / f'{name}.bin.part'
            pending.write_bytes(content)
            pending.replace(tiles / f'{name}.bin')
        (destination / 'index.json').write_bytes(raw)
        provenance = {'origin': origin, 'snapshot': snapshot, 'index_updated': meta['updated'],
                      'total_records': meta['total'], 'tile_count': len(meta['tiles']),
                      'index_sha256': snapshot, 'metadata_only': True}
        (destination / 'source.json').write_text(json.dumps(provenance, indent=2) + '\n')
        pending = root / 'active.json.part'
        pending.write_text(json.dumps({'snapshot': snapshot, 'image_source': 's3'}, indent=2) + '\n')
        pending.replace(root / 'active.json')
    return destination, provenance


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--origin', required=True, help='Immutable source URL or commit reference')
    args = parser.parse_args()
    directory, provenance = install(args.archive, args.origin)
    print(json.dumps({**provenance, 'directory': str(directory)}, indent=2))
