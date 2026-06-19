from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def get_sha_len(sha_mode: int = 1) -> int:
    return 32 if sha_mode == 1 else 0


def get_encrypt_mod(crypto_mode: int) -> int:
    return 1 if crypto_mode == 0 else 16


def get_key_len_bits(crypto_mode: int) -> int:
    if crypto_mode == 1:
        return 128
    if crypto_mode == 2:
        return 256
    return 0


def make_ivec() -> bytes:
    return b"0" * 16


def compute_ext_data_len(
    payload_len: int,
    *,
    crypto_mode: int,
    sha_mode: int = 1,
    include_sha: bool = True,
) -> tuple[int, int]:
    total = payload_len
    if include_sha:
        total += get_sha_len(sha_mode)
    padded = total
    if total and crypto_mode != 0:
        block = get_encrypt_mod(crypto_mode)
        padded = ((total + block - 1) // block) * block
    return total, padded


def sha_bytes(data: bytes, sha_mode: int = 1) -> bytes:
    if sha_mode == 1:
        import hashlib

        return hashlib.sha256(data).digest()
    return b""


def aes_cbc_crypt(
    data: bytes, key: bytes | str, *, crypto_mode: int, decrypt: bool = False
) -> bytes:
    if crypto_mode == 0:
        return data

    if isinstance(key, str):
        key = key.encode("utf-8")

    needed = get_key_len_bits(crypto_mode) // 8
    if len(key) < needed:
        raise ValueError(
            f"key must be at least {needed} "
            f"bytes for crypto_mode={crypto_mode}"
        )
    key = key[:needed]

    cipher = Cipher(algorithms.AES(key), modes.CBC(make_ivec()))
    if decrypt:
        return cipher.decryptor().update(data) + cipher.decryptor().finalize()
    return cipher.encryptor().update(data) + cipher.encryptor().finalize()
