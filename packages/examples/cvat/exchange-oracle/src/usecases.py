from typing import Optional
from src.db import SessionLocal

from src.core.constants import ProviderType
from src.schemas import service as service_api
from src.services import cvat as cvat_db_service


def get_available_tasks(
    username: Optional[str] = None,
) -> list[service_api.TaskResponse]:
    results = []

    with SessionLocal.begin() as session:
        cvat_projects = cvat_db_service.get_available_projects(
            session, username=username
        )

        results.extend(
            service_api.TaskResponse(
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
