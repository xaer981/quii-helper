from typing import Any

from quii_helper.media.merge.bytes import suffix_prefix_overlap

MIN_ANNEXB_STREAM_OVERLAP = 16
MergeDecision = tuple[bytes, str]


def false_positive_or_degraded_merge_decision(
    left: bytes,
    left_analysis: dict[str, Any],
    right: bytes,
    right_analysis: dict[str, Any],
) -> MergeDecision | None:
    if is_false_positive_sps_only(
        left_analysis
    ) and is_false_positive_sps_only(right_analysis):
        return right, "replace_false_positive_with_current"

    if is_degraded_sps_only(left_analysis) and is_sps_only(right_analysis):
        return right, "replace_degraded_persistent_sps_only"
    if is_degraded_sps_only(right_analysis) and is_sps_only(left_analysis):
        return left, "keep_non_degraded_left_sps_only"
    if is_false_positive_sps_only(
        left_analysis
    ) and not is_false_positive_sps_only(right_analysis):
        return right, "replace_false_positive_persistent"
    if is_false_positive_sps_only(
        right_analysis
    ) and not is_false_positive_sps_only(left_analysis):
        return left, "keep_non_false_positive_left"
    return None


def containment_merge_decision(
    left: bytes,
    right: bytes,
) -> MergeDecision | None:
    if right in left or left.startswith(right):
        return left, "left_contains_right"
    if left in right or right.startswith(left):
        return right, "right_extends_left"
    return None


def overlap_merge_decision(
    left: bytes,
    right: bytes,
    *,
    min_overlap: int = MIN_ANNEXB_STREAM_OVERLAP,
) -> MergeDecision | None:
    best_overlap = suffix_prefix_overlap(left, right, min_overlap=min_overlap)
    if best_overlap >= min_overlap:
        return (
            left + right[best_overlap:],
            f"suffix_prefix_overlap:{best_overlap}",
        )

    best_overlap = suffix_prefix_overlap(right, left, min_overlap=min_overlap)
    if best_overlap >= min_overlap:
        return (
            right + left[best_overlap:],
            f"prefix_suffix_overlap:{best_overlap}",
        )
    return None


def sps_only_tie_break_decision(
    left: bytes,
    left_analysis: dict[str, Any],
    right: bytes,
    right_analysis: dict[str, Any],
) -> MergeDecision | None:
    if is_sps_only(left_analysis) and is_sps_only(right_analysis):
        return (
            right if len(right) >= len(left) else left
        ), "prefer_longer_sps_only"
    return None


def is_sps_only(analysis: dict[str, Any]) -> bool:
    counts = analysis.get("counts", {})
    return (
        not analysis.get("has_vcl")
        and not analysis.get("has_pps")
        and set(counts.keys()) <= {"sps"}
        and sum(counts.values()) > 0
    )


def is_degraded_sps_only(analysis: dict[str, Any]) -> bool:
    return (
        is_sps_only(analysis)
        and int(analysis.get("counts", {}).get("sps", 0)) > 1
    )


def is_false_positive_sps_only(analysis: dict[str, Any]) -> bool:
    return bool(analysis.get("false_positive_sps_only"))
