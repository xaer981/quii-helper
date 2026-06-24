from quii_helper.media.frames.models import QuiiHeader
from quii_helper.media.frames.parsing import iter_quii_media_frames
from quii_helper.media.h264.merge.probe_analysis import analyze_annexb_h264

MEDIA_PACKET_TYPES = {0xA0, 0xA1, 0xA2, 0xA3}
VALID_PACKET_TYPES = {0x00, 0x01, 0x0B, 0xFE} | MEDIA_PACKET_TYPES


def safe_text_preview(payload: bytes) -> str:
    text = (
        payload.decode("utf-8", errors="ignore").replace("\x00", " ").strip()
    )
    if not text:
        return ""
    return text[:80]


def is_plausible_quii_header(
    packet_type: int,
    payload_size: int,
    raw_size: int,
    body_available: int,
) -> bool:
    if packet_type not in VALID_PACKET_TYPES:
        return False
    if payload_size < 0 or raw_size < 0:
        return False
    if payload_size > body_available:
        return False
    if raw_size > max(payload_size, body_available):
        return False
    return True


def select_media_payload(
    raw_payload: bytes,
    decrypted_payload: bytes,
) -> tuple[bytes, bool, int, int]:
    raw_score = score_media_payload(raw_payload)
    decrypt_score = score_media_payload(decrypted_payload)
    if decrypt_score > raw_score:
        return decrypted_payload, True, raw_score, decrypt_score
    return raw_payload, False, raw_score, decrypt_score


def score_media_payload(payload: bytes) -> int:
    score = 0
    for frame in iter_quii_media_frames(payload)[:4]:
        bitstream = frame.get("bitstream", b"")
        nal_offset = int(frame.get("nal_offset", -1))
        if not isinstance(bitstream, bytes) or nal_offset < 0:
            continue
        analysis = analyze_annexb_h264(bitstream[nal_offset:])
        if analysis.get("false_positive_sps_only"):
            score -= 300
        if analysis.get("has_pps"):
            score += 120
        if analysis.get("has_idr"):
            score += 120
        if analysis.get("has_sps"):
            score += 60
        if analysis.get("has_vcl"):
            score += 40
        score += min(int(analysis.get("nal_count", 0)), 8)
    return score


def decode_candidate_summary(
    *,
    offset: int,
    header: QuiiHeader,
    decoded: dict,
) -> dict[str, object]:
    return {
        "offset": offset,
        "packet_type": hex(header.packet_type),
        "payload_size": header.payload_size,
        "raw_size": header.raw_size,
        "flag15": header.flag15,
        "flag16": header.flag16,
        "flag17": header.flag17,
        "is_media": decoded["is_media"],
        "payload_prefix": decoded["payload"][:24].hex(),
        "text_preview": decoded["text_preview"],
    }
