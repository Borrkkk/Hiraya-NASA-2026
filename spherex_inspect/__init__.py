"""[0] Orchestrator: order of calls, data passing, partial-failure policy.

No science, no I/O details, no formatting.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from . import intake, reporting
from .discovery import FrameDiscovery
from .measurement import measure
from .models import Cutout, FrameMeasurement, FrameRef, FramesResponse, InspectRequest, Target
from .retrieval import CutoutRetrieval

__all__ = ["inspect_frames", "discover_and_fetch", "measure_frames", "get_discovery", "get_retrieval"]

_discovery: FrameDiscovery | None = None
_retrieval: CutoutRetrieval | None = None


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


async def discover_and_fetch(req: InspectRequest) -> FetchResult:
    """Intake → Discovery → Retrieval. Failed cutouts are kept (status='failed')
    and summarised in warnings; the pipeline carries on with the rest."""
    target = intake.to_target(req)
    result, warnings = await get_discovery().discover(target)
    cutouts = await get_retrieval().fetch(result.frames, target)
    n_failed = sum(c.status == "failed" for c in cutouts)
    if n_failed:
        warnings.append(f"retrieval: {n_failed} of {len(cutouts)} cutouts failed to download")
    return FetchResult(target, result.frames, cutouts, result.n_found, warnings)


async def measure_frames(req: InspectRequest) -> tuple[FetchResult, list[FrameMeasurement]]:
    """Intake → Discovery → Retrieval → Measurement (one measurement per frame, same order;
    failed cutouts give an empty measurement with a note)."""
    fetched = await discover_and_fetch(req)
    measurements = await asyncio.to_thread(lambda: [measure(c, fetched.target) for c in fetched.cutouts])
    return fetched, measurements
