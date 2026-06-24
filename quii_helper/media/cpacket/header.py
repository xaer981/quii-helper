from quii_helper.media.cpacket.constants import (
    CPACKET_HEADER_LEN,
    CPACKET_START_PREFIX,
    CPACKET_START_TYPE_MAX,
    CPACKET_START_TYPE_MIN,
)
from quii_helper.media.h264.merge.probe_analysis import analyze_annexb_h264


def cpacket_codec_name(codec: int) -> str:
    if codec == 1 or 0x10 <= codec <= 0x1F:
        return "h264"
    if codec == 2 or 0x20 <= codec <= 0x2F:
        return "h265"
    return f"codec_{codec}"


def parse_cpacket_header(blob: bytes, offset: int = 0) -> dict:
    available = max(0, len(blob) - offset)
    result: dict[str, object] = {
        "offset": offset,
        "available": available,
        "complete_header": available >= CPACKET_HEADER_LEN,
        "plausible": False,
    }
    if available < 4:
        return result

    prefix = blob[offset : offset + 3]
    marker_type = blob[offset + 3]
    frame_type = (marker_type + 0x20) & 0xFF
    result.update(
        {
            "prefix_hex": blob[offset : offset + min(64, available)].hex(),
            "marker_type": hex(marker_type),
            "frame_type": frame_type,
            "starts_with_cpacket_magic": (
                prefix == CPACKET_START_PREFIX
                and CPACKET_START_TYPE_MIN
                <= marker_type
                <= CPACKET_START_TYPE_MAX
            ),
        }
    )
    if (
        not result["starts_with_cpacket_magic"]
        or available < CPACKET_HEADER_LEN
    ):
        return result

    payload_len = int.from_bytes(blob[offset + 4 : offset + 8], "little")
    total_len = payload_len + CPACKET_HEADER_LEN
    codec = blob[offset + 0x0E]
    fps_raw = blob[offset + 0x0F]
    width = int.from_bytes(blob[offset + 0x10 : offset + 0x12], "little")
    height = int.from_bytes(blob[offset + 0x12 : offset + 0x14], "little")
    is_video_type = frame_type in {0, 1, 9, 10}
    is_h264 = codec == 1 or 0x10 <= codec <= 0x1F
    is_h265 = codec == 2 or 0x20 <= codec <= 0x2F
    is_video = is_video_type and (is_h264 or is_h265)
    plausible = 0 <= payload_len <= 64 * 1024 * 1024
    payload_available = max(
        0, min(payload_len, available - CPACKET_HEADER_LEN)
    )
    payload = blob[
        offset
        + CPACKET_HEADER_LEN : offset
        + CPACKET_HEADER_LEN
        + payload_available
    ]
    media_analysis = _analyze_cpacket_media_payload(payload, is_h264=is_h264)

    result.update(
        {
            "payload_len": payload_len,
            "total_len": total_len,
            "complete_frame": available >= total_len,
            "missing_bytes": max(0, total_len - available),
            "payload_available": payload_available,
            "codec": codec,
            "codec_name": cpacket_codec_name(codec),
            "fps": fps_raw / 4.0,
            "width": width,
            "height": height,
            "is_video_type": is_video_type,
            "is_h264": is_h264,
            "is_h265": is_h265,
            "is_video": is_video,
            "is_key_type": frame_type in {1, 4},
            "plausible": plausible,
            "payload_prefix_hex": payload[:64].hex(),
            "media_analysis": media_analysis,
        }
    )
    return result


def _analyze_cpacket_media_payload(
    payload: bytes, *, is_h264: bool
) -> dict[str, object]:
    if not is_h264 or not payload:
        return {}
    start4 = payload.find(b"\x00\x00\x00\x01")
    start3 = payload.find(b"\x00\x00\x01")
    if start4 >= 0:
        return analyze_annexb_h264(payload[start4:])
    if start3 >= 0:
        return analyze_annexb_h264(
            payload[start3 - 1 :]
            if start3 > 0 and payload[start3 - 1] == 0
            else payload[start3:]
        )
    return {}
