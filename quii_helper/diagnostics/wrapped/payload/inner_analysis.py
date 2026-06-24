from quii_helper.diagnostics.wrapped.payload.probe import (
    analyze_payload_embedded_probe,
)
from quii_helper.diagnostics.wrapped.tail.analysis import (
    analyze_wrapped_quii_tail,
)
from quii_helper.protocols.quii.blob import (
    decode_quii_blob,
    find_quii_decode_candidates,
)


def analyze_partial_wrapped_inner(blob: bytes, key: str) -> dict:
    analysis: dict[str, object] = {
        "blob_len": len(blob),
        "blob_prefix": blob[:96].hex(),
    }
    if len(blob) < 0x38 or blob[:4] != b"\xff\xff\xff\xff":
        return analysis

    packet_length = int.from_bytes(blob[0x04:0x08], "little")
    packet_type_flag = int.from_bytes(blob[0x12:0x14], "little")
    command = int.from_bytes(blob[0x14:0x18], "little")
    seq = int.from_bytes(blob[0x18:0x1C], "little")
    payload_length = int.from_bytes(blob[0x24:0x28], "little")
    dest_id = int.from_bytes(blob[0x28:0x2C], "little")
    src_id = int.from_bytes(blob[0x2C:0x30], "little")
    body_length = int.from_bytes(blob[0x30:0x34], "little")
    payload = blob[0x38:]

    analysis.update(
        {
            "packet_length": packet_length,
            "packet_type_flag": packet_type_flag,
            "command": hex(command),
            "seq": seq,
            "payload_length": payload_length,
            "body_length": body_length,
            "dest_id": hex(dest_id),
            "src_id": hex(src_id),
            "partial_payload_len": len(payload),
            "payload_prefix": payload[:96].hex(),
        }
    )

    try:
        decoded = decode_quii_blob(payload, key, crypto_mode=2)
    except Exception as exc:
        analysis["decode_error"] = repr(exc)
        return analysis

    header = decoded["header"]
    analysis["payload_decode"] = {
        "plausible": decoded["plausible"],
        "packet_type": hex(header.packet_type),
        "payload_size": header.payload_size,
        "raw_size": header.raw_size,
        "text_preview": decoded["text_preview"],
        "payload_prefix": decoded["payload"][:64].hex(),
    }
    embedded_probe = analyze_payload_embedded_probe(decoded["payload"])
    if embedded_probe is not None:
        analysis["payload_embedded_probe"] = embedded_probe
    if not decoded["plausible"]:
        candidates = find_quii_decode_candidates(payload, key, crypto_mode=2)
        if candidates:
            analysis["payload_decode_candidates"] = candidates[:8]
    if decoded["plausible"]:
        tail_analysis = analyze_wrapped_quii_tail(payload, key, decoded)
        if tail_analysis is not None:
            analysis["wrapped_tail_analysis"] = tail_analysis
    return analysis
