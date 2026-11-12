import socket
import threading
import time
from base64 import b64encode
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from quii_helper.camera.streaming import rtsp
from quii_helper.preview.pipeline.config import (
    DEFAULT_PREVIEW_CAPTURE_SETTINGS,
)
from quii_helper.protocols.tcp.live.session import (
    LanTcpConnectError,
    LanTcpRejectedError,
    LanTcpTransportError,
)
from quii_helper.streaming.rtsp import server as rtsp_server
from quii_helper.support.errors import QuiiConnectionError
from tests.camera.test_lan_media import ANNEXB, _read_exact
from tests.media.frames.test_parsing import _cpacket
from tests.protocols.tcp.test_lan_session import (
    command,
    media,
    session_and_socket,
)
from tests.streaming.test_rtsp_server import _recv_until, _rtsp_request

VIDEO = media(_cpacket(ANNEXB))


@pytest.fixture
def stream(tmp_path, monkeypatch):
    monkeypatch.setattr(rtsp, "LAN_RECONNECT_DELAYS", (0, 0, 0))
    camera_stream = rtsp.CameraRtspStream(
        connector=Mock(),
        preview_settings=DEFAULT_PREVIEW_CAPTURE_SETTINGS,
        data_dir=tmp_path,
        emit=Mock(),
        status=Mock(),
        port=0,
        connection_mode="lan",
        reconnect=True,
    )
    yield camera_stream
    camera_stream.close()
    camera_stream.connector.fetch_credentials.assert_not_called()
    camera_stream.connector.create_lan_talk_session.assert_not_called()


def _source(*packets):
    session, sock = session_and_socket()
    sock.chunks.extend((command(), *packets))
    return session, sock


def _watch_status(stream, prefix):
    event = threading.Event()
    previous = stream.status

    def status(message):
        previous(message)
        if message.startswith(prefix):
            event.set()

    stream.status = status
    return event


def test_eof_replaces_source_and_keeps_the_rtsp_listener(stream):
    first, first_socket = _source(VIDEO)
    second, second_socket = _source(
        media(_cpacket(b"\x00\x00\x01\x65idr-without-new-parameters"))
    )
    broken, waiting_for_parameters, send_parameters, send_rtp = (
        threading.Event() for _ in range(4)
    )
    read_first, read_second = first_socket.recv, second_socket.recv
    fresh = ANNEXB.replace(b"sps", b"fresh-sps")
    recovery = _watch_status(stream, "LAN RTSP reconnected:")
    ready = _watch_status(stream, "RTSP stream ready:")
    resuming, resume_allowed = threading.Event(), threading.Event()
    resume_media = stream.server.resume_media

    def resume():
        resuming.set()
        assert resume_allowed.wait(3)
        resume_media()

    stream.server.resume_media = resume

    def first_recv(size):
        if not first_socket.chunks:
            assert broken.wait(3)
        return read_first(size)

    def second_recv(size):
        if not second_socket.chunks:
            if waiting_for_parameters.is_set():
                if not send_rtp.wait(0.01) or second_socket.closed:
                    raise TimeoutError
                send_rtp.clear()
                p_frame = _cpacket(b"\x00\x00\x01\x41p", frame_tag=0xE0)
                second_socket.chunks.extend(
                    (media(p_frame), media(_cpacket(fresh)))
                )
            else:
                waiting_for_parameters.set()
                assert send_parameters.wait(3)
                second_socket.chunks.append(media(_cpacket(fresh)))
        return read_second(size)

    first_socket.recv, second_socket.recv = first_recv, second_recv
    stream.connector.create_lan_session.side_effect = [first, second]
    stream.start()
    try:
        assert ready.wait(2)
        talk = Mock()
        talk.close.side_effect = lambda: stream._talk_finished(talk)
        stream._talk = talk
        listener, url = stream.server._sock, stream.url
        with socket.create_connection(
            ("127.0.0.1", stream.server.port), timeout=2
        ) as old_viewer:
            old_viewer.sendall(_rtsp_request("OPTIONS", url, 1))
            assert b"200 OK" in _recv_until(old_viewer, b"\r\n\r\n")
            broken.set()
            assert waiting_for_parameters.wait(2)
            assert old_viewer.recv(1) == b""
            assert first_socket.closed
            talk.close.assert_called_once()
            assert not stream.ready and not stream.server.parameter_sets
            with pytest.raises(QuiiConnectionError, match="active preview"):
                stream.start_talk()
        send_parameters.set()
        assert resuming.wait(2)
        assert stream.server.video_ready.is_set()
        assert stream.playback_started and not stream.ready
        resume_allowed.set()
        assert recovery.wait(2)
        assert stream.ready
        assert stream.server._sock is listener and stream.url == url
        with socket.create_connection(
            ("127.0.0.1", stream.server.port), timeout=2
        ) as viewer:
            viewer.sendall(_rtsp_request("DESCRIBE", url, 1))
            sdp = _recv_until(viewer, b"a=control:trackID=0\r\n")
            assert b"200 OK" in sdp
            assert b64encode(b"\x67fresh-sps") in sdp
            viewer.sendall(
                _rtsp_request(
                    "SETUP",
                    f"{url}/trackID=0",
                    2,
                    {"Transport": "RTP/AVP/TCP;unicast;interleaved=0-1"},
                )
            )
            assert b"200 OK" in _recv_until(viewer, b"\r\n\r\n")
            viewer.sendall(_rtsp_request("PLAY", url, 3))
            assert b"200 OK" in _recv_until(viewer, b"\r\n\r\n")
            send_rtp.set()
            header = _read_exact(viewer, 4)
            assert header[:2] == b"$\x00"
            rtp = _read_exact(viewer, int.from_bytes(header[2:4], "big"))
            assert rtp[12:] == b"\x67fresh-sps"
        assert stream.connector.create_lan_session.call_count == 2
    finally:
        broken.set()
        send_parameters.set()
        resume_allowed.set()
    stream.close()
    assert second_socket.closed and stream.server._sock is None


