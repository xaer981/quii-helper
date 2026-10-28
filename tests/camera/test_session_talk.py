"""One preview for RTSP and talk; fake PCM devices and loopback only."""

import socket
import struct
import threading
import time
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from quii_helper import (
    AudioDeviceError,
    Camera,
    ConfigurationError,
    QuiiConnectionError,
)
from quii_helper.camera.streaming import conversation
from quii_helper.media.audio.g711 import decode_g711, encode_g711
from tests.camera.test_conversation import Device
from tests.camera.test_talk_session import (
    FakePreview,
    FakeTalk,
    local_duplex_camera,
    wait_until,
)
from tests.media.audio.test_frames import audio_cpacket
from tests.protocols.tcp.test_lan_session import config
from tests.streaming.test_h264_live import _cpacket

IDR = b"\x00\x00\x01\x67sps\x00\x00\x01\x68pps\x00\x00\x01\x65idr"


class Preview(FakePreview):
    def __init__(self):
        super().__init__(initial=[])
        self.config = config(connect_timeout=0.25)
        self.opens = 0

    def open(self):
        self.opens += 1
        return super().open()

    def __enter__(self):
        return self.open()

    def __exit__(self, *args):
        self.close()

    def recv_message(self, *, timeout):
        message = super().recv_message(timeout=timeout)
        return {**message, "header": SimpleNamespace(packet_type=0xA0)}


@contextmanager
def running_preview(monkeypatch, *, audio=False, feed_audio=True):
    preview, devices, backends = Preview(), [], []
    camera = Camera(config=config())
    create_preview = Mock(return_value=preview)
    monkeypatch.setattr(camera.connector, "create_lan_session", create_preview)

    def create_talk():
        backend = FakeTalk()
        backend.config = config(connect_timeout=0.25)
        backends.append(backend)
        return backend

    monkeypatch.setattr(
        camera.connector,
        "create_lan_talk_session",
        Mock(side_effect=create_talk),
    )

    def create_device(*args):
        device = Device()
        devices.append(device)
        return device

    monkeypatch.setattr(conversation, "open_duplex_device", create_device)
    stop = threading.Event()

    def feed():
        while not stop.wait(0.02):
            video = bytearray(_cpacket(IDR))
            struct.pack_into("<I", video, 8, 0x6AA12345)
            payload = bytes(video)
            if feed_audio:
                payload += audio_cpacket(b"\xd5" * 320)
            preview.push(payload)

    feeder = threading.Thread(target=feed)
    feeder.start()
    stream = camera.serve_rtsp(port=0, audio=audio)
    try:
        wait_until(lambda: stream.assembler.access_unit_count > 0)
        yield stream, preview, backends, devices, camera
    finally:
        stream.close()
        stop.set()
        feeder.join(2)
        assert not feeder.is_alive()
    create_preview.assert_called_once_with()
    assert preview.opens == 1
    assert all(device.closed for device in devices)
    assert all(backend.closed.is_set() for backend in backends)


@pytest.mark.parametrize("audio", [False, True])
def test_rtsp_and_conversation_share_one_preview_and_one_frame_packer(
    monkeypatch, audio
):
    with running_preview(monkeypatch, audio=audio) as (
        stream,
        preview,
        backends,
        devices,
        camera,
    ):
        preview_reader = stream._thread
        packer = stream.assembler.packer
        handle = stream.start_talk()
        try:
            assert handle.active and stream.talk_active
            assert stream.stats["talk_active"] is True
            assert handle._talk._preview is None
            assert handle._talk._preview_worker is None
            assert handle._talk._packer.stats["completed"] == 0
            backend, device = backends[0], devices[0]
            wait_until(
                lambda: bool(handle._talk._received)
                or bool(handle._talk._worker)
            )
            pcm = b"\xe8\x03" * 320
            device.callback.send(bytearray(pcm))
            wait_until(lambda: bool(backend.sent))
            assert backend.sent[0][1] == encode_g711(pcm, 4)
            expected = decode_g711(b"\xd5" * 320, 4)
            output = []
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline:
                output.append(device.callback.send(bytearray(640)))
                if expected in output:
                    break
                time.sleep(0.01)
            assert expected in output
            before = stream.assembler.access_unit_count
            stream.stop_talk()
            stream.stop_talk()
            handle.wait(timeout=1)
            assert not handle.active and not stream.talk_active
            assert device.closed and backend.closed.is_set()
            assert not preview.closed.is_set()
            wait_until(lambda: stream.assembler.access_unit_count > before)
            assert (
                stream._thread is preview_reader
                and stream.assembler.packer is packer
            )
            with socket.create_connection(
                ("127.0.0.1", stream.server.port), timeout=1
            ) as client:
                client.sendall(
                    f"DESCRIBE {stream.url} RTSP/1.0\r\nCSeq: 1\r\n\r\n".encode()
                )
                assert client.recv(4096).startswith(b"RTSP/1.0 200")
            assert stream.talk_error is None
        finally:
            handle.close()


