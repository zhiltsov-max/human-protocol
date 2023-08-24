# pylint: disable=too-few-public-methods
from __future__ import annotations

from typing import List
from sqlalchemy import Column, String, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.orm import relationship, Mapped
from sqlalchemy.sql import func

from src.core.types import ProjectStatuses, TaskStatus, JobStatuses, TaskType, Networks
from src.db import Base


class Project(Base):
    __tablename__ = "projects"
    id = Column(String, primary_key=True, index=True)
    cvat_id = Column(Integer, unique=True, index=True, nullable=False)
    cvat_cloudstorage_id = Column(Integer, index=True, nullable=False)
    status = Column(String, Enum(ProjectStatuses), nullable=False)
    job_type = Column(String, Enum(TaskType), nullable=False)
    escrow_address = Column(String(42), unique=True, nullable=False)
    chain_id = Column(Integer, Enum(Networks), nullable=False)
    bucket_url = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_processed_webhook_delivery_id = Column(Integer, nullable=True)

    tasks: Mapped[List["Task"]] = relationship(
        back_populates="project",
        cascade="all, delete",
        passive_deletes=True,
    )

    jobs: Mapped[List["Job"]] = relationship(
        back_populates="project",
        cascade="all, delete",
        passive_deletes=True,
    )

    def __repr__(self):
        return f"Project. id={self.id}"


class Task(Base):
    __tablename__ = "tasks"
    id = Column(String, primary_key=True, index=True)
    cvat_id = Column(Integer, unique=True, index=True, nullable=False)
    cvat_project_id = Column(
        Integer, ForeignKey("projects.cvat_id", ondelete="CASCADE"), nullable=False
    )
    status = Column(String, Enum(TaskStatus), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    project: Mapped["Project"] = relationship(back_populates="tasks")
    jobs: Mapped[List["Job"]] = relationship(
        back_populates="task",
        cascade="all, delete",
        passive_deletes=True,
    )
    data_upload: Mapped["DataUpload"] = relationship(
        back_populates="task", cascade="all, delete", passive_deletes=True
    )

    def __repr__(self):
        return f"Task. id={self.id}"


class DataUpload(Base):
    __tablename__ = "data_uploads"
    id = Column(String, primary_key=True, index=True)
    task_id = Column(
        Integer,
        ForeignKey("tasks.cvat_id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )

    task: Mapped["Task"] = relationship(back_populates="data_upload")

    def __repr__(self):
        return f"DataUpload. id={self.id} task={self.task_id}"


class Job(Base):
    __tablename__ = "jobs"
    id = Column(String, primary_key=True, index=True)
    cvat_id = Column(Integer, unique=True, index=True, nullable=False)
    cvat_task_id = Column(
        Integer, ForeignKey("tasks.cvat_id", ondelete="CASCADE"), nullable=False
    )
    cvat_project_id = Column(
        Integer, ForeignKey("projects.cvat_id", ondelete="CASCADE"), nullable=False
    )
    status = Column(String, Enum(JobStatuses), nullable=False)
    assignee = Column(String(42), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    task: Mapped["Task"] = relationship(back_populates="jobs")
    project: Mapped["Project"] = relationship(back_populates="jobs")

    def __repr__(self):
        return f"Job. id={self.id}"
