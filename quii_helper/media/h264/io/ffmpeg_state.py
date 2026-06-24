from collections.abc import Sequence
from pathlib import Path
from typing import Any

FALSE_POSITIVE_SPS_SKIP_REASON = "single_sps_without_pps_vcl_or_epb"
MISSING_H264_CONTEXT_SKIP_REASON = "missing_sps_pps_or_vcl"


def mp4_skip_reason(nal_analysis: dict[str, Any]) -> str:
    if nal_analysis.get("false_positive_sps_only"):
        return FALSE_POSITIVE_SPS_SKIP_REASON
    return ""


def decodable_mp4_skip_reason(h264_analysis: dict[str, Any]) -> str:
    if not h264_analysis.get("decodable_h264_context"):
        return MISSING_H264_CONTEXT_SKIP_REASON
    return ""


def ffmpeg_input_rate_args(input_fps: float | None) -> list[str]:
    if input_fps is not None and input_fps > 0:
        return ["-r", f"{input_fps:.6f}"]
    return []


def h264_mp4_command(
    stream_path: Path,
    mp4_path: Path,
    *,
    input_rate_args: Sequence[str] = (),
) -> list[str]:
    return [
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


def raw_h264_input_args(stream_path: Path) -> list[str]:
    return ["-f", "h264", "-i", str(stream_path)]


def snapshot_input_args(
    stream_path: Path,
    mp4_path: Path,
    *,
    mp4_ok: bool,
) -> list[str]:
    if mp4_ok:
        return ["-i", str(mp4_path)]
    return raw_h264_input_args(stream_path)


def h264_snapshot_command(
    snapshot_path: Path,
    *,
    input_args: Sequence[str],
) -> list[str]:
    return [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        *input_args,
        "-frames:v",
        "1",
        str(snapshot_path),
    ]


def path_written(path: Path, *, require_non_empty: bool = False) -> bool:
    if not path.exists():
        return False
    if require_non_empty and path.stat().st_size <= 0:
        return False
    return True
