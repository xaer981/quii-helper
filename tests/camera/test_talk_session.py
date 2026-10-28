"""Two-connection talk tested with fake sessions and loopback TCP only."""

import hashlib
import socket
import struct
import threading
import time
from collections import deque
from contextlib import contextmanager
from unittest.mock import Mock

import pytest

from quii_helper import (
    Camera,
    CameraTalkSession,
    ConfigurationError,
    QuiiConnectionError,
)
from quii_helper.media.audio.g711 import encode_g711
from quii_helper.protocols.tcp.live.session import MAX_TCP_PAYLOAD_BYTES
from tests.camera.test_lan_media import _read_exact
from tests.media.audio.test_frames import audio_cpacket
from tests.media.frames.test_parsing import _cpacket
from tests.protocols.tcp.test_lan_session import (
    command,
    config,
    media,
    setup_reply,
)
from tests.protocols.tcp.test_talk_packets import decrypt
from tests.protocols.tcp.test_talk_session import reply


class FakePreview:
    def __init__(self, initial=None):
        self.config = config(connect_timeout=0.1)
        self.received = deque(
            [audio_cpacket(b"preview-ready")] if initial is None else initial
        )
        self.closed = threading.Event()
        self.condition = threading.Condition()
        self.opened = False

    def open(self):
        self.opened = True
        return self

    def push(self, item):
        with self.condition:
            self.received.append(item)
            self.condition.notify_all()

    def recv_message(self, *, timeout):
        with self.condition:
            if not self.received and not self.closed.is_set():
                self.condition.wait(timeout)
            if self.closed.is_set():
                raise QuiiConnectionError("preview closed")
            if not self.received:
                raise TimeoutError
            item = self.received.popleft()
        if isinstance(item, Exception):
            raise item
        return {"is_media": True, "payload": item}

    def close(self):
        self.closed.set()
        with self.condition:
            self.condition.notify_all()


class FakeTalk(FakePreview):
    def __init__(self):
        super().__init__(initial=[])
        self.preview = FakePreview()
        self.codec = 4
        self.receiving = True
        self.receive_pending = False
        self.requests, self.sent = [], []
        self.failure = None

    def request_receive(self, enabled):
        self.requests.append(enabled)
        self.receive_pending = True
        self.push(enabled)

    def recv_message(self, *, timeout):
        result = super().recv_message(timeout=timeout)
        item = result["payload"]
        if isinstance(item, bool):
            self.receiving, self.receive_pending = item, False
            return {"is_media": False}
        return result

    def send_audio(self, encoded):
        if self.failure:
            raise self.failure
        self.sent.append((time.monotonic(), encoded))


def make_talk(backend, **kwargs):
    return CameraTalkSession(backend, preview=backend.preview, **kwargs)


def opened_talk(backend, **kwargs):
    talk = make_talk(backend, **kwargs).open()
    assert talk.recv_frame().data == b"preview-ready"
    return talk


def assert_closed(talk, backend):
    assert backend.closed.is_set() and backend.preview.closed.is_set()
    for worker in (talk._worker, talk._preview_worker):
        assert worker is None or worker.ident is None or not worker.is_alive()


def wait_until(predicate):
    deadline = time.monotonic() + 2
    while not predicate():
        assert (
            time.monotonic() < deadline
        ), "worker did not reach expected state"
        time.sleep(0.002)


@pytest.fixture(autouse=True)
def no_cloud_or_door(monkeypatch):
    fail = Mock(side_effect=AssertionError("cloud/door call forbidden"))
    monkeypatch.setattr(
        "quii_helper.camera.connection.session.fetch_runtime_credentials", fail
    )
    monkeypatch.setattr("quii_helper.camera.api.request_open_door", fail)
    yield
    fail.assert_not_called()


@pytest.mark.parametrize("channel", [None, 2])
def test_public_factory_selects_preview_panel_but_not_talk_channel(
    channel, monkeypatch
):
    camera = Camera(config=config())
    backend = FakeTalk()
    preview_factory = Mock(return_value=backend.preview)
    talk_factory = Mock(return_value=backend)
    monkeypatch.setattr(
        camera.connector, "create_lan_session", preview_factory
    )
    monkeypatch.setattr(
        camera.connector, "create_lan_talk_session", talk_factory
    )
    with pytest.raises(KeyboardInterrupt):
        with camera.talk(channel=channel) as talk:
            assert talk.codec == 4 and backend.opened
            assert talk.recv_frame().data == b"preview-ready"
            raise KeyboardInterrupt
    preview_factory.assert_called_once_with(channel=channel)
    talk_factory.assert_called_once_with()
    assert camera.config.channel == 1
    assert_closed(talk, backend)


