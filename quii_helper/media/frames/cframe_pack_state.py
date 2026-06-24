from quii_helper.media.cpacket.constants import CPACKET_HEADER_LEN


def initial_cframe_pack_stats() -> dict[str, int]:
    return {
        "started": 0,
        "continued": 0,
        "completed": 0,
        "reset_incomplete": 0,
        "invalid_headers": 0,
        "dropped_orphan_bytes": 0,
        "dropped_oversize_frames": 0,
        "trailing_partial_bytes": 0,
    }


def cframe_expected_total_len(frame_len: int) -> int:
    return frame_len + CPACKET_HEADER_LEN


def append_buffer_bytes(
    buffer: bytearray,
    payload: bytes,
    offset: int,
    *,
    target_len: int,
) -> int:
    take = min(target_len - len(buffer), len(payload) - offset)
    if take > 0:
        buffer.extend(payload[offset : offset + take])
        offset += take
    return offset
