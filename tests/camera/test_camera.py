from pathlib import Path
from typing import get_type_hints

import pytest

from quii_helper import MediaRenderError
from quii_helper.camera import Camera, CameraCaptureError, CameraCaptureResult
from quii_helper.camera import options as camera_options
from quii_helper.camera.capture_request.request import (
    CameraCaptureRequest as DirectCameraCaptureRequest,
)
from quii_helper.camera.capture_request.request import (
    resolve_capture_request as direct_resolve_capture_request,
)
from quii_helper.camera.capture_request.request import (
    resolve_capture_settings as direct_resolve_capture_settings,
)
from quii_helper.camera.outputs.paths import (
    output_base_from_path as direct_output_base_from_path,
)
from quii_helper.camera.outputs.paths import (
    validate_output_path as direct_validate_output_path,
)
from quii_helper.camera.outputs.results import capture_done_message
from quii_helper.camera.settings.config import (
    resolve_camera_config as direct_resolve_camera_config,
)
from quii_helper.camera.settings.options import (
    output_base_from_path,
    resolve_capture_request,
    resolve_capture_settings,
    validate_output_path,
)
from quii_helper.config import STREAM_HIGH_QUALITY
from quii_helper.models.capture import CaptureSummary
from quii_helper.preview.pipeline.config import (
    DEFAULT_PREVIEW_CAPTURE_SETTINGS,
)


class CameraCaptureResultTests:
    def test_from_summary_maps_media_result_paths_and_flags(self) -> None:
        summary = {
            "media_result": {
                "snapshot_path": "snapshot.jpg",
                "mp4_path": "video.mp4",
                "snapshot": True,
                "mp4": True,
                "written": True,
            }
        }

        result = CameraCaptureResult.from_summary(summary)

        assert Path("snapshot.jpg") == result.require_snapshot()
        assert Path("video.mp4") == result.require_video()
        assert result.media_written

    def test_result_summary_field_uses_capture_summary_model(self) -> None:
        hints = get_type_hints(CameraCaptureResult)

        assert CaptureSummary is hints["summary"]

    def test_from_summary_falls_back_to_embedded_artifact(self) -> None:
        result = CameraCaptureResult.from_summary(
            {
                "embedded_fallback": {
                    "snapshot_path": "fallback.jpg",
                    "snapshot": True,
                    "written": True,
                }
            }
        )

        assert Path("fallback.jpg") == result.require_snapshot()
        assert result.snapshot_written
        assert not result.video_written

    def test_require_methods_raise_when_artifact_missing(self) -> None:
        result = CameraCaptureResult.from_summary({})

        with pytest.raises(CameraCaptureError):
            result.require_snapshot()
        with pytest.raises(CameraCaptureError):
            result.require_video()

    def test_require_video_raises_render_error_with_summary_details(
        self,
    ) -> None:
        result = CameraCaptureResult.from_summary(
            {
                "media_result": {
                    "mp4": False,
                    "mp4_path": "video.mp4",
                    "mp4_error": "ffmpeg failed",
                    "written": True,
                }
            }
        )

        with pytest.raises(MediaRenderError, match="ffmpeg failed"):
            result.require_video()

    def test_require_snapshot_raises_render_error_with_summary_details(
        self,
    ) -> None:
        result = CameraCaptureResult.from_summary(
            {
                "media_result": {
                    "snapshot": False,
                    "snapshot_path": "snapshot.jpg",
                    "snapshot_error": "snapshot failed",
                    "written": True,
                }
            }
        )

        with pytest.raises(MediaRenderError, match="snapshot failed"):
            result.require_snapshot()

    def test_capture_done_message_prefers_video_then_snapshot(self) -> None:
        assert "Done. Video saved: video.mp4" == (
            capture_done_message(
                {"media_result": {"mp4": True, "mp4_path": "video.mp4"}}
            )
        )
        assert "Done. Snapshot saved: snapshot.jpg" == (
            capture_done_message(
                {
                    "media_result": {
                        "snapshot": True,
                        "snapshot_path": "snapshot.jpg",
                    }
                }
            )
        )


