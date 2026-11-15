"""Refresh recommended fields from NASA FITS headers and merge one binary sky index.

The upstream index is a discovery seed, not the source of the new geometry.
DR1 alternatives are discovered from NASA's public bucket listings. Pixel arrays
are never read. Failed refreshes retain the original index entries and are reported.
"""
import argparse
import asyncio
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import re
import ssl
from xml.etree import ElementTree

import httpx
import numpy as np
import truststore
from astropy.io import fits
from astropy.wcs import WCS

from .index_targets import ROOT, target_fields
from .static_index import INDEX_ROOT, ROW, index_directory, indexed_exposures
from ..models import Exposure

BUCKET = 'https://nasa-irsa-spherex.s3.amazonaws.com'
ARCHIVE = 'https://irsa.ipac.caltech.edu/ibe/data/spherex/'
WORK = INDEX_ROOT / 'recommended-refresh'
URI = re.compile(r'/(dr\d+|qr\d+)/level2/([^/]+)/([^/]+)/([1-6])/([^/]+\.fits)$')


def version_rank(value):
    match = re.search(r'v(\d+)-(\d{4})-(\d+)$', value)
    return tuple(map(int, match.groups())) + ('retry' in value,) if match else (0, 0, 0, False)


def tile_key(ra, dec, step):
    band = min(int((dec + 90) // step), int(180 / step) - 1)
    low, high = -90 + band * step, -90 + (band + 1) * step
    edge = 0 if low <= 0 <= high else min(abs(low), abs(high))
    count = max(1, math.ceil(360 * math.cos(math.radians(edge)) / step))
    return f'{band}_{int((ra % 360) / 360 * count) % count}'


def parse_header(raw, url):
    stream = BytesIO(raw)
    fits.Header.fromfile(stream)
    header = fits.Header.fromfile(stream)
    match = URI.search(url)
    if not match:
        raise ValueError('Unrecognized SPHEREx path')
    release, folder, version, detector, _ = match.groups()
    obs = str(header['OBSID'])
    if obs[:10] != folder or int(header['DETECTOR']) != int(detector):
        raise ValueError('FITS identity differs from its URL')
    wcs = WCS(header, naxis=2).celestial
    cx, cy = (header['NAXIS1'] - 1) / 2, (header['NAXIS2'] - 1) / 2
    ra, dec = map(float, wcs.all_pix2world(cx, cy, 0))
    matrix = wcs.pixel_scale_matrix
    angle = math.degrees(math.atan2(matrix[1, 0], matrix[0, 0]))
    mjd = float(header['MJD-BEG'])
    if not all(map(math.isfinite, [ra, dec, angle, mjd])):
        raise ValueError('Non-finite header geometry')
    return {'release': release, 'folder': folder, 'version': version, 'detector': int(detector),
            'sequence': int(obs.split('_')[-2]), 'sub': int(obs.split('_')[-1]), 'obs_id': obs,
            'ra': ra, 'dec': dec, 'angle': angle, 'mjd': mjd, 'fits_url': url}


async def header_record(client, url):
    cache = WORK / 'headers' / (hashlib.sha256(url.encode()).hexdigest() + '.json')
    if cache.exists():
        return json.loads(cache.read_text())
    remote = url.replace(ARCHIVE, BUCKET + '/', 1)
    response = await client.get(remote, headers={'Range': 'bytes=0-57599', 'Accept-Encoding': 'identity'})
    response.raise_for_status()
    if response.status_code != 206 or not response.headers.get('Content-Range', '').startswith('bytes 0-'):
        raise ValueError('Archive did not honor bounded header request')
    if len(response.content) > 57600:
        raise ValueError('Header response exceeded requested size')
    record = parse_header(response.content, url)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(record))
    return record


async def dr1_versions(client, folder):
    cache = WORK / 'folders' / f'{folder}.json'
    if cache.exists():
        return json.loads(cache.read_text())
    response = await client.get(BUCKET + '/', params={'list-type': '2', 'prefix': f'dr1/level2/{folder}/', 'delimiter': '/'})
    response.raise_for_status()
    tree = ElementTree.fromstring(response.content)
    values = [node.text.rstrip('/').split('/')[-1] for node in tree.findall('{*}CommonPrefixes/{*}Prefix')]
    values = sorted(values, key=version_rank, reverse=True)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(values))
    return values


