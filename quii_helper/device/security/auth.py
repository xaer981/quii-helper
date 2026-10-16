import base64
import hashlib

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def device_supports_sha256_password(transparent_basedata: str) -> bool | None:
    """Read native `TYPE_ENCRYPY_SHA256` (24), or None if data is unknown."""
    try:
        data = base64.b64decode(
            "".join(transparent_basedata.split()), validate=True
        )
    except ValueError:
        return None
    # QvDeviceAbility skips two header bytes before reading capability bits.
    if len(data) < 6:
        return None
    return bool(data[5] & 1)


def encode_device_password(value: str) -> str:
    if value is None or len(value) < 64:
        return hashlib.sha256((value or "").encode("utf-8")).hexdigest()
    return value


def get_encrypt_password(username: str, password: str, nc: str) -> str:
    key = hashlib.sha256(f"{username}:{nc}".encode("utf-8")).digest()
    iv = b"0" * 16

    raw = password.encode("utf-8")
    padded_len = (len(raw) + 15) & ~0x0F
    padded = raw.ljust(padded_len, b"\x00")

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    encrypted = cipher.update(padded) + cipher.finalize()
    return base64.b64encode(encrypted).decode("ascii")
