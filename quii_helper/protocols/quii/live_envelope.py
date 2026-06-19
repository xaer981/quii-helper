import struct
import time

from quii_helper.protocols.quii.crypto import (
    aes_cbc_crypt,
    compute_ext_data_len,
    sha_bytes,
)


def build_live_setup_packet() -> bytes:
    packet = bytearray(32)
    packet[0] = 0xA9
    return bytes(packet)


def build_live_play_packet_from_body(
    body: bytes,
    *,
    timestamp_ms: int | None = None,
    ext_len_low: int = 0,
    ext_len_high: int = 0,
    play_param: int = 1,
    stream_flag: int = 0,
    inner: bool = False,
    packet_type: int = 0x01,
    crypto_mode: int = 0,
    sha_mode: int = 1,
    key: bytes | str | None = None,
    encrypt: bool = False,
) -> tuple[bytes, bytes, bytes]:
    # App packets use Unix time in seconds here, not milliseconds.
    timestamp_ms = int(time.time()) if timestamp_ms is None else timestamp_ms
    raw_len = len(body)
    _ext_len, padded_len = compute_ext_data_len(
        raw_len, crypto_mode=crypto_mode, sha_mode=sha_mode, include_sha=True
    )

    header = bytearray(32)
    header[0] = packet_type & 0xFF
    header[1:9] = struct.pack("<Q", timestamp_ms)
    header[9:11] = struct.pack("<H", padded_len)
    header[11:13] = struct.pack("<H", raw_len)
    header[0x0D] = ext_len_low & 0xFF
    header[0x0E] = ext_len_high & 0xFF
    header[0x0F] = play_param & 0xFF
    header[0x10] = stream_flag & 0xFF
    if inner:
        header[0x11] = 1

    trailer = sha_bytes(bytes(header) + body, sha_mode=sha_mode)
    plain = bytes(header) + body + trailer

    if encrypt and crypto_mode != 0:
        if key is None:
            raise ValueError(
                "key is required when encrypt=True and crypto_mode != 0"
            )

        body_plus_sha = body + trailer
        if len(body_plus_sha) < padded_len:
            body_plus_sha += b"\x00" * (padded_len - len(body_plus_sha))
        encrypted_header = aes_cbc_crypt(
            bytes(header), key, crypto_mode=crypto_mode, decrypt=False
        )
        encrypted_body = aes_cbc_crypt(
            body_plus_sha, key, crypto_mode=crypto_mode, decrypt=False
        )
        return bytes(header), body, encrypted_header + encrypted_body

    return bytes(header), body, plain
