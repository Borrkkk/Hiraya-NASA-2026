"""Inspect a box and detect movers, from the saved SPHEREx frames.

What is real here: the flux in the box, the wavelength of each exposure at that
spot (from the file's WCS-WAVE table), the noise level, how much of the box is
valid data, and the detected sources and their shifts between exposures.

What is a rule, not a measurement: the type guess. It is rule-based on those
computed facts (no model, no score from a model) and the reason always says
which facts it used. The thresholds are placeholders for the science team.
"""
from dataclasses import dataclass
from math import hypot, atan2, degrees, sqrt

import numpy as np
from astropy.coordinates import SkyCoord
from astropy import units as u
from scipy.ndimage import gaussian_filter, maximum_filter

from .common import (LEVELS, Shot, aligned, epochs_at, grid_wcs, in_band, mjd_to_iso, shot_for, shots_at)
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
    a = aligned(str(cutout_path(shot, ra, dec, level)), ra, dec, level)
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
        reason = f"Something soft and spread out, maybe a galaxy or gas. We only have {waves} for this spot."
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


MOTION_LEVEL = 1  # 0.44 degrees; enough sky for a small apparent shift
# Conservative first-pass candidate tracking, NOT confirmed proper-motion science.
# These are pixel-space safety gates, not calibrated astrometric uncertainties.
MOTION_MIN_DETECTIONS = 3
MOTION_MIN_BASELINE_HOURS = 1.0
MOTION_MIN_SHIFT_PX = 3.5
MOTION_MAX_RESIDUAL_PX = 1.0
MOTION_CENTROID_FLOOR_PX = 0.75
MOTION_MIN_SIGNIFICANCE = 4.0
MOTION_WAVELENGTH_TOL_UM = 0.025


def motion_shots(ra: float, dec: float, epoch_ids: list[str], bands: list[str]) -> list[Shot]:
    """Select a *comparable* series: the same detector and nearly the same wavelength.

    Different SPHEREx detectors/wavelengths can reveal unrelated-looking sources.
    Never silently fall back to a different band just to fill a timeline slot.
    """
    requested = set(epoch_ids)
    available = [s for s in shots_at(ra, dec) if s.epoch_id in requested
                 and (not bands or any(in_band(b, s.wavelength) for b in bands))]
    if not available:
        return []
    # Try each observed wavelength as an anchor instead of rounding into bins
    # (which would split near-identical wavelengths at a bin boundary).
    candidates = []
    for anchor in available:
        group = [s for s in available if s.detector == anchor.detector
                 and abs(s.wavelength - anchor.wavelength) <= MOTION_WAVELENGTH_TOL_UM]
        by_epoch: dict[str, Shot] = {}
        for s in sorted(group, key=lambda s: abs(s.wavelength - anchor.wavelength)):
            by_epoch.setdefault(s.epoch_id, s)
        chosen = sorted(by_epoch.values(), key=lambda s: s.mjd)
        baseline = chosen[-1].mjd - chosen[0].mjd if len(chosen) > 1 else 0.0
        candidates.append((len(chosen), baseline, chosen))
    return max(candidates, key=lambda c: (c[0], c[1]))[2]


def _track_candidate(track: list[tuple[str, float, float, float]]) -> dict | None:
    """Validate linear movement using 3+ independent positions.

    Measurements without known centroid errors use a conservative 0.75-pixel
    error floor; this is screening evidence, NOT a measured confidence interval.
    """
    if len(track) < MOTION_MIN_DETECTIONS:
        return None
    t = np.array([p[1] for p in track], dtype=float)
    xy = np.array([(p[2], p[3]) for p in track], dtype=float)
    hours = (t[-1] - t[0]) * 24.0
    if hours < MOTION_MIN_BASELINE_HOURS or len(set(t)) < MOTION_MIN_DETECTIONS:
        return None
    t = (t - t.mean()) * 24.0
    denom = float(np.dot(t, t))
    if denom <= 0:
        return None
    velocity = (t[:, None] * (xy - xy.mean(axis=0))).sum(axis=0) / denom
    fitted = xy.mean(axis=0) + t[:, None] * velocity
    residuals = np.linalg.norm(xy - fitted, axis=1)
    if float(residuals.max()) > MOTION_MAX_RESIDUAL_PX:
        return None
    displacement = float(np.linalg.norm(velocity) * hours)
    if displacement < MOTION_MIN_SHIFT_PX:
        return None
    # Require motion significantly larger than the assumed position-error floor.
    sigma_velocity = MOTION_CENTROID_FLOOR_PX / np.sqrt(denom)
    significance = float(np.linalg.norm(velocity) / sigma_velocity)
    if significance < MOTION_MIN_SIGNIFICANCE:
        return None
    return {"displacementPx": displacement, "fitResidualPx": float(residuals.max()),
            "screeningSignificance": significance}


