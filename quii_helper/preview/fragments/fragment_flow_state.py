from typing import Any

from quii_helper.preview.processing.packets.summary import (
    attach_media_frame_summary,
    build_quii_packet_summary,
)


def has_decoded_media_frames(decoded: dict) -> bool:
    frames = decoded.get("media_frames")
    if isinstance(frames, list):
        return bool(frames)
    return decoded.get("media_frame") is not None


def fragment_remainder_meta(
    meta: dict,
    *,
    message_index: int,
    remainder_len: int,
) -> dict:
    return {
        **meta,
        "from_msg_index": message_index,
        "remainder_len": remainder_len,
    }


def short_fragment_remainder_summary(
    *,
    message_index: int,
    source: str,
    blob_len: int,
) -> dict:
    return {
        "msg_index": message_index,
        "source": source,
        "fragmented_media": "drop_short_remainder",
        "blob_len": blob_len,
    }


def fragment_start_summary(
    *,
    message_index: int,
    source: str,
    blob_len: int,
    fragment_key: tuple[object, ...],
    state: dict,
    meta: dict,
) -> dict:
    return {
        "msg_index": message_index,
        "source": source,
        "blob_len": blob_len,
        "fragmented_media": "start",
        "fragment_key": fragment_key,
        "expected_body_len": state["expected_body_len"],
        "have_body_len": len(state["body"]),
        "packet_type": hex(state["packet_type"]),
        "raw_size": state["raw_size"],
        "frame_tag": hex(state["frame_tag"]),
        "frame_len": state["frame_len"],
        "meta": meta,
    }


def drop_active_fragment_summary(
    *,
    message_index: int,
    source: str,
    blob_len: int,
    reason: str,
    fragment_key: tuple[object, ...],
    state: dict,
    meta: dict,
) -> dict:
    expected_body_len = int(state.get("expected_body_len", 0))
    body = state.get("body", b"")
    have_body_len = len(body) if isinstance(body, (bytes, bytearray)) else 0
    return {
        "msg_index": message_index,
        "source": source,
        "blob_len": blob_len,
        "fragmented_media": "drop_active",
        "reason": reason,
        "fragment_key": fragment_key,
        "start_msg_index": state.get("start_msg_index"),
        "state_source": state.get("source"),
        "fragments": state.get("fragments"),
        "expected_body_len": expected_body_len,
        "have_body_len": have_body_len,
        "missing_body_len": max(0, expected_body_len - have_body_len),
        "meta": meta,
    }


def record_fragmented_media_decoded(
    *,
    decoded_messages: list[dict],
    media_messages: list[dict],
    summary_emitter: Any,
    decoded: dict,
    message_index: int,
    blob_len: int,
    source: str,
    meta: dict,
) -> None:
    if decoded["plausible"]:
        decoded_messages.append(decoded)
    summary = build_quii_packet_summary(
        decoded,
        message_index=message_index,
        source=source,
        blob_len=blob_len,
        meta=meta,
        fragmented_media=decoded.get("fragmented_media", {}),
    )
    if attach_media_frame_summary(summary, decoded):
        media_messages.append(decoded)
    summary_emitter.emit_packet_summary(
        summary, source=source, decoded=decoded
    )
