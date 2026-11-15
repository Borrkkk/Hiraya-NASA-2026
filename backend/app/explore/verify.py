"""Is it already known? Cross-reference a box or mover.

Order of precedence is artifact, then explained, then unexplained, and the
unexplained outcome is never worded as a discovery. Sources:

  - the saved target list (data/targets.json): works offline
  - SIMBAD (object types) and SkyBoT (known asteroids): live queries to the
    public services. They fail quietly when there is no network, and then
    the answer rests on the offline checks only (the result says so).

Live queries are written from the services' public docs and are UNTESTED
against the real services from this machine (no network here); they are
covered by tests with a mocked transport.
"""
import json
from pathlib import Path

import httpx
import numpy as np
from astropy import units as u
from astropy.coordinates import SkyCoord

from ..local_store import DATA_DIR
from .analysis import MOVERS, MIN_VALID_FRACTION, measure, pick_shots
from .common import mjd_to_iso, shots_at

SIMBAD = "https://simbad.cds.unistra.fr/simbad/sim-tap/sync"
SKYBOT = "https://vo.imcce.fr/webservices/skybot/api/conesearch.php"
TIMEOUT = httpx.Timeout(6.0, connect=3.0)

OTYPE = {"BD*": "brown-dwarf", "BD?": "brown-dwarf", "G": "galaxy", "GiG": "galaxy",
         "Pl": "planet", "As*": "asteroid", "*": "star", "PM*": "star", "V*": "star", "Ae*": "star"}
OTYPE_NAME = {"brown-dwarf": "brown dwarf", "galaxy": "galaxy", "planet": "planet",
              "asteroid": "asteroid", "star": "star"}
CATEGORY = {"high_proper_motion": ("star", "Known fast-moving star"), "brown_dwarf": ("brown-dwarf", "Known brown dwarf"),
            "variable": ("star", "Known variable star")}


def local_targets():
    path = Path(DATA_DIR) / "targets.json"
    return json.loads(path.read_text())["targets"] if path.exists() else []


def radius_arcsec(box: dict) -> float:
    return max(15.0, 0.5 * float(np.hypot(box["width"], box["height"])) * 3600)


# Saved target positions are J2000. Fast movers have moved a long way since
# (Barnard's Star about 265 arcsec by 2025), so compare at the observation date.
# (pm ra*cos(dec), pm dec) in arcsec/year, from Gaia. Add more as they are confirmed.
PROPER_MOTION = {"barnards-star": (-0.8028, 10.3625)}


def position_at(t: dict, mjd: float) -> tuple[float, float]:
    pmra, pmdec = PROPER_MOTION.get(t["id"], (0.0, 0.0))
    years = (mjd - 51544.5) / 365.25
    dec = t["dec"] + pmdec * years / 3600
    ra = t["ra"] + pmra * years / 3600 / max(np.cos(np.radians(t["dec"])), 1e-6)
    return ra, dec


def check_local(box: dict, mjd: float):
    here = SkyCoord(box["ra"] * u.deg, box["dec"] * u.deg)
    r = radius_arcsec(box)
    for t in local_targets():
        ra, dec = position_at(t, mjd)
        sep = here.separation(SkyCoord(ra * u.deg, dec * u.deg)).arcsec
        if sep <= r:
            kind, headline = CATEGORY.get(t.get("category"), ("star", "Known object"))
            return {"outcome": "explained", "headline": headline, "name": t["name"],
                    "fact": t.get("why", "Listed in the saved target list at this position."),
                    "source": "Saved target list", "objectType": kind}
    return None


async def check_simbad(client: httpx.AsyncClient, box: dict):
    r = radius_arcsec(box) / 3600
    adql = ("SELECT TOP 3 main_id, otype, ra, dec FROM basic WHERE CONTAINS(POINT('ICRS', ra, dec), "
            f"CIRCLE('ICRS', {box['ra']}, {box['dec']}, {r})) = 1")
    resp = await client.post(SIMBAD, data={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "json", "QUERY": adql})
    resp.raise_for_status()
    rows = resp.json().get("data", [])
    if not rows:
        return None
    name, otype = rows[0][0], rows[0][1] or "*"
    kind = OTYPE.get(otype, "star")
    return {"outcome": "explained", "headline": f"Known {OTYPE_NAME[kind]}", "name": name,
            "fact": f"SIMBAD lists {name} at this position (type {otype}).", "source": "SIMBAD", "objectType": kind}


async def check_skybot(client: httpx.AsyncClient, box: dict, mjd: float):
    r = radius_arcsec(box)
    resp = await client.get(SKYBOT, params={"-ra": box["ra"], "-dec": box["dec"], "-rs": r, "-mime": "json",
                                            "-output": "basic", "-observer": "500",
                                            "-epoch": mjd_to_iso(mjd).replace("T", " ").rstrip("Z")})
    resp.raise_for_status()
    body = resp.json()
    rows = body.get("data", []) if isinstance(body, dict) else []
    if not rows:
        return None
    first = rows[0]
    name = first.get("Name") or first.get("name") or "an asteroid"
    return {"outcome": "explained", "headline": "Known asteroid", "name": str(name),
            "fact": "Its predicted path for this date passes through the box.", "source": "SkyBoT", "objectType": "asteroid"}


def check_instrument(ra: float, dec: float, box: dict, epoch: str, level: int = 0, shots=None):
    shots = shots if shots is not None else [s for s in shots_at(ra, dec) if epoch == "all" or s.epoch_id == epoch]
    if not shots:
        return None
    stats = [measure(s, ra, dec, box, level) for s in shots]
    valid = float(np.mean([s.valid for s in stats]))
    if valid >= MIN_VALID_FRACTION:
        return None
    edge = any(s.edge for s in stats)
    return {"outcome": "artifact", "headline": "Not a real object",
            "reason": (f"Only {valid:.0%} of this box has good data. "
                       + ("It sits on the edge of the frame, where false signals are common." if edge
                          else "The SPHEREx pipeline flagged most of its pixels as unreliable.")),
            "flag": "Pipeline flags and frame edge"}


async def verify(client: httpx.AsyncClient | None, ra: float, dec: float, target: dict, epoch: str, step=lambda m: None,
                 level: int = 0, shots=None) -> dict:
    box = target["box"]
    mover = MOVERS.get((target.get("areaId"), target.get("moverId")))
    notes = []

    step("Checking known stars…")
    mjd = max((s.mjd for s in shots_at(ra, dec)), default=60915.0)
    local = check_local(box, mjd)
    step("Checking known asteroids…")
    skybot = None
    if client is not None:
        try:
            skybot = await check_skybot(client, box, mjd)
        except (httpx.HTTPError, ValueError, KeyError):
            notes.append("SkyBoT could not be reached")
    step("Checking catalogs…")
    simbad = None
    if client is not None:
        try:
            simbad = await check_simbad(client, box)
        except (httpx.HTTPError, ValueError, KeyError, IndexError):
            notes.append("SIMBAD could not be reached")
    step("Checking for instrument glitches…")
    glitch = check_instrument(ra, dec, box, epoch, level, shots)

    if glitch:
        return glitch
    found = local or simbad or skybot
    if found:
        return found
    out = {"outcome": "unexplained", "headline": "We can't match this to anything known"}
    if notes:
        out["nearMatch"] = {"name": "Not fully checked", "source": ", ".join(notes),
                            "note": "Only the saved target list and the instrument checks were available."}
    return out
