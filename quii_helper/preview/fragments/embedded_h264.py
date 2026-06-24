from pathlib import Path

from quii_helper.io.safe_read import read_existing_bytes
from quii_helper.media.h264.io.ffmpeg import (
    write_h264_mp4,
    write_h264_snapshot,
)
from quii_helper.media.h264.merge.annexb_merge import (
    merge_annexb_candidates,
    merge_two_streams,
)
from quii_helper.media.h264.merge.probe_analysis import analyze_annexb_h264
from quii_helper.preview.fragments.embedded_h264_state import (
    embedded_h264_paths,
    embedded_h264_result_payload,
    empty_embedded_h264_result,
    should_write_persistent_embedded,
)


def write_embedded_h264_fallback(
    base_name: str | Path, annexb_blobs: list[bytes]
) -> dict:
    paths = embedded_h264_paths(base_name)
    stream_path = paths["stream_path"]
    mp4_path = paths["mp4_path"]
    snapshot_path = paths["snapshot_path"]
    persistent_path = paths["persistent_path"]

    unique, selected, strategy = merge_annexb_candidates(annexb_blobs)
    persistent_before = read_existing_bytes(persistent_path)
    selected, persistent_strategy = merge_two_streams(
        persistent_before, selected
    )

    if not unique:
        return empty_embedded_h264_result(
            paths=paths,
            persistent_before=persistent_before,
        )

    nal_analysis = analyze_annexb_h264(selected)
    stream_path.write_bytes(selected)

    persistent_written = False
    if should_write_persistent_embedded(nal_analysis):
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

    return embedded_h264_result_payload(
        unique=unique,
        selected=selected,
        merge_strategy=strategy,
        persistent_strategy=persistent_strategy,
        persistent_before=persistent_before,
        nal_analysis=nal_analysis,
        persistent_written=persistent_written,
        mp4_ok=mp4_ok,
        mp4_error=mp4_error,
        snapshot_ok=snapshot_ok,
        snapshot_error=snapshot_error,
        ffmpeg_skipped_reason=ffmpeg_skipped_reason,
        paths=paths,
    )
