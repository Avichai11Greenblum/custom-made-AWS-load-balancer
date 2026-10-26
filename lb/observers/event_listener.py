from abc import ABC, abstractmethod


class EventListener(ABC):
    """Object that reacts to one type of event.

    Subclass it, set event_type to the event class you care about, and put the
    reaction in handle(). Register an instance with EventPublisher.subscribe().

    Example:
        class PrintBackendDown(EventListener):
            event_type = BackendDown

            def handle(self, event: BackendDown) -> None:
                print(event.url)
    """

    event_type: type

    @abstractmethod
    def handle(self, event: object) -> None:
        """React to one event of type event_type."""
