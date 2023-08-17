from pathlib import Path
from pydantic import AnyUrl, BaseModel, Field, root_validator

from src.core.types import TaskType


class DataInfo(BaseModel):
    host_url: AnyUrl
    "Bucket URL, s3 only, virtual-hosted-style access"
    # https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-bucket-intro.html

    data_path: Path
    "Path in the bucket to an archive, a file or a directory"


class LabelInfo(BaseModel):
    name: str
    # https://opencv.github.io/cvat/docs/api_sdk/sdk/reference/models/label/


class TaskInfo(BaseModel):
    type: TaskType

    labels: list[LabelInfo]
    "Label declarations with accepted annotation types"

    description: str = ""
    "Brief task description"

    job_size: int = 10
    "Frames per job, validation frames are not included"

    max_assignment_time: int = 300
    "Maximum time per job (assignment) for an annotator, in seconds"

    @root_validator
    @classmethod
    def validate_type(cls, values: dict):
        if values["type"] == TaskType.image_label_binary:
            if len(values["labels"]) != 2:
                raise ValueError()

        return values


class ValidationInfo(BaseModel):
    min_quality: float = Field(ge=0)
    "Minimal accepted annotation accuracy"

    frames_per_job: int = 2
    "Validation frames per job"

    gt_path: Path
    "Path to in the bucket to an archive, the format is COCO keypoints"


class TaskManifest(BaseModel):
    data: DataInfo
    task: TaskInfo
    validation: ValidationInfo
