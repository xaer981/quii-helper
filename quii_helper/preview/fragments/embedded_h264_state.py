import hashlib
from pathlib import Path
from typing import Any

from quii_helper.io.output_paths import data_base_path


def embedded_h264_paths(base_name: str | Path) -> dict[str, Path]:
    base_path = data_base_path(base_name)
    return {
        "stream_path": base_path.with_name(f"{base_path.name}_embedded.h264"),
        "mp4_path": base_path.with_name(f"{base_path.name}_embedded.mp4"),
        "snapshot_path": base_path.with_name(f"{base_path.name}_embedded.jpg"),
        "persistent_path": base_path.with_name(
            f"{base_path.name}_embedded_best.h264"
        ),
    }


def should_write_persistent_embedded(nal_analysis: dict[str, Any]) -> bool:
    return not bool(nal_analysis.get("false_positive_sps_only"))


def empty_embedded_h264_result(
    *,
    paths: dict[str, Path],
    persistent_before: bytes,
) -> dict:
    return {
        "candidate_count": 0,
        "merge_strategy": "none",
        "persistent_merge_strategy": "none",
        "candidate_lens": [],
        "persistent_previous_len": len(persistent_before),
        "selected_len": 0,
        "written": False,
        "mp4": False,
        "snapshot": False,
        "stream_path": str(paths["stream_path"].resolve()),
        "mp4_path": str(paths["mp4_path"].resolve()),
        "snapshot_path": str(paths["snapshot_path"].resolve()),
        "persistent_path": str(paths["persistent_path"].resolve()),
    }


def embedded_h264_result_payload(
    *,
    unique: list[bytes],
    selected: bytes,
    merge_strategy: str,
    persistent_strategy: str,
    persistent_before: bytes,
    nal_analysis: dict,
    persistent_written: bool,
    mp4_ok: bool,
    mp4_error: str,
    snapshot_ok: bool,
    snapshot_error: str,
    ffmpeg_skipped_reason: str,
    paths: dict[str, Path],
) -> dict:
    return {
        "candidate_count": len(unique),
        "merge_strategy": merge_strategy,
        "persistent_merge_strategy": persistent_strategy,
        "candidate_lens": [len(blob) for blob in unique],
        "persistent_previous_len": len(persistent_before),
        "selected_len": len(selected),
        "selected_sha1": hashlib.sha1(selected).hexdigest(),
        "nal_analysis": nal_analysis,
        "written": True,
        "persistent_written": persistent_written,
        "mp4": mp4_ok,
        "mp4_error": mp4_error,
        "snapshot": snapshot_ok,
        "snapshot_error": snapshot_error,
        "ffmpeg_skipped_reason": ffmpeg_skipped_reason,
        "stream_path": str(paths["stream_path"].resolve()),
        "mp4_path": str(paths["mp4_path"].resolve()),
        "snapshot_path": str(paths["snapshot_path"].resolve()),
        "persistent_path": str(paths["persistent_path"].resolve()),
    }
