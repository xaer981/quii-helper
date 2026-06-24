from quii_helper.media.merge.bytes import (
    suffix_prefix_overlap,
    unique_blobs_by_sha1,
)


def merge_binary_candidates(
    blobs: list[bytes],
) -> tuple[list[bytes], bytes, str]:
    unique = unique_blobs_by_sha1(blobs)
    if not unique:
        return [], b"", "none"

    min_overlap = 16
    stream = unique[0]
    strategy = "longest"
    for blob in sorted(unique[1:], key=len, reverse=True):
        if blob == stream or blob in stream or stream.startswith(blob):
            continue
        if stream in blob or blob.startswith(stream):
            stream = blob
            strategy = "right_extends_left"
            continue

        best_overlap = suffix_prefix_overlap(
            stream, blob, min_overlap=min_overlap
        )
        if best_overlap >= min_overlap:
            stream += blob[best_overlap:]
            strategy = f"suffix_prefix_overlap:{best_overlap}"
            continue

        best_overlap = suffix_prefix_overlap(
            blob, stream, min_overlap=min_overlap
        )
        if best_overlap >= min_overlap:
            stream = blob + stream[best_overlap:]
            strategy = f"prefix_suffix_overlap:{best_overlap}"
            continue

    return unique, stream, strategy
