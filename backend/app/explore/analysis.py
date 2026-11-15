"""Inspect a box and detect movers, from the saved SPHEREx frames.

What is real here: the flux in the box, the wavelength of each exposure at that
spot (from the file's WCS-WAVE table), the noise level, how much of the box is
valid data, and the detected sources and their shifts between exposures.

What is a rule, not a measurement: the type guess. It is rule-based on those
computed facts (no model, no score from a model) and the reason always says
which facts it used. The thresholds are placeholders for the science team.
"""
from dataclasses import dataclass, replace
from math import hypot, atan2, degrees, sqrt

import numpy as np
from astropy.coordinates import SkyCoord
from astropy import units as u
from scipy.ndimage import gaussian_filter, maximum_filter

from .common import (LEVELS, Shot, aligned, epochs_at, grid_wcs, in_band, mjd_to_iso, shot_for, shots_at, _read_wavelength)
from .sources import cutout_path

# Where the placeholders live (spec Q10: the science team owns these).
SOLAR_SYSTEM_ABOVE = 0.2    # arcsec per hour
MIN_SNR = 3.0               # below this a box is "not enough signal"
MIN_VALID_FRACTION = 0.5    # less valid data than this and the box is an artifact
MOVER_MIN_SHIFT_PX = 1.5    # shifts smaller than this are centroid noise
LINK_RADIUS_PX = 8
DETECT_SIGMA = 5.0


def noise_of(finite: np.ndarray) -> float:
    return float(1.4826 * np.median(np.abs(finite - np.median(finite))))


# ---------------------------------------------------------------- the box

@dataclass
class BoxStats:
    shot: Shot
    mean: float
    snr: float
    valid: float       # fraction of the box that has good data
    peak_ratio: float  # brightest pixel over the mean: high means compact
    edge: bool         # the box touches the edge of the frame
    npix: float


def pick_level(ra: float, dec: float, box: dict) -> int:
    """The smallest frame size that holds the whole box."""
    east = (box["ra"] - ra + 540) % 360 - 180
    east *= float(np.cos(np.radians(dec)))
    need = max(abs(east) + box["width"] / 2, abs(box["dec"] - dec) + box["height"] / 2) * 1.05
    for l in LEVELS:
        if need <= l["extentDeg"] / 2:
            return l["level"]
    return LEVELS[-1]["level"]


def pick_shots(ra: float, dec: float, epoch: str, bands: list[str], level: int) -> list[Shot]:
    """Exposures to measure. Bigger frames need a download each, so there only the
    exposures in the bands that are on (everything, at the free smallest size)."""
    shots = [s for s in shots_at(ra, dec) if epoch == "all" or s.epoch_id == epoch]
    if level > 0 and bands:
        shots = [s for s in shots if any(in_band(b, s.wavelength) for b in bands)]
    return shots


def box_geometry(ra: float, dec: float, box: dict, level: int = 0):
    l = LEVELS[level]
    size, scale = l["sizePx"], l["pixelScaleArcsec"]
    w = grid_wcs(ra, dec, level)
    cx, cy = w.all_world2pix(box["ra"], box["dec"], 0)
    hw = max(box["width"] * 3600 / 2 / scale, 0.5)
    hh = max(box["height"] * 3600 / 2 / scale, 0.5)
    yy, xx = np.indices((size, size))
    mask = (np.abs(xx - cx) <= hw) & (np.abs(yy - cy) <= hh)
    edge = bool(cx - hw < 1 or cy - hh < 1 or cx + hw > size - 2 or cy + hh > size - 2)
    return mask, float(cx), float(cy), hw, hh, edge


def measure(shot: Shot, ra: float, dec: float, box: dict, level: int = 0) -> BoxStats:
    path = str(cutout_path(shot, ra, dec, level))
    a = aligned(path, ra, dec, level)
    # Detector wavelength varies with position. The area's centre wavelength
    # is appropriate for the picker, but the plot must use the selected box.
    shot = replace(shot, wavelength=_read_wavelength(path, box['ra'], box['dec']))
    mask, _, _, hw, hh, edge = box_geometry(ra, dec, box, level)
    expected = max(1.0, (2 * hw) * (2 * hh))
    vals = a[mask]
    good = vals[np.isfinite(vals)]
    frame = a[np.isfinite(a)]
    sigma = max(noise_of(frame), 1e-12) if frame.size else 1.0
    if good.size == 0:
        return BoxStats(shot, 0.0, 0.0, 0.0, 1.0, edge, expected)
    mean = float(good.mean())
    snr = mean / (sigma / sqrt(good.size))
    ratio = float(good.max() / mean) if mean > 0 else 1.0
    return BoxStats(shot, mean, snr, min(1.0, good.size / expected), ratio, edge, expected)


