from pathlib import Path

from quii_helper.models.capture import (
    CaptureSummary,
    MediaArtifactSummary,
)


def capture_media_artifact(summary: CaptureSummary) -> MediaArtifactSummary:
    return (
        summary.get("media_result") or summary.get("embedded_fallback") or {}
    )


def optional_artifact_path(value: object) -> Path | None:
    if not value:
        return None
    return Path(str(value))


def media_render_error_message(
    artifact: MediaArtifactSummary,
    *,
    kind: str,
) -> str | None:
    """Return a render error message for a failed media artifact."""

    error_key = "mp4_error" if kind == "video" else "snapshot_error"
    error = str(artifact.get(error_key) or "").strip()
    skipped_reason = str(artifact.get("ffmpeg_skipped_reason") or "").strip()
    details = error or skipped_reason
    if not details:
        return None
    return f"{kind} was not produced: {details}"


def capture_done_message_for_artifact(
    artifact: MediaArtifactSummary,
) -> str:
    mp4_path = artifact.get("mp4_path")
    snapshot_path = artifact.get("snapshot_path")
    if artifact.get("mp4") and mp4_path:
        return f"Done. Video saved: {mp4_path}"
    if artifact.get("snapshot") and snapshot_path:
        return f"Done. Snapshot saved: {snapshot_path}"
    if artifact.get("written"):
        return "Done. Media data was collected, but no final file was written"
    return "Done. No media file was produced"
