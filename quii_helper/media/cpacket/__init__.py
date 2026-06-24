from quii_helper.media.cpacket.constants import (
    CPACKET_HEADER_LEN,
    CPACKET_START_PREFIX,
    CPACKET_START_TYPE_MAX,
    CPACKET_START_TYPE_MIN,
)

CPACKET_MAX_FRAME_LEN = 64 * 1024 * 1024


def starts_cpacket(payload: bytes | bytearray, offset: int) -> bool:
    return (
        offset + 4 <= len(payload)
        and payload[offset : offset + 3] == CPACKET_START_PREFIX
        and CPACKET_START_TYPE_MIN
        <= payload[offset + 3]
        <= CPACKET_START_TYPE_MAX
    )


def find_next_cpacket(payload: bytes, offset: int) -> int:
    cursor = max(0, offset)
    while cursor < len(payload):
        candidate = payload.find(CPACKET_START_PREFIX, cursor)
        if candidate < 0:
            return -1
        if starts_cpacket(payload, candidate):
            return candidate
        cursor = candidate + 1
    return -1


def cpacket_frame_len(
    payload: bytes | bytearray,
    offset: int = 0,
) -> int | None:
    if len(payload) - offset < CPACKET_HEADER_LEN:
        return None
    if not starts_cpacket(payload, offset):
        return None
    return int.from_bytes(payload[offset + 4 : offset + 8], "little")


def parse_cpacket_header(
    payload: bytes | bytearray,
    offset: int = 0,
    *,
    require_complete: bool = True,
) -> dict | None:
    frame_len = cpacket_frame_len(payload, offset)
    if frame_len is None or frame_len <= 0:
        return None

    total_len = frame_len + CPACKET_HEADER_LEN
    if require_complete and offset + total_len > len(payload):
        return None

    frame_tag = payload[offset + 3]
    fps_raw = payload[offset + 0x0F]
    return {
        "payload_offset": offset,
        "frame_tag": frame_tag,
        "frame_type": (frame_tag + 0x20) & 0xFF,
        "frame_len": frame_len,
        "frame_stamp": int.from_bytes(
            payload[offset + 8 : offset + 12],
            "little",
        ),
        "frame_flags": bytes(payload[offset + 12 : offset + 16]),
        "codec": payload[offset + 0x0E],
        "fps_raw": fps_raw,
        "fps": fps_raw / 4.0,
        "total_len": total_len,
        "width": int.from_bytes(payload[offset + 16 : offset + 18], "little"),
        "height": int.from_bytes(
            payload[offset + 18 : offset + 20],
            "little",
        ),
    }
