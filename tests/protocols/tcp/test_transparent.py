"""Native-layout transparent packets with synthetic keys and bodies only."""

import hashlib
import json
import struct
from dataclasses import replace

import pytest

from quii_helper.protocols.quii.crypto import aes_cbc_crypt
from quii_helper.protocols.tcp.codec.message_codec import decode_tcp_header
from quii_helper.protocols.tcp.live.transparent import (
    build_readonly_device_query,
    describe_transparent_reply,
)

KEY = b"K" * 32


def reply_header(command, size):
    raw = bytearray(32)
    raw[0], raw[13] = 0xFE, command
    struct.pack_into("<HH", raw, 9, (size + 47) // 16 * 16, size)
    return decode_tcp_header(bytes(raw), crypto_mode=0, key=b"").header


@pytest.mark.parametrize("command", [5, 6, 2])
def test_readonly_query_matches_native_transparentex_layout(command):
    packet = build_readonly_device_query(
        command, key=KEY, timestamp_seconds=1_700_000_000
    )
    header = aes_cbc_crypt(packet[:32], KEY, crypto_mode=2, decrypt=True)
    expected = bytearray(32)
    expected[0], expected[13] = 0xFE, command
    struct.pack_into("<QHH", expected, 1, 1_700_000_000, 48, 1)
    assert header == bytes(expected)
    body = aes_cbc_crypt(packet[32:], KEY, crypto_mode=2, decrypt=True)
    assert len(packet) == 80
    assert body == (
        b"\x00" + hashlib.sha256(header + b"\x00").digest() + bytes(15)
    )


@pytest.mark.parametrize(
    "command",
    [True, False, -1, 0, 1, 3, 4, 8, 9, 15, 255, 256, 2.0, "5", None],
)
def test_builder_cannot_send_fps_set_unlock_or_arbitrary_commands(command):
    with pytest.raises(ValueError, match="read-only"):
        build_readonly_device_query(command, key=KEY)


@pytest.mark.parametrize(
    "command,body,fields",
    [
        (5, b"\x00\x01", {"version_byte": 1, "result": 0}),
        (
            6,
            b"\x00\x04\x02\x02",
            {"total_count": 4, "camera_count": 2, "cctv_count": 2},
        ),
        (
            8,
            struct.pack("<I", 1_700_000_000),
            {"osd_timestamp_seconds": 1_700_000_000},
        ),
        (
            2,
            b"\x00\x00",
            {"fps_mode": 0, "fps_mode_name": "high", "result": 0},
        ),
        (2, b"\x00\x01", {"fps_mode": 1, "fps_mode_name": "low", "result": 0}),
        (
            2,
            b"\x00\x02",
            {"fps_mode": 2, "fps_mode_name": "picture", "result": 0},
        ),
    ],
)
def test_known_reply_fields_ignore_trailing_sha_padding_and_private_data(
    command, body, fields
):
    result = describe_transparent_reply(
        reply_header(command, len(body)), body + b"private-trailing-data"
    )
    assert result["decode_status"] == "ok"
    assert result["payload_length"] == len(body)
    assert all(result[name] == value for name, value in fields.items())
    assert "private" not in json.dumps(result)


@pytest.mark.parametrize("command,minimum", [(5, 2), (6, 4), (2, 2), (8, 4)])
def test_short_declared_body_never_reads_sha_bytes_as_reply(command, minimum):
    for size in range(minimum):
        result = describe_transparent_reply(
            reply_header(command, size), b"\x00" * 48
        )
        assert result["decode_status"] == "malformed"
        assert "result" not in result and "fps_mode" not in result


@pytest.mark.parametrize("command", [5, 2])
def test_error_reply_is_not_decoded_as_success(command):
    result = describe_transparent_reply(reply_header(command, 2), b"\xff\x01")
    assert result["decode_status"] == "device_error"
    assert result["result"] == -1
    assert "version_byte" not in result and "fps_mode" not in result


def test_invalid_fps_and_signed_channel_counts_do_not_invent_valid_profiles():
    result = describe_transparent_reply(reply_header(2, 2), b"\x00\xff")
    assert result["decode_status"] == "invalid_value"
    assert "fps_mode_name" not in result
    result = describe_transparent_reply(
        reply_header(6, 4), b"\x00\xff\x01\x00"
    )
    assert result["total_count"] == -1
    assert result["decode_status"] == "invalid_value"


@pytest.mark.parametrize("command", [1, 3, 4, 7, 9, 14, 16, 18, 0x77, 0xFF])
def test_unparsed_replies_expose_no_body_or_inline_header_values(command):
    secret = b"private-name-auth-key-location"
    result = describe_transparent_reply(
        reply_header(command, len(secret)), secret
    )
    assert set(result) == {
        "command",
        "name",
        "payload_length",
        "decode_status",
    }
    assert result["decode_status"] == "unparsed"
    assert "private" not in json.dumps(result)


def test_invalid_reply_bounds_and_wrong_packet_type():
    header = reply_header(5, 2)
    assert (
        describe_transparent_reply(header, b"\x00")["decode_status"]
        == "malformed"
    )
    for size in (-1, 0x10000):
        assert (
            describe_transparent_reply(replace(header, raw_size=size), b"")[
                "decode_status"
            ]
            == "malformed"
        )
    with pytest.raises(ValueError, match="0xFE"):
        describe_transparent_reply(replace(header, packet_type=9), b"")
