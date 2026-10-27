import asyncio
import logging

from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from lb.middleware.base import Middleware, build_chain
from lb.middleware.max_in_flight import MaxInFlight
from lb.middleware.request_logging import BACKEND_KEY, RequestLogging


class Recorder(Middleware):
    def __init__(self, name: str, calls: list[str]) -> None:
        self.name = name
        self.calls = calls

    async def handle(self, request, call_next):
        self.calls.append(f"{self.name} in")
        response = await call_next(request)
        self.calls.append(f"{self.name} out")
        return response


class Blocker(Middleware):
    async def handle(self, request, call_next):
        return web.Response(status=403)


def test_chain_runs_first_middleware_outermost():
    calls: list[str] = []

    async def handler(request):
        calls.append("handler")
        return web.Response(text="ok")

    chain = build_chain(handler, [Recorder("A", calls), Recorder("B", calls)])
    response = asyncio.run(chain(make_mocked_request("GET", "/")))

    assert response.status == 200
    assert calls == ["A in", "B in", "handler", "B out", "A out"]


def test_middleware_can_stop_the_request():
    calls: list[str] = []

    async def handler(request):
        calls.append("handler")
        return web.Response(text="ok")

    chain = build_chain(handler, [Blocker()])
    response = asyncio.run(chain(make_mocked_request("GET", "/")))

    assert response.status == 403
    assert calls == []


def test_chain_without_middlewares_is_the_handler():
    async def handler(request):
        return web.Response(text="ok")

    chain = build_chain(handler, [])
    assert asyncio.run(chain(make_mocked_request("GET", "/"))).status == 200


def test_max_in_flight_rejects_requests_over_the_limit():
    async def scenario():
        release = asyncio.Event()

        async def slow_handler(request):
            await release.wait()
            return web.Response(text="ok")

        chain = build_chain(slow_handler, [MaxInFlight(limit=1)])
        first = asyncio.create_task(chain(make_mocked_request("GET", "/")))
        await asyncio.sleep(0)  # let the first request start
        second = await chain(make_mocked_request("GET", "/"))
        release.set()
        return await first, second

    first, second = asyncio.run(scenario())
    assert first.status == 200
    assert second.status == 503


def test_max_in_flight_frees_the_slot_after_a_request_finishes():
    async def handler(request):
        return web.Response(text="ok")

    chain = build_chain(handler, [MaxInFlight(limit=1)])
    statuses = [asyncio.run(chain(make_mocked_request("GET", "/"))).status for _ in range(3)]
    assert statuses == [200, 200, 200]


def test_max_in_flight_frees_the_slot_when_the_handler_fails():
    async def failing_handler(request):
        raise RuntimeError("boom")

    async def ok_handler(request):
        return web.Response(text="ok")

    limiter = MaxInFlight(limit=1)
    try:
        asyncio.run(build_chain(failing_handler, [limiter])(make_mocked_request("GET", "/")))
    except RuntimeError:
        pass
    response = asyncio.run(build_chain(ok_handler, [limiter])(make_mocked_request("GET", "/")))
    assert response.status == 200


def test_request_logging_writes_one_line_with_the_backend(caplog):
    async def handler(request):
        request[BACKEND_KEY] = "http://b1"
        return web.Response(text="ok")

    chain = build_chain(handler, [RequestLogging()])
    with caplog.at_level(logging.INFO, logger="lb.middleware.request_logging"):
        asyncio.run(chain(make_mocked_request("GET", "/hello?x=1")))

    assert len(caplog.records) == 1
    message = caplog.records[0].getMessage()
    assert "GET /hello?x=1 -> 200 via http://b1" in message
