"""Offline talk handshakes, limits, cancellation and fragmented TCP reads."""

import hashlib
import socket
import struct
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from quii_helper.device.security.auth import encode_device_password
from quii_helper.protocols.tcp.talk import session as talk_module
from quii_helper.protocols.tcp.talk.session import (
    MAX_STARTUP_MESSAGES,
    LanTalkSession,
)
from quii_helper.protocols.tcp.transport.socket_transport import (
    TcpSocketTransport,
)
from quii_helper.support.errors import ConfigurationError, QuiiConnectionError
from tests.protocols.tcp.test_lan_session import (
    ScriptedSocket,
    config,
    encrypt,
    media,
    setup_reply,
)
from tests.protocols.tcp.test_talk_packets import decrypt


def reply(kind, *, status=0, mask=1, full_packet=0, bad_sha=False):
    header = bytearray(32)
    header[0], header[11] = kind, status
    struct.pack_into("<H", header, 9, 32)
    if kind == 0x0B:
        struct.pack_into("<H", header, 12, mask)
        header[14] = full_packet
    digest = hashlib.sha256(header).digest()
    if bad_sha:
        digest = bytes(32)
    return encrypt(bytes(header)) + encrypt(digest)


def session_and_socket(
    *, responses=None, channel=None, message_observer=None, **overrides
):
    sock = ScriptedSocket()
    if responses is None:
        responses = [reply(0x0B), reply(0x0C), reply(0x0D)]
    sock.chunks.extend(responses)
    transport = TcpSocketTransport("127.0.0.1", 34567)
    transport.connect = lambda **kwargs: setattr(transport, "sock", sock)
    session = LanTalkSession(
        config(**overrides),
        channel=channel,
        transport_factory=lambda host, port: transport,
        message_observer=message_observer,
    )
    return session, sock


@pytest.mark.parametrize("mask,codec", [(1, 4), (2, 5), (3, 4), (0x12, 5)])
@pytest.mark.parametrize("full_packet", [0, 1, 2])
def test_open_waits_for_native_ready_and_negotiates_supported_intersection(
    mask, codec, full_packet
):
    session, sock = session_and_socket(
        responses=[
            reply(0x0B, mask=mask, full_packet=full_packet),
            reply(0x0D),
        ]
    )
    with session:
        assert session.ready and session.receiving
        assert session.codec == codec and session.full_packet == bool(
            full_packet
        )
        assert [decrypt(wire[:32])[0] for wire in sock.sent[1:]] == [
            0x0B,
            0x0C,
            0x0D,
        ]
        assert decrypt(sock.sent[2][:32])[14] == codec - 4
        assert session.open() is session
        assert len(sock.sent) == 4
    assert sock.closed and not session.ready


@pytest.mark.parametrize("password", ["short-auth", "A" * 64])
def test_authentication_is_normalized_exactly_once(password):
    session, sock = session_and_socket(auth_code=password, channel=0)
    with session:
        header, tail = decrypt(sock.sent[1][:32]), decrypt(sock.sent[1][32:])
        assert tail.startswith(
            b"adminapp2&&"
            + encode_device_password(password).encode()
            + b"\0\0"
        )
        assert header[13:15] == b"\xff\xff"
        assert header[15] == 0


@pytest.mark.parametrize(
    "bad_reply,match",
    [
        (reply(0x0B, status=1), "rejected"),
        (reply(0x0B, mask=0x10), "no supported G.711"),
        (reply(0x0B, bad_sha=True), "SHA256"),
        (reply(0x0D), "unexpected"),
        (reply(0xFE), "invalid.*command"),
    ],
)
def test_invalid_open_fails_closed(bad_reply, match):
    session, sock = session_and_socket(responses=[bad_reply])
    with pytest.raises(QuiiConnectionError, match=match):
        session.open()
    assert sock.closed
    with pytest.raises(QuiiConnectionError, match="closed"):
        session.open()


@pytest.mark.parametrize("kind", [0x0C, 0x0D])
def test_send_or_receive_nack_is_not_ready(kind):
    session, sock = session_and_socket(
        responses=[reply(0x0B), reply(kind, status=8)]
    )
    with pytest.raises(QuiiConnectionError, match="status 8"):
        session.open()
    assert sock.closed and not session.ready


def test_handshake_diagnostics_survive_close_without_exposing_credentials():
    session, sock = session_and_socket(
        responses=[reply(0x0B, mask=3), reply(0x0C), reply(0x0D)]
    )
    with session:
        expected = {
            "setup_status": 0,
            "crypto_mode": 2,
            "sha_mode": 1,
            "open_status": 0,
            "codec_mask": 3,
            "c_status": 0,
            "d_status": 0,
        }
        assert session.handshake_diagnostics == expected
        session.handshake_diagnostics["codec_mask"] = 99
        assert session.handshake_diagnostics == expected
    assert sock.closed and session.handshake_diagnostics == expected


