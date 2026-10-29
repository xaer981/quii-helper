"""Offline JPEG download against a scripted TCP peer; no device/cloud I/O."""

import socket
import struct
from unittest.mock import Mock

import pytest

from quii_helper.device.security.auth import encode_device_password
from quii_helper.protocols.tcp.archive import download
from quii_helper.protocols.tcp.transport.socket_transport import (
    TcpSocketTransport,
)
from quii_helper.support.errors import (
    CameraCaptureError,
    ConfigurationError,
    QuiiConnectionError,
)
from tests.protocols.tcp.test_archive_packets import plain, record
from tests.protocols.tcp.test_lan_session import (
    ScriptedSocket,
    command,
    config,
    encrypt,
    media,
    setup_reply,
)

JPEG = b"\xff\xd8synthetic-JPEG-writer-payload\xff\xd9"


def cpacket(data=JPEG, *, marker=0xE4, codec=3, declared=None):
    header = bytearray(20)
    header[:4] = b"\0\0\x01" + bytes([marker])
    struct.pack_into(
        "<I", header, 4, len(data) if declared is None else declared
    )
    header[14] = codec
    return bytes(header) + data


def unaligned_prefix_header():
    header = bytearray(32)
    header[0], header[9] = 0xA0, 1
    struct.pack_into("<I", header, 11, 100)
    return encrypt(bytes(header))


def peer(responses, *, raw_setup=None):
    sock = ScriptedSocket()
    if raw_setup is not None:
        sock.chunks[0] = raw_setup
    sock.chunks.extend(responses)
    transport = TcpSocketTransport("127.0.0.1", 34567)
    transport.connect = lambda **kwargs: setattr(transport, "sock", sock)
    factory = Mock(return_value=transport)
    return sock, transport, factory


def run(factory, **options):
    return download.download_record_bytes(
        config(), record(), transport_factory=factory, **options
    )


def test_native_open_seek_mode_media_and_end_return_original_bytes():
    sock, _, factory = peer([command(2), media(cpacket()), command(8)])
    assert run(factory) == JPEG
    assert sock.closed
    assert sock.sent[0] == b"\xa9" + bytes(8) + b"\x01" + bytes(22)
    assert [plain(packet)[0][0] for packet in sock.sent[1:]] == [2, 5, 0x15]
    factory.assert_called_once_with("127.0.0.1", 34567)


@pytest.mark.parametrize("auth", ["short-auth", "A" * 64])
def test_open_normalizes_saved_auth_exactly_once(auth):
    sock, _, factory = peer([command(2), media(cpacket()), command(8)])
    assert (
        download.download_record_bytes(
            config(auth_code=auth), record(), transport_factory=factory
        )
        == JPEG
    )
    _, extension = plain(sock.sent[1])
    assert extension.startswith(
        b"adminapp2&&" + encode_device_password(auth).encode() + b"\0\0"
    )


@pytest.mark.parametrize("open_kind", [0, 1, 3])
def test_pending_open_reply_matches_native_state_not_only_opcode(open_kind):
    sock, _, factory = peer([command(open_kind), media(cpacket()), command(8)])
    assert run(factory) == JPEG
    assert sock.closed


@pytest.mark.parametrize("kind", [1, 12, 13, 17, 0xAA])
def test_every_native_play_nack_is_rejected_even_if_jpeg_follows(kind):
    sock, _, factory = peer(
        [command(2), command(kind, status=3), media(cpacket()), command(8)]
    )
    with pytest.raises(QuiiConnectionError, match="command.*rejected.*3"):
        run(factory)
    assert sock.closed


@pytest.mark.parametrize("split", [1, 2, 3, 7, 19, 20, 21, 35])
def test_cpacket_fragments_across_media_messages_are_not_lost(split):
    blob = cpacket()
    sock, _, factory = peer(
        [command(2), media(blob[:split]), media(blob[split:]), command(8)]
    )
    assert run(factory) == JPEG
    assert sock.closed


def test_multiple_cpackets_are_concatenated_like_native_jpeg_writer():
    sock, _, factory = peer(
        [command(2), media(cpacket(JPEG[:7]) + cpacket(JPEG[7:])), command(8)]
    )
    assert run(factory) == JPEG
    assert sock.closed


