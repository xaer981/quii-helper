from pathlib import Path

from quii_helper.io.paths import DATA_DIR, resolve_data_path
from quii_helper.media.assembler import assemble_h264_stream_from_messages
from quii_helper.media.h264_analysis import analyze_h264_annexb_stream
from quii_helper.media.h264_ffmpeg import (
    write_h264_mp4_if_decodable,
    write_h264_snapshot_from_best_source,
)


def write_h264_stream(
    base_name: str | Path,
    messages: list[dict],
    *,
    output_dir: Path = DATA_DIR,
    render_snapshot: bool = True,
    render_video: bool = True,
    keep_raw_h264: bool = False,
    target_duration_seconds: float | None = None,
) -> dict:
    base_path = Path(base_name)
    if not base_path.is_absolute():
        base_path = output_dir / base_path
    base_path = resolve_data_path(base_path)
    stream_path = base_path.with_suffix(".h264")
    mp4_path = base_path.with_suffix(".mp4")
    snapshot_path = base_path.with_suffix(".jpg")
    assembled_stream = assemble_h264_stream_from_messages(messages)
    summary = assembled_stream.summary

    if not assembled_stream.has_access_units:
        return {
            "stream_path": str(stream_path.resolve()) if keep_raw_h264 else "",
            "mp4_path": str(mp4_path.resolve()),
            "snapshot_path": str(snapshot_path.resolve()),
            "frames": assembled_stream.frames,
            "summary": summary,
            "written": False,
            "mp4": False,
            "snapshot": False,
        }

    stream_bytes = assembled_stream.stream_bytes
    stream_path.write_bytes(stream_bytes)
    h264_analysis = analyze_h264_annexb_stream(stream_bytes)
    summary["h264_annexb"] = h264_analysis

    mp4_ok = False
    mp4_error = ""
    ffmpeg_skipped_reason = ""
    if render_video:
        input_fps = _input_fps_for_target_duration(
            frame_count=int(summary.get("assembled_units", 0)),
            target_duration_seconds=target_duration_seconds,
        )
        mp4_ok, mp4_error, ffmpeg_skipped_reason = write_h264_mp4_if_decodable(
            stream_path,
            mp4_path,
            h264_analysis,
            input_fps=input_fps,
        )

    snapshot_ok = False
    snapshot_error = ""
    if render_snapshot:
        snapshot_ok, snapshot_error = write_h264_snapshot_from_best_source(
            stream_path,
            mp4_path,
            snapshot_path,
            mp4_ok=mp4_ok,
            ffmpeg_skipped_reason=ffmpeg_skipped_reason,
        )

    if (mp4_ok or snapshot_ok) and not keep_raw_h264:
        try:
            stream_path.unlink(missing_ok=True)
        except Exception:
            pass

    return {
        "stream_path": str(stream_path.resolve()) if keep_raw_h264 else "",
        "mp4_path": str(mp4_path.resolve()),
        "snapshot_path": str(snapshot_path.resolve()),
        "frames": assembled_stream.frames,
        "summary": summary,
        "written": True,
        "mp4": mp4_ok,
        "mp4_error": mp4_error,
        "snapshot": snapshot_ok,
        "snapshot_error": snapshot_error,
        "ffmpeg_skipped_reason": ffmpeg_skipped_reason,
    }


def _input_fps_for_target_duration(
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
