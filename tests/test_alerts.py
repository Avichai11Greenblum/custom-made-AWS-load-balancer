import asyncio
import logging
import threading
from unittest.mock import MagicMock

from botocore.exceptions import EndpointConnectionError

from lb import config
from lb.aws import factory
from lb.aws.background import BackgroundAlertSink
from lb.aws.factory import create_alert_sink
from lb.aws.setup import ensure_alert_queue, ensure_alert_topic
from lb.aws.sinks import AlertSink, NoOpAlertSink
from lb.aws.sns_alert_sink import SnsAlertSink
from lb.observers.alert_listeners import register_alert_listeners
from lb.observers.health_events import BackendDown, BackendUp, EventPublisher


class RecordingSink(AlertSink):
    def __init__(self) -> None:
        self.alerts: list[tuple[str, str]] = []
        self.delivered = threading.Event()

    def send_alert(self, subject: str, message: str) -> None:
        self.alerts.append((subject, message))
        self.delivered.set()


class FailingSink(AlertSink):
    def send_alert(self, subject: str, message: str) -> None:
        raise RuntimeError("AWS is down")


def test_sns_sink_publishes_to_the_topic():
    sns = MagicMock()
    SnsAlertSink(sns, "arn:topic").send_alert("Backend DOWN", "b1 is down")
    sns.publish.assert_called_once_with(
        TopicArn="arn:topic", Subject="Backend DOWN", Message="b1 is down"
    )


def test_sns_sink_cuts_long_subjects():
    sns = MagicMock()
    SnsAlertSink(sns, "arn:topic").send_alert("x" * 300, "message")
    assert len(sns.publish.call_args.kwargs["Subject"]) == 100


def test_background_sink_delivers_from_a_worker_thread():
    inner = RecordingSink()

    async def scenario():
        BackgroundAlertSink(inner).send_alert("subject", "message")
        await asyncio.get_running_loop().run_in_executor(None, inner.delivered.wait, 2)

    asyncio.run(scenario())
    assert inner.alerts == [("subject", "message")]


def test_background_sink_delivers_directly_when_no_loop_is_running():
    inner = RecordingSink()
    BackgroundAlertSink(inner).send_alert("subject", "message")
    assert inner.alerts == [("subject", "message")]


def test_background_sink_logs_failures_instead_of_raising(caplog):
    with caplog.at_level(logging.ERROR, logger="lb.aws.background"):
        BackgroundAlertSink(FailingSink()).send_alert("subject", "message")
    assert "Could not deliver alert" in caplog.text


def test_listeners_turn_health_events_into_alerts():
    sink = RecordingSink()
    publisher = EventPublisher()
    register_alert_listeners(publisher, sink)
    publisher.publish(BackendDown("http://b1"))
    publisher.publish(BackendUp("http://b1"))
    assert [subject for subject, _ in sink.alerts] == ["Backend DOWN", "Backend UP"]
    assert all("http://b1" in message for _, message in sink.alerts)


def test_ensure_alert_topic_returns_the_arn():
    sns = MagicMock()
    sns.create_topic.return_value = {"TopicArn": "arn:topic"}
    assert ensure_alert_topic(sns, "lb-alerts") == "arn:topic"
    sns.create_topic.assert_called_once_with(Name="lb-alerts")


def test_ensure_alert_queue_subscribes_the_queue_to_the_topic():
    sqs, sns = MagicMock(), MagicMock()
    sqs.create_queue.return_value = {"QueueUrl": "http://queue-url"}
    sqs.get_queue_attributes.return_value = {"Attributes": {"QueueArn": "arn:queue"}}

    assert ensure_alert_queue(sqs, sns, "arn:topic", "lb-alerts-queue") == "http://queue-url"

    sns.subscribe.assert_called_once_with(TopicArn="arn:topic", Protocol="sqs", Endpoint="arn:queue")
    policy = sqs.set_queue_attributes.call_args.kwargs["Attributes"]["Policy"]
    assert "arn:topic" in policy and "arn:queue" in policy


def test_factory_returns_noop_when_aws_is_off(monkeypatch):
    monkeypatch.setattr(config, "AWS_ENABLED", False)
    assert isinstance(create_alert_sink(), NoOpAlertSink)


def test_factory_returns_background_sns_sink_when_aws_is_on(monkeypatch):
    monkeypatch.setattr(config, "AWS_ENABLED", True)
    fake_client = MagicMock()
    fake_client.create_topic.return_value = {"TopicArn": "arn:topic"}
    fake_client.create_queue.return_value = {"QueueUrl": "http://queue-url"}
    fake_client.get_queue_attributes.return_value = {"Attributes": {"QueueArn": "arn:queue"}}
    monkeypatch.setattr(factory, "create_client", lambda service: fake_client)
    assert isinstance(create_alert_sink(), BackgroundAlertSink)


def test_factory_falls_back_to_noop_when_aws_is_unreachable(monkeypatch):
    monkeypatch.setattr(config, "AWS_ENABLED", True)
    broken_client = MagicMock()
    broken_client.create_topic.side_effect = EndpointConnectionError(endpoint_url="http://x")
    monkeypatch.setattr(factory, "create_client", lambda service: broken_client)
    assert isinstance(create_alert_sink(), NoOpAlertSink)
