from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, cast

from quii_helper.media.fragments.fragmented_media import (
    should_start_fragmented_media,
)
from quii_helper.models.capture import MediaCollectionSummary
from quii_helper.models.packets import (
    DecodedQuiiMessage,
    PacketMeta,
    TunnelPacket,
)
from quii_helper.preview.fragments.collectors import FragmentPartialCollector
from quii_helper.preview.fragments.fragment_flow import (
    PreviewFragmentFlow,
    PreviewFragmentFlowOwner,
)
from quii_helper.preview.outputs.manager.artifacts import (
    PreviewArtifactManager,
)
from quii_helper.preview.processing.packets.capture_stats import CaptureStats
from quii_helper.preview.processing.packets.decoder import MediaPacketDecoder
from quii_helper.preview.processing.packets.diagnostics_collector import (
    PacketDiagnosticsCollector,
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
    should_build_media_collection_summary,
)
from quii_helper.preview.processing.packets.recorder import (
    DecodedPacketRecorder,
)
from quii_helper.preview.processing.summaries.emitter import (
    PreviewSummaryEmitter,
)
from quii_helper.preview.summaries.media_summary import (
    media_collection_summary,
)

PacketPhase = Literal["live", "flush", "close"]
Emitter = Callable[[object], None]


@dataclass
class PreviewPacketProcessor:
    key: str
    artifacts: PreviewArtifactManager
    fragment_partial_collector: FragmentPartialCollector
    emit: Emitter
    min_media_messages: int
    max_media_messages: int
    direct_blob_summary_limit: int
    decoded_messages: list[DecodedQuiiMessage] = field(default_factory=list)
    media_messages: list[DecodedQuiiMessage] = field(default_factory=list)
    media_message_sink: Callable[[DecodedQuiiMessage], None] | None = None
    store_media_messages: bool = True
    fragmented_media_stats: dict[str, int] = field(default_factory=dict)
    chained_packet_stats: dict[str, int] = field(default_factory=dict)
    quii_packet_buffers: dict[tuple[object, ...], bytes] = field(
        default_factory=dict
    )
    message_index: int = 0
    fragmented_media_states: dict[tuple[object, ...], dict[str, object]] = (
        field(default_factory=dict)
    )
    summary_emitter: PreviewSummaryEmitter = field(init=False)
    decoder: MediaPacketDecoder = field(init=False)
    diagnostics_collector: PacketDiagnosticsCollector = field(init=False)
    capture_stats: CaptureStats = field(init=False)
    fragment_flow: PreviewFragmentFlow = field(init=False)
    recorder: DecodedPacketRecorder = field(init=False)

    def __post_init__(self) -> None:
        self.decoder = MediaPacketDecoder(key=self.key)
        self.capture_stats = CaptureStats(
            decoded_messages=self.decoded_messages,
            media_messages=self.media_messages,
            media_message_sink=self.media_message_sink,
            store_media_messages=self.store_media_messages,
        )
        self.diagnostics_collector = PacketDiagnosticsCollector(
            key=self.key,
            artifacts=self.artifacts,
            fragment_partial_collector=self.fragment_partial_collector,
        )
        self.summary_emitter = PreviewSummaryEmitter(
            emit=self.emit,
            direct_blob_summary_limit=self.direct_blob_summary_limit,
        )
        self.fragment_flow = PreviewFragmentFlow(
            cast(PreviewFragmentFlowOwner, self)
        )
        self.recorder = DecodedPacketRecorder(
            diagnostics_collector=self.diagnostics_collector,
            capture_stats=self.capture_stats,
            summary_emitter=self.summary_emitter,
        )

    @property
    def implausible_direct_suppressed(self) -> int:
        return self.summary_emitter.implausible_direct_suppressed

    def process_packet(
        self, packet: TunnelPacket, *, phase: PacketPhase
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
        meta: PacketMeta,
        phase: PacketPhase,
    ) -> tuple[bool, bytes]:
        self.message_index += 1

        packet_fragment_key = fragment_key(source=source, meta=meta)
        if packet_fragment_key in self.fragmented_media_states:
            fragment_result = self.fragment_flow.consume_fragment(
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

        decoded = self.decoder.decode(blob)
        if should_start_fragmented_media(
            cast(dict[Any, Any], decoded),
            source,
        ):
            self.fragment_flow.start_fragmented_media(
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

        self.recorder.record(
            blob=blob,
            decoded=decoded,
            message_index=self.message_index,
            source=source,
            meta=meta,
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
        media_message_count = len(self.capture_stats.media_messages)
        summary: MediaCollectionSummary = {}
        if should_build_media_collection_summary(
            media_message_count=media_message_count,
            min_media_messages=self.min_media_messages,
            max_media_messages=self.max_media_messages,
        ):
            summary = media_collection_summary(
                self.capture_stats.media_messages
            )
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

    def fragmented_media_summary(self) -> dict[str, object]:
        return self.fragment_flow.fragmented_media_summary()

    def has_pending_live_buffers(self) -> bool:
        return bool(self.quii_packet_buffers or self.fragmented_media_states)
