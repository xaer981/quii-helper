import subprocess
from pathlib import Path

from quii_helper.media.h264.io.ffmpeg_state import (
    decodable_mp4_skip_reason,
    ffmpeg_input_rate_args,
    h264_mp4_command,
    h264_snapshot_command,
    mp4_skip_reason,
    path_written,
    raw_h264_input_args,
    snapshot_input_args,
)


def _run_ffmpeg(command: list[str]) -> tuple[bool, str]:
    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
        return True, ""
    except subprocess.CalledProcessError as exc:
        return False, (exc.stderr or str(exc)).strip()
    except Exception as exc:
        return False, str(exc)


def write_h264_mp4(
    stream_path: Path, mp4_path: Path, nal_analysis: dict
) -> tuple[bool, str, str]:
    skipped_reason = mp4_skip_reason(nal_analysis)
    if skipped_reason:
        return False, "", skipped_reason
    ok, error = _run_ffmpeg(h264_mp4_command(stream_path, mp4_path))
    return ok and path_written(mp4_path), error, ""


def write_h264_mp4_if_decodable(
    stream_path: Path,
    mp4_path: Path,
    h264_analysis: dict,
    *,
    input_fps: float | None = None,
) -> tuple[bool, str, str]:
    skipped_reason = decodable_mp4_skip_reason(h264_analysis)
    if skipped_reason:
        return False, skipped_reason, skipped_reason
    ok, error = _run_ffmpeg(
        h264_mp4_command(
            stream_path,
            mp4_path,
            input_rate_args=ffmpeg_input_rate_args(input_fps),
        )
    )
    return ok and path_written(mp4_path, require_non_empty=True), error, ""


def write_h264_snapshot(
    stream_path: Path, snapshot_path: Path, ffmpeg_skipped_reason: str
) -> tuple[bool, str]:
    if ffmpeg_skipped_reason:
        return False, ffmpeg_skipped_reason
    ok, error = _run_ffmpeg(
        h264_snapshot_command(
            snapshot_path,
            input_args=raw_h264_input_args(stream_path),
        )
    )
    return ok and path_written(snapshot_path), error


def write_h264_snapshot_from_best_source(
    stream_path: Path,
    mp4_path: Path,
    snapshot_path: Path,
    *,
    mp4_ok: bool,
    ffmpeg_skipped_reason: str,
) -> tuple[bool, str]:
    if ffmpeg_skipped_reason:
        return False, ffmpeg_skipped_reason
    ok, error = _run_ffmpeg(
        h264_snapshot_command(
            snapshot_path,
            input_args=snapshot_input_args(
                stream_path,
                mp4_path,
                mp4_ok=mp4_ok,
            ),
        )
    )
    return ok and path_written(snapshot_path, require_non_empty=True), error