@pytest.mark.parametrize("channel", [None, 1, 2, 4])
def test_connector_keeps_panel_and_generic_selector_separate(channel):
    camera = Camera(config=config(channel=3, stream=2))
    preview = camera.connector.create_lan_session(channel=channel)
    talk = camera.connector.create_lan_talk_session()
    assert preview.config.channel == (3 if channel is None else channel)
    assert preview.config.stream == 2
    assert talk.channel == 65535
    assert camera.config.channel == 3


@pytest.mark.parametrize("channel", [0, -1, True, 65536])
def test_invalid_preview_panel_fails_before_talk_factory(channel, monkeypatch):
    camera = Camera(config=config())
    factory = Mock(side_effect=AssertionError("must not construct talk"))
    monkeypatch.setattr(camera.connector, "create_lan_talk_session", factory)
    with pytest.raises(ConfigurationError):
        camera.talk(channel=channel)
    factory.assert_not_called()


def test_cloud_and_invalid_duplex_fail_before_connector(monkeypatch):
    for kwargs in ({"connection_mode": "cloud"}, {}):
        camera = Camera(**kwargs)
        factory = Mock(side_effect=AssertionError("no session"))
        monkeypatch.setattr(camera.connector, "create_lan_session", factory)
        monkeypatch.setattr(
            camera.connector, "create_lan_talk_session", factory
        )
        with pytest.raises((ConfigurationError, ValueError)):
            camera.talk(full_duplex="yes")
        factory.assert_not_called()


def test_missing_key_does_not_start_transport():
    with pytest.raises(ConfigurationError):
        Camera(config=config(stream_key="")).talk()


def test_talk_is_not_opened_until_delayed_preview_audio_arrives():
    backend = FakeTalk()
    backend.preview = FakePreview(initial=[])
    backend.preview.config.connect_timeout = 1
    backend.open = Mock(wraps=backend.open)
    talk = make_talk(backend)
    errors = []

    def start():
        try:
            talk.open()
        except Exception as exc:
            errors.append(exc)

    starter = threading.Thread(target=start)
    starter.start()
    try:
        wait_until(lambda: backend.preview.opened)
        backend.open.assert_not_called()
        backend.preview.push(audio_cpacket(b"delayed"))
        starter.join(2)
        assert not starter.is_alive() and not errors
        assert talk.recv_frame().data == b"delayed"
        backend.open.assert_called_once_with()
    finally:
        talk.close()
        starter.join(2)
    assert_closed(talk, backend)


def test_preview_audio_is_ready_before_talk_open_and_first_frame_is_retained():
    backend = FakeTalk()
    backend.open = Mock(wraps=backend.open)
    backend.preview = FakePreview(
        [_cpacket(b"video"), audio_cpacket(b"first")]
    )
    with make_talk(backend) as talk:
        backend.open.assert_called_once_with()
        assert backend.preview.opened
        assert talk.recv_frame().data == b"first"
        assert talk.open() is talk
        backend.open.assert_called_once_with()
    assert_closed(talk, backend)


@pytest.mark.parametrize("full_duplex", [False, True])
@pytest.mark.parametrize("codec", [4, 5])
def test_pcm_is_encoded_paced_and_preview_stays_active(full_duplex, codec):
    backend = FakeTalk()
    backend.codec = codec
    with opened_talk(backend, full_duplex=full_duplex) as talk:
        started = time.monotonic()
        talk.send_pcm(bytes(640 * 3))
        assert talk.frames_sent == 3
        assert [data for _, data in backend.sent] == [
            encode_g711(bytes(640), codec)
        ] * 3
        assert all(
            b[0] - a[0] >= 0.035
            for a, b in zip(backend.sent, backend.sent[1:])
        )
        assert time.monotonic() - started >= 0.115
        assert backend.requests == ([] if full_duplex else [False, True])
        assert backend.receiving and not backend.receive_pending
        assert not backend.preview.closed.is_set()
    assert_closed(talk, backend)


