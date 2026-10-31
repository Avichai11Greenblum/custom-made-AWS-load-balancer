import asyncio
import json

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from lb.admin.api import create_admin_app, drain, undrain, wait_until_idle
from lb.backend_servers_pool.backend_server import BackendServer


def admin_request(method: str, path: str, backends: list[BackendServer]):
    return make_mocked_request(method, path, app=create_admin_app(backends))


def test_wait_until_idle_returns_true_when_nothing_is_running():
    server = BackendServer(url="http://b1")
    assert asyncio.run(wait_until_idle(server, timeout=1)) is True


def test_wait_until_idle_waits_for_requests_to_finish():
    server = BackendServer(url="http://b1", active_connections=1)

    async def scenario():
        async def finish_later():
            await asyncio.sleep(0.05)
            server.active_connections = 0

        task = asyncio.create_task(finish_later())
        result = await wait_until_idle(server, timeout=1, poll_interval=0.01)
        await task
        return result

    assert asyncio.run(scenario()) is True


def test_wait_until_idle_gives_up_after_the_timeout():
    server = BackendServer(url="http://b1", active_connections=1)
    assert asyncio.run(wait_until_idle(server, timeout=0.05, poll_interval=0.01)) is False


def test_drain_marks_backend_and_reports_drained_when_idle():
    backend = BackendServer(url="http://b1")
    request = admin_request("POST", "/admin/drain?url=http://b1", [backend])
    response = asyncio.run(drain(request))
    assert backend.draining
    assert json.loads(response.text) == {
        "url": "http://b1",
        "drained": True,
        "active_connections": 0,
    }


def test_drain_reports_not_drained_when_requests_are_still_running():
    backend = BackendServer(url="http://b1", active_connections=2)
    request = admin_request("POST", "/admin/drain?url=http://b1&timeout=0.05", [backend])
    response = asyncio.run(drain(request))
    assert backend.draining
    assert json.loads(response.text)["drained"] is False


def test_undrain_puts_backend_back():
    backend = BackendServer(url="http://b1", draining=True)
    request = admin_request("POST", "/admin/undrain?url=http://b1", [backend])
    asyncio.run(undrain(request))
    assert not backend.draining


def test_unknown_backend_is_404():
    request = admin_request("POST", "/admin/drain?url=http://nope", [BackendServer("http://b1")])
    with pytest.raises(web.HTTPNotFound):
        asyncio.run(drain(request))


def test_missing_url_is_400():
    request = admin_request("POST", "/admin/drain", [BackendServer("http://b1")])
    with pytest.raises(web.HTTPBadRequest):
        asyncio.run(drain(request))
