"""Read FITS sections from S3 using bounded HTTP ranges and Astropy's decoder."""
import asyncio
import hashlib
import io
import json
import logging
from pathlib import Path
import re
import ssl
import time
import uuid

import httpx
import numpy as np
import truststore
from astropy.io import fits
from astropy.wcs import WCS, NoConvergence
from astropy import log as astropy_log

from ..archive import ArchiveError
from .s3_store import s3_url

log = logging.getLogger(__name__)
CACHE = Path(__file__).resolve().parents[2] / '.cache' / 's3-cutouts'
_locks = {}


class _SpectralSipInfo(logging.Filter):
    def filter(self, record):
        return 'Inconsistent SIP distortion information' not in record.getMessage()


astropy_log.addFilter(_SpectralSipInfo())


class RangeFile(io.RawIOBase):
    """Seekable reader; FITS headers and compressed sections request small blocks."""
    BLOCK = 256 * 1024

    def __init__(self, client, url):
        super().__init__()
        self.client, self.url = client, url
        self.position = 0
        self.blocks = {}
        self.transferred = 0
        self.length = None

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        if whence == 2:
            if self.length is None:
                self._block(0)
            offset += self.length
        elif whence == 1:
            offset += self.position
        elif whence != 0:
            raise ValueError('Invalid seek mode')
        if offset < 0:
            raise ValueError('Negative seek')
        self.position = offset
        return offset

    def _block(self, number):
        if number in self.blocks:
            return self.blocks[number]
        start = number * self.BLOCK
        if self.length is not None and start >= self.length:
            return b''
        for attempt in range(3):
            try:
                with self.client.stream('GET', self.url, headers={
                    'Range': f'bytes={start}-{start + self.BLOCK - 1}',
                    'Accept-Encoding': 'identity',
                }) as response:
                    response.raise_for_status()
                    match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', response.headers.get('Content-Range', ''))
                    if response.status_code != 206 or not match or int(match[1]) != start:
                        raise ArchiveError('S3 did not honor the requested byte range')
                    payload = bytearray()
                    for chunk in response.iter_bytes():
                        payload.extend(chunk)
                        if len(payload) > self.BLOCK:
                            raise ArchiveError('S3 range response exceeded requested size')
                    if len(payload) != int(match[2]) - start + 1:
                        raise ArchiveError('Incomplete S3 byte range')
                    self.length = int(match[3])
                    self.transferred += len(payload)
                    self.blocks[number] = bytes(payload)
                    return self.blocks[number]
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in (408, 429) and exc.response.status_code < 500:
                    raise ArchiveError(f'S3 returned HTTP {exc.response.status_code}') from exc
                if attempt == 2:
                    raise ArchiveError('S3 range request failed after retries') from exc
            except httpx.TransportError as exc:
                if attempt == 2:
                    raise ArchiveError('S3 range request failed after retries') from exc
            time.sleep(2 ** attempt)

    def read(self, size=-1):
        if size is None or size < 0:
            if self.length is None:
                self._block(0)
            size = max(0, self.length - self.position)
        chunks = []
        while size:
            number, offset = divmod(self.position, self.BLOCK)
            block = self._block(number)
            chunk = block[offset:offset + size]
            if not chunk:
                break
            chunks.append(chunk)
            size -= len(chunk)
            self.position += len(chunk)
        return b''.join(chunks)


def extract(reader, ra, dec, size_deg, science=True):
    """Keep the local celestial and spectral WCS consistent after cropping."""
    with fits.open(reader, memmap=False, lazy_load_hdus=True) as hdus:
        image = hdus['IMAGE']
        source = WCS(image.header, hdus, naxis=2).celestial
        target = WCS(naxis=2)
        target.wcs.ctype = ['RA---TAN', 'DEC--TAN']
        target.wcs.crval = [ra, dec]
        target.wcs.crpix = [5, 5]
        target.wcs.cdelt = [-size_deg / 8, size_deg / 8]
        gy, gx = np.indices((9, 9))
        sky = target.all_pix2world(gx, gy, 0)
        try:
            x, y = source.all_world2pix(*sky, 0)
        except NoConvergence as exc:
            raise ValueError('Indexed footprint could not be projected into this image') from exc
        if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
            raise ValueError('Cannot project requested cutout')
        height, width = image.shape
        x0, x1 = max(0, int(np.floor(x.min())) - 2), min(width, int(np.ceil(x.max())) + 3)
        y0, y1 = max(0, int(np.floor(y.min())) - 2), min(height, int(np.ceil(y.max())) + 3)
        if x0 >= x1 or y0 >= y1:
            raise ValueError('Indexed exposure does not cover this area')
        output = [fits.PrimaryHDU(header=hdus[0].header.copy())]
        for name in (('IMAGE', 'FLAGS', 'VARIANCE', 'ZODI') if science else ('IMAGE', 'FLAGS')):
            if name not in hdus:
                if name in ('IMAGE', 'FLAGS'):
                    raise ValueError(f'FITS missing {name}')
                continue
            hdu = hdus[name]
            header = hdu.header.copy()
            # Primary, pixel, and spectral WCSes all use the original pixel origin.
            for keyword in list(header):
                if re.fullmatch(r'CRPIX[12][A-Z]?', keyword):
                    header[keyword] -= x0 if keyword[5] == '1' else y0
            data = np.array(hdu.section[y0:y1, x0:x1], copy=True)
            output.append(fits.ImageHDU(data=data, header=header, name=name))
        # Preserve the wavelength lookup table without reading the full images
        # or the unrelated spatial PSF grid (Explore does not use that grid).
        if 'WCS-WAVE' not in hdus:
            raise ValueError('FITS missing wavelength lookup table')
        output.append(hdus['WCS-WAVE'].copy())
        if science and 'EPSF' in hdus:
            output.append(hdus['EPSF'].copy())
        return fits.HDUList(output)


