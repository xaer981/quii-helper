from typing import Any

from quii_helper.diagnostics.wrapped.tail.candidate_state import (
    partial_payload_container_candidate,
    tail_container_probe_candidate,
    tail_startcode_h264_candidate,
)
from quii_helper.diagnostics.wrapped.tail.crypto import (
    decrypt_wrapped_quii_tail_bytes,
)
from quii_helper.diagnostics.wrapped.tail.probe import CONTAINER_PROBE_MARKER
from quii_helper.media.cpacket.header import parse_cpacket_header
from quii_helper.media.cpacket.scanner import find_cpacket_offsets
from quii_helper.media.h264.merge.probe_analysis import analyze_annexb_h264
from quii_helper.protocols.quii.blob import decode_quii_blob


def candidate_embedded_h264(
    blob: bytes, key: str, decoded: dict[str, Any]
) -> bytes:
    decrypted_tail = decrypt_wrapped_quii_tail_bytes(blob, key, decoded)
    if not decrypted_tail:
        return b""
    candidate = tail_startcode_h264_candidate(
        decrypted_tail, marker=CONTAINER_PROBE_MARKER
    )
    if not candidate:
        return b""
    analysis = analyze_annexb_h264(candidate)
    if analysis.get("false_positive_sps_only"):
        return b""
    return candidate


def candidate_container_probe(
    blob: bytes, key: str, decoded: dict[str, Any]
) -> bytes:
    decrypted_tail = decrypt_wrapped_quii_tail_bytes(blob, key, decoded)
    if not decrypted_tail:
        return b""
    return tail_container_probe_candidate(
        decrypted_tail, marker=CONTAINER_PROBE_MARKER
    )


def candidate_cpacket_stream(
    blob: bytes, key: str, decoded: dict[str, Any]
) -> bytes:
    decrypted_tail = decrypt_wrapped_quii_tail_bytes(blob, key, decoded)
    if not decrypted_tail:
        return b""
    return candidate_cpacket_from_decrypted_tail(decrypted_tail)


def candidate_cpacket_from_decrypted_tail(decrypted_tail: bytes) -> bytes:
    for offset in find_cpacket_offsets(decrypted_tail, limit=16):
        parsed = parse_cpacket_header(decrypted_tail, offset)
        if parsed.get("plausible"):
            return decrypted_tail[offset:]
    return b""


def candidate_container_probe_from_partial_payload(
    blob: bytes, key: str
) -> bytes:
    try:
        decoded = decode_quii_blob(blob, key, crypto_mode=2)
    except Exception:
        return b""
    candidate = candidate_container_probe(blob, key, decoded)
    if candidate:
        return candidate
    payload = decoded.get("payload", b"")
    if not isinstance(payload, bytes):
        return b""
    return partial_payload_container_candidate(
        payload, marker=CONTAINER_PROBE_MARKER
    )
