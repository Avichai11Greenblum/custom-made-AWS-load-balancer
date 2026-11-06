from lb.aws.sinks import MetricsSink


class CloudWatchMetricsSink(MetricsSink):
    """Sends each data point to AWS CloudWatch (or LocalStack) under one namespace.

    Calls block, so wrap it in BackgroundMetricsSink when used inside the balancer.
    """

    def __init__(self, cloudwatch_client, namespace: str) -> None:
        self._cloudwatch = cloudwatch_client
        self._namespace = namespace

    def put_metric(
        self,
        name: str,
        value: float,
        unit: str = "Count",
        dimensions: dict[str, str] | None = None,
    ) -> None:
        data_point = {"MetricName": name, "Value": value, "Unit": unit}
        if dimensions:
            data_point["Dimensions"] = [
                {"Name": key, "Value": dimension_value} for key, dimension_value in dimensions.items()
            ]
        self._cloudwatch.put_metric_data(Namespace=self._namespace, MetricData=[data_point])
