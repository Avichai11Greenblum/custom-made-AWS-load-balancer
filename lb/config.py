import os

from lb.backend_server import BackendServer
from lb.resilience.circuit_breaker import CircuitBreaker

MAX_RETRY_ATTEMPTS = int(os.getenv("LB_MAX_ATTEMPTS", "3"))  # backends tried per retryable request
CB_FAILURE_THRESHOLD = int(os.getenv("LB_CB_FAILURE_THRESHOLD", "5"))  # failures to open circuit
CB_RECOVERY_TIMEOUT = float(os.getenv("LB_CB_RECOVERY_TIMEOUT", "10"))  # seconds before trial

DEFAULT_BACKENDS = "http://localhost:8001,http://localhost:8002,http://localhost:8003"


def parse_backends(raw: str) -> list[BackendServer]:
    """Parse 'url|weight,url|weight'. The weight is optional and defaults to 1."""
    backends = []
    for item in raw.split(","):
        url, _, weight = item.strip().partition("|")
        backends.append(
            BackendServer(
                url=url,
                traffic_weight=int(weight) if weight else 1,
                breaker=CircuitBreaker(CB_FAILURE_THRESHOLD, CB_RECOVERY_TIMEOUT),
            )
        )
    return backends


BACKENDS = parse_backends(os.getenv("LB_BACKENDS", DEFAULT_BACKENDS))
ALGORITHM = os.getenv("LB_ALGORITHM", "round_robin")
PORT = int(os.getenv("LB_PORT", "8080"))

HEALTH_INTERVAL = float(os.getenv("LB_HEALTH_INTERVAL", "2"))  # seconds between rounds
HEALTH_TIMEOUT = float(os.getenv("LB_HEALTH_TIMEOUT", "1"))  # seconds per probe
HEALTH_PATH = os.getenv("LB_HEALTH_PATH", "/health")
HEALTH_FAIL_THRESHOLD = int(os.getenv("LB_HEALTH_FAIL_THRESHOLD", "2"))  # fails to mark down
HEALTH_RISE_THRESHOLD = int(os.getenv("LB_HEALTH_RISE_THRESHOLD", "2"))  # passes to mark up
