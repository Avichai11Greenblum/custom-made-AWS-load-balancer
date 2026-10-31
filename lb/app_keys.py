import aiohttp
from aiohttp import web

from lb.backend_servers_pool.servers_registry import BackendRegistry
from lb.choose_servers_algos.base import ServerStrategy
from lb.observers.health_events import EventPublisher

# Typed keys for the shared objects stored on the aiohttp Application.
BACKENDS_KEY = web.AppKey("backends", BackendRegistry)
STRATEGY_KEY = web.AppKey("strategies", ServerStrategy)
EVENT_PUBLISHER_KEY = web.AppKey("event_publisher", EventPublisher)
SESSION_KEY = web.AppKey("session", aiohttp.ClientSession)
