"""[4b] Stacking: pixel-level work ACROSS frames (build step 8, stretch).

- Reproject every cutout onto one TAN grid centred on the target (each frame's own WCS, SIP
  included; bilinear interpolation of surface brightness, flagged pixels masked).
- Co-add: per detector, an inverse-variance weighted stack, measured with Frame Measurement's
  ``measure()`` (one detector stack = one "frame" at the band-mean λ).
- Difference images: each frame minus the median of its detector's frames; the strongest
  positive residual is a transient / mover candidate.

Pure (no network). Never reads catalogs; Field Context explains the transients.
"""
from __future__ import annotations

import logging
import math
import warnings
from dataclasses import dataclass

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from photutils.aperture import CircularAperture
from scipy.ndimage import map_coordinates

from . import config
from .measurement import _mask_for, background, flag_bit_names, measure
from .models import Cutout, DifferenceFrame, FrameMeasurement, FrameRef, StackedMeasurement, Target

log = logging.getLogger(__name__)


@dataclass
class Reprojected:
    cutout: Cutout
    data: np.ndarray  # background-subtracted surface brightness on the common grid (NaN = no data)
    var: np.ndarray
    lam_um: float | None  # λ at the target pixel
    diff_data: np.ndarray | None = None  # same, keeping saturated pixels (for difference images)
    diff_var: np.ndarray | None = None


def common_grid(target: Target, pixel_scale_arcsec: float, n_pix: int) -> WCS:
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [target.coord.ra, target.coord.dec]
    w.wcs.crpix = [(n_pix + 1) / 2, (n_pix + 1) / 2]
    w.wcs.cdelt = [-pixel_scale_arcsec / 3600.0, pixel_scale_arcsec / 3600.0]
    w.wcs.cunit = ["deg", "deg"]
    return w


def reproject(cut: Cutout, target: Target, grid: WCS, n_pix: int) -> Reprojected | None:
    if cut.status != "ok" or cut.image is None:
        return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        w = WCS(cut.header)
    data = np.asarray(cut.image, float) - np.asarray(cut.zodi, float)
    var = np.asarray(cut.variance, float)
    bits = flag_bit_names(cut.flags_header) if cut.flags_header is not None else {}
    flags = np.asarray(cut.flags, np.int64)
    invalid = ~np.isfinite(data) | ~np.isfinite(var) | (var <= 0)
    bad = invalid | _mask_for(flags, bits, config.FLAGS_STACK_EXCLUDE)
    bad_diff = invalid | _mask_for(flags, bits, config.FLAGS_DIFF_EXCLUDE)
    # Per-frame background at the target (same estimator as Frame Measurement).
    tx, ty = (float(v) for v in w.world_to_pixel_values(target.coord.ra, target.coord.dec))
    bg = background(data, bad, flags, bits, tx, ty)

    yy, xx = np.mgrid[0:n_pix, 0:n_pix]
    ra, dec = grid.pixel_to_world_values(xx, yy)
    px, py = w.world_to_pixel_values(ra, dec)
    coords = [py, px]

    def warp(mask):
        d = map_coordinates(np.where(mask, 0.0, data - bg), coords, order=1, mode="constant", cval=0.0)
        v = map_coordinates(np.where(mask, 0.0, var), coords, order=1, mode="constant", cval=0.0)
        g = map_coordinates((~mask).astype(float), coords, order=1, mode="constant", cval=0.0)
        ok = g > 0.999  # every input pixel touching this output pixel was good
        return np.where(ok, d, np.nan), np.where(ok, v, np.nan)

    d, v = warp(bad)
    dd, dv = warp(bad_diff)
    lam = None
    if cut.wave_wcs is not None:
        try:
            lam = float(cut.wave_wcs.pixel_to_world(tx, ty)[0].to_value("um"))
        except Exception:
            lam = None
    return Reprojected(cut, d, v, lam, dd, dv)


