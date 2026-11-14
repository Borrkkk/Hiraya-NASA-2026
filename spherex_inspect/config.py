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
