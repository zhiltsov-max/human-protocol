import uuid

from sqlalchemy import ColumnExpressionArgument, delete, update
from sqlalchemy.sql import select
from sqlalchemy.orm import Session

from typing import List, Optional


from src.core.types import ProjectStatuses, TaskStatus, JobStatuses
from src.models.cvat import DataUpload, Project, Task, Job


# Project
def create_project(
    session: Session,
    cvat_id: int,
    cvat_cloudstorage_id: int,
    job_type: str,
    escrow_address: str,
    chain_id: int,
    bucket_url: str,
) -> int:
    """
    Create a project from CVAT.
    """
    project_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        cvat_id=cvat_id,
        cvat_cloudstorage_id=cvat_cloudstorage_id,
        status=ProjectStatuses.annotation.value,
        job_type=job_type,
        escrow_address=escrow_address,
        chain_id=chain_id,
        bucket_url=bucket_url,
    )

    session.add(project)

    return project_id


def get_project_by_id(session: Session, project_id: int) -> Project:
    project_query = select(Project).where(Project.id == project_id)
    project = session.execute(project_query).scalars().first()

    return project


def get_project_by_escrow_address(session: Session, escrow_address: str) -> Project:
    project_query = select(Project).where(Project.escrow_address == escrow_address)
    project = session.execute(project_query).scalars().first()

    return project


def get_projects_by_status(
    session: Session, status: ProjectStatuses, limit: int = 5
) -> List[Project]:
    projects = (
        session.query(Project)
        .where(
            Project.status == status,
        )
        .limit(limit)
        .all()
    )
    return projects


def get_available_projects(
    session: Session, username: Optional[str] = None, limit: int = 10
) -> List[Project]:
    def _maybe_assigned_to_the_user(
        expr: ColumnExpressionArgument,
    ) -> ColumnExpressionArgument:
        if username:
            return expr | Project.jobs.any(Job.assignee == username)
        return expr

    return (
        session.query(Project)
        .where(
            _maybe_assigned_to_the_user(
                (Project.status == ProjectStatuses.annotation.value)
                & Project.jobs.any(Job.assignee == "")
            )
        )
        .distinct()
        .limit(limit)
        .all()
    )


def update_project_status(
    session: Session, project_id: int, status: ProjectStatuses
) -> None:
    if status not in ProjectStatuses:
        raise ValueError(f"{status} is not available")
    upd = update(Project).where(Project.id == project_id).values(status=status.value)
    session.execute(upd)


def delete_project(session: Session, project_id: int) -> None:
    project = session.query(Project).filter_by(id=project_id).first()
    session.delete(project)


def is_project_completed(session: Session, project_id: int) -> bool:
    project = get_project_by_id(session, project_id)
    jobs = get_jobs_by_cvat_project_id(session, project.cvat_id)
    if len(jobs) > 0 and all(job.status == JobStatuses.completed.value for job in jobs):
        return True
    else:
        return False


# Task
def create_task(
    session: Session, cvat_id: int, cvat_project_id: int, status: TaskStatus
) -> int:
    """
    Create a task from CVAT.
    """
    task_id = str(uuid.uuid4())
    task = Task(
        id=task_id,
        cvat_id=cvat_id,
        cvat_project_id=cvat_project_id,
        status=status.value,
    )

    session.add(task)

    return task_id


def get_task_by_id(session: Session, task_id: int) -> Task:
    task_query = select(Task).where(Task.id == task_id)
    task = session.execute(task_query).scalars().first()

    return task


def get_tasks_by_status(session: Session, status: TaskStatus) -> List[Task]:
    tasks = (
        session.query(Task)
        .where(
            Task.status == status.value,
        )
        .all()
    )
    return tasks


def update_task_status(session: Session, task_id: int, status: TaskStatus) -> None:
    if status not in TaskStatus:
        raise ValueError(f"{status} is not available")
    upd = update(Task).where(Task.id == task_id).values(status=status.values)
    session.execute(upd)


def get_tasks_by_cvat_project_id(session: Session, cvat_project_id: int) -> List[Task]:
    tasks = (
        session.query(Task)
        .where(
            Task.cvat_project_id == cvat_project_id,
        )
        .all()
    )
    return tasks


def create_data_upload(
    session: Session,
    cvat_task_id: int,
):
    upload_id = str(uuid.uuid4())
    upload = DataUpload(
        id=upload_id,
        task_id=cvat_task_id,
    )

    session.add(upload)

    return upload_id


def get_active_task_uploads_by_task_id(
    session: Session, task_ids: List[int]
) -> List[DataUpload]:
    return session.query(DataUpload).where(DataUpload.task_id.in_(task_ids)).all()


def get_active_task_uploads(session: Session, limit: int) -> List[DataUpload]:
    return session.query(DataUpload).limit(limit).all()


def finish_uploads(session: Session, uploads: list[DataUpload]) -> None:
    statement = delete(DataUpload).where(
        DataUpload.id.in_([upload.id for upload in uploads])
    )
    session.execute(statement)


# Job
def create_job(
    session: Session,
    cvat_id: int,
    cvat_task_id: int,
    cvat_project_id: int,
    assignee: str = "",
    status: JobStatuses = JobStatuses.new,
) -> int:
    """
    Create a job from CVAT.
    """
    job_id = str(uuid.uuid4())
    job = Job(
        id=job_id,
        cvat_id=cvat_id,
        cvat_task_id=cvat_task_id,
        cvat_project_id=cvat_project_id,
        status=status.value,
        assignee=assignee,
    )

    session.add(job)

    return job_id


def get_job_by_id(session: Session, job_id: int) -> Job:
    job_query = select(Job).where(Job.id == job_id)
    job = session.execute(job_query).scalars().first()

    return job


def get_job_by_cvat_id(session: Session, cvat_id: int) -> Job:
    job_query = select(Job).where(Job.cvat_id == cvat_id)
    job = session.execute(job_query).scalars().first()

    return job


def update_job_assignee(session: Session, job_id: int, assignee: str) -> None:
    upd = update(Job).where(Job.id == job_id).values(assignee=assignee)
    session.execute(upd)


def update_job_status(session: Session, job_id: int, status: JobStatuses) -> None:
    if status not in JobStatuses:
        raise ValueError(f"{status} is not available")
    upd = update(Job).where(Job.id == job_id).values(status=status.value)
    session.execute(upd)


def get_jobs_by_cvat_task_id(session: Session, cvat_task_id: int) -> List[Job]:
    jobs = (
        session.query(Job)
        .where(
            Job.cvat_task_id == cvat_task_id,
        )
        .all()
    )
    return jobs


def get_jobs_by_cvat_project_id(session: Session, cvat_project_id: int) -> List[Job]:
    jobs = (
        session.query(Job)
        .where(
            Job.cvat_project_id == cvat_project_id,
        )
        .all()
    )
    return jobs
