import base64
from io import BytesIO
import warnings

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from PIL import Image
from scipy.ndimage import map_coordinates

from .models import TimelapseRequest


def target_wcs(request: TimelapseRequest) -> WCS:
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crval = [request.ra, request.dec]
    wcs.wcs.crpix = [(request.size_px + 1) / 2] * 2
    scale = request.pixel_scale_arcsec / 3600
    wcs.wcs.cdelt = [-scale, scale]
    return wcs


def align(body: bytes, request: TimelapseRequest) -> np.ndarray:
    with fits.open(BytesIO(body), memmap=False) as hdus:
        image = hdus["IMAGE"]
        data = np.asarray(image.data, dtype=float).copy()
        if data.ndim != 2:
            raise ValueError("Expected a two dimensional IMAGE extension")
        if "FLAGS" not in hdus and request.bad_bits:
            raise ValueError("FITS has no FLAGS extension; cannot apply requested mask")
        if request.bad_bits:
            flags = np.asarray(hdus["FLAGS"].data, dtype=np.uint32)
            data[(flags & request.bad_bits) != 0] = np.nan
        # Pass the whole HDUList so Astropy can resolve distortion lookup tables.
        source = WCS(image.header, hdus, naxis=2).celestial
        y, x = np.indices((request.size_px, request.size_px), dtype=float)
        ra, dec = target_wcs(request).all_pix2world(x, y, 0)
        sx, sy = source.all_world2pix(ra, dec, 0)
        valid = np.isfinite(sx) & np.isfinite(sy)
        sx, sy = np.where(valid, sx, -1), np.where(valid, sy, -1)
        aligned = map_coordinates(data, [sy, sx], order=1, mode="constant", cval=np.nan, prefilter=False)
        aligned[~valid] = np.nan
        if not np.any(np.isfinite(aligned)):
            raise ValueError("No usable pixels cover this position after masking")
        if request.subtract_background:
            aligned -= np.nanmedian(aligned)
        return aligned


def png(data: np.ndarray, low: float, high: float, signed=False) -> str:
    valid = np.isfinite(data)
    values = np.nan_to_num(data, nan=0, posinf=0, neginf=0)
    if signed:
        pixels = np.clip(127.5 + 127.5 * values / max(high, 1e-12), 0, 255)
    else:
        normalized = np.clip((values - low) / max(high - low, 1e-12), 0, 1)
        pixels = 255 * np.arcsinh(10 * normalized) / np.arcsinh(10)
    # Array row 0 is south in the WCS. PNG row 0 must be north.
    rgba = np.stack([pixels, pixels, pixels, valid * 255], axis=-1).astype(np.uint8)
    output = BytesIO()
    Image.fromarray(np.flipud(rgba)).save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()


def render(arrays: list[np.ndarray]):
    cube = np.stack(arrays)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        median = np.nanmedian(cube, axis=0)
    finite = cube[np.isfinite(cube)]
    low, high = map(float, np.percentile(finite, [1, 99.5]))
    residuals = cube - median
    residual_values = np.abs(residuals[np.isfinite(residuals)])
    difference_scale = float(np.percentile(residual_values, 99)) if len(residual_values) else 1.0
    return {
        "stretch": {"low": low, "high": high, "function": "asinh", "difference_abs_max": difference_scale},
        "images": [png(frame, low, high) for frame in cube],
        "differences": [png(frame, 0, difference_scale, signed=True) for frame in residuals],
        "median_png": png(median, low, high),
    }
