import json
import math
from pathlib import Path

import astropy.units as u
import numpy as np
import pytest
from astropy.coordinates import Distance, SkyCoord
from astropy.io import fits
from astropy.table import Table
from astropy.time import Time
from astropy.wcs import WCS

from spherex_inspect.measurement import classify_flags, decode_flags, epsf_aperture_fraction, flag_bit_names, measure
from spherex_inspect.models import Cutout, FrameRef, SkyPosition, Target, TimeRange
from spherex_inspect.retrieval import parse_cutout

RA0, DEC0 = 180.0, 10.0
SCALE = 6.15  # arcsec / px
N = 29
OMEGA_SR = (SCALE / 3600 * math.pi / 180) ** 2

# Deliberately NOT the real bit numbers: the code must map by name.
BITS = {3: "OVERFLOW", 5: "SOURCE", 8: "GHOST", 9: "DICHROIC", 12: "HOT", 13: "FULLSAMPLE", 30: "MYSTERY"}


def frame():
    return FrameRef(
        frame_id="o1D2", obs_id="o1", detector=2, t_mid=61000.0, t_min=61000.0, t_max=61000.001,
        footprint=[], release="DR1", collection="spherex_dr1", em_min_um=1.1, em_max_um=1.7,
        pixel_scale_arcsec=SCALE, cutout_url="u", full_url="u",
    )


def target(ra=RA0, dec=DEC0):
    return Target(coord=SkyPosition(ra=ra, dec=dec), time_range=TimeRange(), bands=[2], cutout_size_deg=0.05, max_frames=1)


def gaussian(n, x0, y0, sigma, total):
    y, x = np.mgrid[0:n, 0:n]
    g = np.exp(-((x - x0) ** 2 + (y - y0) ** 2) / (2 * sigma**2))
    return total * g / (2 * math.pi * sigma**2)


def synthetic(stars=(), sigma=1.0, flags=None, nan_at=None, noise=0.0, seed=0):
    """stars: [(x, y, total_MJy_sr_pix)]; returns a Cutout with WCS, flags header, ePSF."""
    hdr = fits.Header()
    hdr.update({
        "CTYPE1": "RA---TAN", "CTYPE2": "DEC--TAN", "CRVAL1": RA0, "CRVAL2": DEC0,
        "CRPIX1": (N - 1) / 2 + 1, "CRPIX2": (N - 1) / 2 + 1,
        "CDELT1": -SCALE / 3600, "CDELT2": SCALE / 3600, "CUNIT1": "deg", "CUNIT2": "deg",
        "PSF_FWHM": 2.355 * sigma * SCALE, "CRPIX1A": -100.0, "CRPIX2A": -200.0,
    })
    rng = np.random.default_rng(seed)
    zodi = np.full((N, N), 0.3)
    img = zodi + 0.02  # small residual background the annulus must remove
    for x, y, tot in stars:
        img = img + gaussian(N, x, y, sigma, tot)
    var = np.full((N, N), 1e-4)
    if noise:
        img = img + rng.normal(0, noise, (N, N))
        var[:] = noise**2
    if nan_at:
        img[nan_at[1], nan_at[0]] = np.nan
    fl = np.zeros((N, N), np.int64) if flags is None else flags
    fh = fits.Header()
    for b, n in BITS.items():
        fh[f"MSKN{b:04d}"] = n
    wave = WCS(naxis=2)
    wave.wcs.ctype = ["WAVE", "LINEAR"]
    wave.wcs.cunit = ["um", "um"]
    wave.wcs.crval = [1.4, 0.03]
    wave.wcs.cdelt = [0.001, 1e-5]
    wave.wcs.crpix = [1, 1]
    # ePSF ×5 oversampled, same Gaussian
    psf = gaussian(33, 16, 16, sigma * 5, 1.0)
    epsf = Table({"XCENTER": [50.0, 300.0], "YCENTER": [50.0, 300.0], "EPSF": [psf, psf]})
    return Cutout(frame=frame(), image=img, flags=fl, variance=var, zodi=zodi, epsf=epsf,
                  header=hdr, flags_header=fh, wave_wcs=wave, version="test")


C = (N - 1) / 2  # target pixel (14, 14)


def test_flag_mapping_by_name():
    fh = fits.Header()
    for b, n in BITS.items():
        fh[f"MSKN{b:04d}"] = n
    names = flag_bit_names(fh)
    assert names[3] == "OVERFLOW" and names[30] == "MYSTERY"
    v = (1 << 3) | (1 << 5) | (1 << 9)
    assert decode_flags(v, names) == ["OVERFLOW", "SOURCE", "DICHROIC"]
    flux_ok, pos_ok, rep = classify_flags(decode_flags(v, names))
    assert not flux_ok and pos_ok and rep == ["DICHROIC", "OVERFLOW"]  # SOURCE ignored
    assert classify_flags(["DICHROIC", "MYSTERY"])[:2] == (True, True)  # warning / unknown
    assert classify_flags(["GHOST"])[:2] == (False, False)


