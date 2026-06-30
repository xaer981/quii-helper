from typing import Any, cast

from quii_helper.diagnostics.wrapped.tail.analysis import (
    analyze_wrapped_quii_tail,
    decrypt_wrapped_quii_tail_bytes,
)
from quii_helper.models.packets import DecodedQuiiMessage, PacketMeta
from quii_helper.preview.outputs.manager.artifacts import (
    PreviewArtifactManager,
)
from quii_helper.preview.processing.payloads.diagnostics_state import (
    should_analyze_wrapped_tail,
    should_find_direct_blob_candidates,
    should_record_direct_blob_sample,
)
from quii_helper.protocols.quii.blob import find_quii_decode_candidates


def direct_blob_decode_candidates(
    *,
    blob: bytes,
    key: str,
    source: str,
    decoded: DecodedQuiiMessage,
    phase: str,
) -> list[dict[str, Any]]:
    if not should_find_direct_blob_candidates(
        source=source,
        decoded=decoded,
        phase=phase,
    ):
        return []
    return find_quii_decode_candidates(blob, key, crypto_mode=2)


def record_direct_blob_sample(
    *,
    artifacts: PreviewArtifactManager,
    blob: bytes,
    message_index: int,
    source: str,
    meta: PacketMeta,
    candidates: list[dict[str, Any]],
    phase: str,
) -> None:
    if not should_record_direct_blob_sample(source=source, phase=phase):
        return
    artifacts.record_direct_blob_sample(
        blob=blob,
        msg_index=message_index,
        source=source,
        meta=cast(dict[str, Any], meta),
        candidates=candidates,
    )


def wrapped_tail_diagnostics(
    *,
    artifacts: PreviewArtifactManager,
    blob: bytes,
    key: str,
    decoded: DecodedQuiiMessage,
    message_index: int,
    source: str,
    meta: PacketMeta,
    phase: str,
) -> dict[str, Any] | None:
    if not should_analyze_wrapped_tail(
        source=source,
        decoded=decoded,
        phase=phase,
    ):
        return None

    decoded_dict = cast(dict[Any, Any], decoded)
    analysis = analyze_wrapped_quii_tail(blob, key, decoded_dict)
    if analysis is None:
        return None

    decrypted_tail = decrypt_wrapped_quii_tail_bytes(blob, key, decoded_dict)
    dump_path = artifacts.save_wrapped_tail_dump(
        decrypted_tail=decrypted_tail,
        msg_index=message_index,
        source=source,
    )
    if dump_path is not None:
        analysis["decrypted_dump_path"] = str(dump_path)
    artifacts.record_wrapped_tail_sample(
        blob=blob,
        msg_index=message_index,
        source=source,
        meta=cast(dict[str, Any], meta),
        analysis=analysis,
    )
    return analysis