class CameraLocalValidationTests:
    def test_resolve_capture_settings_overrides_requested_fields(self) -> None:
        settings = resolve_capture_settings(
            DEFAULT_PREVIEW_CAPTURE_SETTINGS,
            duration_seconds=12.5,
            save_diagnostic_artifacts=True,
            stop_when_decodable=False,
        )

        assert 12.5 == settings.capture_seconds
        assert settings.save_diagnostic_artifacts
        assert not settings.stop_when_decodable

    def test_resolve_capture_settings_rejects_non_positive_duration(
        self,
    ) -> None:
        with pytest.raises(ValueError):
            resolve_capture_settings(
                DEFAULT_PREVIEW_CAPTURE_SETTINGS,
                duration_seconds=0,
                save_diagnostic_artifacts=None,
                stop_when_decodable=None,
            )

    def test_resolve_capture_request_normalizes_request_values(self) -> None:
        request = resolve_capture_request(
            DEFAULT_PREVIEW_CAPTURE_SETTINGS,
            duration_seconds=8,
            output_path="clip.mp4",
            save_diagnostic_artifacts=True,
            stop_when_decodable=False,
            render_snapshot=False,
            render_video=True,
        )

        assert 8.0 == request.settings.capture_seconds
        assert request.settings.save_diagnostic_artifacts
        assert not request.settings.stop_when_decodable
        assert Path("clip") == request.output_base
        assert not request.render_snapshot
        assert request.render_video

    def test_output_path_suffix_validation(self) -> None:
        assert validate_output_path(None, ".jpg") is None
        assert Path("frame") == (validate_output_path("frame", ".jpg"))
        assert Path("frame.jpg") == (validate_output_path("frame.jpg", ".jpg"))
        with pytest.raises(ValueError):
            validate_output_path("frame.mp4", ".jpg")

        assert Path("frame.jpg") == (validate_output_path("frame.jpg", ".jpg"))

    def test_output_base_strips_suffix(self) -> None:
        assert Path("clip") == (output_base_from_path("clip.mp4"))
        assert Path("clip") == output_base_from_path("clip")
        assert Path("clip") == output_base_from_path("clip.mp4")

    def test_camera_options_keeps_compatibility_imports(self) -> None:
        assert camera_options.resolve_camera_config is (
            direct_resolve_camera_config
        )
        assert camera_options.CameraCaptureRequest is (
            DirectCameraCaptureRequest
        )
        assert camera_options.resolve_capture_request is (
            direct_resolve_capture_request
        )
        assert camera_options.resolve_capture_settings is (
            direct_resolve_capture_settings
        )
        assert camera_options.output_base_from_path is (
            direct_output_base_from_path
        )
        assert camera_options.validate_output_path is (
            direct_validate_output_path
        )

    def test_init_rejects_ambiguous_stream_inputs(self) -> None:
        with pytest.raises(ValueError):
            Camera(stream=1, stream_quality="high")

    def test_init_rejects_conflicting_cloud_account_aliases(self) -> None:
        with pytest.raises(ValueError):
            Camera(cloud_username="user-a", cloud_account="user-b")

    def test_init_accepts_stream_quality_alias(self) -> None:
        camera = Camera(stream_quality="high")

        assert STREAM_HIGH_QUALITY == camera.config.stream

    def test_capture_uses_normalized_request_without_opening_device(
        self,
    ) -> None:
        camera = Camera()
        captured = {}

        def fake_capture_summary(**kwargs: object) -> dict:
            captured.update(kwargs)
            return {
                "media_result": {
                    "snapshot": True,
                    "snapshot_path": "frame.jpg",
                    "written": True,
                }
            }

        camera._capture_summary = fake_capture_summary

        result = camera.capture(
            duration_seconds=3,
            output_path="frame.jpg",
            render_snapshot=True,
            render_video=False,
        )

        assert Path("frame") == captured["output_base"]
        assert 3.0 == captured["settings"].capture_seconds
        assert captured["render_snapshot"]
        assert not captured["render_video"]
        assert Path("frame.jpg") == result.require_snapshot()
