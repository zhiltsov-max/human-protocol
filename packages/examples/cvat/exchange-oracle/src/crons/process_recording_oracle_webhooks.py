import httpx

from src.db import SessionLocal
from src.core.config import CronConfig

from src.chain.kvstore import get_recording_oracle_url

from src.core.types import OracleWebhookTypes
from src.log import get_root_logger
from src.utils.helpers import (
    prepare_recording_oracle_webhook_body,
    prepare_signed_message,
)

import src.services.webhook as db_service
from src.utils.logging import get_function_logger


LOG_MODULE = "cron.webhook"
module_logger = get_root_logger().getChild(LOG_MODULE)


def process_recording_oracle_webhooks():
    """
    Process webhooks that needs to be sent to recording oracle:
      * Retrieves `webhook_url` from KVStore
      * Sends webhook to recording oracle
    """
    logger = get_function_logger(module_logger)

    try:
        logger.info("Starting cron job")

        with SessionLocal.begin() as session:
            webhooks = db_service.outbox.get_pending_webhooks(
                session,
                OracleWebhookTypes.recording_oracle,
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
                    # TODO: restore
                    # with httpx.Client() as client:
                    #     response = client.post(
                    #         webhook_url, headers=headers, data=serialized_data
                    #     )
                    #     response.raise_for_status()
                    db_service.outbox.handle_webhook_success(session, webhook.id)
                except Exception as e:
                    logger.exception(f"Webhook {webhook.id} sending failed: {e}")
                    db_service.outbox.handle_webhook_fail(session, webhook.id)

        logger.info("Finishing cron job")
    except Exception as e:
        logger.exception(e)
