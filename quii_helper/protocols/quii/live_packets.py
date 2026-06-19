from quii_helper.protocols.quii.live_bodies import (
    build_live_oem_body,
    build_live_path_body,
)
from quii_helper.protocols.quii.live_envelope import (
    build_live_play_packet_from_body,
    build_live_setup_packet,
)


def build_live_keepalive_packet(
    *,
    timestamp_ms: int | None = None,
    crypto_mode: int = 0,
    sha_mode: int = 1,
    key: bytes | str | None = None,
    encrypt: bool = False,
) -> tuple[bytes, bytes, bytes]:
    """
    Reimplementation of CQUIIStreamBase::SendKeepAlive.

    Native sends packet type 0 with an empty command body and the same
    SHA/padding/encryption envelope used by live play packets.
    """
    return build_live_play_packet_from_body(
        b"",
        timestamp_ms=timestamp_ms,
        packet_type=0x00,
        crypto_mode=crypto_mode,
        sha_mode=sha_mode,
        key=key,
        encrypt=encrypt,
    )


def build_live_play_packet(
    username: str,
    password: str,
    path: str,
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
    """
    Reimplementation of CQUIIStreamLive::OnSendPlay / SendFastPlay
    payload builder.

    Returns:
    - header (plain 32-byte header)
    - body_without_sha
    - full packet (plain or encrypted depending on `encrypt`)
    """
    return build_live_play_packet_from_body(
        build_live_path_body(username, password, path),
        timestamp_ms=timestamp_ms,
        ext_len_low=ext_len_low,
        ext_len_high=ext_len_high,
        play_param=play_param,
        stream_flag=stream_flag,
        inner=inner,
        packet_type=packet_type,
        crypto_mode=crypto_mode,
        sha_mode=sha_mode,
        key=key,
        encrypt=encrypt,
    )


def build_live_play_oem_packet(
    username: str,
    password: str,
    oem: str,
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
    """
    Build the app-observed live play packet body:
      username&&password\0OEM\0
    """
    return build_live_play_packet_from_body(
        build_live_oem_body(username, password, oem),
        timestamp_ms=timestamp_ms,
        ext_len_low=ext_len_low,
        ext_len_high=ext_len_high,
        play_param=play_param,
        stream_flag=stream_flag,
        inner=inner,
        packet_type=packet_type,
        crypto_mode=crypto_mode,
        sha_mode=sha_mode,
        key=key,
        encrypt=encrypt,
    )


def build_live_fastplay_packet(
    username: str,
    password: str,
    path: str,
    *,
    timestamp_ms: int | None = None,
    ext_len_low: int = 0,
    ext_len_high: int = 0,
    stream_flag: int = 0,
    inner: bool = False,
    crypto_mode: int = 2,
    sha_mode: int = 1,
    key: bytes | str | None = None,
    encrypt: bool = False,
) -> tuple[bytes, bytes, bytes]:
    return build_live_play_packet(
        username,
        password,
        path,
        timestamp_ms=timestamp_ms,
        ext_len_low=ext_len_low,
        ext_len_high=ext_len_high,
        play_param=1,
        stream_flag=stream_flag,
        inner=inner,
        packet_type=0xAA,
        crypto_mode=crypto_mode,
        sha_mode=sha_mode,
        key=key,
        encrypt=encrypt,
    )


__all__ = [
    "build_live_fastplay_packet",
    "build_live_keepalive_packet",
    "build_live_play_oem_packet",
    "build_live_play_packet",
    "build_live_play_packet_from_body",
    "build_live_setup_packet",
]
