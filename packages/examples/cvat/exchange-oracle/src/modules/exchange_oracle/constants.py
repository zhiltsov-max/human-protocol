from enum import Enum


class ProviderType(str, Enum):
    CVAT = "cvat"


class TaskType(str, Enum):
    image_annotation = "image_annotation"
