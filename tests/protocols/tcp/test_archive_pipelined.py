"""Offline tests for the ``pipelined`` archive protocol variant.

Firmware such as the Intelbras Allo wT7 is silent to a bare Open and
authenticates the file channel with the cloud ``dynamic-password`` instead of
``auth_code``. These tests exercise that variant against the same scripted TCP
peer as the default path; no device, cloud, or real credentials are involved.
"""

import shutil
import socket
import subprocess

import pytest

from quii_helper.protocols.tcp.archive import download
from quii_helper.support.errors import (
    CameraCaptureError,
    ConfigurationError,
    QuiiConnectionError,
)
from tests.protocols.tcp.test_archive_download import JPEG, cpacket, peer
from tests.protocols.tcp.test_archive_packets import plain, record
from tests.protocols.tcp.test_lan_session import command, config, media

PIPELINED_JPEG = bytes.fromhex(
    "ffd8ffe000104a46494600010200000100010000fffe000f4c61766336302e33"
    "2e31303000ffdb00430008040404040405050505050506060606060606060606"
    "06060607070708080807070706060707080808080909090808080809090a0a0a"
    "0c0c0b0b0e0e0e111114ffc4004c000101000000000000000000000000000000"
    "0601010100000000000000000000000000000607100100000000000000000000"
    "000000000000110100000000000000000000000000000000ffc0001108001000"
    "1003012200021100031100ffda000c03010002110311003f008b00517f7fffd9"
)


def run_pipelined(factory, **options):
    return download.download_record_bytes(
        config(dynamic_password="synthetic-test", oem="TEST"),
        record(),
        transport_factory=factory,
        protocol="pipelined",
        **options,
    )


def test_pipelined_uses_dynamic_password_auth_and_pipelines_sequence():
    sock, transport, factory = peer([media(cpacket(PIPELINED_JPEG))])
    receive = transport.recv_exact

    def checked_receive(size):
        if len(sock.sent) > 1:
            assert [plain(p)[0][0] for p in sock.sent[1:]] == [2, 5, 0x15, 7]
        return receive(size)

    transport.recv_exact = checked_receive
    out = download.download_record_bytes(
        config(dynamic_password="dynpass-123", oem="A0077,G0077"),
        record(),
        transport_factory=factory,
        protocol="pipelined",
    )
    assert out == PIPELINED_JPEG
    assert sock.closed
    # Open/Seek/Playback/0x07 are sent up front (default path sends [2, 5, 0x15]).
    assert [plain(packet)[0][0] for packet in sock.sent[1:]] == [2, 5, 0x15, 7]
    # The Open body is the dynamic-password form, not adminapp2&& + auth_code.
    _, extension = plain(sock.sent[1])
    assert extension.startswith(b"adminapp&&dynpass-123.A0077G0077.")


@pytest.mark.parametrize("marker", [0xE1, 0xFE])
def test_embedded_eoi_in_metadata_does_not_end_the_download(marker):
    segment = bytes([0xFF, marker]) + b"\x00\x06AB\xff\xd9"
    prefix = PIPELINED_JPEG[:2] + segment
    expected = prefix + PIPELINED_JPEG[2:]
    sock, _, factory = peer(
        [media(cpacket(prefix)), media(cpacket(PIPELINED_JPEG[2:]))]
    )
    assert run_pipelined(factory) == expected
    assert not sock.chunks and sock.closed


@pytest.mark.parametrize("layout", ["cpacket", "jpeg"])
@pytest.mark.parametrize("split", [1, 2, 3, 4, 19, 20, 21, 210, 222, 223])
def test_pipelined_picture_survives_fragmentation(layout, split):
    if layout == "cpacket":
        data = cpacket(PIPELINED_JPEG)
        chunks = [data[:split], data[split:]]
    else:
        chunks = [
            cpacket(PIPELINED_JPEG[:split]),
            cpacket(PIPELINED_JPEG[split:]),
        ]
    sock, _, factory = peer([media(chunk) for chunk in chunks])
    assert run_pipelined(factory) == PIPELINED_JPEG
    assert sock.closed


def test_pipelined_tcp_fragments_survive_read_timeouts():
    wire = media(cpacket(PIPELINED_JPEG))
    chunks = []
    for offset in range(0, len(wire), 7):
        chunks.extend([wire[offset : offset + 7], socket.timeout()])
    sock, _, factory = peer(chunks)
    assert run_pipelined(factory) == PIPELINED_JPEG
    assert sock.closed


def test_pipelined_metadata_regression_returns_a_decodable_jpeg():
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.skip("FFmpeg required for JPEG decoding check")
    prefix = PIPELINED_JPEG[:2] + b"\xff\xfe\x00\x06AB\xff\xd9"
    sock, _, factory = peer(
        [media(cpacket(prefix)), media(cpacket(PIPELINED_JPEG[2:]))]
    )
    decoded = subprocess.run(
        [
            ffmpeg,
            "-nostdin",
            "-v",
            "error",
            "-i",
            "pipe:0",
            "-frames:v",
            "1",
            "-pix_fmt",
            "rgb24",
            "-f",
            "rawvideo",
            "pipe:1",
        ],
        input=run_pipelined(factory),
        capture_output=True,
        check=True,
        timeout=10,
    )
    assert len(decoded.stdout) == 16 * 16 * 3 and sock.closed


