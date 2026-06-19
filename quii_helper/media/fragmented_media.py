from quii_helper.media.cpacket_constants import (
    CPACKET_HEADER_LEN,
    CPACKET_START_PREFIX,
    CPACKET_START_TYPE_MAX,
    CPACKET_START_TYPE_MIN,
)
from quii_helper.protocols.quii.blob import decode_quii_blob

FRAGMENTED_MEDIA_MAX_BODY_LEN = 2 * 1024 * 1024
FRAGMENTED_MEDIA_SOURCES = {
    "wrapped_quii",
    "wrapped_quii_fragmented_remainder",
}


def cframe_total_len(payload: bytes) -> int:
    if len(payload) < CPACKET_HEADER_LEN:
        return 0
    if payload[:3] != CPACKET_START_PREFIX:
        return 0
    if not (CPACKET_START_TYPE_MIN <= payload[3] <= CPACKET_START_TYPE_MAX):
        return 0
    frame_len = int.from_bytes(payload[4:8], "little")
    total_len = frame_len + CPACKET_HEADER_LEN
    if frame_len <= 0 or total_len > FRAGMENTED_MEDIA_MAX_BODY_LEN:
        return 0
    return total_len


def should_start_fragmented_media(decoded: dict, source: str) -> bool:
    if source not in FRAGMENTED_MEDIA_SOURCES:
        return False
    if not decoded.get("is_media"):
        return False
    expected_body_len = int(decoded.get("read_size", 0))
    body = decoded.get("payload_raw", b"")
    payload = decoded.get("payload", b"")
    if (
        expected_body_len <= len(body)
        or expected_body_len > FRAGMENTED_MEDIA_MAX_BODY_LEN
    ):
        return False
    return cframe_total_len(payload) == expected_body_len


def start_fragmented_media(
    decoded: dict, *, source: str, meta: dict, message_index: int
) -> dict:
    header = decoded["header"]
    payload = decoded["payload"]
    expected_body_len = int(decoded["read_size"])
    return {
        "header_raw": decoded["header_raw"],
        "body": bytearray(decoded["payload_raw"]),
        "expected_body_len": expected_body_len,
        "start_msg_index": message_index,
        "source": source,
        "meta": meta,
        "packet_type": header.packet_type,
        "payload_size": header.payload_size,
        "raw_size": header.raw_size,
        "flag15": header.flag15,
        "frame_tag": payload[3],
        "frame_len": int.from_bytes(payload[4:8], "little"),
        "fragments": 1,
    }


def append_fragmented_media(
    state: dict,
    blob: bytes,
    key: str,
    *,
    source: str,
    meta: dict,
    message_index: int,
) -> tuple[dict | None, bytes, dict]:
    body = state["body"]
    expected_body_len = int(state["expected_body_len"])
    remaining = max(0, expected_body_len - len(body))
    take = min(remaining, len(blob))
    if take:
        body.extend(blob[:take])
        state["fragments"] = int(state.get("fragments", 0)) + 1
    complete = len(body) >= expected_body_len
    summary = {
        "msg_index": message_index,
        "source": source,
        "blob_len": len(blob),
        "fragmented_media": "complete" if complete else "append",
        "start_msg_index": state.get("start_msg_index"),
        "fragments": state.get("fragments"),
        "expected_body_len": expected_body_len,
        "have_body_len": len(body),
        "taken_len": take,
        "remainder_len": max(0, len(blob) - take),
        "packet_type": hex(int(state.get("packet_type", 0))),
        "raw_size": state.get("raw_size"),
        "frame_tag": hex(int(state.get("frame_tag", 0))),
        "frame_len": state.get("frame_len"),
    }
    if meta:
        summary["meta"] = meta
    if not complete:
        return None, b"", summary

    full_blob = bytes(state["header_raw"]) + bytes(body[:expected_body_len])
    decoded = decode_quii_blob(full_blob, key, crypto_mode=2)
    decoded["fragmented_media"] = {
        "start_msg_index": state.get("start_msg_index"),
        "end_msg_index": message_index,
        "fragments": state.get("fragments"),
        "expected_body_len": expected_body_len,
    }
    return decoded, blob[take:], summary
