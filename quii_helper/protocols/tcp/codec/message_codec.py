from dataclasses import dataclass

from quii_helper.media.frames.models import QuiiHeader
from quii_helper.protocols.quii.crypto import aes_cbc_crypt


@dataclass
class DecodedTcpHeader:
    header: QuiiHeader
    command_payload_size: int
    media_payload_size: int
    is_media: bool

    @property
    def read_size(self) -> int:
        return (
            self.media_payload_size
            if self.is_media
            else self.command_payload_size
        )


def decode_tcp_header(
    header_raw: bytes, *, crypto_mode: int, key: bytes
) -> DecodedTcpHeader:
    header = (
        _aes_crypt(header_raw, key=key, crypto_mode=crypto_mode, decrypt=True)
        if crypto_mode
        else header_raw
    )
    packet_type = header[0]
    command_payload_size = int.from_bytes(header[9:11], "little")
    raw_size = int.from_bytes(header[11:13], "little")
    media_payload_size = int.from_bytes(header[11:15], "little")
    parsed = QuiiHeader(
        packet_type=packet_type,
        payload_size=command_payload_size,
        raw_size=raw_size,
        flag13=header[13],
        flag14=header[14],
        flag15=header[15],
        flag16=header[16],
        flag17=header[17],
        raw=header,
    )
    return DecodedTcpHeader(
        header=parsed,
        command_payload_size=command_payload_size,
        media_payload_size=media_payload_size,
        is_media=packet_type in (0xA0, 0xA1, 0xA2, 0xA3),
    )


def decode_tcp_payload(
    decoded: DecodedTcpHeader,
    payload_raw: bytes,
    *,
    crypto_mode: int,
    key: bytes,
) -> bytes:
    if not payload_raw or not crypto_mode:
        return payload_raw
    if not decoded.is_media:
        return _aes_crypt(
            payload_raw, key=key, crypto_mode=crypto_mode, decrypt=True
        )

    command_part_len = min(decoded.command_payload_size, len(payload_raw))
    media_offset = min(
        int(decoded.header.flag16) | (int(decoded.header.flag17) << 8),
        len(payload_raw),
    )
    body = bytearray(payload_raw)
    if command_part_len:
        command_part = _aes_crypt(
            payload_raw[:command_part_len],
            key=key,
            crypto_mode=crypto_mode,
            decrypt=True,
        )
        body[: len(command_part)] = command_part
    return bytes(body[media_offset:])


def _aes_crypt(
    data: bytes, *, key: bytes, crypto_mode: int, decrypt: bool
) -> bytes:
    if not key:
        return data
    return aes_cbc_crypt(data, key, crypto_mode=crypto_mode, decrypt=decrypt)
