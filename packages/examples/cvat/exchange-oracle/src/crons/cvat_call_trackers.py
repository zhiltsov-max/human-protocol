from typing import List

from src.core.oracle_events import (
    ExchangeOracleEvent_TaskCreationFailed,
    ExchangeOracleEvent_TaskFinished,
)


from src.db import SessionLocal
from src.core.config import CronConfig, StorageConfig

from src.core.types import (
    OracleWebhookTypes,
    ProjectStatuses,
    TaskStatus,
    JobStatuses,
)
from src.handlers.annotation import prepare_annotation_metafile, FileDescriptor
from src.log import get_root_logger
import src.services.cvat as cvat_service
import src.services.webhook as oracle_db_service
import src.services.cloud.client as cloud_client
import src.cvat.api_calls as cvat_api
from src.cvat.tasks import cvat_dataset_export_format_mapping
from src.utils.helpers import compose_output_annotation_filename
from src.utils.logging import get_function_logger


LOG_MODULE = "cron.cvat"
module_logger = get_root_logger().getChild(LOG_MODULE)


def track_completed_projects() -> None:
    """
    Tracks completed projects:
    1. Retrieves projects with "annotation" status
    2. Retrieves tasks related to this project
    3. If all tasks are completed -> updates project status to "completed"
    """
    logger = get_function_logger(module_logger)

    try:
        logger.info("Starting cron job")
        with SessionLocal.begin() as session:
            # Get active projects from db
            projects = cvat_service.get_projects_by_status(
                session,
                ProjectStatuses.annotation,
                limit=CronConfig.track_completed_projects_chunk_size,
            )

            for project in projects:
                tasks = cvat_service.get_tasks_by_cvat_project_id(
                    session, project.cvat_id
                )
                if len(tasks) > 0 and all(
                    task.status == TaskStatus.completed for task in tasks
                ):
                    cvat_service.update_project_status(
                        session, project.id, ProjectStatuses.completed
                    )

        logger.info("Finishing cron job")

    except Exception as error:
        logger.exception(error)


def track_completed_tasks() -> None:
    """
    Tracks completed tasks:
    1. Retrieves tasks with "annotation" status
    2. Retrieves jobs related to this task
    3. If all jobs are completed -> updates task status to "completed"
    """
    logger = get_function_logger(module_logger)

    try:
        logger.info("Starting cron job")
        with SessionLocal.begin() as session:
            tasks = cvat_service.get_tasks_by_status(
                session,
                TaskStatus.annotation,
            )

            for task in tasks:
                jobs = cvat_service.get_jobs_by_cvat_task_id(session, task.cvat_id)
                if len(jobs) > 0 and all(
                    job.status == JobStatuses.completed for job in jobs
                ):
                    cvat_service.update_task_status(
                        session, task.id, TaskStatus.completed
                    )

        logger.info("Finishing cron job")

    except Exception as error:
        logger.exception(error)


def track_assignments() -> None:
    """
    Tracks assignments:
    1. Checks time for each active assignment
    2. If an assignment is timed out, expires it
    3. If a project or task state is not "annotation", cancels assignments
    """
    logger = get_function_logger(module_logger)

    try:
        logger.info("Starting cron job")

        with SessionLocal.begin() as session:
            assignments = cvat_service.get_unprocessed_expired_assignments(
                session, limit=CronConfig.track_assignments_chunk_size
            )

            for assignment in assignments:
                logger.info(
                    "Expiring the unfinished assignment {} (user {}, job id {})".format(
                        assignment.id,
                        assignment.user_wallet_id,
                        assignment.cvat_job_id,
                    )
                )

                latest_assignment = cvat_service.get_latest_assignment_by_cvat_job_id(
                    session, assignment.cvat_job_id
                )
                if latest_assignment.id == assignment.id:
                    # Avoid un-assigning if it's not the latest assignment

                    cvat_api.update_job_assignee(
                        assignment.cvat_job_id, assignee_id=None
                    )  # note that calling it in a loop can take too much time

                cvat_service.expire_assignment(session, assignment.id)

        with SessionLocal.begin() as session:
            assignments = cvat_service.get_active_assignments(
                session, limit=CronConfig.track_assignments_chunk_size
            )

            for assignment in assignments:
                if assignment.job.project.status != ProjectStatuses.annotation:
                    logger.warning(
                        "Canceling the unfinished assignment {} (user {}, job id {}) - "
                        "the project state is not annotation".format(
                            assignment.id,
                            assignment.user_wallet_id,
                            assignment.cvat_job_id,
                        )
                    )

                    latest_assignment = (
                        cvat_service.get_latest_assignment_by_cvat_job_id(
                            session, assignment.cvat_job_id
                        )
                    )
                    if latest_assignment.id == assignment.id:
                        # Avoid un-assigning if it's not the latest assignment

                        cvat_api.update_job_assignee(
                            assignment.cvat_job_id, assignee_id=None
                        )  # note that calling it in a loop can take too much time

                    cvat_service.cancel_assignment(session, assignment.id)

        logger.info("Finishing cron job")

    except Exception as error:
        logger.exception(error)


