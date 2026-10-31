import asyncio
import json

from aiohttp.test_utils import TestClient, TestServer

from lb.admin.api import create_admin_app
from lb.backend_servers_pool.backend_server import BackendServer
from lb.backend_servers_pool.servers_registry import BackendRegistry


def call(registry: BackendRegistry, method: str, path: str, **kwargs) -> tuple[int, str]:
    """Send one real HTTP request to the admin app and return (status, body text)."""

    async def scenario():
        async with TestClient(TestServer(create_admin_app(registry))) as client:
            response = await client.request(method, path, **kwargs)
            return response.status, await response.text()

    return asyncio.run(scenario())


def test_list_shows_every_backend_with_its_state():
    registry = BackendRegistry([BackendServer("http://b1", traffic_weight=3)])
    registry.get("http://b1").healthy = False
    status, text = call(registry, "GET", "/admin/backends")
    assert status == 200
    assert json.loads(text) == [
        {
            "url": "http://b1",
            "weight": 3,
            "healthy": False,
            "draining": False,
            "circuit": "closed",
            "active_connections": 0,
        }
    ]


def test_list_of_empty_registry_is_an_empty_list():
    status, text = call(BackendRegistry(), "GET", "/admin/backends")
    assert status == 200
    assert json.loads(text) == []


def test_add_registers_the_backend():
    registry = BackendRegistry()
    status, text = call(registry, "POST", "/admin/backends", json={"url": "http://b1", "weight": 2})
    assert status == 201
    assert json.loads(text)["url"] == "http://b1"
    assert registry.get("http://b1").traffic_weight == 2


def test_added_backend_starts_unhealthy_until_the_health_checker_promotes_it():
    registry = BackendRegistry()
    call(registry, "POST", "/admin/backends", json={"url": "http://b1"})
    assert registry.get("http://b1").healthy is False


def test_add_defaults_weight_to_one_and_strips_trailing_slash():
    registry = BackendRegistry()
    status, _ = call(registry, "POST", "/admin/backends", json={"url": "http://b1/"})
    assert status == 201
    assert registry.get("http://b1").traffic_weight == 1


def test_add_duplicate_is_409():
    registry = BackendRegistry([BackendServer("http://b1")])
    status, _ = call(registry, "POST", "/admin/backends", json={"url": "http://b1"})
    assert status == 409
    assert len(registry) == 1


def test_add_rejects_bad_input_with_400():
    bad_bodies = [
        {},
        {"url": "b1:8000"},
        {"url": 5},
        {"url": "http://b1", "weight": 0},
        {"url": "http://b1", "weight": "2"},
        {"url": "http://b1", "weight": True},
        ["http://b1"],
    ]
    for body in bad_bodies:
        registry = BackendRegistry()
        status, _ = call(registry, "POST", "/admin/backends", json=body)
        assert status == 400, body
        assert len(registry) == 0


def test_add_rejects_invalid_json_with_400():
    status, _ = call(BackendRegistry(), "POST", "/admin/backends", data="not json")
    assert status == 400


def test_remove_unregisters_the_backend():
    registry = BackendRegistry([BackendServer("http://b1"), BackendServer("http://b2")])
    status, text = call(registry, "DELETE", "/admin/backends?url=http://b1")
    assert status == 200
    assert json.loads(text)["url"] == "http://b1"
    assert "http://b1" not in registry
    assert "http://b2" in registry


def test_remove_unknown_is_404_and_missing_url_is_400():
    registry = BackendRegistry([BackendServer("http://b1")])
    assert call(registry, "DELETE", "/admin/backends?url=http://nope")[0] == 404
    assert call(registry, "DELETE", "/admin/backends")[0] == 400
    assert len(registry) == 1
