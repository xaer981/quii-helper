"""Native CQUIITalk layouts from both SDKs, using synthetic credentials."""

import hashlib
import struct
from datetime import datetime
from types import SimpleNamespace

import pytest

from quii_helper.protocols.quii import live_envelope
from quii_helper.protocols.quii.crypto import aes_cbc_crypt
from quii_helper.protocols.tcp.talk import packets
from tests.protocols.tcp.test_lan_session import KEY


def decrypt(data):
    return aes_cbc_crypt(data, KEY, crypto_mode=2, decrypt=True)


@pytest.fixture(autouse=True)
def fixed_time(monkeypatch):
    clock = SimpleNamespace(time=lambda: 1700000000.125)
    monkeypatch.setattr(packets, "time", clock)
    monkeypatch.setattr(live_envelope, "time", clock)


def test_setup_is_talk_not_live_and_has_no_credentials():
    assert packets.setup_packet() == b"\xa9" + bytes(8) + b"\x02" + bytes(22)


@pytest.mark.parametrize(
    "channel,expected", [(1, 1), (2, 2), (0, 65535), (65535, 65535)]
)
def test_open_matches_native_zero_play_flag_and_header_body_hash(
    channel, expected
):
    wire = packets.open_packet(channel, "synthetic-password", KEY.encode())
    header, tail = decrypt(wire[:32]), decrypt(wire[32:])
    body = b"adminapp2&&synthetic-password\0\0"
    expected_header = bytearray(32)
    struct.pack_into(
        "<BQHHH",
        expected_header,
        0,
        0x0B,
        1700000000,
        len(tail),
        len(body),
        expected,
    )
    assert header == expected_header
    assert tail[: len(body)] == body
    assert (
        tail[len(body) : len(body) + 32]
        == hashlib.sha256(header + body).digest()
    )
    assert not any(tail[len(body) + 32 :])


@pytest.mark.parametrize("sending", [False, True])
@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("codec", [4, 5])
def test_request_channel_codec_rate_and_header_only_hash(
    sending, enabled, codec
):
    wire = packets.request_packet(
        2, sending=sending, enabled=enabled, codec=codec, key=KEY.encode()
    )
    expected = bytearray(32)
    struct.pack_into(
        "<BQHHB",
        expected,
        0,
        0x0C if sending else 0x0D,
        1700000000,
        32,
        2,
        enabled,
    )
    if sending:
        expected[14] = codec - 4
        struct.pack_into("<H", expected, 15, 8000)
    assert len(wire) == 64
    assert decrypt(wire[:32]) == expected
    assert decrypt(wire[32:]) == hashlib.sha256(expected).digest()


@pytest.mark.parametrize("codec,tag", [(4, 0x0E), (5, 0x0A)])
@pytest.mark.parametrize("full_packet", [False, True])
def test_audio_encrypts_only_first_32_body_bytes_and_has_no_digest(
    codec, tag, full_packet, monkeypatch
):
    value = datetime(2026, 10, 27, 12, 34, 56, 125000)
    monkeypatch.setattr(
        packets, "datetime", SimpleNamespace(fromtimestamp=lambda _: value)
    )
    encoded = bytes(range(256)) + bytes(range(64))
    wire = packets.audio_packet(
        encoded, codec=codec, full_packet=full_packet, key=KEY.encode()
    )
    header = decrypt(wire[:32])
    body = decrypt(wire[32:64]) + wire[64:]
    expected_header = bytearray(32)
    struct.pack_into(
        "<BQHI", expected_header, 0, 0xA2, 1700000000, 32, len(body)
    )
    assert header == expected_header
    if full_packet:
        stamp = (
            (26 << 26) | (10 << 22) | (27 << 17) | (12 << 12) | (34 << 6) | 56
        )
        prefix = struct.pack(
            "<4sIIHBBHH", b"\0\0\x01\xe3", 320, stamp, 125, codec, 1, 8000, 0
        )
    else:
        prefix = b"\0\0\x01\xf0" + bytes([tag, 2]) + b"\x40\x01"
    assert body == prefix + encoded
    assert len(wire) == 32 + len(prefix) + 320
    assert wire[64:] == body[32:]


@pytest.mark.parametrize("channel", [-1, 65536, True, "1"])
def test_invalid_channel_is_not_truncated(channel):
    with pytest.raises(ValueError, match="talk channel"):
        packets.open_packet(channel, "password", KEY.encode())


@pytest.mark.parametrize("size,codec", [(319, 4), (321, 5), (320, 9)])
def test_invalid_audio_is_rejected_before_encryption(size, codec):
    with pytest.raises(ValueError):
        packets.audio_packet(
            bytes(size), codec=codec, full_packet=False, key=KEY.encode()
        )
