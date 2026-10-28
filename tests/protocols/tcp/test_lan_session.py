"""Synthetic native-layout packets only; no camera/cloud traffic."""

import hashlib
import socket
import struct
import threading
import warnings
from collections import deque
from unittest.mock import Mock

import pytest

from quii_helper import Camera, load_config
from quii_helper.config import AutonomousConfig
from quii_helper.device.security.auth import encode_device_password
from quii_helper.protocols.quii.crypto import aes_cbc_crypt
from quii_helper.protocols.tcp.live.session import (
    MAX_TCP_PAYLOAD_BYTES,
    LanTcpSession,
    validate_lan_config,
)
from quii_helper.protocols.tcp.transport.socket_transport import (
    TcpSocketTransport,
)
from quii_helper.support.errors import ConfigurationError, QuiiConnectionError

KEY = "K" * 32


def config(**overrides):
    values = dict(
        device_host="127.0.0.1",
        stream_key=KEY,
        auth_code="synthetic-auth",
        stream=1,
    )
    values.update(overrides)
    return AutonomousConfig(**values)


def encrypt(data):
    return aes_cbc_crypt(data, KEY, crypto_mode=2)


def setup_reply(status=0, crypto=2, sha=1, kind=0xA9):
    header = bytearray(32)
    header[0], header[9], header[10], header[11] = kind, status, crypto, sha
    return bytes(header)


def command(kind=1, *, status=0, active=1, body=b"", corrupt_sha=False):
    header = bytearray(32)
    header[0] = kind
    body = body if kind == 0xFE else b""
    size = (len(body) + 32 + 15) // 16 * 16
    struct.pack_into("<H", header, 9, size)
    if kind == 0xFE:
        struct.pack_into("<H", header, 11, len(body))
    else:
        header[11], header[12] = status, active
    digest = hashlib.sha256(header + body).digest()
    if corrupt_sha:
        digest = bytes([digest[0] ^ 1]) + digest[1:]
    return encrypt(bytes(header)) + encrypt(
        (body + digest).ljust(size, b"\x00")
    )


def media(
    payload=b"native-layout-media",
    *,
    prefix=b"",
    offset=None,
    flag=0,
    declared_size=None,
):
    header = bytearray(32)
    header[0] = 0xA0
    struct.pack_into("<H", header, 9, len(prefix))
    struct.pack_into(
        "<I",
        header,
        11,
        len(prefix) + len(payload) if declared_size is None else declared_size,
    )
    header[15] = flag
    struct.pack_into(
        "<H", header, 16, len(prefix) if offset is None else offset
    )
    return (
        encrypt(bytes(header)) + (encrypt(prefix) if prefix else b"") + payload
    )


class ScriptedSocket:
    def __init__(self):
        self.chunks = deque([setup_reply()])
        self.sent = []
        self.closed = False
        self.timeout = 1.0

    def recv(self, size):
        if not self.chunks:
            return b""
        chunk = self.chunks.popleft()
        if isinstance(chunk, BaseException):
            raise chunk
        if len(chunk) > size:
            self.chunks.appendleft(chunk[size:])
        return chunk[:size]

    def sendall(self, data):
        self.sent.append(data)

    def settimeout(self, timeout):
        self.timeout = timeout

    def gettimeout(self):
        return self.timeout

    def shutdown(self, how):
        self.closed = True

    def close(self):
        self.closed = True


def session_and_socket(**overrides):
    sock = ScriptedSocket()
    transport = TcpSocketTransport("127.0.0.1", 34567)

    def connect(timeout):
        transport.sock = sock

    transport.connect = connect
    session = LanTcpSession(
        config(**overrides), transport_factory=lambda host, port: transport
    )
    return session, sock


