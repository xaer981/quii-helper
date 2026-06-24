import unittest
from pathlib import Path

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
from quii_helper.preview.pipeline.config import (
    DEFAULT_PREVIEW_CAPTURE_SETTINGS,
)


class CameraCaptureResultTests(unittest.TestCase):
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

        self.assertEqual(Path("snapshot.jpg"), result.require_snapshot())
        self.assertEqual(Path("video.mp4"), result.require_video())
        self.assertTrue(result.media_written)

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

        self.assertEqual(Path("fallback.jpg"), result.require_snapshot())
        self.assertTrue(result.snapshot_written)
        self.assertFalse(result.video_written)

    def test_require_methods_raise_when_artifact_missing(self) -> None:
        result = CameraCaptureResult.from_summary({})

        with self.assertRaises(CameraCaptureError):
            result.require_snapshot()
        with self.assertRaises(CameraCaptureError):
            result.require_video()

    def test_capture_done_message_prefers_video_then_snapshot(self) -> None:
        self.assertEqual(
            "Done. Video saved: video.mp4",
            capture_done_message(
                {"media_result": {"mp4": True, "mp4_path": "video.mp4"}}
            ),
        )
        self.assertEqual(
            "Done. Snapshot saved: snapshot.jpg",
            capture_done_message(
                {
                    "media_result": {
                        "snapshot": True,
                        "snapshot_path": "snapshot.jpg",
                    }
                }
            ),
        )


class CameraLocalValidationTests(unittest.TestCase):
    def test_resolve_capture_settings_overrides_requested_fields(self) -> None:
        settings = resolve_capture_settings(
            DEFAULT_PREVIEW_CAPTURE_SETTINGS,
            duration_seconds=12.5,
            save_diagnostic_artifacts=True,
            stop_when_decodable=False,
        )

        self.assertEqual(12.5, settings.capture_seconds)
        self.assertTrue(settings.save_diagnostic_artifacts)
        self.assertFalse(settings.stop_when_decodable)

    def test_resolve_capture_settings_rejects_non_positive_duration(
        self,
    ) -> None:
        with self.assertRaises(ValueError):
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

        self.assertEqual(8.0, request.settings.capture_seconds)
        self.assertTrue(request.settings.save_diagnostic_artifacts)
        self.assertFalse(request.settings.stop_when_decodable)
        self.assertEqual(Path("clip"), request.output_base)
        self.assertFalse(request.render_snapshot)
        self.assertTrue(request.render_video)

    def test_output_path_suffix_validation(self) -> None:
        self.assertIsNone(validate_output_path(None, ".jpg"))
        self.assertEqual(
            Path("frame"),
            validate_output_path("frame", ".jpg"),
        )
        self.assertEqual(
            Path("frame.jpg"),
            validate_output_path("frame.jpg", ".jpg"),
        )

        with self.assertRaises(ValueError):
            validate_output_path("frame.mp4", ".jpg")

        self.assertEqual(
            Path("frame.jpg"),
            validate_output_path("frame.jpg", ".jpg"),
        )

    def test_output_base_strips_suffix(self) -> None:
        self.assertEqual(
            Path("clip"),
            output_base_from_path("clip.mp4"),
        )
        self.assertEqual(Path("clip"), output_base_from_path("clip"))
        self.assertEqual(Path("clip"), output_base_from_path("clip.mp4"))

    def test_camera_options_keeps_compatibility_imports(self) -> None:
        self.assertIs(
            camera_options.resolve_camera_config,
            direct_resolve_camera_config,
        )
        self.assertIs(
            camera_options.CameraCaptureRequest,
            DirectCameraCaptureRequest,
        )
        self.assertIs(
            camera_options.resolve_capture_request,
            direct_resolve_capture_request,
        )
        self.assertIs(
            camera_options.resolve_capture_settings,
            direct_resolve_capture_settings,
        )
        self.assertIs(
            camera_options.output_base_from_path,
            direct_output_base_from_path,
        )
        self.assertIs(
            camera_options.validate_output_path,
            direct_validate_output_path,
        )

    def test_init_rejects_ambiguous_stream_inputs(self) -> None:
        with self.assertRaises(ValueError):
            Camera(stream=1, stream_quality="high")

    def test_init_rejects_conflicting_cloud_account_aliases(self) -> None:
        with self.assertRaises(ValueError):
            Camera(cloud_username="user-a", cloud_account="user-b")

    def test_init_accepts_stream_quality_alias(self) -> None:
        camera = Camera(stream_quality="high")

        self.assertEqual(STREAM_HIGH_QUALITY, camera.config.stream)

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

        self.assertEqual(Path("frame"), captured["output_base"])
        self.assertEqual(3.0, captured["settings"].capture_seconds)
        self.assertTrue(captured["render_snapshot"])
        self.assertFalse(captured["render_video"])
        self.assertEqual(Path("frame.jpg"), result.require_snapshot())


if __name__ == "__main__":
    unittest.main()
