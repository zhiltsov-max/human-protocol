from typing import List
from dateutil.parser import parse as parse_aware_datetime
from src.db import SessionLocal
from src.core.types import AssignmentStatus, CvatEventTypes, JobStatuses
from src.log import get_root_logger

import src.models.cvat as models
import src.services.cvat as cvat_service
import src.cvat.api_calls as cvat_api
from src.utils.logging import get_function_logger


def handle_update_job_event(payload: dict) -> None:
    logger = get_function_logger(get_root_logger().getChild("handler"))

    with SessionLocal.begin() as session:
        job = cvat_service.get_job_by_cvat_id(session, payload.job["id"])
        if not job:
            return

        if "state" in payload.before_update:
            job_assignments = job.assignments

            if not job_assignments:
                logger.warning(
                    f"Received job #{job.cvat_id} status update: {new_status.value}. "
                    "No assignments for this job, ignoring the update"
                )
            else:
                new_status = JobStatuses(payload.job["state"])
                webhook_time = parse_aware_datetime(payload.job["updated_date"])
                webhook_assignee_id = (payload.job["assignee"] or {}).get("id")

                job_assignments: List[models.Assignment] = sorted(
                    job_assignments, key=lambda a: a.created_at, reverse=True
                )
                latest_assignment = job.assignments[0]
                matching_assignment = next(
                    (
                        a
                        for a in job_assignments
                        if a.user.cvat_id == webhook_assignee_id
                        if a.created_at < webhook_time
                    ),
                    None,
                )

                if not matching_assignment:
                    logger.warning(
                        f"Received job #{job.cvat_id} status update: {new_status.value}. "
                        "Can't find a matching assignment, ignoring the update"
                    )
                elif matching_assignment.is_finished:
                    if matching_assignment.status == AssignmentStatus.created:
                        logger.warning(
                            f"Received job #{job.cvat_id} status update: {new_status.value}. "
                            "Assignment is expired, rejecting the update"
                        )
                        cvat_service.expire_assignment(session, matching_assignment)

                        if matching_assignment.id == latest_assignment.id:
                            cvat_api.update_job_assignee(job.cvat_id, assignee_id=None)

                    else:
                        logger.info(
                            f"Received job #{job.cvat_id} status update: {new_status.value}. "
                            "Assignment is already finished, ignoring the update"
                        )
                elif (
                    new_status == JobStatuses.completed
                    and matching_assignment.id == latest_assignment.id
                    and matching_assignment.status == AssignmentStatus.created
                ):
                    logger.info(
                        f"Received job #{job.cvat_id} status update: {new_status.value}. "
                        "Completing the assignment"
                    )
                    cvat_service.complete_assignment(
                        session, matching_assignment.id, completed_at=webhook_time
                    )
                    cvat_service.update_job_status(session, job.id, new_status)

                    cvat_api.update_job_assignee(job.cvat_id, assignee_id=None)

                else:
                    logger.info(
                        f"Received job #{job.cvat_id} status update: {new_status.value}. "
                        "Ignoring the update"
                    )


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
