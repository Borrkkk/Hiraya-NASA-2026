"""Find a place to look at: the saved SPHEREx targets first (they have images
or at least observation records), then SIMBAD name resolution when online."""
import re

import httpx

from ..local_store import list_targets
from .verify import SIMBAD, TIMEOUT

KIND = {"high_proper_motion": "Fast-moving star", "brown_dwarf": "Brown dwarf", "variable": "Variable star"}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def local_results(q: str) -> list[dict]:
    needle = _norm(q)
    out = []
    for t in list_targets():
        hay = _norm(f"{t['name']} {t['id']} {t.get('category', '')} {t.get('query') or ''}")
        if needle and needle not in hay:
            continue
        # The saved images are cut out around the J2000 position, so open there
        # (a fast mover has since left the middle of them).
        out.append({"id": t["id"], "name": t["name"], "ra": t["ra"], "dec": t["dec"],
                    "kind": KIND.get(t.get("category"), "Target"), "blurb": t.get("why"),
                    "images": t["local_frame_count"] > 0, "source": "spherex"})
    return sorted(out, key=lambda r: (not r["images"], r["name"]))[:6]


async def resolve_name(client: httpx.AsyncClient | None, q: str) -> list[dict]:
    """SIMBAD by identifier. Quietly returns nothing when offline."""
    if client is None or len(q.strip()) < 3:
        return []
    safe = q.strip().replace("'", "''")
    adql = ("SELECT TOP 3 main_id, ra, dec, otype FROM basic JOIN ident ON oidref = oid "
            f"WHERE id = '{safe}'")
    try:
        resp = await client.post(SIMBAD, data={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "json", "QUERY": adql},
                                 timeout=TIMEOUT)
        resp.raise_for_status()
        rows = resp.json().get("data", [])
    except (httpx.HTTPError, ValueError):
        return []
    return [{"id": f"simbad:{r[0]}", "name": r[0], "ra": r[1], "dec": r[2], "kind": r[3] or "Object",
             "blurb": None, "images": False, "source": "simbad"} for r in rows if r[1] is not None]


async def search(client, q: str) -> list[dict]:
    results = local_results(q)
    if q.strip() and len(results) < 3:
        known = {_norm(r["name"]) for r in results}
        results += [r for r in await resolve_name(client, q) if _norm(r["name"]) not in known]
    return results
