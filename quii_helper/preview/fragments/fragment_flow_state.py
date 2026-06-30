from collections.abc import Callable, Mapping
from typing import Any, cast

from quii_helper.models.packets import (
    DecodedQuiiMessage,
    PacketMeta,
    QuiiPacketSummary,
)
from quii_helper.preview.processing.packets.capture_stats import CaptureStats
from quii_helper.preview.processing.packets.summary import (
    build_quii_packet_summary,
)
from quii_helper.preview.processing.summaries.emitter import (
    PreviewSummaryEmitter,
)

MediaMessageSink = Callable[[DecodedQuiiMessage], None]


def has_decoded_media_frames(decoded: Mapping[str, Any]) -> bool:
    frames = decoded.get("media_frames")
    if isinstance(frames, list):
        return bool(frames)
    return decoded.get("media_frame") is not None


def fragment_remainder_meta(
    meta: PacketMeta,
    *,
    message_index: int,
    remainder_len: int,
) -> PacketMeta:
    return cast(
        PacketMeta,
        {
            **meta,
            "from_msg_index": message_index,
            "remainder_len": remainder_len,
        },
    )


def short_fragment_remainder_summary(
    *,
    message_index: int,
    source: str,
    blob_len: int,
) -> dict[str, Any]:
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
    state: Mapping[str, Any],
    meta: PacketMeta,
) -> dict[str, Any]:
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
    state: Mapping[str, Any],
    meta: PacketMeta,
) -> dict[str, Any]:
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
    decoded_messages: list[DecodedQuiiMessage],
    media_messages: list[DecodedQuiiMessage],
    summary_emitter: PreviewSummaryEmitter,
    decoded: DecodedQuiiMessage,
    message_index: int,
    blob_len: int,
    source: str,
    meta: PacketMeta,
    media_message_sink: MediaMessageSink | None = None,
    store_media_messages: bool = True,
) -> None:
    summary: QuiiPacketSummary = build_quii_packet_summary(
        decoded,
        message_index=message_index,
        source=source,
        blob_len=blob_len,
        meta=meta,
        fragmented_media=cast(
            dict[str, Any], decoded.get("fragmented_media", {})
        ),
    )
    CaptureStats(
        decoded_messages=decoded_messages,
        media_messages=media_messages,
        media_message_sink=media_message_sink,
        store_media_messages=store_media_messages,
    ).record_processed_packet(summary=summary, decoded=decoded, phase="live")
    summary_emitter.emit_packet_summary(
        summary, source=source, decoded=decoded
    )
