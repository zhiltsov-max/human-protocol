from fastapi import APIRouter, HTTPException, Header, Query, Request
from typing import Optional, Union

from src.modules.api_schema import (
    OracleWebhook,
    OracleWebhookResponse,
    CvatWebhook,
    TaskResponse,
)
from src.database import SessionLocal

from src.modules.chain.escrow import validate_escrow
from src.validators.signature import validate_webhook_signature, validate_cvat_signature

from src.modules.cvat.handlers.webhook import cvat_webhook_handler
from src.modules.oracle_webhook.service import create_webhook
from src.modules.oracle_webhook.constants import OracleWebhookSenderType
from src.modules.exchange_oracle.service import get_available_tasks


router = APIRouter()


@router.post(
    "/webhook/job-launcher",
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
                sender_type=OracleWebhookSenderType.job_launcher,
                sender_signature=human_signature,
                event_type=webhook.event_type,
                event_data=webhook.event_data,
            )

        return OracleWebhookResponse(id=webhook_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/webhook/cvat",
    description="Consumes a webhook from a cvat",
)
async def cvat_webhook(
    cvat_webhook: CvatWebhook,
    request: Request,
    x_signature_256: str = Header(),
):
    await validate_cvat_signature(request, x_signature_256)
    cvat_webhook_handler(cvat_webhook)


@router.get("/tasks", description="Lists available tasks")
async def list_tasks(
    # TODO: add service authorization
    # request: Request,
    # human_signature: Union[str, None] = Header(default=None),
    username: Optional[str] = Query(default=None),
) -> list[TaskResponse]:
    return get_available_tasks(username=username)
