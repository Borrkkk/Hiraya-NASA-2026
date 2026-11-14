"""Tunable numbers in one place (starting values from the implementer brief)."""
from __future__ import annotations

import os
from pathlib import Path

# Intake
DEFAULT_CUTOUT_SIZE_DEG = 0.05
MAX_CUTOUT_SIZE_DEG = 0.2
MIN_CUTOUT_SIZE_DEG = 0.005
DEFAULT_MAX_FRAMES = 200
HARD_MAX_FRAMES = 2000
ALL_BANDS = [1, 2, 3, 4, 5, 6]

# Discovery
SIA_SEARCH_RADIUS_ARCSEC = 1.0
SIA_RETRIES = 3
SIA_BACKOFF_S = 5.0  # seconds x attempt
# Frame lists change only at the weekly ingest: reuse a cached list for this long, and fall
# back to an older cached list if IRSA's SIA is failing.
SIA_CACHE_TTL_S = 6 * 3600
# Collections: keep the newest DR and newest QR (+ their _deep variants).
# Cubes are not single-exposure frames, so they are excluded.
COLLECTION_FILTER = "spherex"

# Cache
CACHE_DIR = Path(os.environ.get("SPHEREX_CACHE_DIR", ".cache"))
CACHE_SIZE_LIMIT_BYTES = int(float(os.environ.get("SPHEREX_CACHE_SIZE_GB", "10")) * 1e9)

# Cutout Retrieval
CUTOUT_CONCURRENCY = 8
CUTOUT_TIMEOUT_S = 120.0  # brief: remote_timeout=120
CUTOUT_RETRIES = 3
CUTOUT_BACKOFF_S = 10.0  # seconds x attempt
RETRY_STATUS = {429, 500, 502, 503, 504}

# Frame Measurement (brief §3, §4)
BG_ANNULUS_PX = (4.0, 6.0)
BG_MIN_PIXELS = 8
CENTROID_BOX_PX = 5
DETECT_SNR = 5.0
APERTURE_RADIUS_PX = 2.0
POS_ERR_FLOOR_ARCSEC = 0.3
# Saturated stars centroid worse than their SNR implies (Barnard's fixtures: 0.8–2.9" vs
# Gaia), so a larger floor applies when saturation flags are in the aperture.
SATURATED_POS_ERR_FLOOR_ARCSEC = 1.5
FLAGS_SATURATION = frozenset({"OVERFLOW", "BLOOM", "NONLINEAR"})
PIXEL_SCALE_TOLERANCE = 0.02  # SIA s_pixel_scale vs WCS must agree within 2%
# Flag classes, by NAME (bit numbers are read from the FLAGS header at runtime).
FLAGS_UNUSABLE = frozenset({
    "TRANSIENT", "OVERFLOW", "SUR_ERROR", "NONFUNC", "MISSING_DATA", "HOT", "COLD", "NONLINEAR",
    "PERSIST", "OUTLIER", "GHOST", "GHOST_FPA", "GHOST_EXT", "STREAK", "BLOOM", "SNOWBALL", "HALO",
})
FLAGS_WARNING = frozenset({"DICHROIC", "PHANMISS", "CROSSTALK"})
FLAGS_IGNORE = frozenset({"SOURCE", "FULLSAMPLE"})
# Pixels with these flags are dropped from the centroid fit and the background.
FLAGS_BAD_PIXEL = frozenset({"NONFUNC", "MISSING_DATA", "HOT", "COLD"})
# Proposed (NOTES.md): saturation-type flags spoil the flux but not the centroid of a bright
# star, so only these flags make the *position* unusable.
FLAGS_POSITION_UNUSABLE = frozenset({"PERSIST", "GHOST", "GHOST_FPA", "GHOST_EXT", "STREAK", "HALO", "SNOWBALL"})

# Time-Series Aggregation (brief §7)
PM_MIN_BASELINE_DAYS = 150.0
PM_MIN_DETECTIONS = 6
PM_MIN_SIGNIFICANCE = 3.0
PM_CLIP_SIGMA = 4.0  # drop position outliers beyond this (after error rescaling)
PM_MAX_CLIP_FRACTION = 0.2
SPECTRUM_BINS = 102
SPECTRUM_RANGE_UM = (0.75, 5.0)

# Field Context (brief §6)
CONTEXT_MAX_CONE_ARCSEC = 120.0  # cone = cutout half-size, capped here
# Fastest known stellar pm is Barnard's ~10.4"/yr; widen catalog cones so a source this fast,
# seen at its catalog epoch, still lands in the cone at the frame time.
CONTEXT_PM_MAX_ARCSEC_YR = 11.0
CONTEXT_TIMEOUT_S = 45.0
# After a timeout / 5xx, skip that catalog for this long instead of waiting again.
CONTEXT_OUTAGE_S = 15 * 60
CONTEXT_CACHE_TTL_S = {"simbad": 7 * 86400, "gaia_dr3": None, "catwise2020": None}
# SIMBAD object types that are not separate light sources (planets carry the host's
# coordinates: Barnard's Star b/c/d/e would otherwise make every match "ambiguous").
SIMBAD_SKIP_OTYPES = frozenset({"Pl", "Pl?"})
IRSA_TAP_URL = "https://irsa.ipac.caltech.edu/TAP"
SIMBAD_SERVERS = ("simbad.cds.unistra.fr", "simbad.harvard.edu")  # CDS 404'd on 2026-11-14
MATCH_GROUP_RADIUS_ARCSEC = 1.5  # same object across catalogs
MATCH_SIGMA_PSF_ARCSEC = 3.0
MATCH_WEIGHTS = {"position": 0.6, "pm": 0.25, "ir": 0.15}
MATCH_MIN_SCORE = 0.6
MATCH_MIN_MARGIN = 0.2
MATCH_AMBIGUOUS_RADIUS_ARCSEC = 6.0
MATCH_PM_MIN_SIGNIFICANCE = 3.0
MATCH_IR_WINDOW_UM = 0.3
MATCH_IR_SIGMA_MAG = 0.3
# Zero points (Jy): 2MASS Ks (Cohen+2003), WISE W1/W2 (Jarrett+2011)
IR_BANDS = {"Ks": (2.16, 666.7), "W1": (3.4, 309.54), "W2": (4.6, 171.79)}
