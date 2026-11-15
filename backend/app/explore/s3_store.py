"""Download original FITS files from the public bucket, once per exposure."""
import asyncio
import hashlib
from pathlib import Path
import uuid

import httpx
from astropy.io import fits

from ..archive import ArchiveError, validate_url

CACHE = Path(__file__).resolve().parents[2] / '.cache' / 'originals'
_locks = {}


def s3_url(url):
    validated = validate_url(url)
    return validated.replace('https://irsa.ipac.caltech.edu/ibe/data/spherex/',
                             'https://nasa-irsa-spherex.s3.amazonaws.com/', 1)


def validate_file(path):
    with fits.open(path, memmap=False) as hdus:
        for name in ('IMAGE', 'FLAGS', 'WCS-WAVE'):
            if name not in hdus:
                raise ValueError(f'S3 FITS missing {name}')


async def original(client, url):
    remote = s3_url(url)
    path = CACHE / f'{hashlib.sha256(remote.encode()).hexdigest()}.fits'
    async with _locks.setdefault(remote, asyncio.Lock()):
        if path.exists():
            return path
        CACHE.mkdir(parents=True, exist_ok=True)
        for attempt in range(3):
            temporary = path.with_suffix(f'.{uuid.uuid4().hex}.part')
            try:
                async with client.stream('GET', remote) as response:
                    response.raise_for_status()
                    size = 0
                    with temporary.open('wb') as output:
                        async for chunk in response.aiter_bytes():
                            size += len(chunk)
                            if size > 128 * 1024 * 1024:
                                raise ArchiveError('S3 image exceeds 128 MiB limit')
                            output.write(chunk)
                await asyncio.to_thread(validate_file, temporary)
                temporary.replace(path)
                return path
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in (408, 429) and exc.response.status_code < 500:
                    raise ArchiveError(f'S3 returned HTTP {exc.response.status_code}') from exc
                error = exc
            except (httpx.TransportError, ValueError, OSError) as exc:
                error = exc
            finally:
                temporary.unlink(missing_ok=True)
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
        raise ArchiveError(f'S3 download failed after 3 attempts: {error}')
