from dataclasses import dataclass


@dataclass
class BackendServer:
    """Represents one server that the load balancer can forward requests to.

    Attributes:
        url: Base address of the server, e.g. "http://localhost:8001".
            The request path is appended to it when forwarding.
        traffic_weight: Relative share of traffic this server should get. A
            server with traffic_weight 3 gets about three times the requests
            of one with traffic_weight 1. Only used by weighted algorithms.
        active_connections: Number of requests currently being handled by
            this server. The proxy raises it when a request starts and lowers
            it when the request finishes. Used by least_connections.
    """

    url: str
    traffic_weight: int = 1
    active_connections: int = 0