def shots_for(ra: float, dec: float, epoch: str) -> list[Shot]:
    return [s for s in shots_at(ra, dec) if epoch == "all" or s.epoch_id == epoch]


# ---------------------------------------------------------------- inspect

def inspect(ra: float, dec: float, target: dict, epoch: str, level: int = 0, shots: list[Shot] | None = None) -> dict:
    box = target["box"]
    stats = [measure(s, ra, dec, box, level) for s in (shots if shots is not None else shots_for(ra, dec, epoch))]
    stats = [s for s in stats if s.valid > 0]

    points = sorted(
        ({"wavelengthUm": s.shot.wavelength, "flux": s.mean} for s in stats),
        key=lambda p: p["wavelengthUm"],
    )
    spectrum = {
        "points": points,
        "fluxLabel": "Brightness above the background (MJy/sr)",
        "features": [],
    }

    if not stats:
        return _result(True, "artifact", "No usable data inside this box. It is outside the frame or fully masked.",
                       {"artifact": 0.9, "empty": 0.1}, spectrum)

    valid = float(np.mean([s.valid for s in stats]))
    snr = float(max(s.snr for s in stats))
    ratio = float(np.mean([s.peak_ratio for s in stats]))
    edge = any(s.edge for s in stats)
    nwave = len({round(s.shot.wavelength, 3) for s in stats})
    mover = MOVERS.get((target.get("areaId"), target.get("moverId"))) if target["kind"] == "mover" else None

    scores = {t: 0.02 for t in ("star", "brown-dwarf", "planet", "comet", "asteroid", "galaxy", "empty", "artifact")}
    if valid < MIN_VALID_FRACTION:
        scores["artifact"] = 0.9
        where = "at the edge of the frame" if edge else "where the pipeline flagged most pixels"
        return _result(False, "artifact", f"Likely an artifact: only {valid:.0%} of the box has good data, {where}.", scores, spectrum)
    if mover is not None:
        fast = mover["speedArcsecPerHour"] >= SOLAR_SYSTEM_ABOVE
        scores["asteroid" if fast else "star"] = 0.7
        scores["comet" if fast else "brown-dwarf"] = 0.2
        reason = (
            "Likely an asteroid or comet: it moves fast against the stars, which points to something inside our solar system."
            if fast else
            "It moves, but slowly, like a nearby star or a cold brown dwarf. Speed alone can't tell which."
        )
        return _result(False, "asteroid" if fast else "star", reason, scores, spectrum)
    if snr < MIN_SNR:
        scores["empty"] = 0.9
        return _result(True, "empty", "Not enough signal to say. Try a bigger box or other bands.", scores, spectrum)

    compact = ratio > 2.0 and max(box["width"], box["height"]) * 3600 / LEVELS[0]["pixelScaleArcsec"] <= 12
    scores["star" if compact else "galaxy"] = 0.7
    scores["brown-dwarf" if compact else "star"] = 0.15
    waves = f"{nwave} wavelength{'s' if nwave != 1 else ''}"
    if compact:
        reason = f"Likely a star: bright and compact, like a point of light. We only have {waves} for this spot, so we can't tell what kind."
        kind = "star"
    else:
        reason = f"The selected light appears spread out. We measured its brightness at {waves} in this region."
        kind = "galaxy"
    return _result(False, kind, reason, scores, spectrum)


def _result(low: bool, kind: str, reason: str, scores: dict, spectrum: dict) -> dict:
    total = sum(scores.values()) or 1
    ranked = sorted(({"type": t, "confidence": s / total} for t, s in scores.items()), key=lambda c: -c["confidence"])
    return {"lowSignal": low, "guess": {"type": kind, "reason": reason}, "candidates": ranked, "spectrum": spectrum}


# ---------------------------------------------------------------- motion

# (area id, mover id) -> mover, so inspecting a mover can use its speed.
MOVERS: dict[tuple[str, str], dict] = {}


