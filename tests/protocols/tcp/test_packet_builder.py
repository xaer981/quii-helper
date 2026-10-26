"""Native ParseURL/OnSendPlay selector mapping, without camera traffic."""

import pytest

from quii_helper.protocols.tcp.codec.message_codec import decode_tcp_header
from quii_helper.protocols.tcp.live.packet_builder import (
    QuiiLiveOpenPacketBuilder,
)


@pytest.mark.parametrize("crypto_mode", [0, 1, 2])
@pytest.mark.parametrize(
    "channel,stream", [(0, 1), (1, 3), (2, 2), (258, 256)]
)
def test_selectors_are_encoded_in_clear_and_encrypted_headers(
    crypto_mode, channel, stream
):
    builder = QuiiLiveOpenPacketBuilder(
        "synthetic",
        "password",
        f"/mode=real&idc={channel}&ids={stream}&ap=2",
        "K" * 32,
    )
    packet = builder.build_live_open_packet(crypto_mode=crypto_mode)
    header = decode_tcp_header(
        packet[:32],
        crypto_mode=crypto_mode,
        key=builder.key_bytes(crypto_mode),
    ).header
    assert header.flag13 | (header.flag14 << 8) == channel
    assert header.flag16 == stream - 1


def test_explicit_stream_flag_override_is_preserved():
    builder = QuiiLiveOpenPacketBuilder(
        "synthetic", "password", "/mode=real&idc=2&ids=3&ap=2", ""
    )
    header = builder.build_live_open_packet(crypto_mode=0, stream_flag=0)
    assert header[13:17] == b"\x02\x00\x01\x00"


@pytest.mark.parametrize(
    "path",
    [
        "/mode=real",
        "/mode=real&idc=2",
        "/mode=real&idc=-1&ids=1",
        "/mode=real&idc=65536&ids=1",
        "/mode=real&idc=1&ids=0",
        "/mode=real&idc=1&ids=257",
        "/mode=real&idc=1&ids=1junk",
    ],
)
def test_invalid_selectors_are_not_silently_truncated(path):
    builder = QuiiLiveOpenPacketBuilder("synthetic", "password", path, "")
    with pytest.raises(ValueError):
        builder.build_live_open_packet(crypto_mode=0)


@pytest.mark.parametrize("stream_flag", [-1, 256, True, 1.5])
def test_invalid_explicit_stream_flag_is_rejected(stream_flag):
    builder = QuiiLiveOpenPacketBuilder(
        "synthetic", "password", "/mode=real&idc=1&ids=1", ""
    )
    with pytest.raises(ValueError, match="stream_flag"):
        builder.build_live_open_packet(crypto_mode=0, stream_flag=stream_flag)
