import random
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from quii_helper.preview.processing.packets.processor import (
    PreviewPacketProcessor,
)
from quii_helper.protocols.quii.crypto import (
    aes_cbc_crypt,
    aes_cbc_crypt_aligned_prefix,
)
from quii_helper.support.errors import QuiiConnectionError

KEY = "synthetic-test-key-not-secret-0000"


def processor():
    return PreviewPacketProcessor(
        key=KEY,
        artifacts=SimpleNamespace(diagnostics_enabled=False),
        fragment_partial_collector=Mock(),
        emit=lambda _: None,
        min_media_messages=1,
        max_media_messages=160,
        direct_blob_summary_limit=0,
    )


def feed(target, blob, stream=1, phase="live"):
    target.process_packet(
        {
            "payload": blob,
            "source": "wrapped_quii",
            "meta": {"src_id": stream, "dest_id": 4},
        },
        phase=phase,
    )


def media_packet(*, metadata_size=0, encrypted=False):
    frame = bytearray(20)
    frame[:4] = b"\x00\x00\x01\xe1"
    frame[4:8] = (100).to_bytes(4, "little")
    frame[14:16] = b"\x01\x64"
    frame[16:18] = (960).to_bytes(2, "little")
    frame[18:20] = (576).to_bytes(2, "little")
    payload = bytes(frame) + b"\x00\x00\x00\x01\x65" + b"x" * 95
    body = payload
    if encrypted:
        body, _ = aes_cbc_crypt_aligned_prefix(body, KEY, crypto_mode=2)
    if metadata_size:
        body = aes_cbc_crypt(b"m" * metadata_size, KEY, crypto_mode=2) + body
    header = bytearray(32)
    header[0] = 0xA0
    header[9:11] = metadata_size.to_bytes(2, "little")
    header[11:15] = len(body).to_bytes(4, "little")
    header[15] = int(encrypted)
    header[16:18] = metadata_size.to_bytes(2, "little")
    return aes_cbc_crypt(header, KEY, crypto_mode=2) + body, payload


def command_packet():
    header = bytearray(32)
    header[0] = 0xFE
    header[9:13] = b"\x10\0\x02\0"
    return aes_cbc_crypt(header, KEY, crypto_mode=2) + aes_cbc_crypt(
        b"ok" + b"\0" * 14, KEY, crypto_mode=2
    )


@pytest.mark.parametrize("phase", ["live", "flush", "close"])
@pytest.mark.parametrize("tail", range(1, 32))
def test_active_media_accepts_tail_shorter_than_header(tail, phase):
    blob, payload = media_packet()
    target = processor()
    feed(target, blob[:-tail], phase=phase)
    assert target.fragmented_media_states
    feed(target, blob[-tail:], phase=phase)
    assert not target.has_pending_live_buffers()
    assert [item["payload"] for item in target.media_messages] == [payload]


@pytest.mark.parametrize("encrypted", [False, True])
@pytest.mark.parametrize("metadata_size", [0, 16, 32])
def test_every_single_cut_and_one_byte_chunks_preserve_media(
    metadata_size, encrypted
):
    blob, payload = media_packet(
        metadata_size=metadata_size, encrypted=encrypted
    )
    partitions = [[blob[:cut], blob[cut:]] for cut in range(1, len(blob))]
    partitions.append([blob[index : index + 1] for index in range(len(blob))])
    for chunks in partitions:
        target = processor()
        for chunk in chunks:
            feed(target, chunk)
        assert not target.has_pending_live_buffers(), list(map(len, chunks))
        assert [item["payload"] for item in target.media_messages] == [payload]


def test_seeded_partitions_of_coalesced_packets_preserve_order_and_bytes():
    media, payload = media_packet()
    command = command_packet()
    for stream, expected in (
        (command * 3, [b"ok" + b"\0" * 14] * 3),
        (media * 3, [payload] * 3),
        (command + media + command + media, [b"ok" + b"\0" * 14, payload] * 2),
    ):
        for seed in range(500):
            randomizer = random.Random(seed)
            target = processor()
            offset = 0
            while offset < len(stream):
                size = randomizer.randint(1, 100)
                feed(target, stream[offset : offset + size])
                offset += size
            assert not target.has_pending_live_buffers(), seed
            assert [
                item["payload"] for item in target.decoded_messages
            ] == expected


def test_active_media_does_not_consume_other_stream_short_header():
    blob, payload = media_packet()
    target = processor()
    feed(target, blob[:-10])
    feed(target, blob[:10], stream=2)
    feed(target, blob[-10:])
    assert len(target.quii_packet_buffers) == 1
    feed(target, blob[10:], stream=2)
    assert not target.has_pending_live_buffers()
    assert [item["payload"] for item in target.media_messages] == [payload] * 2


def test_short_next_header_is_buffered_after_fragment_completion():
    blob, payload = media_packet()
    target = processor()
    feed(target, blob[:-10])
    feed(target, blob[-10:] + blob[:7])
    assert not target.fragmented_media_states
    assert list(target.quii_packet_buffers.values()) == [blob[:7]]
    feed(target, blob[7:])
    assert not target.has_pending_live_buffers()
    assert [item["payload"] for item in target.media_messages] == [payload] * 2


def test_malformed_command_clears_pending_state_and_raises_domain_error():
    target = processor()
    feed(target, b"partial", stream=2)
    header = bytearray(32)
    header[0] = 0xFE
    header[9:13] = b"\x11\0\x11\0"
    with pytest.raises(QuiiConnectionError, match="invalid QUII packet"):
        feed(target, aes_cbc_crypt(header, KEY, crypto_mode=2) + b"x" * 17)
    assert not target.has_pending_live_buffers()
