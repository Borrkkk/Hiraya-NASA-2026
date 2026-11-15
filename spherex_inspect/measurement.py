"""[4] Frame Measurement: measure the source near the target in ONE cutout.

Pure function of a single Cutout (no network, no cross-frame logic):
background → detection → centroid → λ at centroid → aperture photometry (Jy) → flags.
"""
from __future__ import annotations

import logging
import math
import warnings

import numpy as np
from astropy.stats import sigma_clipped_stats
from astropy.wcs import WCS
from astropy.wcs.utils import proj_plane_pixel_area
from photutils.aperture import CircularAnnulus, CircularAperture
from photutils.centroids import centroid_2dg, centroid_com

from . import config
from .models import Cutout, FrameMeasurement, Target

log = logging.getLogger(__name__)

_ARCSEC_PER_DEG = 3600.0
_SR_PER_DEG2 = (math.pi / 180.0) ** 2
_unknown_flags_logged: set[str] = set()


# --------------------------------------------------------------------------- #
# Flags
# --------------------------------------------------------------------------- #


def flag_bit_names(flags_header) -> dict[int, str]:
    """{bit: name} from MSKNnnnn keywords. Never hard-code bit numbers."""
    out = {}
    for k in flags_header:
        if k.startswith("MSKN"):
            try:
                out[int(k[4:])] = str(flags_header[k]).strip()
            except ValueError:
                pass
    return out


def decode_flags(value: int, bit_names: dict[int, str]) -> list[str]:
    names = []
    for bit in range(64):
        if value >> bit & 1:
            names.append(bit_names.get(bit, f"BIT{bit}"))
    return names


def classify_flags(names: list[str]) -> tuple[bool, bool, list[str]]:
    """→ (flux_usable, position_ok_by_flags, reported names excluding ignored ones)."""
    reported, flux_ok, pos_ok = [], True, True
    for n in names:
        if n in config.FLAGS_IGNORE:
            continue
        reported.append(n)
        if n in config.FLAGS_UNUSABLE:
            flux_ok = False
        elif n not in config.FLAGS_WARNING and n not in _unknown_flags_logged:
            _unknown_flags_logged.add(n)
            log.warning("unknown FLAGS name %r treated as warning-only", n)
        if n in config.FLAGS_POSITION_UNUSABLE:
            pos_ok = False
    return flux_ok, pos_ok, sorted(reported)


def _mask_for(flags: np.ndarray, bit_names: dict[int, str], names: frozenset[str]) -> np.ndarray:
    bits = 0
    for b, n in bit_names.items():
        if n in names:
            bits |= 1 << b
    return (flags & bits) != 0


# --------------------------------------------------------------------------- #
# Pieces
# --------------------------------------------------------------------------- #


def background(data: np.ndarray, bad: np.ndarray, flags: np.ndarray, bit_names, x: float, y: float) -> float:
    """Median of a 4–6 px annulus on unflagged pixels (zodi already subtracted).
    Falls back to sigma-clipped finite annulus pixels, then to 0."""
    rin, rout = config.BG_ANNULUS_PX
    m = CircularAnnulus((x, y), rin, rout).to_mask(method="center").to_image(data.shape)
    if m is None:
        return 0.0
    ring = m > 0
    any_flag = flags & ~_bits_for(bit_names, frozenset({"FULLSAMPLE"})) != 0
    clean = ring & ~bad & ~any_flag
    if clean.sum() >= config.BG_MIN_PIXELS:
        return float(np.median(data[clean]))
    finite = ring & ~bad
    if finite.sum() >= config.BG_MIN_PIXELS:
        return float(sigma_clipped_stats(data[finite], sigma=3.0)[1])
    return 0.0


def _bits_for(bit_names: dict[int, str], names: frozenset[str]) -> int:
    bits = 0
    for b, n in bit_names.items():
        if n in names:
            bits |= 1 << b
    return bits


def _box(n_y: int, n_x: int, cx: int, cy: int, half: int):
    x0, x1 = max(cx - half, 0), min(cx + half + 1, n_x)
    y0, y1 = max(cy - half, 0), min(cy + half + 1, n_y)
    return slice(y0, y1), slice(x0, x1)


