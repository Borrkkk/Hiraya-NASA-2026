import asyncio
from contextlib import asynccontextmanager
import ssl
import httpx
import truststore
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from .archive import ArchiveError, cutout_url, download, search
from .imaging import align, render, target_wcs
from .models import SearchResult, SkyRequest, TimelapseRequest
from .local_store import cutout_path, list_targets, local_path, search_local
from .explore.router import router as explore_router

@asynccontextmanager
async def lifespan(app):
    # The system trust store, so corporate or conda-less Python installs verify TLS like curl does.
    tls = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    async with httpx.AsyncClient(verify=tls, timeout=httpx.Timeout(90, connect=15), follow_redirects=False,
                                 limits=httpx.Limits(max_connections=8)) as client:
        app.state.client = client
        app.state.jobs = asyncio.Semaphore(2)
        app.state.downloads = asyncio.Semaphore(4)
        yield

app = FastAPI(title='Pulsr SPHEREx Backend', version='0.1.0', lifespan=lifespan)

app.include_router(explore_router)

@app.exception_handler(ArchiveError)
async def archive_error(request, exc):
    return JSONResponse(status_code=502, content={'detail': str(exc)})

@app.get('/health')
def health():
    return {'status': 'ok'}

@app.post('/spherex/search', response_model=SearchResult)
async def search_exposures(payload: SkyRequest, request: Request):
    async with request.app.state.jobs:
        if payload.source == 'local':
            return await run_in_threadpool(search_local, payload)
        return await search(request.app.state.client, payload)

@app.get('/spherex/targets')
def targets():
    return list_targets()

@app.get('/spherex/targets/{target_id}/cutouts/{filename}')
def local_cutout(target_id: str, filename: str):
    path = cutout_path(target_id, filename)
    if path is None:
        raise HTTPException(404, 'Local cutout not found')
    return FileResponse(path, media_type='application/fits', filename=filename)

@app.post('/spherex/timelapse')
async def timelapse(payload: TimelapseRequest, request: Request):
    async with request.app.state.jobs:
        result = (await run_in_threadpool(search_local, payload, True) if payload.source == 'local'
                  else await search(request.app.state.client, payload))
        async def frame(exposure):
            url = exposure.local_cutout_url if payload.source == 'local' else cutout_url(exposure, payload)
            try:
                async with request.app.state.downloads:
                    if payload.source == 'local':
                        path = local_path(exposure)
                        if path is None:
                            raise ValueError('Local cutout is missing')
                        body = await run_in_threadpool(path.read_bytes)
                    else:
                        body = await download(request.app.state.client, url)
                    data = await run_in_threadpool(align, body, payload)
                return exposure, data, url, None
            except (ArchiveError, ValueError, OSError, KeyError) as exc:
                return exposure, None, url, str(exc)
        rows = await asyncio.gather(*(frame(e) for e in result.exposures))
        good = [row for row in rows if row[1] is not None]
        failures = [{'id': row[0].id, 'reason': row[3]} for row in rows if row[1] is None]
        if result.exposures and not good:
            raise HTTPException(502, detail={'message': 'No selected exposures could be rendered', 'failures': failures})
        output = await run_in_threadpool(render, [row[1] for row in good]) if good else None
        frames = []
        for i, (exposure, _, url, _) in enumerate(good):
            frames.append({**exposure.model_dump(), 'cutout_fits_url': url,
                           'image_png': output['images'][i], 'difference_png': output['differences'][i]})
        return {
            'target': {'ra': payload.ra, 'dec': payload.dec, 'frame': 'ICRS'},
            'source': result.source,
            'status': ('partial' if failures else 'ready' if good else
                       'no_local_frames' if payload.source == 'local' else 'no_coverage'),
            'size_px': payload.size_px, 'pixel_scale_arcsec': payload.pixel_scale_arcsec,
            'orientation': 'north up, east left', 'units': 'MJy/sr',
            'background_subtracted': payload.subtract_background, 'bad_bits': payload.bad_bits,
            'wcs_header': dict(target_wcs(payload).to_header()),
            'frames': frames, 'median_png': output['median_png'] if output else None,
            'stretch': output['stretch'] if output else None,
            'truncated': result.truncated, 'warnings': result.warnings, 'failures': failures}
