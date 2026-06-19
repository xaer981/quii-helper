import hashlib


def merge_binary_candidates(
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

        best_overlap = 0
        max_check = min(len(stream), len(blob))
        for k in range(max_check, min_overlap - 1, -1):
            if stream[-k:] == blob[:k]:
                best_overlap = k
                break
        if best_overlap >= min_overlap:
            stream += blob[best_overlap:]
            strategy = f"suffix_prefix_overlap:{best_overlap}"
            continue

        best_overlap = 0
        for k in range(max_check, min_overlap - 1, -1):
            if blob[-k:] == stream[:k]:
                best_overlap = k
                break
        if best_overlap >= min_overlap:
            stream = blob + stream[best_overlap:]
            strategy = f"prefix_suffix_overlap:{best_overlap}"
            continue

    return unique, stream, strategy
