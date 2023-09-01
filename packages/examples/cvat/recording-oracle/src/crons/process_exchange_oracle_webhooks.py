import io
import logging
from typing import Dict
import httpx
from sqlalchemy.orm import Session
from src.chain.kvstore import get_exchange_oracle_url

from src.core.oracle_events import (
    RecordingOracleEvent_TaskCompleted,
    RecordingOracleEvent_TaskRejected,
)

from src.core.config import Config
from src.db import SessionLocal
from src.core.config import CronConfig, StorageConfig
from src.log import get_root_logger
from src.models import Webhook
from src.utils.logging import get_function_logger
from src.utils.webhooks import prepare_outgoing_webhook_body, prepare_signed_message

from src.recording.process_intermediate_results import (
    parse_annotation_metafile,
    process_intermediate_results,
)

from src.core.types import ExchangeOracleEventType, OracleWebhookTypes
import src.services.cloud.client as cloud_client
from src.services.cloud import download_file
from src.core.annotation import ANNOTATION_METAFILE_NAME, RESULTING_ANNOTATIONS_FILE
from src.utils.storage import compose_bucket_filename

import src.services.webhooks as oracle_db_service
import src.chain.escrow as escrow


LOG_MODULE = "cron.webhook"
module_logger = get_root_logger().getChild(LOG_MODULE)


def process_incoming_exchange_oracle_webhooks():
    """
    Process incoming oracle webhooks
    """
    logger = get_function_logger(module_logger)

    try:
        logger.debug("Starting cron job")

        with SessionLocal.begin() as session:
            webhooks = oracle_db_service.inbox.get_pending_webhooks(
                session,
                OracleWebhookTypes.exchange_oracle,
                CronConfig.process_exchange_oracle_webhooks_chunk_size,
            )

            for webhook in webhooks:
                try:
                    handle_exchange_oracle_event(
                        webhook, db_session=session, logger=logger
                    )

                    oracle_db_service.inbox.handle_webhook_success(session, webhook.id)
                except Exception as e:
                    logger.exception(f"Webhook {webhook.id} handling failed: {e}")
                    oracle_db_service.inbox.handle_webhook_fail(session, webhook.id)
    except Exception as e:
        logger.exception(e)
    finally:
        logger.debug("Finishing cron job")


def handle_exchange_oracle_event(
    webhook: Webhook, *, db_session: Session, logger: logging.Logger
):
    assert webhook.type == OracleWebhookTypes.exchange_oracle

    match webhook.event_type:
        case ExchangeOracleEventType.task_finished:
            escrow.validate_escrow(webhook.chain_id, webhook.escrow_address)
            job_type = escrow.get_escrow_job_type(
                webhook.chain_id, webhook.escrow_address
            )

            excor_bucket_host = Config.exchange_oracle_storage_config.endpoint_url
            excor_bucket_name = (
                Config.exchange_oracle_storage_config.results_bucket_name
            )

            excor_annotation_meta_path = compose_bucket_filename(
                webhook.escrow_address, webhook.chain_id, ANNOTATION_METAFILE_NAME
            )
            annotation_metafile = io.BytesIO(
                download_file(
                    excor_bucket_host, excor_bucket_name, excor_annotation_meta_path
                )
            )
            annotation_meta = parse_annotation_metafile(annotation_metafile)

            job_annotations: Dict[int, io.RawIOBase] = {}
            for job_meta in annotation_meta.jobs:
                job_filename = compose_bucket_filename(
                    webhook.escrow_address,
                    webhook.chain_id,
                    job_meta.annotation_filename,
                )
                job_annotations[job_meta.job_id] = io.BytesIO(
                    download_file(excor_bucket_host, excor_bucket_name, job_filename)
                )

            # TODO: add GT checks & validation
            results = process_intermediate_results(
                annotation_meta, job_annotations, job_type=job_type
            )

            if results.task_completed:
                excor_merged_annotation_path = compose_bucket_filename(
                    webhook.escrow_address, webhook.chain_id, RESULTING_ANNOTATIONS_FILE
                )
                merged_annotations = download_file(
                    excor_bucket_host, excor_bucket_name, excor_merged_annotation_path
                )

                storage_client = cloud_client.S3Client(
                    StorageConfig.endpoint_url,
                    access_key=StorageConfig.access_key,
                    secret_key=StorageConfig.secret_key,
                )

                # TODO: add encryption
                storage_client.create_file(
                    Config.storage_config.results_bucket_name,
                    RESULTING_ANNOTATIONS_FILE,
                    merged_annotations,
                )
                storage_client.create_file(
                    Config.storage_config.results_bucket_name,
                    VALIDATION_METAFILE_NAME,
                    validation_metafile,
                )

                # TODO: add annotator results

                escrow.store_results(
                    webhook.chain_id,
                    webhook.escrow_address,
                    f"{StorageConfig.bucket_url()}{RESULTING_ANNOTATIONS_FILE}",
                    "samplehash",  # TODO: add hash
                )

                oracle_db_service.outbox.create_webhook(
                    db_session,
                    webhook.escrow_address,
                    webhook.chain_id,
                    OracleWebhookTypes.reputation_oracle.value,
                    event=RecordingOracleEvent_TaskCompleted(),
                )
                oracle_db_service.outbox.create_webhook(
                    db_session,
                    webhook.escrow_address,
                    webhook.chain_id,
                    OracleWebhookTypes.exchange_oracle.value,
                    event=RecordingOracleEvent_TaskCompleted(),
                )
            else:
                oracle_db_service.outbox.create_webhook(
                    db_session,
                    webhook.escrow_address,
                    webhook.chain_id,
                    OracleWebhookTypes.exchange_oracle.value,
                    event=RecordingOracleEvent_TaskRejected(
                        rejected_job_ids=results.rejected_job_ids
                    ),
                )

        case _:
            assert False, f"Unknown exchange oracle event {webhook.event_type}"


def process_outgoing_exchange_oracle_webhooks():
    """
    Process webhooks that needs to be sent to exchange oracle:
      * Retrieves `webhook_url` from KVStore
      * Sends webhook to exchange oracle
    """
    logger = get_function_logger(module_logger)

    try:
        logger.debug("Starting cron job")

        with SessionLocal.begin() as session:
            webhooks = oracle_db_service.outbox.get_pending_webhooks(
                session,
                OracleWebhookTypes.exchange_oracle,
                CronConfig.process_exchange_oracle_webhooks_chunk_size,
            )
            for webhook in webhooks:
                try:
                    body = prepare_outgoing_webhook_body(
                        webhook.escrow_address,
                        webhook.chain_id,
                        webhook.event_type,
                        webhook.event_data,
                    )
                    serialized_data, signature = prepare_signed_message(
                        webhook.escrow_address, webhook.chain_id, body=body
                    )

                    headers = {"human-signature": signature}
                    webhook_url = get_exchange_oracle_url(
                        webhook.chain_id, webhook.escrow_address
                    )
                    with httpx.Client() as client:
                        response = client.post(
                            webhook_url, headers=headers, data=serialized_data
                        )
                        response.raise_for_status()
                    oracle_db_service.outbox.handle_webhook_success(session, webhook.id)
                except Exception as e:
                    logger.exception(f"Webhook {webhook.id} sending failed: {e}")
                    oracle_db_service.outbox.handle_webhook_fail(session, webhook.id)
    except Exception as e:
        logger.exception(e)
    finally:
        logger.debug("Finishing cron job")
