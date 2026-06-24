from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from quii_helper.media.fragments.fragmented_media import (
    should_start_fragmented_media,
)
from quii_helper.preview.fragments.collectors import FragmentPartialCollector
from quii_helper.preview.fragments.fragment_flow import (
    PreviewFragmentFlowMixin,
)
from quii_helper.preview.outputs.manager.artifacts import (
    PreviewArtifactManager,
)
from quii_helper.preview.processing.packets.diagnostics import (
    collect_packet_diagnostics,
)
from quii_helper.preview.processing.packets.flow import (
    buffer_chained_packet,
    chained_packet_summary,
    decoded_needs_more_data,
    decoded_remainder,
    fragment_key,
    packet_payload_context,
    should_stop_media_collection,
    should_stop_packet_processing,
)
from quii_helper.preview.processing.packets.processor_state import (
    process_chained_packet_blob,
    record_processed_packet,
    should_build_media_collection_summary,
)
from quii_helper.preview.processing.packets.summary import (
    build_quii_packet_summary,
)
from quii_helper.preview.processing.summaries.emitter import (
    PreviewSummaryEmitter,
)
from quii_helper.preview.summaries.media_summary import (
    media_collection_summary,
)
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
        blob, source, meta = packet_payload_context(packet)
        return process_chained_packet_blob(
            blob=blob,
            source=source,
            meta=meta,
            phase=phase,
            buffers=self.quii_packet_buffers,
            stats=self.chained_packet_stats,
            process_blob=self._process_packet_blob,
            message_index_provider=lambda: self.message_index,
        )

    def _process_packet_blob(
        self,
        blob: bytes,
        *,
        source: str,
        meta: dict[str, Any],
        phase: PacketPhase,
    ) -> tuple[bool, bytes]:
        self.message_index += 1

        packet_fragment_key = fragment_key(source=source, meta=meta)
        if packet_fragment_key in self.fragmented_media_states:
            fragment_result = self._consume_fragment(
                blob,
                source=source,
                meta=meta,
                phase=phase,
                fragment_key=packet_fragment_key,
            )
            if fragment_result is None:
                return (
                    should_stop_packet_processing(
                        phase=phase,
                        stop_media=self.should_stop_media_collection(),
                    ),
                    b"",
                )
            blob, source, meta = fragment_result
            packet_fragment_key = fragment_key(source=source, meta=meta)

        decoded = decode_quii_blob(blob, self.key, crypto_mode=2)
        if should_start_fragmented_media(decoded, source):
            self._start_fragmented_media(
                decoded,
                blob=blob,
                source=source,
                meta=meta,
                fragment_key=packet_fragment_key,
            )
            return False, b""
        if decoded_needs_more_data(decoded):
            buffer_chained_packet(
                self.quii_packet_buffers,
                self.chained_packet_stats,
                packet_fragment_key,
                blob,
                reason="incomplete_packet",
            )
            return False, b""

        diagnostics = collect_packet_diagnostics(
            artifacts=self.artifacts,
            blob=blob,
            key=self.key,
            decoded=decoded,
            message_index=self.message_index,
            source=source,
            meta=meta,
            phase=phase,
        )

        fragment_partial_analysis = self.fragment_partial_collector.analyze(
            blob,
            source=source,
            meta=meta,
            message_index=self.message_index,
        )

        summary = build_quii_packet_summary(
            decoded,
            message_index=self.message_index,
            source=source,
            blob_len=len(blob),
            meta=meta,
            decode_candidates=diagnostics.decode_candidates,
            wrapped_tail_analysis=diagnostics.wrapped_tail_analysis,
            fragment_partial_analysis=fragment_partial_analysis,
        )

        record_processed_packet(
            decoded_messages=self.decoded_messages,
            media_messages=self.media_messages,
            summary_emitter=self.summary_emitter,
            summary=summary,
            decoded=decoded,
            source=source,
            phase=phase,
        )
        return (
            should_stop_packet_processing(
                phase=phase,
                stop_media=self.should_stop_media_collection(),
            ),
            decoded_remainder(decoded, blob),
        )

    def should_stop_media_collection(self) -> bool:
        media_message_count = len(self.media_messages)
        summary = {}
        if should_build_media_collection_summary(
            media_message_count=media_message_count,
            min_media_messages=self.min_media_messages,
            max_media_messages=self.max_media_messages,
        ):
            summary = media_collection_summary(self.media_messages)
        return should_stop_media_collection(
            media_message_count=media_message_count,
            min_media_messages=self.min_media_messages,
            max_media_messages=self.max_media_messages,
            decodable_h264_context=bool(summary.get("decodable_h264_context")),
        )

    def chained_packet_summary(self) -> dict[str, int]:
        return chained_packet_summary(
            self.chained_packet_stats, self.quii_packet_buffers
        )

    def has_pending_live_buffers(self) -> bool:
        return bool(self.quii_packet_buffers or self.fragmented_media_states)
