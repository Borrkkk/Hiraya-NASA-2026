"""Seed the discussions page with conversations about the DEMO sky (Barnard's Star).

    cd backend && .venv/bin/python -m app.explore.seed_demo_discussions          # add/refresh the samples
    cd backend && .venv/bin/python -m app.explore.seed_demo_discussions --reset  # also clear the live post around the find, so it can be posted again

Everything is simulated (see demo_media.py). The cold, fast-moving object (the "find")
is deliberately NOT seeded, so it can be posted live during the demo.
"""
from datetime import datetime, timedelta, timezone
import json
import math
import sys

from . import demo_media
from .community import database
from .finding_media import attach_media, image_path

AUTHORS = {'Dr. Maya Rao': 'maya-rao', 'Jordan Kim': 'jordan-kim', 'Alex Rivera': 'alex-rivera'}


def separation_arcsec(a, b):
    d_ra = (a[0] - b[0] + 180) % 360 - 180
    return math.hypot(d_ra * math.cos(math.radians(a[1])), a[1] - b[1]) * 3600


def pick(sources, kind=None, cls=None, brightest=True, avoid=(), min_sep=240):
    pool = [s for s in sources if (kind is None or s['kind'] == kind) and (cls is None or s['cls'] == cls)]
    pool.sort(key=lambda s: s['j'])
    for s in pool:
        if all(separation_arcsec((s['ra'], s['dec']), a) > min_sep for a in avoid):
            return s
    raise SystemExit('no suitable source')


def build_posts():
    m = demo_media.manifest()
    if not m:
        raise SystemExit('Run `pnpm demo:data` in frontend/ first: the demo manifest is missing.')
    src = m['sources']
    epochs = m['epochs']
    both = [e['id'] for e in epochs if 'starlight' in e['bands'] and 'warm-glow' in e['bands']]
    star = [e['id'] for e in epochs if 'starlight' in e['bands']]
    find = next(s for s in src if s['id'] == 'find')
    barnard = next(s for s in src if s['id'] == 'barnard')
    galaxy = next(s for s in src if s['id'] == 'gal1')
    hot = next(s for s in src if s['id'] == 'hot1')
    keep_clear = [(find['ra'], find['dec']), (barnard['ra'] + 0.0, barnard['dec'] + 0.075), (galaxy['ra'], galaxy['dec']), (hot['ra'], hot['dec'])]
    a_star = pick(src, 'star', 'A', avoid=keep_clear)
    k_star = pick(src, 'star', 'K', avoid=keep_clear + [(a_star['ra'], a_star['dec'])])

    def track(source, ids):
        out = []
        for e in epochs:
            if e['id'] in ids:
                ra, dec = demo_media.position(source, e['year'])
                out.append({'ra': ra % 360, 'dec': dec, 'epochId': e['id'], 'date': e['date']})
        return out

    mid_barnard = demo_media.position(barnard, 2026.1)
    return [
        dict(id='demo-barnard-motion', days=1, author='Dr. Maya Rao', title="Barnard's Star slides north across 15 months",
             at=mid_barnard, size=.02, bands=['starlight', 'warm-glow'], epochs=both, track=track(barnard, both),
             body="Blinking the starlight and 4–5 µm frames in date order, one star keeps shifting up the picture while its neighbours stay put. "
                  "The ring follows the position I measured in each observation.\n\nThat is about 10 arcseconds a year, which matches the star's catalogued proper motion. "
                  "Worth noting: it is also the brightest thing in the field at both wavelengths, so the centroid is very clean.\n\n"
                  "Could someone repeat this with a different pair of colours? I would like to see whether the shift is the same everywhere.",
             comments=[('Jordan Kim', "Repeated it with Starlight and Helium: same direction, same size. The older Visible-light picture also puts it well south of this position, which fits."),
                       ('Alex Rivera', "Neighbouring stars stay within a fraction of a pixel across all twelve dates, so this is not a pointing drift."),
                       ('Dr. Maya Rao', "Thanks both. Marking this one as explained: SIMBAD lists the same motion.")]),
        dict(id='demo-smudge-galaxy', days=3, author='Jordan Kim', title='An elongated smudge north-west of the star: galaxy or blend?',
             at=(galaxy['ra'], galaxy['dec']), size=.02, bands=['starlight', 'warm-glow'], epochs=star[:8], track=[],
             body="There is a soft, stretched source that does not sharpen like the stars around it, and it does not move. "
                  "In the 4–5 µm frames it keeps a bright core, which an unresolved blend of two stars usually would not.\n\n"
                  "The brightness plot has a small bump near 3.3 µm. Is that enough to say it is a galaxy, or is it noise?",
             comments=[('Alex Rivera', "Only a handful of samples sit near 3.3 µm and they come from different dates, so I would not lean on the bump yet."),
                       ('Dr. Maya Rao', "The shape alone is already suggestive: extended, steady, no motion. I would call it a likely galaxy and look for a catalogue match.")]),
        dict(id='demo-hot-pixel', days=5, author='Alex Rivera', title='The same bright dot in every frame: a detector glitch?',
             at=(hot['ra'], hot['dec']), size=.008, bands=['warm-glow', 'starlight'], epochs=both, track=[],
             body="A tiny, sharp dot shows up in every 4–5 µm frame, always in exactly the same spot of the detector, even though the telescope was pointing slightly differently each time.\n\n"
                  "Real objects should shift relative to the detector grid. Does this look like a hot pixel to you?",
             comments=[('Jordan Kim', "Looks like one to me. It never changes brightness and never gets blurred like the stars do."),
                       ('Dr. Maya Rao', "Agreed. Good example of a false alarm worth keeping in the notebook.")]),
        dict(id='demo-hot-star-lines', days=7, author='Jordan Kim', title="Hydrogen dips in a hot star's colours",
             at=(a_star['ra'], a_star['dec']), size=.016, bands=['starlight', 'hydrogen'], epochs=[e['id'] for e in epochs if 'hydrogen' in e['bands']] or star, track=[],
             body="This is one of the bluest stars in the patch. Its spectrum drops slightly near 1.28 and 1.88 µm, right where hydrogen absorbs.\n\n"
                  "Nothing exotic, but it makes a nice calibration example: a hot star should show these dips and a cool one should not.",
             comments=[('Dr. Maya Rao', "Nice. Compare it with Barnard's Star, which shows water-vapour dips instead.")]),
        dict(id='demo-orange-neighbour', days=9, author='Dr. Maya Rao', title='A steady orange star: what does 4–5 µm tell us?',
             at=(k_star['ra'], k_star['dec']), size=.016, bands=['starlight', 'warm-glow'], epochs=both, track=[],
             body="An ordinary orange star, chosen as a control. It stays fixed on every date and its brightness falls smoothly toward 5 µm with a faint carbon-monoxide dip.\n\n"
                  "If you are new to this, compare its plot with the one in the Barnard's Star post: same idea, cooler star, deeper dips.",
             comments=[('Alex Rivera', "Helpful as a baseline. I used it to check my own box against.")]),
    ]