def centroid(sub: np.ndarray, err: np.ndarray, bad: np.ndarray, px: int, py: int) -> tuple[float, float, str]:
    """2D-Gaussian centroid in a 5×5 box around (px, py); bad pixels masked.
    Falls back to centre of mass, then to the peak pixel."""
    half = config.CENTROID_BOX_PX // 2
    sy, sx = _box(*sub.shape, px, py, half)
    d, e, m = sub[sy, sx], err[sy, sx], bad[sy, sx]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for method, fn in (("2dg", lambda: centroid_2dg(np.where(m, 0, d), error=np.where(m, 1, e), mask=m)),
                           ("com", lambda: centroid_com(np.where(m, 0, np.clip(d, 0, None)), mask=m))):
            try:
                x, y = fn()
            except Exception:
                continue
            if np.isfinite(x) and np.isfinite(y) and -0.5 <= x <= d.shape[1] - 0.5 and -0.5 <= y <= d.shape[0] - 0.5:
                return float(x + sx.start), float(y + sy.start), method
    return float(px), float(py), "peak"


def epsf_aperture_fraction(epsf, det_x: float, det_y: float, radius_px: float, oversample: int = 5) -> float | None:
    """Fraction of ePSF flux inside ``radius_px`` native pixels, using the ePSF row whose
    (XCENTER, YCENTER) is nearest the source's detector position.

    Integrated on the ×5 oversampled grid (radius × 5), which equals rebinning to native
    pixels for a source at pixel centre, without the pixel-phase dependence.
    """
    if epsf is None or len(epsf) == 0:
        return None
    i = int(np.argmin((epsf["XCENTER"] - det_x) ** 2 + (epsf["YCENTER"] - det_y) ** 2))
    psf = np.asarray(epsf["EPSF"][i], dtype=float)
    total = np.nansum(psf)
    if not np.isfinite(total) or total <= 0:
        return None
    ny, nx = psf.shape
    ap = CircularAperture(((nx - 1) / 2, (ny - 1) / 2), radius_px * oversample)
    inside = float(np.sum(ap.to_mask(method="exact").multiply(np.nan_to_num(psf))))
    frac = float(inside / total)
    return frac if 0.05 < frac <= 1.0 else None


def _epsf_native(epsf, det_x: float, det_y: float, oversample: int = 5) -> np.ndarray | None:
    """Nearest ePSF row, normalised so that sampling it at native-pixel spacing sums to ~1."""
    if epsf is None or len(epsf) == 0:
        return None
    i = int(np.argmin((epsf["XCENTER"] - det_x) ** 2 + (epsf["YCENTER"] - det_y) ** 2))
    psf = np.nan_to_num(np.asarray(epsf["EPSF"][i], dtype=float))
    tot = psf.sum()
    return psf / tot * oversample**2 if tot > 0 else None