def retrieve_annotations() -> None:
    """
    Retrieves and stores completed annotations:
    1. Retrieves annotations from projects with "completed" status
    2. Postprocesses them
    3. Stores annotations in s3 bucket
    4. Prepares a webhook to recording oracle
    """
    logger = get_function_logger(module_logger)

    try:
        logger.info("Starting cron job")
        with SessionLocal.begin() as session:
            # Get completed projects from db
            projects = cvat_service.get_projects_by_status(
                session,
                ProjectStatuses.completed.value,
                limit=CronConfig.retrieve_annotations_chunk_size,
            )

            for project in projects:
                # Check if all jobs within the project are completed
                if not cvat_service.is_project_completed(session, project.id):
                    cvat_service.update_project_status(
                        session, project.id, ProjectStatuses.annotation.value
                    )
                    continue

                # TODO: add handlers for other task types?
                # raw_annotations_handler = get_raw_annotations_handler(project.job_type)

                jobs = cvat_service.get_jobs_by_cvat_project_id(
                    session, project.cvat_id
                )

                annotation_format = cvat_dataset_export_format_mapping[project.job_type]
                annotation_files: List[FileDescriptor] = []

                # Collect raw annotations from CVAT, validate and convert them
                # into a recording oracle suitable format
                for job in jobs:
                    job_annotations_file = cvat_api.get_job_annotations(
                        job.cvat_id, format_name=annotation_format
                    )
                    annotation_files.append(
                        FileDescriptor(
                            filename="project_{}-task_{}-job_{}.zip".format(
                                project.cvat_id, job.cvat_task_id, job.cvat_id
                            ),
                            file=job_annotations_file,
                        )
                    )

                project_annotations_file = cvat_api.get_project_annotations(
                    project.cvat_id, format_name=annotation_format
                )
                annotation_files.append(
                    FileDescriptor(
                        filename=f"project_{project.cvat_id}.zip",
                        file=project_annotations_file,
                    )
                )

                annotation_metafile = prepare_annotation_metafile(jobs=jobs)
                annotation_files.append(annotation_metafile)

                # TODO: can switch to StorageClient once binary files are supported
                # Upload file with annotations to s3 storage
                # storage_client = StorageClient(
                #     StorageConfig.endpoint_url,
                #     StorageConfig.region,
                #     Credentials(
                #         StorageConfig.access_key,
                #         StorageConfig.secret_key,
                #     ),
                #     StorageConfig.secure,
                # )
                # files = storage_client.upload_files(
                #     annotation_files, StorageConfig.results_bucket_name
                # )

                storage_client = cloud_client.S3Client(
                    StorageConfig.endpoint_url,
                    access_key=StorageConfig.access_key,
                    secret_key=StorageConfig.secret_key,
                )
                for file_descriptor in annotation_files:
                    try:
                        storage_client.create_file(
                            StorageConfig.results_bucket_name,
                            compose_output_annotation_filename(
                                project.escrow_address,
                                project.chain_id,
                                file_descriptor.filename,
                            ),
                            file_descriptor.file.read(),
                        )
                    except Exception as e:
                        # if already_exist: skip
                        raise

                oracle_db_service.outbox.create_webhook(
                    session,
                    project.escrow_address,
                    project.chain_id,
                    OracleWebhookTypes.recording_oracle,
                    event=ExchangeOracleEvent_TaskFinished(),
                )

                cvat_service.update_project_status(
                    session, project.id, ProjectStatuses.validation
                )

        logger.info("Finishing cron job")

    except Exception as error:
        logger.exception(error)


def track_task_creation() -> None:
    """
    Checks task creation status to report failed tasks and continue task creation process.
    """

    # TODO: maybe add load balancing (e.g. round-robin queue, shuffling)

    logger = get_function_logger(module_logger)

    try:
        logger.info("Starting cron job")

        with SessionLocal.begin() as session:
            # Get active projects from db
            uploads = cvat_service.get_active_task_uploads(
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

            cvat_service.finish_uploads(session, failed + completed)

        logger.info("Finishing cron job")

    except Exception as error:
        logger.exception(error)
