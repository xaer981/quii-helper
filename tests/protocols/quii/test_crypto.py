import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from quii_helper.protocols.quii.blob import decode_quii_blob
from quii_helper.protocols.quii.crypto import (
    aes_cbc_crypt,
    aes_cbc_crypt_aligned_prefix,
)

KEY = "synthetic-test-key-not-secret-0000"


@pytest.mark.parametrize("mode", [1, 2])
@pytest.mark.parametrize("size", [0, 16, 32, 48])
def test_aes_matches_single_context_reference(mode, size):
    plain = bytes(range(size))
    cipher = Cipher(
        algorithms.AES(KEY.encode()[: mode * 16]), modes.CBC(b"0" * 16)
    )
    context = cipher.encryptor()
    expected = context.update(plain) + context.finalize()
    assert aes_cbc_crypt(plain, KEY, crypto_mode=mode) == expected
    assert (
        aes_cbc_crypt(expected, KEY, crypto_mode=mode, decrypt=True) == plain
    )


@pytest.mark.parametrize("mode", [1, 2])
@pytest.mark.parametrize("size", [1, 15, 17, 31])
@pytest.mark.parametrize("decrypt", [False, True])
def test_aes_rejects_partial_blocks_instead_of_truncating(mode, size, decrypt):
    with pytest.raises(ValueError, match="block"):
        aes_cbc_crypt(b"x" * size, KEY, crypto_mode=mode, decrypt=decrypt)


def test_clear_mode_and_media_tail_are_preserved():
    plain = b"x" * 31
    assert aes_cbc_crypt(plain, b"", crypto_mode=0) == plain
    encrypted, size = aes_cbc_crypt_aligned_prefix(plain, KEY, crypto_mode=2)
    assert size == 16 and encrypted[16:] == plain[16:]
    assert aes_cbc_crypt_aligned_prefix(
        encrypted, KEY, crypto_mode=2, decrypt=True
    ) == (plain, 16)


def test_incomplete_command_waits_without_decrypting_a_partial_block():
    header = bytearray(32)
    header[0] = 0xFE
    header[9:11] = (16).to_bytes(2, "little")
    header[11:13] = (2).to_bytes(2, "little")
    encoded = aes_cbc_crypt(header, KEY, crypto_mode=2)
    body = aes_cbc_crypt(b"ok" + b"\0" * 14, KEY, crypto_mode=2)
    for size in range(16):
        decoded = decode_quii_blob(encoded + body[:size], KEY)
        assert decoded["payload"] == b""
        assert decoded["read_size"] == 16
        assert decoded["payload_raw"] == body[:size]
    assert decode_quii_blob(encoded + body, KEY)["payload"][:2] == b"ok"


def test_malformed_full_command_is_not_silently_truncated():
    header = bytearray(32)
    header[0] = 0xFE
    header[9:13] = b"\x11\0\x11\0"
    encoded = aes_cbc_crypt(header, KEY, crypto_mode=2)
    with pytest.raises(ValueError, match="block"):
        decode_quii_blob(encoded + b"x" * 17, KEY)
