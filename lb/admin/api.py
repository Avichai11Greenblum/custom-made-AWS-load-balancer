import asyncio
import logging
from aiohttp import web

from lb import config
from lb.app_keys import BACKENDS_KEY
from lb.backend_servers_pool.backend_server import BackendServer
from lb.backend_servers_pool.servers_registry import BackendNotFoundError, BackendRegistry

logger = logging.getLogger(__name__)


async def wait_until_idle(
    server: BackendServer, timeout: float, poll_interval: float = 0.1
) -> bool:
    """Wait until the server has no requests in progress. False if the timeout ran out first."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while server.active_connections > 0:
        if loop.time() >= deadline:
            return False
        await asyncio.sleep(poll_interval)
    return True


def find_backend(request: web.Request) -> BackendServer:
    url = request.query.get("url")
    if not url:
        raise web.HTTPBadRequest(text="Missing ?url=\n")
    try:
        return request.app[BACKENDS_KEY].get(url)
    except BackendNotFoundError:
        raise web.HTTPNotFound(text=f"Unknown backend: {url}\n") from None


async def drain(request: web.Request) -> web.Response:
    """Stop sending new requests to a backend and wait for its current ones to finish.

    The call returns when the backend is idle (drained: true) or when the timeout
    passes (drained: false). Once it says true, the backend is safe to stop.
    """
    backend = find_backend(request)
    timeout = float(request.query.get("timeout", config.DRAIN_TIMEOUT))
    backend.draining = True
    logger.info("Draining %s (%d requests in progress)", backend.url, backend.active_connections)
    drained = await wait_until_idle(backend, timeout)
    return web.json_response(
        {
            "url": backend.url,
            "drained": drained,
            "active_connections": backend.active_connections,
        }
    )


async def undrain(request: web.Request) -> web.Response:
    """Put a draining backend back into rotation."""
    backend = find_backend(request)
    backend.draining = False
    logger.info("Undrained %s", backend.url)
    return web.json_response({"url": backend.url, "draining": False})


def create_admin_app(backends: BackendRegistry) -> web.Application:
    app = web.Application()
    app[BACKENDS_KEY] = backends
    app.router.add_post("/admin/drain", drain)
    app.router.add_post("/admin/undrain", undrain)
    return app


async def admin_server_context(app: web.Application):
    """Run the admin API on its own port for as long as the proxy runs.

    It shares the proxy's backend list, so commands like drain take effect
    immediately.

    It binds to 127.0.0.1 (localhost), so only programs on the same machine can
    connect. The API has no login, and anyone who could reach it could drain
    backends. Binding to 0.0.0.0 instead would expose it to the whole network.
    """
    runner = web.AppRunner(create_admin_app(app[BACKENDS_KEY]))
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", config.ADMIN_PORT).start()
    logger.info("Admin API on http://127.0.0.1:%d", config.ADMIN_PORT)
    yield
    await runner.cleanup()
