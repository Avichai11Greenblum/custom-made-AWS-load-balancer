from collections.abc import Sequence

from lb.choose_servers_algos.base import ServerStrategy
from lb.backend_server import BackendServer


class LeastConnections(ServerStrategy):
    def __init__(self) -> None:
        self._tie_counter = 0

    def choose_server(self, backends: Sequence[BackendServer], client_ip: str) -> BackendServer:
        fewest = min(b.active_connections for b in backends)
        candidates = [b for b in backends if b.active_connections == fewest]
        # Rotate between tied backends so an idle system doesn't always pick the first.
        backend = candidates[self._tie_counter % len(candidates)]
        self._tie_counter += 1
        return backend