def test_talk_context_closes_only_talk_and_can_be_started_again(monkeypatch):
    with running_preview(monkeypatch) as (
        stream,
        preview,
        backends,
        devices,
        camera,
    ):
        with stream.start_talk() as first:
            with pytest.raises(RuntimeError, match="already"):
                stream.start_talk()
            assert first.active
        assert not preview.closed.is_set()
        second = stream.start_talk()
        assert second is not first and second.active
        assert len(backends) == 2
        assert first._talk._stopped.is_set()


def test_talk_transport_failure_is_reported_without_stopping_rtsp(monkeypatch):
    with running_preview(monkeypatch) as (
        stream,
        preview,
        backends,
        devices,
        camera,
    ):
        handle = stream.start_talk()
        failure = QuiiConnectionError("talk disconnected")
        backends[0].push(failure)
        with pytest.raises(QuiiConnectionError, match="talk disconnected"):
            handle.wait(timeout=1)
        wait_until(lambda: stream.talk_error is failure)
        assert not stream.talk_active and devices[0].closed
        assert not preview.closed.is_set()
        before = stream.assembler.access_unit_count
        wait_until(lambda: stream.assembler.access_unit_count > before)


def test_preview_failure_stops_microphone_and_talk_and_reaches_parent_wait(
    monkeypatch,
):
    with running_preview(monkeypatch) as (
        stream,
        preview,
        backends,
        devices,
        camera,
    ):
        handle = stream.start_talk()
        preview.push(QuiiConnectionError("preview disconnected"))
        with pytest.raises(QuiiConnectionError, match="preview disconnected"):
            stream.wait(timeout=2)
        assert not handle.active and devices[0].closed
        assert backends[0].closed.is_set()


def test_missing_extra_does_not_open_talk_or_stop_video(monkeypatch):
    with running_preview(monkeypatch) as (
        stream,
        preview,
        backends,
        devices,
        camera,
    ):
        failure = ConfigurationError("install audio extra")
        monkeypatch.setattr(
            conversation, "open_duplex_device", Mock(side_effect=failure)
        )
        with pytest.raises(ConfigurationError, match="audio extra"):
            stream.start_talk()
        assert not preview.closed.is_set() and stream._thread.is_alive()
        assert stream.talk_error is failure
        assert backends[0].opened is False


def test_video_without_audio_times_out_before_talk_activation(monkeypatch):
    with running_preview(monkeypatch, feed_audio=False) as (
        stream,
        preview,
        backends,
        devices,
        camera,
    ):
        with pytest.raises(
            QuiiConnectionError, match="shared preview.*startup deadline"
        ):
            stream.start_talk()
        assert not backends[0].opened and devices[0].closed
        assert not preview.closed.is_set() and stream._thread.is_alive()


def test_unsupported_audio_only_fails_talk_not_video_only_rtsp(monkeypatch):
    with running_preview(monkeypatch) as (
        stream,
        preview,
        backends,
        devices,
        camera,
    ):
        handle = stream.start_talk()
        preview.push(audio_cpacket(codec=9))
        with pytest.raises(QuiiConnectionError, match="unsupported"):
            handle.wait(timeout=1)
        assert not preview.closed.is_set() and stream._thread.is_alive()
        assert devices[0].closed


def test_preview_alone_opens_no_talk_or_audio_devices(monkeypatch):
    with running_preview(monkeypatch) as (
        stream,
        preview,
        backends,
        devices,
        camera,
    ):
        stream.stop_talk()
        assert backends == devices == []
        camera.connector.create_lan_talk_session.assert_not_called()


def test_session_with_real_virtual_audio_backend_never_touches_hardware(
    monkeypatch,
):
    audio = pytest.importorskip("miniaudio")
    with running_preview(monkeypatch) as (
        stream,
        preview,
        backends,
        devices,
        camera,
    ):
        device = audio.DuplexStream(
            playback_format=audio.SampleFormat.SIGNED16,
            playback_channels=1,
            capture_format=audio.SampleFormat.SIGNED16,
            capture_channels=1,
            sample_rate=8000,
            buffersize_msec=40,
            backends=[audio.Backend.NULL],
        )
        assert device.backend.lower() == "null"
        monkeypatch.setattr(
            conversation, "open_duplex_device", lambda *args: device
        )
        handle = stream.start_talk()
        try:
            wait_until(lambda: len(backends[0].sent) >= 3)
        finally:
            stream.stop_talk()
        assert not device.running and not handle._thread.is_alive()
        assert not preview.closed.is_set() and stream._thread.is_alive()


