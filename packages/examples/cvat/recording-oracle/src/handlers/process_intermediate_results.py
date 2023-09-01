import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, List, Union
from attrs import define
import io
import numpy as np

# from scipy.linalg import linear_sum_assignment

import zipfile
from sqlalchemy.orm import Session

import datumaro as dm

from src.core.annotation_meta import AnnotationMeta
from src.core.manifest import TaskManifest

from src.core.types import TaskType, TaskType
from src.core.validation_meta import JobMeta, ResultMeta, ValidationMeta
import src.services.validation as db_service


@define
class ValidationSuccess:
    validation_meta: ValidationMeta
    resulting_annotations: bytes


@define
class ValidationFailure:
    rejected_job_ids: List[int]


DM_DATASET_FORMAT_MAPPING = {
    TaskType.image_label_binary: "cvat_images",
    TaskType.image_points: "coco_person_keypoints",
    TaskType.image_boxes: "coco_instances",
}


def extract_zip_archive(data: io.RawIOBase, dst_dir: Path, *, create_dir: bool = True):
    if create_dir:
        dst_dir.mkdir()

    with zipfile.ZipFile(data) as f:
        f.extractall(dst_dir)


def match_boxes(gt_boxes, ds_boxes) -> float:
    # m = np.zeros()
    # matches = linear_sum_assignment(m)
    # ...

    return 0.5


def get_annotation_accuracy(gt_dataset: dm.Dataset, ds_dataset: dm.Dataset) -> float:
    frame_similarities = []

    for ds_sample in ds_dataset:
        gt_sample = gt_dataset.get(ds_sample.id)

        if not gt_sample:
            continue

        ds_boxes = [a for a in ds_sample.annotations if isinstance(a, dm.Bbox)]
        gt_boxes = [a for a in gt_sample.annotations if isinstance(a, dm.Bbox)]

        frame_similarity = match_boxes(gt_boxes=gt_boxes, ds_boxes=ds_boxes)
        frame_similarities.append(frame_similarity)

    return np.mean(frame_similarities)


def process_intermediate_results(
    session: Session,
    *,
    escrow_address: str,
    chain_id: int,
    meta: AnnotationMeta,
    job_annotations: Dict[int, io.RawIOBase],
    gt_annotations: io.RawIOBase,
    merged_annotations: io.RawIOBase,
    manifest: TaskManifest,
) -> Union[ValidationSuccess, ValidationFailure]:
    # validate
    task_type = manifest.annotation.type
    dataset_format = DM_DATASET_FORMAT_MAPPING[task_type]

    job_results: Dict[int, float] = {}
    rejected_job_ids: List[int] = []

    with TemporaryDirectory() as tempdir:
        tempdir = Path(tempdir)

        gt_dataset_path = tempdir / "gt.json"
        gt_dataset_path.write_bytes(gt_annotations.read())
        gt_dataset = dm.Dataset.import_from(
            os.fspath(gt_dataset_path), format=dataset_format
        )

        for job_cvat_id, job_annotations_file in job_annotations.items():
            job_dataset_path = tempdir / str(job_cvat_id)
            extract_zip_archive(job_annotations_file, job_dataset_path)

            job_dataset = dm.Dataset.import_from(
                os.fspath(job_dataset_path), format=dataset_format
            )

            job_mean_accuracy = get_annotation_accuracy(gt_dataset, job_dataset)
            job_results[job_cvat_id] = job_mean_accuracy

            if job_mean_accuracy < manifest.validation.min_quality:
                rejected_job_ids.append(job_cvat_id)

    task = db_service.get_task_by_escrow_address(session, escrow_address)
    if not task:
        task_id = db_service.create_task(
            session, escrow_address=escrow_address, chain_id=chain_id
        )
        task = db_service.get_task_by_id(session, task_id)

    job_final_result_ids: Dict[int, str] = {}
    for job_meta in meta.jobs:
        job = db_service.get_job_by_cvat_id(session, job_meta.job_id)
        if not job:
            job_id = db_service.create_job(
                session, task_id=task.id, job_cvat_id=job_meta.job_id
            )
            job = db_service.get_job_by_id(session, job_id)

        validation_result = db_service.get_validation_result_by_assignment_id(
            session, job_meta.assignment_id
        )
        if not validation_result:
            validation_result_id = db_service.create_validation_result(
                session,
                job_id=job.id,
                annotator_wallet_address=job_meta.annotator_wallet_address,
                annotation_quality=job_results[job_meta.job_id],
                assignment_id=job_meta.assignment_id,
            )
        else:
            validation_result_id = validation_result.id

        job_final_result_ids[job.id] = validation_result_id

    if rejected_job_ids:
        return ValidationFailure(rejected_job_ids)

    task_jobs = task.jobs
    task_validation_results = db_service.get_task_validation_results(session, task.id)

    job_id_to_meta_id = {job.id: i for i, job in enumerate(task_jobs)}

    validation_result_id_to_meta_id = {
        r.id: i for i, r in enumerate(task_validation_results)
    }

    validation_meta = ValidationMeta(
        jobs=[
            JobMeta(
                job_id=job_id_to_meta_id[job.id],
                final_result_id=validation_result_id_to_meta_id[
                    validation_result_id_to_meta_id[job_final_result_ids[job.id]]
                ],
            )
            for job in task_jobs
        ],
        results=[
            ResultMeta(
                job_id=job_id_to_meta_id[r.job.id],
                annotator_wallet_address=r.annotator_wallet_address,
                annotation_quality=r.annotation_quality,
            )
            for r in task_validation_results
        ],
    )

    return ValidationSuccess(
        validation_meta=validation_meta, resulting_annotations=merged_annotations
    )


def parse_annotation_metafile(metafile: io.RawIOBase) -> AnnotationMeta:
    return AnnotationMeta.parse_raw(metafile.read())


def serialize_validation_meta(validation_meta: ValidationMeta) -> bytes:
    return validation_meta.json().encode()
