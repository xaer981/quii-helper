from quii_helper.diagnostics.wrapped.tail_crypto import (
    decrypt_wrapped_quii_tail_bytes,
)
from quii_helper.diagnostics.wrapped.tail_probe import (
    CONTAINER_PROBE_MARKER,
    is_container_probe_before_start_code,
)
from quii_helper.media.annexb_probe_analysis import analyze_annexb_h264
from quii_helper.media.cpacket_header import parse_cpacket_header
from quii_helper.media.cpacket_scanner import find_cpacket_offsets
from quii_helper.protocols.quii.blob import decode_quii_blob


def candidate_embedded_h264(blob: bytes, key: str, decoded: dict) -> bytes:
    decrypted_tail = decrypt_wrapped_quii_tail_bytes(blob, key, decoded)
    if not decrypted_tail:
        return b""
    start4 = decrypted_tail.find(b"\x00\x00\x00\x01")
    if start4 < 0:
        return b""
    if is_container_probe_before_start_code(decrypted_tail, start4):
        return b""
    candidate = decrypted_tail[start4:]
    analysis = analyze_annexb_h264(candidate)
    if analysis.get("false_positive_sps_only"):
        return b""
    return candidate


def candidate_container_probe(blob: bytes, key: str, decoded: dict) -> bytes:
    decrypted_tail = decrypt_wrapped_quii_tail_bytes(blob, key, decoded)
    if not decrypted_tail:
        return b""
    start4 = decrypted_tail.find(b"\x00\x00\x00\x01")
    if start4 < 4:
        return b""
    if not is_container_probe_before_start_code(decrypted_tail, start4):
        return b""
    return decrypted_tail[start4 - 4 :]


def candidate_cpacket_stream(blob: bytes, key: str, decoded: dict) -> bytes:
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
    if not payload:
        return b""
    idx = payload.find(CONTAINER_PROBE_MARKER)
    if idx < 0:
        return b""
    return payload[idx:]