def merge_records(base, additions, provenance, output_root=INDEX_ROOT):
    """Merge by physical observation/detector; refresh DR1 supersedes QR2."""
    meta = json.loads((base / 'index.json').read_text())
    folders, versions = list(meta['folders']), list(meta['versions'])
    folder_ids, version_ids = {v: i for i, v in enumerate(folders)}, {v: i for i, v in enumerate(versions)}
    fresh = {}
    for record in additions:
        identity = (record['obs_id'], record['detector'])
        rank = (record['release'].startswith('dr'), version_rank(record['version']))
        old = fresh.get(identity)
        if old is None or rank > (old['release'].startswith('dr'), version_rank(old['version'])):
            fresh[identity] = record
    tiles = defaultdict(bytearray)
    emitted, replaced = set(), 0

    def emit(record):
        folder = record['release'] + '/' + record['folder']
        if folder not in folder_ids:
            folder_ids[folder] = len(folders)
            folders.append(folder)
        if record['version'] not in version_ids:
            version_ids[record['version']] = len(versions)
            versions.append(record['version'])
        values = (record['ra'], record['dec'], record['mjd'] - meta['mjd0'], round(record['angle'] * 100),
                  record['detector'], record['sub'], folder_ids[folder], record['sequence'], version_ids[record['version']], 0)
        tiles[tile_key(record['ra'], record['dec'], meta['tileDeg'])].extend(ROW.pack(*values))

    for tile in meta['tiles']:
        raw = (base / 'tiles' / f'{tile}.bin').read_bytes()
        for offset in range(0, len(raw), ROW.size):
            row = ROW.unpack_from(raw, offset)
            folder = meta['folders'][row[6]].split('/')[1]
            identity = (f'{folder}_{row[7]:04d}_{row[5]}', row[4])
            if identity in fresh:
                replaced += 1
                if identity not in emitted:
                    emit(fresh[identity])
                    emitted.add(identity)
            else:
                tiles[tile].extend(raw[offset:offset + ROW.size])
    for identity, record in fresh.items():
        if identity not in emitted:
            emit(record)
    counts = {name: len(content) // ROW.size for name, content in sorted(tiles.items())}
    combined = {**meta, 'folders': folders, 'versions': versions, 'tiles': counts, 'total': sum(counts.values()),
                'updated': datetime.now(timezone.utc).isoformat(), 'upstream_updated': meta['updated'],
                'combined': {**provenance, 'refreshed_records': len(fresh), 'replaced_rows': replaced,
                             'additional_records': len(set(fresh) - emitted)}}
    raw_meta = json.dumps(combined, sort_keys=True, separators=(',', ':')).encode()
    snapshot = hashlib.sha256(raw_meta).hexdigest()
    destination = output_root / snapshot
    (destination / 'tiles').mkdir(parents=True, exist_ok=True)
    for name, content in tiles.items():
        (destination / 'tiles' / f'{name}.bin').write_bytes(content)
    (destination / 'index.json').write_bytes(raw_meta)
    source = {**combined['combined'], 'snapshot': snapshot, 'upstream_updated': meta['updated'],
              'total_records': combined['total'], 'index_updated': combined['updated'], 'tile_count': len(counts)}
    (destination / 'source.json').write_text(json.dumps(source, indent=2) + '\n')
    pending = output_root / 'active.json.part'
    pending.write_text(json.dumps({'snapshot': snapshot, 'image_source': 's3'}) + '\n')
    pending.replace(output_root / 'active.json')
    return destination, source


async def main(concurrency=12):
    base = index_directory()
    if base is None:
        raise ValueError('Install the upstream snapshot first')
    original_meta = json.loads((base / 'index.json').read_text())
    if original_meta.get('combined', {}).get('upstream_snapshot'):
        base = INDEX_ROOT / original_meta['combined']['upstream_snapshot']
    fields = [field for field in target_fields() if field['recommended']]
    candidates, associations = {}, defaultdict(set)
    for field in fields:
        for exposure in indexed_exposures(field['ra'], field['dec']):
            candidates[exposure.fits_url] = exposure
            associations[exposure.fits_url].add(field['id'])
    # Also include our independently saved IRSA metadata, not just upstream seeds.
    for path in (ROOT / 'data/targets').glob('*/exposures.json'):
        payload = json.loads(path.read_text())
        for row in payload['exposures']:
            url = row['access_url']
            candidates[url] = Exposure(id=row['obs_id'], detector=row['detector'], mjd=row['mjd_start'],
                                       collection=row['collection'], fits_url=url)
            associations[url].add('saved-' + payload['target']['id'])
    folders = sorted({exposure.id[:10] for exposure in candidates.values() if exposure.collection == 'spherex_qr2'})
    semaphore = asyncio.Semaphore(concurrency)
    tls = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    failures, records, progress = [], [], 0
    async with httpx.AsyncClient(verify=tls, timeout=30, limits=httpx.Limits(max_connections=concurrency), follow_redirects=False) as client:
        async def folder_versions(folder):
            async with semaphore:
                try:
                    return folder, await dr1_versions(client, folder)
                except (httpx.HTTPError, ValueError, ElementTree.ParseError) as exc:
                    failures.append({'folder': folder, 'error': str(exc)})
                    return folder, []
        print(f'Reading NASA DR1 directories for {len(folders)} folders...', flush=True)
        available = dict(await asyncio.gather(*(folder_versions(folder) for folder in folders)))

        async def refresh(url, exposure):
            nonlocal progress
            urls = []
            if exposure.collection == 'spherex_qr2':
                folder = exposure.id[:10]
                for version in available.get(folder, []):
                    urls.append(f'{ARCHIVE}dr1/level2/{folder}/{version}/{exposure.detector}/level2_{exposure.id}D{exposure.detector}_spx_{version}.fits')
            urls.append(url)
            async with semaphore:
                last_error = ''
                for attempt_url in dict.fromkeys(urls):
                    try:
                        record = await header_record(client, attempt_url)
                        records.append({**record, 'targets': sorted(associations[url])})
                        break
                    except (httpx.HTTPError, ValueError, KeyError, OSError) as exc:
                        last_error = str(exc)
                else:
                    failures.append({'url': url, 'error': last_error})
                progress += 1
                if progress % 250 == 0 or progress == len(candidates):
                    print(f'Headers: {progress}/{len(candidates)}; loaded {len(records)}; issues {len(failures)}', flush=True)
        await asyncio.gather(*(refresh(url, exposure) for url, exposure in candidates.items()))
    if not records:
        raise RuntimeError('No independent NASA header records could be built; original index remains active')
    coverage = Counter(target for record in records for target in record['targets'])
    report = {'upstream_snapshot': base.name, 'our_source': 'NASA public S3 FITS headers and DR1 directory listings',
              'seed_sources': ['upstream exposure candidates', 'our saved IRSA target metadata'],
              'loaded_headers': len(records), 'collections': dict(Counter(r['release'] for r in records)),
              'targets': [{**field, 'header_records': coverage[field['id']]} for field in fields],
              'issues': failures, 'metadata_only': True}
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / 'records.json').write_text(json.dumps(records, indent=2))
    (ROOT / 'data/recommended-index-build.json').write_text(json.dumps(report, indent=2) + '\n')
    destination, source = merge_records(base, records, report)
    (ROOT / 'data/combined-index.json').write_text(json.dumps(source, indent=2) + '\n')
    print(json.dumps({'directory': str(destination), 'records': source['total_records'],
                      'refreshed': source['refreshed_records'], 'additional': source['additional_records'],
                      'issues': len(failures)}, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--concurrency', type=int, default=12, choices=range(1, 17))
    asyncio.run(main(parser.parse_args().concurrency))
