"""[0] Orchestrator: order of calls, data passing, partial-failure policy.

No science, no I/O details, no formatting.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from . import intake, reporting
from .aggregation import aggregate
from .context import FieldContextService, default_service
from .discovery import FrameDiscovery
from .measurement import measure
from .models import (
    Cutout,
    FieldContext,
    FrameMeasurement,
    FrameRef,
    FramesResponse,
    InspectRequest,
    InspectResponse,
    Target,
)
from .retrieval import CutoutRetrieval
from .stacking import stack_and_difference

__all__ = ["inspect_point", "inspect_frames", "inspect_context", "discover_and_fetch", "measure_frames",
           "get_discovery", "get_retrieval", "get_context"]

_discovery: FrameDiscovery | None = None
_retrieval: CutoutRetrieval | None = None
_context: FieldContextService | None = None


def get_discovery() -> FrameDiscovery:
    global _discovery
    if _discovery is None:
        _discovery = FrameDiscovery()
    return _discovery


def set_discovery(d: FrameDiscovery | None) -> None:
    """Test hook: swap the discovery component (e.g. with a fake backend)."""
    global _discovery
    _discovery = d


def get_retrieval() -> CutoutRetrieval:
    global _retrieval
    if _retrieval is None:
        _retrieval = CutoutRetrieval()
    return _retrieval


def set_retrieval(r: CutoutRetrieval | None) -> None:
    global _retrieval
    _retrieval = r


def get_context() -> FieldContextService:
    global _context
    if _context is None:
        _context = default_service()
    return _context


def set_context(c: FieldContextService | None) -> None:
    global _context
    _context = c


async def inspect_frames(req: InspectRequest) -> FramesResponse:
    """Discovery only: which frames contain this point (fast; for the flip-book)."""
    target = intake.to_target(req)
    result, warnings = await get_discovery().discover(target)
    return reporting.frames_response(target, result, warnings)


@dataclass
class FetchResult:
    target: Target
    frames: list[FrameRef]
    cutouts: list[Cutout]
    n_found: int
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> list[Cutout]:
        return [c for c in self.cutouts if c.status == "ok"]


async def _fetch(target: Target, frames: list[FrameRef], warnings: list[str]) -> list[Cutout]:
    cutouts = await get_retrieval().fetch(frames, target)
    n_failed = sum(c.status == "failed" for c in cutouts)
    if n_failed:
        warnings.append(f"retrieval: {n_failed} of {len(cutouts)} cutouts failed to download")
    return cutouts


async def _measure(cutouts: list[Cutout], target: Target) -> list[FrameMeasurement]:
    return await asyncio.to_thread(lambda: [measure(c, target) for c in cutouts])


async def discover_and_fetch(req: InspectRequest) -> FetchResult:
    """Intake → Discovery → Retrieval. Failed cutouts are kept (status='failed')
    and summarised in warnings; the pipeline carries on with the rest."""
    target = intake.to_target(req)
    result, warnings = await get_discovery().discover(target)
    cutouts = await _fetch(target, result.frames, warnings)
    return FetchResult(target, result.frames, cutouts, result.n_found, warnings)


async def measure_frames(req: InspectRequest) -> tuple[FetchResult, list[FrameMeasurement]]:
    """Intake → Discovery → Retrieval → Measurement (one measurement per frame, same order;
    failed cutouts give an empty measurement with a note)."""
    fetched = await discover_and_fetch(req)
    return fetched, await _measure(fetched.cutouts, fetched.target)


async def inspect_point(req: InspectRequest) -> InspectResponse:
    """Full pipeline. Catalog queries (Field Context phase 1) run concurrently with
    retrieval + measurement; matching (phase 2) waits for the PointSummary."""
    target = intake.to_target(req)
    result, warnings = await get_discovery().discover(target)
    frames = result.frames

    ctx_task = None
    if target.include_context:
        ctx_task = asyncio.create_task(get_context().fetch(target, frames))

    cutouts = await _fetch(target, frames, warnings)
    measurements = await _measure(cutouts, target)
    summary = aggregate(measurements)
    # Stacking works on pixels across frames; its results ride along in the summary.
    summary.stacked, summary.difference = await asyncio.to_thread(stack_and_difference, cutouts, target, measurements)
    if summary.quality.n_usable == 0 and summary.spectrum_flagged:
        warnings.append("summary: no usable flux samples; detected samples are flagged "
                        "(e.g. saturated) and listed in spectrum_flagged")

    context: FieldContext | None = None
    if ctx_task is not None:
        sources, status, solar = await ctx_task
        context = get_context().build(target, frames, sources, status, summary, solar_by_frame=solar)
        if context.candidate_discovery:
            warnings.append(f"candidate discovery: {context.note}")
        unexplained = [t for t in context.transients if t.kind == "unexplained"]
        if unexplained:
            warnings.append(f"difference images: {len(unexplained)} unexplained transient(s) "
                            f"(possible movers or artifacts), strongest S/N {unexplained[0].peak_snr:.0f} "
                            f"in {unexplained[0].frame_id}")
        failed = [k for k, v in status.items() if not v.startswith("ok")]
        if failed:
            warnings.append(f"context: catalog(s) failed: {', '.join(failed)}")
    return reporting.inspect_response(target, cutouts, measurements, summary, warnings, context)


async def inspect_context(req: InspectRequest, t: float | str | None = None) -> FieldContext:
    """Field Context only: known bodies around the point at time ``t`` (MJD or ISO; default now).
    No pixels are read, so there is no measured source and no best match."""
    target = intake.to_target(req)
    t_mjd = intake.parse_time(t)
    sources, status, _ = await get_context().fetch(target, [], t_mjd)
    return get_context().build(target, [], sources, status, None, t_mjd)
