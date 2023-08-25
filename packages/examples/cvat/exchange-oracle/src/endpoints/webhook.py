from typing import Union

from fastapi import APIRouter, Header, HTTPException, Request
from src.chain.escrow import validate_escrow
from src.core.types import OracleWebhookTypes
from src.db import SessionLocal
from src.schemas.webhook import OracleWebhook, OracleWebhookResponse
import src.services.webhook as oracle_db_service
from src.validators.signature import validate_webhook_signature

router = APIRouter()


@router.post(
    "/oracle-webhook",
    description="Consumes a webhook from an oracle",
)
async def oracle_webhook(
    webhook: OracleWebhook,
    request: Request,
    human_signature: Union[str, None] = Header(default=None),
):
    try:
        await request.body()
        # TODO: restore
        # await validate_webhook_signature(request, human_signature, webhook)
        # validate_escrow(webhook.chain_id, webhook.escrow_address)

        with SessionLocal.begin() as session:
            webhook_id = oracle_db_service.inbox.create_webhook(
                session=session,
                escrow_address=webhook.escrow_address,
                chain_id=webhook.chain_id,
                type=OracleWebhookTypes.job_launcher,
                signature=human_signature,
                event_type=webhook.event_type,
                event_data=webhook.event_data,
            )

        return OracleWebhookResponse(id=webhook_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
