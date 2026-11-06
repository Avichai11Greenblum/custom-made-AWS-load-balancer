from lb.aws.sinks import AlertSink
from lb.observers.circuit_events import CircuitClosed, CircuitOpened
from lb.observers.event_listener import EventListener
from lb.observers.health_events import BackendDown, BackendUp, EventPublisher


class AlertOnBackendDown(EventListener):
    event_type = BackendDown

    def __init__(self, sink: AlertSink) -> None:
        self._sink = sink

    def handle(self, event: BackendDown) -> None:
        self._sink.send_alert(
            "Backend DOWN",
            f"{event.url} failed its health checks and was taken out of rotation.",
        )


class AlertOnBackendUp(EventListener):
    event_type = BackendUp

    def __init__(self, sink: AlertSink) -> None:
        self._sink = sink

    def handle(self, event: BackendUp) -> None:
        self._sink.send_alert(
            "Backend UP",
            f"{event.url} passed its health checks and is back in rotation.",
        )


class AlertOnCircuitOpened(EventListener):
    event_type = CircuitOpened

    def __init__(self, sink: AlertSink) -> None:
        self._sink = sink

    def handle(self, event: CircuitOpened) -> None:
        self._sink.send_alert(
            "Circuit OPEN",
            f"Requests to {event.url} keep failing, so the balancer stopped sending it traffic.",
        )


class AlertOnCircuitClosed(EventListener):
    event_type = CircuitClosed

    def __init__(self, sink: AlertSink) -> None:
        self._sink = sink

    def handle(self, event: CircuitClosed) -> None:
        self._sink.send_alert(
            "Circuit CLOSED",
            f"A trial request to {event.url} succeeded, so it receives traffic again.",
        )


def register_alert_listeners(publisher: EventPublisher, sink: AlertSink) -> None:
    publisher.add_subscriber(AlertOnBackendDown(sink))
    publisher.add_subscriber(AlertOnBackendUp(sink))
    publisher.add_subscriber(AlertOnCircuitOpened(sink))
    publisher.add_subscriber(AlertOnCircuitClosed(sink))
