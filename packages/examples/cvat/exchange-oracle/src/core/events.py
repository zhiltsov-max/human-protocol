from typing import Type
from pydantic import BaseModel

from src.core.types import (
    JobLauncherEventType,
    OracleWebhookTypes,
    RecordingOracleEventType,
)


class OracleEvent(BaseModel):
    pass


class JobLauncherEvent_EscrowCreated(OracleEvent):
    pass


class JobLauncherEvent_EscrowCanceled(OracleEvent):
    pass


class RecordingOracleEvent_TaskCompleted(OracleEvent):
    task_id: int


class RecordingOracleEvent_TaskRejected(OracleEvent):
    task_id: int
    rejected_job_ids: list[int]


def get_class_for_event_type(event_type: str) -> Type[OracleEvent]:
    mapping = {
        JobLauncherEventType.escrow_created: JobLauncherEvent_EscrowCreated,
        JobLauncherEventType.escrow_canceled: JobLauncherEvent_EscrowCanceled,
        RecordingOracleEventType.task_completed: RecordingOracleEvent_TaskCompleted,
        RecordingOracleEventType.task_rejected: RecordingOracleEvent_TaskRejected,
    }
    mapping = {str(k): v for k, v in mapping.items()}

    return mapping[event_type]


def parse_event(
    sender: OracleWebhookTypes, event_type: str, event_data: dict
) -> OracleEvent:
    if sender == OracleWebhookTypes.job_launcher:
        if not event_type in JobLauncherEventType:
            raise ValueError(f"Unknown event '{sender}.{event_type}'")
    elif sender == OracleWebhookTypes.recording_oracle:
        if not event_type in RecordingOracleEventType:
            raise ValueError(f"Unknown event '{sender}.{event_type}'")
    else:
        assert False, f"Unknown event sender type '{sender}'"

    event_class = get_class_for_event_type(event_type)
    return event_class.parse_obj(event_data)


def validate_event(sender: OracleWebhookTypes, event_type: str, event_data: dict):
    parse_event(sender=sender, event_type=event_type, event_data=event_data)
