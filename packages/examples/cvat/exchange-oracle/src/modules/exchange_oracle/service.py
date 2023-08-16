from typing import Optional
from src.database import SessionLocal

from .. import api_schema
from ..cvat import service as cvat_db_service
from ..exchange_oracle.constants import ProviderType


def get_available_tasks(
    username: Optional[str] = None,
) -> list[api_schema.TaskResponse]:
    results = []

    with SessionLocal.begin() as session:
        cvat_projects = cvat_db_service.get_available_projects(
            session, username=username
        )

        results.extend(
            api_schema.TaskResponse(
                escrow_id=p.escrow_address,
                title=f"Task {p.escrow_address[:10]}",
                description="Image annotation task",
                reward_per_unit=0.001,
                unit_size=12,
                assignment_time_limit=2,
                provider=ProviderType.CVAT,
                task_type=p.job_type,
            )
            for p in cvat_projects
        )

    return results
