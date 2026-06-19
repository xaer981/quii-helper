from quii_helper.media.cpacket_constants import (
    CPACKET_START_PREFIX,
    CPACKET_START_TYPE_MAX,
    CPACKET_START_TYPE_MIN,
)


def find_cpacket_offsets(blob: bytes, *, limit: int = 32) -> list[int]:
    offsets: list[int] = []
    cursor = 0
    while len(offsets) < limit:
        idx = blob.find(CPACKET_START_PREFIX, cursor)
        if idx < 0 or idx + 3 >= len(blob):
            break
        marker_type = blob[idx + 3]
        if CPACKET_START_TYPE_MIN <= marker_type <= CPACKET_START_TYPE_MAX:
            offsets.append(idx)
        cursor = idx + 3
    return offsets
