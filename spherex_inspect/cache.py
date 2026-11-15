"""Disk cache for *raw* service responses (cutout bytes, catalog responses).

Never stores derived results, so changing measurement code never needs a cache flush.
"""
from __future__ import annotations

from pathlib import Path

import diskcache

from . import config

_caches: dict[str, diskcache.Cache] = {}


def get_cache(directory: Path | str | None = None) -> diskcache.Cache:
    d = str(directory or config.CACHE_DIR)
    if d not in _caches:
        _caches[d] = diskcache.Cache(d, size_limit=config.CACHE_SIZE_LIMIT_BYTES)
    return _caches[d]


def cutout_key(frame_id: str, ra: float, dec: float, size_deg: float) -> str:
    return f"cutout:v1:{frame_id}:{ra:.7f}:{dec:.7f}:{size_deg:g}"
