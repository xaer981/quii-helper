import base64
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from quii_helper.protocols.ust.key_derivation import derive_ust_aes_key

UST_AES_IV = b"0" * 16


def decrypt_ust_ciphertext(
    ciphertext_b64: str,
    *,
    srcid: str,
    sver: str = "1.0.0",
    so_path: str | Path | None = None,
) -> bytes:
    key = derive_ust_aes_key(srcid, sver=sver, so_path=so_path)
    ciphertext = base64.b64decode(ciphertext_b64)
    if len(ciphertext) % 16 != 0:
        raise ValueError("UST ciphertext is not aligned to AES-CBC block size")
    cipher = Cipher(algorithms.AES(key), modes.CBC(UST_AES_IV))
    decryptor = cipher.decryptor()
    return decryptor.update(ciphertext) + decryptor.finalize()


def decode_ust_mqtt_credentials(
    parsed: Any,
    *,
    srcid: str,
    so_path: str | Path | None = None,
) -> tuple[str | None, str | None]:
    username = parsed.mqtt_username
    password = parsed.mqtt_password
    sver = parsed.sver or "1.0.0"

    decoded_user: str | None = username
    decoded_pass: str | None = password

    if username:
        decoded_user = _decode_ust_text(
            username, srcid=srcid, sver=sver, so_path=so_path
        )
    if password:
        decoded_pass = _decode_ust_text(
            password, srcid=srcid, sver=sver, so_path=so_path
        )
    return decoded_user, decoded_pass


def _decode_ust_text(
    ciphertext_b64: str, *, srcid: str, sver: str, so_path: str | Path | None
) -> str:
    return (
        decrypt_ust_ciphertext(
            ciphertext_b64, srcid=srcid, sver=sver, so_path=so_path
        )
        .rstrip(b"\x00")
        .decode(
            "utf-8",
            errors="ignore",
        )
    )
