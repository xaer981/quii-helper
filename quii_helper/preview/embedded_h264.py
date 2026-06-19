import hashlib
from pathlib import Path

from quii_helper.io.output_paths import data_base_path
from quii_helper.media.annexb_merge import (
    merge_annexb_candidates,
    merge_two_streams,
)
from quii_helper.media.annexb_probe_analysis import analyze_annexb_h264
from quii_helper.media.h264_ffmpeg import write_h264_mp4, write_h264_snapshot


def write_embedded_h264_fallback(
    base_name: str | Path, annexb_blobs: list[bytes]
) -> dict:
    base_path = data_base_path(base_name)
    stream_path = base_path.with_name(f"{base_path.name}_embedded.h264")
    mp4_path = base_path.with_name(f"{base_path.name}_embedded.mp4")
    snapshot_path = base_path.with_name(f"{base_path.name}_embedded.jpg")
    persistent_path = base_path.with_name(
        f"{base_path.name}_embedded_best.h264"
    )

    unique, selected, strategy = merge_annexb_candidates(annexb_blobs)
    persistent_before = _read_existing(persistent_path)
    selected, persistent_strategy = merge_two_streams(
        persistent_before, selected
    )

    if not unique:
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
            "stream_path": str(stream_path.resolve()),
            "mp4_path": str(mp4_path.resolve()),
            "snapshot_path": str(snapshot_path.resolve()),
            "persistent_path": str(persistent_path.resolve()),
        }

    nal_analysis = analyze_annexb_h264(selected)
    stream_path.write_bytes(selected)

    persistent_written = False
    if not nal_analysis.get("false_positive_sps_only"):
        try:
            persistent_path.write_bytes(selected)
            persistent_written = True
        except Exception:
            persistent_written = False

    mp4_ok, mp4_error, ffmpeg_skipped_reason = write_h264_mp4(
        stream_path, mp4_path, nal_analysis
    )
    snapshot_ok, snapshot_error = write_h264_snapshot(
        stream_path, snapshot_path, ffmpeg_skipped_reason
    )

    return {
        "candidate_count": len(unique),
        "merge_strategy": strategy,
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
        "stream_path": str(stream_path.resolve()),
        "mp4_path": str(mp4_path.resolve()),
        "snapshot_path": str(snapshot_path.resolve()),
        "persistent_path": str(persistent_path.resolve()),
    }


def _read_existing(path: Path) -> bytes:
    if not path.exists():
        return b""
    try:
        return path.read_bytes()
    except Exception:
        return b""
