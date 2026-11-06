import asyncio
import logging

from lb.aws.sinks import AlertSink

logger = logging.getLogger(__name__)


class BackgroundAlertSink(AlertSink):
    """Decorator that delivers alerts on a worker thread, so the caller never waits.

    boto3 calls block. Sending an alert straight from the event loop would freeze
    every request being proxied for as long as AWS takes to answer. A failed
    delivery is logged and never reaches the caller.
    """

    def __init__(self, inner: AlertSink) -> None:
        self._inner = inner

    def send_alert(self, subject: str, message: str) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self._deliver(subject, message)  # no event loop running: nothing to protect
            return
        loop.run_in_executor(None, self._deliver, subject, message)

    def _deliver(self, subject: str, message: str) -> None:
        try:
            self._inner.send_alert(subject, message)
        except Exception:
            logger.exception("Could not deliver alert %r", subject)
