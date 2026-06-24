from pathlib import Path


def capture_media_artifact(summary: dict) -> dict:
    return (
        summary.get("media_result") or summary.get("embedded_fallback") or {}
    )


def optional_artifact_path(value: object) -> Path | None:
    if not value:
        return None
    return Path(str(value))


def capture_done_message_for_artifact(artifact: dict) -> str:
    mp4_path = artifact.get("mp4_path")
    snapshot_path = artifact.get("snapshot_path")
    if artifact.get("mp4") and mp4_path:
        return f"Done. Video saved: {mp4_path}"
    if artifact.get("snapshot") and snapshot_path:
        return f"Done. Snapshot saved: {snapshot_path}"
    if artifact.get("written"):
        return "Done. Media data was collected, but no final file was written"
    return "Done. No media file was produced"
