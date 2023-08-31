import datetime
from enum import Enum
import uuid
from attrs import define

from sqlalchemy import update, case
from sqlalchemy.sql import select
from sqlalchemy.orm import Session
from typing import List, Optional

from src.core.oracle_events import OracleEvent, validate_event
from src.core.types import (
    OracleWebhookTypes,
    OracleWebhookStatuses,
)
from src.models import Webhook

from src.core.config import Config
from src.utils.enums import BetterEnumMeta


class OracleWebhookDirectionTag(str, Enum, metaclass=BetterEnumMeta):
    incoming = "incoming"
    outgoing = "outgoing"


@define
class OracleWebhookQueue:
    direction: OracleWebhookDirectionTag

    def create_webhook(
        self,
        session: Session,
        escrow_address: str,
        chain_id: int,
        type: OracleWebhookTypes,
        signature: Optional[str] = None,
        event_type: Optional[str] = None,
        event_data: Optional[dict] = None,
        event: Optional[OracleEvent] = None,
    ) -> int:
        """
        Creates a webhook in a database
        """
        assert not event_data or event_type, "'event_data' requires 'event_type'"
        assert bool(event) ^ bool(
            event_type
        ), f"'event' and 'event_type' cannot be used together. Please use only one of the fields"

        if event_type:
            if self.direction == OracleWebhookDirectionTag.incoming:
                sender = type
            else:
                sender = OracleWebhookTypes.recording_oracle
            validate_event(sender, event_type, event_data)
        elif event:
            event_type = event.get_type()
            event_data = event.dict()

        if self.direction == OracleWebhookDirectionTag.incoming and not signature:
            raise ValueError("Webhook signature must be specified for incoming events")

        existing_webhook_query = select(Webhook).where(Webhook.signature == signature)
        existing_webhook = session.execute(existing_webhook_query).scalars().first()

        if existing_webhook is None:
            webhook_id = str(uuid.uuid4())
            webhook = Webhook(
                id=webhook_id,
                signature=signature,
                escrow_address=escrow_address,
                chain_id=chain_id,
                type=type.value,
                event_type=event_type,
                event_data=event_data,
                direction=self.direction.value,
            )

            session.add(webhook)

            return webhook_id
        return existing_webhook.id

    def get_pending_webhooks(
        self, session: Session, sender_type: OracleWebhookTypes, limit: int
    ) -> List[Webhook]:
        webhooks = (
            session.query(Webhook)
            .where(
                Webhook.direction == self.direction.value,
                Webhook.type == sender_type.value,
                Webhook.status == OracleWebhookStatuses.pending.value,
                Webhook.wait_until <= datetime.datetime.now(),
            )
            .limit(limit)
            .all()
        )
        return webhooks

    def update_webhook_status(
        self, session: Session, webhook_id: int, status: OracleWebhookStatuses
    ) -> None:
        upd = (
            update(Webhook).where(Webhook.id == webhook_id).values(status=status.value)
        )
        session.execute(upd)

    def handle_webhook_success(self, session: Session, webhook_id: int) -> None:
        upd = (
            update(Webhook)
            .where(Webhook.id == webhook_id)
            .values(
                attempts=Webhook.attempts + 1, status=OracleWebhookStatuses.completed
            )
        )
        session.execute(upd)

    def handle_webhook_fail(self, session: Session, webhook_id: int) -> None:
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


inbox = OracleWebhookQueue(direction=OracleWebhookDirectionTag.incoming)
outbox = OracleWebhookQueue(direction=OracleWebhookDirectionTag.outgoing)
