from dataclasses import dataclass
from typing import Any

from quii_helper.models.packets import DecodedQuiiMessage, PacketMeta
from quii_helper.preview.fragments.collectors import FragmentPartialCollector
from quii_helper.preview.outputs.manager.artifacts import (
    PreviewArtifactManager,
)
from quii_helper.preview.processing.packets.diagnostics import (
    collect_packet_diagnostics,
)


@dataclass(frozen=True)
class PacketDiagnosticsResult:
    """Diagnostics produced while handling a decoded QUII packet."""

    decode_candidates: list[dict[str, Any]]
    wrapped_tail_analysis: dict[str, Any] | None
    fragment_partial_analysis: dict[str, Any] | None


@dataclass(frozen=True)
class PacketDiagnosticsCollector:
    """Collect optional packet diagnostics outside the production decode path."""

    key: str
    artifacts: PreviewArtifactManager
    fragment_partial_collector: FragmentPartialCollector

    def collect(
        self,
        *,
        blob: bytes,
        decoded: DecodedQuiiMessage,
        message_index: int,
        source: str,
        meta: PacketMeta,
        phase: str,
    ) -> PacketDiagnosticsResult:
        diagnostics = collect_packet_diagnostics(
            artifacts=self.artifacts,
            blob=blob,
            key=self.key,
            decoded=decoded,
            message_index=message_index,
            source=source,
            meta=meta,
            phase=phase,
        )
        fragment_partial_analysis = self.fragment_partial_collector.analyze(
            blob,
            source=source,
            meta=meta,
            message_index=message_index,
        )
        return PacketDiagnosticsResult(
            decode_candidates=diagnostics.decode_candidates,
            wrapped_tail_analysis=diagnostics.wrapped_tail_analysis,
            fragment_partial_analysis=fragment_partial_analysis,
        )
