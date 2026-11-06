from dataclasses import dataclass


@dataclass(frozen=True)
class StatsSnapshot:
    """Request numbers collected since the previous snapshot."""

    requests: int
    errors: int
    total_latency_ms: float
    max_latency_ms: float

    @property
    def average_latency_ms(self) -> float:
        return self.total_latency_ms / self.requests if self.requests else 0.0


class RequestStats:
    """Counts requests in memory until the metrics publisher collects them.

    The middleware calls record() for every request, so recording must be cheap
    and must not talk to AWS. Both record() and take_snapshot() run on the event
    loop, so no locking is needed.
    """

    def __init__(self) -> None:
        self._reset()

    def _reset(self) -> None:
        self._requests = 0
        self._errors = 0
        self._total_latency_ms = 0.0
        self._max_latency_ms = 0.0

    def record(self, latency_ms: float, is_error: bool) -> None:
        self._requests += 1
        self._errors += is_error
        self._total_latency_ms += latency_ms
        self._max_latency_ms = max(self._max_latency_ms, latency_ms)

    def take_snapshot(self) -> StatsSnapshot:
        """Return everything recorded since the last call and start counting from zero."""
        snapshot = StatsSnapshot(
            self._requests, self._errors, self._total_latency_ms, self._max_latency_ms
        )
        self._reset()
        return snapshot
