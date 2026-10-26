"""Receive-only audio with fake/loopback cameras; no vendor or door traffic."""

import threading
import time
from collections import deque
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from quii_helper import (
    Camera,
    CameraAudioStream,
    ConfigurationError,
    QuiiConnectionError,
)
from tests.camera.test_lan_media import camera_for, local_camera
from tests.media.audio.test_frames import audio_cpacket
from tests.media.frames.test_parsing import _cpacket
from tests.protocols.tcp.test_lan_session import config, media


def message(payload, kind=0xA0):
    return {"header": SimpleNamespace(packet_type=kind), "payload": payload}


class FakeSession:
    def __init__(self, *messages):
        self.messages = deque(messages)
        self.opened = self.closed = False
        self.reads = 0

    def open(self):
        self.opened = True
        return self

    def recv_message(self, *, timeout):
        self.reads += 1
        if self.messages:
            item = self.messages.popleft()
            if isinstance(item, BaseException):
                raise item
            return item
        time.sleep(timeout)
        raise TimeoutError

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def no_cloud_or_door(monkeypatch):
    fail = Mock(side_effect=AssertionError("cloud/door call forbidden"))
    monkeypatch.setattr(
        "quii_helper.camera.connection.session.fetch_runtime_credentials", fail
    )
    monkeypatch.setattr("quii_helper.camera.api.request_open_door", fail)
    yield
    fail.assert_not_called()


def test_camera_opens_owned_session_and_context_closes_on_exception(
    monkeypatch,
):
    camera = Camera(config=config())
    session = FakeSession(message(audio_cpacket()))
    factory = Mock(return_value=session)
    monkeypatch.setattr(camera.connector, "create_lan_session", factory)
    with pytest.raises(KeyboardInterrupt):
        with camera.listen_audio() as stream:
            assert session.opened
            assert stream.recv_frame().data == b"encoded-audio"
            raise KeyboardInterrupt
    factory.assert_called_once_with()
    assert session.closed


def test_cloud_mode_is_rejected_before_connector_or_network(monkeypatch):
    camera = Camera(connection_mode="cloud")
    factory = Mock(side_effect=AssertionError("must not create a session"))
    monkeypatch.setattr(camera.connector, "create_lan_session", factory)
    with pytest.raises(
        ConfigurationError, match="requires connection_mode='lan'"
    ):
        camera.listen_audio()
    factory.assert_not_called()


def test_missing_lan_key_fails_without_connecting():
    with pytest.raises(ConfigurationError):
        Camera(config=config(stream_key="")).listen_audio()


def test_fragmented_audio_mixed_with_video_preserves_order_and_format_changes():
    first = audio_cpacket(b"first")
    second = audio_cpacket(b"second", codec=5, sample_rate=16000, channels=2)
    session = FakeSession(
        message(b"command", kind=1),
        message(_cpacket(b"video") + first[:7]),
        message(first[7:21]),
        message(first[21:] + second),
    )
    with CameraAudioStream(session) as stream:
        a = stream.recv_frame()
        reads = session.reads
        b = stream.recv_frame()
        assert a.data == b"first" and a.codec == 4
        assert b.data == b"second" and b.codec == 5
        assert b.sample_rate == 16000 and b.channels == 2
        assert session.reads == reads
    assert session.closed


def test_receive_timeout_preserves_partial_frame_and_can_be_retried():
    packet = audio_cpacket()
    session = FakeSession(message(packet[:13]))
    with CameraAudioStream(session) as stream:
        with pytest.raises(TimeoutError):
            stream.recv_frame(timeout=0.01)
        assert not session.closed
        session.messages.append(message(packet[13:]))
        assert stream.recv_frame().data == b"encoded-audio"


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_invalid_timeout_does_not_read_or_close_session(timeout):
    session = FakeSession()
    with CameraAudioStream(session) as stream:
        with pytest.raises(ValueError, match="finite and positive"):
            stream.recv_frame(timeout=timeout)
        assert session.reads == 0
        assert not session.closed


def test_continuous_video_does_not_extend_audio_timeout():
    session = FakeSession()
    session.recv_message = lambda **kwargs: message(_cpacket(b"video"))
    with CameraAudioStream(session) as stream:
        started = time.monotonic()
        with pytest.raises(TimeoutError):
            stream.recv_frame(timeout=0.01)
        assert time.monotonic() - started < 1.0
        assert not session.closed


@pytest.mark.parametrize(
    "kwargs", [{"sample_rate": 0}, {"channels": 0}, {"ms": 1000}]
)
def test_invalid_metadata_closes_instead_of_returning_unusable_audio(kwargs):
    session = FakeSession(message(audio_cpacket(**kwargs)))
    with CameraAudioStream(session) as stream:
        with pytest.raises(QuiiConnectionError) as error:
            stream.recv_frame()
        assert isinstance(error.value.__cause__, ValueError)
        assert session.closed


def test_startup_failure_closes_owned_session():
    session = FakeSession()
    session.open = Mock(side_effect=QuiiConnectionError("setup failed"))
    stream = CameraAudioStream(session)
    with pytest.raises(QuiiConnectionError, match="setup failed"):
        stream.open()
    assert session.closed


