import queue
import struct
import threading
from unittest.mock import Mock

import pytest

from quii_helper import AutonomousConfig
from quii_helper.protocols.p2p.models import (
    P2PConnectResponse,
    ParsedP2PTestResponse,
)
from quii_helper.protocols.rbudp.core.rb_data_packets import (
    build_rb_data_packet,
)
from quii_helper.protocols.rbudp.fragments.stream import (
    RbUdpWrappedFragmentStream,
)
from quii_helper.protocols.rbudp.receive import payload_queue
from quii_helper.protocols.rbudp.receive import stream as stream_module
from quii_helper.protocols.rbudp.receive.loop import RbUdpReceiveLoop
from quii_helper.protocols.rbudp.receive.payload_queue import RbUdpPayloadQueue
from quii_helper.protocols.rbudp.receive.stream_state import (
    RbUdpReceiveStreamState,
)
from quii_helper.protocols.rbudp.tunnel.session import RbUdpQuiiTunnel
from quii_helper.support.errors import QuiiConnectionError


def _tunnel():
    return RbUdpQuiiTunnel(
        AutonomousConfig(),
        P2PConnectResponse(),
        ParsedP2PTestResponse(
            result_code=0,
            session_flag="test",
            address="127.0.0.1",
            port=1,
            status_code=0,
            test_id=0,
        ),
        request_session_id=1,
    )


def test_queue_preserves_fifo_metadata_and_byte_budget(monkeypatch):
    monkeypatch.setattr(payload_queue, "MAX_PENDING_PAYLOAD_BYTES", 4)
    packets = RbUdpPayloadQueue()
    packets.queue_payload(b"1234", source="test", lane=2)
    assert packets.get_nowait() == {
        "payload": b"1234",
        "source": "test",
        "meta": {"lane": 2},
    }
    packets.queue_payload(b"5678", source="test")
    assert packets.recv_payload(timeout=0) == b"5678"
    with pytest.raises(queue.Empty):
        packets.recv_packet(timeout=0)


@pytest.mark.parametrize("limit", ["bytes", "packets"])
def test_queue_overflow_is_terminal_and_does_not_silently_drop(
    limit, monkeypatch
):
    monkeypatch.setattr(
        payload_queue,
        (
            "MAX_PENDING_PAYLOAD_BYTES"
            if limit == "bytes"
            else "MAX_PENDING_PAYLOAD_PACKETS"
        ),
        1,
    )
    tunnel = _tunnel()
    tunnel._queue_payload(b"x", source="test")
    with pytest.raises(QuiiConnectionError, match="consumer is too slow"):
        tunnel._queue_payload(b"y", source="test")
    assert tunnel._stop.is_set()
    assert tunnel._payload_queue._pending_bytes == 0
    with pytest.raises(QuiiConnectionError, match="consumer is too slow"):
        tunnel.recv_packet(timeout=0)


def test_receiver_failure_wakes_all_blocked_readers():
    packets = RbUdpPayloadQueue()
    ready = threading.Barrier(3)
    errors = []

    def read():
        ready.wait()
        try:
            packets.recv_packet(timeout=10)
        except QuiiConnectionError as exc:
            errors.append(exc)

    readers = [threading.Thread(target=read) for _ in range(2)]
    for reader in readers:
        reader.start()
    ready.wait()
    cause = OSError("synthetic failure")
    packets.fail(cause)
    for reader in readers:
        reader.join(1)
        assert not reader.is_alive()
    assert len(errors) == 2
    assert all(error.__cause__ is cause for error in errors)


@pytest.mark.parametrize(
    "failure",
    [OSError("receive failed"), RuntimeError("handler failed"), None],
)
def test_tunnel_reports_terminal_receiver_failure(failure):
    tunnel = _tunnel()
    tunnel._receive_loop_runner = Mock()
    tunnel._receive_loop_runner.run_loop.side_effect = failure
    tunnel._receive_loop()
    assert tunnel._stop.is_set()
    with pytest.raises(QuiiConnectionError, match="RBUDP receiver"):
        tunnel.recv_packet(timeout=0)


def test_normal_shutdown_does_not_report_receiver_failure():
    tunnel = _tunnel()
    tunnel._stop.set()
    tunnel._receive_loop_runner = Mock()
    tunnel._receive_loop_runner.run_loop.side_effect = OSError("closed")
    tunnel._receive_loop()
    with pytest.raises(queue.Empty):
        tunnel.recv_packet(timeout=0)


def test_receive_loop_does_not_swallow_socket_failure():
    tunnel = _tunnel()
    tunnel._udp_sock = Mock()
    tunnel._udp_sock.recvfrom.side_effect = OSError("synthetic failure")
    with pytest.raises(OSError, match="synthetic failure"):
        RbUdpReceiveLoop(tunnel).run_loop()


def test_start_reports_receiver_failure_instead_of_timeout():
    tunnel = _tunnel()
    tunnel._lifecycle = Mock()
    tunnel._lifecycle.start.side_effect = TimeoutError("connect timeout")
    tunnel._payload_queue.fail(OSError("receive failed"))
    with pytest.raises(QuiiConnectionError, match="receive failed"):
        tunnel.start()


def test_failure_discards_stale_payloads_and_preserves_first_cause():
    packets = RbUdpPayloadQueue()
    packets.queue_payload(b"old", source="test")
    cause = OSError("first failure")
    packets.fail(cause)
    packets.fail(OSError("second failure"))
    with pytest.raises(QuiiConnectionError, match="first failure") as error:
        packets.recv_packet(timeout=0)
    assert error.value.__cause__ is cause
    assert packets._pending_bytes == 0
    assert not packets._packets


