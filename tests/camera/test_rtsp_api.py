import unittest
from pathlib import Path
from unittest.mock import patch

from quii_helper.camera import Camera
from quii_helper.camera.streaming import CameraRtspStream
from quii_helper.preview.pipeline.config import (
    DEFAULT_PREVIEW_CAPTURE_SETTINGS,
)


class CameraRtspApiTests(unittest.TestCase):
    def test_serve_rtsp_builds_and_starts_stream(self) -> None:
        camera = Camera()

        with patch("quii_helper.camera.api.CameraRtspStream") as stream_cls:
            stream = stream_cls.return_value
            stream.start.return_value = "started"

            result = camera.serve_rtsp(
                host="127.0.0.1",
                port=8555,
                path="cam",
            )

        self.assertEqual("started", result)
        kwargs = stream_cls.call_args.kwargs
        self.assertIs(camera.connector, kwargs["connector"])
        self.assertIs(camera.preview_settings, kwargs["preview_settings"])
        self.assertEqual("127.0.0.1", kwargs["host"])
        self.assertEqual(8555, kwargs["port"])
        self.assertEqual("cam", kwargs["path"])
        stream.start.assert_called_once_with()

    def test_rtsp_stream_context_manager_closes_stream(self) -> None:
        stream = CameraRtspStream(
            connector=object(),
            preview_settings=DEFAULT_PREVIEW_CAPTURE_SETTINGS,
            data_dir=Path("."),
            emit=lambda obj: None,
            status=lambda message: None,
        )

        with patch.object(stream, "start", return_value=stream) as start:
            with patch.object(stream, "close") as close:
                with stream as session:
                    self.assertIs(stream, session)

        start.assert_called_once_with()
        close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