def link_motion_candidates(
    sources: list[tuple[str, float, list[tuple[float, float, float]]]],
) -> list[list[tuple[str, float, float, float]]]:
    """Conservatively link centroids; one source can belong to only one track.

    Seed on two epochs, predict subsequent locations from constant velocity,
    and reject a candidate when an observation is inconsistent or ambiguous.
    """
    if len(sources) < MOTION_MIN_DETECTIONS:
        return []
    first_epoch, first_mjd, first_found = sources[0]
    tracks = [[(first_epoch, first_mjd, x, y)] for x, y, _ in first_found]
    for epoch, mjd, found in sources[1:]:
        free = list(found)
        # Longer, already-confirmed tracks get priority over one-point seeds.
        for track in sorted(tracks, key=len, reverse=True):
            _, last_mjd, x_last, y_last = track[-1]
            if len(track) > 1 and last_mjd != track[-2][1]:
                prev = track[-2]
                dt = (mjd - last_mjd) / (last_mjd - prev[1])
                predicted = (x_last + (x_last - prev[2]) * dt,
                             y_last + (y_last - prev[3]) * dt)
            else:
                predicted = (x_last, y_last)
            ranked = sorted(
                ((hypot(x - predicted[0], y - predicted[1]), (x, y, peak))
                 for x, y, peak in free),
                key=lambda z: z[0],
            )
            if not ranked or ranked[0][0] > LINK_RADIUS_PX:
                continue
            # With two or more points, prediction must be tight. Two possible
            # counterparts at similar distances are too ambiguous to trust.
            tolerance = MOTION_MAX_RESIDUAL_PX * (2.0 if len(track) == 2 else 1.5)
            if len(track) >= 2 and ranked[0][0] > tolerance:
                continue
            if len(ranked) > 1 and ranked[1][0] - ranked[0][0] < MOTION_CENTROID_FLOOR_PX:
                continue
            chosen = ranked[0][1]
            track.append((epoch, mjd, chosen[0], chosen[1]))
            free.remove(chosen)
    # Reject any non-linear or insignificantly moving track.
    return [track for track in tracks if _track_candidate(track) is not None]


def find_movers(area: str, ra: float, dec: float, epoch_ids: list[str], bands: list[str], step=lambda msg: None) -> dict:
    shots = motion_shots(ra, dec, epoch_ids, bands)
    step("Lining up comparable frames…")
    if len(shots) < MOTION_MIN_DETECTIONS:
        return {
            "movers": [], "epochs": epoch_ids,
            "diagnostics": {
                "reason": "insufficient_comparable_observations",
                "comparableObservations": len(shots),
                "requiredObservations": MOTION_MIN_DETECTIONS,
                "detectedSources": 0,
            },
        }
    wcs = grid_wcs(ra, dec, MOTION_LEVEL)
    frames = [(s.epoch_id, s.mjd, aligned(str(cutout_path(s, ra, dec, MOTION_LEVEL)), ra, dec, MOTION_LEVEL))
              for s in shots]
    step("Detecting sources in each frame…")
    sources = [(e, m, detect_sources(a)) for e, m, a in frames]
    detected_count = sum(len(found) for _, _, found in sources)
    step("Checking candidate tracks across at least three observations…")
    tracks = link_motion_candidates(sources)
    step("Rejecting inconsistent movement…")
    movers = []
    for track in tracks:
        pts = []
        for e, m, x, y in track:
            r, d = wcs.all_pix2world(x, y, 0)
            pts.append({"epochId": e, "date": mjd_to_iso(m), "ra": float(r), "dec": float(d)})
        a0 = SkyCoord(pts[0]["ra"] * u.deg, pts[0]["dec"] * u.deg)
        a1 = SkyCoord(pts[-1]["ra"] * u.deg, pts[-1]["dec"] * u.deg)
        hours = (track[-1][1] - track[0][1]) * 24.0
        movers.append({
            "points": pts,
            "speedArcsecPerHour": float(a0.separation(a1).arcsec / hours),
            "positionAngleDeg": float(a0.position_angle(a1).deg),
        })
    movers.sort(key=lambda m: -m["speedArcsecPerHour"])
    for i, mover in enumerate(movers, 1):
        mover["id"], mover["number"] = f"m{i}", i
        MOVERS[(area, mover["id"])] = mover
    return {
        "movers": movers, "epochs": epoch_ids,
        "diagnostics": {
            "reason": "candidates_found" if movers else (
                "no_sources_detected" if detected_count == 0 else "no_consistent_tracks"
            ),
            "comparableObservations": len(shots),
            "requiredObservations": MOTION_MIN_DETECTIONS,
            "detectedSources": detected_count,
        },
    }
