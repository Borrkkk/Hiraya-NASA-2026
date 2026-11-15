"""Install an exposure index snapshot from a configured HTTPS directory."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import re

import httpx

DEST = Path(__file__).resolve().parents[2] / '.cache' / 'exposure-index'


async def main(base):
    # The source must be an immutable snapshot directory, not a moving version.
    if not base.startswith('https://'):
        raise ValueError('Index source must use HTTPS')
    base = base.rstrip('/')
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        response = await client.get(f'{base}/index.json')
        response.raise_for_status()
        meta = response.json()
        snapshot = hashlib.sha256(response.content).hexdigest()
        destination = DEST / snapshot
        (destination / 'tiles').mkdir(parents=True, exist_ok=True)
        sem = asyncio.Semaphore(4)

        async def tile(name):
            if not re.fullmatch(r'\d+_\d+', name):
                raise ValueError('Invalid tile name')
            path = destination / 'tiles' / f'{name}.bin'
            if path.exists() and path.stat().st_size == meta['tiles'][name] * meta['rowBytes']:
                return
            async with sem:
                for attempt in range(3):
                    try:
                        data = await client.get(f'{base}/tiles/{name}.bin')
                        data.raise_for_status()
                        if len(data.content) != meta['tiles'][name] * meta['rowBytes']:
                            raise ValueError(f'Incomplete tile {name}')
                        path.write_bytes(data.content)
                        return
                    except httpx.HTTPError:
                        if attempt == 2:
                            raise
                        await asyncio.sleep(2 ** attempt)

        await asyncio.gather(*(tile(name) for name in meta['tiles']))
        (destination / 'index.json').write_text(json.dumps(meta))
        print(f'Installed {meta["total"]} records; index date: {meta["updated"]}')
        print(f'$env:SPHEREX_INDEX_DIR = "{destination}"')
        print('$env:SPHEREX_IMAGE_SOURCE = "s3"')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, help='HTTPS directory containing an immutable index.json and tiles/')
    asyncio.run(main(parser.parse_args().source))