def test_pipelined_handles_stuffing_restart_dnl_and_multiple_scans():
    scan = PIPELINED_JPEG.index(b"\xff\xda")
    expected = (
        PIPELINED_JPEG[:-2]
        + b"\xff\x00\xd9\xff\xd0\xff\xff\xd1\xff\x01"
        + b"\xff\xdc\x00\x04\x00\x10"
        + PIPELINED_JPEG[scan:]
    )
    sock, _, factory = peer(
        [media(cpacket(bytes([byte]))) for byte in expected]
    )
    assert run_pipelined(factory) == expected
    assert sock.closed


@pytest.mark.parametrize(
    "data",
    [
        b"not-jpeg",
        b"\xff\xd8\xff\xd8",
        b"\xff\xd8\xff\xd0",
        b"\xff\xd8\xff\x00",
        b"\xff\xd8\xff\xfe\x00\x01",
        b"\xff\xd8\xff\xd9",
        b"\xff\xd8\xff\xfe\x00\x08AB\xff\xd9",
        PIPELINED_JPEG + b"trailing",
        PIPELINED_JPEG + b"\x00\x00",
    ],
)
def test_pipelined_rejects_invalid_or_incomplete_jpeg(data):
    sock, _, factory = peer([media(cpacket(data)), command(8)])
    with pytest.raises(CameraCaptureError):
        run_pipelined(factory)
    assert sock.closed


@pytest.mark.parametrize(
    "reply",
    [
        command(2, status=7),
        command(5, status=3),
        command(0x11, status=3),
        command(2, corrupt_sha=True),
    ],
)
def test_pipelined_rejects_errors_before_media(reply):
    sock, _, factory = peer([reply, media(cpacket(PIPELINED_JPEG))])
    with pytest.raises(QuiiConnectionError):
        run_pipelined(factory)
    assert sock.closed


def test_pipelined_enforces_media_limit_without_open_reply():
    sock, _, factory = peer([media(cpacket(PIPELINED_JPEG))])
    with pytest.raises(CameraCaptureError, match="max_bytes"):
        run_pipelined(factory, max_bytes=len(PIPELINED_JPEG) - 1)
    assert sock.closed


def test_pipelined_deadline_closes_partial_picture(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(download.time, "monotonic", lambda: clock[0])
    sock, transport, factory = peer([media(cpacket(PIPELINED_JPEG[:-2]))])
    receive = transport.recv_exact

    def timed_receive(size):
        result = receive(size)
        clock[0] += 0.4
        return result

    transport.recv_exact = timed_receive
    with pytest.raises(CameraCaptureError, match="timed out"):
        run_pipelined(factory, timeout=1.0)
    assert sock.closed


def test_pipelined_disconnect_cannot_complete_a_partial_jpeg():
    sock, _, factory = peer([media(cpacket(PIPELINED_JPEG[:-2]))])
    with pytest.raises(QuiiConnectionError, match="transfer failed"):
        run_pipelined(factory)
    assert sock.closed


def test_pipelined_eoi_does_not_hide_a_partial_cpacket():
    sock, _, factory = peer([media(cpacket(PIPELINED_JPEG) + b"\x00\x00")])
    with pytest.raises(CameraCaptureError, match="incomplete media CPacket"):
        run_pipelined(factory)
    assert sock.closed


def test_pipelined_requires_dynamic_password():
    _, _, factory = peer([command(2), media(cpacket())])
    with pytest.raises(ConfigurationError, match="dynamic_password"):
        download.download_record_bytes(
            config(), record(), transport_factory=factory, protocol="pipelined"
        )


def test_unknown_archive_protocol_is_rejected():
    _, _, factory = peer([command(2), media(cpacket())])
    with pytest.raises(ConfigurationError, match="protocol"):
        download.download_record_bytes(
            config(), record(), transport_factory=factory, protocol="bogus"
        )


def test_default_protocol_keeps_auth_code_open_and_waits_for_reply():
    # Regression guard: the default path is unchanged — adminapp2&& auth and no
    # 0x07, and it still needs the Open reply before Seek/Playback.
    sock, transport, factory = peer([command(2), media(cpacket()), command(8)])
    receive = transport.recv_exact
    reads = [0]

    def checked_receive(size):
        if reads[0] in {1, 2}:
            assert [plain(p)[0][0] for p in sock.sent[1:]] == [2]
        reads[0] += 1
        return receive(size)

    transport.recv_exact = checked_receive
    assert (
        download.download_record_bytes(
            config(), record(), transport_factory=factory
        )
        == JPEG
    )
    assert [plain(packet)[0][0] for packet in sock.sent[1:]] == [2, 5, 0x15]
    _, extension = plain(sock.sent[1])
    assert extension.startswith(b"adminapp2&&")
