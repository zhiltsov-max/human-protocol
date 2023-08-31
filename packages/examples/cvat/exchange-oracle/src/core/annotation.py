from pathlib import Path
from typing import List
from pydantic import BaseModel


ANNOTATION_METAFILE_NAME = "annotators.json"
RESULTING_ANNOTATIONS_FILE = "resulting_annotations.zip"


class JobMeta(BaseModel):
    job_id: int
    annotation_filename: Path
    annotator_wallet_address: str


class AnnotationMeta(BaseModel):
    jobs: List[JobMeta]