def test_preview_audio_can_be_consumed_while_pcm_send_is_blocked():
    backend = FakeTalk()
    backend.config.connect_timeout = 1
    entered, resume = threading.Event(), threading.Event()

    def blocked_send(encoded):
        entered.set()
        assert resume.wait(2)

    backend.send_audio = blocked_send
    talk = opened_talk(backend)
    errors = []

    def produce():
        try:
            talk.send_pcm(bytes(640))
        except Exception as exc:
            errors.append(exc)

    producer = threading.Thread(target=produce)
    producer.start()
    try:
        assert entered.wait(2)
        backend.preview.push(audio_cpacket(b"during-send"))
        assert talk.recv_frame(timeout=0.5).data == b"during-send"
        assert producer.is_alive()
        resume.set()
        producer.join(2)
        assert not errors and not producer.is_alive()
    finally:
        resume.set()
        talk.close()
        producer.join(2)
    assert_closed(talk, backend)


@pytest.mark.parametrize(
    "pcm",
    [b"", b"x", bytes(639), bytes(641), bytes(16640), bytearray(640)],
    ids=["empty", "odd", "short", "long", "oversize", "mutable"],
)
def test_invalid_pcm_never_enqueued(pcm):
    backend = FakeTalk()
    with opened_talk(backend) as talk:
        with pytest.raises(ValueError, match="640-16000"):
            talk.send_pcm(pcm)
        assert not backend.sent and not backend.requests


def test_only_one_producer_and_close_cancels_waiting_sender():
    backend = FakeTalk()
    backend.request_receive = lambda enabled: setattr(
        backend, "receive_pending", True
    )
    talk = opened_talk(backend)
    errors = []

    def send():
        try:
            talk.send_pcm(bytes(640))
        except QuiiConnectionError as exc:
            errors.append(exc)

    sender = threading.Thread(target=send)
    sender.start()
    try:
        wait_until(lambda: backend.receive_pending)
        with pytest.raises(RuntimeError, match="one PCM producer"):
            talk.send_pcm(bytes(640))
    finally:
        talk.close()
        sender.join(2)
    assert errors and not sender.is_alive() and not backend.sent
    assert_closed(talk, backend)


def test_fragmented_preview_audio_ignores_large_video_and_talk_media():
    backend = FakeTalk()
    first, second = audio_cpacket(b"one"), audio_cpacket(b"two", codec=5)
    video = _cpacket(bytes(100_000))
    with opened_talk(backend) as talk:
        backend.push(audio_cpacket(b"wrong-talk-source"))
        for part in [
            video[:50_000],
            video[50_000:] + first[:7],
            first[7:21],
            first[21:] + second,
        ]:
            backend.preview.push(part)
        assert talk.recv_frame().data == b"one"
        assert talk.recv_frame().data == b"two"
        assert talk._packer.stats["trailing_partial_bytes"] == 0
        with pytest.raises(TimeoutError):
            talk.recv_frame(timeout=0.02)


def test_preview_is_drained_without_a_reader_and_queue_is_bounded():
    backend = FakeTalk()
    with opened_talk(backend) as talk:
        backend.preview.push(
            b"".join(audio_cpacket(bytes([i])) for i in range(100))
        )
        wait_until(lambda: talk.dropped_frames == 36)
        assert len(talk._received) == 64
        assert talk.recv_frame().data == bytes([36])
        assert [talk.recv_frame().data for _ in range(63)][-1] == bytes([99])


@pytest.mark.parametrize(
    "kwargs",
    [{"codec": 9}, {"sample_rate": 16000}, {"channels": 2}, {"ms": 1000}],
)
def test_unsupported_preview_format_closes_both_connections(kwargs):
    backend = FakeTalk()
    with opened_talk(backend) as talk:
        backend.preview.push(audio_cpacket(**kwargs))
        with pytest.raises(QuiiConnectionError):
            talk.recv_frame()
    assert_closed(talk, backend)


def test_oversize_complete_audio_is_not_retained_in_the_64_frame_queue():
    backend = FakeTalk()
    with opened_talk(backend) as talk:
        backend.preview.push(audio_cpacket(bytes(65536)))
        with pytest.raises(QuiiConnectionError, match="unsupported"):
            talk.recv_frame()
        assert not talk._received
    assert_closed(talk, backend)


def test_invalid_first_audio_metadata_fails_before_talk_activation():
    backend = FakeTalk()
    backend.preview = FakePreview([audio_cpacket(ms=1000)])
    backend.open = Mock(side_effect=AssertionError("must not activate talk"))
    talk = make_talk(backend)
    with pytest.raises(QuiiConnectionError, match="metadata"):
        talk.open()
    backend.open.assert_not_called()
    assert_closed(talk, backend)


