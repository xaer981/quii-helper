from pathlib import Path

from quii_helper.protocols.ust.crypto_tables import load_p2p_crypto_tables
from quii_helper.protocols.ust.key_schedule import expand_ust_aes_key


def append_zero_to_32(text: str) -> bytes:
    raw = text.encode("utf-8")
    if len(raw) > 32:
        raw = raw[:32]
    if len(raw) < 32:
        raw += b"0" * (32 - len(raw))
    return raw


def generate_ust_seed_and_sbox(
    srcid: str, *, so_path: str | Path | None = None
) -> tuple[bytes, bytes]:
    data1, data2, data3 = load_p2p_crypto_tables(so_path)

    seed = bytearray(32)
    seed[0] = data2[data1[1]]
    for index in range(1, 32):
        prev = seed[index - 1]
        seed[index] = data2[((prev % 0x10) * prev) & 0xFFF]

    srcid_padded = append_zero_to_32(srcid)
    for index in range(32):
        seed[index] = (seed[index] + srcid_padded[index]) & 0xFF

    sbox = bytearray(256)
    sbox[0] = data3[seed[0]]
    for index in range(1, 256):
        prev = sbox[index - 1]
        sbox[index] = data3[((prev % 0x10) * prev) & 0xFFF]

    return bytes(seed), bytes(sbox)


def derive_ust_aes_key(
    srcid: str, *, sver: str = "1.0.0", so_path: str | Path | None = None
) -> bytes:
    if sver != "1.0.0":
        raise ValueError(
            f"unsupported sVer for UST AES key derivation: {sver!r}"
        )

    seed, sbox = generate_ust_seed_and_sbox(srcid, so_path=so_path)
    return expand_ust_aes_key(seed, sbox)
