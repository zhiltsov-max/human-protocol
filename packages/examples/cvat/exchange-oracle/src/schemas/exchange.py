from pydantic import BaseModel

from src.core.types import TaskType, ProviderType


class TaskResponse(BaseModel):
    escrow_id: str
    title: str
    description: str
    reward_per_unit: float
    unit_size: int
    assignment_time_limit: float
    provider: ProviderType
    task_type: TaskType