def _create(url, ra, dec, size_deg, path, science=False):
    temporary = path.with_suffix(f'.{uuid.uuid4().hex}.part')
    try:
        tls = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        with httpx.Client(verify=tls, timeout=httpx.Timeout(30, connect=10)) as client:
            reader = RangeFile(client, s3_url(url))
            with extract(reader, ra, dec, size_deg, science=science) as cutout:
                cutout.writeto(temporary)
            log.info('S3 cutout %s: %.2f MiB transferred', url, reader.transferred / 1024**2)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def cached_path(url, ra, dec, size_deg, science=False):
    identity = f'v3:{science}:{url}:{ra:.5f}:{dec:.5f}:{size_deg}'
    return CACHE / f'{hashlib.sha256(identity.encode()).hexdigest()}.fits'


async def cutout(url, ra, dec, size_deg, science=False):
    path = cached_path(url, ra, dec, size_deg, science)
    identity = str(path)
    async with _locks.setdefault(identity, asyncio.Lock()):
        if not path.exists():
            CACHE.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(_create, url, ra, dec, size_deg, path, science)
    return path


def seed_preview(wide_path, url, ra, dec, size_deg):
    """Derive a smaller display cutout locally rather than re-downloading it."""
    path = cached_path(url, ra, dec, size_deg)
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f'.{uuid.uuid4().hex}.part')
    try:
        with Path(wide_path).open('rb') as reader:
            with extract(reader, ra, dec, size_deg, science=False) as hdus:
                hdus.writeto(temporary)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def _metadata(url, ra, dec):
    """Read headers and the wavelength table; never access image pixel data."""
    tls = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    with httpx.Client(verify=tls, timeout=httpx.Timeout(30, connect=10)) as client:
        reader = RangeFile(client, s3_url(url))
        reader.BLOCK = 16 * 1024
        with fits.open(reader, memmap=False, lazy_load_hdus=True) as hdus:
            header = hdus['IMAGE'].header
            source = WCS(header, hdus, naxis=2).celestial
            try:
                x, y = source.all_world2pix(ra, dec, 0)
            except NoConvergence as exc:
                raise ValueError('Indexed exposure does not cover target') from exc
            if not (0 <= x < header['NAXIS1'] and 0 <= y < header['NAXIS2']):
                raise ValueError('Indexed exposure does not cover target')
            spectral = WCS(header, hdus, key='W')
            spectral.sip = None
            wave, _ = spectral.all_pix2world([x], [y], 0)
            wavelength = float(wave[0])
            if not np.isfinite(wavelength):
                raise ValueError('Invalid wavelength metadata')
            return {'wavelength': wavelength}


async def metadata(url, ra, dec):
    identity = f'metadata-v1:{url}:{ra:.5f}:{dec:.5f}'
    path = CACHE / f'{hashlib.sha256(identity.encode()).hexdigest()}.json'
    async with _locks.setdefault(identity, asyncio.Lock()):
        if path.exists():
            result = json.loads(path.read_text())
            if 'unusable' in result:
                raise ValueError(result['unusable'])
            return result
        try:
            result = await asyncio.to_thread(_metadata, url, ra, dec)
        except ValueError as exc:
            # Immutable exposure geometry/wavelength failures are safe to
            # remember. Transport failures must remain retryable.
            result = {'unusable': str(exc)}
        CACHE.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(f'.{uuid.uuid4().hex}.part')
        try:
            temporary.write_text(json.dumps(result))
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        if 'unusable' in result:
            raise ValueError(result['unusable'])
        return result
