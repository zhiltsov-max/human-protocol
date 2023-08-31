import httpx

from src.db import SessionLocal
from src.core.config import CronConfig

from src.chain.escrow import get_reputation_oracle_address
from src.chain.kvstore import get_reputation_oracle_url

from src.core.types import OracleWebhookTypes
from src.log import get_root_logger
from src.utils.webhooks import prepare_outgoing_webhook_body, prepare_signed_message

import src.services.webhooks as oracle_db_service
from src.utils.logging import get_function_logger


LOG_MODULE = "cron.webhook"
module_logger = get_root_logger().getChild(LOG_MODULE)


def process_outgoing_reputation_oracle_webhooks():
    """
    Process webhooks that needs to be sent to reputation oracle:
      * Retrieves `webhook_url` from KVStore
      * Sends webhook to reputation oracle
    """
    logger = get_function_logger(module_logger)

    try:
        logger.debug("Starting cron job")

        with SessionLocal.begin() as session:
            webhooks = oracle_db_service.outbox.get_pending_webhooks(
                session,
                OracleWebhookTypes.reputation_oracle,
                CronConfig.process_reputation_oracle_webhooks_chunk_size,
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
                    # TODO: restore
                    # service_address = get_reputation_oracle_address()
                    # webhook_url = get_reputation_oracle_url(
                    #     webhook.chain_id, service_address
                    # )
                    # with httpx.Client() as client:
                    #     response = client.post(
                    #         webhook_url, headers=headers, data=serialized_data
                    #     )
                    #     response.raise_for_status()
                    oracle_db_service.outbox.handle_webhook_success(session, webhook.id)
                except Exception as e:
                    logger.exception(f"Webhook {webhook.id} sending failed: {e}")
                    oracle_db_service.outbox.handle_webhook_fail(session, webhook.id)
    except Exception as e:
        logger.exception(e)
    finally:
        logger.debug("Finishing cron job")
