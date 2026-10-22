from collections.abc import Callable, Container

from quii_helper.models.packets import PacketMeta
from quii_helper.preview.processing.packets.flow import (
    buffer_chained_packet,
    chained_remainder_meta,
    fragment_key,
    increment_packet_stat,
    is_short_quii_blob,
    prepend_buffered_packet_prefix,
    record_chained_remainder_split,
)
from quii_helper.support.errors import QuiiConnectionError

ProcessPacketBlob = Callable[..., tuple[bool, bytes]]
MessageIndexProvider = Callable[[], int]


def process_chained_packet_blob(
    *,
    blob: bytes,
    source: str,
    meta: PacketMeta,
    phase: str,
    buffers: dict[tuple[object, ...], bytes],
    stats: dict[str, int],
    process_blob: ProcessPacketBlob,
    message_index_provider: MessageIndexProvider,
    pending_media_keys: Container[tuple[object, ...]] = (),
) -> bool:
    chain_index = 0
    stop_requested = False
    buffer_key = fragment_key(source=source, meta=meta)
    blob = prepend_buffered_packet_prefix(buffers, stats, buffer_key, blob)

    while blob:
        if is_short_quii_blob(blob) and buffer_key not in pending_media_keys:
            buffer_chained_packet(
                buffers,
                stats,
                buffer_key,
                blob,
                reason="short_header",
            )
            return stop_requested
        try:
            should_stop, remainder = process_blob(
                blob, source=source, meta=meta, phase=phase
            )
        except ValueError as exc:
            increment_packet_stat(stats, "decode_errors")
            raise QuiiConnectionError(f"invalid QUII packet: {exc}") from exc
        # Match native OnRecv: drain complete packets before honoring capture limits.
        stop_requested = stop_requested or should_stop
        if not remainder:
            return stop_requested
        if len(remainder) >= len(blob):
            increment_packet_stat(stats, "invalid_remainders")
            return stop_requested

        record_chained_remainder_split(stats, remainder_len=len(remainder))
        chain_index += 1
        meta = chained_remainder_meta(
            meta,
            message_index=message_index_provider(),
            chain_index=chain_index,
            remainder_len=len(remainder),
        )
        blob = remainder

    return stop_requested


def should_build_media_collection_summary(
    *,
    media_message_count: int,
    min_media_messages: int,
    max_media_messages: int,
) -> bool:
    return (
        media_message_count < max_media_messages
        and media_message_count >= min_media_messages
    )
