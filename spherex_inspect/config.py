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
