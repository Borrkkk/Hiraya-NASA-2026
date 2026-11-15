"""Save index-only exposure lists for fixed frontend and curated target fields."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

from .static_index import index_directory, indexed_exposures

ROOT = Path(__file__).resolve().parents[3]


def target_fields():
    frontend = ROOT / 'frontend' / 'src'
    recommendations = '\n'.join((frontend / p).read_text(encoding='utf-8') for p in (
        'lib/feed/mock.ts', 'lib/profiles.ts', 'components/home/sky-backdrop.tsx'))
    wanted = set(re.findall(r'objectId: "([^"]+)"', recommendations))
    wanted.update(re.findall(r'\{ id: "([^"]+)", fov:', recommendations))
    fields = []
    for line in (frontend / 'lib/sky/catalog.ts').read_text(encoding='utf-8').splitlines():
        name = re.search(r'id: "([^"]+)", name: "([^"]+)"', line)
        coord = re.search(r'ra: ([-\d.]+), dec: ([-\d.]+)', line)
        if name and coord:
            ra, dec = map(float, coord.groups())
            fields.append({'id': name[1], 'name': name[2], 'ra': ra, 'dec': dec, 'source': 'frontend',
                           'recommended': name[1] in wanted or 'suggested: true' in line})
    catalog = json.loads((ROOT / 'data/targets.json').read_text())
    for item in catalog['targets']:
        if item.get('category') != 'solar_system':
            fields.append({k: item[k] for k in ('id', 'name', 'ra', 'dec')} |
                          {'id': 'saved-' + item['id'], 'source': 'curated', 'recommended': True})
    return fields


def build_report():
    directory = index_directory()
    if directory is None:
        raise ValueError('Install an index or set SPHEREX_INDEX_DIR first')
    meta = json.loads((directory / 'index.json').read_text())
    provenance = json.loads((directory / 'source.json').read_text()) if (directory / 'source.json').exists() else {}
    saved = directory / 'targets'
    saved.mkdir(exist_ok=True)
    targets = []
    for field in target_fields():
        rows = indexed_exposures(field['ra'], field['dec'])
        payload = {'target': field, 'index_updated': meta['updated'], 'approximate_coverage': True,
                   'exposures': [row.model_dump() for row in rows]}
        (saved / (field['id'] + '.json')).write_text(json.dumps(payload, indent=2) + '\n')
        counts = dict(Counter(row.collection for row in rows))
        targets.append({**field, 'candidate_exposures': len(rows),
                        'observation_ids': len({row.id for row in rows}),
                        'detectors': sorted({row.detector for row in rows}), 'collections': counts,
                        'candidate_file': f"backend/.cache/exposure-index/{directory.name}/targets/{field['id']}.json"})
        print(f"{field['name']}: {len(rows)} candidate detector exposures", flush=True)
    report = {**provenance, 'index_updated': meta['updated'], 'total_index_records': meta['total'],
              'tiles': len(meta['tiles']), 'releases': sorted({folder.split('/')[0] for folder in meta['folders']}),
              'approximate_coverage': True, 'metadata_only': True,
              'note': 'Candidate lists require FITS WCS validation. No new image pixels were downloaded. Moving-object fields need ephemerides.',
              'targets': targets}
    output = ROOT / 'data/indexed-targets.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    report = build_report()
    print(f"Saved coverage for {len(report['targets'])} fixed fields to data/indexed-targets.json")
