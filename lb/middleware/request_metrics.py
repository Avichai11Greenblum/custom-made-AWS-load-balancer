import time

from aiohttp import web

from lb.metrics.request_stats import RequestStats
from lb.middleware.base import Handler, Middleware


class RequestMetrics(Middleware):
    """Records the duration of every request, and whether it ended in an error.

    An error is a 5xx response or an exception from the inner layers. Only
    in-memory counters change here; the numbers leave the process later, in
    batches, from the metrics publisher.
    """

    def __init__(self, stats: RequestStats) -> None:
        self._stats = stats

    async def handle(self, request: web.Request, call_next: Handler) -> web.StreamResponse:
        started = time.monotonic()
        is_error = True
        try:
            response = await call_next(request)
            is_error = response.status >= 500
            return response
        finally:
            self._stats.record((time.monotonic() - started) * 1000, is_error)
