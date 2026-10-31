from abc import ABC, abstractmethod
from collections.abc import Sequence

from lb.backend_servers_pool.backend_server import BackendServer


class ServerStrategy(ABC):
    """Strategy interface: decides which backend serves the next request."""

    @abstractmethod
    def choose_server(self, backends: Sequence[BackendServer], client_ip: str) -> BackendServer:
        """Pick the backend that should handle the next request.

        Args:
            backends: Servers to choose from.
            client_ip: Address of the client making the request. Only used by
                algorithms that route by client, such as ip_hash.

        Returns:
            The selected backend server.
        """
