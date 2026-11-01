import pytest

from lb import config
from lb.aws.clients import create_client
from lb.aws.sinks import AlertSink, MetricsSink, NoOpAlertSink, NoOpMetricsSink


def test_client_points_at_the_configured_endpoint(monkeypatch):
    monkeypatch.setattr(config, "AWS_ENDPOINT_URL", "http://localstack-host:4566")
    monkeypatch.setattr(config, "AWS_REGION", "eu-west-1")
    client = create_client("sns")
    assert client.meta.endpoint_url == "http://localstack-host:4566"
    assert client.meta.region_name == "eu-west-1"


def test_clients_exist_for_every_service_we_will_use():
    for service in ("sns", "sqs", "cloudwatch"):
        assert create_client(service) is not None


def test_noop_sinks_accept_calls_and_do_nothing():
    NoOpAlertSink().send_alert("subject", "message")
    NoOpMetricsSink().put_metric("Requests", 1, dimensions={"Backend": "http://b1"})


def test_noop_sinks_follow_the_interfaces():
    assert isinstance(NoOpAlertSink(), AlertSink)
    assert isinstance(NoOpMetricsSink(), MetricsSink)


def test_interfaces_cannot_be_used_directly():
    with pytest.raises(TypeError):
        AlertSink()
    with pytest.raises(TypeError):
        MetricsSink()
