import logging

from lb.observers.event_listener import EventListener
from lb.observers.health_events import BackendDown, BackendUp, EventPublisher

logger = logging.getLogger("lb.events")


class LogBackendDown(EventListener):
    event_type = BackendDown

    def handle(self, event: BackendDown) -> None:
        logger.warning("Backend DOWN: %s", event.url)


class LogBackendUp(EventListener):
    event_type = BackendUp

    def handle(self, event: BackendUp) -> None:
        logger.info("Backend UP: %s", event.url)


def register_default_listeners(publisher: EventPublisher) -> None:
    publisher.add_subscriber(LogBackendDown())
    publisher.add_subscriber(LogBackendUp())
