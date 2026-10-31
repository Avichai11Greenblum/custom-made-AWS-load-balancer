from collections.abc import Sequence

import aiohttp
from aiohttp import web

from lb.backend_server import BackendServer
from lb.choose_servers_algos.base import ServerStrategy
from lb.observers.health_events import EventPublisher

# Typed keys for the shared objects stored on the aiohttp Application.
BACKENDS_KEY = web.AppKey("backends", Sequence[BackendServer])
STRATEGY_KEY = web.AppKey("strategies", ServerStrategy)
EVENT_PUBLISHER_KEY = web.AppKey("event_publisher", EventPublisher)
SESSION_KEY = web.AppKey("session", aiohttp.ClientSession)
