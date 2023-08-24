import logging
from src.core.events import ExchangeOracleEvent_TaskCreationFailed

from src.db import SessionLocal

from src.core.config import CronConfig
from src.core.types import OracleWebhookTypes, JobLauncherEventType

from src import cvat
from src.chain.escrow import validate_escrow

from src.models.webhook import Webhook
import src.services.webhook as db_service


LOG_MODULE = "[cron][webhook][process_job_launcher_webhooks]"


def process_job_launcher_webhooks() -> None:
    """
    Process incoming webhooks in a pending state:
      * Creates a job on CVAT
      * Store necessary information about jobs in a database
    """
    try:
        logger = logging.getLogger("app")
        logger.info(f"{LOG_MODULE} Starting cron job")

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
                    logger.exception(
                        f"Webhook: {webhook.id} failed during execution. Error {e}",
                    )
                    db_service.inbox.handle_webhook_fail(session, webhook.id)

        logger.info(f"{LOG_MODULE} Finishing cron job")
        return None
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
                    f"{LOG_MODULE} Creating a new CVAT project "
                    f"(escrow_address={webhook.escrow_address})"
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
                    f"{LOG_MODULE} Removing a CVAT project "
                    f"(escrow_address={webhook.escrow_address})"
                )

                cvat.remove_task(webhook.escrow_address)

            except Exception as ex:
                raise

        case _:
            assert False, f"Unknown job launcher event {webhook.event_type}"
