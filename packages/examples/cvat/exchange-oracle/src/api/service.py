from fastapi import APIRouter, Query
from typing import Optional

from src.usecases import get_available_tasks
from src.schemas.service import TaskResponse


router = APIRouter()


@router.get("/tasks", description="Lists available tasks")
async def list_tasks(
    # TODO: add service authorization
    # request: Request,
    # human_signature: Union[str, None] = Header(default=None),
    username: Optional[str] = Query(default=None),
) -> list[TaskResponse]:
    return get_available_tasks(username=username)
