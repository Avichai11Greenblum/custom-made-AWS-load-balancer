from lb.aws.sinks import AlertSink
from lb.backend_servers_pool.backend_server import BackendServer
from lb.backend_servers_pool.servers_registry import BackendRegistry
from lb.observers.alert_listeners import register_alert_listeners
from lb.observers.circuit_events import CircuitClosed, CircuitOpened, circuit_event_publisher
from lb.observers.event_listener import EventListener
from lb.observers.health_events import EventPublisher
from lb.resilience.circuit_breaker import CircuitBreaker


class RecordingSink(AlertSink):
    def __init__(self) -> None:
        self.alerts: list[tuple[str, str]] = []

    def send_alert(self, subject: str, message: str) -> None:
        self.alerts.append((subject, message))


class Collector(EventListener):
    def __init__(self, event_type: type) -> None:
        self.event_type = event_type
        self.events: list[object] = []

    def handle(self, event: object) -> None:
        self.events.append(event)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def publisher_with_collectors():
    publisher = EventPublisher()
    opened, closed = Collector(CircuitOpened), Collector(CircuitClosed)
    publisher.add_subscriber(opened)
    publisher.add_subscriber(closed)
    return publisher, opened, closed


def test_breaker_reports_every_state_change():
    changes = []
    breaker = CircuitBreaker(
        failure_threshold=2, name="b1", on_state_change=lambda *change: changes.append(change)
    )
    breaker.record_failure()
    breaker.record_failure()
    assert changes == [("b1", "closed", "open")]


def test_forwarder_publishes_opened_then_closed():
    publisher, opened, closed = publisher_with_collectors()
    clock = FakeClock()
    breaker = CircuitBreaker(
        failure_threshold=2,
        recovery_timeout=10,
        clock=clock,
        name="b1",
        on_state_change=circuit_event_publisher(publisher),
    )
    breaker.record_failure()
    breaker.record_failure()
    assert opened.events == [CircuitOpened("b1")]

    clock.now = 10
    breaker.begin_attempt()
    breaker.record_success()
    assert closed.events == [CircuitClosed("b1")]


def test_failed_trial_does_not_announce_the_opening_again():
    publisher, opened, _ = publisher_with_collectors()
    clock = FakeClock()
    breaker = CircuitBreaker(
        failure_threshold=1,
        recovery_timeout=10,
        clock=clock,
        name="b1",
        on_state_change=circuit_event_publisher(publisher),
    )
    breaker.record_failure()
    clock.now = 10
    breaker.begin_attempt()
    breaker.record_failure()
    assert breaker.state_name == "open"
    assert len(opened.events) == 1


def test_registry_installs_the_callback_on_initial_and_added_backends():
    calls = []
    callback = lambda *change: calls.append(change)  # noqa: E731
    first = BackendServer("http://b1", breaker=CircuitBreaker(failure_threshold=1))
    registry = BackendRegistry([first], on_circuit_change=callback)
    second = BackendServer("http://b2", breaker=CircuitBreaker(failure_threshold=1))
    registry.add(second)

    first.breaker.record_failure()
    second.breaker.record_failure()
    assert calls == [
        ("http://b1", "closed", "open"),
        ("http://b2", "closed", "open"),
    ]


def test_listeners_turn_circuit_events_into_alerts():
    sink = RecordingSink()
    publisher = EventPublisher()
    register_alert_listeners(publisher, sink)
    publisher.publish(CircuitOpened("http://b1"))
    publisher.publish(CircuitClosed("http://b1"))
    assert [subject for subject, _ in sink.alerts] == ["Circuit OPEN", "Circuit CLOSED"]
    assert all("http://b1" in message for _, message in sink.alerts)
