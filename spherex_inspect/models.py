"""Data contracts shared by every component.

This file is the contract between components. Change a field only after agreeing
on it (see NOTES.md "Contract changes").

Units: positions in ICRS degrees, times in MJD (float), proper motion in mas/yr,
wavelength in µm, flux in Jy, separations in arcsec.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# Request / target
# --------------------------------------------------------------------------- #


class InspectRequest(BaseModel):
    """Raw user input. RA/Dec may be degrees or sexagesimal strings; times may
    be MJD floats or ISO strings. Validated and normalised by Intake."""

    ra: float | str
    dec: float | str
    time_start: float | str | None = None
    time_end: float | str | None = None
    bands: list[int] | None = None
    cutout_size_deg: float | None = None
    max_frames: int | None = None
    include_context: bool = True


class SkyPosition(BaseModel):
    ra: float  # deg, ICRS
    dec: float  # deg, ICRS


class TimeRange(BaseModel):
    start: float | None = None  # MJD
    end: float | None = None  # MJD


class Target(BaseModel):
    coord: SkyPosition
    time_range: TimeRange
    bands: list[int]  # detector numbers 1..6
    cutout_size_deg: float
    max_frames: int
    include_context: bool = True


# --------------------------------------------------------------------------- #
# Frames
# --------------------------------------------------------------------------- #


class FrameRef(BaseModel):
    # NOTE: obs_id is shared by the 6 detectors of one exposure, so `frame_id`
    # (= f"{obs_id}D{detector}") is the unique key. See NOTES.md.
    frame_id: str
    obs_id: str
    detector: int
    t_mid: float  # MJD
    t_min: float  # MJD
    t_max: float  # MJD
    footprint: list[tuple[float, float]]  # polygon vertices (ra, dec) deg
    release: str  # e.g. "DR1", "QR3"
    collection: str  # e.g. "spherex_dr1"
    em_min_um: float | None = None
    em_max_um: float | None = None
    pixel_scale_arcsec: float | None = None
    cutout_url: str
    full_url: str


@dataclass
class Cutout:
    """One downloaded cutout MEF (internal, never serialised as-is)."""

    frame: FrameRef
    status: Literal["ok", "failed"] = "ok"
    error: str | None = None
    image: Any = None  # np.ndarray, MJy/sr (zodi NOT subtracted)
    flags: Any = None  # np.ndarray int32
    variance: Any = None  # np.ndarray (MJy/sr)^2
    zodi: Any = None  # np.ndarray MJy/sr
    epsf: Any = None  # astropy Table (EPSF HDU)
    header: Any = None  # IMAGE header
    flags_header: Any = None  # FLAGS header (bit names MSKNnnnn)
    wave_wcs: Any = None  # astropy WCS (key="W", sip=None)
    version: str | None = None
    from_cache: bool = False
    extra: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Measurements / aggregation
# --------------------------------------------------------------------------- #


class FrameMeasurement(BaseModel):
    frame_id: str
    obs_id: str
    detector: int
    t_mid: float
    wavelength_um: float | None = None
    bandwidth_um: float | None = None
    detected: bool = False
    ra_meas: float | None = None
    dec_meas: float | None = None
    pos_err_arcsec: float | None = None
    offset_from_target_arcsec: float | None = None
    flux_jy: float | None = None
    flux_err_jy: float | None = None
    snr: float | None = None
    flag_bits: int = 0
    flag_names: list[str] = Field(default_factory=list)
    usable: bool = False  # flux usable (no unusable flag in the aperture, finite flux)
    # Proposed (NOTES.md): position usable even when the flux is not (e.g. a saturated star).
    position_usable: bool = False
    aperture_correction: float | None = None  # fraction of ePSF flux inside the aperture
    note: str | None = None  # why nothing could be measured, when that happens


class SpectrumSample(BaseModel):
    wavelength_um: float
    flux: float  # Jy
    err: float  # Jy
    frame_id: str
    bandwidth_um: float | None = None
    detector: int | None = None
    flags: list[str] = Field(default_factory=list)  # set on spectrum_flagged samples


class BinnedSpectrumSample(BaseModel):
    wavelength_um: float
    flux: float | None = None
    err: float | None = None
    n: int = 0


class PositionSample(BaseModel):
    t_mid: float
    ra: float
    dec: float
    err: float  # arcsec
    frame_id: str | None = None
    detector: int | None = None
    used_in_fit: bool = True  # False when rejected as an outlier by the pm fit


class ProperMotion(BaseModel):
    pm_ra_cosdec: float  # mas/yr
    pm_dec: float  # mas/yr
    err: float  # mas/yr, 1-sigma error on the total |pm|
    significance: float  # |pm| / err
    pm_ra_cosdec_err: float | None = None
    pm_dec_err: float | None = None
    pm_total: float | None = None  # mas/yr
    position_angle_deg: float | None = None  # east of north
    baseline_days: float | None = None
    n_used: int | None = None
    n_rejected: int | None = None
    reduced_chi2: float | None = None
    ref_epoch_mjd: float | None = None


class LightCurveSample(BaseModel):
    t_mid: float
    detector: int
    wavelength_um: float | None
    flux: float
    err: float
    frame_id: str


class BandVariability(BaseModel):
    detector: int
    n: int
    reduced_chi2: float | None = None
    amplitude: float | None = None
    variable: bool = False


class QualitySummary(BaseModel):
    n_frames: int
    n_usable: int  # flux-usable
    n_detected: int = 0
    n_position_usable: int = 0
    n_failed: int = 0  # cutouts that could not be measured
    flag_summary: dict[str, int] = Field(default_factory=dict)


class PointSummary(BaseModel):
    spectrum: list[SpectrumSample] = Field(default_factory=list)
    # Proposed: detected samples whose flux was rejected (e.g. saturated), for display only.
    spectrum_flagged: list[SpectrumSample] = Field(default_factory=list)
    spectrum_binned: list[BinnedSpectrumSample] = Field(default_factory=list)
    positions: list[PositionSample] = Field(default_factory=list)
    first_position: PositionSample | None = None
    latest_position: PositionSample | None = None
    proper_motion: ProperMotion | None = None
    # Fit result even when below the reporting thresholds (why pm was not reported).
    proper_motion_fit: ProperMotion | None = None
    proper_motion_note: str | None = None
    light_curve: list[LightCurveSample] = Field(default_factory=list)
    variability: list[BandVariability] = Field(default_factory=list)
    quality: QualitySummary


# --------------------------------------------------------------------------- #
# Field context
# --------------------------------------------------------------------------- #

ObjectClass = Literal[
    "star", "brown_dwarf", "variable_star", "galaxy", "qso", "asteroid", "comet", "unknown"
]


class KnownBody(BaseModel):
    name: str
    object_class: ObjectClass = "unknown"
    source_catalogs: list[str] = Field(default_factory=list)
    ra_at_t: float
    dec_at_t: float
    t_ref: float  # MJD the position applies to
    separation_arcsec: float | None = None
    pm: tuple[float, float] | None = None  # (pm_ra_cosdec, pm_dec) mas/yr
    mags: dict[str, float] = Field(default_factory=dict)
    is_solar_system: bool = False
    ids: dict[str, str] = Field(default_factory=dict)


class BestMatch(KnownBody):
    match_score: float


class FieldContext(BaseModel):
    best_match: BestMatch | None = None
    nearby: list[KnownBody] = Field(default_factory=list)
    solar_system_by_frame: dict[str, list[KnownBody]] = Field(default_factory=dict)
    verdict: Literal["matched", "ambiguous", "no_known_match"] = "no_known_match"
    status_by_source: dict[str, str] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Responses
# --------------------------------------------------------------------------- #

Status = Literal["ok", "partial", "failed"]


class FrameLite(BaseModel):
    frame_id: str
    obs_id: str
    detector: int
    t_mid: float
    release: str
    cutout_url: str
    full_url: str
    status: str = "listed"


class DiscoveryResult(BaseModel):
    """Output of Frame Discovery: the (possibly capped) frames plus counts."""

    frames: list[FrameRef]
    n_found: int  # before capping
    collections: list[str]


class FramesResponse(BaseModel):
    query: Target
    n_found: int
    n_returned: int
    collections: list[str]
    frames: list[FrameRef]
    warnings: list[str] = Field(default_factory=list)
    status: Status = "ok"


class InspectResponse(BaseModel):
    query: Target
    frames: list[FrameLite]
    summary: PointSummary | None = None
    context: FieldContext | None = None
    warnings: list[str] = Field(default_factory=list)
    status: Status = "ok"
