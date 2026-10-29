"""Desktop audio tests: synthetic PCM and fake devices, never host hardware."""

import threading
import time
from array import array
from unittest.mock import Mock

import pytest

from quii_helper import AudioDeviceError, Camera, ConfigurationError
from quii_helper.camera.streaming import conversation
from quii_helper.camera.streaming.talk import _SendBatch
from quii_helper.media.audio import CameraAudioFrame
from quii_helper.media.audio.g711 import decode_g711, encode_g711
from quii_helper.support.errors import QuiiConnectionError
from tests.camera.test_talk_session import (
    FakeTalk,
    make_talk,
    opened_talk,
    wait_until,
)
from tests.media.audio.test_frames import audio_cpacket
from tests.protocols.tcp.test_lan_session import config


class Device:
    """One manually clocked device; no automatic call to any real audio API."""

    def __init__(self):
        self.running = False
        self.closed = False
        self.callback = None
        self.on_start = lambda: None

    def start(self, callback):
        self.callback = callback
        self.running = True
        self.on_start()

    def close(self):
        self.running = False
        self.closed = True


@pytest.fixture
def device(monkeypatch):
    device = Device()
    monkeypatch.setattr(
        conversation, "open_duplex_device", lambda *args: device
    )
    return device


def test_buffers_keep_newest_sample_aligned_pcm_and_fill_silence():
    buffers = conversation._AudioBuffers()
    callback = buffers.callback()
    assert next(callback) == b""
    assert callback.send(bytearray(b"aabb")) == bytes(4)
    buffers.playback.extend(b"1122")
    assert callback.send(bytearray(6)) == b"1122\0\0"
    callback.send(bytearray(b"ab" * 3000))
    assert len(buffers.capture) == conversation.MAX_BUFFER_BYTES
    assert buffers.capture == b"ab" * 1600
    assert buffers.dropped_capture == 2810
    callback.close()


def test_callback_accepts_native_signed16_arrays():
    buffers = conversation._AudioBuffers()
    callback = buffers.callback()
    next(callback)
    assert callback.send(array("h", [1000] * 320)) == bytes(640)
    assert buffers.capture == b"\xe8\x03" * 320
    callback.close()


@pytest.mark.parametrize("value", [bytearray(1), bytearray(16002), None])
def test_bad_callback_never_raises_across_native_boundary(value):
    buffers = conversation._AudioBuffers()
    callback = buffers.callback()
    next(callback)
    assert callback.send(value) == b""
    assert isinstance(buffers.error, AudioDeviceError)
    assert buffers.stopped.is_set()
    callback.close()


def test_conversation_captures_and_plays_through_real_talk_workers(device):
    backend = FakeTalk()
    pcm = b"\xe8\x03" * 320
    incoming = bytes(range(256)) + bytes(64)
    talk = opened_talk(backend, full_duplex=True)
    done = threading.Event()
    errors, output = [], []

    def run():
        try:
            conversation.converse(lambda: talk, stop_event=done)
        except BaseException as exc:
            errors.append(exc)

    worker = threading.Thread(target=run)
    worker.start()
    try:
        wait_until(lambda: device.running)
        assert device.callback.send(bytearray(pcm)) == bytes(640)
        wait_until(lambda: len(backend.sent) == 1)
        assert backend.sent[0][1] == encode_g711(pcm, 4)
        backend.preview.push(audio_cpacket(incoming))
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            output.append(device.callback.send(bytearray(640)))
            if decode_g711(incoming, 4) in output:
                break
            time.sleep(0.01)
        assert decode_g711(incoming, 4) in output
        assert (
            backend.requests == []
        )  # No toggles around continuous mic blocks.
    finally:
        done.set()
        worker.join(3)
    assert not worker.is_alive() and not errors
    assert (
        device.closed
        and backend.closed.is_set()
        and backend.preview.closed.is_set()
    )
    assert not any(
        t.name.startswith("quii-conversation-") for t in threading.enumerate()
    )


def test_short_capture_blocks_are_combined_before_sending():
    buffers = conversation._AudioBuffers()
    talk = Mock()
    worker = threading.Thread(target=buffers.send, args=(talk,))
    worker.start()
    callback = buffers.callback()
    next(callback)
    try:
        for _ in range(4):
            callback.send(bytearray(b"ab" * 80))
        wait_until(lambda: talk._send_captured_pcm.called)
        talk._send_captured_pcm.assert_called_once_with(b"ab" * 320)
    finally:
        buffers.stopped.set()
        with buffers.condition:
            buffers.condition.notify_all()
        worker.join(1)
        callback.close()
    assert not worker.is_alive()


