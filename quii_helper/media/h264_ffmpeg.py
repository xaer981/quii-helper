import subprocess
from pathlib import Path


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
    if nal_analysis.get("false_positive_sps_only"):
        return False, "", "single_sps_without_pps_vcl_or_epb"
    ok, error = _run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "h264",
            "-i",
            str(stream_path),
            "-c:v",
            "copy",
            str(mp4_path),
        ]
    )
    return ok and mp4_path.exists(), error, ""


def write_h264_mp4_if_decodable(
    stream_path: Path,
    mp4_path: Path,
    h264_analysis: dict,
    *,
    input_fps: float | None = None,
) -> tuple[bool, str, str]:
    if not h264_analysis.get("decodable_h264_context"):
        skipped_reason = "missing_sps_pps_or_vcl"
        return False, skipped_reason, skipped_reason
    input_rate_args = []
    if input_fps is not None and input_fps > 0:
        input_rate_args = ["-r", f"{input_fps:.6f}"]
    ok, error = _run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            *input_rate_args,
            "-f",
            "h264",
            "-i",
            str(stream_path),
            "-c:v",
            "copy",
            str(mp4_path),
        ]
    )
    return ok and mp4_path.exists() and mp4_path.stat().st_size > 0, error, ""


def write_h264_snapshot(
    stream_path: Path, snapshot_path: Path, ffmpeg_skipped_reason: str
) -> tuple[bool, str]:
    if ffmpeg_skipped_reason:
        return False, ffmpeg_skipped_reason
    ok, error = _run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "h264",
            "-i",
            str(stream_path),
            "-frames:v",
            "1",
            str(snapshot_path),
        ]
    )
    return ok and snapshot_path.exists(), error


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
    input_args = (
        ["-i", str(mp4_path)]
        if mp4_ok
        else ["-f", "h264", "-i", str(stream_path)]
    )
    ok, error = _run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            *input_args,
            "-frames:v",
            "1",
            str(snapshot_path),
        ]
    )
    return (
        ok and snapshot_path.exists() and snapshot_path.stat().st_size > 0,
        error,
    )
