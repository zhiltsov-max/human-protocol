from src.core.types import CvatLabelType, TaskType
from src.db import SessionLocal

from src.utils.helpers import parse_data_url, parse_manifest, compose_bucket_url

import src.services.cvat as db_service
import src.cvat.api_calls as cvat_api


label_type_mapping = {
    TaskType.image_label_binary: CvatLabelType.tag,
    TaskType.image_points: CvatLabelType.points,
    TaskType.image_boxes: CvatLabelType.rectangle,
}


def create_task(escrow_address: str, chain_id: int, manifest: dict) -> None:
    parsed_manifest = parse_manifest(manifest)

    parsed_bucket_url = parse_data_url(parsed_manifest.data.host_url)
    cloud_provider = parsed_bucket_url.provider
    bucket_name = parsed_bucket_url.bucket_name

    cvat_labels = [
        {"name": label.name, "type": label_type_mapping.get(parsed_manifest.task.type)}
        for label in parsed_manifest.task.labels
    ]

    # Register cloud storage on CVAT to pass user dataset
    cloud_storage = cvat_api.create_cloudstorage(cloud_provider, bucket_name)

    # Create a project on CVAT to enable webhooks
    project = cvat_api.create_project(escrow_address, cvat_labels)

    with SessionLocal.begin() as session:
        db_service.create_project(
            session,
            project.id,
            cloud_storage.id,
            parsed_manifest.task.type,
            escrow_address,
            chain_id,
            compose_bucket_url(bucket_name, cloud_provider),
        )

    # Setup webhooks for a project (update:task, update:job)
    cvat_api.setup_cvat_webhooks(project.id)

    # Task configuration creation
    task = cvat_api.create_task(project.id, escrow_address)

    with SessionLocal.begin() as session:
        db_service.create_task(session, task.id, project.id, task.status)

    # Actual task creation in CVAT takes some time, so it's done in an async process.
    # The task will be created in DB once 'update:task' or 'update:job' webhook is received.
    cvat_api.put_task_data(task.id, cloud_storage.id)
    db_service.create_data_upload(session, cvat_task_id=task.id)


def remove_task(escrow_address: str) -> None:
    with SessionLocal.begin() as session:
        project = db_service.get_project_by_escrow_address(session, escrow_address)
        if project is not None:
            if project.cvat_cloudstorage_id:
                cvat_api.delete_cloudstorage(project.cvat_cloudstorage_id)
            if project.cvat_id:
                cvat_api.delete_project(project.cvat_id)
            db_service.delete_project(session, project.id)
            session.commit()
