import io
from typing import List, Dict

from attrs import define

from src.core.annotation_meta import ANNOTATION_METAFILE_NAME, AnnotationMeta, JobMeta
from src.models.cvat import Job


@define
class FileDescriptor:
    filename: str
    file: io.RawIOBase


def prepare_annotation_metafile(
    jobs: List[Job], job_annotations: Dict[int, FileDescriptor]
) -> FileDescriptor:
    """
    Prepares a task/project annotation descriptor file with annotator mapping.
    """

    meta = AnnotationMeta(
        jobs=[
            JobMeta(
                job_id=job.cvat_id,
                annotation_filename=job_annotations[job.cvat_id],
                annotator_wallet_address=job.latest_assignment.user_wallet_address,
                assignment_id=job.latest_assignment.id
            )
            for job in jobs
        ]
    )

    return FileDescriptor(
        ANNOTATION_METAFILE_NAME, file=io.BytesIO(meta.json().encode())
    )
