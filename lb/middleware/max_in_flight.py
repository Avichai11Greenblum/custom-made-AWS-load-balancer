from aiohttp import web

from lb.middleware.base import Handler, Middleware


class MaxInFlight(Middleware):
    """Load shedding: rejects new requests with 503 while `limit` are already in progress.

    Failing fast keeps the balancer responsive under overload instead of
    queueing work it cannot finish.
    """

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._in_flight = 0

    async def handle(self, request: web.Request, call_next: Handler) -> web.StreamResponse:
        if self._in_flight >= self._limit:
            return web.Response(
                status=503,
                text="Service unavailable: too many requests in flight\n",
                headers={"Retry-After": "1"},
            )
        self._in_flight += 1
        try:
            return await call_next(request)
        finally:
            self._in_flight -= 1