def test_negative_receive_timeout_is_rejected():
    with pytest.raises(ValueError):
        RbUdpPayloadQueue().recv_packet(timeout=-1)


def test_failed_queue_cannot_prevent_close_with_legacy_partial_fragments():
    tunnel = _tunnel()
    sock = Mock()
    tunnel._udp_sock = sock
    tunnel._threads = Mock()
    stream = RbUdpWrappedFragmentStream.from_start_packet(
        struct.pack("<6I2H", 0xFFABEFC1, 1, 2, 1, 1, 0x1900, 0, 31) + b"abc",
        inner_total_length=100,
    )
    tunnel._wrapped_fragments.streams[stream.key] = stream
    tunnel._payload_queue.fail(OSError("synthetic receiver failure"))
    with pytest.raises(
        QuiiConnectionError, match="synthetic receiver failure"
    ):
        tunnel.close()
    sock.close.assert_called_once()
    tunnel._threads.join_all.assert_called_once()
    assert tunnel._udp_sock is None
    assert not tunnel._wrapped_fragments.streams
    tunnel.close()
    sock.close.assert_called_once()


def test_receive_cache_failure_reaches_consumers_and_allows_cleanup(
    monkeypatch,
):
    monkeypatch.setattr(stream_module, "MAX_RECEIVE_CACHE_BYTES", 1)
    tunnel = _tunnel()
    sock = Mock()
    tunnel._udp_sock = sock
    lane = tunnel._lane_states[0]
    word4 = int(lane["bootstrap_word8"])
    tunnel._receive_streams.streams[int(lane["src_id"])] = (
        RbUdpReceiveStreamState(
            word4=word4,
            word8=2,
            next_local_id=100,
        )
    )
    sock.recvfrom.side_effect = [
        (
            struct.pack("<6I2H", 0xFFABEFC1, word4, 2, seq, 1, 0x1900, 0, 29)
            + b"x",
            ("127.0.0.1", 1),
        )
        for seq in (101, 102)
    ]
    tunnel._receive_loop()
    assert tunnel._stop.is_set()
    with pytest.raises(QuiiConnectionError) as error:
        tunnel.recv_packet(timeout=0)
    assert "receive cache limit" in str(error.value.__cause__.__cause__)
    tunnel.close()
    sock.close.assert_called_once()


def _data_packet(word4, seq, payload):
    return (
        struct.pack(
            "<6I2H",
            0xFFABEFC1,
            word4,
            0x3D000022,
            seq,
            1,
            0x1900,
            0,
            28 + len(payload),
        )
        + payload
    )


def test_unknown_lane_in_receive_loop_never_reaches_payload_queue():
    tunnel = _tunnel()
    tunnel._udp_sock = Mock()
    inner = build_rb_data_packet(
        payload=b"unrelated", src_id=3, dest_id=4, seq=1
    )
    received = iter([_data_packet(123, 1, inner)])

    def recv(_size):
        try:
            return next(received), ("192.0.2.123", 31337)
        except StopIteration:
            tunnel._stop.set()
            raise TimeoutError

    tunnel._udp_sock.recvfrom.side_effect = recv
    RbUdpReceiveLoop(tunnel).run_loop()
    assert not tunnel._receive_streams.streams
    tunnel._udp_sock.sendto.assert_not_called()
    with pytest.raises(queue.Empty):
        tunnel.recv_packet(timeout=0)


def test_real_ack_path_keeps_window_open_while_large_frame_is_incomplete():
    tunnel = _tunnel()
    tunnel._udp_sock = Mock()
    lane = tunnel._lane_states[0]
    word4 = int(lane["bootstrap_word8"])
    payload = b"x" * 80000
    inner = build_rb_data_packet(payload=payload, src_id=3, dest_id=4, seq=1)
    sent, credit = 0, 65535
    while sent < len(inner):
        assert credit > 0
        length = min(1400, credit, len(inner) - sent)
        tunnel._receive_streams.feed(
            _data_packet(word4, 1 + sent, inner[sent : sent + length])
        )
        sent += length
        ack = tunnel._udp_sock.sendto.call_args.args[0]
        assert int.from_bytes(ack[16:20], "little") == 1 + sent
        credit = int.from_bytes(ack[20:24], "little") >> 16
    assert tunnel.recv_payload(timeout=0) == payload
    assert not tunnel._receive_streams.has_pending()


def test_corrupt_kcp_tail_stops_receiver_and_wakes_consumer():
    tunnel = _tunnel()
    sock = Mock()
    tunnel._udp_sock = sock
    inner = build_rb_data_packet(payload=b"valid", src_id=3, dest_id=4, seq=1)
    tunnel._handle_wrapped = Mock(wraps=tunnel._handle_wrapped)
    tunnel._receive_streams.handle_wrapped = tunnel._handle_wrapped
    sock.recvfrom.return_value = (
        _data_packet(
            int(tunnel._lane_states[0]["bootstrap_word8"]),
            1,
            inner + b"INVALID_HEADER!!",
        ),
        ("127.0.0.1", 1),
    )
    tunnel._receive_loop()
    assert tunnel._stop.is_set()
    tunnel._handle_wrapped.assert_called_once()
    assert tunnel._receive_streams.stats["frames"] == 1
    assert tunnel._receive_streams.stats["invalid"] == 1
    with pytest.raises(QuiiConnectionError) as error:
        tunnel.recv_packet(timeout=0)
    assert "invalid KCP receive stream" in str(error.value.__cause__.__cause__)
    assert isinstance(error.value.__cause__.__cause__.__cause__, ValueError)
    tunnel.close()
    sock.close.assert_called_once()
