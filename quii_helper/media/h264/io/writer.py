import warnings
from pathlib import Path
from typing import Any

from quii_helper.io.paths import DATA_DIR
from quii_helper.media.audio.recording import AudioRecording
from quii_helper.media.frames.assembler import (
    AssembledH264Stream,
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
    last_snapshot_frame: bool = False,
) -> MediaArtifactSummary:
    return write_assembled_h264_stream(
        base_name,
        assemble_h264_stream_from_messages(
            messages, collect_audio=render_video
        ),
        output_dir=output_dir,
        render_snapshot=render_snapshot,
        render_video=render_video,
        keep_raw_h264=keep_raw_h264,
        target_duration_seconds=target_duration_seconds,
        last_snapshot_frame=last_snapshot_frame,
    )


def write_assembled_h264_stream(
    base_name: str | Path,
    assembled_stream: AssembledH264Stream,
    *,
    output_dir: Path = DATA_DIR,
    render_snapshot: bool = True,
    render_video: bool = True,
    keep_raw_h264: bool = False,
    target_duration_seconds: float | None = None,
    input_fps: float | None = None,
    last_snapshot_frame: bool = False,
) -> MediaArtifactSummary:
    """Render assembled access units; explicit camera FPS overrides retiming."""
    stream_path, mp4_path, snapshot_path = h264_output_paths(
        base_name,
        output_dir=output_dir,
    )
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
        if input_fps is None:
            input_fps = input_fps_for_target_duration(
                frame_count=int(summary.get("assembled_units", 0)),
                target_duration_seconds=target_duration_seconds,
            )
        duration = (
            int(summary.get("assembled_units", 0)) / input_fps
            if input_fps is not None and input_fps > 0
            else None
        )
        audio_to_mux: AudioRecording | None = None
        audio_summary: dict[str, Any] = {}
        if assembled_stream.audio is not None:
            audio = assembled_stream.audio
            reason = audio.skipped_reason
            if audio.data:
                if duration is None:
                    reason = "video duration is unknown"
                elif audio.offset_seconds >= duration:
                    reason = "audio starts after video ends"
                else:
                    audio_to_mux = audio
                if reason:
                    warnings.warn(
                        f"MP4 audio unavailable; writing video-only: {reason}",
                        UserWarning,
                        stacklevel=2,
                    )
            audio_summary = {
                "included": False,
                "source_codec": audio.codec,
                "sample_rate": 8000 if audio.codec is not None else None,
                "channels": 1 if audio.codec is not None else None,
                "samples": len(audio.data),
                "offset_seconds": audio.offset_seconds,
                "skipped_reason": reason
                or ("" if audio.data else "no_audio_frames"),
            }
            summary["audio"] = audio_summary
        mp4_ok, mp4_error, ffmpeg_skipped_reason = write_h264_mp4_if_decodable(
            stream_path,
            mp4_path,
            h264_analysis,
            input_fps=input_fps,
            audio=audio_to_mux,
            duration_seconds=duration,
        )
        if audio_summary:
            audio_summary["included"] = mp4_ok and audio_to_mux is not None

    snapshot_ok = False
    snapshot_error = ""
    if render_snapshot:
        snapshot_ok, snapshot_error = write_h264_snapshot_from_best_source(
            stream_path,
            mp4_path,
            snapshot_path,
            mp4_ok=mp4_ok,
            ffmpeg_skipped_reason=ffmpeg_skipped_reason,
            **(
                {
                    "frame_index": max(
                        0, int(summary.get("assembled_units", 0)) - 1
                    )
                }
                if last_snapshot_frame
                else {}
            ),
        )

    if should_remove_raw_h264(
        mp4_ok=mp4_ok,
        snapshot_ok=snapshot_ok,
        keep_raw_h264=keep_raw_h264,
        render_video=render_video,
        render_snapshot=render_snapshot,
    ):
        try:
            stream_path.unlink(missing_ok=True)
        except OSError:
            pass

    return h264_stream_result_payload(
        stream_path=stream_path,
        mp4_path=mp4_path,
        snapshot_path=snapshot_path,
        frames=assembled_stream.frames,
        summary=summary,
        keep_raw_h264=stream_path.is_file(),
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
