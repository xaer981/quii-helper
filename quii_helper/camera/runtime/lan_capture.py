"""Bounded, direct-TCP capture using the shared CFrame/H.264 renderers."""

import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from quii_helper.camera.connection.session import CameraConnector
from quii_helper.camera.outputs.results import capture_done_message
from quii_helper.media.frames.assembler import AssembledH264Stream
from quii_helper.media.frames.assembler_state import (
    KEY_FRAME_TAGS,
    access_unit_from_frame,
    build_media_summary,
    frame_info_from_parsed_frame,
)
from quii_helper.media.frames.parsing import QuiiCFramePack
from quii_helper.media.h264.core.analysis import analyze_h264_annexb_stream
from quii_helper.media.h264.io.writer import write_assembled_h264_stream
from quii_helper.models.capture import CaptureSummary, MediaFrameSummary
from quii_helper.preview.outputs.writer.state import (
    resolve_preview_output_base,
)
from quii_helper.preview.pipeline.config import PreviewCaptureSettings
from quii_helper.support.errors import CameraCaptureError

MAX_LAN_CAPTURE_BYTES = 256 * 1024 * 1024


def capture_lan_summary(
    *,
    connector: CameraConnector,
    settings: PreviewCaptureSettings,
    output_base: Path | None,
    data_dir: Path,
    emit: Callable[[object], None],
    status: Callable[[str], None],
    render_snapshot: bool,
    render_video: bool,
) -> CaptureSummary:
    """Collect a wall-clock window after TCP setup/play, without cloud fallback.

    Snapshot capture stops at a decodable keyframe. Video keeps the source FPS,
    never stretches sparse frames, and fails explicitly on the memory limit.
    RBUDP-specific drain, diagnostics and message limits do not apply to TCP.
    """
    packer = QuiiCFramePack()
    frames: list[MediaFrameSummary] = []
    stream = bytearray()
    nal_counts: Counter[str] = Counter()
    decoded_count = media_count = 0
    decodable = False
    waiting_for_keyframe = True
    status("Opening LAN preview session")
    with connector.create_lan_session() as session:
        status("Connected")
        status("Receiving media packets")
        started = time.monotonic()
        deadline = started + settings.capture_seconds
        while (remaining := deadline - time.monotonic()) > 0:
            try:
                message = session.recv_message(timeout=min(1.0, remaining))
            except TimeoutError:
                continue
            decoded_count += 1
            if not message["is_media"]:
                continue
            media_count += 1
            for frame in packer.feed(message["payload"]):
                # Native PackFrame suppresses frames until the first keyframe.
                if waiting_for_keyframe:
                    if frame["frame_tag"] not in KEY_FRAME_TAGS:
                        continue
                    waiting_for_keyframe = False
                access_unit = access_unit_from_frame(frame)
                if not access_unit:
                    continue
                if len(stream) + len(access_unit) > MAX_LAN_CAPTURE_BYTES:
                    raise CameraCaptureError(
                        "LAN capture exceeds the 256 MiB buffer limit; "
                        "use shorter recordings or serve_rtsp()"
                    )
                stream.extend(access_unit)
                frames.append(frame_info_from_parsed_frame(frame))
                nal_counts.update(
                    analyze_h264_annexb_stream(access_unit).get("counts", {})
                )
            decodable = all(
                nal_counts[name] for name in ("sps", "pps", "idr_slice")
            )
            if settings.stop_when_decodable and decodable:
                break
        elapsed = time.monotonic() - started

    media_summary = build_media_summary(
        frames, assembled_units=len(frames), cframe_stats=dict(packer.stats)
    )
    summary: CaptureSummary = {
        "decoded_messages": decoded_count,
        "media_messages": media_count,
        "capture_settings": {
            "connection_mode": "lan",
            "transport": "tcp",
            "capture_seconds": settings.capture_seconds,
            "stop_when_decodable": settings.stop_when_decodable,
            "elapsed_seconds": round(elapsed, 3),
            "source_fps": frames[0]["fps"] if frames else None,
        },
        "media_collection": {
            "media_messages": media_count,
            "media_frame_count": len(frames),
            "cframe_pack": dict(packer.stats),
            "keyframes": media_summary["keyframes"],
            "counts": dict(nal_counts),
            "has_sps": bool(nal_counts["sps"]),
            "has_pps": bool(nal_counts["pps"]),
            "has_idr": bool(nal_counts["idr_slice"]),
            "has_vcl": bool(
                nal_counts["idr_slice"] or nal_counts["non_idr_slice"]
            ),
            "decodable_h264_context": decodable if media_count else False,
        },
        "diagnostic_artifacts_saved": False,
        "media_result": None,
    }
    if stream:
        base = resolve_preview_output_base(output_base, data_dir)
        try:
            summary["media_result"] = write_assembled_h264_stream(
                base,
                AssembledH264Stream(bytes(stream), frames, media_summary),
                render_snapshot=render_snapshot,
                render_video=render_video,
                input_fps=float(frames[0]["fps"]) or None,
            )
        finally:
            reservation = base.with_name(base.name + ".h264")
            if output_base is None:
                try:
                    if reservation.stat().st_size == 0:
                        reservation.unlink()
                except OSError:
                    pass
    emit(summary)
    status(capture_done_message(summary))
    return summary
