import asyncio
import threading
from unittest.mock import MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request
from botocore.exceptions import EndpointConnectionError

from lb import config
from lb.aws import factory
from lb.aws.background import BackgroundMetricsSink
from lb.aws.cloudwatch_metrics_sink import CloudWatchMetricsSink
from lb.aws.factory import create_metrics_sink
from lb.aws.sinks import MetricsSink, NoOpMetricsSink
from lb.backend_servers_pool.backend_server import BackendServer
from lb.backend_servers_pool.servers_registry import BackendRegistry
from lb.metrics.publisher import MetricsPublisher
from lb.metrics.request_stats import RequestStats
from lb.middleware.request_metrics import RequestMetrics


class RecordingMetricsSink(MetricsSink):
    def __init__(self) -> None:
        self.points: list[tuple[str, float, str]] = []
        self.delivered = threading.Event()

    def put_metric(self, name, value, unit="Count", dimensions=None) -> None:
        self.points.append((name, value, unit))
        self.delivered.set()


class FailingMetricsSink(MetricsSink):
    def put_metric(self, name, value, unit="Count", dimensions=None) -> None:
        raise RuntimeError("AWS is down")


def test_request_stats_snapshot_sums_and_resets():
    stats = RequestStats()
    stats.record(10.0, is_error=False)
    stats.record(30.0, is_error=True)

    snapshot = stats.take_snapshot()
    assert snapshot.requests == 2
    assert snapshot.errors == 1
    assert snapshot.average_latency_ms == 20.0
    assert snapshot.max_latency_ms == 30.0

    assert stats.take_snapshot().requests == 0


def run_through_middleware(stats, call_next):
    return asyncio.run(RequestMetrics(stats).handle(make_mocked_request("GET", "/"), call_next))


def test_middleware_records_successful_request():
    stats = RequestStats()

    async def ok(request):
        return web.Response(status=200)

    run_through_middleware(stats, ok)
    snapshot = stats.take_snapshot()
    assert (snapshot.requests, snapshot.errors) == (1, 0)


def test_middleware_counts_5xx_as_error():
    stats = RequestStats()

    async def bad_gateway(request):
        return web.Response(status=502)

    run_through_middleware(stats, bad_gateway)
    assert stats.take_snapshot().errors == 1


def test_middleware_counts_exception_as_error_and_reraises():
    stats = RequestStats()

    async def broken(request):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        run_through_middleware(stats, broken)
    assert stats.take_snapshot().errors == 1


def test_publisher_reports_requests_latency_and_healthy_backends():
    stats = RequestStats()
    stats.record(10.0, is_error=False)
    stats.record(30.0, is_error=True)
    down = BackendServer("http://b2", healthy=False)
    registry = BackendRegistry([BackendServer("http://b1"), down])
    sink = RecordingMetricsSink()

    MetricsPublisher(stats, registry, sink, interval=10).publish_once()

    assert sink.points == [
        ("Requests", 2, "Count"),
        ("Errors", 1, "Count"),
        ("LatencyAverage", 20.0, "Milliseconds"),
        ("LatencyMax", 30.0, "Milliseconds"),
        ("HealthyBackends", 1, "None"),
    ]


def test_publisher_skips_latency_when_idle():
    sink = RecordingMetricsSink()
    MetricsPublisher(RequestStats(), BackendRegistry(), sink, interval=10).publish_once()
    assert [name for name, _, _ in sink.points] == ["Requests", "Errors", "HealthyBackends"]


def test_cloudwatch_sink_sends_a_data_point_with_dimensions():
    cloudwatch = MagicMock()
    sink = CloudWatchMetricsSink(cloudwatch, "LoadBalancer")
    sink.put_metric("Requests", 5, "Count", {"Backend": "http://b1"})
    cloudwatch.put_metric_data.assert_called_once_with(
        Namespace="LoadBalancer",
        MetricData=[
            {
                "MetricName": "Requests",
                "Value": 5,
                "Unit": "Count",
                "Dimensions": [{"Name": "Backend", "Value": "http://b1"}],
            }
        ],
    )


def test_cloudwatch_sink_omits_dimensions_when_none_given():
    cloudwatch = MagicMock()
    CloudWatchMetricsSink(cloudwatch, "LoadBalancer").put_metric("Requests", 5)
    data_point = cloudwatch.put_metric_data.call_args.kwargs["MetricData"][0]
    assert "Dimensions" not in data_point


def test_background_metrics_sink_delivers_from_a_worker_thread():
    inner = RecordingMetricsSink()

    async def scenario():
        BackgroundMetricsSink(inner).put_metric("Requests", 3)
        await asyncio.get_running_loop().run_in_executor(None, inner.delivered.wait, 2)

    asyncio.run(scenario())
    assert inner.points == [("Requests", 3, "Count")]


def test_background_metrics_sink_logs_failures_instead_of_raising(caplog):
    BackgroundMetricsSink(FailingMetricsSink()).put_metric("Requests", 3)
    assert "Could not deliver metric" in caplog.text


def test_factory_returns_noop_metrics_when_aws_is_off(monkeypatch):
    monkeypatch.setattr(config, "AWS_ENABLED", False)
    assert isinstance(create_metrics_sink(), NoOpMetricsSink)


def test_factory_returns_background_cloudwatch_sink_when_aws_is_on(monkeypatch):
    monkeypatch.setattr(config, "AWS_ENABLED", True)
    monkeypatch.setattr(factory, "create_client", lambda service: MagicMock())
    assert isinstance(create_metrics_sink(), BackgroundMetricsSink)


def test_factory_falls_back_to_noop_metrics_when_cloudwatch_is_unreachable(monkeypatch):
    monkeypatch.setattr(config, "AWS_ENABLED", True)
    broken_client = MagicMock()
    broken_client.list_metrics.side_effect = EndpointConnectionError(endpoint_url="http://x")
    monkeypatch.setattr(factory, "create_client", lambda service: broken_client)
    assert isinstance(create_metrics_sink(), NoOpMetricsSink)
