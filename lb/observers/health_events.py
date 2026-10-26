import logging
from collections import defaultdict
from dataclasses import dataclass

from lb.observers.event_listener import EventListener

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BackendDown:
    """A backend failed enough health checks in a row to be taken out of rotation."""

    url: str


@dataclass(frozen=True)
class BackendUp:
    """A backend passed enough health checks in a row to be put back in rotation."""

    url: str


class EventPublisher:
    """Delivers events to the listeners subscribed to their type (Observer pattern).

    The code that announces an event (e.g. the health checker) only calls
    publish() and knows nothing about who is listening, so new reactions such
    as alerts or metrics can be added with subscribe() without touching it.

    Delivery is synchronous and in-process: publish() runs every matching
    listener in subscription order before it returns.

    Example:
        publisher = EventPublisher()
        publisher.subscribe(LogBackendDown())
        publisher.publish(BackendDown("http://localhost:8001"))
    """

    def __init__(self) -> None:
        self.type_to_listeners: dict[type, list[EventListener]] = defaultdict(list)

    def add_subscriber(self, listener: EventListener) -> None:
        """Call listener.handle(event) for every future event of its event_type.

        Subclasses of listener.event_type are not matched.
        """
        self.type_to_listeners[listener.event_type].append(listener)

    def publish(self, event: object) -> None:
        """Deliver event to every listener subscribed to its type.

        An exception raised by a listener is logged and removed, so the
        remaining listeners and the caller are not affected. Publishing an
        event nobody subscribed to does nothing.
        """
        for listener in self.type_to_listeners[type(event)]:
            try:
                listener.handle(event)
            except Exception:
                # One broken listener must not stop the others or the publisher.
                logger.exception("Listener %r failed on %r", listener, event)
