import hashlib


def unique_blobs_by_sha1(blobs: list[bytes]) -> list[bytes]:
    unique: list[bytes] = []
    seen = set()
    for blob in sorted(blobs, key=len, reverse=True):
        digest = hashlib.sha1(blob).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        unique.append(blob)
    return unique


def suffix_prefix_overlap(
    left: bytes, right: bytes, *, min_overlap: int = 1
) -> int:
    max_check = min(len(left), len(right))
    for size in range(max_check, min_overlap - 1, -1):
        if left[-size:] == right[:size]:
            return size
    return 0