def test_oversize_partial_preview_cannot_accumulate_unbounded_memory():
    backend = FakeTalk()
    header = bytearray(audio_cpacket()[:20])
    struct.pack_into("<I", header, 4, 2 * MAX_TCP_PAYLOAD_BYTES)
    with opened_talk(backend) as talk:
        backend.preview.push(bytes(header) + bytes(MAX_TCP_PAYLOAD_BYTES))
        with pytest.raises(QuiiConnectionError, match="framing"):
            talk.recv_frame()
    assert_closed(talk, backend)


@pytest.mark.parametrize("source", ["preview", "talk"])
def test_failure_in_either_connection_wakes_sender_and_closes_both(source):
    backend = FakeTalk()
    backend.request_receive = lambda enabled: setattr(
        backend, "receive_pending", True
    )
    talk = opened_talk(backend)
    errors = []

    def send():
        try:
            talk.send_pcm(bytes(640))
        except QuiiConnectionError as exc:
            errors.append(exc)

    worker = threading.Thread(target=send)
    worker.start()
    try:
        wait_until(lambda: backend.receive_pending)
        target = backend.preview if source == "preview" else backend
        target.push(QuiiConnectionError("connection lost"))
        worker.join(2)
        assert not worker.is_alive() and errors
        with pytest.raises(QuiiConnectionError, match="connection lost"):
            talk.recv_frame()
    finally:
        talk.close()
        worker.join(2)
    assert not backend.sent
    assert_closed(talk, backend)


def test_worker_send_failure_wakes_producer_and_does_not_retry():
    backend = FakeTalk()
    backend.failure = OSError("synthetic send failure")
    with opened_talk(backend) as talk:
        with pytest.raises(
            QuiiConnectionError, match="worker failed"
        ) as error:
            talk.send_pcm(bytes(640))
        assert isinstance(error.value.__cause__, OSError)
        assert not backend.sent
    assert_closed(talk, backend)


def test_receive_timeout_preserves_both_sessions_and_close_prevents_reopen():
    backend = FakeTalk()
    with opened_talk(backend) as talk:
        with pytest.raises(TimeoutError):
            talk.recv_frame(timeout=0.01)
        assert (
            not backend.closed.is_set() and not backend.preview.closed.is_set()
        )
    talk.close()
    for operation in (
        talk.open,
        talk.recv_frame,
        lambda: talk.send_pcm(bytes(640)),
    ):
        with pytest.raises(QuiiConnectionError, match="closed"):
            operation()
    assert_closed(talk, backend)


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_invalid_receive_timeout_preserves_session(timeout):
    backend = FakeTalk()
    with opened_talk(backend) as talk:
        with pytest.raises(ValueError, match="finite and positive"):
            talk.recv_frame(timeout=timeout)


@pytest.mark.parametrize("source", ["preview", "talk"])
def test_startup_failure_closes_both_even_if_only_preview_opened(source):
    backend = FakeTalk()
    target = backend.preview if source == "preview" else backend
    target.open = Mock(side_effect=QuiiConnectionError("setup failed"))
    talk = make_talk(backend)
    with pytest.raises(QuiiConnectionError, match="setup failed"):
        talk.open()
    assert_closed(talk, backend)


def test_missing_preview_audio_times_out_before_talk_is_opened():
    backend = FakeTalk()
    backend.preview = FakePreview(initial=[_cpacket(b"video")])
    backend.open = Mock(side_effect=AssertionError("must not open talk"))
    talk = make_talk(backend)
    with pytest.raises(QuiiConnectionError, match="preview.*startup deadline"):
        talk.open()
    backend.open.assert_not_called()
    assert_closed(talk, backend)


def test_continuous_video_does_not_extend_preview_audio_startup_deadline():
    backend = FakeTalk()

    def video_only(**kwargs):
        return {"is_media": True, "payload": _cpacket(b"video")}

    backend.preview.recv_message = video_only
    talk = make_talk(backend)
    started = time.monotonic()
    with pytest.raises(QuiiConnectionError, match="startup deadline"):
        talk.open()
    assert time.monotonic() - started < 1
    assert not backend.opened
    assert_closed(talk, backend)


def test_close_while_waiting_for_first_preview_audio_wakes_startup():
    backend = FakeTalk()
    backend.preview = FakePreview(initial=[])
    backend.preview.config.connect_timeout = 5
    talk = make_talk(backend)
    errors = []

    def start():
        try:
            talk.open()
        except QuiiConnectionError as exc:
            errors.append(exc)

    starter = threading.Thread(target=start)
    starter.start()
    try:
        wait_until(lambda: backend.preview.opened)
        talk.close()
        starter.join(2)
        assert not starter.is_alive() and errors
        assert not backend.opened
    finally:
        talk.close()
        starter.join(2)
    assert_closed(talk, backend)