def test_fragmented_and_coalesced_tcp_messages_with_read_timeouts():
    wire = command(2) + media(cpacket(), prefix=b"X" * 32) + command(8)
    chunks = []
    for offset in range(0, len(wire), 7):
        chunks.extend((wire[offset : offset + 7], socket.timeout()))
    sock, _, factory = peer(chunks)
    assert run(factory) == JPEG
    assert sock.closed


@pytest.mark.parametrize(
    "raw_setup",
    [
        setup_reply(status=1),
        setup_reply(crypto=0),
        setup_reply(crypto=1),
        setup_reply(sha=0),
        setup_reply(kind=1),
    ],
)
def test_setup_is_validated_before_sending_credentials(raw_setup):
    sock, _, factory = peer([], raw_setup=raw_setup)
    with pytest.raises(QuiiConnectionError):
        run(factory)
    assert len(sock.sent) == 1 and sock.closed


@pytest.mark.parametrize(
    "responses,match",
    [
        ([command(2, status=7)], "Open rejected.*7"),
        ([command(2, corrupt_sha=True)], "SHA256"),
        ([command(2), command(5, status=3)], "command.*rejected"),
        ([command(2), command(0x11, status=3)], "command.*rejected"),
        (
            [command(2), media(cpacket()), command(8, corrupt_sha=True)],
            "SHA256",
        ),
        ([media(cpacket())], "before Open"),
        ([command(0x99)], "command header"),
        ([command(2), media(cpacket(), flag=1)], "media header"),
        ([command(2), media(cpacket(), offset=65535)], "media header"),
        ([command(2), unaligned_prefix_header()], "media header"),
        (
            [
                command(2),
                media(b"", declared_size=download.MAX_TCP_PAYLOAD_BYTES + 1),
            ],
            "media header",
        ),
    ],
)
def test_rejected_corrupt_or_unsupported_messages_fail_closed(
    responses, match
):
    sock, _, factory = peer(responses)
    with pytest.raises(QuiiConnectionError, match=match):
        run(factory)
    assert sock.closed


@pytest.mark.parametrize(
    "stage", [[], [command(2)], [command(2), media(cpacket())]]
)
def test_disconnect_is_not_success_even_with_a_complete_jpeg(stage):
    sock, _, factory = peer(stage)
    with pytest.raises(QuiiConnectionError, match="transfer failed"):
        run(factory)
    assert sock.closed


@pytest.mark.parametrize(
    "payload,match",
    [
        (b"", "without a complete JPEG"),
        (cpacket()[:10], "incomplete"),
        (cpacket()[:-1], "incomplete"),
        (cpacket(b"not-a-JPEG"), "without a complete JPEG"),
        (cpacket(JPEG[:-2]), "without a complete JPEG"),
        (cpacket(JPEG[2:]), "without a complete JPEG"),
        (cpacket(marker=0xE1, codec=1), "non-JPEG"),
        (cpacket(codec=4), "non-JPEG"),
        (cpacket(declared=0), "invalid length"),
        (cpacket() + b"garbage", "incomplete"),
    ],
)
def test_end_requires_complete_picture_framing(payload, match):
    responses = [command(2)]
    if payload:
        responses.append(media(payload))
    responses.append(command(8))
    sock, _, factory = peer(responses)
    with pytest.raises(CameraCaptureError, match=match):
        run(factory)
    assert sock.closed


def test_limit_is_checked_on_declared_frame_before_payload_allocation():
    sock, _, factory = peer([command(2), media(cpacket(b"", declared=20000))])
    with pytest.raises(CameraCaptureError, match="max_bytes"):
        run(factory, max_bytes=1024)
    assert sock.closed


def test_limit_applies_to_all_writer_packets_not_each_one_separately():
    sock, _, factory = peer(
        [command(2), media(cpacket(JPEG[:7]) + cpacket(JPEG[7:])), command(8)]
    )
    with pytest.raises(CameraCaptureError, match="max_bytes"):
        run(factory, max_bytes=len(JPEG) - 1)
    assert sock.closed


