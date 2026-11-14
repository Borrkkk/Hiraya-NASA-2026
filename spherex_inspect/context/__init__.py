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
from .solar_system import SolarSystemLookup

log = logging.getLogger(__name__)

__all__ = ["FieldContextService", "SolarSystemLookup", "cone_radius_arcsec", "default_service"]


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
    """``solar=None`` skips the per-frame solar-system lookup (used by tests and /context)."""

    def __init__(self, adapters: list[CatalogAdapter] | None = None, solar: SolarSystemLookup | None = None):
        self.adapters = adapters if adapters is not None else default_adapters()
        self.solar = solar

    async def fetch(self, target: Target, frames: list[FrameRef], t: float | None = None
                    ) -> tuple[list[CatalogSource], dict[str, str], dict[str, list]]:
        """Fixed-catalog cones + per-frame solar-system lookup, all concurrently.
        → (catalog sources, status by source, {frame_id: solar-system bodies}). Never raises."""
        cat_task = asyncio.create_task(self._catalogs(target, frames, t))
        solar_by_frame: dict[str, list] = {}
        solar_status: dict[str, str] = {}
        if self.solar is not None and frames:
            try:
                solar_by_frame, solar_status = await self.solar.lookup(target, frames)
            except Exception as exc:  # lookup() should not raise; belt and braces
                log.warning("solar-system lookup failed: %s", exc)
                solar_status = {"skybot": f"error: {type(exc).__name__}: {str(exc)[:200]}"}
        sources, status = await cat_task
        return sources, {**status, **solar_status}, solar_by_frame

    async def _catalogs(self, target: Target, frames: list[FrameRef], t: float | None
                        ) -> tuple[list[CatalogSource], dict[str, str]]:
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
              status: dict[str, str], summary: PointSummary | None, t: float | None = None,
              solar_by_frame: dict[str, list] | None = None) -> FieldContext:
        t_ref = reference_mjd(frames, summary, t)
        bodies = group_sources(sources, t_ref, (target.coord.ra, target.coord.dec), cone_radius_arcsec(target))
        lp = summary.latest_position if summary is not None else None
        if lp is not None:  # separations from the measured source, not the target
            for b in bodies:
                b.separation_arcsec = sep_arcsec(b.ra_at_t, b.dec_at_t, lp.ra, lp.dec)
            bodies.sort(key=lambda b: b.separation_arcsec)
        candidates = list(bodies)
        if lp is not None and lp.frame_id and solar_by_frame and solar_by_frame.get(lp.frame_id):
            # A solar-system body in the very frame of the latest measured position can explain
            # the detection (e.g. an asteroid crossing the cutout); without this, a known
            # asteroid would be reported as a candidate discovery.
            for sb in solar_by_frame[lp.frame_id]:
                c = sb.model_copy()
                c.separation_arcsec = sep_arcsec(c.ra_at_t, c.dec_at_t, lp.ra, lp.dec)
                candidates.append(c)
            candidates.sort(key=lambda b: b.separation_arcsec)
        best, verdict, note = decide(candidates, summary)
        fixed = [status[a.name] for a in self.adapters if a.name in status]
        if fixed and all(not s.startswith("ok") for s in fixed):
            note = "all catalogs failed; verdict is not meaningful"
        return FieldContext(best_match=best, nearby=bodies, solar_system_by_frame=solar_by_frame or {}, verdict=verdict,
                            status_by_source=status, note=note, t_ref=t_ref)


def default_service() -> FieldContextService:
    return FieldContextService(default_adapters(), SolarSystemLookup())
