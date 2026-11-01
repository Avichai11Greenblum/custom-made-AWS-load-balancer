"""Connectivity check: python -m lb.aws.check

Calls one harmless "list" operation on SNS, SQS and CloudWatch.
"""

from lb import config
from lb.aws.clients import create_client

CHECKS = {
    "sns": lambda client: client.list_topics()["Topics"],
    "sqs": lambda client: client.list_queues().get("QueueUrls", []),
    "cloudwatch": lambda client: client.list_metrics()["Metrics"],
}


def main() -> int:
    print(f"Endpoint: {config.AWS_ENDPOINT_URL or 'real AWS'}, region: {config.AWS_REGION}")
    failed = False
    for service, list_things in CHECKS.items():
        try:
            found = list_things(create_client(service))
            print(f"{service}: OK ({len(found)} found)")
        except Exception as error:  # a diagnostic script: report any failure and keep going
            failed = True
            print(f"{service}: FAILED - {error}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
