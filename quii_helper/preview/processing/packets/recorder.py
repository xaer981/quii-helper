from dataclasses import dataclass

from quii_helper.models.packets import (
    DecodedQuiiMessage,
    PacketMeta,
    QuiiPacketSummary,
)
from quii_helper.preview.processing.packets.capture_stats import CaptureStats
from quii_helper.preview.processing.packets.diagnostics_collector import (
    PacketDiagnosticsCollector,
)
from quii_helper.preview.processing.packets.summary import (
    build_quii_packet_summary,
)
from quii_helper.preview.processing.summaries.emitter import (
    PreviewSummaryEmitter,
)


@dataclass(frozen=True)
class DecodedPacketRecorder:
    """Record decoded packet output and diagnostics in one place."""

    diagnostics_collector: PacketDiagnosticsCollector
    capture_stats: CaptureStats
    summary_emitter: PreviewSummaryEmitter

    def record(
        self,
        *,
        blob: bytes,
        decoded: DecodedQuiiMessage,
        message_index: int,
        source: str,
        meta: PacketMeta,
        phase: str,
    ) -> QuiiPacketSummary:
        diagnostics = self.diagnostics_collector.collect(
            blob=blob,
            decoded=decoded,
            message_index=message_index,
            source=source,
            meta=meta,
            phase=phase,
        )
        summary = build_quii_packet_summary(
            decoded,
            message_index=message_index,
            source=source,
            blob_len=len(blob),
            meta=meta,
            decode_candidates=diagnostics.decode_candidates,
            wrapped_tail_analysis=diagnostics.wrapped_tail_analysis,
            fragment_partial_analysis=diagnostics.fragment_partial_analysis,
        )
        self.capture_stats.record_processed_packet(
            summary=summary,
            decoded=decoded,
            phase=phase,
        )
        self.summary_emitter.emit_packet_summary(
            summary,
            source=source,
            decoded=decoded,
        )
        return summary
