from dataclasses import dataclass
from pathlib import Path

from quii_helper.camera.outputs.result_state import (
    capture_done_message_for_artifact,
    capture_media_artifact,
    optional_artifact_path,
)


class CameraCaptureError(RuntimeError):
    """Raised when a requested media artifact could not be produced."""


@dataclass(frozen=True)
class CameraCaptureResult:
    """Result returned by `Camera.capture()`.

    Attributes:
        summary: Raw structured capture summary with protocol and media
            diagnostics.
        snapshot_path: Path to the requested JPEG snapshot, if one was written.
        video_path: Path to the requested MP4 video, if one was written.
        snapshot_written: Whether the snapshot artifact exists and was reported
            as written.
        video_written: Whether the MP4 artifact exists and was reported as
            written.
        media_written: Whether any media artifact was written.
    """

    summary: dict
    snapshot_path: Path | None
    video_path: Path | None
    snapshot_written: bool
    video_written: bool
    media_written: bool

    @classmethod
    def from_summary(cls, summary: dict) -> "CameraCaptureResult":
        """Build a result object from the low-level capture summary.

        Args:
            summary: Summary dictionary returned by the preview pipeline.

        Returns:
            Parsed `CameraCaptureResult` with normalized artifact paths.
        """
        artifact = capture_media_artifact(summary)
        snapshot_path = optional_artifact_path(artifact.get("snapshot_path"))
        video_path = optional_artifact_path(artifact.get("mp4_path"))
        return cls(
            summary=summary,
            snapshot_path=snapshot_path,
            video_path=video_path,
            snapshot_written=bool(artifact.get("snapshot"))
            and snapshot_path is not None,
            video_written=bool(artifact.get("mp4")) and video_path is not None,
            media_written=bool(artifact.get("written")),
        )

    def require_snapshot(self) -> Path:
        """Return the snapshot path or raise a capture error.

        Returns:
            Path to the generated JPEG snapshot.

        Raises:
            CameraCaptureError: If the snapshot was requested but not written.
        """
        if self.snapshot_written and self.snapshot_path is not None:
            return self.snapshot_path
        raise CameraCaptureError(
            "snapshot was not produced; "
            "inspect CameraCaptureResult.summary for details"
        )

    def require_video(self) -> Path:
        """Return the video path or raise a capture error.

        Returns:
            Path to the generated MP4 video.

        Raises:
            CameraCaptureError: If the video was requested but not written.
        """
        if self.video_written and self.video_path is not None:
            return self.video_path
        raise CameraCaptureError(
            "video was not produced; "
            "inspect CameraCaptureResult.summary for details"
        )


def capture_done_message(summary: dict) -> str:
    """Format a user-facing completion message for a capture summary."""
    artifact = capture_media_artifact(summary)
    return capture_done_message_for_artifact(artifact)
