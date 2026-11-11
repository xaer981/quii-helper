from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from quii_helper.camera import Camera
from quii_helper.camera.streaming import CameraRtspStream
from quii_helper.config import AutonomousConfig
from quii_helper.preview.pipeline.config import (
    DEFAULT_PREVIEW_CAPTURE_SETTINGS,
)
from tests.media.frames.test_parsing import _cpacket

H264_PARAMETERS = b"\x00\x00\x01\x67sps\x00\x00\x01\x68pps"
H264_IDR = b"\x00\x00\x01\x65idr"


def _feed_video(stream, bitstream):
    stream._feed_assembler_message(
        {
            "header": SimpleNamespace(packet_type=0xA0),
            "payload": _cpacket(
                bitstream, frame_stamp=(26 << 26) | (1 << 22) | (1 << 17)
            ),
        }
    )


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
            port=0,
        )
        with stream.server:
            _feed_video(stream, H264_PARAMETERS)
            assert not stream.ready and not statuses
            _feed_video(stream, H264_IDR)
            assert not stream.ready and not statuses
            stream.server.audio_format = G711Format(4)
            _feed_video(stream, H264_IDR)
            assert stream.ready
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

    def test_rtsp_ready_status_requires_idr_with_decoder_parameters(
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
            port=0,
        )
        with stream.server:
            _feed_video(stream, H264_IDR)
            assert not stream.ready and not statuses
            _feed_video(stream, H264_PARAMETERS)
            _feed_video(stream, b"\x00\x00\x01\x41p")
            assert not stream.ready and not statuses
            _feed_video(stream, H264_IDR)
            _feed_video(stream, H264_IDR)
            assert stream.ready
            assert statuses == [f"RTSP stream ready: {stream.url}"]
        assert not stream.ready
