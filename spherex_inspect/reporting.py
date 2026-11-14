"""[7] Reporting: the only component that knows the public JSON shape.

Makes no decisions and re-ranks nothing; it only assembles and passes status through.
"""
from __future__ import annotations

from .models import (
    Cutout,
    DiscoveryResult,
    FieldContext,
    FrameLite,
    FrameMeasurement,
    FramesResponse,
    InspectResponse,
    PointSummary,
    Status,
    Target,
)


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


def inspect_response(
    target: Target,
    cutouts: list[Cutout],
    measurements: list[FrameMeasurement],
    summary: PointSummary,
    warnings: list[str],
    context: FieldContext | None = None,
) -> InspectResponse:
    frames = []
    for c, m in zip(cutouts, measurements):
        f = c.frame
        if c.status != "ok":
            st = "failed"
        elif m.detected:
            st = "detected"
        else:
            st = "not_detected"
        frames.append(FrameLite(frame_id=f.frame_id, obs_id=f.obs_id, detector=f.detector, t_mid=f.t_mid,
                                release=f.release, cutout_url=f.cutout_url, full_url=f.full_url, status=st))
    n_failed = sum(c.status != "ok" for c in cutouts)
    status: Status = "ok"
    if cutouts and n_failed == len(cutouts):
        status = "failed"
    elif n_failed or any("failed" in w for w in warnings):  # incl. "context: catalog(s) failed"
        status = "partial"
    return InspectResponse(query=target, frames=frames, summary=summary, context=context,
                           warnings=warnings, status=status)
