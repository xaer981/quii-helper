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


@pytest.mark.parametrize("channel", [1, 2, 127, 255])
def test_channel_ability_query_matches_native_one_byte_channel(channel):
    packet = build_readonly_device_query(
        14, key=KEY, channel=channel, timestamp_seconds=1_700_000_000
    )
    header = aes_cbc_crypt(packet[:32], KEY, crypto_mode=2, decrypt=True)
    expected = bytearray(32)
    expected[0], expected[13] = 0xFE, 14
    struct.pack_into("<QHH", expected, 1, 1_700_000_000, 48, 1)
    assert header == bytes(expected)
    body = bytes([channel])
    assert aes_cbc_crypt(packet[32:], KEY, crypto_mode=2, decrypt=True) == (
        body + hashlib.sha256(header + body).digest() + bytes(15)
    )


@pytest.mark.parametrize(
    "channel", [None, True, False, 0, -1, 256, 65535, 1.0, "1"]
)
def test_channel_ability_query_rejects_missing_or_truncated_channel(channel):
    with pytest.raises(ValueError, match="channel"):
        build_readonly_device_query(14, key=KEY, channel=channel)


@pytest.mark.parametrize("command", [5, 6, 2])
def test_zero_body_queries_do_not_accept_channel_payloads(command):
    with pytest.raises(ValueError, match="only query 14"):
        build_readonly_device_query(command, key=KEY, channel=1)


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
            14,
            b"\x00\x02\x85",
            {
                "result": 0,
                "channel": 2,
                "stream_support": {"main": True, "sub": False, "third": True},
            },
        ),
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


@pytest.mark.parametrize(
    "command,minimum", [(5, 2), (6, 4), (2, 2), (8, 4), (14, 3)]
)
def test_short_declared_body_never_reads_sha_bytes_as_reply(command, minimum):
    for size in range(minimum):
        result = describe_transparent_reply(
            reply_header(command, size), b"\x00" * 48
        )
        assert result["decode_status"] == "malformed"
        assert "result" not in result and "fps_mode" not in result


@pytest.mark.parametrize("command", [5, 2, 14])
def test_error_reply_is_not_decoded_as_success(command):
    body = b"\xff\x01\x07" if command == 14 else b"\xff\x01"
    result = describe_transparent_reply(reply_header(command, len(body)), body)
    assert result["decode_status"] == "device_error"
    assert result["result"] == -1
    assert "version_byte" not in result and "fps_mode" not in result
    assert "stream_support" not in result


def test_invalid_fps_and_signed_channel_counts_do_not_invent_valid_profiles():
    result = describe_transparent_reply(reply_header(2, 2), b"\x00\xff")
    assert result["decode_status"] == "invalid_value"
    assert "fps_mode_name" not in result
    result = describe_transparent_reply(
        reply_header(6, 4), b"\x00\xff\x01\x00"
    )
    assert result["total_count"] == -1
    assert result["decode_status"] == "invalid_value"


def test_channel_flags_match_java_camera_and_cctv_mapping():
    # Four channels: availability, four lock bytes, then talk availability.
    body = b"\x00\x04\x02\x02\x21\xff\xff\xff\xff\x12"
    result = describe_transparent_reply(reply_header(6, len(body)), body)
    assert result["decode_status"] == "ok"
    assert result["channel_flags"] == [
        {"channel": 1, "enabled": True, "talk_enabled": False},
        {"channel": 2, "enabled": False, "talk_enabled": True},
        {"channel": 3, "enabled": False, "talk_enabled": True},
        {"channel": 4, "enabled": True, "talk_enabled": False},
    ]
    assert set(result) == {
        "command",
        "name",
        "payload_length",
        "decode_status",
        "total_count",
        "camera_count",
        "cctv_count",
        "channel_flags",
        "direct_switch_supported",
    }
    assert result["direct_switch_supported"] is None


