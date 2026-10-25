from collections.abc import Sequence

from lb.choose_servers_algos.base import ServerStrategy
from lb.backend_server import BackendServer


class RoundRobin(ServerStrategy):
    def __init__(self) -> None:
        self._counter = 0

    def choose_server(self, backends: Sequence[BackendServer], client_ip: str) -> BackendServer:
        backend = backends[self._counter % len(backends)]
        self._counter += 1
        return backend