def test_timeout_is_one_deadline_and_closes_partial_transfer(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(download.time, "monotonic", lambda: clock[0])
    sock, transport, factory = peer([command(2), media(cpacket())])
    recv = transport.recv_exact

    def timed_recv(size):
        result = recv(size)
        clock[0] += 0.4
        return result

    transport.recv_exact = timed_recv
    with pytest.raises(CameraCaptureError, match="timed out"):
        run(factory, timeout=1.0)
    assert sock.closed and clock[0] <= 1.3


def test_keepalive_is_header_only_and_does_not_restart_live_preview(
    monkeypatch,
):
    clock = [0.0]
    monkeypatch.setattr(download.time, "monotonic", lambda: clock[0])
    sock, transport, factory = peer([command(2), media(cpacket()), command(8)])
    recv = transport.recv_exact

    def timed_recv(size):
        result = recv(size)
        clock[0] += 1.0
        return result

    transport.recv_exact = timed_recv
    result = download.download_record_bytes(
        config(live_keepalive_interval=1.0),
        record(),
        timeout=30,
        transport_factory=factory,
    )
    assert result == JPEG and sock.closed
    kinds = [plain(packet)[0][0] for packet in sock.sent[1:]]
    assert 0 in kinds and 1 not in kinds


@pytest.mark.parametrize(
    "failure", [OSError("send failed"), KeyboardInterrupt()]
)
def test_send_failure_or_interrupt_always_closes(failure):
    sock, transport, factory = peer([])
    transport.send_all = Mock(side_effect=failure)
    expected = (
        KeyboardInterrupt
        if isinstance(failure, KeyboardInterrupt)
        else QuiiConnectionError
    )
    with pytest.raises(expected):
        run(factory)
    assert sock.closed


@pytest.mark.parametrize(
    "options",
    [
        {"timeout": 0},
        {"timeout": -1},
        {"timeout": float("nan")},
        {"timeout": float("inf")},
        {"timeout": True},
        {"timeout": "30"},
        {"timeout": 10**400},
        {"max_bytes": 0},
        {"max_bytes": -1},
        {"max_bytes": True},
        {"max_bytes": 3.5},
    ],
)
def test_invalid_limits_are_rejected_before_transport_creation(options):
    factory = Mock(side_effect=AssertionError("transport forbidden"))
    with pytest.raises(ConfigurationError):
        run(factory, **options)
    factory.assert_not_called()


@pytest.mark.parametrize(
    "overrides",
    [
        {"connection_mode": "cloud"},
        {"device_host": "camera.example"},
        {"stream_key": ""},
        {"auth_code": ""},
    ],
)
def test_invalid_lan_config_does_not_resolve_hosts_or_fetch_credentials(
    overrides,
):
    factory = Mock(side_effect=AssertionError("transport forbidden"))
    with pytest.raises(ConfigurationError):
        download.download_record_bytes(
            config(**overrides), record(), transport_factory=factory
        )
    factory.assert_not_called()


def test_untrusted_url_is_not_used_and_cgi_size_is_not_exact_length():
    sock, _, factory = peer([command(2), media(cpacket()), command(8)])
    entry = record(url="https://example.invalid/private", file_size=1)
    assert (
        download.download_record_bytes(
            config(), entry, transport_factory=factory
        )
        == JPEG
    )
    factory.assert_called_once_with("127.0.0.1", 34567)
    assert sock.closed


def test_invalid_metadata_is_rejected_before_transport_creation():
    factory = Mock(side_effect=AssertionError("transport forbidden"))
    with pytest.raises(ConfigurationError):
        download.download_record_bytes(
            config(), record(picture_index=""), transport_factory=factory
        )
    factory.assert_not_called()


def test_oversized_auth_is_rejected_before_transport_creation():
    factory = Mock(side_effect=AssertionError("transport forbidden"))
    with pytest.raises(ConfigurationError, match="authentication body"):
        download.download_record_bytes(
            config(auth_code="A" * 65535), record(), transport_factory=factory
        )
    factory.assert_not_called()


def test_wrong_saved_key_fails_closed_without_exposing_credentials():
    sock, _, factory = peer([command(2), media(cpacket()), command(8)])
    with pytest.raises(QuiiConnectionError) as caught:
        download.download_record_bytes(
            config(stream_key="W" * 32), record(), transport_factory=factory
        )
    assert "W" * 32 not in str(caught.value)
    assert "synthetic-auth" not in str(caught.value)
    assert sock.closed


def test_sha_checked_transparent_reply_does_not_confuse_file_framing():
    sock, _, factory = peer(
        [
            command(2),
            command(0xFE, body=b"read-only information"),
            command(5),
            command(0x11),
            media(cpacket()),
            command(8),
        ]
    )
    assert run(factory) == JPEG
    assert sock.closed