def _stack_cutout(members: list[Reprojected], grid: WCS, n_pix: int, target: Target, det: int) -> Cutout:
    """Inverse-variance stack as a Cutout so that ``measure()`` can be reused unchanged."""
    d = np.stack([m.data for m in members])
    v = np.stack([m.var for m in members])
    w = np.where(np.isfinite(d) & np.isfinite(v) & (v > 0), 1.0 / np.where(v > 0, v, 1.0), 0.0)
    wsum = w.sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        img = np.where(wsum > 0, np.nansum(np.nan_to_num(d) * w, axis=0) / wsum, np.nan)
        var = np.where(wsum > 0, 1.0 / wsum, np.nan)

    first = members[0].cutout
    hdr = grid.to_header()
    hdr["PSF_FWHM"] = float(np.median([m.cutout.header.get("PSF_FWHM", 7.5) for m in members]))
    # Detector position of the target in the first frame, so the ePSF lookup picks a sensible
    # row: CRPIXnA maps the stack's centre pixel onto it.
    fw = WCS(first.header)
    tx, ty = (float(v) for v in fw.world_to_pixel_values(target.coord.ra, target.coord.dec))
    if "CRPIX1A" in first.header:
        det_x, det_y = tx + 1 - first.header["CRPIX1A"], ty + 1 - first.header["CRPIX2A"]
        c = (n_pix - 1) / 2
        hdr["CRPIX1A"], hdr["CRPIX2A"] = c + 1 - det_x, c + 1 - det_y

    lams = [m.lam_um for m in members if m.lam_um is not None]
    wave = None
    if lams:
        wave = WCS(naxis=2)
        wave.wcs.ctype = ["WAVE", "LINEAR"]
        wave.wcs.cunit = ["um", "um"]
        wave.wcs.crval = [float(np.mean(lams)), float(max(lams) - min(lams)) or 0.01]
        wave.wcs.cdelt = [1e-9, 1e-9]
        wave.wcs.crpix = [1, 1]
    frame = FrameRef(
        frame_id=f"stack-D{det}", obs_id=f"stack-D{det}", detector=det,
        t_mid=float(np.mean([m.cutout.frame.t_mid for m in members])),
        t_min=min(m.cutout.frame.t_min for m in members), t_max=max(m.cutout.frame.t_max for m in members),
        footprint=[], release="stack", collection="stack", pixel_scale_arcsec=first.frame.pixel_scale_arcsec,
        cutout_url="", full_url="",
    )
    return Cutout(frame=frame, image=np.where(np.isfinite(img), img, np.nan), flags=np.zeros_like(img, dtype=np.int64),
                  variance=var, zodi=np.zeros_like(img), epsf=first.epsf, header=hdr, flags_header=fits.Header(),
                  wave_wcs=wave, version="stack")


def stack_and_difference(cutouts: list[Cutout], target: Target, measurements: list[FrameMeasurement] | None = None
                         ) -> tuple[list[StackedMeasurement], list[DifferenceFrame]]:
    ok = [c for c in cutouts if c.status == "ok" and c.image is not None]
    if not ok:
        return [], []
    scale = float(np.median([c.frame.pixel_scale_arcsec or 6.15 for c in ok]))
    n_pix = int(round(target.cutout_size_deg * 3600 / scale)) | 1  # odd → target on a pixel centre
    grid = common_grid(target, scale, n_pix)

    by_det: dict[int, list[Reprojected]] = {}
    for c in ok:
        r = reproject(c, target, grid, n_pix)
        if r is not None:
            by_det.setdefault(c.frame.detector, []).append(r)

    snr_by_frame = {m.frame_id: m.snr for m in (measurements or []) if m.snr is not None}
    saturated = {m.frame_id for m in (measurements or [])
                 if m.detected and set(m.flag_names) & config.FLAGS_SATURATION}
    omega_sr = (scale / 3600 * math.pi / 180) ** 2
    stacked, diffs = [], []
    for det in sorted(by_det):
        members = by_det[det]
        n_sat = sum(r.cutout.frame.frame_id in saturated for r in members)
        if len(members) >= config.STACK_MIN_FRAMES and n_sat > config.STACK_MAX_SATURATED_FRACTION * len(members):
            stacked.append(StackedMeasurement(
                detector=det, n_frames=len(members),
                note=f"{n_sat}/{len(members)} frames saturated: stacking adds no signal (saturated pixels are excluded)"))
        elif len(members) >= config.STACK_MIN_FRAMES:
            m = measure(_stack_cutout(members, grid, n_pix, target, det), target)
            lams = [r.lam_um for r in members if r.lam_um is not None]
            frame_snrs = [snr_by_frame[r.cutout.frame.frame_id] for r in members if r.cutout.frame.frame_id in snr_by_frame]
            stacked.append(StackedMeasurement(
                detector=det, n_frames=len(members), wavelength_um=m.wavelength_um,
                wavelength_min_um=min(lams) if lams else None, wavelength_max_um=max(lams) if lams else None,
                detected=m.detected, ra=m.ra_meas, dec=m.dec_meas, offset_from_target_arcsec=m.offset_from_target_arcsec,
                flux_jy=m.flux_jy, flux_err_jy=m.flux_err_jy, snr=m.snr, flag_names=m.flag_names, usable=m.usable,
                flux_method=m.flux_method, median_frame_snr=float(np.median(frame_snrs)) if frame_snrs else None,
            ))
        if len(members) >= config.DIFF_MIN_FRAMES:
            diffs += _differences(members, grid, n_pix, omega_sr)
    diffs.sort(key=lambda d: d.t_mid)
    return stacked, diffs


