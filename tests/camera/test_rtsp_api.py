from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from quii_helper.camera import Camera
from quii_helper.camera.streaming import CameraRtspStream
from quii_helper.config import AutonomousConfig
from quii_helper.preview.pipeline.config import (
    DEFAULT_PREVIEW_CAPTURE_SETTINGS,
)


class _FakeRtspAssembler:
    access_unit_count = 0

    def feed_message(self, decoded: dict[str, Any]) -> list[bytes]:
        self.access_unit_count = decoded["access_unit_count"]
        return []


class CameraRtspApiTests:
    @pytest.mark.parametrize(
        "overrides,option",
        [
            ({"live_play_payload": "oem"}, "live_play_payload"),
            ({"live_inner": True}, "live_inner"),
            ({"live_newcn": True}, "live_newcn"),
        ],
    )
    def test_legacy_lan_options_warn_without_blocking_rtsp_start(
        self, overrides, option
    ):
        camera = Camera(
            AutonomousConfig(
                device_host="127.0.0.1",
                stream_key="K" * 32,
                auth_code="synthetic-auth",
            ),
            **overrides,
        )
        with patch("quii_helper.camera.api.CameraRtspStream") as rtsp:
            with pytest.warns(UserWarning, match=option):
                camera.serve_rtsp(audio=True)
        rtsp.return_value.start.assert_called_once_with()

    def test_av_ready_requires_real_audio_and_video_configuration(self):
        from quii_helper.streaming.rtp.g711 import G711Format

        statuses = []
        stream = CameraRtspStream(
            connector=object(),
            preview_settings=DEFAULT_PREVIEW_CAPTURE_SETTINGS,
            data_dir=Path("."),
            emit=lambda value: None,
            status=statuses.append,
            audio=True,
        )
        stream.assembler = _FakeRtspAssembler()
        stream._feed_assembler_message({"access_unit_count": 1})
        assert not statuses
        stream.server.audio_format = G711Format(4)
        stream._feed_assembler_message({"access_unit_count": 1})
        assert not statuses
        stream.server._sps, stream.server._pps = b"sps", b"pps"
        stream._feed_assembler_message({"access_unit_count": 1})
        stream._feed_assembler_message({"access_unit_count": 2})
        assert len(statuses) == 1 and statuses[0].startswith(
            "RTSP stream ready:"
        )

    def test_audio_opt_in_uses_the_same_rtsp_producer(self):
        camera = Camera(connection_mode="cloud")
        with patch("quii_helper.camera.api.CameraRtspStream") as rtsp:
            with patch(
                "quii_helper.camera.api.CameraAudioStream"
            ) as separate_audio:
                camera.serve_rtsp(audio=True)
        assert rtsp.call_args.kwargs["audio"] is True
        separate_audio.assert_not_called()

    def test_serve_rtsp_defaults_to_loopback(self) -> None:
        camera = Camera(connection_mode="cloud")
        with patch("quii_helper.camera.api.CameraRtspStream") as stream_cls:
            camera.serve_rtsp()
        assert stream_cls.call_args.kwargs["host"] == "127.0.0.1"

    def test_serve_rtsp_builds_and_starts_stream(self) -> None:
        camera = Camera(connection_mode="cloud")

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
