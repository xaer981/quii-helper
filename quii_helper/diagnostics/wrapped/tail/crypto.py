from quii_helper.protocols.quii.crypto import aes_cbc_crypt


def extract_wrapped_quii_tail(
    blob: bytes, decoded: dict
) -> tuple[bytes, bytes, int]:
    header = decoded["header"]
    consumed = 32 + header.payload_size
    if len(blob) <= consumed:
        return b"", b"", consumed
    tail = blob[consumed:]
    return tail, tail.rstrip(b"\xBB"), consumed


def decrypt_wrapped_quii_tail_bytes(
    blob: bytes, key: str, decoded: dict
) -> bytes:
    _tail, tail_trimmed, _consumed = extract_wrapped_quii_tail(blob, decoded)
    decryptable_len = len(tail_trimmed) - (len(tail_trimmed) % 16)
    if decryptable_len < 16:
        return b""
    try:
        return aes_cbc_crypt(
            tail_trimmed[:decryptable_len],
            key,
            crypto_mode=2,
            decrypt=True,
        )
    except Exception:
        return b""
