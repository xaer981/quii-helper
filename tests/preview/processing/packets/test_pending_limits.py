from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from quii_helper.preview.processing.packets import flow
from quii_helper.preview.processing.packets.processor import (
    PreviewPacketProcessor,
)
from quii_helper.protocols.quii import blob as blob_module
from quii_helper.protocols.quii.crypto import aes_cbc_crypt
from quii_helper.support.errors import QuiiConnectionError

KEY = "synthetic-test-key-not-secret-0000"


def _processor():
    return PreviewPacketProcessor(
        key=KEY,
        artifacts=SimpleNamespace(diagnostics_enabled=False),
        fragment_partial_collector=Mock(),
        emit=Mock(),
        min_media_messages=1,
        max_media_messages=160,
        direct_blob_summary_limit=16,
        store_media_messages=False,
    )


def _feed(processor, blob, stream=1):
    return processor.process_packet(
        {
            "payload": blob,
            "source": "wrapped_quii",
            "meta": {"src_id": stream, "dest_id": 4},
        },
        phase="live",
    )


def _media_header(size):
    header = bytearray(32)
    header[0] = 0xA0
    header[11:15] = size.to_bytes(4, "little")
    return aes_cbc_crypt(header, KEY, crypto_mode=2)


@pytest.mark.parametrize("size", [0, 20 * 1024 * 1024 + 1, 2**31])
def test_invalid_declared_media_size_fails_without_retaining_data(size):
    processor = _processor()
    with pytest.raises(QuiiConnectionError, match="QUII"):
        _feed(processor, _media_header(size))
    assert not processor.has_pending_live_buffers()


@pytest.mark.parametrize("fragmented", [False, True])
def test_pending_stream_count_is_bounded_and_failure_releases_all_buffers(
    monkeypatch,
    fragmented,
):
    monkeypatch.setattr(flow, "MAX_PENDING_QUII_STREAMS", 2, raising=False)
    processor = _processor()
    _feed(processor, b"partial", 1)
    if fragmented:
        processor.fragmented_media_states[("rb_data", 2, 4)] = {
            "header_raw": b"h" * 32,
            "body": bytearray(b"partial"),
        }
    else:
        _feed(processor, b"partial", 2)
    with pytest.raises(QuiiConnectionError, match="QUII.*limit"):
        _feed(processor, b"partial", 3)
    assert not processor.has_pending_live_buffers()


def test_declared_size_limit_allows_boundary_and_rejects_one_more(monkeypatch):
    monkeypatch.setattr(blob_module, "MAX_QUII_BODY_SIZE", 128)
    processor = _processor()
    _feed(processor, _media_header(128))
    assert processor.has_pending_live_buffers()
    with pytest.raises(QuiiConnectionError, match="QUII"):
        _feed(processor, _media_header(129), 2)
    assert not processor.has_pending_live_buffers()


def test_exact_byte_budget_is_allowed(monkeypatch):
    monkeypatch.setattr(flow, "MAX_PENDING_QUII_BYTES", 64)
    processor = _processor()
    _feed(processor, _media_header(256))
    _feed(processor, b"x" * 32)
    assert processor.chained_packet_summary()["buffered_bytes"] == 64


def test_decode_failure_does_not_become_a_permanent_pending_prefix(
    monkeypatch,
):
    processor = _processor()
    monkeypatch.setattr(
        type(processor.decoder),
        "decode",
        Mock(side_effect=ValueError("invalid header")),
    )
    _feed(processor, b"partial", 2)
    with pytest.raises(QuiiConnectionError, match="invalid QUII packet"):
        _feed(processor, b"x" * 32)
    assert not processor.has_pending_live_buffers()


@pytest.mark.parametrize("fragmented", [False, True])
def test_pending_byte_budget_includes_both_assemblers(monkeypatch, fragmented):
    monkeypatch.setattr(flow, "MAX_PENDING_QUII_BYTES", 64, raising=False)
    processor = _processor()
    if fragmented:
        processor.fragmented_media_states[("rb_data", 2, 4)] = {
            "header_raw": b"h" * 32,
            "body": bytearray(b"b" * 20),
        }
    else:
        processor.quii_packet_buffers[("rb_data", 2, 4)] = b"b" * 52
    with pytest.raises(QuiiConnectionError, match="QUII.*limit"):
        _feed(processor, b"p" * 13)
    assert not processor.has_pending_live_buffers()


def test_pending_byte_limit_is_checked_before_prepend_or_decode(monkeypatch):
    monkeypatch.setattr(flow, "MAX_PENDING_QUII_BYTES", 64, raising=False)
    processor = _processor()
    _feed(processor, _media_header(256))
    with pytest.raises(QuiiConnectionError, match="QUII.*limit"):
        _feed(processor, b"x" * 33)
    assert not processor.has_pending_live_buffers()


def test_valid_command_header_and_body_can_arrive_separately():
    processor = _processor()
    processor.capture_stats.store_media_messages = True
    header = bytearray(32)
    header[0] = 0xFE
    header[9:11] = (16).to_bytes(2, "little")
    header[11:13] = (2).to_bytes(2, "little")
    blob = aes_cbc_crypt(header, KEY, crypto_mode=2) + aes_cbc_crypt(
        b"ok" + b"\0" * 14, KEY, crypto_mode=2
    )
    for part in (blob[:31], blob[31:35], blob[35:]):
        _feed(processor, part)
    assert not processor.has_pending_live_buffers()
    assert len(processor.decoded_messages) == 1
