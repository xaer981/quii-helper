from pathlib import Path
from typing import Any

from quii_helper.preview.outputs.manager.sample_recorder import (
    PreviewJsonlSampleRecorder,
)


def should_save_wrapped_tail_dump(
    *, diagnostics_enabled: bool, decrypted_tail: bytes
) -> bool:
    return bool(diagnostics_enabled and decrypted_tail)


def wrapped_tail_dump_path(
    dump_dir: Path,
    *,
    msg_index: int,
    source: str,
) -> Path:
    return dump_dir / f"msg_{msg_index:03d}_{source}.bin"


def direct_blob_sample_payload(
    *,
    blob: bytes,
    msg_index: int,
    source: str,
    meta: dict[str, Any],
    candidates: list[dict],
) -> dict[str, Any]:
    return {
        "msg_index": msg_index,
        "source": source,
        "meta": meta,
        "blob_len": len(blob),
        "blob_hex": blob.hex(),
        "candidates": candidates,
    }


def wrapped_tail_sample_payload(
    *,
    blob: bytes,
    msg_index: int,
    source: str,
    meta: dict[str, Any],
    analysis: dict,
) -> dict[str, Any]:
    return {
        "msg_index": msg_index,
        "source": source,
        "meta": meta,
        "analysis": analysis,
        "blob_len": len(blob),
        "blob_prefix": blob[:128].hex(),
    }


def fragment_partial_sample_payload(
    *,
    msg_index: int,
    source: str,
    meta: dict[str, Any],
    analysis: dict,
) -> dict[str, Any]:
    return {
        "msg_index": msg_index,
        "source": source,
        "meta": meta,
        "analysis": analysis,
    }


def sample_recorder(
    *,
    sample_path: Path,
    limit: int,
    enabled: bool,
    seen_hashes: set[str],
) -> PreviewJsonlSampleRecorder:
    return PreviewJsonlSampleRecorder(
        sample_path=sample_path,
        limit=limit,
        enabled=enabled,
        seen_hashes=seen_hashes,
    )
