from collections.abc import Callable, Iterable, Iterator

from lb.backend_servers_pool.backend_server import BackendServer


class DuplicateBackendError(ValueError):
    """A backend with this URL is already registered."""


class BackendNotFoundError(KeyError):
    """No backend with this URL is registered."""


class BackendRegistry:
    """The single place that owns the set of backends (Registry pattern).

    The proxy, the health checker and the admin API all share one registry, so a
    backend added or removed through one is seen by the others immediately.
    Backends are identified by URL, and a URL can be registered only once.

    Iterating returns a snapshot, so it is safe to add or remove backends while
    another piece of code is looping over the registry.

    If on_circuit_change is given, it is installed as the on_state_change
    callback of every backend's circuit breaker, including backends added later.
    """

    def __init__(
        self,
        backends: Iterable[BackendServer] = (),
        on_circuit_change: Callable[[str, str, str], None] | None = None,
    ) -> None:
        self._backends: dict[str, BackendServer] = {}
        self._on_circuit_change = on_circuit_change
        for backend in backends:
            self.add(backend)

    def add(self, backend: BackendServer) -> None:
        """Register a backend. Raises DuplicateBackendError if its URL is taken."""
        if backend.url in self._backends:
            raise DuplicateBackendError(backend.url)
        if self._on_circuit_change is not None:
            backend.breaker.on_state_change = self._on_circuit_change
        self._backends[backend.url] = backend

    def remove(self, url: str) -> BackendServer:
        """Unregister and return the backend. Raises BackendNotFoundError if unknown."""
        try:
            return self._backends.pop(url)
        except KeyError:
            raise BackendNotFoundError(url) from None

    def get(self, url: str) -> BackendServer:
        """Return the backend with this URL. Raises BackendNotFoundError if unknown."""
        try:
            return self._backends[url]
        except KeyError:
            raise BackendNotFoundError(url) from None

    def __iter__(self) -> Iterator[BackendServer]:
        return iter(list(self._backends.values()))

    def __len__(self) -> int:
        return len(self._backends)

    def __contains__(self, url: object) -> bool:
        return url in self._backends
