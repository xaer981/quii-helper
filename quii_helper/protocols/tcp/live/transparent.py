"""Native transparent commands: read-only queries and payload-safe diagnostics."""

from typing import Any

from quii_helper.media.frames.models import QuiiHeader
from quii_helper.protocols.quii.live_envelope import (
    build_live_play_packet_from_body,
)

READONLY_DEVICE_QUERIES = (5, 6, 2)
COMMAND_NAMES = {
    1: "HANG_UP",
    2: "FPS_GET",
    3: "FPS_SET",
    4: "UNLOCK",
    5: "VERSION_GET",
    6: "CHANNELS_GET",
    7: "OSD_INFO",
    8: "OSD_TIMESTAMP",
    9: "CHANNEL_SWITCH",
    14: "GET_CHANNEL_ABILITY",
    16: "GET_ATTACHMENT_INFO",
    18: "GET_ATTACHMENT_INFO_JSON",
}


def build_readonly_device_query(
    command: int, *, key: bytes, timestamp_seconds: int | None = None
) -> bytes:
    """Encode only native VERSION_GET, CHANNELS_GET or FPS_GET, each with 00.

    No arbitrary payload or write command can be supplied. vEye Pro JNI
    transparentEx uses no inline parameters; the command occupies header[13].
    """
    if (
        isinstance(command, bool)
        or not isinstance(command, int)
        or command not in READONLY_DEVICE_QUERIES
    ):
        raise ValueError(
            "only read-only device queries 5, 6 and 2 are allowed"
        )
    _, _, packet = build_live_play_packet_from_body(
        b"\x00",
        timestamp_ms=timestamp_seconds,
        packet_type=0xFE,
        ext_len_low=command,
        play_param=0,
        crypto_mode=2,
        sha_mode=1,
        key=key,
        encrypt=True,
    )
    return packet


def describe_transparent_reply(
    header: QuiiHeader, payload: bytes
) -> dict[str, Any]:
    """Summarize an authenticated FE reply without exposing arbitrary bytes.

    The caller must verify the command SHA first. Only the declared raw body,
    never SHA/padding, is parsed. Unknown commands retain just ID and length;
    attachment names, identifiers, strings and raw dumps are never returned.
    This is diagnostic metadata, not proof of a correlated request/reply.
    """
    if header.packet_type != 0xFE:
        raise ValueError("expected a transparent 0xFE command")
    command, size = header.flag13, header.raw_size
    result: dict[str, Any] = {
        "command": command,
        "name": COMMAND_NAMES.get(command, "UNKNOWN"),
        "payload_length": size,
        "decode_status": "unparsed",
    }
    if not 0 <= size <= min(len(payload), 0xFFFF):
        result["decode_status"] = "malformed"
        return result
    minimum = {2: 2, 5: 2, 6: 4, 8: 4}.get(command)
    if minimum is None:
        return result
    if size < minimum:
        result["decode_status"] = "malformed"
        return result
    result["decode_status"] = "ok"
    if command in (2, 5):
        result["result"] = int.from_bytes(payload[:1], "little", signed=True)
        if result["result"] != 0:
            result["decode_status"] = "device_error"
        elif command == 5:
            result["version_byte"] = payload[1]
        else:
            mode = payload[1]
            result["fps_mode"] = mode
            if mode in (0, 1, 2):
                result["fps_mode_name"] = ("high", "low", "picture")[mode]
            else:
                result["decode_status"] = "invalid_value"
    elif command == 6:
        # QvDeviceChannelsInfo reads these as signed Java bytes, not an XML model.
        for name, offset in (("total", 1), ("camera", 2), ("cctv", 3)):
            value = int.from_bytes(
                payload[offset : offset + 1], "little", signed=True
            )
            result[name + "_count"] = value
            if value < 0:
                result["decode_status"] = "invalid_value"
    elif command == 8:
        result["osd_timestamp_seconds"] = int.from_bytes(payload[:4], "little")
    return result
