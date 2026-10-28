"""CQUIITalk wire layouts verified against vHome and vEye Pro native."""

import hashlib
import struct
import time
from datetime import datetime

from quii_helper.protocols.quii.crypto import aes_cbc_crypt
from quii_helper.protocols.quii.live_envelope import (
    build_live_play_packet_from_body,
)

SAMPLES_PER_FRAME = 320
PCM_FRAME_BYTES = SAMPLES_PER_FRAME * 2
FRAME_SECONDS = SAMPLES_PER_FRAME / 8000


def talk_channel(value: int) -> int:
    """Validate a selector; native ParseURL maps generic channel 0 to 65535."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("talk channel must be an integer between 0 and 65535")
    if not 0 <= value <= 65535:
        raise ValueError("talk channel must be between 0 and 65535")
    return value or 65535


def setup_packet() -> bytes:
    """Build unencrypted SendSetup, distinguished from live by byte 9."""
    header = bytearray(32)
    header[0], header[9] = 0xA9, 2
    return bytes(header)


def open_packet(channel: int, password: str, key: bytes) -> bytes:
    """Build SendOpen with empty custom/client ids and no live-play flags."""
    channel = talk_channel(channel)
    body = b"adminapp2&&" + password.encode("utf-8") + b"\x00\x00"
    return build_live_play_packet_from_body(
        body,
        packet_type=0x0B,
        ext_len_low=channel & 255,
        ext_len_high=channel >> 8,
        play_param=0,
        crypto_mode=2,
        key=key,
        encrypt=True,
    )[2]


def request_packet(
    channel: int, *, sending: bool, enabled: bool, codec: int, key: bytes
) -> bytes:
    """Build native OnSendRequest: 0x0C sends, 0x0D requests incoming audio."""
    channel = talk_channel(channel)
    if codec not in (4, 5):
        raise ValueError("unsupported LAN talk codec")
    header = bytearray(32)
    header[0] = 0x0C if sending else 0x0D
    struct.pack_into(
        "<QHHB", header, 1, int(time.time()), 32, channel, enabled
    )
    if sending:
        header[14] = codec - 4
        struct.pack_into("<H", header, 15, 8000)
    # Request channel overlaps live's body-length field: hash this header, not play.
    return aes_cbc_crypt(bytes(header), key, crypto_mode=2) + aes_cbc_crypt(
        hashlib.sha256(header).digest(), key, crypto_mode=2
    )


def audio_packet(
    encoded: bytes, *, codec: int, full_packet: bool, key: bytes
) -> bytes:
    """Build paced 40ms OnSendData in the negotiated compact/CPacket dialect."""
    if len(encoded) != SAMPLES_PER_FRAME or codec not in (4, 5):
        raise ValueError("LAN talk requires 320 encoded G.711 samples")
    now = time.time()
    if full_packet:
        value = datetime.fromtimestamp(now)
        if not 2000 <= value.year <= 2063:
            raise ValueError("CPacket time is outside the native year range")
        stamp = (
            ((value.year - 2000) << 26)
            | (value.month << 22)
            | (value.day << 17)
            | (value.hour << 12)
            | (value.minute << 6)
            | value.second
        )
        body = (
            struct.pack(
                "<4sIIHBBHH",
                b"\x00\x00\x01\xe3",
                len(encoded),
                stamp,
                value.microsecond // 1000,
                codec,
                1,
                8000,
                0,
            )
            + encoded
        )
    else:
        body = (
            struct.pack(
                "<IBBH",
                0xF0010000,
                0x0E if codec == 4 else 0x0A,
                2,
                len(encoded),
            )
            + encoded
        )
    header = bytearray(32)
    header[0] = 0xA2
    struct.pack_into("<QHI", header, 1, int(now), 32, len(body))
    return (
        aes_cbc_crypt(bytes(header), key, crypto_mode=2)
        + aes_cbc_crypt(body[:32], key, crypto_mode=2)
        + body[32:]
    )
