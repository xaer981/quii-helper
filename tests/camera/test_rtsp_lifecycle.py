import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from unittest.mock import Mock

import pytest

import quii_helper
from quii_helper.camera.streaming import CameraRtspStream
from quii_helper.preview.pipeline.config import (
    DEFAULT_PREVIEW_CAPTURE_SETTINGS,
)
from quii_helper.protocols.rbudp.receive.payload_queue import RbUdpPayloadQueue
from quii_helper.support.errors import QuiiConnectionError


def _stream(tmp_path: Path) -> CameraRtspStream:
    stream = CameraRtspStream(
        connector=Mock(),
        preview_settings=DEFAULT_PREVIEW_CAPTURE_SETTINGS,
        data_dir=tmp_path,
        emit=lambda value: None,
        status=lambda value: None,
    )
    stream.server = Mock()
    return stream


@pytest.mark.parametrize("stage", ["credentials", "connect", "setup"])
def test_close_during_startup_cannot_resume_or_restart(
    tmp_path, monkeypatch, stage
):
    monkeypatch.setattr(
        "quii_helper.camera.streaming.rtsp.PRODUCER_JOIN_TIMEOUT_SECONDS", 0.01
    )
    stream = _stream(tmp_path)
    entered, release = threading.Event(), threading.Event()
    session = Mock()
    context = Mock()
    context.__enter__ = Mock(return_value=session)
    context.__exit__ = Mock(return_value=False)
    stream.connector.open_preview.return_value = context

    def block(*args, **kwargs):
        entered.set()
        assert release.wait(2)
        return {"credentials": object(), "connect": context, "setup": True}[
            stage
        ]

    target = {
        "credentials": stream.connector.fetch_credentials,
        "connect": stream.connector.open_preview,
        "setup": session.start_live_preview,
    }[stage]
    target.side_effect = block
    stream._consume_session_packets = Mock()
    stream.start()
    assert entered.wait(2)
    thread = stream._thread
    try:
        stream.close()
        assert thread is stream._thread and thread.is_alive()
        with pytest.raises(RuntimeError, match="still stopping"):
            stream.start()
    finally:
        release.set()
        thread.join(2)
        stream.close()
    assert not thread.is_alive()
    stream._consume_session_packets.assert_not_called()
    if stage == "credentials":
        stream.connector.open_preview.assert_not_called()
    if stage == "connect":
        session.start_live_preview.assert_not_called()
    if stage == "setup":
        session.tunnel.close.assert_called()


def test_failed_producer_stops_rtsp_and_wait_reports_error(tmp_path):
    stream = _stream(tmp_path)
    stream.connector.fetch_credentials.side_effect = ValueError("failed")
    stream.start()
    try:
        with pytest.raises(ValueError, match="failed"):
            stream.wait(timeout=2)
        stream.server.close.assert_called()
    finally:
        stream.close()


def test_close_can_be_called_from_producer_status_callback(tmp_path):
    stream = _stream(tmp_path)

    def status(message):
        if message == "Fetching runtime credentials":
            stream.close()

    stream.status = status
    stream.start()
    stream.wait(timeout=2)
    stream.close()
    assert stream._error is None
    stream.connector.open_preview.assert_not_called()


@pytest.mark.parametrize(
    "cause",
    [
        OSError("synthetic UDP failure"),
        QuiiConnectionError("camera disconnected KCP preview connection"),
    ],
)
def test_udp_receiver_failure_stops_rtsp_producer_and_cleans_session(
    tmp_path,
    monkeypatch,
    cause,
):
    stream = _stream(tmp_path)
    packets = RbUdpPayloadQueue()
    session = Mock()
    session.credentials.data_encode_key = b"0" * 16
    session.tunnel.recv_packet.side_effect = packets.recv_packet
    context = Mock()
    context.__enter__ = Mock(return_value=session)
    context.__exit__ = Mock(return_value=False)
    stream.connector.open_preview.return_value = context
    monkeypatch.setattr(
        "quii_helper.camera.streaming.rtsp.PreviewPacketProcessor", Mock()
    )
    ready = threading.Event()
    stream.status = lambda message: (
        ready.set() if message == "Receiving media packets" else None
    )
    stream.start()
    try:
        assert ready.wait(2)
        packets.fail(cause)
        with pytest.raises(QuiiConnectionError, match=str(cause)):
            stream.wait(timeout=2)
        assert stream._error.__cause__ is cause
        stream.server.close.assert_called()
        context.__exit__.assert_called_once()
        assert not stream._thread.is_alive()
    finally:
        stream.close()