@pytest.mark.parametrize("codec", [4, 5])
@pytest.mark.parametrize("full_packet", [False, True])
def test_one_preview_and_generic_talk_over_real_loopback_tcp(
    monkeypatch, codec, full_packet
):
    monkeypatch.setattr(
        "quii_helper.camera.streaming.rtsp.STREAM_PACKET_TIMEOUT_SECONDS", 0.02
    )
    device = Device()
    monkeypatch.setattr(
        conversation, "open_duplex_device", lambda *args: device
    )
    with local_duplex_camera(
        codec=codec,
        full_packet=full_packet,
        panel=2,
        stream=2,
        periodic_preview=True,
    ) as (port, sent, preview_closed, talk_closed):
        camera = Camera(
            config=config(
                stream_port=port,
                channel=2,
                stream=2,
                connect_timeout=1,
                live_keepalive_interval=0.03,
            )
        )
        with camera.serve_rtsp(port=0) as session:
            handle = session.start_talk()
            pcm = b"\xe8\x03" * 320
            device.callback.send(bytearray(pcm))
            wait_until(lambda: any(header[0] == 0xA2 for header, _ in sent))
            header, body = next(
                (header, body) for header, body in sent if header[0] == 0xA2
            )
            assert body.endswith(encode_g711(pcm, codec))
            assert sent[0][0][13:15] == b"\xff\xff"
            assert (
                handle._talk._preview is None
                and handle._talk._preview_worker is None
            )
            before = session.assembler.access_unit_count
            session.stop_talk()
            assert talk_closed.wait(1) and not preview_closed.is_set()
            wait_until(lambda: session.assembler.access_unit_count > before)
        assert preview_closed.wait(1) and device.closed


def test_parent_close_stops_talk_and_all_audio_workers(monkeypatch):
    with running_preview(monkeypatch) as (
        stream,
        preview,
        backends,
        devices,
        camera,
    ):
        handle = stream.start_talk()
        stream.close()
        assert preview.closed.is_set() and devices[0].closed
        assert backends[0].closed.is_set()
        assert not handle._thread.is_alive()
        assert not handle._talk._worker.is_alive()
        assert not stream._thread
        with pytest.raises(QuiiConnectionError):
            stream.start_talk()


def test_stop_talk_interrupts_audio_readiness_without_closing_preview(
    monkeypatch,
):
    with running_preview(monkeypatch, feed_audio=False) as (
        stream,
        preview,
        backends,
        devices,
        camera,
    ):
        errors = []

        def start():
            try:
                stream.start_talk()
            except (QuiiConnectionError, AudioDeviceError) as exc:
                errors.append(exc)

        worker = threading.Thread(target=start)
        worker.start()
        try:
            wait_until(lambda: bool(devices))
            with pytest.raises(RuntimeError, match="already"):
                stream.start_talk()
            stream.stop_talk()
        finally:
            worker.join(2)
        assert errors and not worker.is_alive()
        assert not preview.closed.is_set() and stream._thread.is_alive()
        assert backends[0].closed.is_set() and devices[0].closed


def test_audio_device_failure_is_isolated_from_video(monkeypatch):
    with running_preview(monkeypatch) as (
        stream,
        preview,
        backends,
        devices,
        camera,
    ):
        handle = stream.start_talk()
        devices[0].running = False
        with pytest.raises(AudioDeviceError, match="unexpectedly"):
            handle.wait(timeout=1)
        wait_until(lambda: stream.talk_error is not None)
        assert not preview.closed.is_set() and stream._thread.is_alive()


@pytest.mark.parametrize(
    "name", ["quii-session-conversation", "quii-conversation-receive"]
)
def test_talk_worker_start_failure_cleans_up_without_stopping_preview(
    monkeypatch, name
):
    with running_preview(monkeypatch) as (
        stream,
        preview,
        backends,
        devices,
        camera,
    ):
        original = threading.Thread.start

        def start(worker):
            if worker.name == name:
                raise RuntimeError("synthetic thread failure")
            original(worker)

        monkeypatch.setattr(threading.Thread, "start", start)
        with pytest.raises(RuntimeError, match="synthetic thread"):
            stream.start_talk()
        assert not stream.talk_active and stream._talk is None
        assert all(device.closed for device in devices)
        assert backends[0].closed.is_set() and not preview.closed.is_set()


