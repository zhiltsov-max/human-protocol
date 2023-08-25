from enum import Enum
import io
import zipfile
import xmltodict
import logging
from http import HTTPStatus
from typing import Dict, List, Optional

from src.core.config import Config
from cvat_sdk.api_client import Configuration, ApiClient, models, exceptions
from cvat_sdk.core.helpers import get_paginated_collection
from src.core.types import JobStatuses

from src.utils.enums import BetterEnumMeta


def get_api_client() -> ApiClient:
    configuration = Configuration(
        host=Config.cvat_config.cvat_url,
        username=Config.cvat_config.cvat_admin,
        password=Config.cvat_config.cvat_admin_pass,
    )

    return ApiClient(configuration=configuration)


def create_cloudstorage(
    provider: str, bucket_host: str, bucket_name: str
) -> models.CloudStorageRead:
    logger = logging.getLogger("app")
    with get_api_client() as api_client:
        cloud_storage_write_request = models.CloudStorageWriteRequest(
            provider_type=models.ProviderTypeEnum(provider),
            resource=bucket_name,
            display_name=bucket_name,
            credentials_type=models.CredentialsTypeEnum("ANONYMOUS_ACCESS"),
            description=bucket_name,
            specific_attributes=f"endpoint_url={bucket_host}",
        )  # CloudStorageWriteRequest
        try:
            (data, response) = api_client.cloudstorages_api.create(
                cloud_storage_write_request,
            )

            return data
        except exceptions.ApiException as e:
            logger.exception(f"Exception when calling CloudstoragesApi.create(): {e}\n")
            raise


def create_project(escrow_address: str, labels: list) -> models.ProjectRead:
    logger = logging.getLogger("app")
    with get_api_client() as api_client:
        project_write_request = models.ProjectWriteRequest(
            name=escrow_address,
            labels=labels,
            owner_id=Config.cvat_config.cvat_admin_user_id,
        )
        try:
            (data, response) = api_client.projects_api.create(project_write_request)
            return data
        except exceptions.ApiException as e:
            logger.exception(f"Exception when calling ProjectsApi.create: {e}\n")
            raise


def setup_cvat_webhooks(project_id: int) -> models.WebhookRead:
    logger = logging.getLogger("app")
    with get_api_client() as api_client:
        webhook_write_request = models.WebhookWriteRequest(
            target_url=Config.cvat_config.cvat_incoming_webhooks_url,
            description="Exchange Oracle notification",
            type=models.WebhookType("project"),
            content_type=models.WebhookContentType("application/json"),
            secret=Config.cvat_config.cvat_webhook_secret,
            is_active=True,
            # enable_ssl=True,
            project_id=project_id,
            events=[
                models.EventsEnum("update:job"),
                models.EventsEnum("create:job"),
            ],
        )  # WebhookWriteRequest
        try:
            (data, response) = api_client.webhooks_api.create(
                webhook_write_request,
            )
            return data
        except exceptions.ApiException as e:
            logger.exception(f"Exception when calling WebhooksApi.create(): {e}\n")
            raise


def create_task(project_id: int, escrow_address: str) -> models.TaskRead:
    logger = logging.getLogger("app")
    with get_api_client() as api_client:
        task_write_request = models.TaskWriteRequest(
            name=escrow_address,
            project_id=project_id,
            owner_id=Config.cvat_config.cvat_admin_user_id,
            overlap=0,
            segment_size=Config.cvat_config.cvat_job_segment_size,
        )
        try:
            (task_info, response) = api_client.tasks_api.create(task_write_request)
            return task_info

        except exceptions.ApiException as e:
            logger.exception(f"Exception when calling tasks_api.create: {e}\n")
            raise


def create_gt_job(task_id: int, size: int) -> models.JobRead:
    logger = logging.getLogger("app")
    with get_api_client() as api_client:
        job_write_request = models.JobWriteRequest(
            task_id=task_id,
            frame_selection_method="random_uniform",
            size=size,
        )
        try:
            (job, response) = api_client.jobs_api.create(job_write_request)
            return job

        except exceptions.ApiException as e:
            logger.exception(f"Exception when calling tasks_api.create: {e}\n")
            raise


def get_cloudstorage_contents(cloudstorage_id: int) -> List[str]:
    logger = logging.getLogger("app")
    with get_api_client() as api_client:
        try:
            (content_data, response) = api_client.cloudstorages_api.retrieve_content(
                cloudstorage_id
            )
            return content_data
        except exceptions.ApiException as e:
            logger.exception(
                f"Exception when calling cloudstorages_api.retrieve_content: {e}\n"
            )
            raise


def put_task_data(
    task_id: int,
    cloudstorage_id: int,
    *,
    filenames: Optional[list[str]] = None,
    sort_images: bool = True,
) -> None:
    logger = logging.getLogger("app")

    with get_api_client() as api_client:
        kwargs = {}
        if filenames:
            kwargs["server_files"] = filenames
        else:
            kwargs["filename_pattern"] = "*"

        data_request = models.DataRequest(
            chunk_size=Config.cvat_config.cvat_job_segment_size,
            cloud_storage_id=cloudstorage_id,
            image_quality=Config.cvat_config.cvat_default_image_quality,
            use_cache=True,
            use_zip_chunks=True,
            sorting_method="lexicographical" if sort_images else "predefined",
            **kwargs,
        )
        try:
            (_, response) = api_client.tasks_api.create_data(
                task_id, data_request=data_request
            )
            return None

        except exceptions.ApiException as e:
            logger.exception(f"Exception when calling ProjectsApi.put_task_data: {e}\n")
            raise


