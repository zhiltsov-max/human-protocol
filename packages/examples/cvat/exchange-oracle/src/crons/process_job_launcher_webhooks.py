import logging
from src.core.oracle_events import ExchangeOracleEvent_TaskCreationFailed

from src.db import SessionLocal

from src.core.config import CronConfig
from src.core.types import OracleWebhookTypes, JobLauncherEventType

from src.chain.escrow import validate_escrow
import src.cvat.tasks as cvat
from src.log import get_root_logger

from src.models.webhook import Webhook
import src.services.webhook as db_service
from src.utils.logging import get_function_logger


LOG_MODULE = "cron.webhook"
module_logger = get_root_logger().getChild(LOG_MODULE)


def process_job_launcher_webhooks():
    """
    Process incoming oracle webhooks
    """
    logger = get_function_logger(module_logger)

    try:
        logger.info("Starting cron job")

        with SessionLocal.begin() as session:
            webhooks = db_service.inbox.get_pending_webhooks(
                session,
                OracleWebhookTypes.job_launcher,
                CronConfig.process_job_launcher_webhooks_chunk_size,
            )

            for webhook in webhooks:
                try:
                    handle_job_launcher_event(
                        webhook, db_session=session, logger=logger
                    )

                    db_service.inbox.handle_webhook_success(session, webhook.id)
                except Exception as e:
                    logger.exception(f"Webhook {webhook.id} handling failed: {e}")
                    db_service.inbox.handle_webhook_fail(session, webhook.id)

        logger.info("Finishing cron job")
    except Exception as e:
        logger.exception(e)


def handle_job_launcher_event(
    webhook: Webhook, *, db_session: SessionLocal, logger: logging.Logger
):
    assert webhook.type == OracleWebhookTypes.job_launcher

    match webhook.event_type:
        case JobLauncherEventType.escrow_created:
            try:
                # TODO: enable validation
                # validate_escrow(webhook.chain_id, webhook.escrow_address)

                logger.info(
                    f"Creating a new CVAT project (escrow_address={webhook.escrow_address})"
                )

                cvat.create_task(webhook.escrow_address, webhook.chain_id)

            except Exception as ex:
                try:
                    cvat.remove_task(webhook.escrow_address)
                except Exception as ex_remove:
                    logger.exception(ex_remove)

                db_service.outbox.create_webhook(
                    session=db_session,
                    escrow_address=webhook.escrow_address,
                    chain_id=webhook.chain_id,
                    type=OracleWebhookTypes.exchange_oracle,
                    event=ExchangeOracleEvent_TaskCreationFailed(reason=str(ex)),
                )

                raise

        case JobLauncherEventType.escrow_canceled:
            try:
                # TODO: enable validation
                # validate_escrow(webhook.chain_id, webhook.escrow_address)

                logger.info(
                    f"Removing a CVAT project (escrow_address={webhook.escrow_address})"
                )

                cvat.remove_task(webhook.escrow_address)

            except Exception as ex:
                raise

        case _:
            assert False, f"Unknown job launcher event {webhook.event_type}"
