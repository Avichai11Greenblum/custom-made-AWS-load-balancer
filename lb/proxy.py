import asyncio
import logging

import aiohttp
from aiohttp import web

from lb import config
from lb.choose_servers_algos.base import ServerStrategy
from lb.backend_server import BackendServer
from lb.observers.health_events import EventPublisher
from lb.factory import create_server_strategy
from lb.health_checker import health_check_context
from lb.observers.listeners import register_default_listeners

# Headers that describe a single connection, not the message.
# A proxy must not forward them (RFC 7230 section 6.1).
# HOP_BY_HOP is the standard name for the next machine in line 
HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


def forward_headers_without_irrelevant(request: web.Request) -> dict[str, str]:
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in HOP_BY_HOP and k.lower() != "host"
    }
    client_ip = request.remote or ""
    previous = request.headers.get("X-Forwarded-For")
    headers["X-Forwarded-For"] = f"{previous}, {client_ip}" if previous else client_ip
    return headers


async def proxy(request: web.Request) -> web.StreamResponse:
    healthy_backends = [b for b in request.app["backends"] if b.healthy]
    if not healthy_backends:
        return web.Response(status=503, text="Service unavailable: no healthy backends\n")
    strategy: ServerStrategy = request.app["strategies"]
    server = strategy.choose_server(healthy_backends, request.remote or "")
    server_url = server.url
    url = server_url + request.path_qs
    session: aiohttp.ClientSession = request.app["session"]

    server.active_connections += 1
    try:
        async with session.request(
            request.method,
            url,
            headers=forward_headers_without_irrelevant(request),
            data=request.content if request.can_read_body else None,
            allow_redirects=False,
        ) as upstream:
            response = web.StreamResponse(status=upstream.status, reason=upstream.reason)
            for key, value in upstream.headers.items():
                if key.lower() not in HOP_BY_HOP:
                    response.headers[key] = value
            await response.prepare(request)
            async for chunk in upstream.content.iter_chunked(64 * 1024):
                await response.write(chunk)
            await response.write_eof()
            return response
    except aiohttp.ClientConnectionError:
        return web.Response(status=502, text=f"Bad gateway: cannot reach {server_url}\n")
    except asyncio.TimeoutError:
        return web.Response(status=504, text=f"Gateway timeout: {server_url}\n")
    finally:
        server.active_connections -= 1


async def client_session(app: web.Application):
    timeout = aiohttp.ClientTimeout(total=30, connect=3)
    # auto_decompress=False keeps bytes identical to what the backend sent,
    # so Content-Encoding and Content-Length stay correct.
    async with aiohttp.ClientSession(timeout=timeout, auto_decompress=False) as session:
        app["session"] = session
        yield


def create_app(
    backends: list[BackendServer], strategies: ServerStrategy, event_publisher: EventPublisher
) -> web.Application:
    app = web.Application()
    app["backends"] = backends
    app["strategies"] = strategies
    app["event_publisher"] = event_publisher
    app.cleanup_ctx.append(client_session)
    app.cleanup_ctx.append(health_check_context)  # needs app["session"], so it comes second
    app.router.add_route("*", "/{tail:.*}", proxy)
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    event_publisher = EventPublisher()
    register_default_listeners(event_publisher)
    web.run_app(
        create_app(config.BACKENDS, create_server_strategy(config.ALGORITHM), event_publisher),
        port=config.PORT,
    )
