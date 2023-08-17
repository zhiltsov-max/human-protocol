import httpx
import logging

from src.db import SessionLocal
from src.core.config import CronConfig

from src.chain.kvstore import get_recording_oracle_url

from src.core.types import OracleWebhookTypes
from src.utils.helpers import (
    prepare_recording_oracle_webhook_body,
    prepare_signed_message,
)

import src.services.webhook as db_service


LOG_MODULE = "[cron][webhook][process_recording_oracle_webhooks]"


def process_recording_oracle_webhooks() -> None:
    """
    Process webhooks that needs to be sent to recording oracle:
      * Retrieves `webhook_url` from KVStore
      * Sends webhook to recording oracle
    """
    try:
        logger = logging.getLogger("app")
        logger.info(f"{LOG_MODULE} Starting cron job")
        with SessionLocal.begin() as session:
            webhooks = db_service.outbox.get_pending_webhooks(
                session,
                OracleWebhookTypes.recording_oracle.value,
                CronConfig.process_recording_oracle_webhooks_chunk_size,
            )
            for webhook in webhooks:
                try:
                    webhook_url = get_recording_oracle_url(
                        webhook.chain_id, webhook.escrow_address
                    )

                    body = prepare_recording_oracle_webhook_body(
                        webhook.escrow_address,
                        webhook.chain_id,
                        webhook.event_type,
                        webhook.event_data,
                    )
                    serialized_data, signature = prepare_signed_message(
                        webhook.escrow_address, webhook.chain_id, body=body
                    )

                    headers = {"human-signature": signature}
                    with httpx.Client() as client:
                        response = client.post(
                            webhook_url, headers=headers, data=serialized_data
                        )
                        response.raise_for_status()
                    db_service.outbox.handle_webhook_success(session, webhook.id)
                except Exception as e:
                    logger.exception(
                        f"{LOG_MODULE} Webhook: {webhook.id} failed during execution. Error {e}"
                    )
                    db_service.outbox.handle_webhook_fail(session, webhook.id)

        logger.info(f"{LOG_MODULE} Finishing cron job")
        return None
    except Exception as e:
        logger.exception(e)
