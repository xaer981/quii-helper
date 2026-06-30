from pathlib import Path
from typing import get_type_hints

from quii_helper.camera.outputs.result_state import (
    capture_done_message_for_artifact,
    capture_media_artifact,
    media_render_error_message,
    optional_artifact_path,
)
from quii_helper.models.capture import (
    CaptureSummary,
    MediaArtifactSummary,
)


class CameraResultStateTests:
    def test_capture_media_artifact_prefers_media_result(self) -> None:
        summary = {
            "media_result": {"source": "media"},
            "embedded_fallback": {"source": "fallback"},
        }

        assert {"source": "media"} == capture_media_artifact(summary)

    def test_capture_media_artifact_falls_back_to_embedded_result(
        self,
    ) -> None:
        assert {"source": "fallback"} == capture_media_artifact(
            {"embedded_fallback": {"source": "fallback"}}
        )

    def test_capture_media_artifact_returns_empty_dict_without_artifact(
        self,
    ) -> None:
        assert {} == capture_media_artifact({})

    def test_capture_media_artifact_uses_typed_summary_models(self) -> None:
        hints = get_type_hints(capture_media_artifact)

        assert CaptureSummary is hints["summary"]
        assert MediaArtifactSummary is hints["return"]

    def test_optional_artifact_path_preserves_existing_coercion(self) -> None:
        assert optional_artifact_path("") is None
        assert optional_artifact_path(None) is None
        assert Path("out.mp4") == optional_artifact_path("out.mp4")

    def test_capture_done_message_for_artifact_preserves_branch_order(
        self,
    ) -> None:
        assert (
            "Done. Video saved: video.mp4"
            == capture_done_message_for_artifact(
                {
                    "mp4": True,
                    "mp4_path": "video.mp4",
                    "snapshot": True,
                    "snapshot_path": "snapshot.jpg",
                }
            )
        )
        assert (
            "Done. Snapshot saved: snapshot.jpg"
            == capture_done_message_for_artifact(
                {
                    "snapshot": True,
                    "snapshot_path": "snapshot.jpg",
                }
            )
        )
        assert (
            "Done. Media data was collected, but no final file was written"
            == capture_done_message_for_artifact({"written": True})
        )
        assert (
            "Done. No media file was produced"
            == capture_done_message_for_artifact({})
        )

    def test_media_render_error_message_prefers_artifact_error(self) -> None:
        assert (
            "video was not produced: ffmpeg failed"
            == media_render_error_message(
                {
                    "mp4_error": "ffmpeg failed",
                    "ffmpeg_skipped_reason": "missing idr",
                },
                kind="video",
            )
        )

    def test_media_render_error_message_uses_skip_reason(self) -> None:
        assert (
            "snapshot was not produced: missing decodable H264"
            == media_render_error_message(
                {"ffmpeg_skipped_reason": "missing decodable H264"},
                kind="snapshot",
            )
        )

    def test_media_render_error_message_returns_none_without_details(
        self,
    ) -> None:
        assert media_render_error_message({}, kind="video") is None