@pytest.mark.parametrize(
    "kind,key", [(0x0B, "open_status"), (0x0C, "c_status"), (0x0D, "d_status")]
)
def test_diagnostics_keep_authenticated_rejections(kind, key):
    responses = ([] if kind == 0x0B else [reply(0x0B)]) + [
        reply(kind, status=8)
    ]
    session, _ = session_and_socket(responses=responses)
    with pytest.raises(QuiiConnectionError, match="status 8"):
        session.open()
    assert session.handshake_diagnostics[key] == 8


def test_diagnostics_do_not_report_unverified_ack_as_success():
    session, _ = session_and_socket(
        responses=[reply(0x0B), reply(0x0D, bad_sha=True)]
    )
    with pytest.raises(QuiiConnectionError, match="SHA256"):
        session.open()
    assert session.handshake_diagnostics["d_status"] is None


def test_diagnostics_distinguish_missing_c_reply_from_ready_d_reply():
    session, _ = session_and_socket(responses=[reply(0x0B), reply(0x0D)])
    with session:
        assert session.ready
        assert session.handshake_diagnostics["c_status"] is None
        assert session.handshake_diagnostics["d_status"] == 0


def test_diagnostics_preserve_unsupported_codec_mask():
    session, _ = session_and_socket(responses=[reply(0x0B, mask=16)])
    with pytest.raises(QuiiConnectionError, match="G.711"):
        session.open()
    assert session.handshake_diagnostics["codec_mask"] == 16
    assert session.codec is None


@pytest.mark.parametrize(
    "raw",
    [
        setup_reply(status=1),
        setup_reply(crypto=0),
        setup_reply(sha=0),
        setup_reply(kind=1),
    ],
)
def test_unsupported_setup_fails_before_credentials_are_sent(raw):
    session, sock = session_and_socket()
    sock.chunks[0] = raw
    with pytest.raises(QuiiConnectionError):
        session.open()
    assert len(sock.sent) == 1 and sock.closed


def test_early_media_is_retained_in_order_until_ready():
    session, sock = session_and_socket(
        responses=[media(b"first"), reply(0x0B), media(b"second"), reply(0x0D)]
    )
    with session:
        assert session.recv_message()["payload"] == b"first"
        assert session.recv_message()["payload"] == b"second"
    assert sock.closed


def test_early_media_is_bounded():
    session, sock = session_and_socket(
        responses=[media()] * (MAX_STARTUP_MESSAGES + 1)
    )
    with pytest.raises(QuiiConnectionError, match="too much"):
        session.open()
    assert sock.closed


def test_observer_sees_early_media_once_even_when_dequeued_after_ready():
    observed = []
    session, _ = session_and_socket(
        responses=[media(b"early"), reply(0x0B), reply(0x0D)],
        message_observer=observed.append,
    )
    with session:
        assert len(observed) == 3
        assert session.recv_message()["payload"] == b"early"
        assert len(observed) == 3


def test_observer_sees_early_media_before_later_startup_rejection():
    observed = []
    session, sock = session_and_socket(
        responses=[reply(0x0B), media(b"early"), reply(0x0D, status=8)],
        message_observer=observed.append,
    )
    with pytest.raises(QuiiConnectionError, match="status 8"):
        session.open()
    assert sock.closed
    assert [m["payload"] for m in observed if m["is_media"]] == [b"early"]


def test_observer_does_not_see_unverified_commands():
    observed = []
    session, _ = session_and_socket(
        responses=[reply(0x0B, bad_sha=True)],
        message_observer=observed.append,
    )
    with pytest.raises(QuiiConnectionError, match="SHA256"):
        session.open()
    assert observed == []


def test_observer_failure_closes_session():
    observer = Mock(side_effect=ValueError("synthetic observer failure"))
    session, sock = session_and_socket(message_observer=observer)
    with pytest.raises(QuiiConnectionError, match="startup failed"):
        session.open()
    observer.assert_called_once()
    assert sock.closed


def test_read_timeout_preserves_partial_header_and_body():
    session, sock = session_and_socket()
    packet = media(b"fragmented")
    with session:
        sock.chunks.extend(
            [
                packet[:7],
                socket.timeout(),
                packet[7:35],
                socket.timeout(),
                packet[35:],
            ]
        )
        for _ in range(2):
            with pytest.raises(TimeoutError):
                session.recv_message(timeout=0.01)
            assert session.ready and not sock.closed
        assert session.recv_message()["payload"] == b"fragmented"


def test_receive_toggle_updates_only_after_ack():
    session, sock = session_and_socket()
    with session:
        session.request_receive(False)
        assert session.receiving and session.receive_pending
        with pytest.raises(QuiiConnectionError, match="pending"):
            session.request_receive(True)
        sock.chunks.extend([media(b"in-flight"), reply(0x0D)])
        assert session.recv_message()["is_media"]
        assert session.receive_pending
        session.recv_message()
        assert not session.receiving and not session.receive_pending
        session.request_receive(True)
        sock.chunks.append(reply(0x0D))
        session.recv_message()
        assert session.receiving
        assert [decrypt(wire[:32])[13] for wire in sock.sent[-2:]] == [0, 1]


