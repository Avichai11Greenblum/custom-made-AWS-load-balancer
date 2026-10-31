import asyncio
from collections import defaultdict
from collections.abc import Sequence
from contextlib import suppress

import aiohttp
from aiohttp import web

from lb import config
from lb.app_keys import BACKENDS_KEY, EVENT_PUBLISHER_KEY, SESSION_KEY
from lb.backend_servers_pool.backend_server import BackendServer
from lb.observers.health_events import BackendDown, BackendUp, EventPublisher


class HealthChecker:
    """Periodically probes every backend and flips its `healthy` flag.

    A backend goes down after `fail_threshold` failed probes in a row and comes
    back after `rise_threshold` successful probes in a row, so one blip does
    not make it flap in and out of rotation.
    """

    def __init__(
        self,
        backends: Sequence[BackendServer],
        session: aiohttp.ClientSession | None,
        event_publisher: EventPublisher,
        interval: float = config.HEALTH_INTERVAL,
        timeout: float = config.HEALTH_TIMEOUT,
        path: str = config.HEALTH_PATH,
        fail_threshold: int = config.HEALTH_FAIL_THRESHOLD,
        rise_threshold: int = config.HEALTH_RISE_THRESHOLD,
    ) -> None:
        self._backends = backends
        self._session = session
        self._event_publisher = event_publisher
        self._interval = interval
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._path = path
        self._fail_threshold = fail_threshold
        self._rise_threshold = rise_threshold
        self._failures: dict[str, int] = defaultdict(int)
        self._successes: dict[str, int] = defaultdict(int)

    async def run(self) -> None:
        while True:
            await self.check_all()
            await asyncio.sleep(self._interval)

    async def check_all(self) -> None:
        results = await asyncio.gather(*(self._probe(b) for b in self._backends))
        for backend, ok in zip(self._backends, results):
            self.record_result(backend, ok)

    async def _probe(self, backend: BackendServer) -> bool:
        try:
            async with self._session.get(
                backend.url + self._path, timeout=self._timeout
            ) as response:
                return response.status == 200
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return False

    def record_result(self, backend: BackendServer, ok: bool) -> None:
        """Update the streak counters and publish an event when health flips."""
        url = backend.url
        if ok:
            self._failures[url] = 0
            self._successes[url] += 1
            if not backend.healthy and self._successes[url] >= self._rise_threshold:
                backend.healthy = True
                self._event_publisher.publish(BackendUp(url))
        else:
            self._successes[url] = 0
            self._failures[url] += 1
            if backend.healthy and self._failures[url] >= self._fail_threshold:
                backend.healthy = False
                self._event_publisher.publish(BackendDown(url))


async def health_check_context(app: web.Application):
    """aiohttp cleanup_ctx: start the checker with the app, stop it on shutdown."""
    checker = HealthChecker(app[BACKENDS_KEY], app[SESSION_KEY], app[EVENT_PUBLISHER_KEY])
    task = asyncio.create_task(checker.run())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