def test_close_after_receive_before_buffer_copy_never_returns_short_header():
    transport = TcpSocketTransport("127.0.0.1", 1)
    sock = ScriptedSocket()
    sock.chunks.clear()
    sock.chunks.append(b"x" * 32)
    transport.sock = sock
    calls = []

    def restore_timeout(timeout):
        calls.append(timeout)
        if len(calls) == 2:
            transport.close()

    sock.settimeout = restore_timeout
    with pytest.raises(RuntimeError, match="socket is closed"):
        transport.recv_exact(32)
    assert sock.closed and transport.sock is None


@pytest.mark.parametrize("channel", [1, 2])
@pytest.mark.parametrize(
    "stream,expected", [("high", 1), ("low", 2), ("3", 3)]
)
def test_environment_selectors_reach_camera_play_header(
    channel, stream, expected, monkeypatch
):
    camera = Camera(
        config=load_config(
            env={
                "CAMERA_DEVICE_HOST": "127.0.0.1",
                "STREAM_KEY": KEY,
                "AUTH_CODE": "synthetic-auth",
                "CAMERA_CHANNEL": str(channel),
                "CAMERA_STREAM": stream,
            }
        )
    )
    session = camera.connector.create_lan_session()
    sock = ScriptedSocket()
    monkeypatch.setattr(
        session._client.transport,
        "connect",
        lambda **kwargs: setattr(session._client.transport, "sock", sock),
    )
    with session:
        header = aes_cbc_crypt(
            sock.sent[1][:32], KEY, crypto_mode=2, decrypt=True
        )
        assert struct.unpack_from("<H", header, 13)[0] == channel
        assert header[16] == expected - 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"device_host": "camera.example"},
        {"device_host": ""},
        {"device_host": "0.0.0.0"},
        {"device_host": "239.0.0.1"},
        {"stream_key": "short"},
        {"stream_key": "K" * 33},
        {"stream_key": "\x00" * 32},
        {"auth_code": ""},
        {"auth_code": "a" * 64 + "\x00"},
        {"channel": 0},
        {"channel": True},
        {"channel": 0x10000},
        {"stream": True},
        {"stream": 0x101},
        {"connect_timeout": float("nan")},
        {"connect_timeout": 0},
        {"live_keepalive_interval": float("inf")},
        {"connection_mode": "cloud"},
    ],
)
def test_invalid_lan_inputs_fail_before_transport_construction(overrides):
    factory = Mock(side_effect=AssertionError("network must not start"))
    with pytest.raises(ConfigurationError):
        LanTcpSession(config(**overrides), transport_factory=factory)
    factory.assert_not_called()


@pytest.mark.parametrize(
    "overrides,option",
    [
        ({"live_play_payload": "oem"}, "live_play_payload"),
        ({"live_inner": True}, "live_inner"),
        ({"live_newcn": True}, "live_newcn"),
    ],
)
def test_legacy_lan_live_options_warn_and_keep_verified_packet(
    overrides, option
):
    with pytest.warns(UserWarning, match=option):
        session, sock = session_and_socket(**overrides)
    with session:
        header = aes_cbc_crypt(
            sock.sent[1][:32], KEY, crypto_mode=2, decrypt=True
        )
        body = aes_cbc_crypt(
            sock.sent[1][32:], KEY, crypto_mode=2, decrypt=True
        )
        assert header[17] == 0
        assert b"/mode=real&idc=1&ids=1&ap=2\x00" in body
        assert b"inner=" not in body and b"newcn=" not in body


def test_explicit_supported_lan_live_options_preserve_play_packet():
    session, sock = session_and_socket(
        live_play_payload="path", live_inner=False, live_newcn=False
    )
    with session:
        header = aes_cbc_crypt(
            sock.sent[1][:32], KEY, crypto_mode=2, decrypt=True
        )
        body = aes_cbc_crypt(
            sock.sent[1][32:], KEY, crypto_mode=2, decrypt=True
        )
        assert header[17] == 0
        assert b"/mode=real&idc=1&ids=1&ap=2\x00" in body
        assert b"inner=" not in body and b"newcn=" not in body