def psf_wing_fit(sub: np.ndarray, var: np.ndarray, exclude: np.ndarray, psf: np.ndarray,
                 cx: float, cy: float, oversample: int = 5):
    """Fit amplitude + position of the ePSF to the pixels a saturated star leaves usable
    (its wings): everything flagged as saturated/bad is excluded. The amplitude is the total
    flux (image units summed over pixels), so no aperture correction is needed.

    → dict(flux, flux_err, x, y, n_pix, rchi2) or None when the fit is not trustworthy."""
    from scipy.ndimage import map_coordinates
    from scipy.optimize import least_squares

    ny, nx = sub.shape
    yy, xx = np.mgrid[0:ny, 0:nx]
    r = np.hypot(xx - cx, yy - cy)
    sel = (r <= config.WING_FIT_RADIUS_PX) & ~exclude & np.isfinite(sub) & np.isfinite(var) & (var > 0)
    if sel.sum() < config.WING_FIT_MIN_PIXELS:
        return None
    xs, ys = xx[sel].astype(float), yy[sel].astype(float)
    d, e = sub[sel], np.sqrt(var[sel])
    c0 = (psf.shape[0] - 1) / 2

    def model(x0, y0):
        return map_coordinates(psf, [c0 + oversample * (ys - y0), c0 + oversample * (xs - x0)],
                               order=3, mode="constant", cval=0.0)

    m0 = model(cx, cy)
    if m0.sum() <= 0:
        return None
    a0 = max(float(np.sum(d * m0) / np.sum(m0 * m0)), 1e-6)
    try:
        fit = least_squares(lambda p: (p[2] * model(p[0], p[1]) - d) / e, [cx, cy, a0],
                            x_scale=[0.3, 0.3, a0])
    except Exception:
        return None
    x0, y0, amp = (float(v) for v in fit.x)
    if amp <= 0 or math.hypot(x0 - cx, y0 - cy) > config.WING_FIT_MAX_SHIFT_PX:
        return None
    dof = max(len(d) - 3, 1)
    rchi2 = float(np.sum(fit.fun**2) / dof)
    try:
        cov = np.linalg.pinv(fit.jac.T @ fit.jac)
        amp_err = math.sqrt(max(cov[2, 2], 0.0) * max(rchi2, 1.0))
    except Exception:
        return None
    return {"flux": amp, "flux_err": amp_err, "x": x0, "y": y0, "n_pix": int(sel.sum()), "rchi2": rchi2}


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def measure(cutout: Cutout, target: Target) -> FrameMeasurement:
    f = cutout.frame
    base = dict(frame_id=f.frame_id, obs_id=f.obs_id, detector=f.detector, t_mid=f.t_mid)
    if cutout.status != "ok":
        return FrameMeasurement(**base, note=f"cutout failed: {cutout.error}")

    hdr = cutout.header
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        wcs = WCS(hdr)
    img = np.asarray(cutout.image, float)
    zodi = np.asarray(cutout.zodi, float)
    var = np.asarray(cutout.variance, float)
    flags = np.asarray(cutout.flags, np.int64)
    bit_names = flag_bit_names(cutout.flags_header) if cutout.flags_header is not None else {}
    ny, nx = img.shape

    tx, ty = (float(v) for v in wcs.world_to_pixel_values(target.coord.ra, target.coord.dec))
    if not (-0.5 <= tx <= nx - 0.5 and -0.5 <= ty <= ny - 0.5):
        return FrameMeasurement(**base, note="target outside cutout")

    data = img - zodi
    bad = ~np.isfinite(data) | ~np.isfinite(var) | (var <= 0) | _mask_for(flags, bit_names, config.FLAGS_BAD_PIXEL)
    bg = background(data, bad, flags, bit_names, tx, ty)
    sub = data - bg
    err = np.sqrt(np.where(var > 0, var, np.nan))

    # Detection: peak SNR in the 5×5 box around the target pixel.
    half = config.CENTROID_BOX_PX // 2
    itx, ity = int(round(tx)), int(round(ty))
    sy, sx = _box(ny, nx, itx, ity, half)
    snr_box = np.where(bad[sy, sx], -np.inf, sub[sy, sx] / err[sy, sx])
    peak_snr = float(np.max(snr_box)) if np.isfinite(snr_box).any() else -np.inf
    detected = peak_snr >= config.DETECT_SNR
    if detected:
        # Locate by the brightest valid pixel (for saturated stars the SNR peak is off-core).
        flux_box = np.where(bad[sy, sx], -np.inf, sub[sy, sx])
        py, px = np.unravel_index(int(np.argmax(flux_box)), flux_box.shape)
        # The peak must be a local maximum over its valid 8-neighbours in the full image.
        # Otherwise it is the wing of a neighbour centred outside the box. Masked pixels
        # (e.g. a NaN saturated core) are skipped, so a bright star with a bad core still counts.
        gx, gy = px + sx.start, py + sy.start
        ny0, nx0 = _box(ny, nx, gx, gy, 1)
        neigh = np.where(bad[ny0, nx0], -np.inf, sub[ny0, nx0])
        if sub[gy, gx] < np.max(neigh):
            detected = False
    if detected:
        cx, cy, method = centroid(sub, err, bad, px + sx.start, py + sy.start)
        # Only a source within a 2 px RADIUS of the target is "the" source. The square box lets
        # a neighbour in a corner (up to 2.8 px ≈ 17″) through; mixing it with forced photometry
        # at the target made a blank field look wildly variable.
        if math.hypot(cx - tx, cy - ty) > config.DETECT_MAX_OFFSET_PX:
            detected = False
    if not detected:
        cx, cy, method = tx, ty, "forced"

    # Photometry: 2 px aperture at the centroid (or forced at the target pixel).
    apmask = CircularAperture((cx, cy), config.APERTURE_RADIUS_PX).to_mask(method="exact").to_image((ny, nx))
    w = apmask if apmask is not None else np.zeros_like(img)
    in_ap = w > 0
    n_bad_ap = int((in_ap & bad).sum())
    flux_sb = float(np.sum(w * np.where(bad, 0.0, sub)))  # MJy/sr summed over pixels
    var_sb = float(np.sum(w * np.where(bad, 0.0, var)))

    det_x, det_y = cx, cy
    if "CRPIX1A" in hdr:  # 0-based active-pixel (detector) coordinates
        det_x, det_y = cx - (hdr["CRPIX1A"] - 1), cy - (hdr["CRPIX2A"] - 1)
    apcorr = epsf_aperture_fraction(cutout.epsf, det_x, det_y, config.APERTURE_RADIUS_PX)
    corr = apcorr or 1.0

    omega_sr = float(proj_plane_pixel_area(wcs)) * _SR_PER_DEG2
    flux_jy = flux_sb / corr * omega_sr * 1e6
    flux_err_jy = math.sqrt(var_sb) / corr * omega_sr * 1e6 if var_sb > 0 else None
    snr = flux_jy / flux_err_jy if flux_err_jy else None

    note = None
    if f.pixel_scale_arcsec:
        wcs_scale = math.sqrt(omega_sr / _SR_PER_DEG2) * _ARCSEC_PER_DEG
        if abs(wcs_scale / f.pixel_scale_arcsec - 1) > config.PIXEL_SCALE_TOLERANCE:
            note = f"pixel scale mismatch: WCS {wcs_scale:.3f}\" vs SIA {f.pixel_scale_arcsec:.3f}\""

    # Flags OR'd over the aperture.
    flag_or = int(np.bitwise_or.reduce(flags[in_ap])) if in_ap.any() else 0
    flux_ok, pos_ok, names = classify_flags(decode_flags(flag_or, bit_names))
    if n_bad_ap:
        names = sorted(set(names) | {"MASKED_PIXELS"})

    # Masked (NaN) saturated core: the aperture misses the core, so fit the ePSF to the wings.
    # Not used for saturated-but-unmasked stars: there the aperture flux scatters less (live:
    # Barnard's wing fits scattered 17–50% vs aperture χ² 0.1–0.3 at a 10% floor).
    flux_method = "aperture" if detected else "forced"
    wing = None
    if detected and n_bad_ap:
        psf = _epsf_native(cutout.epsf, det_x, det_y)
        if psf is not None:
            exclude = bad | _mask_for(flags, bit_names, config.FLAGS_WING_EXCLUDE)
            wing = psf_wing_fit(sub, var, exclude, psf, cx, cy)
        if wing is not None:
            flux_method = "psf_wings"
            flux_jy = wing["flux"] * omega_sr * 1e6
            flux_err_jy = wing["flux_err"] * omega_sr * 1e6
            snr = flux_jy / flux_err_jy if flux_err_jy else None
            cx, cy = wing["x"], wing["y"]  # the centroid came from the wings anyway

    # Position.
    ra_m, dec_m = (float(v) for v in wcs.pixel_to_world_values(cx, cy))
    offset = _sep_arcsec(target.coord.ra, target.coord.dec, ra_m, dec_m)
    fwhm = float(hdr.get("PSF_FWHM", 2.35 * (f.pixel_scale_arcsec or 6.2)))
    saturated = any(n in config.FLAGS_SATURATION for n in names)
    floor = config.SATURATED_POS_ERR_FLOOR_ARCSEC if saturated else config.POS_ERR_FLOOR_ARCSEC
    if saturated and "MASKED_PIXELS" in names:  # centroid from the wings only (R Dra: ~4″ off)
        floor = config.MASKED_CORE_POS_ERR_FLOOR_ARCSEC
    pos_err = max(fwhm / (2.35 * snr), floor) if snr and snr > 0 else None

    # Wavelength at the centroid.
    lam = bw = None
    if cutout.wave_wcs is not None:
        try:
            wl, band = cutout.wave_wcs.pixel_to_world(cx, cy)
            lam, bw = float(wl.to_value("um")), float(band.to_value("um"))
        except Exception as exc:
            log.info("spectral WCS failed for %s: %s", f.frame_id, exc)

    usable = bool(flux_ok and n_bad_ap == 0 and np.isfinite(flux_jy) and flux_err_jy and lam is not None)
    position_usable = bool(detected and pos_ok and method != "peak")

    return FrameMeasurement(
        **base,
        wavelength_um=lam,
        bandwidth_um=bw,
        detected=detected,
        ra_meas=ra_m if detected else None,
        dec_meas=dec_m if detected else None,
        pos_err_arcsec=pos_err if detected else None,
        offset_from_target_arcsec=offset if detected else None,
        flux_jy=flux_jy if np.isfinite(flux_jy) else None,
        flux_err_jy=flux_err_jy,
        snr=snr,
        flag_bits=flag_or,
        flag_names=names,
        usable=usable,
        position_usable=position_usable,
        aperture_correction=apcorr,
        flux_method=flux_method,
        psf_fit_rchi2=wing["rchi2"] if wing else None,
        note=note,
    )


def _sep_arcsec(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    r1, d1, r2, d2 = map(math.radians, (ra1, dec1, ra2, dec2))
    s = math.sin((d2 - d1) / 2) ** 2 + math.cos(d1) * math.cos(d2) * math.sin((r2 - r1) / 2) ** 2
    return math.degrees(2 * math.asin(min(1.0, math.sqrt(s)))) * _ARCSEC_PER_DEG