def main(reset=False):
    posts = build_posts()
    now = datetime.now(timezone.utc)
    with database() as connection:
        if reset:
            # Only the slot reserved for the live demo post (around the find); nobody else's posts.
            find = next(s for s in demo_media.manifest()['sources'] if s['id'] == 'find')
            spot = demo_media.position(find, 2026.1)
            for row in connection.execute('SELECT * FROM findings').fetchall():
                ev = json.loads(row['evidence'])
                if ev.get('sample') or separation_arcsec((row['ra'], row['dec']), spot) > 60:
                    continue
                connection.execute('DELETE FROM comments WHERE finding_id=?', (row['id'],))
                connection.execute('DELETE FROM findings WHERE id=?', (row['id'],))
                for path in (image_path(row['id']), image_path(row['id']).with_suffix('.context.png'), image_path(row['id']).with_suffix('.gif')):
                    path.unlink(missing_ok=True)
                print('removed live post', row['id'], row['title'])
    for p in posts:
        created = now - timedelta(days=p['days'], hours=3)
        evidence = {'bands': p['bands'], 'epochs': p['epochs'], 'track': p['track'], 'view': {'ra': p['at'][0] % 360, 'dec': p['at'][1], 'fov': 0.2},
                    'sample': True, 'demo': True, 'authorId': AUTHORS[p['author']]}
        with database() as connection:
            connection.execute('DELETE FROM findings WHERE id=?', (p['id'],))
            connection.execute('DELETE FROM comments WHERE finding_id=?', (p['id'],))
            connection.execute('INSERT INTO findings VALUES (?,?,?,?,?,?,?,?,?,?)', (
                p['id'], p['at'][0] % 360, p['at'][1], p['size'], p['size'], p['title'], p['body'], p['author'],
                created.isoformat(), json.dumps(evidence)))
            for i, (who, text) in enumerate(p['comments']):
                connection.execute('INSERT INTO comments VALUES (?,?,?,?,?)', (
                    f"{p['id']}-c{i}", p['id'], who, text, (created + timedelta(hours=5 * (i + 1) + 2)).isoformat()))
        attach_media(p['id'])
        print('seeded', p['id'])


if __name__ == '__main__':
    main(reset='--reset' in sys.argv)
