from collections import Counter
import io

from src.core.annotation import AnnotationMeta

from src.core.types import JobTypes


def process_image_label_binary_intermediate_results(intermediate_results: str) -> dict:
    final_results = [
        {
            "url": item["url"],
            "final_answer": Counter(
                answer["tag"] for answer in item["answers"]
            ).most_common(1)[0][0],
            "correct": [
                answer["assignee"]
                for answer in item["answers"]
                if answer["tag"]
                == Counter(answer["tag"] for answer in item["answers"]).most_common(1)[
                    0
                ][0]
            ],
            "wrong": [
                answer["assignee"]
                for answer in item["answers"]
                if answer["tag"]
                != Counter(answer["tag"] for answer in item["answers"]).most_common(1)[
                    0
                ][0]
            ],
        }
        for item in intermediate_results
    ]

    return final_results


def process_intermediate_results(
    meta: AnnotationMeta, intermediate_results: dict, job_type: str
) -> dict:
    match job_type:
        case JobTypes.image_label_binary.value:
            final_results = process_image_label_binary_intermediate_results(
                intermediate_results
            )

    return final_results


def parse_annotation_metafile(metafile: io.RawIOBase) -> AnnotationMeta:
    return AnnotationMeta.parse_raw(metafile.read())
