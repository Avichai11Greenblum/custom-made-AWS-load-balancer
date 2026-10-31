from collections.abc import Sequence

from lb.choose_servers_algos.base import ServerStrategy
from lb.backend_servers_pool.backend_server import BackendServer


class WeightedRoundRobin(ServerStrategy):
    """Smooth weighted round robin (the algorithm nginx uses).

    Every round each backend's score grows by its weight, the highest score
    wins, and the winner pays back the total weight. Heavy backends get more
    requests, spread evenly instead of in bursts.
    """

    def __init__(self) -> None:
        self._scores: dict[str, int] = {}

    def choose_server(self, backends: Sequence[BackendServer], client_ip: str) -> BackendServer:
        total = sum(b.traffic_weight for b in backends)
        for b in backends:
            self._scores[b.url] = self._scores.get(b.url, 0) + b.traffic_weight
        best = max(backends, key=lambda b: self._scores[b.url])
        self._scores[best.url] -= total
        return best