def test_default_warning_filter_deduplicates_rtsp_preflight_and_session():
    settings = config(live_newcn=True)
    with warnings.catch_warnings(record=True) as observed:
        warnings.simplefilter("default")
        validate_lan_config(settings)
        LanTcpSession(settings)
    assert len(observed) == 1
    assert "live_newcn" in str(observed[0].message)


@pytest.mark.parametrize(
    ("channel", "stream"),
    [(1, 1), (2, 1), (1, 2), (1, 3), (2, 2), (0x102, 0x100), (0xFFFF, 1)],
)
def test_play_matches_native_seconds_flags_body_and_separate_aes(
    monkeypatch, channel, stream
):
    monkeypatch.setattr(
        "quii_helper.protocols.tcp.live.packet_builder.time.time",
        lambda: 1700000000,
    )
    session, sock = session_and_socket(channel=channel, stream=stream)
    with session:
        assert sock.sent[0] == b"\xa9" + bytes(31)
        packet = sock.sent[1]
        header = aes_cbc_crypt(packet[:32], KEY, crypto_mode=2, decrypt=True)
        body = aes_cbc_crypt(packet[32:], KEY, crypto_mode=2, decrypt=True)
        assert struct.unpack_from("<Q", header, 1)[0] == 1700000000
        assert header[13:18] == struct.pack("<HBBB", channel, 1, stream - 1, 0)
        expected = (
            "adminapp2&&"
            + encode_device_password("synthetic-auth")
            + f"\x00/mode=real&idc={channel}&ids={stream}&ap=2\x00"
        ).encode()
        assert struct.unpack_from("<H", header, 11)[0] == len(expected)
        assert body[: len(expected)] == expected
        assert (
            body[len(expected) : len(expected) + 32]
            == hashlib.sha256(header + expected).digest()
        )
    assert sock.closed


@pytest.mark.parametrize(
    "reply",
    [
        setup_reply(status=1),
        setup_reply(crypto=0),
        setup_reply(crypto=1),
        setup_reply(sha=0),
        setup_reply(kind=0),
    ],
)
def test_rejected_or_unsupported_setup_closes_without_sending_play(reply):
    session, sock = session_and_socket()
    sock.chunks = deque([reply])
    with pytest.raises(QuiiConnectionError):
        session.open()
    assert sock.closed and len(sock.sent) == 1


def test_header_and_body_timeouts_preserve_every_byte():
    session, sock = session_and_socket()
    packet = command(0xFE, body=b"transparent-content")
    sock.chunks.extend(
        [packet[:7], TimeoutError(), packet[7:40], TimeoutError(), packet[40:]]
    )
    with session:
        for _ in range(2):
            with pytest.raises(TimeoutError):
                session.recv_message()
            assert not sock.closed
        decoded = session.recv_message()
        assert decoded["header"].packet_type == 0xFE
        assert decoded["payload"].startswith(b"transparent-content")


def test_coalesced_command_and_media_keep_packet_boundaries():
    session, sock = session_and_socket()
    sock.chunks.append(
        command() + media(b"one", prefix=b"p" * 16) + media(b"two")
    )
    with session:
        assert not session.recv_message()["is_media"]
        assert session.play_accepted
        assert session.recv_message()["payload"] == b"one"
        assert session.recv_message()["payload"] == b"two"


@pytest.mark.parametrize(
    "packet",
    [
        command(corrupt_sha=True),
        command(status=4),
        media(flag=1),
        media(offset=500),
        media(declared_size=MAX_TCP_PAYLOAD_BYTES + 1),
        media(declared_size=0),
        encrypt(bytes([0x99]) + bytes(31)),
    ],
)
def test_invalid_packets_fail_closed(packet):
    session, sock = session_and_socket()
    sock.chunks.append(packet)
    with session:
        with pytest.raises(QuiiConnectionError):
            session.recv_message()
        assert sock.closed