def test_clean_star_position_and_flux():
    total = 50.0  # MJy/sr summed over pixels
    cut = synthetic(stars=[(C + 0.3, C - 0.4, total)])
    m = measure(cut, target())
    assert m.detected and m.usable and m.position_usable
    w = WCS(cut.header)
    x, y = w.world_to_pixel_values(m.ra_meas, m.dec_meas)
    assert abs(x - (C + 0.3)) < 0.05 and abs(y - (C - 0.4)) < 0.05
    expected_jy = total * OMEGA_SR * 1e6
    # Aperture correction recovers the total to within the pixel-phase error of a 2 px
    # aperture on an undersampled PSF (~2.4% for this sub-pixel offset).
    assert m.flux_jy == pytest.approx(expected_jy, rel=0.03)
    assert 0.8 < m.aperture_correction < 1.0
    assert m.flux_err_jy > 0 and m.snr > 100
    assert m.pos_err_arcsec == pytest.approx(0.3)  # floor at high SNR
    assert m.offset_from_target_arcsec == pytest.approx(math.hypot(0.3, 0.4) * SCALE, rel=0.05)
    assert m.wavelength_um == pytest.approx(1.4 + 0.001 * (C + 0.3), abs=1e-3)
    assert m.flag_names == [] and m.note is None


def test_offset_star_within_box_found():
    m = measure(synthetic(stars=[(C + 1.6, C, 20.0)]), target())
    assert m.detected and m.offset_from_target_arcsec == pytest.approx(1.6 * SCALE, rel=0.05)


def test_blank_field_forced_photometry():
    m = measure(synthetic(noise=0.01), target())
    assert not m.detected and m.ra_meas is None and m.pos_err_arcsec is None
    assert m.flux_jy is not None and abs(m.flux_jy / m.flux_err_jy) < 5
    assert m.usable and not m.position_usable  # a valid non-detection flux sample


def test_neighbour_wing_is_not_a_detection():
    # Bright star centred 3 px away: its wing reaches the box edge but is not our source.
    m = measure(synthetic(stars=[(C + 3.0, C, 200.0)]), target())
    assert not m.detected


def test_nan_core_still_detected_but_flux_unusable():
    cut = synthetic(stars=[(C, C, 100.0)], nan_at=(14, 14))
    m = measure(cut, target())
    assert m.detected and m.position_usable and not m.usable
    assert "MASKED_PIXELS" in m.flag_names


def test_saturation_flags_spoil_flux_not_position():
    fl = np.zeros((N, N), np.int64)
    fl[14, 14] = (1 << 3) | (1 << 5)  # OVERFLOW + SOURCE
    m = measure(synthetic(stars=[(C, C, 100.0)], flags=fl), target())
    assert m.detected and not m.usable and m.position_usable
    assert m.flag_names == ["OVERFLOW"] and m.pos_err_arcsec == pytest.approx(1.5)


def test_ghost_spoils_position():
    fl = np.zeros((N, N), np.int64)
    fl[14, 15] = 1 << 8  # GHOST
    m = measure(synthetic(stars=[(C, C, 100.0)], flags=fl), target())
    assert m.detected and not m.usable and not m.position_usable


def test_hot_pixel_masked_from_fit():
    fl = np.zeros((N, N), np.int64)
    fl[15, 14] = 1 << 12  # HOT, inside aperture
    cut = synthetic(stars=[(C, C, 100.0)], flags=fl)
    cut.image[15, 14] = 1e4
    m = measure(cut, target())
    x, y = WCS(cut.header).world_to_pixel_values(m.ra_meas, m.dec_meas)
    assert abs(x - C) < 0.1 and abs(y - C) < 0.1  # not dragged by the hot pixel
    assert not m.usable and "HOT" in m.flag_names


def test_target_outside_cutout():
    m = measure(synthetic(), target(ra=RA0 + 1.0))
    assert not m.detected and m.note == "target outside cutout"


def test_failed_cutout():
    m = measure(Cutout(frame=frame(), status="failed", error="HTTP 503"), target())
    assert not m.detected and not m.usable and "503" in m.note


def test_epsf_fraction_nearest_row():
    t = Table({"XCENTER": [0.0, 1000.0], "YCENTER": [0.0, 1000.0],
               "EPSF": [gaussian(33, 16, 16, 5, 1), gaussian(33, 16, 16, 15, 1)]})
    narrow = epsf_aperture_fraction(t, 10, 10, 2.0)
    wide = epsf_aperture_fraction(t, 990, 990, 2.0)
    assert narrow == pytest.approx(1 - math.exp(-2**2 / 2), abs=0.01)  # σ = 1 native px
    assert wide < narrow


# ---- Done check on real fixtures (step 3) -----------------------------------

FIXTURES = Path(__file__).parent.parent / "fixtures"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text())
BARNARD = [k for k in MANIFEST if k.startswith("barnard_")]


