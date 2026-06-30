from collections.abc import Mapping
from typing import Any, cast

from quii_helper.models.packets import PacketMeta
from quii_helper.preview.fragments.fragment_summary_state import (
    active_fragmented_media_summary,
    fragmented_media_summary,
)

QUII_HEADER_SIZE = 0x20

__all__ = [
    "QUII_HEADER_SIZE",
    "active_fragmented_media_summary",
    "buffer_chained_packet",
    "chained_packet_summary",
    "chained_remainder_meta",
    "decoded_needs_more_data",
    "decoded_remainder",
    "fragment_key",
    "fragmented_media_summary",
    "increment_packet_stat",
    "is_short_quii_blob",
    "packet_payload_context",
    "prepend_buffered_packet_prefix",
    "record_chained_remainder_split",
    "should_stop_media_collection",
    "should_stop_packet_processing",
]


def _int_value(value: object, default: int = 0) -> int:
    if isinstance(value, int | str | bytes):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
    return default


def packet_payload_context(
    packet: Mapping[str, object],
) -> tuple[bytes, str, PacketMeta]:
    payload = packet["payload"]
    meta = packet.get("meta", {})
    return (
        payload if isinstance(payload, bytes) else bytes(cast(Any, payload)),
        str(packet.get("source", "unknown")),
        cast(PacketMeta, dict(meta) if isinstance(meta, Mapping) else {}),
    )


def is_short_quii_blob(blob: bytes) -> bool:
    return len(blob) < QUII_HEADER_SIZE


def fragment_key(
    *, source: str, meta: Mapping[str, object]
) -> tuple[object, ...]:
    src_id = meta.get("src_id")
    dest_id = meta.get("dest_id")
    if src_id is not None or dest_id is not None:
        return ("rb_data", src_id, dest_id)
    from_msg_index = meta.get("from_msg_index")
    if from_msg_index is not None:
        return ("remainder", from_msg_index)
    return ("global", source)


def decoded_needs_more_data(decoded: Mapping[str, object]) -> bool:
    read_size = _int_value(decoded.get("read_size"))
    body_available = _int_value(decoded.get("body_available"))
    return read_size > body_available


def decoded_remainder(decoded: Mapping[str, object], blob: bytes) -> bytes:
    if not decoded.get("plausible"):
        return b""
    consumed = (
        _int_value(decoded.get("offset"))
        + QUII_HEADER_SIZE
        + _int_value(decoded.get("read_size"))
    )
    if consumed <= 0 or consumed >= len(blob):
        return b""
    return blob[consumed:]


def should_stop_media_collection(
    *,
    media_message_count: int,
    min_media_messages: int,
    max_media_messages: int,
    decodable_h264_context: bool,
) -> bool:
    if media_message_count >= max_media_messages:
        return True
    if media_message_count < min_media_messages:
        return False
    return bool(decodable_h264_context)


def should_stop_packet_processing(*, phase: str, stop_media: bool) -> bool:
    return phase == "live" and bool(stop_media)


def chained_remainder_meta(
    meta: Mapping[str, object],
    *,
    message_index: int,
    chain_index: int,
    remainder_len: int,
) -> PacketMeta:
    return cast(
        PacketMeta,
        {
            **dict(meta),
            "from_chained_msg_index": message_index,
            "chained_packet": chain_index,
            "remainder_len": remainder_len,
        },
    )


def chained_packet_summary(
    stats: Mapping[str, int],
    buffers: Mapping[tuple[object, ...], bytes],
) -> dict[str, int]:
    return {
        **stats,
        "buffered_streams": len(buffers),
        "buffered_bytes": sum(len(value) for value in buffers.values()),
    }


def increment_packet_stat(
    stats: dict[str, int],
    key: str,
    amount: int = 1,
) -> None:
    stats[key] = int(stats.get(key, 0)) + amount


def prepend_buffered_packet_prefix(
    buffers: dict[tuple[object, ...], bytes],
    stats: dict[str, int],
    key: tuple[object, ...],
    blob: bytes,
) -> bytes:
    pending = buffers.pop(key, b"")
    if not pending:
        return blob
    increment_packet_stat(stats, "buffered_prefixes")
    increment_packet_stat(stats, "buffered_prefix_bytes", len(pending))
    return pending + blob


def record_chained_remainder_split(
    stats: dict[str, int],
    *,
    remainder_len: int,
) -> None:
    increment_packet_stat(stats, "split_remainders")
    increment_packet_stat(stats, "split_remainder_bytes", remainder_len)


def buffer_chained_packet(
    buffers: dict[tuple[object, ...], bytes],
    stats: dict[str, int],
    key: tuple[object, ...],
    blob: bytes,
    *,
    reason: str,
) -> None:
    buffers[key] = bytes(blob)
    increment_packet_stat(stats, "buffered_packets")
    increment_packet_stat(stats, "buffered_packet_bytes", len(blob))
    increment_packet_stat(stats, f"buffered_{reason}")