def test_eof_mid_body_closes_session():
    session, sock = session_and_socket()
    sock.chunks.append(command()[:40])
    with session:
        with pytest.raises(QuiiConnectionError):
            session.recv_message()
        assert sock.closed


def test_keepalive_uses_native_envelope_only_after_play_acceptance(
    monkeypatch,
):
    clock = [100.0]
    monkeypatch.setattr(
        "quii_helper.protocols.tcp.live.session.time.monotonic",
        lambda: clock[0],
    )
    session, sock = session_and_socket()
    sock.chunks.extend([command(), TimeoutError(), TimeoutError()])
    with session:
        clock[0] = 120
        session.recv_message()
        assert len(sock.sent) == 2
        with pytest.raises(TimeoutError):
            session.recv_message()
        assert len(sock.sent) == 3
        header = aes_cbc_crypt(
            sock.sent[-1][:32], KEY, crypto_mode=2, decrypt=True
        )
        body = aes_cbc_crypt(
            sock.sent[-1][32:], KEY, crypto_mode=2, decrypt=True
        )
        assert header[0] == 0 and header[11:13] == b"\0\0"
        assert header[13:] == bytes(19)
        assert body == hashlib.sha256(header).digest()
        with pytest.raises(TimeoutError):
            session.recv_message()
        assert len(sock.sent) == 3


def test_close_is_idempotent_and_closed_session_does_not_reconnect():
    session, sock = session_and_socket()
    session.open()
    session.close()
    session.close()
    with pytest.raises(QuiiConnectionError, match="new session"):
        session.open()
    assert sock.closed


def test_close_during_connect_prevents_setup():
    transport = Mock(spec=TcpSocketTransport)
    session = LanTcpSession(
        config(), transport_factory=lambda host, port: transport
    )
    transport.connect.side_effect = lambda **kwargs: session.close()
    with pytest.raises(QuiiConnectionError):
        session.open()
    transport.send_all.assert_not_called()


def test_setup_eof_is_a_domain_error_and_releases_socket():
    session, sock = session_and_socket()
    sock.chunks.clear()
    with pytest.raises(QuiiConnectionError, match="startup failed"):
        session.open()
    assert sock.closed


def test_already_encoded_auth_code_is_not_hashed_again():
    encoded = encode_device_password("synthetic-auth")
    session, sock = session_and_socket(auth_code=encoded)
    with session:
        body = aes_cbc_crypt(
            sock.sent[1][32:], KEY, crypto_mode=2, decrypt=True
        )
        assert body.startswith(("adminapp2&&" + encoded + "\0").encode())


def test_tcp_read_deadline_stops_drip_feed_and_preserves_partial_bytes(
    monkeypatch,
):
    clock = [0.0]
    monkeypatch.setattr(
        "quii_helper.protocols.tcp.transport.socket_transport.time.monotonic",
        lambda: clock[0],
    )
    sock = ScriptedSocket()
    sock.chunks = deque([b"a", b"b"])
    original_recv = sock.recv

    def recv(size):
        chunk = original_recv(size)
        clock[0] += 0.6
        return chunk

    sock.recv = recv
    transport = TcpSocketTransport("127.0.0.1", 1)
    transport.sock = sock
    with pytest.raises(TimeoutError, match="deadline"):
        transport.recv_exact(3)
    sock.chunks.append(b"c")
    assert transport.recv_exact(3) == b"abc"
    transport.close()


def test_close_interrupts_a_blocked_socket_read():
    local, peer = socket.socketpair()
    transport = TcpSocketTransport("127.0.0.1", 1)
    transport.sock = local
    started = threading.Event()
    errors = []

    def receive():
        started.set()
        try:
            transport.recv_exact(32)
        except (OSError, RuntimeError) as exc:
            errors.append(exc)

    worker = threading.Thread(target=receive, daemon=True)
    try:
        worker.start()
        assert started.wait(1)
        transport.close()
        worker.join(timeout=2)
        assert not worker.is_alive()
        assert len(errors) == 1
    finally:
        transport.close()
        peer.close()


