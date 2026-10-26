from lb.observers.event_listener import EventListener
from lb.observers.health_events import BackendDown, BackendUp, EventPublisher


class RecordBackendDown(EventListener):
    event_type = BackendDown

    def __init__(self) -> None:
        self.received: list[BackendDown] = []

    def handle(self, event: BackendDown) -> None:
        self.received.append(event)


class BrokenListener(EventListener):
    event_type = BackendDown

    def handle(self, event: BackendDown) -> None:
        raise RuntimeError("boom")


def test_listener_only_gets_events_of_its_type():
    publisher = EventPublisher()
    listener = RecordBackendDown()
    publisher.add_subscriber(listener)
    publisher.publish(BackendUp("http://b1"))
    publisher.publish(BackendDown("http://b2"))
    assert listener.received == [BackendDown("http://b2")]


def test_all_listeners_are_called():
    publisher = EventPublisher()
    first, second = RecordBackendDown(), RecordBackendDown()
    publisher.add_subscriber(first)
    publisher.add_subscriber(second)
    publisher.publish(BackendDown("http://b1"))
    assert first.received == second.received == [BackendDown("http://b1")]


def test_failing_listener_does_not_block_others():
    publisher = EventPublisher()
    listener = RecordBackendDown()
    publisher.add_subscriber(BrokenListener())
    publisher.add_subscriber(listener)
    publisher.publish(BackendDown("http://b1"))
    assert listener.received == [BackendDown("http://b1")]


def test_publish_without_listeners_is_fine():
    EventPublisher().publish(BackendDown("http://b1"))
