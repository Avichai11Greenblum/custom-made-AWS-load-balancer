import asyncio
import logging
from aiohttp import web

from lb import config
from lb.app_keys import BACKENDS_KEY
from lb.backend_servers_pool.backend_server import BackendServer
from lb.backend_servers_pool.servers_registry import (
    BackendNotFoundError,
    BackendRegistry,
    DuplicateBackendError,
)

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


def describe(backend: BackendServer) -> dict:
    return {
        "url": backend.url,
        "weight": backend.traffic_weight,
        "healthy": backend.healthy,
        "draining": backend.draining,
        "circuit": backend.breaker.state_name,
        "active_connections": backend.active_connections,
    }


async def list_backends(request: web.Request) -> web.Response:
    """Show every registered backend and its current state."""
    return web.json_response([describe(b) for b in request.app[BACKENDS_KEY]])


async def add_backend(request: web.Request) -> web.Response:
    """Register a new backend from a JSON body: {"url": "http://host:port", "weight": 2}.

    The weight is optional and defaults to 1. The backend counts as healthy until
    the health checker says otherwise, so it starts receiving traffic right away.
    """
    try:
        body = await request.json()
    except ValueError:
        raise web.HTTPBadRequest(text="Body must be valid JSON\n") from None
    if not isinstance(body, dict):
        raise web.HTTPBadRequest(text='Body must be a JSON object like {"url": "..."}\n')

    url = body.get("url")
    weight = body.get("weight", 1)
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        raise web.HTTPBadRequest(text="url must start with http:// or https://\n")
    if not isinstance(weight, int) or isinstance(weight, bool) or weight < 1:
        raise web.HTTPBadRequest(text="weight must be an integer of 1 or more\n")

    # The proxy appends the request path to the URL, so a trailing slash would double up.
    backend = config.make_backend(url.rstrip("/"), weight)
    try:
        request.app[BACKENDS_KEY].add(backend)
    except DuplicateBackendError:
        raise web.HTTPConflict(text=f"Backend already registered: {backend.url}\n") from None
    logger.info("Added backend %s (weight %d)", backend.url, backend.traffic_weight)
    return web.json_response(describe(backend), status=201)


async def remove_backend(request: web.Request) -> web.Response:
    """Unregister a backend. It stops receiving requests immediately.

    Requests already running on it still finish. To avoid cutting any of them
    off, call drain first and remove once it reports drained: true.
    """
    backend = find_backend(request)
    request.app[BACKENDS_KEY].remove(backend.url)
    logger.info("Removed backend %s", backend.url)
    return web.json_response(describe(backend))


def create_admin_app(backends: BackendRegistry) -> web.Application:
    app = web.Application()
    app[BACKENDS_KEY] = backends
    app.router.add_get("/admin/backends", list_backends)
    app.router.add_post("/admin/backends", add_backend)
    app.router.add_delete("/admin/backends", remove_backend)
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
