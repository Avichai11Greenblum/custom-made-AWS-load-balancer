"""Manual check that alerts arrive: python -m lb.aws.read_alerts

The balancer never runs this. LocalStack has no real inbox (email, SMS), so the
SQS queue subscribed to the alert topic acts as the mailbox. This script prints
the alerts waiting in it and deletes them, so each alert is shown once.
"""

import json

from botocore.exceptions import ClientError

from lb import config
from lb.aws.clients import create_client


def main() -> int:
    sqs = create_client("sqs")
    try:
        queue_url = sqs.get_queue_url(QueueName=config.ALERT_QUEUE_NAME)["QueueUrl"]
    except ClientError as error:
        print(f"Queue {config.ALERT_QUEUE_NAME!r} not found: {error}")
        print("Start the balancer once with LB_AWS_ENABLED=true so it creates the queue.")
        return 1

    count = 0
    while True:
        batch = sqs.receive_message(
            QueueUrl=queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=1
        ).get("Messages", [])
        if not batch:
            break
        for item in batch:
            # SNS wraps the alert in an envelope; the alert text is inside it.
            envelope = json.loads(item["Body"])
            print(f"[{envelope.get('Subject')}] {envelope.get('Message')}")
            sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=item["ReceiptHandle"])
            count += 1
    print(f"{count} alert(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
