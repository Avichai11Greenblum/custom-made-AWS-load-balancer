from dataclasses import dataclass, field

from lb.resilience.circuit_breaker import CircuitBreaker


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
        healthy: Whether the server may receive requests. Set by the health
            checker; unhealthy servers are skipped by the proxy. Servers start
            healthy until a health check says otherwise.
        breaker: Circuit breaker fed by real request results. While it is open
            the proxy skips this server even if health checks still pass.
    """

    url: str
    traffic_weight: int = 1
    active_connections: int = 0
    healthy: bool = True
    breaker: CircuitBreaker = field(default_factory=CircuitBreaker)

    def __post_init__(self) -> None:
        if not self.breaker.name:
            self.breaker.name = self.url
