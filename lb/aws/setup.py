import json

from botocore.client import BaseClient


def ensure_alert_topic(sns_client: BaseClient, topic_name: str) -> str:
    """Create the SNS topic if it does not exist yet and return its ARN.

    create_topic does nothing when the topic is already there, so this is safe to
    call on every start. An ARN is AWS's unique id for a resource.
    """
    return sns_client.create_topic(Name=topic_name)["TopicArn"]


def ensure_alert_queue(
    sqs_client: BaseClient, sns_client: BaseClient, topic_arn: str, queue_name: str
) -> str:
    """Create an SQS queue that receives every message published to the topic.

    The queue is a mailbox where alerts can be read back later. Returns its URL.
    """
    queue_url = sqs_client.create_queue(QueueName=queue_name)["QueueUrl"]
    queue_arn = sqs_client.get_queue_attributes(
        QueueUrl=queue_url, AttributeNames=["QueueArn"]
    )["Attributes"]["QueueArn"]

    # Real AWS refuses SNS deliveries unless the queue explicitly allows this topic.
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "sns.amazonaws.com"},
                "Action": "sqs:SendMessage",
                "Resource": queue_arn,
                "Condition": {"ArnEquals": {"aws:SourceArn": topic_arn}},
            }
        ],
    }
    sqs_client.set_queue_attributes(QueueUrl=queue_url, Attributes={"Policy": json.dumps(policy)})
    sns_client.subscribe(TopicArn=topic_arn, Protocol="sqs", Endpoint=queue_arn)
    return queue_url