def test_channel_flags_preserve_java_four_bit_stride_across_bitmap_bytes():
    body = b"\x00\x0a\x06\x04" + b"\x50\x02" + bytes(10) + b"\xa0\x04"
    result = describe_transparent_reply(reply_header(6, len(body)), body)
    channels = result["channel_flags"]
    assert [item["channel"] for item in channels] == list(range(1, 11))
    assert [item["channel"] for item in channels if item["enabled"]] == [
        6,
        9,
    ]
    assert [item["channel"] for item in channels if item["talk_enabled"]] == [
        7,
        10,
    ]


@pytest.mark.parametrize("size", range(11))
def test_channel_flags_never_read_missing_sections_from_sha_or_padding(size):
    body = b"\x00\x04\x02\x02\x33\xff\xff\xff\xff\x00"
    result = describe_transparent_reply(
        reply_header(6, size), body[:size] + b"\xff" * 48
    )
    if size < 4:
        assert result["decode_status"] == "malformed"
        assert "channel_flags" not in result
        return
    assert result["decode_status"] == "ok"
    assert result["channel_flags"] == [
        {
            "channel": channel,
            "enabled": True if size >= 5 else None,
            "talk_enabled": False if size >= 10 else None,
        }
        for channel in range(1, 5)
    ]


@pytest.mark.parametrize("size", [4, 5, 6, 16, 17, 18])
def test_partial_multibyte_bitmaps_are_unknown_not_partially_decoded(size):
    body = b"\x00\x0a\x06\x04" + b"\xff" * 14
    result = describe_transparent_reply(
        reply_header(6, size), body[:size] + b"\xff" * 48
    )
    assert len(result["channel_flags"]) == 10
    assert all(
        item["enabled"] is (True if size >= 6 else None)
        and item["talk_enabled"] is (True if size >= 18 else None)
        for item in result["channel_flags"]
    )


@pytest.mark.parametrize("counts", [(0, 0, 0), (127, 127, 0)])
def test_absent_channel_flags_are_bounded_by_signed_total(counts):
    body = bytes([0, *counts])
    result = describe_transparent_reply(reply_header(6, len(body)), body)
    assert result["decode_status"] == "ok"
    assert len(result["channel_flags"]) == counts[0]
    assert all(
        item["enabled"] is None and item["talk_enabled"] is None
        for item in result["channel_flags"]
    )


@pytest.mark.parametrize("offset", [1, 2, 3])
def test_negative_java_counts_do_not_produce_channel_flags(offset):
    body = bytearray(b"\x00\x04\x02\x02" + b"\xff" * 32)
    body[offset] = 0xFF
    result = describe_transparent_reply(reply_header(6, len(body)), body)
    assert result["decode_status"] == "invalid_value"
    assert "channel_flags" not in result
    assert "direct_switch_supported" not in result


@pytest.mark.parametrize("size", range(10, 15))
@pytest.mark.parametrize("ability", [0, 1, 128, 129])
def test_direct_channel_switch_requires_complete_capabilities_block(
    size, ability
):
    body = b"\x00\x04\x02\x02" + bytes(6) + bytes([ability, 0, 0, 0])
    result = describe_transparent_reply(
        reply_header(6, size), body[:size] + b"\xff" * 48
    )
    assert result["direct_switch_supported"] is (
        bool(ability & 1) if size >= 14 else None
    )


@pytest.mark.parametrize("mask", range(8))
def test_channel_ability_bits_report_support_not_quality_or_audio(mask):
    body = bytes([0, 1, mask])
    result = describe_transparent_reply(reply_header(14, 3), body)
    assert result["decode_status"] == "ok"
    assert result["stream_support"] == {
        "main": bool(mask & 1),
        "sub": bool(mask & 2),
        "third": bool(mask & 4),
    }
    assert set(result) == {
        "command",
        "name",
        "payload_length",
        "decode_status",
        "result",
        "channel",
        "stream_support",
    }


@pytest.mark.parametrize("command", [1, 3, 4, 7, 9, 16, 18, 0x77, 0xFF])
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