@pytest.mark.parametrize("stalled_read", [TimeoutError(), command()])
def test_video_stall_retries_even_with_control_traffic(stream, stalled_read):
    first, sock = _source(VIDEO)
    read = sock.recv

    def stalled_recv(size):
        if not sock.chunks:
            stream.server.last_video_at -= rtsp.LAN_VIDEO_STALL_SECONDS + 1
            sock.chunks.append(stalled_read)
        return read(size)

    sock.recv = stalled_recv
    rejected, rejected_socket = session_and_socket()
    rejected_socket.chunks.append(command(status=1))
    stream.connector.create_lan_session.side_effect = [first, rejected]
    stream.start()
    with pytest.raises(LanTcpRejectedError, match="play rejected"):
        stream.wait(2)
    assert sock.closed and rejected_socket.closed
    assert stream.connector.create_lan_session.call_count == 2


@pytest.mark.parametrize("recovering", [False, True])
@pytest.mark.parametrize("late_by", [0.0, 0.125])
def test_keyframe_at_or_after_deadline_is_not_published(
    stream, monkeypatch, recovering, late_by
):
    monkeypatch.setattr(rtsp, "LAN_RECONNECT_DELAYS", (0,))
    now = [100.0]
    clock = SimpleNamespace(monotonic=lambda: now[0], sleep=time.sleep)
    monkeypatch.setattr(rtsp, "time", clock)
    monkeypatch.setattr(rtsp_server, "time", clock)
    publish = Mock(wraps=stream.server.publish)
    monkeypatch.setattr(stream.server, "publish", publish)
    deadline = now[0] + rtsp.LAN_VIDEO_STALL_SECONDS
    first, _ = _source(VIDEO)
    source, sock = _source() if recovering else _source(VIDEO)
    read = sock.recv
    read_timeouts = []

    def delayed_recv(size):
        if not sock.chunks and len(read_timeouts) < 2:
            read_timeouts.append(sock.timeout)
            if len(read_timeouts) == 1:
                now[0] = deadline - 0.25
                raise TimeoutError
            now[0] = deadline + late_by
            sock.chunks.append(VIDEO)
        return read(size)

    sock.recv = delayed_recv
    stream.connector.create_lan_session.side_effect = (
        [first, source]
        if recovering
        else [source, LanTcpConnectError("unreachable")]
    )
    stream.start()
    stream._thread.join(2)
    assert not stream._thread.is_alive()
    with pytest.raises(
        LanTcpTransportError, match="attempts exhausted"
    ) as error:
        stream.wait(0)
    assert publish.call_count == 1
    assert read_timeouts == pytest.approx([1.0, 0.25])
    if recovering:
        assert "timed out waiting for video" in str(error.value.__cause__)
    assert sock.closed and stream.connector.create_lan_session.call_count == 2