def _fixture(name):
    m = MANIFEST[name]
    f = FrameRef(**m["frame"])
    cut = parse_cutout(f, (FIXTURES / m["file"]).read_bytes())
    t = Target(coord=SkyPosition(**m["target"]), time_range=TimeRange(), bands=[1, 2, 3, 4, 5, 6],
               cutout_size_deg=m["cutout_size_deg"], max_frames=1)
    return f, cut, t


def _gaia_barnard_at(mjd):
    g = MANIFEST["_gaia_dr3_barnard"]
    c = SkyCoord(g["ra"] * u.deg, g["dec"] * u.deg, pm_ra_cosdec=g["pmra"] * u.mas / u.yr,
                 pm_dec=g["pmdec"] * u.mas / u.yr, distance=Distance(parallax=g["parallax"] * u.mas),
                 radial_velocity=g["radial_velocity"] * u.km / u.s, obstime=Time(g["ref_epoch"], format="jyear"))
    return c.apply_space_motion(new_obstime=Time(mjd, format="mjd"))


@pytest.mark.parametrize("name", BARNARD)
def test_barnard_detected_within_1px_of_gaia(name):
    f, cut, t = _fixture(name)
    m = measure(cut, t)
    assert m.detected and m.position_usable
    gaia = _gaia_barnard_at(f.t_mid)
    sep = gaia.separation(SkyCoord(m.ra_meas * u.deg, m.dec_meas * u.deg)).arcsec
    assert sep < f.pixel_scale_arcsec, f"{sep:.2f}\" from Gaia"
    # λ inside the detector's range, allowing ±Δλ/2 (SIA em range is not a hard per-pixel bound)
    assert f.em_min_um - m.bandwidth_um / 2 <= m.wavelength_um <= f.em_max_um + m.bandwidth_um / 2
    # Barnard's Star saturates SPHEREx: flux flagged unusable, position kept
    assert not m.usable and "OVERFLOW" in m.flag_names
    assert 1.0 < m.flux_jy < 20.0  # right order of magnitude for a J≈5 M dwarf


def test_blank_field_fixture_not_detected():
    _, cut, t = _fixture("blank_badpix_d1")
    m = measure(cut, t)
    assert not m.detected and abs(m.flux_jy) < 0.01


def test_neighbour_in_box_corner_is_not_the_source():
    """2.5 px away diagonally: inside the 5×5 box, outside the 2 px detection radius."""
    m = measure(synthetic(stars=[(C + 1.8, C + 1.8, 50.0)]), target())
    assert not m.detected and m.ra_meas is None


def test_masked_core_gets_larger_position_floor():
    fl = np.zeros((N, N), np.int64)
    fl[14, 14] = 1 << 3  # OVERFLOW
    cut = synthetic(stars=[(C, C, 100.0)], flags=fl, nan_at=(14, 14))
    m = measure(cut, target())
    assert m.detected and "MASKED_PIXELS" in m.flag_names and m.pos_err_arcsec == pytest.approx(3.0)


def _saturated_star(total=400.0, core_r=1.1, x0=C + 0.3, y0=C - 0.2):
    """Bright star whose core (r ≤ core_r px) is saturated: NaN + OVERFLOW/BLOOM flags."""
    fl = np.zeros((N, N), np.int64)
    yy, xx = np.mgrid[0:N, 0:N]
    core = np.hypot(xx - x0, yy - y0) <= core_r
    fl[core] = (1 << 3)  # OVERFLOW (name mapped in BITS)
    cut = synthetic(stars=[(x0, y0, total)], flags=fl)
    cut.image[core] = np.nan
    return cut, total, x0, y0


def test_wing_fit_recovers_flux_of_masked_core():
    cut, total, x0, y0 = _saturated_star()
    m = measure(cut, target())
    assert m.detected and m.flux_method == "psf_wings" and not m.usable
    expected = total * OMEGA_SR * 1e6
    assert m.flux_jy == pytest.approx(expected, rel=0.05)  # the aperture alone loses the core
    x, y = WCS(cut.header).world_to_pixel_values(m.ra_meas, m.dec_meas)
    assert abs(x - x0) < 0.1 and abs(y - y0) < 0.1  # position from the ePSF fit
    assert m.psf_fit_rchi2 is not None


def test_wing_fit_gives_up_without_wings():
    # saturated region larger than the ePSF stamp (R Dra-like): the wing fit must give up
    cut, total, *_ = _saturated_star(core_r=4.5)
    m = measure(cut, target())
    assert m.flux_method != "psf_wings" and m.psf_fit_rchi2 is None and not m.usable


def test_saturated_without_masked_core_keeps_aperture():
    fl = np.zeros((N, N), np.int64)
    fl[14, 14] = 1 << 3  # OVERFLOW, but the pixel value is fine
    m = measure(synthetic(stars=[(C, C, 100.0)], flags=fl), target())
    assert m.flux_method == "aperture"
