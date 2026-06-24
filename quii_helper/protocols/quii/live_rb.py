from quii_helper.protocols.quii.live_packets import (
    build_live_keepalive_packet,
    build_live_play_oem_packet,
    build_live_play_packet,
    build_live_setup_packet,
)
from quii_helper.protocols.rbudp.kcp.link_packets import build_rb_data_packet


def build_direct_quii_setup_rb(
    *, src_id: int, dest_id: int, seq: int
) -> bytes:
    """
    Wrap the 32-byte QUII live setup packet into a direct RB data frame.
    """
    return build_rb_data_packet(
        payload=build_live_setup_packet(),
        src_id=src_id,
        dest_id=dest_id,
        seq=seq,
    )


def build_direct_quii_keepalive_rb(
    *,
    src_id: int,
    dest_id: int,
    seq: int,
    timestamp_ms: int | None = None,
    crypto_mode: int = 0,
    sha_mode: int = 1,
    key: bytes | str | None = None,
    encrypt: bool = False,
) -> bytes:
    """
    Build a direct KCP/RB tunnel packet carrying QUII live keepalive.
    """
    _header, _body, payload = build_live_keepalive_packet(
        timestamp_ms=timestamp_ms,
        crypto_mode=crypto_mode,
        sha_mode=sha_mode,
        key=key,
        encrypt=encrypt,
    )
    return build_rb_data_packet(
        payload=payload, src_id=src_id, dest_id=dest_id, seq=seq
    )


def build_direct_quii_play_rb(
    username: str,
    password: str,
    path: str,
    *,
    src_id: int,
    dest_id: int,
    seq: int,
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
) -> bytes:
    """
    Build a direct KCP/RB tunnel packet carrying the QUII play/open message.
    """
    _header, _body, payload = build_live_play_packet(
        username,
        password,
        path,
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
    return build_rb_data_packet(
        payload=payload, src_id=src_id, dest_id=dest_id, seq=seq
    )


def build_direct_quii_play_oem_rb(
    username: str,
    password: str,
    oem: str,
    *,
    src_id: int,
    dest_id: int,
    seq: int,
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
) -> bytes:
    """
    Build the app-observed encrypted QUII play packet body:
      username&&dynamic_password\0OEM\0
    """
    _header, _body, payload = build_live_play_oem_packet(
        username,
        password,
        oem,
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
    return build_rb_data_packet(
        payload=payload, src_id=src_id, dest_id=dest_id, seq=seq
    )
