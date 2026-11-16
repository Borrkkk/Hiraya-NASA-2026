"""Delete the newest post you made yourself (never the seeded samples).

    cd backend && .venv/bin/python -m app.explore.delete_last_post          # newest one
    cd backend && .venv/bin/python -m app.explore.delete_last_post --all    # every post of yours
"""
import json
import sys

from .community import database
from .finding_media import image_path


def main(everything=False):
    with database() as connection:
        rows = [r for r in connection.execute('SELECT * FROM findings ORDER BY created_at DESC').fetchall()
                if not json.loads(r['evidence']).get('sample')]
        if not rows:
            print('nothing to delete')
            return
        for row in rows if everything else rows[:1]:
            connection.execute('DELETE FROM comments WHERE finding_id=?', (row['id'],))
            connection.execute('DELETE FROM findings WHERE id=?', (row['id'],))
            base = image_path(row['id'])
            for path in (base, base.with_suffix('.context.png'), base.with_suffix('.gif')):
                path.unlink(missing_ok=True)
            print('deleted', row['id'], row['title'], row['created_at'])


if __name__ == '__main__':
    main(everything='--all' in sys.argv)
