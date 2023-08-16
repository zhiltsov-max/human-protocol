from pydantic import BaseModel, validator
from typing import Optional

from src.constants import Networks
from src.modules.chain.web3 import validate_address

from src.modules.cvat.constants import JobTypes
from src.modules.exchange_oracle.constants import ProviderType


class CvatWebhook(BaseModel):
    delivery_id: int
    event: str
    job: Optional[dict]
    task: Optional[dict]
    before_update: Optional[dict]


class OracleWebhook(BaseModel):
    escrow_address: str
    chain_id: Networks
    event_type: str
    event_data: dict

    @validator("escrow_address", allow_reuse=True)
    def validate_escrow_(cls, value):
        return validate_address(value)

    # pylint: disable=too-few-public-methods
    class Config:
        schema_extra = {
            "example": {
                "escrow_address": "0x199c44cfa6a84554ac01f3e3b01d7cfce38a75eb",
                "chain_id": 80001,
            }
        }


class OracleWebhookResponse(BaseModel):
    id: str


class TaskResponse(BaseModel):
    escrow_id: str
    title: str
    description: str
    reward_per_unit: float
    unit_size: int
    assignment_time_limit: float
    provider: ProviderType
    task_type: JobTypes
