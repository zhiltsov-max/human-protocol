from http import HTTPStatus
from fastapi import APIRouter, HTTPException, Header, Query
from typing import Optional

import sqlalchemy.exc
from src.db import SessionLocal

import src.cvat.api_calls as cvat_api
from src.schemas.exchange import TaskResponse, UserRequest, UserResponse
import src.services.exchange as oracle_service
from src.validators.signature import validate_human_app_signature
import src.services.cvat as cvat_service

router = APIRouter()


@router.get("/tasks", description="Lists available tasks")
async def list_tasks(
    wallet_id: Optional[str] = Query(default=None),
    signature: str = Header(description="Calling service signature"),
) -> list[TaskResponse]:
    await validate_human_app_signature(signature)
    return oracle_service.get_available_tasks(wallet_id=wallet_id)


@router.put("/register", description="Binds a CVAT user a to HUMAN App user")
async def register(
    user: UserRequest,
    signature: str = Header(description="Calling service signature"),
) -> UserResponse:
    await validate_human_app_signature(signature)

    try:
        cvat_id = cvat_api.get_user_id(user.cvat_email)
    except cvat_api.exceptions.ApiException as e:
        if (
            e.status == HTTPStatus.BAD_REQUEST
            and "It is not a valid email in the system." in e.body
        ):
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="User with this email not found",
            ) from e
        raise

    # The db exception is raised after the session (which is a transaction) is closed
    try:
        with SessionLocal.begin() as session:
            user = cvat_service.put_user(
                session,
                wallet_id=user.wallet_id,
                cvat_email=user.cvat_email,
                cvat_id=cvat_id,
            )
    except sqlalchemy.exc.IntegrityError as e:
        if f"(cvat_email)=({user.cvat_email}) already exists" in str(e):
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST, detail="User already exists"
            ) from e
        raise

    return UserResponse(
        wallet_id=user.wallet_id, cvat_email=user.cvat_email, cvat_id=user.cvat_id
    )


@router.post(
    "/tasks/{id}/assignment",
    description="Start an assignment within the task for the annotator",
)
async def create_assignment(
    wallet_id: str,
    project_id: str = Query(alias="id"),
    signature: str = Header(description="Calling service signature"),
) -> TaskResponse:
    await validate_human_app_signature(signature)

    assignment_id = oracle_service.create_assignment(
        project_id=project_id, wallet_id=wallet_id
    )
    return oracle_service.serialize_task(project_id, assignment_id=assignment_id)