def test_receive_failure_discards_pending_state_and_prevents_reopening():
    session = FakeSession(QuiiConnectionError("connection lost"))
    stream = CameraAudioStream(session).open()
    with pytest.raises(QuiiConnectionError, match="connection lost"):
        stream.recv_frame()
    assert session.closed
    stream.close()
    for method in (stream.open, stream.recv_frame):
        with pytest.raises(QuiiConnectionError, match="closed"):
            method()


def test_unread_audio_is_not_returned_after_close():
    session = FakeSession(
        message(audio_cpacket(b"one") + audio_cpacket(b"two"))
    )
    stream = CameraAudioStream(session).open()
    assert stream.recv_frame().data == b"one"
    stream.close()
    stream.close()
    assert not stream._pending
    with pytest.raises(QuiiConnectionError, match="closed"):
        stream.recv_frame()


def test_long_stream_does_not_retain_previous_frames():
    session = FakeSession()
    session.recv_message = lambda **kwargs: message(audio_cpacket())
    with CameraAudioStream(session) as stream:
        for _ in range(2000):
            assert stream.recv_frame().data == b"encoded-audio"
            assert not stream._pending
        assert stream._packer.stats["trailing_partial_bytes"] == 0


def test_loopback_tcp_decodes_fragmented_audio_and_closes_socket(tmp_path):
    packet = audio_cpacket(b"loopback-audio")
    with local_camera([media(packet[:12]), media(packet[12:])]) as (
        port,
        closed,
    ):
        with camera_for(port, tmp_path).listen_audio() as stream:
            assert stream.recv_frame().data == b"loopback-audio"
        assert closed.wait(2)
    assert not list(tmp_path.iterdir())


def test_loopback_eof_is_an_error_not_silent_end_of_audio(tmp_path):
    with local_camera([], disconnect=True) as (port, _):
        with camera_for(port, tmp_path).listen_audio() as stream:
            with pytest.raises(QuiiConnectionError):
                stream.recv_frame()


def test_close_interrupts_another_threads_loopback_receive(
    tmp_path, monkeypatch
):
    with local_camera([]) as (port, closed):
        stream = camera_for(port, tmp_path).listen_audio()
        reading, errors = threading.Event(), []
        original = stream._session.recv_message

        def receive(**kwargs):
            reading.set()
            return original(**kwargs)

        monkeypatch.setattr(stream._session, "recv_message", receive)

        def read():
            try:
                stream.recv_frame(timeout=10)
            except QuiiConnectionError as exc:
                errors.append(exc)

        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        assert reading.wait(2)
        stream.close()
        reader.join(2)
        assert not reader.is_alive()
        assert errors and closed.wait(2)


def test_example_uses_saved_credentials_and_prints_only_metadata(
    monkeypatch, capsys
):
    from examples import listen_audio

    stream = CameraAudioStream(
        FakeSession(message(audio_cpacket(b"private-speech") * 10))
    ).open()
    saved = SimpleNamespace(
        device_id="test-device", stream_key="S" * 32, auth_code="test-auth"
    )
    load = Mock(return_value=saved)
    settings = config()
    camera = Mock(return_value=SimpleNamespace(listen_audio=lambda: stream))
    monkeypatch.setattr(listen_audio.CameraStreamCredentials, "load", load)
    monkeypatch.setattr(listen_audio, "load_config", lambda: settings)
    monkeypatch.setattr(listen_audio, "Camera", camera)
    monkeypatch.setattr(
        listen_audio, "configure_logging", lambda **kwargs: None
    )

    listen_audio.main()

    load.assert_called_once_with("data/stream_credentials.json")
    camera.assert_called_once_with(
        config=settings,
        connection_mode="lan",
        device_id="test-device",
        stream_key="S" * 32,
        auth_code="test-auth",
    )
    output = capsys.readouterr().out
    assert len(output.splitlines()) == 10
    assert "codec=g711_alaw sample_rate=8000 channels=1" in output
    assert "private-speech" not in output and saved.stream_key not in output
    assert stream._session.closed


def test_close_during_frame_assembly_discards_newly_completed_audio(
    monkeypatch,
):
    session = FakeSession(message(audio_cpacket()))
    stream = CameraAudioStream(session).open()
    assembling, release, closed = (
        threading.Event(),
        threading.Event(),
        threading.Event(),
    )
    original_feed = stream._packer.feed
    errors = []

    def feed(payload):
        assembling.set()
        assert release.wait(2)
        return original_feed(payload)

    def close_session():
        session.closed = True
        closed.set()

    def read():
        try:
            stream.recv_frame()
        except QuiiConnectionError as exc:
            errors.append(exc)

    monkeypatch.setattr(stream._packer, "feed", feed)
    monkeypatch.setattr(session, "close", close_session)
    reader = threading.Thread(target=read, daemon=True)
    closer = threading.Thread(target=stream.close, daemon=True)
    reader.start()
    try:
        assert assembling.wait(2)
        closer.start()
        assert closed.wait(2)
    finally:
        release.set()
        reader.join(2)
        if closer.ident is not None:
            closer.join(2)
    assert not reader.is_alive() and not closer.is_alive()
    assert errors and not stream._pending
    assert stream._packer.stats["trailing_partial_bytes"] == 0
