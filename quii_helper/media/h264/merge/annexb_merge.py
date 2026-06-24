from quii_helper.media.h264.merge.annexb_merge_state import (
    containment_merge_decision,
    false_positive_or_degraded_merge_decision,
    overlap_merge_decision,
    sps_only_tie_break_decision,
)
from quii_helper.media.h264.merge.probe_analysis import analyze_annexb_h264
from quii_helper.media.merge.bytes import (
    suffix_prefix_overlap,
    unique_blobs_by_sha1,
)


def merge_annexb_candidates(
    blobs: list[bytes],
) -> tuple[list[bytes], bytes, str]:
    unique = unique_blobs_by_sha1(blobs)
    if not unique:
        return [], b"", "none"

    stream = unique[0]
    merged = False
    for blob in sorted(unique[1:], key=len, reverse=True):
        if blob == stream:
            continue
        if blob in stream:
            continue
        if stream.startswith(blob):
            continue
        if blob.startswith(stream):
            stream = blob
            continue

        best_overlap = suffix_prefix_overlap(stream, blob)
        if best_overlap > 0:
            stream += blob[best_overlap:]
            merged = True
            continue

        stream += blob
        merged = True
    return unique, stream, ("merged" if merged else "longest")


def merge_two_streams(left: bytes, right: bytes) -> tuple[bytes, str]:
    if not left:
        return right, "right_only"
    if not right:
        return left, "left_only"
    if left == right:
        return left, "same"
    left_nal = analyze_annexb_h264(left)
    right_nal = analyze_annexb_h264(right)

    for decision in (
        false_positive_or_degraded_merge_decision(
            left, left_nal, right, right_nal
        ),
        containment_merge_decision(left, right),
        overlap_merge_decision(left, right),
        sps_only_tie_break_decision(left, left_nal, right, right_nal),
    ):
        if decision is not None:
            return decision

    return right, "replace_with_current_disjoint"
