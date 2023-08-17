from dataclasses import dataclass
import json
from typing import Dict, Optional, Tuple, cast
from urllib.parse import urlparse

from src.chain.web3 import sign_message
from src.core.events import ExchangeOracleEvent_TaskFinished, OracleEvent, parse_event
from src.core.manifest import TaskManifest
from src.core.types import (
    ExchangeOracleEventType,
    Networks,
    OracleWebhookTypes,
    RecordingOracleEventType,
)
from src.core.types import CloudProviders


@dataclass
class ParsedBucketUrl:
    provider: str
    bucket_name: str


def parse_data_url(data_url: str) -> ParsedBucketUrl:
    parsed_url = urlparse(data_url)

    if parsed_url.netloc.endswith("s3.amazonaws.com"):
        # AWS S3 bucket
        return ParsedBucketUrl(
            provider=CloudProviders.aws.value,
            bucket_name=parsed_url.netloc.split(".")[0],
        )
    elif parsed_url.netloc.endswith("storage.googleapis.com"):
        # Google Cloud Storage (GCS) bucket
        return ParsedBucketUrl(
            provider=CloudProviders.gcs.value,
            bucket_name=parsed_url.netloc.split(".")[0],
        )
    else:
        raise ValueError(f"{parsed_url.netloc} cloud provider is not supported by CVAT")


def parse_manifest(manifest: dict) -> TaskManifest:
    return TaskManifest.parse_obj(manifest)


def compose_bucket_url(bucket_name: str, provider: str) -> str:
    match provider:
        case CloudProviders.aws.value:
            return f"https://{bucket_name}.s3.amazonaws.com/"
        case CloudProviders.gcs.value:
            return f"https://{bucket_name}.storage.googleapis.com/"


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
    Optionally serialize and sign the message.
    """

    assert (message is not None) ^ (
        body is not None
    ), "Either 'message' or 'body' expected"

    if not message and body:
        message = json.dumps(body)

    signature = sign_message(chain_id, message)

    return message, signature
