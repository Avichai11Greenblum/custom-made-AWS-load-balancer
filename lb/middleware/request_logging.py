import logging
import time

from aiohttp import web

from lb.middleware.base import Handler, Middleware

logger = logging.getLogger(__name__)

# Typed key for the URL of the backend that served the request.
BACKEND_KEY = web.RequestKey("backend", str)


class RequestLogging(Middleware):
    """Logs one line per request: method, path, status, chosen backend and duration.

    The proxy stores the backend it used in request[BACKEND_KEY]. Requests that
    never reach a backend show "-".
    """

    async def handle(self, request: web.Request, call_next: Handler) -> web.StreamResponse:
        started = time.monotonic()
        status: int | str = "error"
        try:
            response = await call_next(request)
            status = response.status
            return response
        finally:
            elapsed_ms = (time.monotonic() - started) * 1000
            logger.info(
                "%s %s -> %s via %s in %.1f ms",
                request.method,
                request.path_qs,
                status,
                request.get(BACKEND_KEY, "-"),
                elapsed_ms,
            )
