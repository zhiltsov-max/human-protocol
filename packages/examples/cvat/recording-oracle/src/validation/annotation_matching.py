import itertools
from typing import (
    Callable,
    Dict,
    List,
    NamedTuple,
    Sequence,
    Tuple,
    TypeVar,
)
import numpy as np

from scipy.optimize import linear_sum_assignment


Annotation = TypeVar("Annotation")


class Bbox(NamedTuple):
    x: float
    y: float
    w: float
    h: float
    label: int


def bbox_iou(a_bbox: Bbox, b_bbox: Bbox) -> float:
    """
    IoU computation for simple cases with bounding boxes
    """

    a_x, a_y, a_w, a_h = a_bbox[:4]
    b_x, b_y, b_w, b_h = b_bbox[:4]
    int_right = min(a_x + a_w, b_x + b_w)
    int_left = max(a_x, b_x)
    int_top = max(a_y, b_y)
    int_bottom = min(a_y + a_h, b_y + b_h)

    int_w = max(0, int_right - int_left)
    int_h = max(0, int_bottom - int_top)
    intersection = int_w * int_h
    if not intersection:
        return 0

    a_area = a_w * a_h
    b_area = b_w * b_h
    union = a_area + b_area - intersection
    return intersection / union


class MatchResult(NamedTuple):
    matches: List[Tuple[Annotation, Annotation]]
    mispred: List[Tuple[Annotation, Annotation]]
    a_extra: List[Annotation]
    b_extra: List[Annotation]


def match_annotations(
    a_anns: Sequence[Annotation],
    b_anns: Sequence[Annotation],
    similarity: Callable[[Annotation, Annotation], float] = bbox_iou,
    min_similarity: float = 1.0,
    label_matcher: Callable[[Annotation, Annotation], bool] = lambda a, b: a.label
    == b.label,
) -> MatchResult:
    assert callable(similarity), similarity
    assert callable(label_matcher), label_matcher

    max_ann_count = max(len(a_anns), len(b_anns))
    distances = np.array(
        [
            [
                1 - similarity(a, b) if a is not None and b is not None else 1
                for b, _ in itertools.zip_longest(
                    b_anns, range(max_ann_count), fillvalue=None
                )
            ]
            for a, _ in itertools.zip_longest(
                a_anns, range(max_ann_count), fillvalue=None
            )
        ]
    )
    distances[distances > 1 - min_similarity] = 1

    if a_anns and b_anns:
        a_matches, b_matches = linear_sum_assignment(distances)
    else:
        a_matches = []
        b_matches = []

    # matches: boxes we succeeded to match completely
    # mispred: boxes we succeeded to match, having label mismatch
    matches = []
    mispred = []
    # *_umatched: boxes of (*) we failed to match
    a_unmatched = []
    b_unmatched = []

    for a_idx, b_idx in zip(a_matches, b_matches):
        dist = distances[a_idx, b_idx]
        if dist > 1 - min_similarity or dist == 1:
            if a_idx < len(a_anns):
                a_unmatched.append(a_anns[a_idx])
            if b_idx < len(b_anns):
                b_unmatched.append(b_anns[b_idx])
        else:
            a_ann = a_anns[a_idx]
            b_ann = b_anns[b_idx]
            if label_matcher(a_ann, b_ann):
                matches.append((a_ann, b_ann))
            else:
                mispred.append((a_ann, b_ann))

    if not len(a_matches) and not len(b_matches):
        a_unmatched = list(a_anns)
        b_unmatched = list(b_anns)

    return MatchResult(matches, mispred, a_unmatched, b_unmatched)
