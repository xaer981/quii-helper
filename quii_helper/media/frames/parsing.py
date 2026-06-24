from quii_helper.media.cpacket import find_next_cpacket, starts_cpacket
from quii_helper.media.cpacket.constants import CPACKET_HEADER_LEN
from quii_helper.media.frames import cframe_pack as _cframe_pack
from quii_helper.media.frames.frame_parsing import parse_quii_media_frame_at

QuiiCFramePack = _cframe_pack.QuiiCFramePack
_parse_quii_media_frame_at = parse_quii_media_frame_at


def parse_quii_media_frame(payload: bytes) -> dict | None:
    frames = iter_quii_media_frames(payload)
    return frames[0] if frames else None


def iter_quii_media_frames(payload: bytes) -> list[dict]:
    frames: list[dict] = []
    offset = 0
    while offset + CPACKET_HEADER_LEN <= len(payload):
        if not starts_cpacket(payload, offset):
            next_offset = find_next_cpacket(payload, offset + 1)
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
