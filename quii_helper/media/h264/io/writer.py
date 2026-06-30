from pathlib import Path
from typing import Any

from quii_helper.io.paths import DATA_DIR
from quii_helper.media.frames.assembler import (
    assemble_h264_stream_from_messages,
)
from quii_helper.media.h264.core.analysis import analyze_h264_annexb_stream
from quii_helper.media.h264.io.ffmpeg import (
    write_h264_mp4_if_decodable,
    write_h264_snapshot_from_best_source,
)
from quii_helper.media.h264.io.writer_state import (
    empty_h264_stream_result,
    h264_output_paths,
    h264_stream_result_payload,
    input_fps_for_target_duration,
    should_remove_raw_h264,
)
from quii_helper.models.capture import MediaArtifactSummary
from quii_helper.support.errors import MediaRenderError


def write_h264_stream(
    base_name: str | Path,
    messages: list[dict[str, Any]],
    *,
    output_dir: Path = DATA_DIR,
    render_snapshot: bool = True,
    render_video: bool = True,
    keep_raw_h264: bool = False,
    target_duration_seconds: float | None = None,
) -> MediaArtifactSummary:
    stream_path, mp4_path, snapshot_path = h264_output_paths(
        base_name,
        output_dir=output_dir,
    )
    assembled_stream = assemble_h264_stream_from_messages(messages)
    summary = assembled_stream.summary

    if not assembled_stream.has_access_units:
        return empty_h264_stream_result(
            stream_path=stream_path,
            mp4_path=mp4_path,
            snapshot_path=snapshot_path,
            frames=assembled_stream.frames,
            summary=summary,
            keep_raw_h264=keep_raw_h264,
        )

    stream_bytes = assembled_stream.stream_bytes
    _write_stream_bytes(stream_path, stream_bytes)
    h264_analysis = analyze_h264_annexb_stream(stream_bytes)
    summary["h264_annexb"] = h264_analysis

    mp4_ok = False
    mp4_error = ""
    ffmpeg_skipped_reason = ""
    if render_video:
        input_fps = input_fps_for_target_duration(
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

    if should_remove_raw_h264(
        mp4_ok=mp4_ok,
        snapshot_ok=snapshot_ok,
        keep_raw_h264=keep_raw_h264,
    ):
        try:
            stream_path.unlink(missing_ok=True)
        except Exception:
            pass

    return h264_stream_result_payload(
        stream_path=stream_path,
        mp4_path=mp4_path,
        snapshot_path=snapshot_path,
        frames=assembled_stream.frames,
        summary=summary,
        keep_raw_h264=keep_raw_h264,
        mp4_ok=mp4_ok,
        mp4_error=mp4_error,
        snapshot_ok=snapshot_ok,
        snapshot_error=snapshot_error,
        ffmpeg_skipped_reason=ffmpeg_skipped_reason,
    )


def _write_stream_bytes(stream_path: Path, stream_bytes: bytes) -> None:
    try:
        stream_path.write_bytes(stream_bytes)
    except OSError as exc:
        raise MediaRenderError(
            f"unable to write raw H.264 stream {stream_path}: {exc}"
        ) from exc
