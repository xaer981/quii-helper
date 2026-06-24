from dataclasses import dataclass

from quii_helper.preview.outputs.manager.artifacts import (
    PreviewArtifactManager,
)
from quii_helper.preview.processing.payloads.diagnostics import (
    direct_blob_decode_candidates,
    record_direct_blob_sample,
    wrapped_tail_diagnostics,
)


@dataclass(frozen=True)
class PreviewPacketDiagnostics:
    decode_candidates: list[dict]
    wrapped_tail_analysis: dict | None


def collect_packet_diagnostics(
    *,
    artifacts: PreviewArtifactManager,
    blob: bytes,
    key: str,
    decoded: dict,
    message_index: int,
    source: str,
    meta: dict,
    phase: str,
) -> PreviewPacketDiagnostics:
    if not artifacts.diagnostics_enabled:
        return PreviewPacketDiagnostics(
            decode_candidates=[],
            wrapped_tail_analysis=None,
        )

    candidates = direct_blob_decode_candidates(
        blob=blob,
        key=key,
        source=source,
        decoded=decoded,
        phase=phase,
    )
    record_direct_blob_sample(
        artifacts=artifacts,
        blob=blob,
        message_index=message_index,
        source=source,
        meta=meta,
        candidates=candidates,
        phase=phase,
    )
    tail_analysis = wrapped_tail_diagnostics(
        artifacts=artifacts,
        blob=blob,
        key=key,
        decoded=decoded,
        message_index=message_index,
        source=source,
        meta=meta,
        phase=phase,
    )
    return PreviewPacketDiagnostics(
        decode_candidates=candidates,
        wrapped_tail_analysis=tail_analysis,
    )
