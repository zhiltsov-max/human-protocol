from enum import Enum

from src.core.config import Config
from src.utils.types import BetterEnumMeta


class Networks(int, Enum, metaclass=BetterEnumMeta):
    polygon_mainnet = Config.polygon_mainnet.chain_id
    polygon_mumbai = Config.polygon_mumbai.chain_id
    localhost = Config.localhost.chain_id


class EventTypes(str, Enum, metaclass=BetterEnumMeta):
    update_job = "update:job"
    create_job = "create:job"


class ProjectStatuses(str, Enum, metaclass=BetterEnumMeta):
    annotation = "annotation"
    completed = "completed"
    recorded = "recorded"


class TaskStatuses(str, Enum, metaclass=BetterEnumMeta):
    annotation = "annotation"
    completed = "completed"


class JobStatuses(str, Enum, metaclass=BetterEnumMeta):
    new = "new"
    in_progress = "in_progress"
    completed = "completed"


class JobTypes(str, Enum, metaclass=BetterEnumMeta):
    image_label_binary = "IMAGE_LABEL_BINARY"


class CvatLabelTypes(str, Enum, metaclass=BetterEnumMeta):
    tag = "tag"


class Providers(str, Enum, metaclass=BetterEnumMeta):
    aws = "AWS_S3_BUCKET"
    gcs = "GOOGLE_CLOUD_STORAGE"


class OracleWebhookTypes(str, Enum, metaclass=BetterEnumMeta):
    job_launcher = "job_launcher"
    recording_oracle = "recording_oracle"


class JobLauncherEventType(str, Enum, metaclass=BetterEnumMeta):
    escrow_created = "escrow_created"
    escrow_canceled = "escrow_canceled"


class RecordingOracleEventType(str, Enum, metaclass=BetterEnumMeta):
    task_completed = "task_completed"
    task_rejected = "task_rejected"


class OracleWebhookStatuses(str, Enum, metaclass=BetterEnumMeta):
    pending = "pending"
    completed = "completed"
    failed = "failed"


class ProviderType(str, Enum):
    CVAT = "cvat"


class TaskType(str, Enum):
    image_annotation = "image_annotation"