def _differences(members: list[Reprojected], grid: WCS, n_pix: int, omega_sr: float) -> list[DifferenceFrame]:
    cube = np.stack([m.diff_data for m in members])
    vcube = np.stack([m.diff_var for m in members])
    c = (n_pix - 1) / 2
    ap = CircularAperture((c, c), config.APERTURE_RADIUS_PX).to_mask(method="exact").to_image((n_pix, n_pix))
    yy, xx = np.mgrid[0:n_pix, 0:n_pix]
    # Search the inscribed circle only: frames are rotated differently, so corners are covered
    # by few frames and their template is noisy.
    inner = np.hypot(xx - c, yy - c) <= (n_pix - 1) / 2 - config.DIFF_EDGE_PX
    out = []
    for i, m in enumerate(members):
        others = np.delete(np.arange(len(members)), i)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            tmpl = np.nanmedian(cube[others], axis=0)
            n_eff = np.sum(np.isfinite(cube[others]), axis=0)
            # variance of a median ≈ (π/2) · mean variance / N
            tvar = (math.pi / 2) * np.nanmean(vcube[others], axis=0) / np.maximum(n_eff, 1)
        diff = m.diff_data - tmpl
        noise = np.sqrt(m.diff_var + tvar + (config.DIFF_TEMPLATE_FRAC * np.abs(tmpl)) ** 2)
        full = n_eff >= max(config.DIFF_MIN_FRAMES - 1, int(0.6 * len(others)))  # a real template behind it
        snr = np.where(inner & full & np.isfinite(diff) & np.isfinite(noise) & (noise > 0), diff / noise, -np.inf)
        f = m.cutout.frame
        if not np.isfinite(snr).any():
            out.append(DifferenceFrame(frame_id=f.frame_id, detector=f.detector, t_mid=f.t_mid))
            continue
        k = int(np.argmax(snr))
        py, px = divmod(k, n_pix)
        pra, pdec = (float(v) for v in grid.pixel_to_world_values(px, py))
        sep = math.hypot(px - c, py - c) * grid.wcs.cdelt[1] * 3600
        at = ap > 0
        fin = at & np.isfinite(diff) & np.isfinite(noise)
        flux = float(np.sum(ap[fin] * diff[fin])) * omega_sr * 1e6 if fin.any() else None
        ferr = float(np.sqrt(np.sum(ap[fin] * noise[fin] ** 2))) * omega_sr * 1e6 if fin.any() else None
        peak = float(snr[py, px])
        out.append(DifferenceFrame(
            frame_id=f.frame_id, detector=f.detector, t_mid=f.t_mid, peak_snr=peak, peak_ra=pra, peak_dec=pdec,
            peak_sep_from_target_arcsec=sep, flux_at_target_jy=flux, flux_at_target_err_jy=ferr,
            transient=peak >= config.DIFF_SNR,
        ))
    return out
