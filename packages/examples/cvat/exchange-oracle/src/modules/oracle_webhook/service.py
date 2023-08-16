import datetime
import uuid
from pydantic import BaseModel

from sqlalchemy import update, case
from sqlalchemy.sql import select
from sqlalchemy.orm import Session
from typing import List, Optional, Type

from src.modules.oracle_webhook.constants import (
    OracleWebhookSenderType,
    OracleWebhookStatuses,
    JobLauncherEventType,
    RecordingOracleEventType,
)
from src.modules.oracle_webhook.model import Webhook

from src.config import Config


def create_webhook(
    session: Session,
    escrow_address: str,
    chain_id: int,
    sender_type: OracleWebhookSenderType,
    sender_signature: str,
    event_type: str,
    event_data: dict,
    s3_url: Optional[str] = None,
) -> int:
    """
    Creates a webhook in a database
    """
    print(parse_event(sender_type, event_type, event_data))
    return

    existing_webhook_query = select(Webhook).where(
        Webhook.signature == sender_signature
    )
    existing_webhook = session.execute(existing_webhook_query).scalars().first()

    if existing_webhook is None:
        webhook_id = str(uuid.uuid4())
        webhook = Webhook(
            id=webhook_id,
            signature=sender_signature,
            escrow_address=escrow_address,
            chain_id=chain_id,
            s3_url=s3_url,
            type=sender_type.value,
            event_type=event_type,
            event_data=event_data,
            status=OracleWebhookStatuses.pending.value,
        )

        session.add(webhook)

        return webhook_id
    return existing_webhook.id


def get_pending_webhooks(
    session: Session, sender_type: OracleWebhookSenderType, limit: int
) -> List[Webhook]:
    webhooks = (
        session.query(Webhook)
        .where(
            Webhook.type == sender_type,
            Webhook.status == OracleWebhookStatuses.pending.value,
            Webhook.wait_until <= datetime.datetime.now(),
        )
        .limit(limit)
        .all()
    )
    return webhooks


def update_webhook_status(
    session: Session, webhook_id: id, status: OracleWebhookStatuses
) -> None:
    if status not in OracleWebhookStatuses.__members__.values():
        raise ValueError(f"{status} is not available")
    upd = update(Webhook).where(Webhook.id == webhook_id).values(status=status)
    session.execute(upd)


def handle_webhook_success(session: Session, webhook_id: id) -> None:
    upd = (
        update(Webhook)
        .where(Webhook.id == webhook_id)
        .values(attempts=Webhook.attempts + 1, status=OracleWebhookStatuses.completed)
    )
    session.execute(upd)


def handle_webhook_fail(session: Session, webhook_id: id) -> None:
    upd = (
        update(Webhook)
        .where(Webhook.id == webhook_id)
        .values(
            attempts=Webhook.attempts + 1,
            status=case(
                (
                    Webhook.attempts + 1 >= Config.webhook_max_retries,
                    OracleWebhookStatuses.failed.value,
                ),
                else_=OracleWebhookStatuses.pending.value,
            ),
            wait_until=Webhook.wait_until
            + datetime.timedelta(minutes=Config.webhook_delay_if_failed),
        )
    )
    session.execute(upd)


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
    sender: OracleWebhookSenderType, event_type: str, event_data: dict
) -> OracleEvent:
    if sender == OracleWebhookSenderType.job_launcher:
        if not event_type in JobLauncherEventType:
            raise ValueError(f"Unknown event '{sender}.{event_type}'")
    elif sender == OracleWebhookSenderType.recording_oracle:
        if not event_type in RecordingOracleEventType:
            raise ValueError(f"Unknown event '{sender}.{event_type}'")
    else:
        assert False, f"Unknown event sender type '{sender}'"

    event_class = get_class_for_event_type(event_type)
    return event_class.parse_obj(event_data)


def validate_event(sender: OracleWebhookSenderType, event_type: str, event_data: dict):
    parse_event(sender=sender, event_type=event_type, event_data=event_data)
