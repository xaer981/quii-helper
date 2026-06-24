from quii_helper.media.cpacket.constants import (
    CPACKET_HEADER_LEN,
    CPACKET_START_PREFIX,
    CPACKET_START_TYPE_MAX,
    CPACKET_START_TYPE_MIN,
)
from quii_helper.media.fragments.state import (
    append_fragmented_media_body,
    build_fragmented_media_state,
    complete_fragmented_blob,
    fragmented_media_append_summary,
    fragmented_media_decode_meta,
    fragmented_media_lengths,
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
    expected_body_len, expected_media_len, body_len = fragmented_media_lengths(
        decoded
    )
    payload = decoded.get("payload", b"")
    if (
        expected_body_len <= body_len
        or expected_body_len > FRAGMENTED_MEDIA_MAX_BODY_LEN
    ):
        return False
    return cframe_total_len(payload) == expected_media_len


def start_fragmented_media(
    decoded: dict, *, source: str, meta: dict, message_index: int
) -> dict:
    return build_fragmented_media_state(
        decoded, source=source, meta=meta, message_index=message_index
    )


def append_fragmented_media(
    state: dict,
    blob: bytes,
    key: str,
    *,
    source: str,
    meta: dict,
    message_index: int,
) -> tuple[dict | None, bytes, dict]:
    take, complete, expected_body_len = append_fragmented_media_body(
        state, blob
    )
    summary = fragmented_media_append_summary(
        state,
        blob,
        source=source,
        meta=meta,
        message_index=message_index,
        take=take,
        complete=complete,
        expected_body_len=expected_body_len,
    )
    if not complete:
        return None, b"", summary

    full_blob = complete_fragmented_blob(state, expected_body_len)
    decoded = decode_quii_blob(full_blob, key, crypto_mode=2)
    decoded["fragmented_media"] = fragmented_media_decode_meta(
        state, message_index=message_index, expected_body_len=expected_body_len
    )
    return decoded, blob[take:], summary
