from botocore.client import BaseClient

from lb.aws.sinks import AlertSink

# SNS rejects subjects longer than 100 characters.
MAX_SUBJECT_LENGTH = 100


class SnsAlertSink(AlertSink):
    """Sends alerts as messages published to an SNS topic.

    The call to AWS is blocking. Wrap this in BackgroundAlertSink when it is used
    inside the running proxy.
    """

    def __init__(self, sns_client: BaseClient, topic_arn: str) -> None:
        self._sns = sns_client
        self._topic_arn = topic_arn

    def send_alert(self, subject: str, message: str) -> None:
        self._sns.publish(
            TopicArn=self._topic_arn,
            Subject=subject[:MAX_SUBJECT_LENGTH],
            Message=message,
        )