def fetch_task_jobs(task_id: int) -> List[models.JobRead]:
    logger = logging.getLogger("app")
    with get_api_client() as api_client:
        try:
            data = get_paginated_collection(
                api_client.jobs_api.list_endpoint, task_id=task_id
            )
            return data
        except exceptions.ApiException as e:
            logger.exception(f"Exception when calling JobsApi.list: {e}\n")
            raise


def get_job_annotations(cvat_project_id: int) -> Dict:
    logger = logging.getLogger("app")
    with get_api_client() as api_client:
        try:
            for _ in range(5):
                (_, response) = api_client.jobs_api.retrieve_annotations(
                    id=cvat_project_id,
                    action="download",
                    format="CVAT for images 1.1",
                    _parse_response=False,
                )
                if response.status == HTTPStatus.OK:
                    break
            buffer = io.BytesIO(response.data)
            with zipfile.ZipFile(buffer, "r") as zip_file:
                xml_content = zip_file.read("annotations.xml").decode("utf-8")
            annotations = xmltodict.parse(xml_content, attr_prefix="")
            return annotations["annotations"]
        except exceptions.ApiException as e:
            logger.exception(
                f"Exception when calling JobsApi.retrieve_annotations: {e}\n"
            )
            raise


def delete_project(cvat_id: int) -> None:
    logger = logging.getLogger("app")
    with get_api_client() as api_client:
        try:
            api_client.projects_api.destroy(cvat_id)
        except exceptions.ApiException as e:
            logger.exception(f"Exception when calling ProjectsApi.destroy(): {e}\n")
            raise


def delete_cloudstorage(cvat_id: int) -> None:
    logger = logging.getLogger("app")
    with get_api_client() as api_client:
        try:
            api_client.cloudstorages_api.destroy(cvat_id)
        except exceptions.ApiException as e:
            logger.exception(
                f"Exception when calling CloudstoragesApi.destroy(): {e}\n"
            )
            raise


def fetch_projects(assignee: str = "") -> List[models.ProjectRead]:
    logger = logging.getLogger("app")
    with get_api_client() as api_client:
        try:
            return get_paginated_collection(
                api_client.projects_api.list_endpoint,
                **(dict(assignee=assignee) if assignee else {}),
            )
        except exceptions.ApiException as e:
            logger.exception(f"Exception when calling ProjectsApi.list(): {e}\n")
            raise


class UploadStatus(str, Enum, metaclass=BetterEnumMeta):
    QUEUED = "Queued"
    STARTED = "Started"
    FINISHED = "Finished"
    FAILED = "Failed"


def get_task_upload_status(cvat_id: int) -> Optional[UploadStatus]:
    logger = logging.getLogger("app")

    with get_api_client() as api_client:
        try:
            (status, _) = api_client.tasks_api.retrieve_status(cvat_id)
            return UploadStatus[status.state.value]
        except exceptions.ApiException as e:
            if e.status == 404:
                return None

            logger.exception(f"Exception when calling ProjectsApi.list(): {e}\n")
            raise


def put_job_annotations(job_id: int, storage_id: int, path: str) -> str:
    logger = logging.getLogger("app")

    with get_api_client() as api_client:
        try:
            (_, response) = api_client.jobs_api.create_annotations(
                job_id,
                cloud_storage_id=storage_id,
                use_default_location=False,
                location=path,
                format="COCO 1.0",
            )
            return response.data["rq_id"]
        except exceptions.ApiException as e:
            if e.status == 404:
                return None

            logger.exception(
                f"Exception when calling JobsApi.create_annotations(): {e}\n"
            )
            raise


def update_job_assignee(id: str, assignee: str):
    logger = logging.getLogger("app")

    with get_api_client() as api_client:
        try:
            api_client.jobs_api.partial_update(
                id=id,
                patched_job_write_request=models.PatchedJobWriteRequest(
                    assignee=assignee
                ),
            )
        except exceptions.ApiException as e:
            logger.exception(f"Exception when calling JobsApi.partial_update(): {e}\n")
            raise


def invite_user_into_org(user_email: str):
    logger = logging.getLogger("app")

    with get_api_client() as api_client:
        try:
            api_client.invitations_api.create(
                models.InvitationWriteRequest(role="worker", email=user_email)
            )
        except exceptions.ApiException as e:
            logger.exception(f"Exception when calling InvitationsApi.create(): {e}\n")
            raise


def get_user_id(user_email: str) -> int:
    logger = logging.getLogger("app")

    with get_api_client() as api_client:
        try:
            (invitation, _) = api_client.invitations_api.create(
                models.InvitationWriteRequest(role="worker", email=user_email),
                org=Config.cvat_config.cvat_org_slug,
            )

            (page, _) = api_client.memberships_api.list(user=invitation.user.username)
            membership = page.results[0]
            api_client.memberships_api.destroy(membership.id)
        except exceptions.ApiException as e:
            logger.exception(f"Exception when calling InvitationsApi.create(): {e}\n")
            raise

        return invitation.user.id
