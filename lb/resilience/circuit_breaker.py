import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Callable

logger = logging.getLogger(__name__)


class CircuitState(ABC):
    """One state of the circuit breaker (State pattern).

    Each state decides for itself whether the backend may be used and how the
    breaker moves to another state when a request succeeds or fails.
    """

    name: str

    @abstractmethod
    def is_available(self, breaker: "CircuitBreaker") -> bool:
        """Whether a new request may be sent. Must not change any state."""

    def begin_attempt(self, breaker: "CircuitBreaker") -> None:
        """Called right before a request is sent to the backend."""

    def cancel_attempt(self) -> None:
        """Called when a request ended without a success or failure result."""

    @abstractmethod
    def on_success(self, breaker: "CircuitBreaker") -> None:
        ...

    @abstractmethod
    def on_failure(self, breaker: "CircuitBreaker") -> None:
        ...


class ClosedState(CircuitState):
    """Normal operation. Counts consecutive failures; too many opens the circuit."""

    name = "closed"

    def __init__(self) -> None:
        self.failures = 0

    def is_available(self, breaker: "CircuitBreaker") -> bool:
        return True

    def on_success(self, breaker: "CircuitBreaker") -> None:
        self.failures = 0

    def on_failure(self, breaker: "CircuitBreaker") -> None:
        self.failures += 1
        if self.failures >= breaker.failure_threshold:
            breaker.transition(OpenState(opened_at=breaker.clock()))


class OpenState(CircuitState):
    """Backend is skipped. After the recovery timeout one trial request is allowed."""

    name = "open"

    def __init__(self, opened_at: float) -> None:
        self.opened_at = opened_at

    def is_available(self, breaker: "CircuitBreaker") -> bool:
        return breaker.clock() - self.opened_at >= breaker.recovery_timeout

    def begin_attempt(self, breaker: "CircuitBreaker") -> None:
        breaker.transition(HalfOpenState(trial_in_flight=True))

    def on_success(self, breaker: "CircuitBreaker") -> None:
        # A late result from a request sent before the circuit opened: ignore it.
        pass

    def on_failure(self, breaker: "CircuitBreaker") -> None:
        pass


class HalfOpenState(CircuitState):
    """One trial request decides: success closes the circuit, failure reopens it."""

    name = "half-open"

    def __init__(self, trial_in_flight: bool = False) -> None:
        self.trial_in_flight = trial_in_flight

    def is_available(self, breaker: "CircuitBreaker") -> bool:
        return not self.trial_in_flight

    def begin_attempt(self, breaker: "CircuitBreaker") -> None:
        self.trial_in_flight = True

    def cancel_attempt(self) -> None:
        self.trial_in_flight = False

    def on_success(self, breaker: "CircuitBreaker") -> None:
        breaker.transition(ClosedState())

    def on_failure(self, breaker: "CircuitBreaker") -> None:
        breaker.transition(OpenState(opened_at=breaker.clock()))


class CircuitBreaker:
    """Stops sending requests to a backend that keeps failing, then probes it again.

    Usage per request: check is_available(), call begin_attempt(), send the
    request, then report record_success() or record_failure(). If the request
    ends with neither, call cancel_attempt() so a half-open trial is not stuck.

    Attributes:
        failure_threshold: Consecutive failures that open the circuit.
        recovery_timeout: Seconds an open circuit waits before allowing a trial.
        clock: Time source in seconds; replaceable in tests.
        name: Label used in log messages, usually the backend URL.
        on_state_change: Optional callback called as (name, old_state_name,
            new_state_name) after every state change.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 10.0,
        clock: Callable[[], float] = time.monotonic,
        name: str = "",
        on_state_change: Callable[[str, str, str], None] | None = None,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.clock = clock
        self.name = name
        self.on_state_change = on_state_change
        self._state: CircuitState = ClosedState()

    @property
    def state_name(self) -> str:
        return self._state.name

    def transition(self, new_state: CircuitState) -> None:
        old_name = self._state.name
        logger.warning("Circuit %s: %s -> %s", self.name, old_name, new_state.name)
        self._state = new_state
        if self.on_state_change is not None:
            self.on_state_change(self.name, old_name, new_state.name)

    def is_available(self) -> bool:
        return self._state.is_available(self)

    def begin_attempt(self) -> None:
        self._state.begin_attempt(self)

    def cancel_attempt(self) -> None:
        self._state.cancel_attempt()

    def record_success(self) -> None:
        self._state.on_success(self)

    def record_failure(self) -> None:
        self._state.on_failure(self)
