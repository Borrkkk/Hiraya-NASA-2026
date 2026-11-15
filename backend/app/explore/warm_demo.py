"""Pre-download recommended regions and render their display frames for demos."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import re
import time

from ..runtime import lifespan
from fastapi import FastAPI
from . import sources
from .common import BAND_WINDOWS, LEVELS, SHOTS, in_band, key, shot_for
from .frames import frame_png
from .s3_cutouts import seed_preview

ROOT = Path(__file__).resolve().parents[3]
REPORT = ROOT / 'backend' / '.cache' / 'demo-warm-report.json'


def recommended_targets():
    """Use the same coordinates as the cards and search suggestions."""
    frontend = ROOT / 'frontend' / 'src' / 'lib'
    feed = (frontend / 'feed' / 'mock.ts').read_text(encoding='utf-8')
    wanted = set(re.findall(r'objectId: "([^"]+)"', feed)) | {'barnard'}
    result = []
    for line in (frontend / 'sky' / 'catalog.ts').read_text(encoding='utf-8').splitlines():
        name = re.search(r'id: "([^"]+)", name: "([^"]+)"', line)
        coord = re.search(r'ra: ([-\d.]+), dec: ([-\d.]+)', line)
        if name and coord and (name[1] in wanted or 'suggested: true' in line):
            ra, dec = map(float, coord.groups())
            result.append({'id': name[1], 'name': name[2], 'ra': ra, 'dec': dec})
    return result


def configure_index(index_dir=None):
    if not index_dir:
        from .static_index import index_directory
        index_dir = index_directory()
        if index_dir is None:
            raise ValueError('Install an exposure index first or supply --index-dir')
    os.environ['SPHEREX_INDEX_DIR'] = str(Path(index_dir).resolve())
    os.environ['SPHEREX_IMAGE_SOURCE'] = 's3'


async def warm_region(client, target, concurrency=3):
    ra, dec = key(target['ra'], target['dec'])
    await sources.ensure_shots(client, ra, dec)
    shots = SHOTS[(ra, dec)]
    report = {**target, 'exposures': len(shots), 'completed': 0, 'pngs': 0, 'failures': []}
    semaphore = asyncio.Semaphore(concurrency)

    async def fetch(shot):
        async with semaphore:
            try:
                widest = len(LEVELS) - 1
                wide = await sources.ensure_cutout(client, shot, ra, dec, widest)
                for level in range(widest):
                    await asyncio.to_thread(seed_preview, wide, shot.fits_url, ra, dec, LEVELS[level]['cutout_deg'])
                    await sources.ensure_cutout(client, shot, ra, dec, level)
                report['completed'] += 1
                print(f"  {target['name']}: {report['completed']}/{len(shots)} exposures cached", flush=True)
            except Exception as exc:
                report['failures'].append({'epoch': shot.epoch_id, 'detector': shot.detector, 'error': str(exc)})
                print(f"  Failed {shot.epoch_id} D{shot.detector}: {exc}", flush=True)

    await asyncio.gather(*(fetch(shot) for shot in shots))
    # Render in a stable order: latest preview defines each band's shared scale.
    rendered = set()
    for shot in sorted(shots, key=lambda s: s.mjd, reverse=True):
        for level in range(len(LEVELS)):
            path = sources.cutout_path(shot, ra, dec, level, science=False)
            if not path.exists():
                continue
            for band in BAND_WINDOWS:
                identity = (shot.epoch_id, band, level)
                if not in_band(band, shot.wavelength) or identity in rendered:
                    continue
                selected = shot_for(ra, dec, shot.epoch_id, band)
                if selected is None or selected != shot:
                    continue
                try:
                    await asyncio.to_thread(frame_png, ra, dec, shot.epoch_id, band, level, path)
                    rendered.add(identity)
                    report['pngs'] += 1
                except Exception as exc:
                    report['failures'].append({'epoch': shot.epoch_id, 'band': band, 'level': level, 'error': str(exc)})
    if not shots:
        report['failures'].append({'error': 'No usable exposures found'})
    return report


async def main(args):
    configure_index(args.index_dir)
    targets = recommended_targets()
    if args.target:
        unknown = set(args.target) - {t['id'] for t in targets}
        if unknown:
            raise ValueError(f'Unknown recommended target IDs: {sorted(unknown)}')
        targets = [t for t in targets if t['id'] in args.target]
    print('Targets: ' + ', '.join(t['name'] for t in targets), flush=True)
    if args.list:
        return
    started = time.time()
    results = []
    app = FastAPI()
    async with lifespan(app):
        for target in targets:
            print(f"Preparing {target['name']} metadata...", flush=True)
            try:
                result = await warm_region(app.state.client, target, args.concurrency)
            except Exception as exc:
                result = {**target, 'failures': [{'error': str(exc)}]}
            results.append(result)
            REPORT.parent.mkdir(parents=True, exist_ok=True)
            REPORT.write_text(json.dumps({'index': os.environ['SPHEREX_INDEX_DIR'],
                'elapsed_seconds': round(time.time()-started, 1), 'targets': results}, indent=2))
            print(f"Finished {target['name']}: {result.get('pngs', 0)} rendered frames; {len(result['failures'])} failures", flush=True)
    print(f'Report: {REPORT}', flush=True)
    if any(r['failures'] for r in results):
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', action='append', help='Recommended target ID; repeat to select several')
    parser.add_argument('--index-dir')
    parser.add_argument('--concurrency', type=int, choices=range(1, 7), default=3)
    parser.add_argument('--list', action='store_true', help='List targets without downloading')
    asyncio.run(main(parser.parse_args()))
