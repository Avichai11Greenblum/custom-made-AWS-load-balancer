import pytest

from lb.backend_servers_pool.backend_server import BackendServer
from lb.backend_servers_pool.servers_registry import (
    BackendNotFoundError,
    BackendRegistry,
    DuplicateBackendError,
)


def test_starts_with_the_given_backends():
    registry = BackendRegistry([BackendServer("http://b1"), BackendServer("http://b2")])
    assert len(registry) == 2
    assert [b.url for b in registry] == ["http://b1", "http://b2"]


def test_add_and_get():
    registry = BackendRegistry()
    backend = BackendServer("http://b1")
    registry.add(backend)
    assert registry.get("http://b1") is backend
    assert "http://b1" in registry


def test_add_rejects_duplicate_url():
    registry = BackendRegistry([BackendServer("http://b1")])
    with pytest.raises(DuplicateBackendError):
        registry.add(BackendServer("http://b1"))
    assert len(registry) == 1


def test_remove_returns_the_backend_and_forgets_it():
    registry = BackendRegistry([BackendServer("http://b1")])
    removed = registry.remove("http://b1")
    assert removed.url == "http://b1"
    assert "http://b1" not in registry
    assert len(registry) == 0


def test_remove_and_get_unknown_url_raise():
    registry = BackendRegistry()
    with pytest.raises(BackendNotFoundError):
        registry.remove("http://nope")
    with pytest.raises(BackendNotFoundError):
        registry.get("http://nope")


def test_removed_url_can_be_added_again():
    registry = BackendRegistry([BackendServer("http://b1")])
    registry.remove("http://b1")
    registry.add(BackendServer("http://b1"))
    assert len(registry) == 1


def test_iteration_is_a_snapshot_safe_against_changes():
    registry = BackendRegistry([BackendServer("http://b1"), BackendServer("http://b2")])
    seen = []
    for backend in registry:
        registry.remove(backend.url)
        seen.append(backend.url)
    assert seen == ["http://b1", "http://b2"]
    assert len(registry) == 0
