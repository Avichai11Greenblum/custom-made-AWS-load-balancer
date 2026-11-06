import aiohttp
from aiohttp import web

from lb.aws.sinks import MetricsSink
from lb.backend_servers_pool.servers_registry import BackendRegistry
from lb.choose_servers_algos.base import ServerStrategy
from lb.metrics.request_stats import RequestStats
from lb.observers.health_events import EventPublisher

# Typed keys for the shared objects stored on the aiohttp Application.
BACKENDS_KEY = web.AppKey("backends", BackendRegistry)
STRATEGY_KEY = web.AppKey("strategies", ServerStrategy)
EVENT_PUBLISHER_KEY = web.AppKey("event_publisher", EventPublisher)
SESSION_KEY = web.AppKey("session", aiohttp.ClientSession)
REQUEST_STATS_KEY = web.AppKey("request_stats", RequestStats)
METRICS_SINK_KEY = web.AppKey("metrics_sink", MetricsSink)