def test_preview_failure_during_talk_startup_preserves_original_error():
    backend = FakeTalk()
    entered, resume = threading.Event(), threading.Event()

    def blocked_open():
        entered.set()
        assert resume.wait(2)

    backend.open = blocked_open
    talk = make_talk(backend)
    errors = []

    def start():
        try:
            talk.open()
        except QuiiConnectionError as exc:
            errors.append(exc)

    starter = threading.Thread(target=start)
    starter.start()
    try:
        assert entered.wait(2)
        backend.preview.push(
            QuiiConnectionError("preview failed during startup")
        )
        assert backend.closed.wait(2)
        resume.set()
        starter.join(2)
        assert not starter.is_alive() and errors
        assert str(errors[0]) == "preview failed during startup"
    finally:
        resume.set()
        talk.close()
        starter.join(2)
    assert_closed(talk, backend)


@pytest.mark.parametrize("stage", ["preview", "talk"])
def test_close_during_startup_cannot_leave_connections_or_workers(stage):
    entered, resume = threading.Event(), threading.Event()
    backend = FakeTalk()
    target = backend.preview if stage == "preview" else backend

    def blocked_open():
        entered.set()
        assert resume.wait(2)

    target.open = blocked_open
    talk = make_talk(backend)
    errors = []

    def open_talk():
        try:
            talk.open()
        except QuiiConnectionError as exc:
            errors.append(exc)

    starter = threading.Thread(target=open_talk)
    starter.start()
    try:
        assert entered.wait(2)
        talk.close()
    finally:
        resume.set()
        starter.join(2)
    assert errors and not starter.is_alive()
    assert_closed(talk, backend)


@pytest.mark.parametrize("name", ["quii-lan-talk", "quii-lan-talk-preview"])
def test_thread_start_failure_closes_both_and_joins_started_reader(
    name, monkeypatch
):
    backend = FakeTalk()
    original = threading.Thread.start

    def start(worker):
        if worker.name == name:
            raise RuntimeError("no threads")
        original(worker)

    monkeypatch.setattr(threading.Thread, "start", start)
    talk = make_talk(backend)
    with pytest.raises(RuntimeError, match="no threads"):
        talk.open()
    assert_closed(talk, backend)


def test_close_interrupts_network_send_and_waiting_pcm_producer():
    backend = FakeTalk()
    entered = threading.Event()

    def blocked_send(encoded):
        entered.set()
        assert backend.closed.wait(2)
        raise OSError("cancelled socket")

    backend.send_audio = blocked_send
    talk = opened_talk(backend)
    errors = []

    def produce():
        try:
            talk.send_pcm(bytes(640))
        except QuiiConnectionError as exc:
            errors.append(exc)

    producer = threading.Thread(target=produce)
    producer.start()
    try:
        assert entered.wait(2)
    finally:
        talk.close()
        producer.join(2)
    assert errors and not producer.is_alive() and talk.frames_sent == 0
    assert_closed(talk, backend)


