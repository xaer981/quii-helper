from pathlib import Path
from typing import Any
from unittest.mock import patch

from quii_helper.camera import Camera
from quii_helper.camera.streaming import CameraRtspStream
from quii_helper.preview.pipeline.config import (
    DEFAULT_PREVIEW_CAPTURE_SETTINGS,
)


class _FakeRtspAssembler:
    access_unit_count = 0

    def feed_message(self, decoded: dict[str, Any]) -> list[bytes]:
        self.access_unit_count = decoded["access_unit_count"]
        return []


class CameraRtspApiTests:
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

        assert "started" == result
        kwargs = stream_cls.call_args.kwargs
        assert camera.connector is kwargs["connector"]
        assert camera.preview_settings is kwargs["preview_settings"]
        assert "127.0.0.1" == kwargs["host"]
        assert 8555 == kwargs["port"]
        assert "cam" == kwargs["path"]
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
                    assert stream is session

        start.assert_called_once_with()
        close.assert_called_once_with()

    def test_rtsp_ready_status_is_emitted_after_first_access_unit(
        self,
    ) -> None:
        statuses = []
        stream = CameraRtspStream(
            connector=object(),
            preview_settings=DEFAULT_PREVIEW_CAPTURE_SETTINGS,
            data_dir=Path("."),
            emit=lambda obj: None,
            status=statuses.append,
            host="127.0.0.1",
            port=8555,
        )
        stream.assembler = _FakeRtspAssembler()

        stream._feed_assembler_message({"access_unit_count": 0})
        stream._feed_assembler_message({"access_unit_count": 1})
        stream._feed_assembler_message({"access_unit_count": 2})

        assert [f"RTSP stream ready: {stream.url}"] == statuses
