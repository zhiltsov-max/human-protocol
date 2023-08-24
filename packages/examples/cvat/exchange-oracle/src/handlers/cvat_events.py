from src.db import SessionLocal
from src.core.types import CvatEventTypes, JobStatuses

import src.services.cvat as cvat_service


def handle_update_job_event(payload: dict) -> None:
    with SessionLocal.begin() as session:
        job = cvat_service.get_job_by_cvat_id(session, payload.job["id"])
        if not job:
            cvat_service.create_job(
                session,
                payload.job["id"],
                payload.job["task_id"],
                payload.job["project_id"],
                assignee=payload.job["assignee"]["username"]
                if payload.job["assignee"]
                else "",
                status=JobStatuses[payload.job["state"]],
            )
        else:
            if "assignee" in payload.before_update:
                assignee = (
                    payload.job["assignee"]["username"]
                    if payload.job["assignee"]
                    else ""
                )
                cvat_service.update_job_assignee(session, job.id, assignee)
            if "state" in payload.before_update:
                cvat_service.update_job_status(
                    session, job.id, JobStatuses[payload.job["state"]]
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
                assignee=payload.job["assignee"]["username"]
                if payload.job["assignee"]
                else "",
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