@pytest.mark.parametrize("live", [False, True])
def test_only_hardware_capture_skips_final_playback_wait(live):
    backend = FakeTalk()
    talk = make_talk(backend, full_duplex=True)
    batch = _SendBatch(bytes(640), live=live)
    talk._batch = batch
    talk._advance_send()
    assert len(backend.sent) == 1
    assert (talk._batch is None) == live
    if not live:
        assert talk._batch.next_send > time.monotonic()


@pytest.mark.parametrize(
    "full_duplex,pcm", [(False, bytes(640)), (True, bytes(1280)), (True, b"x")]
)
def test_live_capture_rejects_unclocked_batches(full_duplex, pcm):
    talk = make_talk(FakeTalk(), full_duplex=full_duplex)
    with pytest.raises(ValueError):
        talk._send_captured_pcm(pcm)


def test_long_received_audio_is_bounded_and_oldest_dropped():
    buffers = conversation._AudioBuffers()
    frame = CameraAudioFrame(bytes(range(256)) * 32, 4, 8000, 1, 0, 0)
    talk = Mock()

    def receive(**kwargs):
        buffers.stopped.set()
        return frame

    talk.recv_frame.side_effect = receive
    buffers.receive(talk)
    assert buffers.playback == decode_g711(frame.data, 4)[-3200:]
    assert buffers.dropped_playback == len(frame.data) * 2 - 3200


def test_captured_backlog_sends_newest_block_without_bursting_old_audio():
    buffers = conversation._AudioBuffers()
    buffers.capture.extend(b"old!" * 320 + b"ab" * 320 + b"tail")
    talk = Mock()
    talk._send_captured_pcm.side_effect = lambda pcm: buffers.stopped.set()
    buffers.send(talk)
    talk._send_captured_pcm.assert_called_once_with(b"ab" * 320)
    assert buffers.capture == b"tail"
    assert buffers.dropped_capture == 1280


@pytest.mark.parametrize(
    "failure", [QuiiConnectionError("lost"), KeyboardInterrupt()]
)
def test_startup_failure_always_closes_local_device(device, failure):
    open_talk = Mock(side_effect=failure)
    with pytest.raises(type(failure)):
        conversation.converse(open_talk)
    assert device.closed and not device.running


def test_device_start_failure_closes_talk_and_workers(device):
    device.on_start = Mock(side_effect=RuntimeError("access denied"))
    talk = opened_talk(FakeTalk(), full_duplex=True)
    with pytest.raises(AudioDeviceError, match="Could not start"):
        conversation.converse(lambda: talk)
    assert device.closed and talk._stopped.is_set()


def test_keyboard_interrupt_during_device_start_closes_both(device):
    device.on_start = Mock(side_effect=KeyboardInterrupt)
    talk = opened_talk(FakeTalk(), full_duplex=True)
    with pytest.raises(KeyboardInterrupt):
        conversation.converse(lambda: talk)
    assert device.closed and talk._stopped.is_set()


def test_ctrl_c_during_active_conversation_releases_all_workers(
    device, monkeypatch
):
    buffers = conversation._AudioBuffers()
    monkeypatch.setattr(conversation, "_AudioBuffers", lambda: buffers)
    monkeypatch.setattr(
        buffers.stopped, "wait", Mock(side_effect=KeyboardInterrupt)
    )
    talk = opened_talk(FakeTalk(), full_duplex=True)
    with pytest.raises(KeyboardInterrupt):
        conversation.converse(lambda: talk)
    assert device.closed and talk._stopped.is_set()
    assert buffers.capture == buffers.playback == b""
    assert not any(
        t.name.startswith("quii-conversation-") for t in threading.enumerate()
    )


def test_second_worker_start_failure_closes_first_and_talk(
    device, monkeypatch
):
    talk = opened_talk(FakeTalk(), full_duplex=True)
    start = threading.Thread.start

    def start_or_fail(worker):
        if worker.name == "quii-conversation-receive":
            raise RuntimeError("cannot start thread")
        start(worker)

    monkeypatch.setattr(threading.Thread, "start", start_or_fail)
    with pytest.raises(RuntimeError, match="cannot start"):
        conversation.converse(lambda: talk)
    assert device.closed and talk._stopped.is_set()
    assert not any(
        t.name.startswith("quii-conversation-") for t in threading.enumerate()
    )


def test_bad_callback_propagates_to_monitor_and_closes_talk(device):
    device.on_start = lambda: device.callback.send(bytearray(1))
    talk = opened_talk(FakeTalk(), full_duplex=True)
    with pytest.raises(AudioDeviceError, match="Invalid PCM"):
        conversation.converse(lambda: talk)
    assert device.closed and talk._stopped.is_set()


