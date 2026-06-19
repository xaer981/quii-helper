CPACKET_HEADER_LEN = 0x14
CPACKET_START_MARKER = b"\x00\x00\x01"


def parse_quii_media_frame(payload: bytes) -> dict | None:
    frames = iter_quii_media_frames(payload)
    return frames[0] if frames else None


def iter_quii_media_frames(payload: bytes) -> list[dict]:
    frames: list[dict] = []
    offset = 0
    while offset + CPACKET_HEADER_LEN <= len(payload):
        if payload[offset : offset + 3] != CPACKET_START_MARKER:
            next_offset = payload.find(CPACKET_START_MARKER, offset + 1)
            if next_offset < 0:
                break
            offset = next_offset
            continue

        frame = _parse_quii_media_frame_at(payload, offset)
        if frame is None:
            break
        frames.append(frame)
        offset = int(frame["payload_offset"]) + int(frame["total_len"])
    return frames


def _parse_quii_media_frame_at(payload: bytes, offset: int) -> dict | None:
    if len(payload) - offset < CPACKET_HEADER_LEN:
        return None
    if payload[offset : offset + 3] != CPACKET_START_MARKER:
        return None

    frame_tag = payload[offset + 3]
    frame_len = int.from_bytes(payload[offset + 4 : offset + 8], "little")
    frame_stamp = int.from_bytes(payload[offset + 8 : offset + 12], "little")
    frame_flags = payload[offset + 12 : offset + 16]
    total_len = frame_len + CPACKET_HEADER_LEN
    if frame_len <= 0 or offset + total_len > len(payload):
        return None

    width = int.from_bytes(payload[offset + 16 : offset + 18], "little")
    height = int.from_bytes(payload[offset + 18 : offset + 20], "little")
    bitstream = payload[offset + CPACKET_HEADER_LEN : offset + total_len]
    nal_offset = bitstream.find(b"\x00\x00\x00\x01")
    if nal_offset < 0:
        nal_offset = bitstream.find(b"\x00\x00\x01")

    return {
        "payload_offset": offset,
        "frame_tag": frame_tag,
        "frame_len": frame_len,
        "frame_stamp": frame_stamp,
        "frame_flags": frame_flags,
        "total_len": total_len,
        "width": width,
        "height": height,
        "bitstream": bitstream,
        "nal_offset": nal_offset,
    }
