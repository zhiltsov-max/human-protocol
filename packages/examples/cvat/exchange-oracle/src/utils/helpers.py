from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Dict, Optional, Tuple, cast
from urllib.parse import urljoin, urlparse

from src.chain.web3 import sign_message
from src.core.config import Config
from src.core.oracle_events import ExchangeOracleEvent_TaskFinished, parse_event
from src.core.manifest import TaskManifest
from src.core.types import (
    ExchangeOracleEventType,
    Networks,
    OracleWebhookTypes,
)
from src.core.types import CloudProviders


@dataclass
class ParsedBucketUrl:
    provider: str
    host_url: str
    bucket_name: str
    path: str


DEFAULT_S3_HOST = "s3.amazonaws.com"


def parse_bucket_url(data_url: str) -> ParsedBucketUrl:
    parsed_url = urlparse(data_url)

    if parsed_url.netloc.endswith(DEFAULT_S3_HOST):
        # AWS S3 bucket
        return ParsedBucketUrl(
            provider=CloudProviders.aws.value,
            host_url=f"https://{DEFAULT_S3_HOST}",
            bucket_name=parsed_url.netloc.split(".")[0],
            path=parsed_url.path.lstrip("/"),
        )
    # elif parsed_url.netloc.endswith("storage.googleapis.com"):
    #     # Google Cloud Storage (GCS) bucket
    #     return ParsedBucketUrl(
    #         provider=CloudProviders.gcs.value,
    #         bucket_name=parsed_url.netloc.split(".")[0],
    #     )
    elif Config.features.enable_custom_cloud_host:
        return ParsedBucketUrl(
            provider=CloudProviders.aws.value,
            host_url=f"{parsed_url.scheme}://{parsed_url.netloc.partition('.')[2]}",
            bucket_name=parsed_url.netloc.split(".")[0],
            path=parsed_url.path.lstrip("/"),
        )
    else:
        raise ValueError(f"{parsed_url.netloc} cloud provider is not supported by CVAT")


def parse_manifest(manifest: dict) -> TaskManifest:
    return TaskManifest.parse_obj(manifest)


def compose_bucket_url(
    bucket_name: str, provider: CloudProviders, *, bucket_host: Optional[str] = None
) -> str:
    match provider:
        case CloudProviders.aws.value:
            return f"https://{bucket_name}.{bucket_host or 's3.amazonaws.com'}/"
        case CloudProviders.gcs.value:
            return f"https://{bucket_name}.{bucket_host or 'storage.googleapis.com'}/"


def prepare_recording_oracle_webhook_body(
    escrow_address: str,
    chain_id: Networks,
    event_type: str,
    event_data: dict,
) -> Dict:
    body = {"escrow_address": escrow_address, "chain_id": chain_id}

    event = parse_event(OracleWebhookTypes.exchange_oracle, event_type, event_data)

    match event_type:
        case ExchangeOracleEventType.task_finished:
            event = cast(ExchangeOracleEvent_TaskFinished, event)
            body["task_id"] = event.task_id
            body["s3_url"] = event.s3_url

        case _:
            assert False, f"Unexpected event {event_type} for recoding oracle"

    return body


def prepare_signed_message(
    escrow_address: str,
    chain_id: Networks,
    message: Optional[str] = None,
    body: Optional[dict] = None,
) -> Tuple[str, str]:
    """
    Sign the message with the service identity.
    Optionally, can serialize the input structure.
    """

    assert (message is not None) ^ (
        body is not None
    ), "Either 'message' or 'body' expected"

    if not message and body:
        message = json.dumps(body)

    signature = sign_message(chain_id, message)

    return message, signature


def utcnow() -> datetime:
    "Returns tz-aware UTC now"
    return datetime.now(timezone.utc)


def compose_assignment_url(task_id, job_id) -> str:
    return urljoin(Config.cvat_config.cvat_url, f"/tasks/{task_id}/jobs/{job_id}")