def test_real_loopback_server_accepts_play_and_streams_media():
    errors = []
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(3)

    def serve():
        try:
            sock, _ = listener.accept()
            with sock:
                sock.settimeout(3)

                def read(size):
                    data = bytearray()
                    while len(data) < size:
                        chunk = sock.recv(size - len(data))
                        assert chunk
                        data.extend(chunk)
                    return bytes(data)

                assert read(32) == b"\xa9" + bytes(31)
                sock.sendall(setup_reply())
                header = aes_cbc_crypt(
                    read(32), KEY, crypto_mode=2, decrypt=True
                )
                read(int.from_bytes(header[9:11], "little"))
                sock.sendall(
                    command(0xFE, body=b"hello")
                    + command()
                    + media(b"loopback-video")
                )
        except BaseException as exc:
            errors.append(exc)

    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    try:
        with LanTcpSession(
            config(stream_port=listener.getsockname()[1])
        ) as session:
            assert session.recv_message()["header"].packet_type == 0xFE
            session.recv_message()
            assert session.play_accepted
            assert session.recv_message()["payload"] == b"loopback-video"
    finally:
        listener.close()
        worker.join(timeout=4)
    assert not worker.is_alive()
    assert not errors


def test_message_deadline_includes_header_and_body(monkeypatch):
    session, sock = session_and_socket()
    session.open()
    clock = [0.0]
    monkeypatch.setattr(
        "quii_helper.protocols.tcp.live.session.time.monotonic",
        lambda: clock[0],
    )
    sock.chunks.append(media(b"body"))
    receive = session._client.recv_exact

    def delayed_read(size):
        result = receive(size)
        if size == 32:
            clock[0] += 0.7
        return result

    session._client.recv_exact = delayed_read
    assert session.recv_message(timeout=1.0)["payload"] == b"body"
    assert sock.timeout == pytest.approx(0.3)
    session.close()


def test_stream_switch_preserves_media_and_changes_state_only_after_ack():
    session, sock = session_and_socket()
    sock.chunks.append(command())
    with session:
        session.recv_message()
        assert session.active_stream == 1
        session.request_stream_switch(2)
        assert len(sock.sent) == 3
        assert session.stream_switch_pending and session.active_stream == 1
        sock.chunks.append(
            media(b"before-ack") + command(9, active=0) + media(b"after-ack")
        )
        assert session.recv_message()["payload"] == b"before-ack"
        assert session.stream_switch_pending
        assert session.recv_message()["header"].packet_type == 9
        assert not session.stream_switch_pending
        assert session.active_stream == 2 and session.config.stream == 1
        assert session.recv_message()["payload"] == b"after-ack"
        session.request_stream_switch(1)
        sock.chunks.append(command(9, active=0))
        session.recv_message()
        assert session.active_stream == 1
    assert session.active_stream is None and not session.stream_switch_pending


def test_switch_to_current_selector_is_not_optimized_away():
    session, sock = session_and_socket()
    sock.chunks.append(command())
    with session:
        session.recv_message()
        session.request_stream_switch(1)
        assert session.stream_switch_pending and len(sock.sent) == 3
        with pytest.raises(QuiiConnectionError, match="pending"):
            session.request_stream_switch(2)
        assert not sock.closed and len(sock.sent) == 3


@pytest.mark.parametrize("status", [0, 3])
def test_unsolicited_switch_reply_preserves_existing_receive_behavior(status):
    session, sock = session_and_socket()
    sock.chunks.append(command() + command(9, status=status, active=0))
    with session:
        session.recv_message()
        session.recv_message()
        assert not sock.closed and session.active_stream == 1
        assert not session.stream_switch_pending and len(sock.sent) == 2


