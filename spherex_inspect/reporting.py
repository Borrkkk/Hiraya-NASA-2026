"""[7] Reporting: the only component that knows the public JSON shape.

Makes no decisions and re-ranks nothing; it only assembles and passes status through.
"""
from __future__ import annotations

from .models import DiscoveryResult, FramesResponse, Status, Target


def frames_response(target: Target, result: DiscoveryResult, warnings: list[str]) -> FramesResponse:
    status: Status = "partial" if any("failed" in w for w in warnings) else "ok"
    return FramesResponse(
        query=target,
        n_found=result.n_found,
        n_returned=len(result.frames),
        collections=result.collections,
        frames=result.frames,
        warnings=warnings,
        status=status,
    )
