import asyncio
import logging
from contextlib import suppress

from aiohttp import web

from lb import config
from lb.app_keys import BACKENDS_KEY, METRICS_SINK_KEY, REQUEST_STATS_KEY
from lb.aws.sinks import MetricsSink
from lb.backend_servers_pool.servers_registry import BackendRegistry
from lb.metrics.request_stats import RequestStats

logger = logging.getLogger(__name__)


class MetricsPublisher:
    """Reports the balancer's numbers to a MetricsSink once per interval.

    One report sends a handful of data points, not one per request, so the cost
    stays the same however much traffic the balancer handles.
    """

    def __init__(
        self, stats: RequestStats, backends: BackendRegistry, sink: MetricsSink, interval: float
    ) -> None:
        self._stats = stats
        self._backends = backends
        self._sink = sink
        self._interval = interval

    def publish_once(self) -> None:
        snapshot = self._stats.take_snapshot()
        self._sink.put_metric("Requests", snapshot.requests, "Count")
        self._sink.put_metric("Errors", snapshot.errors, "Count")
        if snapshot.requests:  # an idle interval has no latency to report
            self._sink.put_metric("LatencyAverage", snapshot.average_latency_ms, "Milliseconds")
            self._sink.put_metric("LatencyMax", snapshot.max_latency_ms, "Milliseconds")
        healthy_count = sum(1 for backend in self._backends if backend.healthy)
        self._sink.put_metric("HealthyBackends", healthy_count, "None")

    async def run(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            self.publish_once()


async def metrics_publisher_context(app: web.Application):
    """aiohttp cleanup_ctx: start the publisher with the app, stop it on shutdown."""
    publisher = MetricsPublisher(
        app[REQUEST_STATS_KEY], app[BACKENDS_KEY], app[METRICS_SINK_KEY], config.METRICS_INTERVAL
    )
    task = asyncio.create_task(publisher.run())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
