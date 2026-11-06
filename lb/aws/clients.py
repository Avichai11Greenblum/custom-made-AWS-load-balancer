import boto3
from botocore.client import BaseClient
from botocore.config import Config

from lb import config

# Fail fast when AWS or LocalStack is not reachable, instead of hanging for a minute.
_CLIENT_CONFIG = Config(connect_timeout=3, read_timeout=5, retries={"max_attempts": 1})


def create_client(service: str) -> BaseClient:
    """Create a boto3 client for "sns", "sqs", "cloudwatch" and so on.

    With LB_AWS_ENDPOINT_URL set (the default, pointing at LocalStack) it talks to
    LocalStack, which accepts any credentials. With it empty, boto3 uses real AWS
    and finds credentials the usual way (environment variables, ~/.aws).
    """
    endpoint_url = config.AWS_ENDPOINT_URL
    credentials = (
        {"aws_access_key_id": "test", "aws_secret_access_key": "test"} if endpoint_url else {}
    )
    return boto3.client(
        service,
        endpoint_url=endpoint_url,
        region_name=config.AWS_REGION,
        config=_CLIENT_CONFIG,
        **credentials,
    )
