"""Read a locally installed SPHEREx binary tile index without live SIA queries.

Reads 24-byte binary exposure records. Set
SPHEREX_INDEX_DIR to a directory containing index.json and tiles/*.bin.
The index is metadata only; coverage is approximate until FITS WCS validation.
"""
import json
import math
import os
from pathlib import Path
import struct

from ..models import Exposure

ROW = struct.Struct('<fffhBBHHHH')


def indexed_exposures(ra, dec):
    location = os.environ.get('SPHEREX_INDEX_DIR')
    if not location:
        return None
    root = Path(location)
    meta = json.loads((root / 'index.json').read_text())
    if meta['rowBytes'] != ROW.size:
        raise ValueError('Unsupported SPHEREx index row format')
    # Select tile rectangles intersecting a conservative spherical search box.
    radius = 2.6
    extent = min(90, abs(dec) + radius)
    longitude = 180 if extent >= 90 else min(180, radius / math.cos(math.radians(extent)))
    result = {}
    for tile in meta['tiles']:
        band, column = map(int, tile.split('_'))
        low = -90 + band * meta['tileDeg']
        high = low + meta['tileDeg']
        if high < dec - radius or low > dec + radius:
            continue
        edge = 0 if low <= 0 <= high else min(abs(low), abs(high))
        count = max(1, math.ceil(360 * math.cos(math.radians(edge)) / meta['tileDeg']))
        centre = (column + .5) * 360 / count
        if abs((centre - ra + 180) % 360 - 180) > longitude + 180 / count:
            continue
        raw = (root / 'tiles' / f'{tile}.bin').read_bytes()
        if len(raw) % ROW.size:
            raise ValueError(f'Truncated SPHEREx tile: {tile}')
        for r, d, time, angle, detector, sub, folder_id, sequence, version_id, _ in ROW.iter_unpack(raw):
            delta = math.radians((ra - r + 180) % 360 - 180)
            lat, origin = math.radians(dec), math.radians(d)
            denominator = math.sin(lat)*math.sin(origin) + math.cos(lat)*math.cos(origin)*math.cos(delta)
            if denominator <= 0:
                continue
            east = math.degrees(math.cos(lat)*math.sin(delta)/denominator)
            north = math.degrees((math.sin(lat)*math.cos(origin)-math.cos(lat)*math.sin(origin)*math.cos(delta))/denominator)
            rotation = math.radians(angle / 100)
            u = east*math.cos(rotation) + north*math.sin(rotation)
            v = north*math.cos(rotation) - east*math.sin(rotation)
            if max(abs(u), abs(v)) > 1.74:
                continue
            release, folder = meta['folders'][folder_id].split('/')
            version = meta['versions'][version_id]
            identifier = f'{folder}_{sequence:04d}_{sub}'
            path = f'{release}/level2/{folder}/{version}/{detector}/level2_{identifier}D{detector}_spx_{version}.fits'
            result.setdefault((identifier, detector), Exposure(
                id=identifier, detector=detector, mjd=time+meta['mjd0'],
                collection=f'spherex_{release}',
                fits_url=f'https://irsa.ipac.caltech.edu/ibe/data/spherex/{path}'))
    return sorted(result.values(), key=lambda e: (e.mjd, e.detector))
