"""Exercise the installed RTSP command with a synthetic loopback camera."""

import os
import socket
from threading import Event
from unittest.mock import MagicMock, Mock, PropertyMock, call

import pytest

from quii_helper import Camera, CameraStreamCredentials, cli
from quii_helper.camera.streaming.rtsp import CameraRtspStream
from tests.camera.test_lan_media import ANNEXB, local_camera
from tests.media.frames.test_parsing import _cpacket
from tests.protocols.tcp.test_lan_session import KEY, media
from tests.streaming.test_rtsp_server import _recv_until, _rtsp_request

AUTH = "synthetic-private-auth"


@pytest.fixture(autouse=True)
def synthetic_environment(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(os, "environ", {})
    monkeypatch.setenv("CAMERA_DEVICE_HOST", "127.0.0.1")
    monkeypatch.setenv("AUTH_CODE", AUTH)
    monkeypatch.setenv("STREAM_KEY", KEY)
    forbidden = Mock(side_effect=AssertionError("cloud/door call forbidden"))
    monkeypatch.setattr(
        "quii_helper.camera.connection.session.fetch_runtime_credentials",
        forbidden,
    )
    monkeypatch.setattr("quii_helper.camera.api.request_open_door", forbidden)
    connect = socket.socket.connect

    def loopback_only(sock, address):
        assert address[0] == "127.0.0.1"
        return connect(sock, address)

    monkeypatch.setattr(socket.socket, "connect", loopback_only)
    yield
    forbidden.assert_not_called()


@pytest.fixture
def ephemeral_rtsp_port(monkeypatch):
    serve = Camera.serve_rtsp

    def use_free_port(camera, **kwargs):
        assert camera.config.connection_mode == "lan"
        return serve(camera, **(kwargs | {"port": 0}))

    monkeypatch.setattr(Camera, "serve_rtsp", use_free_port)


def test_rtsp_help_does_not_load_settings(monkeypatch, capsys):
    load = Mock(side_effect=AssertionError("read settings from --help"))
    monkeypatch.setattr(cli.SettingsLoader, "load", load)
    with pytest.raises(SystemExit) as exc:
        cli.main(["rtsp", "--help"])
    assert exc.value.code == 0
    assert "--credentials" in capsys.readouterr().out
    load.assert_not_called()


@pytest.mark.parametrize("args", [["--port", "65536"], []])
def test_invalid_port_or_cloud_mode_does_not_create_camera(
    args, monkeypatch, capsys
):
    camera = Mock(
        side_effect=AssertionError("created camera without valid settings")
    )
    monkeypatch.setattr(cli, "Camera", camera)
    monkeypatch.setenv("CAMERA_CONNECTION_MODE", "cloud")
    if args:
        with pytest.raises(SystemExit) as exc:
            cli.main(["rtsp", *args])
        assert exc.value.code == 2
        assert "use a port from 1 to 65535" in capsys.readouterr().err
    else:
        assert cli.main(["rtsp"]) == 1
        assert "CAMERA_CONNECTION_MODE" in capsys.readouterr().err
    camera.assert_not_called()


def test_rtsp_serves_saved_pair_and_closes_on_ctrl_c(
    monkeypatch, capsys, ephemeral_rtsp_port
):
    saved = CameraStreamCredentials("synthetic-camera", KEY, AUTH).save(
        "private.json"
    )
    monkeypatch.setenv("STREAM_KEY", "invalid-configured-key")
    original_wait = CameraRtspStream.wait

    def wait(stream, timeout=None):
        if timeout is not None:
            return original_wait(stream, timeout)
        assert stream.ready
        with socket.create_connection(
            ("127.0.0.1", stream.server.port), timeout=2
        ) as viewer:
            viewer.sendall(_rtsp_request("DESCRIBE", stream.url, 1))
            assert b"RTSP/1.0 200 OK" in _recv_until(
                viewer, b"sprop-parameter-sets"
            )
        raise KeyboardInterrupt

    monkeypatch.setattr(CameraRtspStream, "wait", wait)
    with local_camera([media(_cpacket(ANNEXB))]) as (port, closed):
        monkeypatch.setenv("CAMERA_STREAM_PORT", str(port))
        assert cli.main(["rtsp", "--credentials", str(saved)]) == 130
        assert closed.wait(2)
    captured = capsys.readouterr()
    assert "RTSP stream ready: rtsp://127.0.0.1:" in captured.out
    assert not captured.err
    for value in (KEY, AUTH, str(saved)):
        assert value not in captured.out + captured.err


@pytest.mark.parametrize("reconnect", [False, True])
def test_rtsp_reports_listener_error_without_connecting(
    monkeypatch, capsys, reconnect
):
    serve = Mock(side_effect=OSError("synthetic-private-error"))
    monkeypatch.setattr(Camera, "serve_rtsp", serve)
    args = ["rtsp", "--port", "8555"]
    if reconnect:
        args.append("--reconnect")
    assert cli.main(args) == 1
    serve.assert_called_once_with(port=8555, reconnect=reconnect)
    captured = capsys.readouterr()
    assert "local RTSP listener" in captured.err
    assert "synthetic-private-error" not in captured.err


def test_rtsp_reports_tcp_connect_failure(
    monkeypatch, capsys, ephemeral_rtsp_port
):
    connect = Mock(
        side_effect=ConnectionRefusedError("synthetic-private-error")
    )
    monkeypatch.setattr(socket, "create_connection", connect)
    assert cli.main(["rtsp"]) == 1
    connect.assert_called_once()
    captured = capsys.readouterr()
    assert "Cannot connect to the camera over LAN" in captured.err
    assert "synthetic-private-error" not in captured.out + captured.err


@pytest.mark.parametrize("first_poll_started", [True, False])
def test_rtsp_startup_deadline_does_not_cancel_recovery_after_first_video(
    first_poll_started, monkeypatch, capsys
):
    stream = MagicMock(spec=CameraRtspStream)
    stream.__enter__.return_value = stream
    type(stream).playback_started = PropertyMock(
        side_effect=[first_poll_started, True]
    )
    stream.ready = False
    stream.wait.side_effect = (
        KeyboardInterrupt if first_poll_started else [None, KeyboardInterrupt]
    )
    monkeypatch.setattr(Camera, "serve_rtsp", Mock(return_value=stream))
    monkeypatch.setattr(cli, "monotonic", Mock(side_effect=[0.0, 45.0]))

    assert cli.main(["rtsp", "--reconnect"]) == 130
    assert stream.wait.call_args_list == (
        [call()] if first_poll_started else [call(timeout=0), call()]
    )
    captured = capsys.readouterr()
    assert "RTSP stream ready" not in captured.out
    assert not captured.err


def test_rtsp_deadline_accepts_ready_media_before_announcement(
    monkeypatch, capsys, ephemeral_rtsp_port
):
    send_media, before_announcement = Event(), Event()
    real_wait = CameraRtspStream.wait

    def delay_announcement(stream):
        before_announcement.set()
        assert stream._stop_event.wait(5)

    def expire_after_media():
        send_media.set()
        assert before_announcement.wait(2)
        return cli.RTSP_STARTUP_TIMEOUT_SECONDS

    def wait(stream, timeout=None):
        if timeout is not None:
            return real_wait(stream, timeout)
        assert stream.ready
        with socket.create_connection(
            ("127.0.0.1", stream.server.port), timeout=2
        ) as viewer:
            viewer.sendall(_rtsp_request("DESCRIBE", stream.url, 1))
            response = _recv_until(viewer, b"a=control:trackID=0\r\n")
            assert b"RTSP/1.0 200 OK" in response
            assert b"sprop-parameter-sets=" in response
        raise KeyboardInterrupt

    clock = Mock()
    clock.side_effect = lambda: (
        0.0 if clock.call_count == 1 else expire_after_media()
    )
    monkeypatch.setattr(cli, "monotonic", clock)
    monkeypatch.setattr(
        CameraRtspStream, "_announce_ready_once", delay_announcement
    )
    monkeypatch.setattr(CameraRtspStream, "wait", wait)
    with local_camera([media(_cpacket(ANNEXB))], before_media=send_media) as (
        port,
        closed,
    ):
        monkeypatch.setenv("CAMERA_STREAM_PORT", str(port))
        assert cli.main(["rtsp", "--reconnect"]) == 130
        assert closed.wait(2)
    captured = capsys.readouterr()
    assert "RTSP stream ready: rtsp://127.0.0.1:" in captured.out
    assert not captured.err


@pytest.mark.parametrize("phase", ["setup_status", "play_status"])
def test_rtsp_reports_explicit_device_rejection(
    phase, monkeypatch, capsys, ephemeral_rtsp_port
):
    with local_camera([], **{phase: 1}) as (port, _):
        monkeypatch.setenv("CAMERA_STREAM_PORT", str(port))
        assert cli.main(["rtsp"]) == 1
    captured = capsys.readouterr()
    assert "camera rejected LAN setup or playback" in captured.err
    assert "RTSP stream ready" not in captured.out


@pytest.mark.parametrize(
    "packets",
    [
        [],
        [media(_cpacket(b"\x00\x00\x01\x65idr"))],
        [media(_cpacket(ANNEXB.removesuffix(b"\x00\x00\x00\x01\x65idr")))],
    ],
)
def test_rtsp_without_usable_video_times_out_and_closes(
    packets, monkeypatch, capsys, ephemeral_rtsp_port
):
    monkeypatch.setattr(cli, "RTSP_STARTUP_TIMEOUT_SECONDS", 0.5)
    with local_camera(packets) as (port, closed):
        monkeypatch.setenv("CAMERA_STREAM_PORT", str(port))
        assert cli.main(["rtsp"]) == 1
        assert closed.wait(2)
    captured = capsys.readouterr()
    assert "No playable H.264 video" in captured.err
    assert "RTSP stream ready" not in captured.out
