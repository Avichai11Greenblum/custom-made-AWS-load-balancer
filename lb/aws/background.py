import asyncio
import logging
from collections.abc import Callable

from lb.aws.sinks import AlertSink, MetricsSink

logger = logging.getLogger(__name__)


def _run_in_worker_thread(function: Callable[..., None], *args: object) -> None:
    """Run function(*args) on a worker thread so the event loop is not blocked.

    boto3 calls block. Calling them straight from the event loop would freeze
    every request being proxied for as long as AWS takes to answer.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        function(*args)  # no event loop running: nothing to protect
        return
    loop.run_in_executor(None, function, *args)


class BackgroundAlertSink(AlertSink):
    """Decorator that delivers alerts on a worker thread, so the caller never waits.

    A failed delivery is logged and never reaches the caller.
    """

    def __init__(self, inner: AlertSink) -> None:
        self._inner = inner

    def send_alert(self, subject: str, message: str) -> None:
        _run_in_worker_thread(self._deliver, subject, message)

    def _deliver(self, subject: str, message: str) -> None:
        try:
            self._inner.send_alert(subject, message)
        except Exception:
            logger.exception("Could not deliver alert %r", subject)


class BackgroundMetricsSink(MetricsSink):
    """Decorator that delivers metrics on a worker thread, so the caller never waits.

    A failed delivery is logged and never reaches the caller.
    """

    def __init__(self, inner: MetricsSink) -> None:
        self._inner = inner

    def put_metric(
        self,
        name: str,
        value: float,
        unit: str = "Count",
        dimensions: dict[str, str] | None = None,
    ) -> None:
        _run_in_worker_thread(self._deliver, name, value, unit, dimensions)

    def _deliver(
        self, name: str, value: float, unit: str, dimensions: dict[str, str] | None
    ) -> None:
        try:
            self._inner.put_metric(name, value, unit, dimensions)
        except Exception:
            logger.exception("Could not deliver metric %r", name)
