import itertools
from typing import Any, Dict, Tuple
from attrs import define, field
import numpy as np
import datumaro as dm
from .annotation_matching import match_annotations, bbox_iou


@define
class DatasetComparator:
    min_similarity_threshold: float
    _memo: Dict[Tuple[int, int], float] = field(factory=dict, init=False)

    def _similarity(self, gt_ann: Any, ds_ann: Any) -> float:
        key = (
            id(gt_ann),
            id(ds_ann),
        )  # make sure the boxes have stable ids before calling this!
        cached_value = self._memo.get(key)

        if cached_value is None:
            cached_value = bbox_iou(gt_ann, ds_ann)
            self._memo[key] = cached_value

        return cached_value

    def _clear_cache(self):
        self._memo.clear()

    def compare(self, gt_dataset: dm.Dataset, ds_dataset: dm.Dataset) -> float:
        self._clear_cache()

        all_similarities = []

        for ds_sample in ds_dataset:
            gt_sample = gt_dataset.get(ds_sample.id)

            if not gt_sample:
                continue

            ds_boxes = [a for a in ds_sample.annotations if isinstance(a, dm.Bbox)]
            gt_boxes = [a for a in gt_sample.annotations if isinstance(a, dm.Bbox)]

            matching_result = match_annotations(
                gt_boxes,
                ds_boxes,
                similarity=self._similarity,
                min_similarity=self.min_similarity_threshold,
            )

            for a_bbox, b_bbox in itertools.chain(
                matching_result.matches,
                matching_result.mispred,
                zip(matching_result.a_extra, itertools.repeat(None)),
                zip(itertools.repeat(None), matching_result.b_extra),
            ):
                sim = self._similarity(a_bbox, b_bbox) if a_bbox and b_bbox else 0
                all_similarities.append(sim)

        return np.mean(all_similarities) if all_similarities else 0
