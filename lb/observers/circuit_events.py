from collections.abc import Callable
from dataclasses import dataclass

from lb.observers.health_events import EventPublisher


@dataclass(frozen=True)
class CircuitOpened:
    """Real requests to a backend failed so often that its circuit breaker opened."""

    url: str


@dataclass(frozen=True)
class CircuitClosed:
    """A trial request to a backend succeeded, so its circuit breaker closed again."""

    url: str


def circuit_event_publisher(publisher: EventPublisher) -> Callable[[str, str, str], None]:
    """Return a callback for CircuitBreaker.on_state_change that publishes circuit events.

    Only the first opening is announced. While the backend stays broken the
    breaker keeps going open -> half-open -> open every recovery timeout, and
    announcing each of those would repeat the same alert.
    """

    def publish_circuit_event(url: str, old_state: str, new_state: str) -> None:
        if old_state == "closed" and new_state == "open":
            publisher.publish(CircuitOpened(url))
        elif new_state == "closed":
            publisher.publish(CircuitClosed(url))

    return publish_circuit_event