def test_retries_are_bounded_and_close_listener_when_exhausted(stream):
    first, sock = _source(VIDEO)
    stream.connector.create_lan_session.side_effect = [
        first,
        LanTcpConnectError("unreachable"),
        LanTcpConnectError("unreachable"),
        LanTcpConnectError("unreachable"),
    ]
    stream.start()
    with pytest.raises(LanTcpTransportError, match="attempts exhausted"):
        stream.wait(2)
    assert sock.closed
    assert stream.connector.create_lan_session.call_count == 4
    assert stream.server._sock is None


def test_single_keyframe_on_each_retry_does_not_reset_budget(stream):
    sources = [_source(VIDEO) for _ in range(5)]
    stream.connector.create_lan_session.side_effect = [
        session for session, _ in sources
    ]
    stream.start()
    with pytest.raises(LanTcpTransportError, match="attempts exhausted"):
        stream.wait(2)
    assert stream.connector.create_lan_session.call_count == 4
    assert all(sock.closed for _, sock in sources[:4])
    assert not sources[4][1].closed


def test_stable_video_resets_reconnect_budget(stream, monkeypatch):
    monkeypatch.setattr(rtsp, "LAN_RECONNECT_DELAYS", (0,))
    now = [100.0]
    clock = SimpleNamespace(monotonic=lambda: now[0], sleep=time.sleep)
    monkeypatch.setattr(rtsp, "time", clock)
    monkeypatch.setattr(rtsp_server, "time", clock)
    first, _ = _source(VIDEO)
    stable, sock = _source(VIDEO)
    read = sock.recv
    frames = iter((110.0, 120.0, 130.0))

    def stable_recv(size):
        if not sock.chunks and (timestamp := next(frames, None)) is not None:
            now[0] = timestamp
            sock.chunks.append(VIDEO)
        return read(size)

    sock.recv = stable_recv
    stream.connector.create_lan_session.side_effect = [
        first,
        stable,
        LanTcpConnectError("unreachable again"),
    ]
    stream.start()
    stream._thread.join(2)
    assert not stream._thread.is_alive()
    with pytest.raises(
        LanTcpTransportError, match="attempts exhausted"
    ) as error:
        stream.wait(0)
    assert isinstance(error.value.__cause__, LanTcpConnectError)
    assert stream.connector.create_lan_session.call_count == 3


def test_reconnected_socket_without_playable_video_consumes_attempt(
    stream, monkeypatch
):
    monkeypatch.setattr(rtsp, "LAN_RECONNECT_DELAYS", (0,))
    now = [time.monotonic()]
    monkeypatch.setattr(
        rtsp,
        "time",
        SimpleNamespace(monotonic=lambda: now[0], sleep=time.sleep),
    )
    first, _ = _source(VIDEO)
    retry, sock = _source(media(_cpacket(b"\x00\x00\x01\x65no-parameters")))
    read = sock.recv

    def stalled_recv(size):
        if not sock.chunks:
            now[0] += rtsp.LAN_VIDEO_STALL_SECONDS + 1
            raise TimeoutError
        return read(size)

    sock.recv = stalled_recv
    stream.connector.create_lan_session.side_effect = [first, retry]
    stream.start()
    # Join with real time: the simulated clock only measures source inactivity.
    stream._thread.join(2)
    assert not stream._thread.is_alive()
    with pytest.raises(
        LanTcpTransportError, match="attempts exhausted"
    ) as error:
        stream.wait(0)
    assert "timed out waiting for video" in str(error.value.__cause__)
    assert sock.closed and stream.server._sock is None
    assert stream.connector.create_lan_session.call_count == 2


@pytest.mark.parametrize(
    "reconnect,initial_video", [(False, True), (True, False)]
)
def test_no_retry_by_default_or_before_initial_video(
    stream, reconnect, initial_video
):
    stream.reconnect = reconnect
    first, _ = _source(*([VIDEO] if initial_video else []))
    stream.connector.create_lan_session.return_value = first
    stream.start()
    with pytest.raises(LanTcpTransportError, match="LAN TCP receive failed"):
        stream.wait(2)
    stream.connector.create_lan_session.assert_called_once()


def test_close_cancels_pending_reconnect(stream, monkeypatch):
    monkeypatch.setattr(rtsp, "LAN_RECONNECT_DELAYS", (60,))
    first, sock = _source(VIDEO)
    retrying = _watch_status(stream, "LAN RTSP reconnecting")
    stream.connector.create_lan_session.return_value = first
    stream.start()
    assert retrying.wait(2)
    worker = stream._thread
    stream.close()
    assert worker is not None and not worker.is_alive()
    assert sock.closed and stream.server._sock is None
    stream.wait(0)
    stream.connector.create_lan_session.assert_called_once()