def detect_sources(a: np.ndarray) -> list[tuple[float, float, float]]:
    """Point sources as (x, y, peak), by smoothing and picking significant local maxima."""
    valid = np.isfinite(a)
    if valid.sum() < 25:
        return []
    filled = np.where(valid, a, np.median(a[valid]))
    smooth = gaussian_filter(filled, 1.0)
    sigma = max(noise_of(smooth[valid]), 1e-12)
    peaks = (smooth == maximum_filter(smooth, size=5)) & (smooth > DETECT_SIGMA * sigma)
    peaks &= valid & (gaussian_filter(valid.astype(float), 2) > 0.8)  # not at a masked edge
    out = []
    for y, x in zip(*np.nonzero(peaks)):
        y0, y1, x0, x1 = max(y - 2, 0), min(y + 3, a.shape[0]), max(x - 2, 0), min(x + 3, a.shape[1])
        patch = np.clip(smooth[y0:y1, x0:x1] - np.median(smooth[valid]), 0, None)
        if patch.sum() <= 0:
            continue
        yy, xx = np.indices(patch.shape)
        out.append((float((xx * patch).sum() / patch.sum() + x0), float((yy * patch).sum() / patch.sum() + y0), float(smooth[y, x])))
    return out


MOTION_LEVEL = 1  # 0.44 degrees: wide enough to follow things that move


def motion_shots(ra: float, dec: float, epoch_ids: list[str], bands: list[str]) -> list[Shot]:
    """The exposure used for each epoch: the first selected band that has one, else any."""
    out = []
    for e in epoch_ids:
        shot = next((shot_for(ra, dec, e, b) for b in bands if shot_for(ra, dec, e, b)), None)
        shot = shot or next((s for s in shots_at(ra, dec) if s.epoch_id == e), None)
        if shot is not None:
            out.append(shot)
    return out


def find_movers(area: str, ra: float, dec: float, epoch_ids: list[str], bands: list[str], step=lambda msg: None) -> dict:
    wcs = grid_wcs(ra, dec, MOTION_LEVEL)
    epochs = {e: m for e, m in epochs_at(ra, dec)}
    chosen = [e for e in sorted(epoch_ids, key=lambda e: epochs.get(e, 0)) if e in epochs]
    step("Lining up the frames…")
    frames = [(s.epoch_id, epochs[s.epoch_id], aligned(str(cutout_path(s, ra, dec, MOTION_LEVEL)), ra, dec, MOTION_LEVEL))
              for s in motion_shots(ra, dec, chosen, bands)]
    step("Matching stars between frames…")
    sources = [(e, m, detect_sources(a)) for e, m, a in frames]
    step("Looking for things that shifted…")
    tracks: list[list[tuple[str, float, float, float]]] = []
    if sources:
        tracks = [[(sources[0][0], sources[0][1], x, y)] for x, y, _ in sources[0][2]]
    for e, m, found in sources[1:]:
        free = list(found)
        for track in tracks:
            _, _, lx, ly = track[-1]
            best = min(free, key=lambda s: hypot(s[0] - lx, s[1] - ly), default=None)
            if best is not None and hypot(best[0] - lx, best[1] - ly) <= LINK_RADIUS_PX:
                track.append((e, m, best[0], best[1]))
                free.remove(best)
    step("Joining the dots into tracks…")
    movers = []
    for track in tracks:
        if len(track) < 2:
            continue  # seen in one frame only: not a mover (it can still be boxed)
        shift = max(hypot(p[2] - q[2], p[3] - q[3]) for p in track for q in track)
        if shift < MOVER_MIN_SHIFT_PX:
            continue
        pts = []
        for e, m, x, y in track:
            r, d = wcs.all_pix2world(x, y, 0)
            pts.append({"epochId": e, "date": mjd_to_iso(m), "ra": float(r), "dec": float(d)})
        a0, a1 = SkyCoord(pts[0]["ra"] * u.deg, pts[0]["dec"] * u.deg), SkyCoord(pts[-1]["ra"] * u.deg, pts[-1]["dec"] * u.deg)
        hours = max((track[-1][1] - track[0][1]) * 24, 1e-6)
        movers.append({
            "points": pts,
            "speedArcsecPerHour": float(a0.separation(a1).arcsec / hours),
            "positionAngleDeg": float(a0.position_angle(a1).deg),
        })
    movers.sort(key=lambda m: -m["speedArcsecPerHour"])
    for i, m in enumerate(movers, 1):
        m["id"], m["number"] = f"m{i}", i
        MOVERS[(area, m["id"])] = m
    return {"movers": movers, "epochs": epoch_ids}
