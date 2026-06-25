import inspect
import unittest

from quii_helper import Camera
from quii_helper.camera.outputs.results import CameraCaptureResult
from quii_helper.camera.streaming import CameraRtspStream
from quii_helper.config import AutonomousConfig
from quii_helper.preview.pipeline.config import PreviewCaptureSettings

DOCUMENTED_OBJECTS = (
    Camera,
    Camera.__init__,
    Camera.capture,
    Camera.snapshot,
    Camera.save_video,
    Camera.record,
    Camera.serve_rtsp,
    CameraCaptureResult,
    CameraCaptureResult.from_summary,
    CameraCaptureResult.require_snapshot,
    CameraCaptureResult.require_video,
    CameraRtspStream,
    CameraRtspStream.start,
    CameraRtspStream.wait,
    CameraRtspStream.close,
    AutonomousConfig,
    PreviewCaptureSettings,
)


class PublicDocstringTests(unittest.TestCase):
    def test_high_level_api_has_docstrings(self) -> None:
        missing = [
            obj.__qualname__
            for obj in DOCUMENTED_OBJECTS
            if not inspect.getdoc(obj)
        ]
        self.assertEqual([], missing)


if __name__ == "__main__":
    unittest.main()
