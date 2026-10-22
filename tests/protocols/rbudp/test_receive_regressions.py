import struct
from unittest.mock import Mock

import pytest

from quii_helper.protocols.rbudp.core.rb_data_packets import (
    build_rb_data_packet,
)
from quii_helper.protocols.rbudp.lanes.registry import RbUdpLaneRegistry
from quii_helper.protocols.rbudp.receive.stream import (
    RbUdpReceiveStreamAssembler,
)
from quii_helper.support.errors import QuiiConnectionError


def _packet(seq, payload, *, word4=0x01000000, word8=0x3D000022):
    return (
        struct.pack(
            "<6I2H",
            0xFFABEFC1,
            word4,
            word8,
            seq & 0xFFFFFFFF,
            1,
            0x1900,
            0,
            28 + len(payload),
        )
        + payload
    )


def _assembler():
    registry = RbUdpLaneRegistry.create(
        src_ids=[0x04000006, 0x04000007],
        bootstrap_word4=0,
        bootstrap_remote_id=1,
        bootstrap_local_ids=[0, 1],
    )
    for lane in registry.lanes:
        lane["local_id"] = 165
        lane["word8"] = lane["bootstrap_word8"]
    return RbUdpReceiveStreamAssembler(
        debug=Mock(),
        lane_for_packet_words=registry.for_packet_words,
        send_fragment_ack=Mock(),
        handle_wrapped=Mock(),
    )


@pytest.mark.parametrize("size", [65500, 80000, 200000])
@pytest.mark.parametrize("start", [1, 0xFFFF8000])
def test_large_frame_completes_when_sender_obeys_advertised_window(
    size, start
):
    assembler = _assembler()
    inner = build_rb_data_packet(
        payload=b"x" * size, src_id=3, dest_id=4, seq=1
    )
    sent, credit = 0, 65535
    while sent < len(inner):
        assert (
            credit > 0
        ), "receiver closed its window on an incomplete KCP frame"
        length = min(1400, credit, len(inner) - sent)
        assembler.feed(_packet(start + sent, inner[sent : sent + length]))
        sent += length
        ack = assembler.send_fragment_ack.call_args
        assert ack.args[2] == (start + sent) & 0xFFFFFFFF
        credit = ack.kwargs["status_word"] >> 16
    assert assembler.handle_wrapped.call_count == 1
    assert assembler.handle_wrapped.call_args.args[0].inner_packet == inner
    assert not assembler.has_pending()


def test_reordered_large_frame_drains_transport_without_losing_kcp_prefix():
    assembler = _assembler()
    inner = build_rb_data_packet(
        payload=b"x" * 80000, src_id=3, dest_id=4, seq=1
    )
    assembler.feed(_packet(1, inner[:1400]))
    assembler.feed(_packet(2801, inner[2800:4200]))
    assembler.feed(_packet(1401, inner[1400:2800]))
    assert assembler.stats["cache_drained"] == 1
    for offset in range(4200, len(inner), 1400):
        assembler.feed(_packet(1 + offset, inner[offset : offset + 1400]))
    assert assembler.handle_wrapped.call_args.args[0].inner_packet == inner
    assert all(
        call.kwargs["status_word"] >> 16 > 0
        for call in assembler.send_fragment_ack.call_args_list
    )
    assert not assembler.has_pending()


@pytest.mark.parametrize("word4", [0, 123, 0xFFFFFFFF])
def test_unknown_connections_never_allocate_ack_or_dispatch(word4):
    assembler = _assembler()
    inner = build_rb_data_packet(
        payload=b"unrelated", src_id=3, dest_id=4, seq=1
    )
    for word8 in range(1000):
        assert assembler.feed(_packet(1, inner, word4=word4, word8=word8))
    assert not assembler.streams
    assert not assembler.has_pending()
    assembler.send_fragment_ack.assert_not_called()
    assembler.handle_wrapped.assert_not_called()


def test_peer_word_changes_reuse_one_state_and_keep_sequence_validation():
    assembler = _assembler()
    inner = build_rb_data_packet(
        payload=b"x" * 10000, src_id=3, dest_id=4, seq=1
    )
    for offset in range(0, len(inner), 100):
        assembler.feed(
            _packet(1 + offset, inner[offset : offset + 100], word8=offset + 1)
        )
    assert len(assembler.streams) == 1
    assert assembler.handle_wrapped.call_count == 1
    assert assembler.handle_wrapped.call_args.args[0].inner_packet == inner
    for word8 in range(1000):
        assembler.feed(_packet(1, inner[:100], word8=word8 + 1))
    assert len(assembler.streams) == 1
    assert assembler.stats["replayed"] == 1000
    assert assembler.handle_wrapped.call_count == 1
    assert not assembler.has_pending()


@pytest.mark.parametrize(
    "tail",
    [
        b"INVALID_HEADER!!",
        struct.pack("<4I", 0xFFFFFFFF, 0, 0, 0),
        struct.pack("<4I", 0xFFFFFFFF, 16, 0, 0),
        struct.pack("<4I", 0xFFFFFFFF, 20 * 1024 * 1024 + 1, 0, 0),
    ],
)
def test_valid_prefix_is_dispatched_before_corrupt_tail_fails(tail):
    assembler = _assembler()
    inner = build_rb_data_packet(payload=b"valid", src_id=3, dest_id=4, seq=1)
    with pytest.raises(
        QuiiConnectionError, match="invalid KCP receive stream"
    ):
        assembler.feed(_packet(1, inner + tail))
    assert assembler.handle_wrapped.call_count == 1
    assert assembler.handle_wrapped.call_args.args[0].inner_packet == inner
    assert assembler.stats["invalid"] == 1


def test_partial_next_header_is_kept_and_both_frames_delivered_once():
    assembler = _assembler()
    first = build_rb_data_packet(payload=b"first", src_id=3, dest_id=4, seq=1)
    second = build_rb_data_packet(
        payload=b"second", src_id=3, dest_id=4, seq=2
    )
    assembler.feed(_packet(1, first + second[:7]))
    assert assembler.handle_wrapped.call_count == 1
    assert assembler.has_pending()
    assembler.feed(_packet(1 + len(first) + 7, second[7:]))
    assert [
        call.args[0].inner_packet
        for call in assembler.handle_wrapped.call_args_list
    ] == [first, second]
    assert not assembler.has_pending()


def test_lane_streams_do_not_mix_partial_kcp_frames():
    assembler = _assembler()
    first = build_rb_data_packet(payload=b"first", src_id=3, dest_id=4, seq=1)
    second = build_rb_data_packet(
        payload=b"second", src_id=5, dest_id=6, seq=1
    )
    assembler.feed(_packet(1, first[:30]))
    assembler.feed(_packet(1, second, word4=0x02000001))
    assembler.feed(_packet(31, first[30:]))
    assert len(assembler.streams) == 2
    assert [
        call.args[0].inner_packet
        for call in assembler.handle_wrapped.call_args_list
    ] == [second, first]
    assert not assembler.has_pending()


def test_wrapped_handler_failure_is_not_misreported_as_corrupt_kcp():
    assembler = _assembler()
    cause = ValueError("synthetic consumer failure")
    assembler.handle_wrapped.side_effect = cause
    inner = build_rb_data_packet(payload=b"media", src_id=3, dest_id=4, seq=1)
    with pytest.raises(ValueError) as error:
        assembler.feed(_packet(1, inner))
    assert error.value is cause
    assert assembler.stats["invalid"] == 0
