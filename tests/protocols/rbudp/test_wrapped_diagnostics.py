from types import SimpleNamespace

import pytest

from quii_helper.protocols.rbudp.core.models import ParsedRbUdpWrappedPacket
from quii_helper.protocols.rbudp.core.rb_data_packets import (
    build_rb_data_packet,
)
from quii_helper.protocols.rbudp.wrapped import frame_handler
from quii_helper.protocols.rbudp.wrapped.handler import RbUdpWrappedHandler


def _wrapped(inner: bytes) -> ParsedRbUdpWrappedPacket:
    return ParsedRbUdpWrappedPacket(
        marker=0xFFABEFC1,
        word4=1,
        word8=2,
        local_id=1,
        remote_id=1,
        status_word=0x1900,
        rand16=0,
        packet_len16=0,
        inner_total_length=len(inner),
        tag8=b"",
        inner_packet=inner,
    )


@pytest.mark.parametrize("debug", [False, True])
def test_media_diagnostics_never_retain_full_packets(debug, monkeypatch):
    messages, logs = [], []
    owner = SimpleNamespace(
        config=SimpleNamespace(rbudp_debug=debug),
        _lane_states=[],
        _peer_addr=("127.0.0.1", 1),
        _dbg=lambda label, **fields: logs.append(label),
        _queue_payload=lambda payload, **fields: messages.append(len(payload)),
    )
    handler = RbUdpWrappedHandler(owner)
    if not debug:
        monkeypatch.setattr(
            frame_handler,
            "sha256",
            lambda packet: pytest.fail(
                "disabled diagnostics must not hash media"
            ),
        )
    for seq in range(1000):
        inner = build_rb_data_packet(
            payload=b"x" * 4096,
            src_id=3,
            dest_id=4,
            seq=seq,
        )
        handler.handle_wrapped(_wrapped(inner))
    assert messages == [4096] * 1000
    fingerprints = handler._frame_handler._debug_seen
    assert len(fingerprints) == (
        frame_handler.MAX_WRAPPED_DEBUG_SAMPLES if debug else 0
    )
    assert all(len(fingerprint) == 32 for fingerprint in fingerprints)
    assert logs.count("recv_wrapped_data_parsed") == (1000 if debug else 0)
    handler.handle_wrapped(_wrapped(inner))
    assert logs.count("recv_wrapped_data_parsed") == (1000 if debug else 0)
    assert len(messages) == 1001


def test_unparsed_diagnostics_use_the_same_bounded_fingerprints():
    logs = []
    owner = SimpleNamespace(
        config=SimpleNamespace(rbudp_debug=True),
        _lane_states=[],
        _peer_addr=("127.0.0.1", 1),
        _dbg=lambda label, **fields: logs.append(label),
    )
    handler = RbUdpWrappedHandler(owner)
    for index in range(1000):
        handler.handle_wrapped(
            _wrapped(b"invalid" + index.to_bytes(4, "little"))
        )
    handler.handle_wrapped(_wrapped(b"invalid" + (999).to_bytes(4, "little")))
    assert logs.count("recv_wrapped_unparsed") == 1000
    assert (
        len(handler._frame_handler._debug_seen)
        == frame_handler.MAX_WRAPPED_DEBUG_SAMPLES
    )
    assert all(len(item) == 32 for item in handler._frame_handler._debug_seen)
