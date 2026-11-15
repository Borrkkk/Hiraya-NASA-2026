"""Adapt cached Explore cutouts to the spherex_inspect science pipeline.

Image rendering and field-wide mover detection remain in the Explore renderer.
The spectrum measures a source at the selection's centre, not integrated box flux.
"""
from pathlib import Path
import re
from urllib.parse import urlencode

from astropy.io import fits
from astropy.wcs import WCS
from astropy.wcs.utils import proj_plane_pixel_scales
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

import spherex_inspect
from spherex_inspect import config
from spherex_inspect.intake import IntakeError
from spherex_inspect.models import Cutout, FrameRef, InspectRequest
from spherex_inspect.retrieval import parse_cutout
from backend.app.explore.analysis import inspect as morphology_inspect
from backend.app.explore.sources import cutout_path

OBJECT_TYPES = {
    "star": "star", "variable_star": "star", "brown_dwarf": "brown-dwarf",
    "galaxy": "galaxy", "qso": "galaxy", "asteroid": "asteroid", "comet": "comet",
}


def load_cutouts(shots, ra, dec, level):
    cutouts = []
    for shot in shots:
        path = cutout_path(shot, ra, dec, level)
        release_match = re.search(r"/((?:dr|qr)\d+)/", shot.fits_url)
        release = release_match[1] if release_match else None
        frame = FrameRef(frame_id=f"{shot.epoch_id}D{shot.detector}", obs_id=shot.epoch_id,
                         detector=shot.detector, t_mid=shot.mjd, t_min=shot.mjd, t_max=shot.mjd,
                         footprint=[], release=release.upper() if release else "unknown",
                         collection=f"spherex_{release}" if release else "unknown",
                         pixel_scale_arcsec=6.15, cutout_url=shot.fits_url, full_url=shot.fits_url)
        try:
            raw = Path(path).read_bytes()
            cutout = parse_cutout(frame, raw, from_cache=True)
            height, width = cutout.image.shape
            wcs = WCS(cutout.header, naxis=2).celestial
            xs, ys = [0, width - 1, width - 1, 0], [0, 0, height - 1, height - 1]
            ras, decs = wcs.all_pix2world(xs, ys, 0)
            frame.footprint = list(zip(map(float, ras), map(float, decs)))
            frame.pixel_scale_arcsec = float(sum(proj_plane_pixel_scales(wcs)) / 2 * 3600)
            if shot.fits_url:
                cx, cy = wcs.all_pix2world((width - 1) / 2, (height - 1) / 2, 0)
                frame.cutout_url = shot.fits_url + "?" + urlencode({
                    "center": f"{float(cx)},{float(cy)}", "size": max(width, height) * frame.pixel_scale_arcsec / 3600})
            with fits.open(path, memmap=False) as hdus:
                seconds = float(hdus[0].header.get("EXPTIME", hdus["IMAGE"].header.get("EXPTIME", 0)))
            frame.t_max = frame.t_min + max(seconds, 0) / 86400
            frame.t_mid = (frame.t_min + frame.t_max) / 2
        except (OSError, ValueError, KeyError, TypeError) as exc:
            cutout = Cutout(frame=frame, status="failed", error=str(exc))
        cutouts.append(cutout)
    return cutouts


async def analyze(ra, dec, target, epoch, level, shots, include_context=False):
    box = target["box"]
    request = InspectRequest(
        ra=box["ra"], dec=box["dec"],
        cutout_size_deg=min(config.MAX_CUTOUT_SIZE_DEG, max(config.MIN_CUTOUT_SIZE_DEG,
                                                          box["width"], box["height"])),
        bands=sorted({shot.detector for shot in shots}) or None,
        max_frames=max(1, len(shots)), include_context=include_context,
    )
    cutouts = await run_in_threadpool(load_cutouts, shots, ra, dec, level)
    try:
        return await spherex_inspect.inspect_cutouts(request, cutouts)
    except IntakeError as exc:
        raise HTTPException(422, str(exc)) from exc


def evidence(result):
    summary = result.summary
    return {
        "engine": "spherex_inspect", "measurement": "Point source at selection centre",
        "nFrames": summary.quality.n_frames, "nDetected": summary.quality.n_detected,
        "nUsable": summary.quality.n_usable, "nFailed": summary.quality.n_failed,
        "warnings": result.warnings, "flags": summary.quality.flag_summary,
        "properMotion": summary.proper_motion.model_dump() if summary.proper_motion else None,
    }


async def inspect(ra, dec, target, epoch, level, shots):
    result = await analyze(ra, dec, target, epoch, level, shots)
    # Preserve the existing morphology explanation, without claiming its rule
    # scores are scientific probabilities. The spectrum comes only from clean
    # aperture/PSF photometry; flagged samples remain available in science.
    fallback = await run_in_threadpool(morphology_inspect, ra, dec, target, epoch, level, shots)
    samples = result.summary.spectrum
    usable = result.summary.quality.n_usable
    return {
        "lowSignal": not bool(samples),
        "guess": fallback["guess"] if usable else {
            "type": "empty", "reason": "No usable point-source flux at the selection centre. Check the quality flags or select a different source."},
        "candidates": [],
        "spectrum": {"points": [{"wavelengthUm": s.wavelength_um, "flux": s.flux, "err": s.err} for s in samples],
                     "fluxLabel": "Point-source flux (Jy)", "features": []},
        "evidence": evidence(result), "science": result.model_dump(mode="json"),
    }


async def verify(ra, dec, target, epoch, step, level, shots):
    step("Measuring source flux, positions, and quality flags…")
    step("Comparing measured positions with known objects…")
    result = await analyze(ra, dec, target, epoch, level, shots, include_context=True)
    summary, context = result.summary, result.context
    extra = {"evidence": evidence(result), "science": result.model_dump(mode="json")}
    if not summary.quality.n_detected:
        return {"outcome": "unexplained", "headline": "Not enough source evidence to verify this selection",
                "nearMatch": {"name": "No reliable detection", "source": "SPHEREx measurements",
                              "note": "Try centring the selection on a source. No detection is not evidence of an artifact."}, **extra}
    # Field-wide tracks are created by the Explore detector, not the point-source
    # science fit. Identifying a source at one location does NOT verify every
    # position of that track. Withhold any confirmed verdict until an epoch-by-
    # epoch trajectory comparison is implemented.
    if target.get("kind") == "mover":
        return {"outcome": "unexplained",
                "headline": "Motion candidate — track not yet verified",
                "nearMatch": {
                    "name": "Track verification unavailable",
                    "source": "SPHEREx point inspection",
                    "note": "A source match at one position does not confirm a moving path. "
                            "This candidate needs independent positions and catalog ephemerides "
                            "checked at every observation date."
                }, **extra}
    if context and context.verdict == "matched" and context.best_match:
        match = context.best_match
        kind = OBJECT_TYPES.get(match.object_class)
        if kind:
            return {"outcome": "explained", "headline": "Measured source matches a known object",
                    "name": match.name, "fact": context.note or "Matched at the observation epoch using the measured position.",
                    "source": ", ".join(match.source_catalogs), "objectType": kind, **extra}
    failed = {name: status for name, status in (context.status_by_source if context else {}).items()
              if not status.startswith("ok")}
    note = ("Some catalog checks were unavailable: " + ", ".join(failed)) if failed else (
        context.note if context and context.note else "No conclusive catalog match. This is not a discovery confirmation.")
    return {"outcome": "unexplained", "headline": "No conclusive match for the measured source",
            "nearMatch": {"name": "Checks incomplete" if failed else "No confirmed match",
                          "source": "Catalog comparison", "note": note}, **extra}
