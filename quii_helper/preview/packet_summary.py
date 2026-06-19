from typing import Any


def build_quii_packet_summary(
    decoded: dict,
    *,
    message_index: int,
    source: str,
    blob_len: int,
    meta: dict[str, Any] | None = None,
    decode_candidates: list[dict] | None = None,
    wrapped_tail_analysis: dict | None = None,
    fragment_partial_analysis: dict | None = None,
    fragmented_media: dict | None = None,
) -> dict:
    header = decoded["header"]
    summary = {
        "msg_index": message_index,
        "source": source,
        "blob_len": blob_len,
        "packet_type": hex(header.packet_type),
        "payload_size": header.payload_size,
        "raw_size": header.raw_size,
        "flag15": header.flag15,
        "flag16": header.flag16,
        "flag17": header.flag17,
        "is_media": decoded["is_media"],
        "plausible": decoded["plausible"],
        "offset": decoded["offset"],
        "payload_prefix": decoded["payload"][:32].hex(),
    }
    if meta:
        summary["meta"] = meta
    if decoded["text_preview"]:
        summary["text_preview"] = decoded["text_preview"]
    if decoded["is_media"]:
        summary["media_payload_offset"] = decoded.get(
            "media_payload_offset", 0
        )
        summary["media_encrypted"] = decoded.get("media_encrypted", False)
        summary["media_command_part_len"] = decoded.get(
            "media_command_part_len", 0
        )
        summary["media_decrypt_candidate_len"] = decoded.get(
            "media_decrypt_candidate_len", 0
        )
        summary["media_decrypt_len"] = decoded.get("media_decrypt_len", 0)
        summary["media_decrypt_applied"] = decoded.get(
            "media_decrypt_applied", False
        )
        summary["media_decrypt_selected"] = decoded.get(
            "media_decrypt_selected", False
        )
        summary["media_raw_score"] = decoded.get("media_raw_score", 0)
        summary["media_decrypt_score"] = decoded.get("media_decrypt_score", 0)
    if decode_candidates:
        summary["decode_candidates"] = decode_candidates[:6]
    if wrapped_tail_analysis is not None:
        summary["wrapped_tail_analysis"] = wrapped_tail_analysis
    if fragment_partial_analysis is not None:
        summary["fragment_partial_analysis"] = fragment_partial_analysis
    if fragmented_media is not None:
        summary["fragmented_media"] = fragmented_media
    return summary


def attach_media_frame_summary(summary: dict, decoded: dict) -> bool:
    frames = decoded.get("media_frames")
    if not isinstance(frames, list):
        frame = decoded.get("media_frame")
        frames = [frame] if isinstance(frame, dict) else []
    frames = [frame for frame in frames if isinstance(frame, dict)]
    if not frames:
        return False

    frame = frames[0]
    summary["media_frame_count"] = len(frames)
    summary["frame_tag"] = hex(frame["frame_tag"])
    summary["frame_len"] = frame["frame_len"]
    summary["frame_stamp"] = frame["frame_stamp"]
    summary["width"] = frame["width"]
    summary["height"] = frame["height"]
    if len(frames) > 1:
        summary["frame_tags"] = [
            hex(int(item["frame_tag"])) for item in frames[:8]
        ]
    return True
