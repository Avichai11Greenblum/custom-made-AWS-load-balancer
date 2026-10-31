from lb.backend_servers_pool.backend_server import BackendServer
from lb.observers.event_listener import EventListener
from lb.observers.health_events import BackendDown, BackendUp, EventPublisher
from lb.resilience.health_checker import HealthChecker


class RecordBackendDown(EventListener):
    event_type = BackendDown

    def __init__(self, events: list) -> None:
        self._events = events

    def handle(self, event: BackendDown) -> None:
        self._events.append(event)


class RecordBackendUp(EventListener):
    event_type = BackendUp

    def __init__(self, events: list) -> None:
        self._events = events

    def handle(self, event: BackendUp) -> None:
        self._events.append(event)


def make_checker(fail_threshold=2, rise_threshold=2):
    backend = BackendServer(url="http://b1")
    publisher = EventPublisher()
    events = []
    publisher.add_subscriber(RecordBackendDown(events))
    publisher.add_subscriber(RecordBackendUp(events))
    checker = HealthChecker(
        [backend],
        session=None,
        event_publisher=publisher,
        fail_threshold=fail_threshold,
        rise_threshold=rise_threshold,
    )
    return backend, checker, events


def test_backend_goes_down_only_after_threshold_failures():
    backend, checker, events = make_checker(fail_threshold=2)
    checker.record_result(backend, False)
    assert backend.healthy
    assert events == []
    checker.record_result(backend, False)
    assert not backend.healthy
    assert events == [BackendDown("http://b1")]


def test_one_success_resets_the_failure_streak():
    backend, checker, events = make_checker(fail_threshold=2)
    checker.record_result(backend, False)
    checker.record_result(backend, True)
    checker.record_result(backend, False)
    assert backend.healthy
    assert events == []


def test_backend_comes_back_after_threshold_successes():
    backend, checker, events = make_checker(fail_threshold=1, rise_threshold=2)
    checker.record_result(backend, False)
    checker.record_result(backend, True)
    assert not backend.healthy
    checker.record_result(backend, True)
    assert backend.healthy
    assert events == [BackendDown("http://b1"), BackendUp("http://b1")]


def test_down_event_is_published_once_not_on_every_failure():
    backend, checker, events = make_checker(fail_threshold=1)
    for _ in range(5):
        checker.record_result(backend, False)
    assert events == [BackendDown("http://b1")]
