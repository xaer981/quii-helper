from pathlib import Path
from typing import Any

from quii_helper.io.paths import DATA_DIR, resolve_data_path


def h264_output_paths(
    base_name: str | Path,
    *,
    output_dir: Path = DATA_DIR,
) -> tuple[Path, Path, Path]:
    base_path = Path(base_name)
    if not base_path.is_absolute():
        base_path = output_dir / base_path
    base_path = resolve_data_path(base_path)
    return (
        base_path.with_suffix(".h264"),
        base_path.with_suffix(".mp4"),
        base_path.with_suffix(".jpg"),
    )


def input_fps_for_target_duration(
    *, frame_count: int, target_duration_seconds: float | None
) -> float | None:
    if (
        target_duration_seconds is None
        or target_duration_seconds <= 0
        or frame_count <= 0
    ):
        return None
    # ffmpeg timestamps raw H.264 by frame intervals,
    # so N frames span N-1 intervals.
    intervals = max(frame_count - 1, 1)
    return max(intervals / target_duration_seconds, 0.001)


def should_remove_raw_h264(
    *, mp4_ok: bool, snapshot_ok: bool, keep_raw_h264: bool
) -> bool:
    return bool((mp4_ok or snapshot_ok) and not keep_raw_h264)


def empty_h264_stream_result(
    *,
    stream_path: Path,
    mp4_path: Path,
    snapshot_path: Path,
    frames: list[dict],
    summary: dict,
    keep_raw_h264: bool,
) -> dict:
    return {
        "stream_path": str(stream_path.resolve()) if keep_raw_h264 else "",
        "mp4_path": str(mp4_path.resolve()),
        "snapshot_path": str(snapshot_path.resolve()),
        "frames": frames,
        "summary": summary,
        "written": False,
        "mp4": False,
        "snapshot": False,
    }


def h264_stream_result_payload(
    *,
    stream_path: Path,
    mp4_path: Path,
    snapshot_path: Path,
    frames: list[dict],
    summary: dict[str, Any],
    keep_raw_h264: bool,
    mp4_ok: bool,
    mp4_error: str,
    snapshot_ok: bool,
    snapshot_error: str,
    ffmpeg_skipped_reason: str,
) -> dict:
    return {
        "stream_path": str(stream_path.resolve()) if keep_raw_h264 else "",
        "mp4_path": str(mp4_path.resolve()),
        "snapshot_path": str(snapshot_path.resolve()),
        "frames": frames,
        "summary": summary,
        "written": True,
        "mp4": mp4_ok,
        "mp4_error": mp4_error,
        "snapshot": snapshot_ok,
        "snapshot_error": snapshot_error,
        "ffmpeg_skipped_reason": ffmpeg_skipped_reason,
    }
