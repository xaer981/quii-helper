from quii_helper.diagnostics.wrapped.tail.crypto import (
    decrypt_wrapped_quii_tail_bytes,
    extract_wrapped_quii_tail,
)
from quii_helper.diagnostics.wrapped.tail.probe import analyze_decrypted_tail


def analyze_wrapped_quii_tail(
    blob: bytes, key: str, decoded: dict
) -> dict | None:
    header = decoded["header"]
    tail, tail_trimmed, consumed = extract_wrapped_quii_tail(blob, decoded)
    if not tail:
        return None

    decryptable_len = len(tail_trimmed) - (len(tail_trimmed) % 16)
    decrypted = decrypt_wrapped_quii_tail_bytes(blob, key, decoded)
    decrypted_analysis = analyze_decrypted_tail(decrypted)

    return {
        "packet_type": hex(header.packet_type),
        "payload_size": header.payload_size,
        "raw_size": header.raw_size,
        "blob_len": len(blob),
        "consumed": consumed,
        "tail_len": len(tail),
        "tail_trimmed_len": len(tail_trimmed),
        "tail_bb_suffix_len": len(tail) - len(tail_trimmed),
        "decryptable_len": decryptable_len,
        "tail_prefix": tail[:64].hex(),
        "tail_trimmed_prefix": tail_trimmed[:64].hex(),
        "tail_trimmed_suffix": (
            tail_trimmed[-64:].hex() if tail_trimmed else ""
        ),
        **decrypted_analysis,
    }
