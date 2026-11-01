from abc import ABC, abstractmethod


class AlertSink(ABC):
    """Where alerts go (Adapter pattern).

    The rest of the balancer talks to this interface and never to AWS directly.
    """

    @abstractmethod
    def send_alert(self, subject: str, message: str) -> None:
        """Deliver one alert message."""


class MetricsSink(ABC):
    """Where numbers over time go (Adapter pattern)."""

    @abstractmethod
    def put_metric(
        self,
        name: str,
        value: float,
        unit: str = "Count",
        dimensions: dict[str, str] | None = None,
    ) -> None:
        """Record one data point, e.g. put_metric("Requests", 1, dimensions={"Backend": url})."""


class NoOpAlertSink(AlertSink):
    """Drops every alert. Used when AWS is turned off, so the balancer runs without LocalStack."""

    def send_alert(self, subject: str, message: str) -> None:
        pass


class NoOpMetricsSink(MetricsSink):
    """Drops every metric. Used when AWS is turned off."""

    def put_metric(
        self,
        name: str,
        value: float,
        unit: str = "Count",
        dimensions: dict[str, str] | None = None,
    ) -> None:
        pass
