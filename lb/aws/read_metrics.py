"""Manual check that metrics arrive: python -m lb.aws.read_metrics

The balancer never runs this. It asks CloudWatch (LocalStack) for the latest
data point of every metric the balancer reports and prints it.
"""

from datetime import datetime, timedelta, timezone

from lb import config
from lb.aws.clients import create_client

LOOK_BACK = timedelta(minutes=30)
PERIOD_SECONDS = 60


def main() -> int:
    cloudwatch = create_client("cloudwatch")
    metrics = cloudwatch.list_metrics(Namespace=config.METRICS_NAMESPACE)["Metrics"]
    if not metrics:
        print(f"No metrics in namespace {config.METRICS_NAMESPACE!r} yet.")
        print("Start the balancer with LB_AWS_ENABLED=true, send some requests, and wait one report interval.")
        return 1

    now = datetime.now(timezone.utc)
    for metric in sorted(metrics, key=lambda item: item["MetricName"]):
        name = metric["MetricName"]
        points = cloudwatch.get_metric_statistics(
            Namespace=config.METRICS_NAMESPACE,
            MetricName=name,
            Dimensions=metric.get("Dimensions", []),
            StartTime=now - LOOK_BACK,
            EndTime=now + timedelta(minutes=1),
            Period=PERIOD_SECONDS,
            Statistics=["Sum", "Average", "Maximum"],
        )["Datapoints"]
        if not points:
            print(f"{name}: no data points in the last {LOOK_BACK}")
            continue
        latest = max(points, key=lambda point: point["Timestamp"])
        unit = latest.get("Unit", "")
        # Counts add up over the period; the other metrics are values to average.
        shown = latest["Sum"] if unit == "Count" else latest["Average"]
        print(f"{name}: {shown:g} {unit}  (latest of {len(points)} one-minute period(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
