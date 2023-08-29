import io
import json
from typing import List, Dict, Callable

from attrs import define

from src.core.types import TaskType
from src.models.cvat import Job


@define
class FileDescriptor:
    filename: str
    file: io.RawIOBase


ANNOTATION_METAFILE_NAME = "annotators.json"


def process_image_label_binary_raw_annotations(
    annotations: List[Dict], raw_annotations: List[Dict], bucket_url: str, assignee: str
) -> List[Dict]:
    if "image" in raw_annotations:
        for image in raw_annotations["image"]:
            url = bucket_url + image["name"]
            answer = {
                "tag": image["tag"]["label"] if "tag" in image else "",
                "assignee": assignee,
            }

            existing_image = next((x for x in annotations if x["url"] == url), None)

            if existing_image:
                existing_image["answers"].append(answer)
            else:
                annotations.append({"url": url, "answers": [answer]})

    return annotations


def process_image_bbox_annotations():
    # TODO: add job-annotator mapping file
    raise NotImplementedError


def get_raw_annotations_handler(
    job_type: TaskType,
) -> Callable[[List[Dict], List[Dict], str, str], List[Dict]]:
    match job_type:
        case TaskType.image_label_binary.value:
            return process_image_label_binary_raw_annotations
        case TaskType.image_boxes.value:
            return process_image_bbox_annotations
        case _:
            raise ValueError(f"{job_type=} is not supported")


def prepare_annotation_metafile(jobs: List[Job]) -> FileDescriptor:
    """
    Prepares a task/project annotation descriptor file with annotator mapping.
    """

    contents = dict(
        annotators=[
            dict(
                job_id=job.cvat_id,
                annotator_wallet_id=job.latest_assignment.user_wallet_id,
            )
            for job in jobs
        ]
    )

    serialized_contents = json.dumps(contents, sort_keys=True).encode()
    return FileDescriptor(
        ANNOTATION_METAFILE_NAME, file=io.BytesIO(serialized_contents)
    )
