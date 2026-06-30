from __future__ import annotations

from typing import Any

FragmentedMediaState = dict[str, Any]
DecodedMediaBlob = dict[str, Any]
DiagnosticMeta = dict[str, Any]


def fragmented_media_lengths(
    decoded: DecodedMediaBlob,
) -> tuple[int, int, int]:
    expected_body_len = int(decoded.get("read_size", 0))
    media_payload_offset = int(decoded.get("media_payload_offset", 0))
    expected_media_len = max(0, expected_body_len - media_payload_offset)
    body_len = len(decoded.get("payload_raw", b""))
    return expected_body_len, expected_media_len, body_len


def build_fragmented_media_state(
    decoded: DecodedMediaBlob,
    *,
    source: str,
    meta: DiagnosticMeta,
    message_index: int,
) -> FragmentedMediaState:
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
        "media_payload_offset": decoded.get("media_payload_offset", 0),
        "frame_tag": payload[3],
        "frame_len": int.from_bytes(payload[4:8], "little"),
        "fragments": 1,
    }


def append_fragmented_media_body(
    state: FragmentedMediaState, blob: bytes
) -> tuple[int, bool, int]:
    body = state["body"]
    expected_body_len = int(state["expected_body_len"])
    remaining = max(0, expected_body_len - len(body))
    take = min(remaining, len(blob))
    if take:
        body.extend(blob[:take])
        state["fragments"] = int(state.get("fragments", 0)) + 1
    complete = len(body) >= expected_body_len
    return take, complete, expected_body_len


def fragmented_media_append_summary(
    state: FragmentedMediaState,
    blob: bytes,
    *,
    source: str,
    meta: DiagnosticMeta,
    message_index: int,
    take: int,
    complete: bool,
    expected_body_len: int,
) -> dict[str, Any]:
    body = state["body"]
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
    return summary


def complete_fragmented_blob(
    state: FragmentedMediaState, expected_body_len: int
) -> bytes:
    return bytes(state["header_raw"]) + bytes(
        state["body"][:expected_body_len]
    )


def fragmented_media_decode_meta(
    state: FragmentedMediaState,
    *,
    message_index: int,
    expected_body_len: int,
) -> dict[str, Any]:
    return {
        "start_msg_index": state.get("start_msg_index"),
        "end_msg_index": message_index,
        "fragments": state.get("fragments"),
        "expected_body_len": expected_body_len,
    }
