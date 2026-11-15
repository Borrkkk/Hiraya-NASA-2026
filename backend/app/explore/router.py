"""The Explore page's API. Contract: frontend/src/lib/explore/types.ts.

  GET  /explore/area?ra&dec&fov                       the area, its epochs and bands
  GET  /explore/areas/{id}/frames/{epoch}/{band}      one greyscale PNG frame
  POST /explore/areas/{id}/inspect                    type guess + spectrum for a box
  POST /explore/areas/{id}/motion                     -> {jobId}
  POST /explore/areas/{id}/verify                     -> {jobId}
  GET  /explore/jobs/{jobId}                          progress and result
  GET  /explore/search?q=                             find a place to look at
"""
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from . import jobs
from .analysis import find_movers, inspect
from ..archive import ArchiveError
from .common import BAND_WINDOWS, key, parse_area_id
from .sources import ensure_shots
from .frames import build_area, frame_png, sample_suggestion
from .search import search
from .verify import verify

router = APIRouter(prefix="/explore", tags=["explore"])


class Box(BaseModel):
    ra: float
    dec: float
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class Target(BaseModel):
    kind: Literal["box", "mover"]
    box: Box
    moverId: str | None = None


class InspectBody(BaseModel):
    areaId: str
    target: Target
    epoch: str
    bands: list[str] = []


class MotionBody(BaseModel):
    areaId: str
    epochs: list[str] = Field(min_length=2)
    bands: list[str] = []


class VerifyBody(InspectBody):
    moverId: str | None = None


async def _ready(client, ra: float, dec: float) -> None:
    try:
        await ensure_shots(client, ra, dec)
    except ArchiveError as exc:
        raise HTTPException(502, detail=f"Couldn't reach NASA's SPHEREx archive: {exc}") from None


async def _area(area_id: str, request: Request) -> tuple[float, float]:
    try:
        ra, dec = parse_area_id(area_id)
    except KeyError:
        raise HTTPException(404, "Unknown area") from None
    await _ready(request.app.state.client, ra, dec)
    return ra, dec


@router.get("/area")
async def get_area(request: Request, ra: float, dec: float, fov: float | None = None):
    ra, dec = key(ra, dec)
    await _ready(request.app.state.client, ra, dec)
    area = await run_in_threadpool(build_area, ra, dec)
    if area is None:
        raise HTTPException(404, detail={
            "message": "SPHEREx hasn't observed this spot yet.",
            "suggestion": sample_suggestion()})
    return area


@router.get("/areas/{area_id}/frames/{epoch}/{band}")
async def get_frame(area_id: str, epoch: str, band: str, request: Request):
    if band not in BAND_WINDOWS:
        raise HTTPException(404, "Unknown band")
    ra, dec = await _area(area_id, request)
    png = await run_in_threadpool(frame_png, ra, dec, epoch, band)
    return Response(png, media_type="image/png", headers={"Cache-Control": "public, max-age=300"})


@router.post("/areas/{area_id}/inspect")
async def post_inspect(area_id: str, body: InspectBody, request: Request):
    ra, dec = await _area(area_id, request)
    target = body.target.model_dump()
    target["areaId"] = area_id
    return await run_in_threadpool(inspect, ra, dec, target, body.epoch)


@router.post("/areas/{area_id}/motion")
async def post_motion(area_id: str, body: MotionBody, request: Request):
    ra, dec = await _area(area_id, request)

    async def work(step):
        return await run_in_threadpool(find_movers, area_id, ra, dec, body.epochs, body.bands, step)

    return {"jobId": jobs.start(work)}


@router.post("/areas/{area_id}/verify")
async def post_verify(area_id: str, body: VerifyBody, request: Request):
    ra, dec = await _area(area_id, request)
    target = body.target.model_dump()
    target["areaId"] = area_id
    target["moverId"] = body.moverId or target.get("moverId")

    async def work(step):
        return await verify(request.app.state.client, ra, dec, target, body.epoch, step)

    return {"jobId": jobs.start(work)}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "Unknown job")
    return job


@router.get("/search")
async def get_search(q: str = "", request: Request = None):
    return {"results": await search(request.app.state.client, q)}
