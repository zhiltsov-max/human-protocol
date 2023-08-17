import logging

from human_protocol_sdk.storage import Credentials
from human_protocol_sdk.storage import StorageClient
from src.core.events import (
    ExchangeOracleEvent_TaskCreationFailed,
    ExchangeOracleEvent_TaskFinished,
)


from src.db import SessionLocal
from src.core.config import CronConfig, StorageConfig

from src.core.types import (
    ExchangeOracleEventType,
    OracleWebhookTypes,
    ProjectStatuses,
    TaskStatus,
    JobStatuses,
)
from src.handlers.annotation import get_annotations_handler
import src.services.cvat as cvat_db_service
import src.services.webhook as oracle_db_service
import src.cvat.api_calls as cvat_api
from src.utils.helpers import prepare_signature


LOG_MODULE = "[cron][cvat]"
logger = logging.getLogger("app")


def track_completed_projects() -> None:
    """
    Tracks completed projects:
    1. Retrieves projects with "annotation" status
    2. Retrieves tasks related to this project
    3. If all tasks are completed -> updates project status to "completed"
    """
    try:
        logger.info(f"{LOG_MODULE}[track_completed_projects] Starting cron job")
        with SessionLocal.begin() as session:
            # Get active projects from db
            projects = cvat_db_service.get_projects_by_status(
                session,
                ProjectStatuses.annotation,
                limit=CronConfig.track_completed_projects_chunk_size,
            )

            for project in projects:
                tasks = cvat_db_service.get_tasks_by_cvat_project_id(
                    session, project.cvat_id
                )
                if len(tasks) > 0 and all(
                    task.status == TaskStatus.completed for task in tasks
                ):
                    cvat_db_service.update_project_status(
                        session, project.id, ProjectStatuses.completed
                    )

        logger.info(f"{LOG_MODULE}[track_completed_projects] Finishing cron job")

    except Exception as error:
        logger.exception(f"{LOG_MODULE}[track_completed_projects] {error}")


def track_completed_tasks() -> None:
    """
    Tracks completed tasks:
    1. Retrieves tasks with "annotation" status
    2. Retrieves jobs related to this task
    3. If all jobs are completed -> updates task status to "completed"
    """
    try:
        logger.info(f"{LOG_MODULE}[track_completed_tasks] Starting cron job")
        with SessionLocal.begin() as session:
            tasks = cvat_db_service.get_tasks_by_status(
                session,
                TaskStatus.annotation,
            )

            for task in tasks:
                jobs = cvat_db_service.get_jobs_by_cvat_task_id(session, task.cvat_id)
                if len(jobs) > 0 and all(
                    job.status == JobStatuses.completed for job in jobs
                ):
                    cvat_db_service.update_task_status(
                        session, task.id, TaskStatus.completed
                    )

        logger.info(f"{LOG_MODULE}[track_completed_tasks] Finishing cron job")

    except Exception as error:
        logger.exception(f"{LOG_MODULE}[track_completed_tasks] {error}")


def retrieve_annotations() -> None:
    """
    Retrieves and stores completed annotations:
    1. Retrieves annotations from projects with "completed" status
    2. Postprocesses them
    3. Stores annotations in s3 bucket
    4. Prepares a webhook to recording oracle
    """
    try:
        logger.info(f"{LOG_MODULE} Starting cron job")
        with SessionLocal.begin() as session:
            # Get completed projects from db
            projects = cvat_db_service.get_projects_by_status(
                session,
                ProjectStatuses.completed.value,
                limit=CronConfig.retrieve_annotations_chunk_size,
            )

            for project in projects:
                annotations = []
                annotations_handler = get_annotations_handler(project.job_type)
                # Check if all jobs within a project are completed
                if not cvat_db_service.is_project_completed(session, project.id):
                    cvat_db_service.update_project_status(
                        session, project.id, ProjectStatuses.annotation.value
                    )
                    break
                jobs = cvat_db_service.get_jobs_by_cvat_project_id(
                    session, project.cvat_id
                )

                # Collect raw annotations from CVAT and convert them into a recording oracle suitable format
                for job in jobs:
                    raw_annotations = cvat_api.get_job_annotations(job.cvat_id)
                    annotations = annotations_handler(
                        annotations,
                        raw_annotations,
                        project.bucket_url,
                        job.assignee,
                    )

                # Upload file with annotations to s3 storage
                storage_client = StorageClient(
                    StorageConfig.endpoint_url,
                    StorageConfig.region,
                    Credentials(
                        StorageConfig.access_key,
                        StorageConfig.secret_key,
                    ),
                    StorageConfig.secure,
                )
                files = storage_client.upload_files(
                    [annotations], StorageConfig.results_bucket_name
                )

                oracle_db_service.outbox.create_webhook(
                    session,
                    project.escrow_address,
                    project.chain_id,
                    OracleWebhookTypes.recording_oracle.value,
                    event=ExchangeOracleEvent_TaskFinished(
                        s3_url=f"{StorageConfig.bucket_url()}{files[0]['key']}"
                    ),
                )

                cvat_db_service.update_project_status(
                    session, project.id, ProjectStatuses.recorded.value
                )

        logger.info(f"{LOG_MODULE} Finishing cron job")

    except Exception as error:
        logger.exception(f"{LOG_MODULE} {error}")


def track_task_creation() -> None:
    """
    Checks task creation status to report failed tasks.
    """

    # TODO: add load balancing (e.g. round-robin queue)

    logger_prefix = f"{LOG_MODULE}[track_creating_tasks]"

    try:
        logger.info(f"{logger_prefix} Starting cron job")

        with SessionLocal.begin() as session:
            # Get active projects from db
            uploads = cvat_db_service.get_active_task_uploads(
                session,
                limit=CronConfig.track_creating_tasks_chunk_size,
            )

            completed = []
            failed = []
            for upload in uploads:
                status = cvat_api.get_task_upload_status(upload.task_id)
                if not status or status == cvat_api.UploadStatus.FAILED:
                    failed.append(upload)

                    project = upload.task.project

                    oracle_db_service.outbox.create_webhook(
                        session,
                        escrow_address=project.escrow_address,
                        chain_id=project.chain_id,
                        type=OracleWebhookTypes.job_launcher,
                        event=ExchangeOracleEvent_TaskCreationFailed(
                            reason=""  # TODO: add error details
                        ),
                    )
                elif status == cvat_api.UploadStatus.FINISHED:
                    completed.append(upload)

            cvat_db_service.finish_uploads(session, completed + failed)

        logger.info(f"{logger_prefix} Finishing cron job")

    except Exception as error:
        logger.exception(f"{logger_prefix} {error}")