@pytest.mark.parametrize(
    "reply,error",
    [
        (command(9, status=2), "status 2"),
        (command(9, corrupt_sha=True), "SHA256"),
    ],
)
def test_switch_rejection_or_corrupted_ack_fails_closed(reply, error):
    session, sock = session_and_socket()
    sock.chunks.append(command())
    with session:
        session.recv_message()
        session.request_stream_switch(2)
        sock.chunks.append(reply)
        with pytest.raises(QuiiConnectionError, match=error):
            session.recv_message()
        assert sock.closed and not session.stream_switch_pending


def test_switch_ack_survives_partial_read_timeout():
    session, sock = session_and_socket()
    sock.chunks.append(command())
    with session:
        session.recv_message()
        session.request_stream_switch(2)
        reply = command(9, active=0)
        sock.chunks.extend([reply[:40], TimeoutError(), reply[40:]])
        with pytest.raises(TimeoutError):
            session.recv_message()
        assert session.stream_switch_pending and not sock.closed
        session.recv_message()
        assert session.active_stream == 2 and not session.stream_switch_pending


def test_switch_deadline_limits_read_and_closes_without_retry(monkeypatch):
    session, sock = session_and_socket()
    sock.chunks.append(command())
    clock = [100.0]
    monkeypatch.setattr(
        "quii_helper.protocols.tcp.live.session.time.monotonic",
        lambda: clock[0],
    )
    with session:
        session.recv_message()
        session.request_stream_switch(2, timeout=2)

        def blocked_recv(size):
            clock[0] += sock.timeout
            raise TimeoutError()

        sock.recv = blocked_recv
        with pytest.raises(QuiiConnectionError, match="switch timed out"):
            session.recv_message(timeout=30)
        assert sock.timeout == pytest.approx(2)
        assert sock.closed and not session.stream_switch_pending
        with pytest.raises(QuiiConnectionError):
            session.request_stream_switch(2)
        assert len(sock.sent) == 3


def test_media_does_not_extend_switch_deadline(monkeypatch):
    session, sock = session_and_socket()
    sock.chunks.append(command())
    clock = [100.0]
    monkeypatch.setattr(
        "quii_helper.protocols.tcp.live.session.time.monotonic",
        lambda: clock[0],
    )
    with session:
        session.recv_message()
        session.request_stream_switch(2, timeout=2)
        clock[0] = 101
        sock.chunks.append(media(b"still-streaming"))
        assert session.recv_message()["payload"] == b"still-streaming"
        clock[0] = 102
        sock.chunks.append(command(9))
        with pytest.raises(QuiiConnectionError, match="switch timed out"):
            session.recv_message()
        assert sock.closed


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_invalid_switch_timeout_does_not_send_or_close(timeout):
    session, sock = session_and_socket()
    sock.chunks.append(command())
    with session:
        session.recv_message()
        with pytest.raises(ValueError, match="timeout"):
            session.request_stream_switch(2, timeout=timeout)
        assert len(sock.sent) == 2 and not sock.closed
        assert not session.stream_switch_pending


def test_switch_requires_play_acceptance():
    session, sock = session_and_socket()
    with pytest.raises(QuiiConnectionError, match="not active"):
        session.request_stream_switch(2)
    with session:
        with pytest.raises(QuiiConnectionError, match="not active"):
            session.request_stream_switch(2)
        assert len(sock.sent) == 2 and not session.stream_switch_pending


@pytest.mark.parametrize("cancelled", [False, True])
def test_switch_send_failure_or_cancellation_releases_socket(cancelled):
    session, sock = session_and_socket()
    sock.chunks.append(command())
    with session:
        session.recv_message()

        def send(packet):
            if cancelled:
                session.close()
            else:
                raise OSError("synthetic send failure")

        session._client.transport.send_all = send
        with pytest.raises(QuiiConnectionError):
            session.request_stream_switch(2)
        assert sock.closed and not session.stream_switch_pending
