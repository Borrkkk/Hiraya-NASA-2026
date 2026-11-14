"""HTTP layer. No logic: parse query params → orchestrator → JSON."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

import spherex_inspect
from spherex_inspect.discovery import DiscoveryError
from spherex_inspect.intake import IntakeError
from spherex_inspect.models import FramesResponse, InspectRequest, InspectResponse

app = FastAPI(title="SPHEREx Point Inspection API", version="0.1.0")


def _bands(bands: str | None) -> list[int] | None:
    if not bands:
        return None
    try:
        return [int(b) for b in bands.split(",") if b.strip()]
    except ValueError:
        raise HTTPException(422, f"bands must be a comma-separated list of 1..6, got {bands!r}")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/inspect/frames", response_model=FramesResponse)
async def inspect_frames(
    ra: str = Query(..., description="RA in degrees or sexagesimal (hours)"),
    dec: str = Query(..., description="Dec in degrees or sexagesimal"),
    start: str | None = Query(None, description="Start time, MJD or ISO"),
    end: str | None = Query(None, description="End time, MJD or ISO"),
    bands: str | None = Query(None, description="Detectors, e.g. 1,4,6"),
    size: float | None = Query(None, description="Cutout size in degrees"),
    max_frames: int | None = Query(None),
) -> FramesResponse:
    req = InspectRequest(
        ra=ra, dec=dec, time_start=start, time_end=end,
        bands=_bands(bands), cutout_size_deg=size, max_frames=max_frames,
    )
    try:
        return await spherex_inspect.inspect_frames(req)
    except IntakeError as exc:
        raise HTTPException(422, str(exc))
    except DiscoveryError as exc:
        raise HTTPException(502, f"IRSA unavailable: {exc}")


@app.get("/inspect", response_model=InspectResponse)
async def inspect(
    ra: str = Query(..., description="RA in degrees or sexagesimal (hours)"),
    dec: str = Query(..., description="Dec in degrees or sexagesimal"),
    start: str | None = Query(None, description="Start time, MJD or ISO"),
    end: str | None = Query(None, description="End time, MJD or ISO"),
    bands: str | None = Query(None, description="Detectors, e.g. 1,4,6"),
    size: float | None = Query(None, description="Cutout size in degrees"),
    max_frames: int | None = Query(None),
    include_context: bool = Query(True),
) -> InspectResponse:
    req = InspectRequest(
        ra=ra, dec=dec, time_start=start, time_end=end, bands=_bands(bands),
        cutout_size_deg=size, max_frames=max_frames, include_context=include_context,
    )
    try:
        return await spherex_inspect.inspect_point(req)
    except IntakeError as exc:
        raise HTTPException(422, str(exc))
    except DiscoveryError as exc:
        raise HTTPException(502, f"IRSA unavailable: {exc}")