def test_parent_close_interrupts_talk_handshake_and_prevents_audio_start(
    monkeypatch,
):
    with running_preview(monkeypatch) as (
        stream,
        preview,
        backends,
        devices,
        camera,
    ):
        entered = threading.Event()
        errors = []

        def blocked_open(backend):
            entered.set()
            assert backend.closed.wait(2)
            raise QuiiConnectionError("cancelled talk handshake")

        monkeypatch.setattr(FakeTalk, "open", blocked_open)

        def start():
            try:
                stream.start_talk()
            except (QuiiConnectionError, AudioDeviceError) as exc:
                errors.append(exc)

        worker = threading.Thread(target=start)
        worker.start()
        try:
            assert entered.wait(1)
            stream.close()
        finally:
            worker.join(2)
        assert errors and not worker.is_alive()
        assert devices[0].closed and devices[0].callback is None
        assert preview.closed.is_set() and backends[0].closed.is_set()


def test_ctrl_c_in_parent_wait_closes_active_conversation(monkeypatch):
    with running_preview(monkeypatch) as (
        stream,
        preview,
        backends,
        devices,
        camera,
    ):
        handle = stream.start_talk()
        with monkeypatch.context() as patch:
            patch.setattr(
                "quii_helper.camera.streaming.rtsp.time.sleep",
                Mock(side_effect=KeyboardInterrupt),
            )
            with pytest.raises(KeyboardInterrupt):
                stream.wait()
        stream.close()
        assert devices[0].closed and preview.closed.is_set()
        assert not handle._thread.is_alive()


def test_dead_preview_cannot_start_talk_or_touch_audio_devices(monkeypatch):
    with running_preview(monkeypatch) as (
        stream,
        preview,
        backends,
        devices,
        camera,
    ):
        preview.push(QuiiConnectionError("preview lost"))
        with pytest.raises(QuiiConnectionError):
            stream.wait(timeout=1)
        with pytest.raises(QuiiConnectionError, match="active preview"):
            stream.start_talk()
        assert devices == backends == []


@pytest.mark.parametrize("timeout", [-1, float("nan"), float("inf")])
def test_invalid_talk_wait_timeout_does_not_stop_preview(monkeypatch, timeout):
    with running_preview(monkeypatch) as (
        stream,
        preview,
        backends,
        devices,
        camera,
    ):
        handle = stream.start_talk()
        with pytest.raises(ValueError, match="nonnegative"):
            handle.wait(timeout)
        assert handle.active and not preview.closed.is_set()


def test_invalid_audio_metadata_does_not_break_video_only_preview(monkeypatch):
    with running_preview(monkeypatch) as (
        stream,
        preview,
        backends,
        devices,
        camera,
    ):
        preview.push(audio_cpacket(ms=1000))
        before = stream.assembler.access_unit_count
        wait_until(lambda: stream.assembler.access_unit_count > before)
        assert stream._error is None and backends == []
        handle = stream.start_talk()
        preview.push(audio_cpacket(ms=1000))
        with pytest.raises(QuiiConnectionError):
            handle.wait(timeout=1)
        assert not preview.closed.is_set() and stream._thread.is_alive()


def test_talk_start_is_rejected_inside_producer_callback(monkeypatch):
    with running_preview(monkeypatch) as (
        stream,
        preview,
        backends,
        devices,
        camera,
    ):
        called = threading.Event()
        original = stream.assembler.audio_frame_observer

        def observe(frame):
            with pytest.raises(RuntimeError, match="producer callback"):
                stream.start_talk()
            called.set()
            original(frame)

        stream.assembler.audio_frame_observer = observe
        assert called.wait(1)
        assert backends == devices == []


@pytest.mark.parametrize("mode", ["lan", "cloud"])
def test_inactive_or_cloud_session_rejected_without_audio_or_talk(
    mode, monkeypatch
):
    camera = Camera(config=config(connection_mode=mode))
    from quii_helper.camera.streaming import CameraRtspStream

    stream = CameraRtspStream(
        camera.connector,
        camera.preview_settings,
        camera.data_dir,
        lambda x: None,
        lambda x: None,
        connection_mode=mode,
    )
    factory = Mock()
    monkeypatch.setattr(camera.connector, "create_lan_talk_session", factory)
    with pytest.raises(
        ConfigurationError if mode == "cloud" else QuiiConnectionError
    ):
        stream.start_talk()
    factory.assert_not_called()
