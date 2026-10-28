import re
import struct
import time
from dataclasses import dataclass

from quii_helper.protocols.quii.crypto import aes_cbc_crypt, sha_bytes
from quii_helper.protocols.quii.live_bodies import build_live_credentials_body
from quii_helper.protocols.quii.live_envelope import (
    build_live_play_packet_from_body,
)


def validate_live_identity(custom_id: str | None, client_id: str) -> None:
    """Bound opt-in native metadata; never allow embedded field separators."""
    if not isinstance(client_id, str):
        raise ValueError("client_id must be a string")
    if custom_id is None:
        if client_id:
            raise ValueError("client_id requires an explicit custom_id")
        return
    if not isinstance(custom_id, str) or not custom_id.strip():
        raise ValueError("custom_id must be a nonempty string")
    for name, value in (("custom_id", custom_id), ("client_id", client_id)):
        if "\x00" in value or len(value.encode("utf-8")) > 256:
            raise ValueError(
                f"{name} must contain at most 256 bytes and no NUL"
            )


def build_stream_switch_packet(
    stream: int, *, key: bytes, timestamp_seconds: int | None = None
) -> bytes:
    """Encode native SendSwitchStream for the LAN AES-256/SHA256 profile.

    Args:
        stream: One-based selector (1-256); actual profiles are device-specific.
        key: The existing session's command encryption key.
        timestamp_seconds: Unix seconds; defaults to the current time.
    """
    if isinstance(stream, bool) or not isinstance(stream, int):
        raise ValueError("stream must be an integer between 1 and 256")
    if not 1 <= stream <= 256:
        raise ValueError("stream must be an integer between 1 and 256")
    header = bytearray(32)
    header[0] = 9
    struct.pack_into(
        "<QH",
        header,
        1,
        int(time.time()) if timestamp_seconds is None else timestamp_seconds,
        32,
    )
    # Unlike play, native switch stores its selector at byte 11, not byte 16.
    header[11] = stream - 1
    plain = bytes(header)
    return aes_cbc_crypt(plain, key, crypto_mode=2) + aes_cbc_crypt(
        sha_bytes(plain), key, crypto_mode=2
    )


@dataclass
class QuiiLiveOpenPacketBuilder:
    username: str
    password: str
    path: str
    key: str
    use_inner: bool = False

    def build_live_open_packet(
        self,
        *,
        crypto_mode: int,
        play_param: int = 1,
        stream_flag: int | None = None,
        timestamp_ms: int | None = None,
        custom_id: str | None = None,
        client_id: str = "",
        fast_play: bool = False,
    ) -> bytes:
        """Keep the path-body default; native identities/FastPlay are opt-in."""
        validate_live_identity(custom_id, client_id)
        if fast_play and (
            crypto_mode != 2 or play_param != 1 or custom_id is None
        ):
            raise ValueError(
                "FastPlay requires AES-256, play_param=1 and custom_id"
            )
        selectors = re.search(
            r"(?:^|[/?&])idc=([0-9]+)&ids=([0-9]+)(?:&|$)", self.path
        )
        if selectors is None:
            raise ValueError(
                "live path requires numeric idc and ids selectors"
            )
        channel, stream = map(int, selectors.groups())
        if not 0 <= channel <= 0xFFFF or not 1 <= stream <= 0x100:
            raise ValueError("channel or stream exceeds live header range")
        if stream_flag is None:
            stream_flag = stream - 1
        if (
            isinstance(stream_flag, bool)
            or not isinstance(stream_flag, int)
            or not 0 <= stream_flag <= 0xFF
        ):
            raise ValueError("stream_flag must be a byte-sized stream index")
        body = build_live_credentials_body(
            self.username,
            self.password,
            self.path if custom_id is None else custom_id,
        )
        if client_id:
            body += client_id.encode("utf-8") + b"\x00"
        header, _body, packet = build_live_play_packet_from_body(
            body,
            timestamp_ms=(
                int(time.time()) if timestamp_ms is None else timestamp_ms
            ),
            play_param=play_param,
            # Native ParseURL/OnSendPlay copies idc and zero-based ids here.
            ext_len_low=channel & 0xFF,
            ext_len_high=channel >> 8,
            stream_flag=stream_flag,
            inner=self.use_inner,
            packet_type=0xAA if fast_play else 1,
            crypto_mode=crypto_mode,
            sha_mode=1,
            key=self.key_bytes(crypto_mode) if crypto_mode else None,
            encrypt=crypto_mode != 0,
        )
        # Native SendFastPlay leaves only the header unencrypted.
        return header + packet[32:] if fast_play else packet

    def key_bytes(self, crypto_mode: int) -> bytes:
        if crypto_mode == 1:
            return self.key.encode("utf-8")[:16].ljust(16, b"\x00")
        if crypto_mode == 2:
            return self.key.encode("utf-8")[:32].ljust(32, b"\x00")
        return b""
