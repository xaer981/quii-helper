from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from quii_helper.media.fragmented_media import should_start_fragmented_media
from quii_helper.preview.artifacts import PreviewArtifactManager
from quii_helper.preview.collectors import FragmentPartialCollector
from quii_helper.preview.fragment_flow import PreviewFragmentFlowMixin
from quii_helper.preview.media_summary import media_collection_summary
from quii_helper.preview.packet_summary import (
    attach_media_frame_summary,
    build_quii_packet_summary,
)
from quii_helper.preview.payload_diagnostics import (
    direct_blob_decode_candidates,
    record_direct_blob_sample,
    wrapped_tail_diagnostics,
)
from quii_helper.preview.summary_emitter import PreviewSummaryEmitter
from quii_helper.protocols.quii.blob import decode_quii_blob

PacketPhase = Literal["live", "flush", "close"]
Emitter = Callable[[object], None]


@dataclass
class PreviewPacketProcessor(PreviewFragmentFlowMixin):
    key: str
    artifacts: PreviewArtifactManager
    fragment_partial_collector: FragmentPartialCollector
    emit: Emitter
    min_media_messages: int
    max_media_messages: int
    direct_blob_summary_limit: int
    decoded_messages: list[dict] = field(default_factory=list)
    media_messages: list[dict] = field(default_factory=list)
    fragmented_media_stats: dict[str, int] = field(default_factory=dict)
    chained_packet_stats: dict[str, int] = field(default_factory=dict)
    quii_packet_buffers: dict[tuple[object, ...], bytes] = field(
        default_factory=dict
    )
    message_index: int = 0
    fragmented_media_states: dict[tuple[object, ...], dict] = field(
        default_factory=dict
    )
    summary_emitter: PreviewSummaryEmitter = field(init=False)

    def __post_init__(self) -> None:
        self.summary_emitter = PreviewSummaryEmitter(
            emit=self.emit,
            direct_blob_summary_limit=self.direct_blob_summary_limit,
        )

    @property
    def implausible_direct_suppressed(self) -> int:
        return self.summary_emitter.implausible_direct_suppressed

    def process_packet(
        self, packet: dict[str, Any], *, phase: PacketPhase
    ) -> bool:
        blob = bytes(packet["payload"])
        source = str(packet.get("source", "unknown"))
        meta = dict(packet.get("meta", {}))
        chain_index = 0
        buffer_key = self._fragment_key(source=source, meta=meta)
        pending = self.quii_packet_buffers.pop(buffer_key, b"")
        if pending:
            blob = pending + blob
            self._inc_chained_packet_stat("buffered_prefixes")
            self._inc_chained_packet_stat(
                "buffered_prefix_bytes", len(pending)
            )

        while blob:
            if len(blob) < 0x20:
                self._buffer_quii_packet(
                    buffer_key, blob, reason="short_header"
                )
                return False
            try:
                should_stop, remainder = self._process_packet_blob(
                    blob, source=source, meta=meta, phase=phase
                )
            except ValueError:
                self._buffer_quii_packet(
                    buffer_key, blob, reason="decode_error"
                )
                return False
            if should_stop:
                return True
            if not remainder:
                return False
            if len(remainder) >= len(blob):
                self._inc_chained_packet_stat("invalid_remainders")
                return False

            self._inc_chained_packet_stat("split_remainders")
            self._inc_chained_packet_stat(
                "split_remainder_bytes", len(remainder)
            )
            chain_index += 1
            meta = {
                **meta,
                "from_chained_msg_index": self.message_index,
                "chained_packet": chain_index,
                "remainder_len": len(remainder),
            }
            blob = remainder

        return False

    def _process_packet_blob(
        self,
        blob: bytes,
        *,
        source: str,
        meta: dict[str, Any],
        phase: PacketPhase,
    ) -> tuple[bool, bytes]:
        self.message_index += 1

        fragment_key = self._fragment_key(source=source, meta=meta)
        if fragment_key in self.fragmented_media_states:
            fragment_result = self._consume_fragment(
                blob,
                source=source,
                meta=meta,
                phase=phase,
                fragment_key=fragment_key,
            )
            if fragment_result is None:
                return (
                    phase == "live" and self.should_stop_media_collection(),
                    b"",
                )
            blob, source, meta = fragment_result
            fragment_key = self._fragment_key(source=source, meta=meta)

        decoded = decode_quii_blob(blob, self.key, crypto_mode=2)
        if should_start_fragmented_media(decoded, source):
            self._start_fragmented_media(
                decoded,
                blob=blob,
                source=source,
                meta=meta,
                fragment_key=fragment_key,
            )
            return False, b""
        if self._decoded_needs_more_data(decoded):
            self._buffer_quii_packet(
                fragment_key, blob, reason="incomplete_packet"
            )
            return False, b""

        candidates = direct_blob_decode_candidates(
            blob=blob,
            key=self.key,
            source=source,
            decoded=decoded,
            phase=phase,
        )
        record_direct_blob_sample(
            artifacts=self.artifacts,
            blob=blob,
            message_index=self.message_index,
            source=source,
            meta=meta,
            candidates=candidates,
            phase=phase,
        )

        fragment_partial_analysis = self._analyze_fragment_partial(
            blob,
            source=source,
            meta=meta,
        )

        if decoded["plausible"]:
            self.decoded_messages.append(decoded)

        wrapped_tail_analysis = wrapped_tail_diagnostics(
            artifacts=self.artifacts,
            blob=blob,
            key=self.key,
            decoded=decoded,
            message_index=self.message_index,
            source=source,
            meta=meta,
            phase=phase,
        )

        summary = build_quii_packet_summary(
            decoded,
            message_index=self.message_index,
            source=source,
            blob_len=len(blob),
            meta=meta,
            decode_candidates=candidates,
            wrapped_tail_analysis=wrapped_tail_analysis,
            fragment_partial_analysis=fragment_partial_analysis,
        )

        if phase == "live" and attach_media_frame_summary(summary, decoded):
            self.media_messages.append(decoded)

        self._emit_packet_summary(summary, source=source, decoded=decoded)
        return (
            phase == "live" and self.should_stop_media_collection(),
            self._decoded_remainder(decoded, blob),
        )

    def should_stop_media_collection(self) -> bool:
        if len(self.media_messages) >= self.max_media_messages:
            return True
        if len(self.media_messages) < self.min_media_messages:
            return False
        return bool(
            media_collection_summary(self.media_messages).get(
                "decodable_h264_context"
            )
        )

    def _emit_packet_summary(
        self, summary: dict, *, source: str, decoded: dict
    ) -> None:
        self.summary_emitter.emit_packet_summary(
            summary, source=source, decoded=decoded
        )

    def _decoded_remainder(self, decoded: dict, blob: bytes) -> bytes:
        if not decoded.get("plausible"):
            return b""
        try:
            consumed = (
                int(decoded.get("offset", 0))
                + 0x20
                + int(decoded.get("read_size", 0))
            )
        except (TypeError, ValueError):
            return b""
        if consumed <= 0 or consumed >= len(blob):
            return b""
        return blob[consumed:]

    def chained_packet_summary(self) -> dict[str, int]:
        return {
            **self.chained_packet_stats,
            "buffered_streams": len(self.quii_packet_buffers),
            "buffered_bytes": sum(
                len(value) for value in self.quii_packet_buffers.values()
            ),
        }

    def has_pending_live_buffers(self) -> bool:
        return bool(self.quii_packet_buffers or self.fragmented_media_states)

    def _inc_chained_packet_stat(self, key: str, amount: int = 1) -> None:
        self.chained_packet_stats[key] = (
            int(self.chained_packet_stats.get(key, 0)) + amount
        )

    def _decoded_needs_more_data(self, decoded: dict) -> bool:
        try:
            read_size = int(decoded.get("read_size", 0))
            body_available = int(decoded.get("body_available", 0))
        except (TypeError, ValueError):
            return False
        return read_size > body_available

    def _buffer_quii_packet(
        self, key: tuple[object, ...], blob: bytes, *, reason: str
    ) -> None:
        self.quii_packet_buffers[key] = bytes(blob)
        self._inc_chained_packet_stat("buffered_packets")
        self._inc_chained_packet_stat("buffered_packet_bytes", len(blob))
        self._inc_chained_packet_stat(f"buffered_{reason}")
