import logging
from src.db import SessionLocal
from src.core.types import CvatEventTypes, JobStatuses

import src.services.cvat as cvat_service
import src.cvat.api_calls as cvat_api
from src.utils.helpers import utcnow


def handle_update_job_event(payload: dict) -> None:
    logger = logging.getLogger(
        __package__ + "." + __name__ + ".handle_update_job_event"
    )

    with SessionLocal.begin() as session:
        job = cvat_service.get_job_by_cvat_id(session, payload.job["id"])
        if not job:
            return

        if "state" in payload.before_update:
            new_status = JobStatuses[payload.job["state"]]

            if job.assignment and new_status == JobStatuses.completed:
                if job.assignment.is_finished:
                    if not job.assignment.finished_at:
                        logger.warning(
                            f"Received job #{job.cvat_id} status update: {new_status.value}. "
                            "Assignment is expired, discarding the update"
                        )
                        cvat_service.expire_assignment(session, job.assignment.id)

                        if payload.job["assignee"]["id"] == job.assignment.user.cvat_id:
                            cvat_api.update_job_assignee(job.cvat_id, assignee_id=None)

                    else:
                        logger.info(
                            f"Received job #{job.cvat_id} status update: {new_status.value}. "
                            "Assignment is already finished, ignoring the update"
                        )

                elif payload.job["assignee"]["id"] != job.assignment.user.cvat_id:
                    logger.warning(
                        f"Received job #{job.cvat_id} status update: {new_status.value}. "
                        f"CVAT assignee ({payload.job['assignee']['id']}) mismatches "
                        f"the assigned user ({job.assignment.user.cvat_id}), "
                        "ignoring the update, discarding the assignment"
                    )
                    cvat_service.delete_assignment(session, job.assignment.id)

                else:
                    logger.info(
                        f"Received job #{job.cvat_id} status update: {new_status.value}. "
                        "Completing the assignment"
                    )
                    cvat_service.complete_assignment(
                        session, job.assignment.id, finished_at=utcnow()
                    )
                    cvat_service.update_job_status(session, job.id, new_status)

                    if payload.job["assignee"]["id"] == job.assignment.user.cvat_id:
                        cvat_api.update_job_assignee(job.cvat_id, assignee_id=None)
            elif not job.assignment and payload.job["assignee"]["id"]:
                cvat_api.update_job_assignee(job.cvat_id, assignee_id=None)


def handle_create_job_event(payload: dict) -> None:
    with SessionLocal.begin() as session:
        job = cvat_service.get_job_by_cvat_id(session, payload.job["id"])

        if not job:
            cvat_service.create_job(
                session,
                payload.job["id"],
                payload.job["task_id"],
                payload.job["project_id"],
                status=JobStatuses[payload.job["state"]],
            )


def cvat_webhook_handler(cvat_webhook: dict) -> None:
    match cvat_webhook.event:
        case CvatEventTypes.update_job.value:
            handle_update_job_event(cvat_webhook)
        case CvatEventTypes.create_job.value:
            handle_create_job_event(cvat_webhook)
        case CvatEventTypes.ping.value:
            pass
