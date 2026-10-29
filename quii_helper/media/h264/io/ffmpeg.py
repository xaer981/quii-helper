import math
import subprocess
from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from quii_helper.media.audio.recording import AudioRecording
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
    except FileNotFoundError:
        return False, (
            "FFmpeg executable not found on PATH; install FFmpeg and verify "
            "'ffmpeg -version' before saving JPEG/MP4 files."
        )
    except Exception as exc:
        return False, str(exc)


def write_h264_mp4(
    stream_path: Path, mp4_path: Path, nal_analysis: Mapping[str, Any]
) -> tuple[bool, str, str]:
    skipped_reason = mp4_skip_reason(nal_analysis)
    if skipped_reason:
        return False, "", skipped_reason
    ok, error = _run_ffmpeg(h264_mp4_command(stream_path, mp4_path))
    return ok and path_written(mp4_path), error, ""


def write_h264_mp4_if_decodable(
    stream_path: Path,
    mp4_path: Path,
    h264_analysis: Mapping[str, Any],
    *,
    input_fps: float | None = None,
    audio: AudioRecording | None = None,
    duration_seconds: float | None = None,
) -> tuple[bool, str, str]:
    skipped_reason = decodable_mp4_skip_reason(h264_analysis)
    if skipped_reason:
        return False, skipped_reason, skipped_reason
    if audio is not None and audio.data:
        if (
            duration_seconds is None
            or not math.isfinite(duration_seconds)
            or duration_seconds <= 0
        ):
            return (
                False,
                "MP4 audio requires a finite positive video duration",
                "",
            )
        try:
            with TemporaryDirectory(
                prefix=".quii-audio-", dir=mp4_path.parent
            ) as temp:
                audio_path = Path(temp) / "audio.g711"
                audio_path.write_bytes(audio.data)
                ok, error = _run_ffmpeg(
                    h264_mp4_command(
                        stream_path,
                        mp4_path,
                        input_rate_args=ffmpeg_input_rate_args(input_fps),
                        audio_path=audio_path,
                        audio_format="alaw" if audio.codec == 4 else "mulaw",
                        audio_offset_seconds=audio.offset_seconds,
                        duration_seconds=duration_seconds,
                    )
                )
        except OSError as exc:
            return False, f"unable to prepare MP4 audio: {exc}", ""
        return ok and path_written(mp4_path, require_non_empty=True), error, ""
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
    frame_index: int = 0,
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
            frame_index=frame_index,
        )
    )
    return ok and path_written(snapshot_path, require_non_empty=True), error
