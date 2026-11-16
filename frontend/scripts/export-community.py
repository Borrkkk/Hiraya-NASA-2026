"""Bake the discussions into static files, so the deployed app needs no backend.

    pnpm demo:community      (from frontend/, needs backend/.venv and backend/.data)

Reads backend/.data/community.sqlite3 and writes frontend/public/demo/community/:
    community.json            the five sample discussions with their comments
    <id>.png / .context.png / .gif    snapshot, wider context image and blink animation
    live.png / .context.png / .gif    the same three for the "live" post, reused for any
                                      discussion posted around the simulated find
The newest post that is not a seeded sample is the template for the live post:
post once locally around the faint mover, run this, then delete that post.
"""
import json
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))

from app.explore.finding_media import image_path  # noqa: E402

DB = ROOT / 'backend' / '.data' / 'community.sqlite3'
OUT = ROOT / 'frontend' / 'public' / 'demo' / 'community'
BASE = '/demo/community'


def media(identifier, evidence, name):
    """Copy the three media files next to the JSON and point the evidence at them."""
    base = image_path(identifier)
    files = {'': base, '.context': base.with_suffix('.context.png'), '.anim': base.with_suffix('.gif')}
    for suffix, source in files.items():
        if source.exists():
            shutil.copyfile(source, OUT / (f'{name}{suffix}' + ('.gif' if suffix == '.anim' else '.png')))
    if evidence.get('image'):
        evidence['image']['url'] = f'{BASE}/{name}.png'
        if files['.context'].exists():
            evidence['image']['contextUrl'] = f'{BASE}/{name}.context.png'
        else:
            evidence['image'].pop('contextUrl', None)
    if evidence.get('animation'):
        evidence['animation']['url'] = f'{BASE}/{name}.anim.gif'
    return evidence


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    rows = connection.execute('SELECT * FROM findings ORDER BY created_at DESC').fetchall()
    comments = {}
    for c in connection.execute('SELECT * FROM comments ORDER BY created_at'):
        comments.setdefault(c['finding_id'], []).append(
            {'id': c['id'], 'author': c['author'], 'body': c['body'], 'created_at': c['created_at']})

    findings, live = [], None
    for row in rows:
        evidence = json.loads(row['evidence'])
        box = {k: row[k] for k in ('ra', 'dec', 'width', 'height')}
        if evidence.get('sample'):
            findings.append({
                'id': row['id'], 'title': row['title'], 'body': row['body'], 'author': row['author'],
                'created_at': row['created_at'], 'box': box, 'status': 'suspected-motion',
                'evidence': media(row['id'], evidence, row['id']), 'comments': comments.get(row['id'], [])})
        elif live is None:
            live = {'box': box, 'evidence': media(row['id'], evidence, 'live')}
    if live is None:
        raise SystemExit('No live post to use as template: post around the faint mover first.')
    live['evidence'].pop('authorId', None)
    (OUT / 'community.json').write_text(json.dumps({'findings': findings, 'live': live}, separators=(',', ':')))
    print(f'wrote {len(findings)} discussions + the live template to {OUT}')


if __name__ == '__main__':
    main()
