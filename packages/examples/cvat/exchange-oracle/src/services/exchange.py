from datetime import timedelta
from typing import Optional
from src.db import SessionLocal

from src.core.types import JobStatuses, PlatformType, ProjectStatuses
from src.schemas import exchange as service_api
import src.models.cvat as models
import src.cvat.api_calls as cvat_api
import src.services.cvat as cvat_service

from src.chain.escrow import get_escrow_manifest
from src.utils.helpers import parse_manifest, utcnow, compose_assignment_url
from src.utils.requests import get_or_404


def serialize_task(
    project_id: str, *, assignment_id: Optional[str] = None
) -> service_api.TaskResponse:
    with SessionLocal.begin() as session:
        project = cvat_service.get_project_by_id(session, project_id)

        assignment = None
        if assignment_id:
            assignment = cvat_service.get_assignments_by_id(session, [assignment_id])[0]

        manifest = parse_manifest(
            get_escrow_manifest(project.chain_id, project.escrow_address)
        )

        serialized_assignment = None
        if assignment:
            serialized_assignment = service_api.AssignmentResponse(
                assignment_url=compose_assignment_url(
                    task_id=assignment.job.cvat_task_id, job_id=assignment.cvat_job_id
                ),
                started_at=assignment.created_at,
                finishes_at=assignment.closes_at,
            )

        return service_api.TaskResponse(
            id=project.id,
            escrow_address=project.escrow_address,
            title=f"Task {project.escrow_address[:10]}",
            description=manifest.annotation.description,
            job_bounty=manifest.job_bounty,
            job_time_limit=manifest.annotation.max_time,
            job_size=manifest.annotation.job_size + manifest.validation.val_size,
            job_type=project.job_type,
            platform=PlatformType.CVAT,
            assignment=serialized_assignment,
        )


def get_available_tasks(
    wallet_id: Optional[str] = None,
) -> list[service_api.TaskResponse]:
    results = []

    with SessionLocal.begin() as session:
        cvat_projects = cvat_service.get_available_projects(
            session, wallet_id=wallet_id
        )
        user_assignments = {
            assignment.job.project.id: assignment
            for assignment in cvat_service.get_user_assignments_in_cvat_projects(
                session,
                wallet_id=wallet_id,
                cvat_projects=[p.cvat_id for p in cvat_projects],
            )
        }

        for project in cvat_projects:
            assignment = user_assignments.get(project.id)
            results.append(
                serialize_task(
                    project.id, assignment_id=assignment.id if assignment else None
                )
            )

    return results


def create_assignment(project_id: int, wallet_id: str) -> Optional[str]:
    with SessionLocal.begin() as session:
        user = get_or_404(
            cvat_service.get_user_by_id(session, wallet_id), wallet_id, "user"
        )
        project = get_or_404(
            cvat_service.get_project_by_id(session, project_id), project_id, "task"
        )

        if project.status != ProjectStatuses.annotation:
            return None

        manifest = parse_manifest(
            get_escrow_manifest(project.chain_id, project.escrow_address)
        )

        project_jobs = project.jobs
        unassigned_job: Optional[models.Job] = None
        unfinished_assignments: list[models.Assignment] = []
        for job in project_jobs:
            if job.assignment and not job.assignment.is_finished:
                unfinished_assignments.append(job.assignment)

            if (
                not unassigned_job
                and job.status == JobStatuses.new
                and (not job.assignment or not job.assignment.is_finished)
            ):
                unassigned_job = job

        now = utcnow()
        unfinished_user_assignments = [
            assignment
            for assignment in unfinished_assignments
            if assignment.user_wallet_id == wallet_id and now < assignment.closes_at
        ]
        if unfinished_user_assignments:
            raise Exception(
                "The user already has an unfinished assignment in this project"
            )

        if not unassigned_job:
            return None

        assignment_id = cvat_service.create_assignment(
            session,
            wallet_id=user.wallet_id,
            cvat_job_id=unassigned_job.cvat_id,
            closes_at=now + timedelta(seconds=manifest.annotation.max_time),
        )

        cvat_api.clear_job_annotations(unassigned_job.cvat_id)
        cvat_api.restart_job(unassigned_job.cvat_id)
        cvat_api.update_job_assignee(
            id=unassigned_job.cvat_id, assignee_id=user.cvat_id
        )
        # rollback is automatic within the transaction

    return assignment_id