@pytest.mark.parametrize("primary", [None, QuiiConnectionError("original")])
def test_cleanup_failure_does_not_mask_original_and_still_closes_talk(
    device, primary
):
    talk = opened_talk(FakeTalk(), full_duplex=True)

    def close():
        raise RuntimeError("device teardown")

    device.close = close
    if primary:
        open_talk = Mock(side_effect=primary)
        expected = QuiiConnectionError
    else:
        open_talk = lambda: talk
        expected = AudioDeviceError
    try:
        with pytest.raises(expected):
            conversation.converse(open_talk, duration_seconds=0.001)
        if not primary:
            assert talk._stopped.is_set()
    finally:
        talk.close()


def test_missing_audio_extra_opens_no_camera(monkeypatch):
    device = Mock(side_effect=ConfigurationError("missing audio extra"))
    monkeypatch.setattr(conversation, "open_duplex_device", device)
    open_talk = Mock()
    with pytest.raises(ConfigurationError):
        conversation.converse(open_talk)
    open_talk.assert_not_called()


def test_unexpected_device_stop_is_not_success(device):
    device.on_start = lambda: setattr(device, "running", False)
    talk = opened_talk(FakeTalk(), full_duplex=True)
    with pytest.raises(AudioDeviceError, match="unexpectedly"):
        conversation.converse(lambda: talk)
    assert device.closed and talk._stopped.is_set()


def test_network_failure_preserves_error_and_closes_microphone(device):
    backend = FakeTalk()
    failure = QuiiConnectionError("preview disconnected")
    device.on_start = lambda: backend.preview.push(failure)
    talk = opened_talk(backend, full_duplex=True)
    with pytest.raises(QuiiConnectionError, match="disconnected"):
        conversation.converse(lambda: talk, duration_seconds=1)
    assert device.closed and backend.closed.is_set()


def test_duration_limits_active_audio_and_cleans_up(device):
    talk = opened_talk(FakeTalk(), full_duplex=True)
    start = time.monotonic()
    conversation.converse(lambda: talk, duration_seconds=0.06)
    assert 0.06 <= time.monotonic() - start < 1
    assert device.closed and talk._stopped.is_set()


@pytest.mark.parametrize(
    "value", [0, -1, True, float("nan"), float("inf"), "3"]
)
def test_invalid_duration_fails_before_local_audio(monkeypatch, value):
    device = Mock()
    monkeypatch.setattr(conversation, "open_duplex_device", device)
    with pytest.raises(ConfigurationError):
        conversation.converse(Mock(), duration_seconds=value)
    device.assert_not_called()


def test_precancelled_call_opens_nothing(monkeypatch):
    device, open_talk = Mock(), Mock()
    monkeypatch.setattr(conversation, "open_duplex_device", device)
    done = threading.Event()
    done.set()
    conversation.converse(open_talk, stop_event=done)
    open_talk.assert_not_called()
    device.assert_not_called()


def test_camera_passes_options_and_selects_continuous_talk(monkeypatch):
    camera = Camera(config=config())
    talk = Mock()
    monkeypatch.setattr(camera, "talk", talk)
    run = Mock()
    monkeypatch.setattr("quii_helper.camera.api.converse", run)
    done = threading.Event()
    camera.converse(
        channel=2, input_device="Mic", output_device="Headset", stop_event=done
    )
    callback = run.call_args.args[0]
    assert callback() is talk.return_value
    talk.assert_called_once_with(channel=2, full_duplex=True)
    assert run.call_args.kwargs == {
        "input_device": "Mic",
        "output_device": "Headset",
        "duration_seconds": None,
        "stop_event": done,
    }
    assert camera.config.channel == 1


@pytest.mark.parametrize(
    "options",
    [{"connection_mode": "cloud"}, {"channel": 0}, {"stream_key": ""}],
)
def test_invalid_lan_config_fails_before_audio(monkeypatch, options):
    run = Mock()
    monkeypatch.setattr("quii_helper.camera.api.converse", run)
    with pytest.raises(ConfigurationError):
        Camera(config=config(**options)).converse()
    run.assert_not_called()


def test_actual_miniaudio_null_backend_callback_without_hardware(monkeypatch):
    audio = pytest.importorskip("miniaudio")
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
    talk = opened_talk(FakeTalk(), full_duplex=True)
    buffers = conversation._AudioBuffers()
    monkeypatch.setattr(conversation, "_AudioBuffers", lambda: buffers)
    conversation.converse(lambda: talk, duration_seconds=2)
    # The old double-pacing path lost ~20% of samples even without network load.
    assert talk.frames_sent >= 44
    assert buffers.dropped_capture <= 2 * 640
    assert not device.running and talk._stopped.is_set()
