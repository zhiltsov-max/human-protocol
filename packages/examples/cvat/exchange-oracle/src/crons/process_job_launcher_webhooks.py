import logging

from src.db import SessionLocal

from src.core.config import CronConfig
from src.core.types import OracleWebhookTypes, JobLauncherEventType

from src import cvat
from src.chain.escrow import get_escrow_manifest, validate_escrow

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
                    handle_job_launcher_event(webhook)

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


def handle_job_launcher_event(webhook: Webhook):
    assert webhook.type == OracleWebhookTypes.job_launcher

    match webhook.event_type:
        case JobLauncherEventType.escrow_created:
            try:
                # validate_escrow(webhook.chain_id, webhook.escrow_address)

                # TODO: remove mock
                # manifest = get_escrow_manifest(webhook.chain_id, webhook.escrow_address)
                manifest = {
                    "data": {
                        "host_url": "http://DOC-EXAMPLE-BUCKET1.eu.s3.eu-west-1.amazonaws.com",
                        "data_path": "data/dir/",
                    },
                    "task": {"labels": [{"name": "cat"}], "type": "IMAGE_BOXES"},
                    "validation": {
                        "min_quality": 0.9,
                        "gt_path": "path/to/coco_gt.zip",
                    },
                }

                cvat.create_task(webhook.escrow_address, webhook.chain_id, manifest)

            except Exception:
                cvat.remove_task(webhook.escrow_address)
                raise

        case JobLauncherEventType.escrow_canceled:
            raise NotImplementedError

        case _:
            assert False, f"Unknown job launcher event {webhook.event_type}"
