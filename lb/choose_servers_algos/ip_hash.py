import zlib
from collections.abc import Sequence

from lb.choose_servers_algos.base import ServerStrategy
from lb.backend_server import BackendServer


class IpHash(ServerStrategy):
    """Same client IP always lands on the same backend (sticky sessions)."""

    def choose_server(self, backends: Sequence[BackendServer], client_ip: str) -> BackendServer:
        # Built-in hash() changes between runs; crc32 is stable.
        return backends[zlib.crc32(client_ip.encode()) % len(backends)]
