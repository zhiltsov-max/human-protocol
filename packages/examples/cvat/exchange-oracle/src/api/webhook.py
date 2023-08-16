from typing import Union

from fastapi import APIRouter, Header, HTTPException, Request
from src.chain.escrow import validate_escrow
from src.core.constants import OracleWebhookTypes
from src.db import SessionLocal
from src.schemas.webhook import OracleWebhook, OracleWebhookResponse
from src.services.webhook import create_webhook
from src.validators.signature import validate_webhook_signature

router = APIRouter()


@router.post(
    "/job-launcher",
    description="Consumes a webhook from a job launcher",
)
async def job_launcher_webhook(
    webhook: OracleWebhook,
    request: Request,
    human_signature: Union[str, None] = Header(default=None),
):
    try:
        await validate_webhook_signature(request, human_signature, webhook)
        validate_escrow(webhook.chain_id, webhook.escrow_address)

        with SessionLocal.begin() as session:
            webhook_id = create_webhook(
                session=session,
                escrow_address=webhook.escrow_address,
                chain_id=webhook.chain_id,
                sender_type=OracleWebhookTypes.job_launcher,
                sender_signature=human_signature,
                event_type=webhook.event_type,
                event_data=webhook.event_data,
            )

        return OracleWebhookResponse(id=webhook_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
