import asyncio
import logging

import aiohttp
from aiohttp import web

from lb import config
from lb.admin import admin_server_context
from lb.app_keys import BACKENDS_KEY, EVENT_PUBLISHER_KEY, SESSION_KEY, STRATEGY_KEY
from lb.choose_servers_algos.base import ServerStrategy
from lb.backend_server import BackendServer
from lb.observers.health_events import EventPublisher
from lb.factory import create_server_strategy
from lb.health_checker import health_check_context
from lb.middleware.base import build_chain
from lb.middleware.max_in_flight import MaxInFlight
from lb.middleware.request_logging import BACKEND_KEY, RequestLogging
from lb.observers.listeners import register_default_listeners

logger = logging.getLogger(__name__)

RETRYABLE_METHODS = {"GET", "HEAD", "OPTIONS"}

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


class UpstreamFailure(Exception):
    """A backend could not produce a response. Nothing was sent to the client yet."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


async def forward_request_to_server(request: web.Request, server: BackendServer) -> web.StreamResponse:
    """Send the request to one backend and stream its response back.

    Raises UpstreamFailure if the backend cannot be reached or times out before
    it answers. Once the backend has answered, errors are not turned into
    UpstreamFailure, because the client may already be receiving the response.
    """
    session = request.app[SESSION_KEY]
    outcome_recorded = False

    server.active_connections += 1
    try:
        async with session.request(
            request.method,
            server.url + request.path_qs,
            headers=forward_headers_without_irrelevant(request),
            data=request.content if request.can_read_body else None,
            allow_redirects=False,
        ) as upstream:
            if upstream.status >= 500:
                server.breaker.record_failure()
            else:
                server.breaker.record_success()
            outcome_recorded = True

            response = web.StreamResponse(status=upstream.status, reason=upstream.reason)
            for key, value in upstream.headers.items():
                if key.lower() not in HOP_BY_HOP:
                    response.headers[key] = value
            await response.prepare(request)
            async for chunk in upstream.content.iter_chunked(64 * 1024):
                await response.write(chunk)
            await response.write_eof()
            return response
    except (aiohttp.ClientError, asyncio.TimeoutError) as error:
        if outcome_recorded:
            raise
        server.breaker.record_failure()
        outcome_recorded = True
        if isinstance(error, asyncio.TimeoutError):
            raise UpstreamFailure(504, f"Gateway timeout: {server.url}\n") from error
        raise UpstreamFailure(502, f"Bad gateway: cannot reach {server.url}\n") from error
    finally:
        server.active_connections -= 1
        if not outcome_recorded:
            server.breaker.cancel_attempt()


async def proxy(request: web.Request) -> web.StreamResponse:
    strategy = request.app[STRATEGY_KEY]
    # Only requests that are safe to repeat and have no body (which can be read once) are retried.
    retryable = request.method in RETRYABLE_METHODS and not request.can_read_body
    max_retry_attempts = config.MAX_RETRY_ATTEMPTS if retryable else 1
    tried: set[str] = set()
    last_failure: UpstreamFailure | None = None

    for _ in range(max_retry_attempts):
        candidates = [
            b
            for b in request.app[BACKENDS_KEY]
            if b.healthy and not b.draining and b.url not in tried and b.breaker.is_available()
        ]
        if not candidates:
            break
        server = strategy.choose_server(candidates, request.remote or "")
        request[BACKEND_KEY] = server.url  # read by the RequestLogging middleware
        tried.add(server.url)
        server.breaker.begin_attempt()
        try:
            return await forward_request_to_server(request, server)
        except UpstreamFailure as failure:
            last_failure = failure
            logger.warning("Request to %s failed (%s), trying another backend", server.url, failure.status)

    if last_failure is not None:
        return web.Response(status=last_failure.status, text=str(last_failure))
    return web.Response(status=503, text="Service unavailable: no available backends\n")


async def client_session(app: web.Application):
    timeout = aiohttp.ClientTimeout(total=30, connect=3)
    # auto_decompress=False keeps bytes identical to what the backend sent,
    # so Content-Encoding and Content-Length stay correct.
    async with aiohttp.ClientSession(timeout=timeout, auto_decompress=False) as session:
        app[SESSION_KEY] = session
        yield


def create_app(
    backends: list[BackendServer], strategies: ServerStrategy, event_publisher: EventPublisher
) -> web.Application:
    app = web.Application()
    app[BACKENDS_KEY] = backends
    app[STRATEGY_KEY] = strategies
    app[EVENT_PUBLISHER_KEY] = event_publisher
    app.cleanup_ctx.append(client_session)
    app.cleanup_ctx.append(health_check_context)  # needs app[SESSION_KEY], so it comes second
    app.cleanup_ctx.append(admin_server_context)
    # First in the list is outermost, so logging also sees the 503s from MaxInFlight.
    handler = build_chain(proxy, [RequestLogging(), MaxInFlight(config.MAX_IN_FLIGHT)])
    app.router.add_route("*", "/{tail:.*}", handler)
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    event_publisher = EventPublisher()
    register_default_listeners(event_publisher)
    web.run_app(
        create_app(config.BACKENDS, create_server_strategy(config.ALGORITHM), event_publisher),
        port=config.PORT,
    )
