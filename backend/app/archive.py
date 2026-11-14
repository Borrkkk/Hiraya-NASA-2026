import asyncio
from io import BytesIO
import re
from urllib.parse import urlsplit, urlencode
from xml.etree import ElementTree
import httpx
import numpy as np
from astropy.io.votable import parse_single_table
from .models import Exposure, SearchResult

SIA_URL = 'https://irsa.ipac.caltech.edu/SIA'
MAX_BYTES = 32 * 1024 * 1024

class ArchiveError(Exception):
    pass

def validate_url(url):
    p = urlsplit(url)
    if (p.scheme != 'https' or p.netloc != 'irsa.ipac.caltech.edu' or
        not p.path.startswith('/ibe/data/spherex/') or not p.path.endswith('.fits') or
        p.query or p.fragment or '..' in p.path):
        raise ArchiveError('Archive returned an unsupported FITS URL')
    return url

async def download(client, url, params=None):
    try:
        async with client.stream('GET', url, params=params) as response:
            response.raise_for_status()
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > MAX_BYTES:
                    raise ArchiveError('Archive response exceeded 32 MiB limit')
            return bytes(body)
    except httpx.HTTPError as exc:
        raise ArchiveError('IRSA request failed; retry later') from exc

def parse_results(body, collection, request):
    try:
        root = ElementTree.fromstring(body)
        statuses = [n.attrib.get('value') for n in root.iter()
                    if n.tag.split('}')[-1] == 'INFO' and n.attrib.get('name') == 'QUERY_STATUS']
        if 'ERROR' in statuses:
            raise ArchiveError('IRSA rejected the search')
        table = parse_single_table(BytesIO(body)).to_table()
        results = []
        for row in table:
            url = str(row['access_url'])
            match = re.search(r'D([1-6])_spx_', url)
            if not match or int(match[1]) != request.detector:
                continue
            mjd = float(row['t_min'])
            if not np.isfinite(mjd):
                continue
            if request.mjd_start is not None and mjd < request.mjd_start:
                continue
            if request.mjd_end is not None and mjd > request.mjd_end:
                continue
            results.append(Exposure(id=str(row['obs_id']), collection=collection,
                                    detector=request.detector, mjd=mjd, fits_url=validate_url(url)))
        return results, 'OVERFLOW' in statuses
    except ArchiveError:
        raise
    except Exception as exc:
        raise ArchiveError('IRSA returned an invalid observation table') from exc

async def search(client, request):
    async def query(collection):
        params = {'COLLECTION': collection, 'POS': f'CIRCLE {request.ra} {request.dec} 0.000001', 'MAXREC': '10000'}
        if request.mjd_start is not None or request.mjd_end is not None:
            start = request.mjd_start if request.mjd_start is not None else '-Inf'
            end = request.mjd_end if request.mjd_end is not None else '+Inf'
            params['TIME'] = f'{start} {end}'
        return parse_results(await download(client, SIA_URL, params), collection, request)
    batches = await asyncio.gather(*(query(c) for c in request.collections))
    unique = {}
    for rows, _ in batches:
        for row in rows:
            unique.setdefault((row.id, row.detector), row)
    rows = sorted(unique.values(), key=lambda row: (row.mjd, row.id))
    overflow = any(flag for _, flag in batches)
    return SearchResult(exposures=rows[:request.limit], truncated=overflow or len(rows) > request.limit,
                        warnings=['IRSA search overflowed; narrow the date range for complete results.'] if overflow else [])

def cutout_url(exposure, request):
    size_deg = request.size_px * request.pixel_scale_arcsec / 3600 * 1.6
    return validate_url(exposure.fits_url) + '?' + urlencode({
        'center': f'{request.ra},{request.dec}', 'size': size_deg, 'gzip': 'false'})
