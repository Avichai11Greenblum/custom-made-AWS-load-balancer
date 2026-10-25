import os

from lb.backend_server import BackendServer

DEFAULT_BACKENDS = "http://localhost:8001,http://localhost:8002,http://localhost:8003"


def parse_backends(raw: str) -> list[BackendServer]:
    """Parse 'url|weight,url|weight'. The weight is optional and defaults to 1."""
    backends = []
    for item in raw.split(","):
        url, _, weight = item.strip().partition("|")
        backends.append(BackendServer(url=url, traffic_weight=int(weight) if weight else 1))
    return backends


BACKENDS = parse_backends(os.getenv("LB_BACKENDS", DEFAULT_BACKENDS))
ALGORITHM = os.getenv("LB_ALGORITHM", "round_robin")
PORT = int(os.getenv("LB_PORT", "8080"))
