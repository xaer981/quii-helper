"""Portable G.711 vectors; no audioop dependency (removed in Python 3.13)."""

import hashlib
import struct

import pytest

from quii_helper.media.audio.g711 import decode_g711, encode_g711


@pytest.mark.parametrize(
    "codec,expected",
    [
        (4, [42, 58, 122, 85, 85, 213, 213, 212, 218, 197, 250, 165, 170]),
        (5, [0, 15, 78, 125, 126, 255, 255, 253, 231, 231, 206, 143, 128]),
    ],
)
def test_signed_little_endian_pcm_boundaries(codec, expected):
    samples = [
        -32768,
        -16384,
        -1000,
        -16,
        -1,
        0,
        1,
        16,
        255,
        256,
        1000,
        16384,
        32767,
    ]
    assert encode_g711(struct.pack("<13h", *samples), codec) == bytes(expected)


@pytest.mark.parametrize(
    "codec,digest",
    [
        (
            4,
            "38488f6fd710f4686360edc4d38639f96c491595ef93f8eb8d62d5e07ca6ce7b",
        ),
        (
            5,
            "81d633c9e6972a18c74a58720b96cb8ca0bdd096d4060b646dd708c3b846019a",
        ),
    ],
)
def test_all_pcm16_values_match_fixed_reference(codec, digest):
    # CPython 3.11.14 audioop.lin2alaw/lin2ulaw, width=2, signed LE input.
    pcm = struct.pack("<65536h", *range(-32768, 32768))
    assert hashlib.sha256(encode_g711(pcm, codec)).hexdigest() == digest


@pytest.mark.parametrize("pcm,codec", [(b"x", 4), (b"\0\0", 9)])
def test_invalid_pcm_or_codec_is_rejected(pcm, codec):
    with pytest.raises(ValueError):
        encode_g711(pcm, codec)


@pytest.mark.parametrize(
    "codec,digest",
    [
        (
            4,
            "e04788d110e58ff8c70c93b8480190d973e3b67876b6119abbaec766cc75c174",
        ),
        (
            5,
            "3dab54339e520bb2c924826e3b72a917a2b612e9fd12fc867500f1d983a75827",
        ),
    ],
)
def test_every_g711_code_decodes_to_fixed_pcm_reference(codec, digest):
    # CPython 3.11 audioop.alaw2lin/ulaw2lin, width=2; no runtime dependency.
    pcm = decode_g711(bytes(range(256)), codec)
    assert len(pcm) == 512
    assert hashlib.sha256(pcm).hexdigest() == digest
    assert decode_g711(b"", codec) == b""


def test_decode_rejects_other_codecs():
    with pytest.raises(ValueError):
        decode_g711(b"test", 9)