@contextmanager
def local_duplex_camera(
    *, codec, full_packet, panel, stream, periodic_preview=False
):
    """One fake device port accepting separate preview and generic-talk sockets."""
    stop, preview_closed, talk_closed = (
        threading.Event(),
        threading.Event(),
        threading.Event(),
    )
    errors, sent, events, workers = [], [], [], []
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        listener.settimeout(2)

        def handle(sock):
            closed = None
            try:
                with sock:
                    sock.settimeout(0.3)
                    setup = _read_exact(sock, 32)
                    is_talk = setup[9] == 2
                    assert setup == b"\xa9" + bytes(8) + bytes(
                        [2 if is_talk else 0]
                    ) + bytes(22)
                    closed = talk_closed if is_talk else preview_closed
                    sock.sendall(setup_reply())
                    while not stop.is_set():
                        try:
                            header = decrypt(_read_exact(sock, 32))
                        except TimeoutError:
                            continue
                        kind = header[0]
                        size = int.from_bytes(
                            header[11:15] if kind == 0xA2 else header[9:11],
                            "little",
                        )
                        wire_body = _read_exact(sock, size)
                        if kind == 0xA2:
                            assert is_talk
                            body = decrypt(wire_body[:32]) + wire_body[32:]
                        else:
                            body = decrypt(wire_body)
                            raw_size = (
                                int.from_bytes(header[11:13], "little")
                                if kind in (1, 0x0B)
                                else 0
                            )
                            assert (
                                body[raw_size : raw_size + 32]
                                == hashlib.sha256(
                                    header + body[:raw_size]
                                ).digest()
                            )
                        if not is_talk:
                            assert kind in (0, 1)
                            if kind == 1:
                                assert (
                                    int.from_bytes(header[13:15], "little")
                                    == panel
                                )
                                assert header[16] == stream - 1
                                events.append("preview_play")
                                first = audio_cpacket(
                                    b"first-preview", codec=codec
                                )
                                second = audio_cpacket(
                                    b"second-preview", codec=codec
                                )
                                sock.sendall(
                                    command()
                                    + media(first[:11])
                                    + media(first[11:])
                                    + media(second)
                                )
                            else:
                                extra = b""
                                if periodic_preview:
                                    extra = media(
                                        audio_cpacket(
                                            b"\xd5" * 320, codec=codec
                                        )
                                    ) + media(
                                        _cpacket(
                                            b"\x00\x00\x01\x67sps\x00\x00\x01\x68pps\x00\x00\x01\x65idr",
                                            frame_stamp=0x6AA12345,
                                        )
                                    )
                                sock.sendall(command(0) + extra)
                            continue
                        sent.append((header, body))
                        if kind == 0x0B:
                            assert events == ["preview_play"]
                            events.append("talk_open")
                            sock.sendall(
                                reply(
                                    kind,
                                    mask=1 << (codec - 4),
                                    full_packet=full_packet,
                                )
                            )
                        elif kind in (0x0C, 0x0D):
                            sock.sendall(reply(kind))
                            if kind == 0x0D and header[13]:
                                sock.sendall(
                                    media(
                                        audio_cpacket(
                                            b"not-preview", codec=codec
                                        )
                                    )
                                )
                        elif kind == 0:
                            sock.sendall(reply(0))
            except (
                EOFError,
                ConnectionResetError,
                ConnectionAbortedError,
                BrokenPipeError,
            ):
                pass
            except Exception as exc:
                errors.append(exc)
            finally:
                if closed is not None:
                    closed.set()

        def accept():
            try:
                for _ in range(2):
                    worker = threading.Thread(
                        target=handle,
                        args=(listener.accept()[0],),
                        daemon=True,
                    )
                    workers.append(worker)
                    worker.start()
            except Exception as exc:
                errors.append(exc)

        acceptor = threading.Thread(target=accept, daemon=True)
        acceptor.start()
        try:
            yield listener.getsockname()[1], sent, preview_closed, talk_closed
        finally:
            stop.set()
            acceptor.join(3)
            for worker in workers:
                worker.join(2)
                assert not worker.is_alive()
            assert not acceptor.is_alive() and not errors


@pytest.mark.parametrize("codec", [4, 5])
@pytest.mark.parametrize("full_packet", [0, 1])
@pytest.mark.parametrize("panel,stream", [(1, 1), (2, 2)])
def test_public_duplex_talk_over_two_loopback_connections(
    codec, full_packet, panel, stream
):
    with local_duplex_camera(
        codec=codec, full_packet=full_packet, panel=panel, stream=stream
    ) as (port, sent, preview_closed, talk_closed):
        camera = Camera(
            config=config(stream_port=port, connect_timeout=2, stream=stream)
        )
        with camera.talk(channel=panel) as talk:
            assert talk.codec == codec
            assert talk.recv_frame().data == b"first-preview"
            assert talk.recv_frame().data == b"second-preview"
            talk.send_pcm(bytes(640 * 2))
            assert talk.frames_sent == 2
            with pytest.raises(TimeoutError):
                talk.recv_frame(timeout=0.03)
        assert preview_closed.wait(2) and talk_closed.wait(2)
        assert (
            not talk._worker.is_alive() and not talk._preview_worker.is_alive()
        )
    assert [header[0] for header, _ in sent] == [
        0x0B,
        0x0C,
        0x0D,
        0x0D,
        0xA2,
        0xA2,
        0x0D,
    ]
    assert sent[0][0][13:15] == b"\xff\xff"
    assert all(
        header[11:13] == b"\xff\xff"
        for header, _ in sent
        if header[0] in (0x0C, 0x0D)
    )
    assert [header[13] for header, _ in sent if header[0] == 0x0D] == [1, 0, 1]
    encoded = encode_g711(bytes(640), codec)
    assert all(
        body.endswith(encoded) for header, body in sent if header[0] == 0xA2
    )
