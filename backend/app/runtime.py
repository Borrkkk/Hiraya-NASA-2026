"""Shared HTTP resources for the legacy and unified API entry points."""
import asyncio
from contextlib import asynccontextmanager
import ssl

import httpx
import truststore


@asynccontextmanager
async def lifespan(app):
    tls = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    async with httpx.AsyncClient(verify=tls, timeout=httpx.Timeout(90, connect=15), follow_redirects=False,
                                 limits=httpx.Limits(max_connections=8)) as client:
        app.state.client = client
        app.state.jobs = asyncio.Semaphore(2)
        app.state.downloads = asyncio.Semaphore(4)
        yield
