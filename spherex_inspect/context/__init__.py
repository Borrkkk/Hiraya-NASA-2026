"""[6] Field Context: which known bodies are in / around the frames at their times.

Uses frame metadata and the measured position, never pixels. Two phases so the
orchestrator can run the slow catalog queries concurrently with retrieval + measurement:

    sources, status = await ctx.fetch(target, frames)   # network (catalogs)
    context = ctx.build(target, frames, sources, status, summary)   # pure
"""
from __future__ import annotations

import asyncio
import logging
from statistics import median

from .. import config
from ..models import FieldContext, FrameRef, PointSummary, Target
from .base import CatalogAdapter, CatalogSource, CatalogUnavailable, ConeQuery
from .fixed import default_adapters
from .match import decide, group_sources, sep_arcsec

log = logging.getLogger(__name__)

__all__ = ["FieldContextService", "cone_radius_arcsec"]


def cone_radius_arcsec(target: Target) -> float:
    return min(target.cutout_size_deg / 2 * 3600.0, config.CONTEXT_MAX_CONE_ARCSEC)


def reference_mjd(frames: list[FrameRef], summary: PointSummary | None, t: float | None = None) -> float:
    """Time catalog positions are propagated to: the latest measured position (what gets
    matched), else an explicit time, else the median frame time."""
    if summary is not None and summary.latest_position is not None:
        return summary.latest_position.t_mid
    if t is not None:
        return t
    if frames:
        return float(median(f.t_mid for f in frames))
    from astropy.time import Time

    return float(Time.now().mjd)


class FieldContextService:
    def __init__(self, adapters: list[CatalogAdapter] | None = None):
        self.adapters = adapters if adapters is not None else default_adapters()

    async def fetch(self, target: Target, frames: list[FrameRef], t: float | None = None
                    ) -> tuple[list[CatalogSource], dict[str, str]]:
        """Cone queries on every catalog, concurrently. Never raises: failures go to status."""
        q = ConeQuery(ra=target.coord.ra, dec=target.coord.dec, radius_arcsec=cone_radius_arcsec(target),
                      mjd=reference_mjd(frames, None, t))

        async def one(a: CatalogAdapter):
            try:
                rows = await a.cone(q)
                return a.name, rows, f"ok ({len(rows)} rows)"
            except CatalogUnavailable as exc:
                return a.name, [], str(exc)
            except asyncio.TimeoutError:
                return a.name, [], f"timeout after {a.timeout_s:g}s"
            except Exception as exc:
                log.warning("catalog %s failed: %s", a.name, exc)
                return a.name, [], f"error: {type(exc).__name__}: {str(exc)[:200]}"

        results = await asyncio.gather(*(one(a) for a in self.adapters))
        sources = [s for _, rows, _ in results for s in rows]
        return sources, {name: st for name, _, st in results}

    def build(self, target: Target, frames: list[FrameRef], sources: list[CatalogSource],
              status: dict[str, str], summary: PointSummary | None, t: float | None = None) -> FieldContext:
        t_ref = reference_mjd(frames, summary, t)
        bodies = group_sources(sources, t_ref, (target.coord.ra, target.coord.dec), cone_radius_arcsec(target))
        lp = summary.latest_position if summary is not None else None
        if lp is not None:  # separations from the measured source, not the target
            for b in bodies:
                b.separation_arcsec = sep_arcsec(b.ra_at_t, b.dec_at_t, lp.ra, lp.dec)
            bodies.sort(key=lambda b: b.separation_arcsec)
        best, verdict, note = decide(bodies, summary)
        if all(not s.startswith("ok") for s in status.values()) and status:
            note = "all catalogs failed; verdict is not meaningful"
        return FieldContext(best_match=best, nearby=bodies, solar_system_by_frame={}, verdict=verdict,
                            status_by_source=status, note=note, t_ref=t_ref)
