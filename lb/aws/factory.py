import logging

from botocore.exceptions import BotoCoreError, ClientError

from lb import config
from lb.aws.background import BackgroundAlertSink
from lb.aws.clients import create_client
from lb.aws.setup import ensure_alert_queue, ensure_alert_topic
from lb.aws.sinks import AlertSink, NoOpAlertSink
from lb.aws.sns_alert_sink import SnsAlertSink

logger = logging.getLogger(__name__)


def create_alert_sink() -> AlertSink:
    """Build the alert sink the settings ask for.

    With AWS off (the default), alerts are dropped. With AWS on, the SNS topic and
    SQS queue are created and alerts are published to the topic. If AWS cannot be
    reached at startup the balancer still runs, with alerts off.
    """
    if not config.AWS_ENABLED:
        return NoOpAlertSink()
    try:
        sns = create_client("sns")
        sqs = create_client("sqs")
        topic_arn = ensure_alert_topic(sns, config.ALERT_TOPIC_NAME)
        ensure_alert_queue(sqs, sns, topic_arn, config.ALERT_QUEUE_NAME)
    except (BotoCoreError, ClientError):
        logger.exception("AWS alerts are off: could not set up the SNS topic and SQS queue")
        return NoOpAlertSink()
    logger.info("AWS alerts are on: topic %s", topic_arn)
    return BackgroundAlertSink(SnsAlertSink(sns, topic_arn))
