from collections.abc import Sequence


def build_native_play_profile(
    *,
    channel: int,
    stream: int,
    inner: bool,
) -> dict[str, int]:
    channel_id = max(0, int(channel)) & 0xFFFF
    stream_flag = max(0, int(stream) - 1) & 0xFF
    return {
        "channel_id": channel_id,
        "packet_type": 0x01,
        "ext_len_low": channel_id & 0xFF,
        "ext_len_high": (channel_id >> 8) & 0xFF,
        "play_param": 0x01,
        "stream_flag": stream_flag,
        "inner": int(bool(inner)),
    }


def normalize_live_play_payload(play_payload: object) -> str:
    normalized = str(play_payload).lower()
    if normalized not in {"path", "oem"}:
        raise ValueError("live_play_payload must be 'path' or 'oem'")
    return normalized


def build_quii_play_common_args(
    *,
    src_id: int,
    dest_id: int,
    seq: int,
    profile: dict[str, int],
    data_encode_key: bytes | str,
) -> dict[str, object]:
    return {
        "src_id": src_id,
        "dest_id": dest_id,
        "seq": seq,
        "packet_type": int(profile["packet_type"]),
        "ext_len_low": int(profile["ext_len_low"]),
        "ext_len_high": int(profile["ext_len_high"]),
        "play_param": int(profile["play_param"]),
        "stream_flag": int(profile["stream_flag"]),
        "inner": bool(profile.get("inner", 0)),
        "crypto_mode": 2,
        "key": data_encode_key,
        "encrypt": True,
    }


def select_live_command_lane_destinations(
    pairs: Sequence[tuple[dict, int]],
    *,
    active_src_id: int,
) -> list[tuple[dict, int]]:
    active_pairs = [
        (lane, dest_id)
        for lane, dest_id in pairs
        if int(lane["src_id"]) == int(active_src_id)
    ]
    return active_pairs or list(pairs[:1])