def test_media_does_not_extend_pending_receive_deadline(monkeypatch):
    session, sock = session_and_socket(connect_timeout=0.5)
    with session:
        clock = [10.0]
        monkeypatch.setattr(
            talk_module, "time", SimpleNamespace(monotonic=lambda: clock[0])
        )
        session.request_receive(False)
        sock.chunks.extend([media(), media()])
        session.recv_message()
        clock[0] += 0.6
        with pytest.raises(QuiiConnectionError, match="timed out"):
            session.recv_message()
        assert sock.closed


@pytest.mark.parametrize(
    "packet", [media(declared_size=65556), media(flag=1), media(offset=99)]
)
def test_invalid_media_lengths_are_rejected_before_reading_body(packet):
    session, sock = session_and_socket()
    with session:
        sock.chunks.append(packet)
        with pytest.raises(QuiiConnectionError, match="media header"):
            session.recv_message()
        assert sock.closed


def test_keepalive_is_not_another_open(monkeypatch):
    session, sock = session_and_socket(live_keepalive_interval=1)
    with session:
        session._last_keepalive = 0
        sock.chunks.append(reply(0))
        session.recv_message()
        assert decrypt(sock.sent[-1][:32])[0] == 0


def test_setup_open_and_ready_share_one_absolute_deadline(monkeypatch):
    clock = [10.0]
    monkeypatch.setattr(
        talk_module, "time", SimpleNamespace(monotonic=lambda: clock[0])
    )
    session, sock = session_and_socket(connect_timeout=0.5)
    original = sock.recv

    def slow_recv(size):
        result = original(size)
        clock[0] += 0.2
        return result

    sock.recv = slow_recv
    with pytest.raises(QuiiConnectionError) as error:
        session.open()
    assert isinstance(error.value.__cause__, TimeoutError)
    assert not session.ready and sock.closed


@pytest.mark.parametrize("kind", [0x0B, 0x0C, 0x0D, 0])
def test_bad_command_digest_after_ready_closes_session(kind):
    session, sock = session_and_socket()
    with session:
        sock.chunks.append(reply(kind, bad_sha=True))
        with pytest.raises(QuiiConnectionError, match="SHA256"):
            session.recv_message()
        assert sock.closed


def test_duplicate_open_after_ready_is_rejected():
    session, sock = session_and_socket()
    with session:
        sock.chunks.append(reply(0x0B))
        with pytest.raises(QuiiConnectionError, match="unexpected.*Open"):
            session.recv_message()
        assert sock.closed


def test_eof_while_reading_audio_closes_session():
    session, sock = session_and_socket()
    with session:
        sock.chunks.append(media()[:-1])
        with pytest.raises(QuiiConnectionError, match="receive failed"):
            session.recv_message()
        assert sock.closed


@pytest.mark.parametrize("operation", ["send", "toggle"])
def test_socket_send_failure_closes_without_retry(operation):
    session, sock = session_and_socket()
    with session:
        sock.sendall = Mock(side_effect=OSError("synthetic send failure"))
        with pytest.raises(OSError):
            if operation == "send":
                session.send_audio(bytes(320))
            else:
                session.request_receive(False)
        sock.sendall.assert_called_once()
        assert sock.closed


def test_invalid_pcm_frame_does_not_close_valid_session():
    session, sock = session_and_socket()
    with session:
        with pytest.raises(ValueError):
            session.send_audio(b"short")
        assert session.ready and not sock.closed


def test_misaligned_encrypted_prefix_is_rejected_before_body_read():
    session, sock = session_and_socket()
    with session:
        packet = media()
        raw = bytearray(decrypt(packet[:32]))
        struct.pack_into("<H", raw, 9, 1)
        sock.chunks.append(encrypt(bytes(raw)))
        with pytest.raises(QuiiConnectionError, match="media header"):
            session.recv_message()
        assert sock.closed


def test_close_during_connect_closes_new_socket():
    entered, resume = threading.Event(), threading.Event()
    sock = ScriptedSocket()
    transport = TcpSocketTransport("127.0.0.1", 34567)

    def connect(**kwargs):
        entered.set()
        assert resume.wait(2)
        transport.sock = sock

    transport.connect = connect
    session = LanTalkSession(
        config(), transport_factory=lambda *args: transport
    )
    errors = []

    def run():
        try:
            session.open()
        except QuiiConnectionError as exc:
            errors.append(exc)

    worker = threading.Thread(target=run)
    worker.start()
    try:
        assert entered.wait(2)
        session.close()
    finally:
        resume.set()
        worker.join(2)
    assert errors and sock.closed and not worker.is_alive()
    assert not sock.sent


@pytest.mark.parametrize(
    "overrides,channel",
    [
        ({"stream_key": ""}, None),
        ({"connection_mode": "cloud"}, None),
        ({}, True),
        ({}, 65536),
    ],
)
def test_invalid_config_is_rejected_before_transport(overrides, channel):
    factory = Mock(side_effect=AssertionError("must not connect"))
    with pytest.raises(ConfigurationError):
        LanTalkSession(
            config(**overrides), channel=channel, transport_factory=factory
        )
    factory.assert_not_called()
