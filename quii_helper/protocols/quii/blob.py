from typing import Any

from quii_helper.media.frames.models import QuiiHeader
from quii_helper.media.frames.parsing import iter_quii_media_frames
from quii_helper.protocols.quii.blob_flow import (
    MEDIA_PACKET_TYPES,
    VALID_PACKET_TYPES,
    decode_candidate_summary,
    is_plausible_quii_header,
    safe_text_preview,
    score_media_payload,
    select_media_payload,
)
from quii_helper.protocols.quii.crypto import (
    aes_cbc_crypt,
    aes_cbc_crypt_aligned_prefix,
)

__all__ = [
    "MEDIA_PACKET_TYPES",
    "VALID_PACKET_TYPES",
    "decode_quii_blob",
    "find_quii_decode_candidates",
    "is_plausible_quii_header",
    "safe_text_preview",
]


def decode_quii_blob(
    blob: bytes, key: str, *, crypto_mode: int = 2, offset: int = 0
) -> dict[str, Any]:
    if len(blob) - offset < 32:
        raise ValueError(
            f"blob too short for QUII packet: {len(blob)} offset={offset}"
        )

    header_raw = blob[offset : offset + 32]
    header = aes_cbc_crypt(
        header_raw, key, crypto_mode=crypto_mode, decrypt=True
    )

    packet_type = header[0]
    command_payload_size = int.from_bytes(header[9:11], "little")
    raw_size = int.from_bytes(header[11:13], "little")
    media_payload_size = int.from_bytes(header[11:15], "little")
    media_payload_offset = int.from_bytes(header[16:18], "little")
    media_encrypted = header[15] != 0
    is_media = packet_type in MEDIA_PACKET_TYPES
    read_size = media_payload_size if is_media else command_payload_size
    encrypted_body = blob[offset + 32 : offset + 32 + read_size]
    body_available = max(0, len(blob) - offset - 32)
    plausible = is_plausible_quii_header(
        packet_type, command_payload_size, raw_size, body_available
    )

    if is_media:
        command_part_len = min(command_payload_size, len(encrypted_body))
        media_offset = min(media_payload_offset, len(encrypted_body))
        body = bytearray(encrypted_body)
        media_decrypt_len = 0
        media_decrypt_candidate_len = 0
        if command_part_len:
            command_part = aes_cbc_crypt(
                encrypted_body[:command_part_len],
                key,
                crypto_mode=crypto_mode,
                decrypt=True,
            )
            body[: len(command_part)] = command_part
        raw_payload = bytes(body[media_offset:])
        if media_encrypted and raw_payload:
            decrypted_media_part, media_decrypt_candidate_len = (
                aes_cbc_crypt_aligned_prefix(
                    raw_payload, key, crypto_mode=crypto_mode, decrypt=True
                )
            )
            payload, decrypt_selected, raw_score, decrypt_score = (
                select_media_payload(raw_payload, decrypted_media_part)
            )
            if decrypt_selected:
                media_decrypt_len = media_decrypt_candidate_len
        else:
            payload = raw_payload
            decrypt_selected = False
            raw_score = score_media_payload(payload)
            decrypt_score = raw_score
    else:
        command_part_len = 0
        media_decrypt_len = 0
        media_decrypt_candidate_len = 0
        decrypt_selected = False
        raw_score = 0
        decrypt_score = 0
        payload = (
            aes_cbc_crypt(
                encrypted_body, key, crypto_mode=crypto_mode, decrypt=True
            )
            if encrypted_body
            else b""
        )

    header_obj = QuiiHeader(
        packet_type=packet_type,
        payload_size=command_payload_size,
        raw_size=raw_size,
        flag13=header[13],
        flag14=header[14],
        flag15=header[15],
        flag16=header[16],
        flag17=header[17],
        raw=header,
    )
    media_frames = iter_quii_media_frames(payload) if is_media else []
    media_frame = media_frames[0] if media_frames else None
    return {
        "header": header_obj,
        "header_raw": header_raw,
        "payload": payload,
        "payload_raw": encrypted_body,
        "is_media": is_media,
        "media_frame": media_frame,
        "media_frames": media_frames,
        "text_preview": safe_text_preview(
            payload[:raw_size] if raw_size else payload
        ),
        "plausible": plausible,
        "offset": offset,
        "body_available": body_available,
        "media_payload_size": media_payload_size,
        "media_payload_offset": media_payload_offset,
        "media_encrypted": media_encrypted,
        "read_size": read_size,
        "media_command_part_len": command_part_len,
        "media_decrypt_len": media_decrypt_len,
        "media_decrypt_candidate_len": media_decrypt_candidate_len,
        "media_decrypt_applied": media_decrypt_len > 0,
        "media_decrypt_selected": decrypt_selected,
        "media_raw_score": raw_score,
        "media_decrypt_score": decrypt_score,
    }


def find_quii_decode_candidates(
    blob: bytes, key: str, *, crypto_mode: int = 2, max_offsets: int = 32
) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    limit = min(max_offsets, max(0, len(blob) - 32) + 1)
    for offset in range(limit):
        try:
            decoded = decode_quii_blob(
                blob, key, crypto_mode=crypto_mode, offset=offset
            )
        except Exception:
            continue
        if not decoded["plausible"]:
            continue
        header = decoded["header"]
        candidates.append(
            decode_candidate_summary(
                offset=offset,
                header=header,
                decoded=decoded,
            )
        )
    return candidates
