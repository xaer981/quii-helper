import hashlib

from quii_helper.media.annexb_probe_analysis import analyze_annexb_h264


def merge_annexb_candidates(
    blobs: list[bytes],
) -> tuple[list[bytes], bytes, str]:
    unique: list[bytes] = []
    seen = set()
    for blob in sorted(blobs, key=len, reverse=True):
        digest = hashlib.sha1(blob).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        unique.append(blob)

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

        best_overlap = 0
        max_check = min(len(stream), len(blob))
        for k in range(max_check, 0, -1):
            if stream[-k:] == blob[:k]:
                best_overlap = k
                break
        if best_overlap > 0:
            stream += blob[best_overlap:]
            merged = True
            continue

        stream += blob
        merged = True
    return unique, stream, ("merged" if merged else "longest")


def merge_two_streams(left: bytes, right: bytes) -> tuple[bytes, str]:
    min_overlap = 16
    if not left:
        return right, "right_only"
    if not right:
        return left, "left_only"
    if left == right:
        return left, "same"
    left_nal = analyze_annexb_h264(left)
    right_nal = analyze_annexb_h264(right)

    if _is_false_positive_sps_only(left_nal) and _is_false_positive_sps_only(
        right_nal
    ):
        return right, "replace_false_positive_with_current"

    if _is_degraded_sps_only(left_nal) and _is_sps_only(right_nal):
        return right, "replace_degraded_persistent_sps_only"
    if _is_degraded_sps_only(right_nal) and _is_sps_only(left_nal):
        return left, "keep_non_degraded_left_sps_only"
    if _is_false_positive_sps_only(
        left_nal
    ) and not _is_false_positive_sps_only(right_nal):
        return right, "replace_false_positive_persistent"
    if _is_false_positive_sps_only(
        right_nal
    ) and not _is_false_positive_sps_only(left_nal):
        return left, "keep_non_false_positive_left"

    if right in left or left.startswith(right):
        return left, "left_contains_right"
    if left in right or right.startswith(left):
        return right, "right_extends_left"

    best_overlap = 0
    max_check = min(len(left), len(right))
    for k in range(max_check, 0, -1):
        if left[-k:] == right[:k]:
            best_overlap = k
            break
    if best_overlap >= min_overlap:
        return (
            left + right[best_overlap:],
            f"suffix_prefix_overlap:{best_overlap}",
        )

    best_overlap = 0
    for k in range(max_check, 0, -1):
        if right[-k:] == left[:k]:
            best_overlap = k
            break
    if best_overlap >= min_overlap:
        return (
            right + left[best_overlap:],
            f"prefix_suffix_overlap:{best_overlap}",
        )

    if _is_sps_only(left_nal) and _is_sps_only(right_nal):
        return (
            right if len(right) >= len(left) else left
        ), "prefer_longer_sps_only"

    return right, "replace_with_current_disjoint"


def _is_sps_only(analysis: dict) -> bool:
    counts = analysis.get("counts", {})
    return (
        not analysis.get("has_vcl")
        and not analysis.get("has_pps")
        and set(counts.keys()) <= {"sps"}
        and sum(counts.values()) > 0
    )


def _is_degraded_sps_only(analysis: dict) -> bool:
    return (
        _is_sps_only(analysis)
        and int(analysis.get("counts", {}).get("sps", 0)) > 1
    )


def _is_false_positive_sps_only(analysis: dict) -> bool:
    return bool(analysis.get("false_positive_sps_only"))
