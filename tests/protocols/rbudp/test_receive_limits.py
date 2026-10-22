import struct
from unittest.mock import Mock

import pytest

from quii_helper.protocols.rbudp.core.rb_data_packets import (
    build_rb_data_packet,
)
from quii_helper.protocols.rbudp.receive import stream as stream_module
from quii_helper.protocols.rbudp.receive.stream import (
    RbUdpReceiveStreamAssembler,
)
from quii_helper.protocols.rbudp.receive.stream_state import (
    RbUdpReceiveStreamState,
)
from quii_helper.support.errors import QuiiConnectionError


def _packet(local_id, payload):
    return (
        struct.pack(
            "<6I2H",
            0xFFABEFC1,
            1,
            2,
            local_id,
            1,
            0x1900,
            0,
            28 + len(payload),
        )
        + payload
    )


def _assembler(next_id=100):
    assembler = RbUdpReceiveStreamAssembler(
        debug=Mock(),
        lane_for_packet_words=Mock(return_value={"local_id": 1, "src_id": 3}),
        send_fragment_ack=Mock(),
        handle_wrapped=Mock(),
    )
    state = RbUdpReceiveStreamState(word4=1, word8=2, next_local_id=next_id)
    assembler.streams[3] = state
    return assembler, state


@pytest.mark.parametrize("distance", [65535, 65536, 65537, 0xFFFFFFFF])
def test_native_receive_window_is_exclusive_and_ack_does_not_count_cache(
    distance,
):
    assembler, state = _assembler()
    local_id = (100 + distance) & 0xFFFFFFFF
    assert assembler.feed(_packet(local_id, b"x"))
    assert len(state.cache) == (1 if distance < 65536 else 0)
    assert state.cached_bytes == (1 if distance < 65536 else 0)
    ack = assembler.send_fragment_ack.call_args
    assert ack.args[2] == 100
    assert ack.kwargs["status_word"] == 0xFFFF0900


def test_persistent_gap_does_not_cache_packets_beyond_native_window():
    assembler, state = _assembler(1)
    for index in range(1, 4097):
        assembler.feed(_packet(1 + index * 1400, b"x" * 1400))
    assert len(state.cache) == 46
    assert state.cached_bytes == 64400
    assert assembler.stats["out_of_window"] == 4050
    assert assembler.send_fragment_ack.call_args.args[2] == 1


def test_reordered_packets_are_reassembled_across_uint32_wrap():
    assembler, state = _assembler(0xFFFFFFF0)
    inner = build_rb_data_packet(payload=b"media", src_id=3, dest_id=4, seq=1)
    assembler.feed(_packet(0x10, inner[32:]))
    assembler.feed(_packet(0xFFFFFFF0, inner[:32]))
    assert not state.cache and state.cached_bytes == 0
    assert not state.buffer
    assert state.next_local_id == (0xFFFFFFF0 + len(inner)) & 0xFFFFFFFF
    assert assembler.handle_wrapped.call_args.args[0].inner_packet == inner
    assembler.feed(_packet(0xFFFFFFF0, inner[:32]))
    assert not state.cache and state.cached_bytes == 0
    assert assembler.stats["replayed"] == 1


@pytest.mark.parametrize("limit", ["packets", "bytes"])
def test_receive_cache_overflow_is_explicit_and_does_not_replace_data(
    limit, monkeypatch
):
    monkeypatch.setattr(
        stream_module,
        (
            "MAX_RECEIVE_CACHE_PACKETS"
            if limit == "packets"
            else "MAX_RECEIVE_CACHE_BYTES"
        ),
        1,
    )
    assembler, state = _assembler()
    assembler.feed(_packet(101, b"x"))
    assembler.feed(_packet(101, b"x"))
    assert state.cached_bytes == 1
    assert assembler.stats["cache_duplicates"] == 1
    with pytest.raises(QuiiConnectionError, match="receive cache limit"):
        assembler.feed(_packet(102, b"y"))
    assert state.cache == {101: b"x"} and state.cached_bytes == 1