@pytest.mark.parametrize("timeout", [None, 10])
@pytest.mark.parametrize("stage", ["credentials", "receiving"])
def test_sigint_interrupts_wait_and_closes_listener_without_losing_worker(
    tmp_path, timeout, stage
):
    code = """
import _thread
import json
import signal
import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch
from quii_helper.camera.streaming import rtsp
from quii_helper.preview.pipeline.config import DEFAULT_PREVIEW_CAPTURE_SETTINGS

signal.signal(signal.SIGINT, signal.default_int_handler)
rtsp.PRODUCER_JOIN_TIMEOUT_SECONDS = 0.01
entered, release = threading.Event(), threading.Event()
connector = Mock()
session, context = Mock(), Mock()
context.__enter__ = Mock(return_value=session)
context.__exit__ = Mock(return_value=False)
connector.open_preview.return_value = context
def block(*args):
    entered.set()
    release.wait()
    return object()
stream = rtsp.CameraRtspStream(
    connector=connector, preview_settings=DEFAULT_PREVIEW_CAPTURE_SETTINGS,
    data_dir=Path.cwd(), emit=lambda _: None, status=lambda _: None, port=0,
)
if sys.argv[2] == 'credentials':
    connector.fetch_credentials.side_effect = block
else:
    stream._consume_session_packets = block
with patch('socket.socket.connect', side_effect=AssertionError('network')), \\
     patch('socket.socket.sendto', side_effect=AssertionError('network')):
    stream.start()
    producer = stream._thread
    assert entered.wait(2)
    interrupt = threading.Timer(0.05, _thread.interrupt_main)
    fallback = threading.Timer(2, release.set)
    started = time.monotonic()
    try:
        interrupt.start()
        fallback.start()
        try:
            with stream:
                stream.wait(timeout=json.loads(sys.argv[1]))
        except KeyboardInterrupt:
            elapsed = time.monotonic() - started
        else:
            raise AssertionError('SIGINT did not propagate')
        print(json.dumps({'interrupt_and_close_seconds': elapsed}))
        assert elapsed < 1.0, f'SIGINT delayed {elapsed:.3f}s'
        assert stream.server._sock is None
        assert not stream.server._running
        assert producer.is_alive(), 'interrupt lost a still-running worker'
        assert stream._thread is producer
    finally:
        release.set()
        interrupt.cancel()
        fallback.cancel()
        interrupt.join(2)
        fallback.join(2)
        producer.join(2)
        stream.close()
    assert not producer.is_alive()
    assert stream._thread is None
    if sys.argv[2] == 'credentials':
        connector.open_preview.assert_not_called()
    else:
        connector.open_preview.assert_called_once()
        session.tunnel.close.assert_called()
"""
    root = str(Path(quii_helper.__file__).resolve().parents[1])
    code = f"import sys; sys.path.insert(0, {root!r})\n" + code
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", code, json.dumps(timeout), stage],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("timeout", [-1, 0, 0.025])
def test_wait_timeout_returns_without_closing_a_live_producer(
    tmp_path, timeout
):
    stream = _stream(tmp_path)
    release = threading.Event()
    worker = threading.Thread(target=release.wait)
    stream._thread = worker
    worker.start()
    started = time.monotonic()
    try:
        stream.wait(timeout=timeout)
        assert time.monotonic() - started >= max(0, timeout)
        assert worker.is_alive()
        assert not stream._stop_event.is_set()
        stream.server.close.assert_not_called()
    finally:
        release.set()
        worker.join(2)


def test_wait_without_timeout_returns_when_producer_finishes(tmp_path):
    stream = _stream(tmp_path)
    stream._thread = threading.Thread(target=lambda: time.sleep(0.025))
    stream._thread.start()
    try:
        stream.wait()
        assert not stream._thread.is_alive()
    finally:
        stream._thread.join(2)
