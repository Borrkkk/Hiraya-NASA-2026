"""[3] Cutout Retrieval: download cutout MEFs, in parallel, with retries + disk cache.

Talks to IRSA *data* only. Opens the FITS structure (HDUs, headers, WCS objects)
but does not interpret pixels. A failed frame is marked failed; the rest carry on.
"""
from __future__ import annotations

import asyncio
import io
import logging
import time

import httpx
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS

from . import config
from .cache import cutout_key, get_cache
from .models import Cutout, FrameRef, Target

log = logging.getLogger(__name__)

EXPECTED_HDUS = ("IMAGE", "FLAGS", "VARIANCE", "ZODI", "EPSF", "WCS-WAVE")


def _silence_sip_info() -> None:
    """The alternate (spectral) WCS triggers a harmless 'Inconsistent SIP' INFO
    from astropy on every frame (same filter as the IRSA tutorial)."""
    from astropy import log as astropy_log

    class _NoSip(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            return "Inconsistent SIP distortion" not in record.getMessage()

    if not any(isinstance(f, _NoSip) or type(f).__name__ == "_NoSip" for f in astropy_log.filters):
        astropy_log.addFilter(_NoSip())


_silence_sip_info()


class _Retryable(Exception):
    pass


class _Fatal(Exception):
    pass


# --------------------------------------------------------------------------- #
# Parsing (pure)
# --------------------------------------------------------------------------- #


def parse_cutout(frame: FrameRef, raw: bytes, from_cache: bool = False) -> Cutout:
    """Raw MEF bytes → Cutout. Raises ValueError if the file isn't a valid cutout."""
    if not raw.startswith(b"SIMPLE"):
        raise ValueError(f"not a FITS file (starts with {raw[:40]!r})")
    with fits.open(io.BytesIO(raw), memmap=False) as hdul:
        names = {h.name for h in hdul}
        missing = [n for n in EXPECTED_HDUS if n not in names]
        if missing:
            raise ValueError(f"cutout missing HDUs {missing}")
        img_hdr = hdul["IMAGE"].header.copy()
        wave_wcs = WCS(img_hdr, fobj=hdul, key="W")
        wave_wcs.sip = None
        return Cutout(
            frame=frame,
            status="ok",
            image=np.array(hdul["IMAGE"].data, dtype=np.float64),
            flags=np.array(hdul["FLAGS"].data, dtype=np.int64),
            variance=np.array(hdul["VARIANCE"].data, dtype=np.float64),
            zodi=np.array(hdul["ZODI"].data, dtype=np.float64),
            epsf=hdul["EPSF"].data.copy(),
            header=img_hdr,
            flags_header=hdul["FLAGS"].header.copy(),
            wave_wcs=wave_wcs,
            version=str(hdul[0].header.get("VERSION")) if hdul[0].header.get("VERSION") is not None else None,
            from_cache=from_cache,
        )


# --------------------------------------------------------------------------- #
# Component
# --------------------------------------------------------------------------- #


class CutoutRetrieval:
    def __init__(
        self,
        cache=None,
        concurrency: int | None = None,
        timeout_s: float | None = None,
        retries: int | None = None,
        backoff_s: float | None = None,
        client: httpx.AsyncClient | None = None,
    ):
        self.cache = cache if cache is not None else get_cache()
        self.concurrency = concurrency or config.CUTOUT_CONCURRENCY
        self.timeout_s = timeout_s or config.CUTOUT_TIMEOUT_S
        self.retries = retries or config.CUTOUT_RETRIES
        self.backoff_s = config.CUTOUT_BACKOFF_S if backoff_s is None else backoff_s
        self._client = client

    async def fetch(self, frames: list[FrameRef], target: Target) -> list[Cutout]:
        """One Cutout per frame, same order. Never raises for a single frame."""
        sem = asyncio.Semaphore(self.concurrency)
        own_client = self._client is None
        client = self._client or httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_s), follow_redirects=True,
            limits=httpx.Limits(max_connections=self.concurrency),
        )
        try:
            return list(await asyncio.gather(*(self._one(client, sem, f, target) for f in frames)))
        finally:
            if own_client:
                await client.aclose()

    async def _one(self, client: httpx.AsyncClient, sem: asyncio.Semaphore, frame: FrameRef, target: Target) -> Cutout:
        key = cutout_key(frame.frame_id, target.coord.ra, target.coord.dec, target.cutout_size_deg)
        raw = self.cache.get(key)
        if raw is not None:
            try:
                return await asyncio.to_thread(parse_cutout, frame, raw, True)
            except Exception as exc:  # corrupt/unparseable entry: drop and re-download
                log.warning("bad cache entry %s (%s); re-downloading", key, exc)
                self.cache.delete(key)

        t0 = time.monotonic()
        last_err = "unknown error"
        for attempt in range(1, self.retries + 1):
            try:
                async with sem:
                    raw = await self._download(client, frame.cutout_url)
                cut = await asyncio.to_thread(parse_cutout, frame, raw, False)
                self.cache.set(key, raw)
                cut.extra["download_s"] = round(time.monotonic() - t0, 2)
                cut.extra["attempts"] = attempt
                return cut
            except _Fatal as exc:
                last_err = str(exc)
                break
            except Exception as exc:  # 5xx, transport errors, truncated/invalid FITS, WCS errors
                last_err = f"{type(exc).__name__}: {exc}"
                log.info("cutout %s attempt %d/%d failed: %s", frame.frame_id, attempt, self.retries, last_err)
                if attempt < self.retries:
                    await asyncio.sleep(self.backoff_s * attempt)
        return Cutout(frame=frame, status="failed", error=last_err)

    async def _download(self, client: httpx.AsyncClient, url: str) -> bytes:
        r = await client.get(url)
        if r.status_code in config.RETRY_STATUS:
            raise _Retryable(f"HTTP {r.status_code}")
        if r.status_code != 200:
            raise _Fatal(f"HTTP {r.status_code}: {r.text[:200]}")
        return r.content
